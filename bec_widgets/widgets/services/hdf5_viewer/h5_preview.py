"""
The preview of the HDF5 viewer: one dataset as a map, a line, an image, a table or a value.

Only what is on screen is read: a reduced overview of a long signal and then the rows in
view, one frame of a stack, the visible window of a table, the points of a map. The plots
are the BEC Waveform, Image, ScatterWaveform and Heatmap widgets, given the file's data.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import numpy as np
from bec_lib.endpoints import MessageEndpoints
from bec_qthemes import material_icon
from qtpy.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer, Signal
from qtpy.QtGui import QFont, QGuiApplication, QTransform
from qtpy.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTableView,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.widgets.services.hdf5_viewer import h5_reader
from bec_widgets.widgets.services.hdf5_viewer.h5_reader import (
    CurveData,
    FrameData,
    H5Details,
    H5Node,
    H5ReadError,
    MapData,
    ScanAxes,
    TableData,
)
from bec_widgets.widgets.services.hdf5_viewer.h5_service import H5Service, ReadContext
from bec_widgets.widgets.services.hdf5_viewer.h5_tree import can_keep
from bec_widgets.widgets.services.hdf5_viewer.map_view import GRID_SCANS
from bec_widgets.widgets.services.hdf5_viewer.scan_list import series_color
from bec_widgets.widgets.services.hdf5_viewer.style import mute

#: Rows and columns of the table that are read in one piece.
TABLE_BLOCK_ROWS = 200
TABLE_BLOCK_COLS = 50
#: Pieces of the table that are kept in memory.
TABLE_BLOCKS_KEPT = 48
#: Rows the table offers at once; longer datasets are paged with "From row".
TABLE_MAX_ROWS = 1_000_000
#: Datasets that are not numbers are shown as one value up to this many elements.
VALUE_MAX_ELEMENTS = 64
#: Pause before the bar that shows a running read appears.
PROGRESS_DELAY_MS = 200
#: Datasets that can be kept on the plot besides the selected one.
KEPT_MAX = 8

VIEW_LABELS = {"map": "Map", "line": "Line", "image": "Image", "table": "Table", "value": "Value"}
VIEW_ICONS = {
    "map": "scatter_plot",
    "line": "show_chart",
    "image": "image",
    "table": "table_rows",
    "value": "tag",
}
#: What the plot-against box holds besides datasets: the scan's axes and the time.
SCAN_AXES = "@axes"
TIME = "@time"
#: The x axes of no dataset of the file, named as the Waveform and the X field name them.
INDEX_TEXT = "Index"
TIME_TEXT = "Timestamp"
TIME_LABEL = "Timestamp (s since the first point)"


def _grid_levels(values: np.ndarray) -> np.ndarray | None:
    """The evenly spaced levels the values lie on, or None when they lie on none."""
    finite = np.sort(values[np.isfinite(values)])
    if finite.size < 2:
        return None
    span = float(finite[-1] - finite[0])
    if span <= 0:
        return None
    # Positions closer than a thousandth of the span are one level: readbacks jitter.
    breaks = np.flatnonzero(np.diff(finite) > span * 1e-3) + 1
    levels = np.array([chunk.mean() for chunk in np.split(finite, breaks)])
    if levels.size < 2 or not np.allclose(np.diff(levels), np.diff(levels).mean(), rtol=0.05):
        return None
    return levels


def grid_image(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, QTransform] | None:
    """
    The values of a scan whose points lie on a regular grid, one pixel per point, as the
    Heatmap draws a grid scan: no interpolation, missing points left empty.

    Args:
        x (np.ndarray): x position of each point.
        y (np.ndarray): y position of each point.
        z (np.ndarray): Value of each point.

    Returns:
        tuple[np.ndarray, QTransform] | None: The image, indexed [x, y], and the transform to
        the positions; None when the points do not lie on a regular grid.
    """
    x_levels, y_levels = _grid_levels(x), _grid_levels(y)
    if x_levels is None or y_levels is None or x_levels.size * y_levels.size > 2 * len(z):
        return None
    step_x = float(x_levels[-1] - x_levels[0]) / (x_levels.size - 1)
    step_y = float(y_levels[-1] - y_levels[0]) / (y_levels.size - 1)
    image = np.full((x_levels.size, y_levels.size), np.nan)
    inside = np.isfinite(x) & np.isfinite(y)
    x_index = np.clip(
        np.round((x[inside] - x_levels[0]) / step_x).astype(int), 0, x_levels.size - 1
    )
    y_index = np.clip(
        np.round((y[inside] - y_levels[0]) / step_y).astype(int), 0, y_levels.size - 1
    )
    image[x_index, y_index] = z[inside]
    transform = QTransform()
    transform.scale(step_x, step_y)
    transform.translate(x_levels[0] / step_x - 0.5, y_levels[0] / step_y - 0.5)
    return image, transform


def dataset_name(path: str, with_parent: bool = False) -> str:
    """
    The short name of a dataset, as the legend and the chips name it: a BEC ``value``
    dataset is named by its signal group.

    Args:
        path (str): Path of the dataset inside its file.
        with_parent (bool): Put the name of the group above in front, for two equal names.

    Returns:
        str: E.g. ``bpm4i`` for ``.../bpm4i/bpm4i/value``, or ``data/samx`` with its parent.
    """
    parts = [part for part in path.split("/") if part]
    if not parts:
        return path
    at = len(parts) - 2 if parts[-1] == "value" and len(parts) > 1 else len(parts) - 1
    if with_parent and at > 0:
        return f"{parts[at - 1]}/{parts[at]}"
    return parts[at]


def views_for(node: H5Node) -> list[str]:
    """
    The views a dataset can be shown in, the best one first.

    Args:
        node (H5Node): The dataset.

    Returns:
        list[str]: Any of ``line``, ``image``, ``table`` and ``value``.
    """
    if node.kind != "dataset":
        return []
    if not node.is_numeric:
        return ["value"] if node.size <= VALUE_MAX_ELEMENTS else ["table"]
    if node.size <= 1:
        return ["value"]
    if node.ndim == 1:
        return ["line", "table"]
    return ["image", "line", "table"]


class StatePage(QWidget):
    """A centred message with an icon and up to two actions, shown in place of content."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.icon = QLabel(self)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel(self)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setWordWrap(True)
        font = self.title.font()
        font.setPointSizeF(font.pointSizeF() * 1.15)
        font.setWeight(QFont.Weight.DemiBold)
        self.title.setFont(font)
        self.text = QLabel(self)
        self.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text.setMaximumWidth(480)
        mute(self.text)
        text_row = QHBoxLayout()
        text_row.addStretch(1)
        text_row.addWidget(self.text, 20)
        text_row.addStretch(1)
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(8)
        self._actions: list[QPushButton] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addStretch(1)
        layout.addWidget(self.icon)
        layout.addWidget(self.title)
        layout.addLayout(text_row)
        layout.addSpacing(4)
        layout.addLayout(self.buttons)
        layout.addStretch(1)

    def show_state(
        self,
        icon: str,
        title: str,
        text: str = "",
        actions: tuple[tuple[str, Callable[[], None]], ...] = (),
        detail: str = "",
    ) -> None:
        """
        Fill the page.

        Args:
            icon (str): Name of a Material icon.
            title (str): What is the case, in a few words.
            text (str): What it means and what can be done.
            actions (tuple[tuple[str, Callable[[], None]], ...]): Label and callback of up to
                two buttons; the first one is the main action.
            detail (str): The tooltip of the text, for example the error a library gave.
        """
        self.icon.setPixmap(material_icon(icon, size=(40, 40)))
        self.title.setText(title)
        self.text.setText(text)
        self.text.setToolTip(detail)
        self.text.setVisible(bool(text))
        for button in self._actions:
            self.buttons.removeWidget(button)
            # Gone from sight at once: deleteLater only acts once the event loop runs again.
            button.hide()
            button.deleteLater()
        self._actions = []
        while self.buttons.count():
            self.buttons.takeAt(0)
        self.buttons.addStretch(1)
        for index, (label, callback) in enumerate(actions):
            button = QPushButton(label, self)
            button.setDefault(index == 0)
            # A click focuses it on every platform (macOS buttons take Tab focus only), so the
            # page can hand the focus on to what replaces it.
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.clicked.connect(lambda _checked=False, callback=callback: callback())
            self.buttons.addWidget(button)
            self._actions.append(button)
        self.buttons.addStretch(1)


def error_state(
    error: H5ReadError,
    retry: Callable[[], None],
    read_anyway: Callable[[], None] | None = None,
    waiting: bool = False,
) -> tuple[str, str, str, tuple[tuple[str, Callable[[], None]], ...]]:
    """
    Icon, title, text and actions that explain a failed read.

    Args:
        error (H5ReadError): The error.
        retry (Callable[[], None]): Tries the read again.
        read_anyway (Callable[[], None] | None): Reads a file although it is being written.
        waiting (bool): Whether a file that is being written is looked at again by itself.

    Returns:
        tuple: Arguments for :meth:`StatePage.show_state`.
    """
    name = Path(error.file_path).name if error.file_path else "The file"
    path = error.file_path

    def copy_path():
        QGuiApplication.clipboard().setText(path)

    if error.kind == "busy" and error.other_reader:
        return (
            "hourglass_top",
            "In use at this moment",
            f"Another part of this program is reading {name} right now. "
            + ("It opens here by itself in a moment." if waiting else "Check again in a moment."),
            (("Check again", retry),),
        )
    if error.kind == "busy":
        actions: tuple = (("Check again", retry),)
        if read_anyway is not None:
            actions += (("Read it anyway", read_anyway),)
        then = (
            "It opens here by itself as soon as the writer is done."
            if waiting
            else "It is not read while it is written, so that nothing gets in the writer's way."
        )
        return (
            "hourglass_top",
            "Still being written",
            f"{name} changed a moment ago, or a program has it open for writing. {then}",
            actions,
        )
    if error.kind == "missing":
        return (
            "search_off",
            "Not found",
            f"{error.message}.",
            (("Try again", retry), ("Copy file path", copy_path)),
        )
    if error.kind == "denied":
        return ("lock", "No permission", f"{error.message}.", (("Try again", retry),))
    return (
        "error",
        "This could not be read",
        f"{error.message}.",
        (("Try again", retry), ("Copy file path", copy_path)),
    )


