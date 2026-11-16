"""
The preview of the HDF5 viewer: one dataset as a line, an image, a table or a value.

Only what is on screen is read: a reduced overview of a long signal and then the rows in
view, one frame of a stack, the visible window of a table. The plots are the BEC Waveform
and Image widgets.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from functools import partial
from pathlib import Path

import numpy as np
from bec_qthemes import material_icon
from qtpy.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer, Signal
from qtpy.QtGui import QFont, QGuiApplication, QPalette
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
    TableData,
)
from bec_widgets.widgets.services.hdf5_viewer.h5_service import H5Service, ReadContext

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

VIEW_LABELS = {"line": "Line", "image": "Image", "table": "Table", "value": "Value"}
VIEW_ICONS = {"line": "show_chart", "image": "image", "table": "table_rows", "value": "tag"}


def mute(label: QWidget) -> None:
    """
    Draw a widget's text in the muted text colour of the theme.

    Args:
        label (QWidget): The widget, usually a label.
    """
    label.setForegroundRole(QPalette.ColorRole.PlaceholderText)


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
    ) -> None:
        """
        Fill the page.

        Args:
            icon (str): Name of a Material icon.
            title (str): What is the case, in a few words.
            text (str): What it means and what can be done.
            actions (tuple[tuple[str, Callable[[], None]], ...]): Label and callback of up to
                two buttons; the first one is the main action.
        """
        self.icon.setPixmap(material_icon(icon, size=(40, 40)))
        self.title.setText(title)
        self.text.setText(text)
        self.text.setVisible(bool(text))
        for button in self._actions:
            self.buttons.removeWidget(button)
            button.deleteLater()
        self._actions = []
        while self.buttons.count():
            self.buttons.takeAt(0)
        self.buttons.addStretch(1)
        for index, (label, callback) in enumerate(actions):
            button = QPushButton(label, self)
            button.setDefault(index == 0)
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


class H5Preview(QWidget):
    """Shows the dataset that is selected in the tree."""

    #: The details of the shown node were read: an :class:`H5Details`, or None.
    details_changed = Signal(object)

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
        self._index: list[int] = []
        self._overview: CurveData | None = None
        self._detail_bins: tuple[int, int] | None = None
        self._curve = None
        self._waveform = None
        self._image = None
        self._fresh_image = True

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
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(self.name_label)
        header.addWidget(self.summary_label, 1)
        for key in ("line", "image", "table"):
            button = QToolButton(self)
            button.setText(VIEW_LABELS[key])
            button.setIcon(material_icon(VIEW_ICONS[key], convert_to_pixmap=False))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setToolTip(f"Show as {VIEW_LABELS[key].lower()}")
            button.clicked.connect(partial(self._on_view_clicked, key))
            self.view_group.addButton(button)
            self.view_buttons[key] = button
            header.addWidget(button)

        # Mapping: which x axis, which frame
        self.x_label = QLabel("X axis", self)
        self.x_combo = QComboBox(self)
        self.x_combo.setAccessibleName("X axis")
        self.x_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.x_combo.activated.connect(lambda _index: self._load())
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
        for page in (self.state_page, self.line_page, self.image_page, self.table, self.value_view):
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
    def view(self) -> str:
        """The view that is shown: ``line``, ``image``, ``table``, ``value`` or empty."""
        return self._view

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
        self._details = None
        self._overview = None
        self._detail_bins = None
        self._curve = None
        self._view = ""
        self._fresh_image = True
        self._index = [0] * (node.ndim if node is not None else 0)
        self.details_changed.emit(None)
        self.table_model.set_source(None, ())
        self.info_label.clear()
        self._set_views([])
        self._set_mapper()
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
            button.setVisible(bool(views) and views != ["value"])
            button.setEnabled(key in views)
            if key not in views:
                button.setToolTip(f"This dataset cannot be shown as {VIEW_LABELS[key].lower()}")
            else:
                button.setToolTip(f"Show as {VIEW_LABELS[key].lower()}")

    def _set_mapper(self) -> None:
        """Offer the x axis, the frame sliders and the first row that fit the view."""
        node = self._node
        line = self._view == "line"
        candidates = self._details.x_candidates if self._details is not None else ()
        self.x_label.setVisible(line)
        self.x_combo.setVisible(line)
        self.x_combo.blockSignals(True)
        self.x_combo.clear()
        if line and node is not None:
            self.x_combo.addItem("Row number", "")
            for candidate in candidates:
                text = candidate.name + (f" ({candidate.units})" if candidate.units else "")
                self.x_combo.addItem(text, candidate.path)
            preferred = next((c for c in candidates if c.preferred), None)
            if preferred is not None:
                self.x_combo.setCurrentIndex(self.x_combo.findData(preferred.path))
            self.x_combo.setEnabled(bool(candidates))
            self.x_combo.setToolTip(
                "Datasets next to this one with one value per row"
                if candidates
                else "No dataset next to this one has one value per row"
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
        self.mapper.setVisible(line or lead > 0 or paged)

    def _on_details(self, details: H5Details) -> None:
        self._details = details
        self.details_changed.emit(details)
        node = details.node
        if node.kind != "dataset" or node.size == 0:
            return
        views = views_for(node)
        self._set_views(views)
        wanted = self._preferred.get(min(node.ndim, 3))
        self._set_view(wanted if wanted in views else views[0])

    def _on_view_clicked(self, key: str) -> None:
        if self._node is None or key == self._view:
            return
        self._preferred[min(self._node.ndim, 3)] = key
        self._set_view(key)

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
        self._range_timer.stop()
        if self._view == "line":
            self._overview = None
            self._detail_bins = None
            lead, x_path = self._lead(1), self.x_combo.currentData() or None
            self._request(
                "data",
                lambda ctx: h5_reader.read_curve(
                    node.file_path,
                    node.path,
                    lead,
                    cancel=ctx.cancelled,
                    progress=ctx.progress,
                    x_path=x_path,
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
            self._curve = waveform.plot(x=x, y=y, label=self._node.name, pen_width=2)
            self._curve.setDownsampling(auto=True, method="peak")
            self._curve.setClipToView(True)
            x_text = self.x_combo.currentText() if self.x_combo.currentData() else "Row number"
            waveform.x_label = x_text
            units = f" ({self._node.units})" if self._node.units else ""
            waveform.y_label = f"{self._node.name}{units}"
            waveform.plot_item.enableAutoRange(x=True, y=True)
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
        lead, x_path = self._lead(1), self.x_combo.currentData() or None
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

    def _on_frame(self, frame: FrameData) -> None:
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