class IndexBar(QWidget):
    """Sliders that pick the position along the dimensions a view does not show."""

    #: Emitted with the positions, one per slider, shortly after the last change.
    index_changed = Signal(tuple)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._spins: list[QSpinBox] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(60)
        self._timer.timeout.connect(lambda: self.index_changed.emit(self.index()))

    def set_dimensions(self, labels: list[str], sizes: list[int], index: list[int]) -> None:
        """
        Rebuild the sliders.

        Args:
            labels (list[str]): Name of each dimension.
            sizes (list[int]): Length of each dimension.
            index (list[int]): Position to start at.
        """
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._spins = []
        for label, size, value in zip(labels, sizes, index):
            name = QLabel(label, self)
            slider = QSlider(Qt.Orientation.Horizontal, self)
            slider.setRange(0, max(0, size - 1))
            slider.setValue(value)
            slider.setMinimumWidth(120)
            slider.setAccessibleName(label)
            spin = QSpinBox(self)
            spin.setRange(0, max(0, size - 1))
            spin.setValue(value)
            spin.setAccessibleName(label)
            spin.setKeyboardTracking(False)
            count = QLabel(f"of {h5_reader.format_count(size)}", self)
            mute(count)
            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            spin.valueChanged.connect(lambda _value: self._timer.start())
            for widget in (name, slider, spin, count):
                self._layout.addWidget(widget)
            self._layout.setStretchFactor(slider, 1)
            self._layout.addSpacing(10)
            self._spins.append(spin)
        self._layout.addStretch(0 if self._spins else 1)
        self.setVisible(bool(self._spins))

    def index(self) -> tuple[int, ...]:
        """
        The positions of the sliders.

        Returns:
            tuple[int, ...]: One position per dimension.
        """
        return tuple(spin.value() for spin in self._spins)


class H5TableModel(QAbstractTableModel):
    """Table over a dataset that reads the cells in view, a block at a time."""

    def __init__(self, service: H5Service, parent=None):
        super().__init__(parent)
        self._service = service
        self._node: H5Node | None = None
        self._index: tuple[int, ...] = ()
        self._rows = 0
        self._cols = 0
        self._row_offset = 0
        self._blocks: OrderedDict[tuple[int, int], list[list[str]]] = OrderedDict()
        self._pending: set[tuple[int, int]] = set()
        self._generation = 0
        self._channel = f"table-{id(self)}"
        self.error: H5ReadError | None = None

    def set_source(self, node: H5Node | None, index: tuple[int, ...], row_offset: int = 0):
        """
        Show a dataset, or nothing.

        Args:
            node (H5Node | None): The dataset.
            index (tuple[int, ...]): Position along the dimensions before the last two.
            row_offset (int): First row of the dataset that the table shows.
        """
        self.beginResetModel()
        self._generation += 1
        self._service.cancel_all(self._channel)
        self._node = node
        self._index = index
        self._row_offset = row_offset
        self._blocks.clear()
        self._pending.clear()
        self.error = None
        shape = node.shape if node is not None and node.shape is not None else ()
        if node is None:
            self._rows, self._cols = 0, 0
        elif len(shape) == 0:
            self._rows, self._cols = 1, 1
        elif len(shape) == 1:
            self._rows, self._cols = shape[0], 1
        else:
            self._rows, self._cols = shape[-2], shape[-1]
        self._rows = max(0, min(self._rows - row_offset, TABLE_MAX_ROWS))
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else self._rows

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else self._cols

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Vertical:
            return str(section + self._row_offset)
        return str(section) if self._cols > 1 else "Value"

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if self._node is not None and self._node.is_numeric:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        key = (index.row() // TABLE_BLOCK_ROWS, index.column() // TABLE_BLOCK_COLS)
        block = self._blocks.get(key)
        if block is None:
            self._request(key)
            return "…"
        try:
            return block[index.row() % TABLE_BLOCK_ROWS][index.column() % TABLE_BLOCK_COLS]
        except IndexError:
            return ""

    def _request(self, key: tuple[int, int]) -> None:
        if key in self._pending or self._node is None or self.error is not None:
            return
        self._pending.add(key)
        node, lead, generation = self._node, self._index, self._generation
        row_start = key[0] * TABLE_BLOCK_ROWS + self._row_offset
        col_start = key[1] * TABLE_BLOCK_COLS

        def read(_ctx: ReadContext) -> TableData:
            return h5_reader.read_table(
                node.file_path,
                node.path,
                lead,
                row_start,
                row_start + TABLE_BLOCK_ROWS,
                col_start,
                col_start + TABLE_BLOCK_COLS,
            )

        self._service.request(
            f"{self._channel}-{key[0]}-{key[1]}",
            node.file_path,
            read,
            partial(self._on_block, generation, key),
            partial(self._on_error, generation),
        )

    def _on_block(self, generation: int, key: tuple[int, int], table: TableData) -> None:
        if generation != self._generation:
            return
        self._pending.discard(key)
        self._blocks[key] = table.cells
        while len(self._blocks) > TABLE_BLOCKS_KEPT:
            self._blocks.popitem(last=False)
        top = key[0] * TABLE_BLOCK_ROWS
        left = key[1] * TABLE_BLOCK_COLS
        bottom = min(self._rows, top + TABLE_BLOCK_ROWS) - 1
        right = min(self._cols, left + TABLE_BLOCK_COLS) - 1
        if bottom >= top and right >= left:
            self.dataChanged.emit(self.index(top, left), self.index(bottom, right))

    def _on_error(self, generation: int, error: H5ReadError) -> None:
        if generation != self._generation or self.error is not None:
            return
        self.error = error
        self.modelReset.emit()

    def cleanup(self) -> None:
        """Drop the pending reads."""
        self._generation += 1
        self._service.cancel_all(self._channel)


class H5DetailsPanel(QTreeWidget):
    """Lists how a node is stored and its attributes."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setColumnCount(2)
        self.setHeaderLabels(["Detail", "Value"])
        self.setRootIsDecorated(False)
        self.setIndentation(10)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.setAccessibleName("Details of the selected entry")
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setStretchLastSection(True)
        self.set_details(None)

    def _section(self, title: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem(self, [title, ""])
        font = item.font(0)
        font.setWeight(QFont.Weight.DemiBold)
        item.setFont(0, font)
        item.setFirstColumnSpanned(True)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        item.setExpanded(True)
        return item

    def _row(self, parent: QTreeWidgetItem, name: str, value: str) -> None:
        item = QTreeWidgetItem(parent, [name, value])
        item.setToolTip(1, value)

    def set_details(self, details: H5Details | None) -> None:
        """
        Show the details of a node, or a hint when there is none.

        Args:
            details (H5Details | None): The details.
        """
        self.clear()
        if details is None:
            hint = QTreeWidgetItem(self, ["Pick an entry to see how it is stored."])
            hint.setFirstColumnSpanned(True)
            hint.setFlags(Qt.ItemFlag.NoItemFlags)
            return
        node = details.node
        stored = self._section("Stored as")
        self._row(stored, "Path", node.path)
        self._row(stored, "File", Path(node.file_path).name)
        if node.kind == "dataset":
            self._row(stored, "Shape", h5_reader.format_shape(node.shape))
            self._row(stored, "Type", node.dtype)
            if node.units:
                self._row(stored, "Units", node.units)
            size = h5_reader.format_bytes(details.logical_bytes)
            if details.stored_bytes and details.stored_bytes != details.logical_bytes:
                size += f", {h5_reader.format_bytes(details.stored_bytes)} in the file"
            self._row(stored, "Size", size)
            chunks = h5_reader.format_shape(details.chunks) if details.chunks else "one block"
            self._row(stored, "Chunks", chunks)
            self._row(stored, "Compression", details.compression or "none")
        elif node.kind == "group":
            count = node.n_children or 0
            self._row(stored, "Contains", "1 item" if count == 1 else f"{count} items")
        attributes = self._section(
            f"Attributes ({len(details.attributes)})" if details.attributes else "No attributes"
        )
        for key, value in details.attributes.items():
            self._row(attributes, key, value)
        self.resizeColumnToContents(0)


@dataclass
class _Kept:
    """A dataset kept on the plot of the Line view, looked up by its path in the shown file."""

    path: str
    #: Its place in the colours of the plot; the selected dataset has the first.
    slot: int
    #: What the file says about it, once looked up.
    details: H5Details | None = None
    #: Why it is not in the shown file, or empty.
    missing: str = ""
    looking: bool = False
    #: Its rows against the x axis they were read for: (file, x path, relative).
    data: CurveData | None = None
    data_key: tuple | None = None
    #: Why the shown x axis does not fit it, or empty.
    x_problem: str = ""
    #: Why its rows could not be read, or empty.
    read_problem: str = ""

    def problem(self, line: bool) -> str:
        """Why it is not drawn, in the Line view or not."""
        return self.missing or (self.x_problem or self.read_problem if line else "")


@dataclass(frozen=True)
class LineSource:
    """What the Line view of the preview shows."""

    node: H5Node
    #: Position along the axes before the last one, for a row of a stack.
    index: tuple[int, ...]
    #: Path of the dataset used as x axis, or empty for the row number.
    x_path: str
    x_label: str


@dataclass(frozen=True)
class KeptChip:
    """A dataset kept on the plot, as the box of the File tab shows it."""

    #: Path of the dataset inside the file.
    path: str
    #: Short name, as in the legend.
    label: str
    #: Colour of its curve; empty while it has none.
    color: str = ""
    #: Why it is not drawn, or empty when it is (or is still being read).
    problem: str = ""
    #: The colour it keeps for its curve, also while it is not drawn.
    slot_color: str = ""


@dataclass(frozen=True)
class XEntry:
    """Something the Line view can plot against, as the X field of the File tab lists it."""

    #: What :meth:`H5Preview.choose_x` takes: SCAN_AXES, TIME, "" or the path of a dataset.
    data: str
    text: str
    enabled: bool = True
    tip: str = ""


@dataclass(frozen=True)
class KeptLine:
    """A kept dataset the Line view draws next to the selected one."""

    node: H5Node
    #: Path of the dataset used as x axis, or None for the row number.
    x_path: str | None
    #: Whether the x values count from the first.
    relative: bool
    #: Its name in the legend.
    label: str


class H5Preview(QWidget):
    """Shows the dataset that is selected in the tree."""

    #: The details of the shown node were read: an :class:`H5Details`, or None.
    details_changed = Signal(object)
    #: What is shown changed: the node, the view, the row of a stack or the x axis.
    shown_changed = Signal()
    #: Datasets were kept on the plot or taken off it.
    kept_changed = Signal()
    #: What the box of the File tab shows changed: the selection, its view, the x axis or the
    #: kept datasets.
    roles_changed = Signal()
    #: What the Line view plots against was chosen, by the user or with :meth:`set_x`.
    x_changed = Signal()

    def __init__(self, service: H5Service, client=None, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = service
        self._client = client
        self._channel = f"preview-{id(self)}"
        self._node: H5Node | None = None
        self._details: H5Details | None = None
        self._token = 0
        self._view = ""
        self._preferred: dict[int, str] = {}
        #: What the user chose to plot against, for the viewer's lifetime: SCAN_AXES, TIME,
        #: "" for the row number, or the name of a dataset. None until they choose.
        self._x_choice: str | None = None
        #: Datasets chosen as the x axis by their path, e.g. a signal of the scan, with their
        #: name and number of values: path -> (name, length).
        self._x_datasets: dict[str, tuple[str, int]] = {}
        #: Why the remembered choice does not fit the shown dataset, or empty.
        self._x_note = ""
        self._map_data: MapData | None = None
        self._map_scatter = None
        self._map_heatmap = None
        #: The default plot shown for a selected group, or None.
        self._default: h5_reader.DefaultPlot | None = None
        self._index: list[int] = []
        self._overview: CurveData | None = None
        self._detail_bins: tuple[int, int] | None = None
        self._curve = None
        self._waveform = None
        self._image = None
        self._fresh_image = True
        #: The frame the Image view shows, as read.
        self._frame: FrameData | None = None
        #: The datasets kept on the Line view's plot besides the selected one, by path, in
        #: the order they were kept; drawn from the file :attr:`_kept_file`.
        self._kept: OrderedDict[str, _Kept] = OrderedDict()
        self._kept_file = ""
        self._kept_channel = f"kept-{id(self)}"
        self._kept_generation = 0
        #: Whether the values of the shown and the kept datasets are read: not while the
        #: preview is out of sight. Their details are read all the same.
        self._reading = True
        #: Whether a read was left out while :attr:`_reading` is off.
        self._unread = False
        #: The curves of the kept datasets on the plot: path -> (curve, label).
        self._kept_curves: dict[str, tuple] = {}
        #: Colours of kept datasets given from outside, e.g. those of the Signals tab's curves.
        self._fixed_colors: dict[str, str] = {}
        #: What the chips show of each kept dataset's colour, as told with kept_changed.
        self._kept_colors: dict[str, str] = {}
        #: Name of the y axis while the selected dataset is drawn alone.
        self._y_name = ""
        self._kept_note = ""
        #: What the box shows of the kept datasets, as last told with roles_changed.
        self._kept_chips: list[KeptChip] = []
        self._kept_shown_note = ""

        # Header: what is shown, and the switch between the views
        self.name_label = QLabel(self)
        font = self.name_label.font()
        font.setWeight(QFont.Weight.DemiBold)
        self.name_label.setFont(font)
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.summary_label = QLabel(self)
        mute(self.summary_label)
        self.summary_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.view_group = QButtonGroup(self)
        self.view_group.setExclusive(True)
        self.view_buttons: dict[str, QToolButton] = {}
        header = self._header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(self.name_label)
        header.addWidget(self.summary_label, 1)
        for key in ("map", "line", "image", "table"):
            button = QToolButton(self)
            button.setText(VIEW_LABELS[key])
            button.setIcon(material_icon(VIEW_ICONS[key], convert_to_pixmap=False))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setObjectName(f"preview_{key}_button")
            button.setToolTip(f"Show as {VIEW_LABELS[key].lower()}")
            button.clicked.connect(partial(self._on_view_clicked, key))
            self.view_group.addButton(button)
            self.view_buttons[key] = button
            header.addWidget(button)

        # Mapping: which x axis, which frame
        self.x_label = QLabel("Plot against", self)
        self.x_combo = QComboBox(self)
        self.x_combo.setObjectName("plot_against_combo")
        self.x_combo.setAccessibleName("Plot against")
        self.x_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.x_combo.activated.connect(self._on_x_chosen)
        self.index_bar = IndexBar(self)
        self.index_bar.index_changed.connect(self._on_index_changed)
        self.row_label = QLabel("From row", self)
        self.row_spin = QSpinBox(self)
        self.row_spin.setAccessibleName("First row of the table")
        self.row_spin.setKeyboardTracking(False)
        self.row_spin.setGroupSeparatorShown(True)
        self.row_spin.setSingleStep(TABLE_MAX_ROWS)
        self.row_spin.valueChanged.connect(lambda _value: self._load())
        self.mapper = QWidget(self)
        mapper = QHBoxLayout(self.mapper)
        mapper.setContentsMargins(0, 0, 0, 0)
        mapper.setSpacing(6)
        mapper.addWidget(self.x_label)
        mapper.addWidget(self.x_combo)
        mapper.addWidget(self.row_label)
        mapper.addWidget(self.row_spin)
        mapper.addWidget(self.index_bar, 8)
        mapper.addStretch(1)

        self.progress = QProgressBar(self)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setAccessibleName("Reading from the file")
        self._progress_holder = QWidget(self)
        self._progress_holder.setFixedHeight(4)
        holder = QVBoxLayout(self._progress_holder)
        holder.setContentsMargins(0, 0, 0, 0)
        holder.addWidget(self.progress)
        self.progress.hide()
        self._progress_timer = QTimer(self)
        self._progress_timer.setSingleShot(True)
        self._progress_timer.setInterval(PROGRESS_DELAY_MS)
        self._progress_timer.timeout.connect(self.progress.show)

        # Content
        self.state_page = StatePage(self)
        self.line_page = QWidget(self)
        QVBoxLayout(self.line_page).setContentsMargins(0, 0, 0, 0)
        self.image_page = QWidget(self)
        QVBoxLayout(self.image_page).setContentsMargins(0, 0, 0, 0)
        self.map_page = QWidget(self)
        QVBoxLayout(self.map_page).setContentsMargins(0, 0, 0, 0)
        self.table_model = H5TableModel(service, self)
        self.table = QTableView(self)
        self.table.setModel(self.table_model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setAccessibleName("Values of the dataset")
        self.table.horizontalHeader().setDefaultSectionSize(110)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table_model.modelReset.connect(self._on_table_reset)
        self.value_view = QPlainTextEdit(self)
        self.value_view.setReadOnly(True)
        self.value_view.setAccessibleName("Value of the dataset")
        self.stack = QStackedWidget(self)
        for page in (
            self.state_page,
            self.line_page,
            self.image_page,
            self.map_page,
            self.table,
            self.value_view,
        ):
            self.stack.addWidget(page)

        self.info_label = QLabel(self)
        self.info_label.setWordWrap(True)
        mute(self.info_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self.mapper)
        layout.addWidget(self._progress_holder)
        layout.addWidget(self.stack, 1)
        layout.addWidget(self.info_label)

        self._range_timer = QTimer(self)
        self._range_timer.setSingleShot(True)
        self._range_timer.setInterval(250)
        self._range_timer.timeout.connect(self._load_rows_in_view)

        self.show_node(None)

    ################################################################################
    # Public interface
    ################################################################################

    @property
    def node(self) -> H5Node | None:
        """The node that is shown."""
        return self._node

    @property
    def default_plot(self) -> h5_reader.DefaultPlot | None:
        """The default plot of the selected group that is shown, or None."""
        return self._default

    @property
    def view(self) -> str:
        """The view that is shown: ``map``, ``line``, ``image``, ``table``, ``value`` or empty."""
        return self._view

    def add_header_widget(self, widget: QWidget) -> None:
        """
        Put a widget at the right end of the header, after the view buttons.

        Args:
            widget (QWidget): The widget, e.g. a button.
        """
        self._header.addWidget(widget)

    def line_source(self) -> LineSource | None:
        """
        What the Line view shows: the dataset, the row of a stack and the x axis.

        Returns:
            LineSource | None: The source, or None when the Line view of a dataset is not shown.
        """
        node = self._node
        if self._view != "line" or node is None or node.kind != "dataset":
            return None
        x_path, _relative, x_label = self._x_source()
        return LineSource(node=node, index=self._lead(1), x_path=x_path or "", x_label=x_label)

    @property
    def scan_axes(self) -> ScanAxes | None:
        """The axes the file names for the points of its scan, for the shown dataset."""
        return self._details.scan_axes if self._details is not None else None

    @property
    def x_choice(self) -> str | None:
        """
        What the user chose to plot against, remembered for the viewer's lifetime.

        Returns:
            str | None: ``@axes``, ``@time``, empty for the row number, the name of a dataset,
            or None before the user chose.
        """
        return self._x_choice

    @property
    def x_note(self) -> str:
        """Why the remembered choice is not used for the shown dataset, or empty."""
        return self._x_note

    def show_node(self, node: H5Node | None) -> None:
        """
        Show a node of a file, or the hint to pick one.

        Args:
            node (H5Node | None): The node. Links must be followed already.
        """
        self._token += 1
        self._service.cancel_all(self._channel)
        self._set_loading(False)
        self._range_timer.stop()
        self._node = node
        self._default = None
        self._details = None
        self._overview = None
        self._detail_bins = None
        self._curve = None
        self._map_data = None
        self._frame = None
        self._x_note = ""
        self._view = ""
        self._fresh_image = True
        self._index = [0] * (node.ndim if node is not None else 0)
        self.details_changed.emit(None)
        self.shown_changed.emit()
        self.table_model.set_source(None, ())
        self.info_label.clear()
        self._set_views([])
        self._set_mapper()
        self._update_kept()
        if node is None:
            self.name_label.clear()
            self.summary_label.clear()
            self._show_state(
                "data_object", "Nothing picked", "Pick a dataset in the tree to see its values."
            )
            return
        self.name_label.setText(node.name)
        self.summary_label.setText(self._summary(node))
        if node.kind == "broken":
            reason = node.link_path or "It points to something that does not exist."
            self._show_state("link_off", "Broken link", reason)
            return
        if node.kind != "dataset":
            count = node.n_children
            items = "" if count is None else ("1 item" if count == 1 else f"{count} items")
            self._show_state(
                "folder_open",
                f"A group with {items}" if items else "A group",
                "Pick a dataset inside it to see its values.",
            )
            if node.kind in ("file", "group"):
                self._request(
                    "default",
                    lambda _ctx: h5_reader.default_plot(node.file_path, node.path),
                    lambda plot: self._on_default_plot(node, plot),
                    quiet=True,
                )
        elif node.size == 0:
            self._show_state("data_array", "Empty dataset", "It holds no values.")
        self._request(
            "details",
            lambda _ctx: h5_reader.describe(node.file_path, node.path),
            self._on_details,
            quiet=node.kind != "dataset",
        )

    def reload(self) -> None:
        """Read the shown node again."""
        self.show_node(self._node)

    def set_reading(self, reading: bool) -> None:
        """
        Read the values of the shown dataset and of the kept ones, or leave them unread while
        the preview is out of sight. What is kept and what to plot against stay in step either
        way; the reads left out are made when reading is on again.

        Args:
            reading (bool): Whether to read.
        """
        if reading == self._reading:
            return
        self._reading = reading
        if not reading or not self._unread:
            return
        self._unread = False
        node = self._node
        if node is not None and node.kind == "dataset" and self._view:
            self._load()
        else:
            self._load_kept()

    def show_message(self, icon: str, title: str, text: str = "", actions: tuple = ()) -> None:
        """
        Show a message in place of a dataset.

        Args:
            icon (str): Name of a Material icon.
            title (str): What is the case, in a few words.
            text (str): What it means and what can be done.
            actions (tuple): Label and callback of up to two buttons.
        """
        self.show_node(None)
        self._show_state(icon, title, text, actions)

    def show_file_error(
        self, error: H5ReadError, retry, read_anyway=None, waiting: bool = False
    ) -> None:
        """
        Explain why a file could not be opened, in place of a dataset.

        Args:
            error (H5ReadError): The error.
            retry (Callable[[], None]): Opens the file again.
            read_anyway (Callable[[], None] | None): Opens a file that is being written.
            waiting (bool): Whether the file is looked at again by itself.
        """
        self.show_node(None)
        self._show_state(*error_state(error, retry, read_anyway, waiting))

    def cleanup(self) -> None:
        """Stop the timers and drop the pending reads."""
        self._token += 1
        self._range_timer.stop()
        self._progress_timer.stop()
        self.table_model.cleanup()
        self._service.cancel_all(self._channel)
        self._kept_generation += 1
        self._service.cancel_all(self._kept_channel)
        for plot in (self._map_scatter, self._map_heatmap):
            if plot is not None:
                plot.close()
                plot.deleteLater()
        self._map_scatter = self._map_heatmap = None

    ################################################################################
    # Plumbing
    ################################################################################

    @staticmethod
    def _summary(node: H5Node) -> str:
        if node.kind != "dataset":
            return node.nx_class
        parts = [h5_reader.format_shape(node.shape), node.dtype]
        if node.units:
            parts.append(node.units)
        return "  ·  ".join(part for part in parts if part)

    def _request(
        self,
        name: str,
        read: Callable[[ReadContext], object],
        on_done: Callable[[object], None],
        quiet: bool = False,
    ) -> None:
        """Ask for a read on behalf of the shown node; stale answers are dropped."""
        if self._node is None:
            return
        token = self._token
        if not quiet:
            self._set_loading(True)

        def done(result):
            if token != self._token:
                return
            self._set_loading(False)
            on_done(result)

        def failed(error: H5ReadError):
            if token != self._token:
                return
            self._set_loading(False)
            if not quiet:
                self._show_error(error)

        def progressed(fraction: float):
            if token == self._token and not quiet:
                self.progress.setRange(0, 1000)
                self.progress.setValue(int(fraction * 1000))

        self._service.request(
            f"{self._channel}-{name}", self._node.file_path, read, done, failed, progressed
        )

    def _on_default_plot(self, group: H5Node, plot: h5_reader.DefaultPlot | None) -> None:
        """Show the signal a group names as its default plot, or say that it names none."""
        if plot is None:
            if group.kind == "file" or group.nx_class in ("NXroot", "NXentry", "NXdata"):
                count = group.n_children
                items = "" if count is None else ("1 item" if count == 1 else f"{count} items")
                self._show_state(
                    "folder_open",
                    f"A group with {items}" if items else "A group",
                    "It names no default plot (no @default leading to an NXdata with a "
                    "@signal). Pick a dataset inside it to see its values.",
                )
            return
        self.show_node(plot.signal)
        self._default = plot
        what = "main signal" if plot.rule == "device" else "default plot"
        self.summary_label.setText(f"{what} of {group.name}  ·  {self._summary(plot.signal)}")

    def _set_loading(self, loading: bool) -> None:
        if loading:
            self.progress.setRange(0, 0)
            if not self.progress.isVisible():
                self._progress_timer.start()
            return
        self._progress_timer.stop()
        self.progress.hide()

    def _show_state(self, icon: str, title: str, text: str = "", actions: tuple = ()) -> None:
        self.state_page.show_state(icon, title, text, actions)
        self.stack.setCurrentWidget(self.state_page)

    def _show_error(self, error: H5ReadError) -> None:
        def read_anyway():
            self._service.allow_busy_file(error.file_path)
            self.reload()

        self.info_label.clear()
        self._show_state(*error_state(error, self.reload, read_anyway))

    ################################################################################
    # Views and mapping
    ################################################################################

    def _set_views(self, views: list[str]) -> None:
        for key, button in self.view_buttons.items():
            # The map exists only for a signal of a scan with two axes.
            button.setVisible(bool(views) and views != ["value"] and (key != "map" or key in views))
            button.setEnabled(key in views)
            if key not in views:
                button.setToolTip(f"This dataset cannot be shown as {VIEW_LABELS[key].lower()}")
            else:
                button.setToolTip(f"Show as {VIEW_LABELS[key].lower()}")

    def _rows(self) -> int:
        """Rows of the shown dataset's signal: one value per scan point for a 1D dataset."""
        node = self._node
        return int(node.shape[-1]) if node is not None and node.shape else 0

    def _axes_fit(self) -> bool:
        """Whether the scan axes have one value per row of the shown dataset."""
        axes, node = self.scan_axes, self._node
        return (
            axes is not None and node is not None and node.ndim == 1 and axes.length == self._rows()
        )

    def map_fits(self) -> bool:
        """
        Whether the shown dataset can be drawn as a map of the scan's two axes.

        Returns:
            bool: True for a signal with one value per point of a scan with two axes.
        """
        axes = self.scan_axes
        return self._axes_fit() and axes is not None and len(axes.axes) == 2

    def _time_fits(self) -> bool:
        details = self._details
        return (
            details is not None
            and details.time is not None
            and (details.time.length == self._rows())
        )

    def _add_x_entry(self, text: str, data: str, enabled: bool = True, tip: str = "") -> None:
        self.x_combo.addItem(text, data)
        index = self.x_combo.count() - 1
        item = self.x_combo.model().item(index)
        if item is not None:
            item.setEnabled(enabled)
        if tip:
            self.x_combo.setItemData(index, tip, Qt.ItemDataRole.ToolTipRole)

    def _choice_of(self, data: str) -> str:
        """What is remembered of an entry: a dataset by its name, the others as they are."""
        if data in (SCAN_AXES, TIME, "") or data in self._x_datasets:
            return data
        return data.rstrip("/").rsplit("/", 1)[-1]

    def _index_of_choice(self, choice: str) -> int:
        for index in range(self.x_combo.count()):
            data = self.x_combo.itemData(index) or ""
            if self._choice_of(data) == choice:
                item = self.x_combo.model().item(index)
                return index if item is None or item.isEnabled() else -1
        return -1

    def _why_not(self, choice: str) -> str:
        """The note shown in place when the remembered choice does not fit the dataset."""
        rows = h5_reader.format_count(self._rows())
        axes, details = self.scan_axes, self._details
        if choice == SCAN_AXES:
            if axes is None:
                return "This file names no scan axes. Shown against Index."
            if self._node is not None and self._node.ndim != 1:
                return (
                    "Scan axes do not fit this dataset (it holds many values per scan point). "
                    "Shown against Index."
                )
            return (
                f"Scan axes do not fit this dataset ({rows} rows, the scan has "
                f"{h5_reader.format_count(axes.length)} points). Shown against Index."
            )
        if choice == TIME:
            if details is None or details.time is None:
                return "This dataset has no timestamps next to it. Shown against Index."
            return (
                f"Its timestamps do not fit this dataset ({rows} rows, "
                f"{h5_reader.format_count(details.time.length)} timestamps). "
                "Shown against Index."
            )
        if choice in self._x_datasets:
            name, length = self._x_datasets[choice]
            return (
                f"{name} does not fit this dataset ({rows} rows, {name} has "
                f"{h5_reader.format_count(length)} values). Shown against Index."
            )
        return f"No dataset {choice} with one value per row next to this one. Shown against Index."

    def _set_mapper(self) -> None:
        """Offer what to plot against, the frame sliders and the first row that fit the view."""
        node = self._node
        line = self._view in ("line", "map")
        details = self._details
        candidates = details.x_candidates if details is not None else ()
        time = details.time if details is not None else None
        axes = self.scan_axes
        # The X field of the File tab offers these; the plot pane does not show them.
        self.x_label.hide()
        self.x_combo.hide()
        self.x_combo.blockSignals(True)
        self.x_combo.clear()
        self._x_note = ""
        if line and node is not None:
            rows = h5_reader.format_count(self._rows())
            if axes is not None:
                fits = self._axes_fit()
                self._add_x_entry(
                    f"Scan axes ({axes.names})",
                    SCAN_AXES,
                    fits,
                    (
                        "The positions of the scan's points, as the file names them"
                        if fits
                        else f"The scan has {h5_reader.format_count(axes.length)} points, "
                        f"this dataset {rows} rows"
                    ),
                )
            self._add_x_entry(INDEX_TEXT, "", True, "The number of each row")
            if time is not None:
                self._add_x_entry(
                    TIME_TEXT,
                    TIME,
                    self._time_fits(),
                    "When each value was taken, from the timestamps next to it",
                )
            others = [c for c in candidates if time is None or c.path != time.path]
            for candidate in others:
                text = candidate.name + (f" ({candidate.units})" if candidate.units else "")
                self._add_x_entry(text, candidate.path)
            if self._x_choice in self._x_datasets and self.x_combo.findData(self._x_choice) < 0:
                # A dataset chosen by its path, e.g. a signal of the scan as in Signals.
                name, length = self._x_datasets[self._x_choice]
                fits = length == self._rows()
                self._add_x_entry(
                    name,
                    self._x_choice,
                    fits,
                    (
                        f"The values of {name}, one per row"
                        if fits
                        else f"{name} has {h5_reader.format_count(length)} values, "
                        f"this dataset {rows} rows"
                    ),
                )
            preferred = next((c for c in candidates if c.preferred), None)
            default = self._default
            own = ""
            if default is not None and default.x_path:
                # The @axes of the NXdata, also when it is a link to a dataset elsewhere.
                if self.x_combo.findData(default.x_path) < 0:
                    units = f" ({default.x_units})" if default.x_units else ""
                    self._add_x_entry(default.x_name + units, default.x_path)
                own = default.x_path
            elif preferred is not None:
                own = preferred.path
            # The file's suggestion: the dataset's own NXdata axis, else the scan's axes.
            suggested = own or (SCAN_AXES if self._axes_fit() else "")
            choice = self._x_choice
            if choice is None:
                index = self.x_combo.findData(suggested)
            elif choice == SCAN_AXES and own:
                index = self.x_combo.findData(own)  # the axis the file names for it
            else:
                index = self._index_of_choice(choice)
                if index < 0:
                    self._x_note = self._why_not(choice)
                    index = self.x_combo.findData("")
            self.x_combo.setCurrentIndex(max(0, index))
            self.x_combo.setEnabled(self.x_combo.count() > 1)
            self.x_combo.setToolTip(
                "What the values are plotted against; the choice is kept for other datasets"
            )
        self.x_combo.blockSignals(False)

        shape = node.shape if node is not None and node.shape is not None else ()
        kept = {"line": 1, "image": 2, "table": 2 if len(shape) > 1 else 1}.get(self._view, 0)
        lead = max(0, len(shape) - kept) if kept else 0
        if lead == 1:
            labels = ["Row" if self._view == "line" else "Frame"]
        else:
            labels = [f"Dimension {axis}" for axis in range(lead)]
        self.index_bar.set_dimensions(labels, list(shape[:lead]), self._index[:lead])

        rows = 0
        if self._view == "table" and shape:
            rows = shape[0] if len(shape) == 1 else shape[-2]
        paged = rows > TABLE_MAX_ROWS
        self.row_label.setVisible(paged)
        self.row_spin.setVisible(paged)
        self.row_spin.blockSignals(True)
        self.row_spin.setRange(0, max(0, rows - 1))
        self.row_spin.setValue(0)
        self.row_spin.blockSignals(False)
        self.mapper.setVisible(lead > 0 or paged)
        self.roles_changed.emit()

    def _on_details(self, details: H5Details) -> None:
        self._details = details
        self.details_changed.emit(details)
        node = details.node
        if node.kind != "dataset" or node.size == 0:
            return
        views = views_for(node)
        if self.map_fits():
            views = ["map", *views]
        self._set_views(views)
        wanted = self._preferred.get(min(node.ndim, 3))
        if "map" in views and wanted != "table":
            # A map of the scan's axes while they are what to plot against, else a line;
            # a line too while datasets are kept on its plot.
            wanted = "map" if self._x_choice in (None, SCAN_AXES) and not self._kept else "line"
        self._set_view(wanted if wanted in views else views[0])

    def _on_view_clicked(self, key: str) -> None:
        if self._node is None or key == self._view:
            return
        self._preferred[min(self._node.ndim, 3)] = key
        if key == "map":
            self._x_choice = SCAN_AXES  # a map is drawn against the scan's axes
        self._set_view(key)

    def _on_x_chosen(self, index: int) -> None:
        """Remember what the user plots against and show the dataset that way."""
        data = self.x_combo.itemData(index) or ""
        self._x_choice = self._choice_of(data)
        self._x_note = ""
        if self._view == "map" and data != SCAN_AXES:
            self._set_view("line")
            return
        self.x_changed.emit()
        if self._view == "line" and data == SCAN_AXES and self.map_fits():
            self._set_view("map")
            return
        self.roles_changed.emit()
        self._load()

    def x_entries(self) -> list[XEntry]:
        """
        What the Line view can plot against for the shown dataset, as offered now.

        Returns:
            list[XEntry]: Each choice; empty while the dataset is drawn as no line or map.
        """
        combo = self.x_combo
        entries = []
        for index in range(combo.count()):
            item = combo.model().item(index)
            entries.append(
                XEntry(
                    data=combo.itemData(index) or "",
                    text=combo.itemText(index),
                    enabled=item is None or item.isEnabled(),
                    tip=combo.itemData(index, Qt.ItemDataRole.ToolTipRole) or "",
                )
            )
        return entries

    def x_data(self) -> str | None:
        """What the Line view plots against now, as :meth:`choose_x` takes it; None if nothing."""
        return self.x_combo.currentData() if self.x_combo.count() else None

    def x_text(self) -> str:
        """The name of what the Line view plots against now, e.g. ``samx`` or ``Index``."""
        data = self.x_data()
        axes = self.scan_axes
        if data == SCAN_AXES and axes is not None:
            return axes.names
        return self.x_combo.currentText()

    def x_is_auto(self) -> bool:
        """Whether the x axis is the one the file suggests, not one chosen by hand."""
        return self._x_choice is None

    def choose_x(self, data: str) -> None:
        """
        Plot against another axis and remember it, as the user's choice.

        Args:
            data (str): SCAN_AXES, TIME, "" for the row number, or the path of a dataset.
        """
        index = self.x_combo.findData(data)
        if index < 0:
            return
        self.x_combo.setCurrentIndex(index)
        self._on_x_chosen(index)

    def reset_x(self) -> None:
        """Forget the chosen x axis: the file's suggestion is used again."""
        if self._x_choice is None:
            return
        self._x_choice = None
        self._x_note = ""
        self.x_changed.emit()
        if self._node is not None and self._details is not None:
            self._on_details(self._details)

    def set_x(self, choice: str | None, name: str = "", length: int = 0) -> None:
        """
        Plot against this from now on, as if the user chose it, also while no dataset is shown,
        e.g. to follow the x axis of the Signals tab.

        Args:
            choice (str | None): None for the file's suggestion, SCAN_AXES, TIME, "" for the
                row number, or the path of a dataset.
            name (str): For a dataset: its name on the axis.
            length (int): For a dataset: its number of values; it fits datasets with as many
                rows.
        """
        if choice not in (None, SCAN_AXES, TIME, ""):
            self._x_datasets[choice] = (name or dataset_name(choice), int(length))
        if choice == self._x_choice:
            return
        self._x_choice = choice
        self._x_note = ""
        self.x_changed.emit()
        if self._node is not None and self._details is not None:
            self._on_details(self._details)
        else:
            self._load_kept()
            self.roles_changed.emit()

    def selected_color(self) -> str:
        """Colour of the selected dataset's curve."""
        return self._main_color()

    def _x_source(self) -> tuple[str | None, bool, str]:
        """
        What the Line view plots against.

        Returns:
            tuple[str | None, bool, str]: Path of the x dataset (None for the row number),
            whether its values count from its first, and the label of the axis.
        """
        data = self.x_combo.currentData() or ""
        axes, details = self.scan_axes, self._details
        if data == SCAN_AXES and axes is not None:
            axis = axes.axes[0]
            return axis.path, False, axis.name + (f" ({axis.units})" if axis.units else "")
        if data == TIME and details is not None and details.time is not None:
            return details.time.path, True, TIME_LABEL
        if data:
            return data, False, self.x_combo.currentText()
        return None, False, INDEX_TEXT

    def _set_view(self, key: str) -> None:
        self._view = key
        if key in self.view_buttons:
            self.view_buttons[key].setChecked(True)
        self._overview = None
        self._detail_bins = None
        self._set_mapper()
        self._load()

    def _on_index_changed(self, index: tuple) -> None:
        for axis, value in enumerate(index):
            if axis < len(self._index):
                self._index[axis] = value
        self._load()

    def _lead(self, kept: int) -> tuple[int, ...]:
        count = max(0, len(self._index) - kept)
        return tuple(self._index[:count])

    ################################################################################
    # Loading
    ################################################################################

    def _load(self) -> None:
        node = self._node
        if node is None or node.kind != "dataset":
            return
        self._frame = None
        self.shown_changed.emit()
        self._range_timer.stop()
        if not self._reading:
            self._unread = True
            return
        self._load_kept()
        if self._view == "map":
            self._load_map()
        elif self._view == "line":
            self._overview = None
            self._detail_bins = None
            lead = self._lead(1)
            x_path, relative, _label = self._x_source()
            self._request(
                "data",
                lambda ctx: h5_reader.read_curve(
                    node.file_path,
                    node.path,
                    lead,
                    cancel=ctx.cancelled,
                    progress=ctx.progress,
                    x_path=x_path,
                    relative_x=relative,
                ),
                self._on_overview,
            )
        elif self._view == "image":
            lead = self._lead(2)
            self._request(
                "data",
                lambda _ctx: h5_reader.read_frame(node.file_path, node.path, lead),
                self._on_frame,
            )
        elif self._view == "table":
            lead = self._lead(2) if node.ndim > 1 else ()
            self.table_model.set_source(node, lead, self.row_spin.value())
            self.stack.setCurrentWidget(self.table)
            self.info_label.setText(self._table_info())
        elif self._view == "value":
            self._request(
                "data", lambda _ctx: h5_reader.read_value(node.file_path, node.path), self._on_value
            )

    # Line ---------------------------------------------------------------------------

    def _ensure_waveform(self):
        if self._waveform is None:
            # pylint: disable=import-outside-toplevel
            from bec_widgets.widgets.plots.waveform.waveform import Waveform

            self._waveform = Waveform(parent=self.line_page, client=self._client)
            # The tools for live scans have nothing to act on in a file.
            self._waveform.toolbar.show_bundles(
                ["plot_export", "mouse_interaction", "roi", "axis_popup"]
            )
            self.line_page.layout().addWidget(self._waveform)
            self._waveform.plot_item.vb.sigXRangeChanged.connect(
                lambda *_args: self._range_timer.start()
            )
        return self._waveform

    def _draw(self, x: np.ndarray, y: np.ndarray) -> None:
        waveform = self._ensure_waveform()
        if self._curve is None:
            waveform.clear_all()
            self._kept_curves = {}
            self._curve = waveform.plot(
                x=x, y=y, label=self.signal_name(), color=self._main_color(), pen_width=2
            )
            self._curve.setDownsampling(auto=True, method="peak")
            self._curve.setClipToView(True)
            waveform.x_label = self._x_source()[2]
            units = f" ({self._node.units})" if self._node.units else ""
            self._y_name = f"{self.signal_name()}{units}"
            waveform.y_label = self._y_name
            waveform.plot_item.enableAutoRange(x=True, y=True)
            self._draw_kept()
        else:
            self._curve.setData(x, y)

    def _on_overview(self, curve: CurveData) -> None:
        self._overview = curve
        self._detail_bins = None
        self._curve = None
        self._draw(curve.x, curve.y)
        self.stack.setCurrentWidget(self.line_page)
        self.info_label.setText(self._line_info())

    def _bin_rows(self) -> float:
        curve = self._overview
        return (curve.stop - curve.start) / max(1, len(curve.x) // 2)

    def _load_rows_in_view(self) -> None:
        """Read the rows the plot is zoomed to in full and splice them into the overview."""
        curve, node = self._overview, self._node
        if curve is None or not curve.reduced or node is None or self._view != "line":
            return
        if self._waveform is None or self.stack.currentWidget() is not self.line_page:
            return
        bins = len(curve.x) // 2
        steps = np.diff(curve.x[::2])
        if steps.size and not (np.all(steps >= 0) or np.all(steps <= 0)):
            return  # x values that go back and forth cannot be mapped to rows
        low, high = self._waveform.plot_item.vb.viewRange()[0]
        starts = curve.x[::2]
        if steps.size and steps[0] < 0:
            first = bins - int(np.searchsorted(starts[::-1], high, side="right"))
            last = bins - int(np.searchsorted(starts[::-1], low, side="left"))
        else:
            first = int(np.searchsorted(starts, low, side="right")) - 1
            last = int(np.searchsorted(starts, high, side="left"))
        first, last = max(0, first), min(bins, max(last, first + 1))
        if last - first >= 0.9 * bins:
            if self._detail_bins is not None:
                self._detail_bins = None
                self._curve.setData(curve.x, curve.y)
                self.info_label.setText(self._line_info())
            return
        pad = max(1, (last - first) // 4)
        first, last = max(0, first - pad), min(bins, last + pad)
        if self._detail_bins is not None:
            shown_first, shown_last = self._detail_bins
            inside = shown_first <= first and last <= shown_last
            if inside and (last - first) * 4 >= (shown_last - shown_first):
                return
        bin_rows = self._bin_rows()
        row_a = curve.start + int(round(first * bin_rows))
        row_b = min(curve.stop, curve.start + int(round(last * bin_rows)))
        lead = self._lead(1)
        x_path, relative, _label = self._x_source()
        self._request(
            "rows",
            lambda ctx: h5_reader.read_curve(
                node.file_path,
                node.path,
                lead,
                start=row_a,
                stop=row_b,
                cancel=ctx.cancelled,
                progress=ctx.progress,
                x_path=x_path,
                relative_x=relative,
            ),
            partial(self._on_rows, first, last),
        )

    def _on_rows(self, first: int, last: int, detail: CurveData) -> None:
        curve = self._overview
        if curve is None or self._curve is None:
            return
        self._detail_bins = (first, last)
        x = np.concatenate((curve.x[: 2 * first], detail.x, curve.x[2 * last :]))
        y = np.concatenate((curve.y[: 2 * first], detail.y, curve.y[2 * last :]))
        self._curve.setData(x, y)
        self.info_label.setText(self._line_info(detail))

    def _line_info(self, detail: CurveData | None = None) -> str:
        text = self._line_rows_info(detail)
        notes = [self._x_note] if self._x_note else []
        axes = self.scan_axes
        if (
            not self._x_note
            and self.x_combo.currentData() == SCAN_AXES
            and axes is not None
            and len(axes.axes) == 2
        ):
            notes.append(f"Drawn against {axes.axes[0].name}, the first scan axis; Map shows both.")
        return "  ".join([*notes, text]).strip()

    def _line_rows_info(self, detail: CurveData | None = None) -> str:
        curve = self._overview
        if curve is None:
            return ""
        total = h5_reader.format_count(curve.total)
        if not curve.reduced:
            return f"All {total} rows are drawn."
        count = h5_reader.format_count
        every = int(round(self._bin_rows()))
        overview = f"the lowest and highest value of every {every} rows"
        if detail is None:
            return (
                f"{total} rows, drawn as {overview}. "
                "Zoom in and the rows in view are read in full."
            )
        rows = f"{count(detail.start)} to {count(detail.stop - 1)}"
        how = "in full" if not detail.reduced else "in finer steps"
        return f"Rows {rows} are drawn {how}, the rest as {overview}."

    def signal_name(self) -> str:
        """
        The name of the shown signal: a BEC ``value`` dataset is named by its signal group.

        Returns:
            str: E.g. ``bpm4i`` for ``.../devices/bpm4i/bpm4i/value``.
        """
        node = self._node
        if node is None:
            return ""
        if node.name == "value" and node.path.count("/") > 1:
            return node.path.rstrip("/").rsplit("/", 2)[-2]
        return node.name

    # Kept datasets -------------------------------------------------------------------

    def kept_paths(self) -> list[str]:
        """
        The datasets kept on the plot, in the order they were kept.

        Returns:
            list[str]: Their paths inside the file.
        """
        return list(self._kept)

    def kept_file(self) -> str:
        """The file the kept datasets are drawn from; empty while there is none."""
        return self._kept_file

    def toggle_kept(self, node: H5Node | None) -> None:
        """
        Keep a dataset on the plot of the Line view as one more curve, or take it off.

        Args:
            node (H5Node | None): A dataset of numbers along one axis.
        """
        if not can_keep(node):
            return
        if node.path in self._kept:
            self.remove_kept(node.path)
            return
        if len(self._kept) >= KEPT_MAX:
            self._kept_note = f"{KEPT_MAX} kept at most: take one off to keep another"
            self._update_kept()
            return
        if not self._kept_file:
            self._kept_file = node.file_path
        self._kept[node.path] = _Kept(path=node.path, slot=self._free_slot())
        self._kept_note = ""
        self.kept_changed.emit()
        line = self.view_buttons["line"]
        if self._view in ("map", "image", "table") and line.isEnabled():
            self._set_view("line")  # keeping a dataset shows the curves
        else:
            self._load_kept()

    def remove_kept(self, path: str) -> None:
        """
        Take a kept dataset off the plot.

        Args:
            path (str): Its path inside the file.
        """
        if self._kept.pop(path, None) is None:
            return
        self._fixed_colors.pop(path, None)
        self._kept_note = ""
        self._remove_kept_curve(path)
        self._draw_kept()
        self._update_kept()
        self.kept_changed.emit()

    def clear_kept(self) -> None:
        """Take every kept dataset off the plot."""
        if not self._kept:
            return
        self._kept.clear()
        self._fixed_colors.clear()
        self._kept_note = ""
        self._kept_generation += 1
        self._service.cancel_all(self._kept_channel)
        for path in list(self._kept_curves):
            self._remove_kept_curve(path)
        self._draw_kept()
        self._update_kept()
        self.kept_changed.emit()

    def set_kept(self, paths: list[str], colors: dict[str, str], file_path: str = "") -> None:
        """
        Keep exactly these datasets on the plot, in this order, e.g. to follow the curves of
        the Signals tab. Those kept before keep what was read of them.

        Args:
            paths (list[str]): Their paths inside the file, in the order of their chips.
            colors (dict[str, str]): Colour of a dataset's curve where it is given; the others
                keep a colour none of these has.
            file_path (str): The file they are drawn from; empty to keep the current one.
        """
        if file_path:
            self.set_kept_file(file_path)
        paths = list(dict.fromkeys(paths))
        colors = {path: color for path, color in colors.items() if path in paths}
        if paths == list(self._kept) and colors == self._fixed_colors:
            return
        old = self._kept
        self._kept = OrderedDict(
            (path, old.get(path) or _Kept(path=path, slot=-1)) for path in paths
        )
        self._fixed_colors = colors
        for path, kept in self._kept.items():
            # A colour of its own that none of the given ones has.
            if path not in colors and (kept.slot < 0 or self._color_taken(kept)):
                kept.slot = -1
                kept.slot = self._free_slot()
        for path in old:
            if path not in self._kept:
                self._remove_kept_curve(path)
        self._kept_note = ""
        self.kept_changed.emit()
        self._load_kept()

    def kept_color(self, path: str) -> str:
        """
        The colour of a kept dataset's curve, also while it is not drawn.

        Args:
            path (str): Its path inside the file.

        Returns:
            str: The colour, or empty for a dataset that is not kept.
        """
        kept = self._kept.get(path)
        return self._color_of(kept) if kept is not None else ""

    def _color_of(self, kept: _Kept) -> str:
        return self._fixed_colors.get(kept.path) or series_color(kept.slot)

    def _color_taken(self, kept: _Kept) -> bool:
        """Whether another kept dataset has the colour of this one's slot."""
        color = series_color(kept.slot)
        return any(
            other is not kept and self._color_of(other) == color for other in self._kept.values()
        )

    def _free_slot(self) -> int:
        """A slot of the palette that no kept dataset has, by number nor by colour."""
        used = {kept.slot for kept in self._kept.values()}
        colors = {self._color_of(kept) for kept in self._kept.values() if kept.slot >= 0}
        colors |= set(self._fixed_colors.values())
        free = [slot for slot in range(1, 64) if slot not in used]
        return next((slot for slot in free if series_color(slot) not in colors), free[0])

    def set_kept_file(self, file_path: str) -> None:
        """
        Draw the kept datasets from another file: those that exist there are read again, the
        others keep their chips and say that they are not in this file.

        Args:
            file_path (str): The file the tree shows, or empty for none.
        """
        if file_path == self._kept_file:
            return
        self._kept_file = file_path
        self._kept_generation += 1
        self._service.cancel_all(self._kept_channel)
        for path, kept in self._kept.items():
            self._kept[path] = _Kept(path=path, slot=kept.slot)
            self._remove_kept_curve(path)
        self._load_kept()

    def kept_problems(self) -> dict[str, str]:
        """
        Why kept datasets are not drawn.

        Returns:
            dict[str, str]: The reason by path, for each kept dataset that is not drawn.
        """
        line = self._view == "line"
        return {path: kept.problem(line) for path, kept in self._kept.items() if kept.problem(line)}

    def kept_curve(self, path: str):
        """The curve of a kept dataset on the plot, or None while it is not drawn."""
        entry = self._kept_curves.get(path)
        return entry[0] if entry is not None else None

    def kept_lines(self) -> list[KeptLine]:
        """
        The kept datasets the Line view draws next to the selected one, in the order of their
        chips. The selected dataset is not among them, kept or not.

        Returns:
            list[KeptLine]: One per drawn curve.
        """
        lines = []
        for path, kept in self._kept.items():
            entry = self._kept_curves.get(path)
            if entry is None or kept.details is None:
                continue
            x_path, relative, _problem = self._kept_x(kept)
            lines.append(KeptLine(kept.details.node, x_path, relative, entry[1]))
        return lines

    def _kept_labels(self) -> dict[str, str]:
        """Short names of the kept datasets: with the group above where two would be equal."""
        main = self._node.path if self._node is not None else ""
        paths = [*self._kept]
        names = {path: dataset_name(path) for path in paths}
        shown = self.signal_name() if self._node is not None else ""
        labels = {}
        for path in paths:
            twins = [other for other in paths if other != path and names[other] == names[path]]
            clash = twins or (path != main and shown and names[path] == shown)
            labels[path] = dataset_name(path, with_parent=bool(clash))
        return labels

    def _main_color(self) -> str:
        """
        Colour of the selected dataset's curve: its chip's colour while it is kept, so that a
        kept dataset keeps its colour when it is selected; else the first of the palette, which
        no kept dataset takes.
        """
        node = self._node
        kept = self._kept.get(node.path) if node is not None else None
        if kept is not None and self._is_main(node.path):
            return self._color_of(kept)
        if not self._fixed_colors:
            return series_color(0)
        # Given colours may take the first of the palette: the next one no curve has.
        colors = {self._color_of(kept) for kept in self._kept.values()}
        return next(
            (series_color(slot) for slot in range(64) if series_color(slot) not in colors),
            series_color(0),
        )

    def _is_main(self, path: str) -> bool:
        node = self._node
        return node is not None and node.path == path and node.file_path == self._kept_file

    def _kept_x(self, kept: _Kept) -> tuple[str | None, bool, str]:
        """
        What a kept dataset is plotted against: what "Plot against" shows, looked up next to
        the dataset itself.

        Returns:
            tuple[str | None, bool, str]: Path of its x dataset (None for the row number),
            whether the values count from the first, and why the axis does not fit it.
        """
        data = self.x_combo.currentData() or ""
        details = kept.details
        if not data or details is None:
            return None, False, ""
        rows = int(details.node.shape[-1]) if details.node.shape else 0
        count = h5_reader.format_count
        if data == SCAN_AXES:
            axes = details.scan_axes
            if axes is None:
                return None, False, "its file names no scan axes for it"
            if axes.length != rows:
                return (
                    None,
                    False,
                    f"it has {count(rows)} rows, the scan has {count(axes.length)} points",
                )
            return axes.axes[0].path, False, ""
        if data == TIME:
            time = details.time
            if time is None:
                return None, False, "it has no timestamps next to it"
            if time.length and time.length != rows:
                return (None, False, f"it has {count(rows)} rows, {count(time.length)} timestamps")
            return time.path, True, ""
        if data in self._x_datasets:
            name, length = self._x_datasets[data]
            if length == rows:
                return data, False, ""
            return None, False, f"it has {count(rows)} rows, {name} has {count(length)} values"
        name = self._choice_of(data)
        for candidate in details.x_candidates:
            if candidate.path == data or candidate.name == name:
                if candidate.length in (0, rows):
                    return candidate.path, False, ""
        return None, False, f"there is no {name} with one value per row next to it"

    def _load_kept(self) -> None:
        """Look the kept datasets up in the file and read those the Line view draws."""
        if not self._kept or not self._kept_file:
            self._update_kept()
            return
        if not self._reading:
            self._unread = True
            self._update_kept()
            return
        line = self._view == "line"
        for kept in self._kept.values():
            if kept.details is None:
                if not kept.looking and not kept.missing:
                    self._look_up_kept(kept)
                continue
            if not line:
                continue
            x_path, relative, problem = self._kept_x(kept)
            kept.x_problem = problem
            if problem:
                self._remove_kept_curve(kept.path)
                continue
            if self._is_main(kept.path):
                continue  # drawn as the selected dataset
            key = (self._kept_file, x_path, relative)
            if kept.data_key == key:
                continue
            kept.data_key, kept.data, kept.read_problem = key, None, ""
            self._read_kept(kept, x_path, relative)
        self._update_kept()
        self._draw_kept()

    def _look_up_kept(self, kept: _Kept) -> None:
        file_path, path, generation = self._kept_file, kept.path, self._kept_generation
        kept.looking = True

        def done(details: H5Details):
            if generation != self._kept_generation or self._kept.get(path) is not kept:
                return
            kept.looking = False
            if not can_keep(details.node):
                kept.missing = "in this file it is not one curve"
            else:
                kept.details = details
            self._load_kept()

        def failed(error: H5ReadError):
            if generation != self._kept_generation or self._kept.get(path) is not kept:
                return
            kept.looking = False
            kept.missing = "not in this file" if error.kind == "missing" else error.message
            self._load_kept()

        self._service.request(
            f"{self._kept_channel}-look-{path}",
            file_path,
            lambda _ctx: h5_reader.describe(file_path, path),
            done,
            failed,
        )

    def _read_kept(self, kept: _Kept, x_path: str | None, relative: bool) -> None:
        file_path, path, key = self._kept_file, kept.path, kept.data_key

        def done(curve: CurveData):
            if self._kept.get(path) is not kept or kept.data_key != key:
                return
            kept.data = curve
            self._draw_kept()

        def failed(error: H5ReadError):
            if self._kept.get(path) is not kept or kept.data_key != key:
                return
            kept.read_problem = error.message
            self._update_kept()

        self._service.request(
            f"{self._kept_channel}-read-{path}",
            file_path,
            lambda ctx: h5_reader.read_curve(
                file_path,
                path,
                (),
                cancel=ctx.cancelled,
                progress=ctx.progress,
                x_path=x_path,
                relative_x=relative,
            ),
            done,
            failed,
        )

    def _remove_kept_curve(self, path: str) -> None:
        entry = self._kept_curves.pop(path, None)
        if entry is not None and self._waveform is not None:
            self._waveform.remove_curve(entry[1])

    def _draw_kept(self) -> None:
        """Draw the kept datasets that are read next to the selected one, each in its colour."""
        waveform = self._waveform
        if waveform is None or self._curve is None or self._view != "line":
            return
        labels = self._kept_labels()
        wanted = {
            path: kept
            for path, kept in self._kept.items()
            if kept.data is not None and not kept.problem(True) and not self._is_main(path)
        }
        for path, (_curve, label) in list(self._kept_curves.items()):
            if path not in wanted or labels.get(path) != label:
                self._remove_kept_curve(path)
        # The legend lists the curves in the order they are plotted: the selected one, then the
        # kept ones in the order of their chips, however the reads finish. Only the drawn
        # curves before the first one still to plot stay; those after it are plotted again.
        stay = 0
        for path in wanted:
            if path not in self._kept_curves:
                break
            stay += 1
        for path in list(wanted)[stay:]:
            self._remove_kept_curve(path)
        for path, kept in wanted.items():
            entry = self._kept_curves.get(path)
            if entry is None:
                curve = waveform.plot(
                    x=kept.data.x,
                    y=kept.data.y,
                    label=labels[path],
                    color=self._color_of(kept),
                    pen_width=2,
                )
                curve.setDownsampling(auto=True, method="peak")
                curve.setClipToView(True)
                self._kept_curves[path] = (curve, labels[path])
            else:
                entry[0].setData(kept.data.x, kept.data.y)
        # Taking a curve off gives the others the Waveform's colours by count: give them back.
        self._curve.set_color(self._main_color())
        for path, (curve, _label) in self._kept_curves.items():
            curve.set_color(self._color_of(self._kept[path]))
        # With more than one curve the legend names them; the y axis names one curve only.
        y_name = "" if self._kept_curves else self._y_name
        if waveform.y_label != y_name:
            waveform.y_label = y_name
        self._update_kept()

    def _update_kept(self) -> None:
        line = self._view == "line"
        labels = self._kept_labels()
        chips = []
        for path, kept in self._kept.items():
            problem = kept.problem(line)
            color = ""
            if not problem:
                color = self._color_of(kept)
            chips.append(
                KeptChip(
                    path=path,
                    label=labels[path],
                    color=color,
                    problem=problem,
                    slot_color=self._color_of(kept),
                )
            )
        self._kept_chips = chips
        self._kept_shown_note = self._kept_note
        colors = {chip.path: chip.color for chip in chips}
        if colors != self._kept_colors:
            self._kept_colors = colors
            self.kept_changed.emit()
        self.roles_changed.emit()

    def kept_chips(self) -> list[KeptChip]:
        """
        The kept datasets as the box of the File tab shows them, in the order they were kept.

        Returns:
            list[KeptChip]: Name, colour and why one is not drawn, of each.
        """
        return list(self._kept_chips)

    def kept_note(self) -> str:
        """A note on the kept datasets, e.g. that the cap is reached; empty when none."""
        return self._kept_shown_note

    def kept_colors(self) -> dict[str, str]:
        """
        The colour of each kept dataset's curve, by path, in the order they were kept; empty
        for one that is not drawn.
        """
        return {path: self._kept_colors.get(path, "") for path in self._kept}

    # Map ----------------------------------------------------------------------------

    def map_kind(self) -> str:
        """
        How a map of the shown dataset is drawn, by the rule of the Signals tab.

        Returns:
            str: ``heatmap`` for a grid scan, else ``scatter``.
        """
        axes = self.scan_axes
        return "heatmap" if axes is not None and axes.scan_name in GRID_SCANS else "scatter"

    def map_widget(self):
        """The ScatterWaveform or the Heatmap that shows the map, or None before one is drawn."""
        return self._map_heatmap if self.map_kind() == "heatmap" else self._map_scatter

    def _detached(self, plot) -> None:
        """A plot of the file's data: running scans must not reset it."""
        plot.bec_dispatcher.disconnect_slot(plot.on_scan_status, MessageEndpoints.scan_status())

    def _ensure_map(self, kind: str):
        # pylint: disable=import-outside-toplevel
        if kind == "heatmap":
            if self._map_heatmap is None:
                from bec_widgets.widgets.plots.heatmap.heatmap import Heatmap

                plot = Heatmap(parent=self.map_page, client=self._client)
                plot.setObjectName("file_map_heatmap")
                self._detached(plot)
                plot.toolbar.show_bundles(
                    [
                        "plot_export",
                        "mouse_interaction",
                        "image_crosshair",
                        "image_autorange",
                        "image_colorbar",
                        "axis_popup",
                    ]
                )
                self.map_page.layout().addWidget(plot)
                self._map_heatmap = plot
            shown, hidden = self._map_heatmap, self._map_scatter
        else:
            if self._map_scatter is None:
                from bec_widgets.widgets.plots.scatter_waveform.scatter_waveform import (
                    ScatterWaveform,
                )

                plot = ScatterWaveform(parent=self.map_page, client=self._client)
                plot.setObjectName("file_map_scatter")
                self._detached(plot)
                plot.toolbar.show_bundles(["plot_export", "mouse_interaction", "axis_popup"])
                plot.plot_item.addItem(plot.main_curve)
                # The points only: the path between them hides them where they are dense.
                plot.main_curve.setPen(None)
                self.map_page.layout().addWidget(plot)
                self._map_scatter = plot
            shown, hidden = self._map_scatter, self._map_heatmap
        shown.show()
        if hidden is not None:
            hidden.hide()
        return shown

    def _load_map(self) -> None:
        node, axes = self._node, self.scan_axes
        if node is None or axes is None or len(axes.axes) != 2:
            return
        kind = self.map_kind()
        plot = self._ensure_map(kind)
        image = None
        if kind == "heatmap":
            image = type(plot).compute_step_scan_image
        x_path, y_path = axes.axes[0].path, axes.axes[1].path

        def read(ctx: ReadContext):
            data = h5_reader.read_map(
                node.file_path, node.path, x_path, y_path, cancel=ctx.cancelled
            )
            if image is None:
                return data, None
            grid = grid_image(data.x, data.y, data.z)
            if grid is not None:
                return data, grid
            try:
                return data, image(data.x, data.y, data.z, 1.0, "linear")
            except Exception:  # pylint: disable=broad-except
                return data, None  # e.g. points on one line: drawn as points instead

        self._request("data", read, self._on_map)

    def _on_map(self, result) -> None:
        data, image = result
        self._map_data = data
        axes, node = self.scan_axes, self._node
        x_axis, y_axis = axes.axes
        kind = self.map_kind() if image is not None else "scatter"
        plot = self._ensure_map(kind)
        units = f" ({node.units})" if node.units else ""
        plot.x_label = x_axis.name + (f" ({x_axis.units})" if x_axis.units else "")
        plot.y_label = y_axis.name + (f" ({y_axis.units})" if y_axis.units else "")
        plot.title = f"{self.signal_name()}{units}"
        if kind == "heatmap":
            img, transform = image
            plot.main_image.set_data(img, transform=transform)
            plot.plot_item.autoRange()
        else:
            plot.main_curve.set_data(data.x, data.y, data.z)
            plot.plot_item.enableAutoRange(x=True, y=True)
        self.stack.setCurrentWidget(self.map_page)
        count = h5_reader.format_count
        parts = [
            f"{count(len(data.z))} points",
            f"x: {x_axis.name}",
            f"y: {y_axis.name}",
            f"colour: {self.signal_name()}",
        ]
        if data.stride > 1:
            parts.append(f"every {data.stride}. point is drawn")
        if kind == "scatter" and self.map_kind() == "heatmap":
            parts.append("drawn as points: they span no area to fill")
        parts.append("read from the file")
        self.info_label.setText("  ·  ".join(parts))

    # Image --------------------------------------------------------------------------

    def _ensure_image(self):
        if self._image is None:
            # pylint: disable=import-outside-toplevel
            from bec_widgets.widgets.plots.image.image import Image

            self._image = Image(parent=self.image_page, client=self._client)
            # The device picker belongs to live images; here the tree picks what is shown.
            self._image.toolbar.show_bundles(
                [
                    "plot_export",
                    "mouse_interaction",
                    "image_crosshair",
                    "image_processing",
                    "axis_popup",
                ]
            )
            self.image_page.layout().addWidget(self._image)
        return self._image

    def shown_frame(self) -> tuple[FrameData, tuple[int, ...]] | None:
        """
        The frame the Image view shows, and its position in a stack.

        Returns:
            tuple[FrameData, tuple[int, ...]] | None: The frame as read and its index, or None
            when no frame is shown.
        """
        if self._view != "image" or self._frame is None or self._node is None:
            return None
        return self._frame, self._lead(2)

    def _on_frame(self, frame: FrameData) -> None:
        self._frame = frame
        count = h5_reader.format_count
        image = self._ensure_image()
        image.main_image.set_data(np.asarray(frame.data))
        if self._fresh_image:
            self._fresh_image = False
            image.auto_range(True)
        self.stack.setCurrentWidget(self.image_page)
        node = self._node
        height, width = node.shape[-2], node.shape[-1]
        parts = [f"{count(height)} × {count(width)} pixels"]
        lead = self._lead(2)
        if len(lead) == 1:
            parts.insert(0, f"Frame {count(lead[0])} of {count(node.shape[0])}")
        if frame.stride > 1:
            parts.append(f"every {frame.stride}. pixel is drawn, the frame is too large to show")
        parts.append("only this frame is read")
        self.info_label.setText("  ·  ".join(parts))

    # Table and value ------------------------------------------------------------------

    def _table_info(self) -> str:
        node = self._node
        rows = node.shape[0] if node.ndim == 1 else node.shape[-2]
        text = "The cells in view are read as you scroll."
        if rows > TABLE_MAX_ROWS:
            shown = h5_reader.format_count(TABLE_MAX_ROWS)
            text += f" The table holds {shown} rows at a time; “From row” moves on."
        return text

    def _on_table_reset(self) -> None:
        if self.table_model.error is not None and self._view == "table":
            self._show_error(self.table_model.error)

    def _on_value(self, text: str) -> None:
        self.value_view.setPlainText(text)
        self.stack.setCurrentWidget(self.value_view)
        self.info_label.clear()
