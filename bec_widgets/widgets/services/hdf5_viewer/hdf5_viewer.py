"""
The HDF5 viewer: browse the scans BEC has written and look into any HDF5 file.

The scans come from the scan history that BEC keeps in memory and their curves are drawn
by the Waveform widget through the Data API. Files are read by
:mod:`~bec_widgets.widgets.services.hdf5_viewer.h5_reader`, which never keeps a file open
and never reads more than is shown. It opens the file of a scan BEC lists as the Data API
does, and every other file without the HDF5 file lock.
"""

from __future__ import annotations

import contextlib
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QFont, QGuiApplication, QKeySequence
from qtpy.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedLayout,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.imported_scans import (
    ImportedScan,
    forget_imported,
    imported_id,
    register_imported,
)
from bec_widgets.utils.rpc_register import RPCRegister
from bec_widgets.utils.theme_utils import theme_colors
from bec_widgets.widgets.containers.dock_area.basic_dock_area import DockAreaWidget
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from bec_widgets.widgets.progress.scan_progressbar.scan_ui import ElidedLabel
from bec_widgets.widgets.services.hdf5_viewer import h5_reader
from bec_widgets.widgets.services.hdf5_viewer.file_box import FileBox
from bec_widgets.widgets.services.hdf5_viewer.h5_preview import (
    KEPT_MAX,
    SCAN_AXES,
    TIME,
    H5DetailsPanel,
    H5Preview,
    KeptLine,
    StatePage,
    dataset_name,
)
from bec_widgets.widgets.services.hdf5_viewer.h5_reader import (
    CurveData,
    FileSummary,
    H5Node,
    H5ReadError,
)
from bec_widgets.widgets.services.hdf5_viewer.h5_service import H5Service
from bec_widgets.widgets.services.hdf5_viewer.h5_tree import H5Tree, ZButton, can_keep
from bec_widgets.widgets.services.hdf5_viewer.map_view import (
    GRID_SCANS,
    ONE_LINE_REASON,
    MapPlots,
    ViewSwitch,
    default_view,
    is_area_scan,
    map_axes,
    points_on_one_line,
)
from bec_widgets.widgets.services.hdf5_viewer.plot_targets import (
    PLOT_KINDS,
    AddResult,
    CurveSource,
    MapSource,
    Offer,
    Undo,
    add_history_curves,
    copy_label,
    curves_effect,
    dock_area_for,
    has_curve,
    open_plots,
    other_plots,
    plot_kind,
    plot_name,
    show_image_copy,
    show_map,
    shown_map,
    shown_signals,
    signal_label,
    signal_of_dataset,
)
from bec_widgets.widgets.services.hdf5_viewer.role_fields import ChipInfo, Swatch
from bec_widgets.widgets.services.hdf5_viewer.scan_list import ScanEntry, ScanList, series_color
from bec_widgets.widgets.services.hdf5_viewer.signal_list import (
    INDEX_X,
    TIMESTAMP_X,
    X_MODES,
    DatasetKey,
    SignalInfo,
    SignalList,
    SourceKey,
)
from bec_widgets.widgets.services.hdf5_viewer.style import (
    control_key_name,
    mute,
    remute,
    scan_shades,
)
from bec_widgets.widgets.services.scan_history_browser.components.scan_history_view import (
    BECHistoryManager,
)

logger = bec_logger.logger

#: Pen styles that tell the signals of one scan apart when scans are compared.
PEN_STYLES = ("solid", "dash", "dot", "dashdot")
#: Width the scan list opens at: its rows show motor, points and time, and its search row the
#: whole placeholder beside "Open file".
SCAN_LIST_OPEN_WIDTH = 300
#: Width the pane of the Signals and File tabs opens at.
MIDDLE_OPEN_WIDTH = 360
#: Room between the scan list and the edges of its pane, when it cannot be measured yet.
SCAN_LIST_PADDING = 18
#: Room between the plot's toolbar and the edges of its pane, when it cannot be measured yet.
PLOT_TOOLBAR_PADDING = 24
#: How soon after a click or a key in the tree a newly selected row counts as picked by hand.
#: Pause between two looks at a file that is still being written.
BUSY_RETRY_MS = 2000
#: Pause before the curves are checked for points, and how often while they still load.
EMPTY_CHECK_MS = 1500
EMPTY_CHECK_TRIES = 20
#: A map whose data has not arrived after this long says that it is still loading.
MAP_WAIT_MS = 8000
#: How often the viewer looks whether the curves of newly picked scans have their data.
LINES_WAIT_POLL_MS = 25
#: How long, from the click, the plot of the scan before stays on screen while the newly
#: picked scan is read: the pane changes once, to the new plot, if it is drawn by then.
SWITCH_HOLD_MS = 400
#: A loading page that shows stays at least this long, so that it never flashes.
LOADING_KEPT_MS = 300
#: Text of the button that adds the curves to another plot.
ADD_BUTTON_TEXT = "Add to plot"
#: The end of a message on that button after a replace: the menu offers the way back.
UNDO_SUFFIX = " · Undo"
#: How long the result of adding curves stays on that button.
ADD_FEEDBACK_MS = 3000
#: Room a message gets on a button that is not on screen: all it needs.
HIDDEN_BUTTON_ROOM = 100_000
#: Largest number of rows a dataset of the File tab may have to be copied to another plot.
COPY_MAX_POINTS = 1_000_000
#: What the File tab's button says about a copy before and after it is made.
COPY_TOOLTIP = "Adds a copy of these values. A copy is not saved with the workspace."
#: Time a scan that ended stays listed as running while its history entry is awaited.
LIVE_LINGER_MS = 20000
#: How often and how long to wait for BEC's client to finish reading the scan history.
HISTORY_POLL_MS = 200
#: While a key is held, a scan is loaded once no repeat came for this long (above the key
#: repeat interval of the desktops, 25 to 90 ms), or at once when the key is let go.
HOLD_SETTLE_MS = 150
#: How many finished scans keep the Data API's answer of how their signals are keyed.
DESCRIBED_KEPT = 100
HISTORY_WAIT_MS = 10000

CurveKey = tuple[str, str, str]
#: Why a dataset of a running scan's file is not on the plot.
RUNNING_FILE = "the scan is still running: its file is read once it is done"
#: What the x axis of a dataset that is no signal is read from: ``("index",)``,
#: ``("time",)`` or ``("dataset", path, name)``.
FileX = tuple


def read_file_curve(
    file_path: str,
    path: str,
    x: FileX,
    full: bool = False,
    cancel: Callable[[], bool] | None = None,
    progress: Callable[[float], None] | None = None,
) -> CurveData | int | str:
    """
    Read a dataset of a scan's file that is no signal, as one curve of the scan's plot,
    against the x axis of that plot. Runs off the GUI thread.

    A dataset whose length does not fit the x axis is not read and never cut, as the File
    tab's preview keeps it; neither is one longer than the plot reads by itself.

    Args:
        file_path (str): The scan's file.
        path (str): The dataset inside it.
        x (FileX): What the x values are read from.
        full (bool): Read it also when it has more rows than :data:`COPY_MAX_POINTS`.
        cancel (Callable[[], bool] | None): Returns True when the read is no longer wanted.
        progress (Callable[[float], None] | None): Called with the fraction read so far.

    Returns:
        CurveData | int | str: Its values, its number of rows when it is longer than the
        plot reads by itself, or why it is not drawn, in the words of the preview.
    """
    count = h5_reader.format_count
    details = h5_reader.describe(file_path, path)
    if not can_keep(details.node):
        return "in this file it is not one curve"
    rows = int(details.node.shape[-1])
    x_path = None
    if x[0] == "time":
        time_axis = details.time
        if time_axis is None:
            return "it has no timestamps next to it"
        if time_axis.length and time_axis.length != rows:
            return f"it has {count(rows)} rows, {count(time_axis.length)} timestamps"
        x_path = time_axis.path
    elif x[0] == "dataset":
        try:
            axis = h5_reader.describe(file_path, x[1]).node
        except H5ReadError as error:
            if error.kind == "missing":
                return f"{x[2]} is not in this file"
            raise
        length = int(axis.shape[0]) if axis.shape else 0
        if length != rows:
            return f"it has {count(rows)} rows, {x[2]} has {count(length)} values"
        x_path = x[1]
    if rows > COPY_MAX_POINTS and not full:
        return rows
    return h5_reader.read_curve(
        file_path,
        path,
        (),
        max_points=max(rows, 1),
        cancel=cancel,
        progress=progress,
        x_path=x_path,
    )


def _names(value) -> list:
    """
    The items of a list in a message, which may also arrive as a numpy array or be missing.

    Args:
        value: A list, a tuple, a numpy array or None.

    Returns:
        list: The items; empty for None.
    """
    return [] if value is None else list(value)


#: The reasons the Waveform gives for a curve that is not a failed read.
NO_DATA = "no data in this scan"
TOO_LARGE = "not loaded: it is larger than the size limit"


def read_sentence(error: str, device: str) -> str:
    """
    Say in the user's words why the stored data of a signal could not be read.

    The text HDF5 or the Data API gave stays for the tooltip: a bug report needs it.

    Args:
        error (str): The reason the read gave.
        device (str): The device of the signal.

    Returns:
        str: One sentence, without its full stop.
    """
    text = error.strip()
    errno = re.search(r"errno\s*=?\s*(\d+)", text, re.IGNORECASE)
    number = int(errno.group(1)) if errno else None
    if number == 2 or "No such file" in text:
        path = re.search(r"name = '([^']+)'|: '([^']+)'", text)
        where = path.group(1) or path.group(2) if path else ""
        return "The scan's file is not there any more" + (f": {middle_cut(where)}" if where else "")
    if number == 13 or "Permission denied" in text:
        return "This account may not read the scan's file"
    if "locking flag values don't match" in text:
        return "The scan's file was open for another read at that moment"
    if text.rstrip(".") == "Stored signal is missing":
        return f"{device} is not stored in this scan's file"
    if text.rstrip(".") == "Error accessing file":
        # bec_lib's retry of a file read: the reason is in its log only.
        return "The scan's file could not be opened at that moment"
    if text == "not available in this scan":
        return f"{device} is not in this scan"
    if text == NO_DATA:
        return f"{device} has no points in this scan"
    if text == TOO_LARGE:
        return f"{device} was not loaded: it is larger than the size limit"
    return text.rstrip(".") or "The read failed"


def middle_cut(path: str, room: int = 48) -> str:
    """Shorten a path in its middle, so that its start and its file name stay."""
    if len(path) <= room:
        return path
    keep = room - 1
    return f"{path[: keep // 3]}…{path[len(path) - (keep - keep // 3):]}"


def planned_on_one_line(info) -> bool | None:
    """
    Whether the positions a scan plans (``positions`` in the ``info`` of its status message)
    lie on one line, tested on its first two motors.

    Args:
        info: The ``info`` of a ``ScanStatusMessage``.

    Returns:
        bool | None: The answer, or None for a scan whose status names no positions of two
        motors (fly scans, custom scans).
    """
    positions = info.get("positions") if isinstance(info, dict) else None
    if positions is None:
        return None
    try:
        points = np.asarray(positions, dtype=np.float64)
    except (TypeError, ValueError):
        return None
    if points.ndim != 2 or points.shape[0] == 0 or points.shape[1] < 2:
        return None
    return points_on_one_line(points[:, 0], points[:, 1])


@dataclass(frozen=True)
class _SendItem:
    """One of the curves "Add to plot" sends from the File tab while datasets are kept."""

    #: Its name in the legend of the preview.
    label: str
    #: The history curve that stands for it, for a signal of a listed scan.
    history: CurveSource | None = None
    #: The dataset to copy, for anything else.
    node: H5Node | None = None
    index: tuple[int, ...] = ()
    x_path: str | None = None
    relative: bool = False
    #: Why it cannot be sent; it is named on the button.
    problem: str = ""


@dataclass
class _FileCurve:
    """A dataset of a scan's file on the scan's plot that is no signal, for one scan."""

    color: str = ""
    style: str = "solid"
    #: What it is read for: (file, path, x axis, whether in full); None while not read.
    job: tuple | None = None
    data: CurveData | None = None
    #: Why it is not drawn, in the user's words; empty while it is or is being read.
    problem: str = ""
    #: Its rows, while it was not read for being longer than the plot reads by itself.
    large: int = 0
    #: Its curve on the plot, and the name the curve has there.
    item: object | None = None
    label: str = ""


class FactsLabel(ElidedLabel):
    """
    The line beside the title of the plot: the facts of the scan, elided where they are cut,
    and a hint after them only where it fits whole.
    """

    #: Between the facts and the hint.
    SEPARATOR = "  ·  "

    def __init__(self, parent: QWidget | None = None):
        self._facts = ""
        self._hint = ""
        super().__init__(parent=parent)

    def setText(self, text: str) -> None:  # pylint: disable=invalid-name
        """Set facts without a hint."""
        self.set_facts(text)

    def set_facts(self, facts: str, hint: str = "") -> None:
        """
        Set the facts and the hint after them; :meth:`full_text` is both.

        Args:
            facts (str): What is shown, elided where it is cut.
            hint (str): What can be done, shown only where it fits whole.
        """
        self._facts, self._hint = facts or "", hint or ""
        full = self.SEPARATOR.join(part for part in (self._facts, self._hint) if part)
        if full == self.full_text():
            return
        self._full = full
        self._elide()

    def shown_text(self) -> str:
        """The text as it is shown: the facts, elided or not, with the hint where it fits."""
        return QLabel.text(self)

    def _elide(self) -> None:
        hint = getattr(self, "_hint", "")
        if not hint:
            super()._elide()
            return
        width = max(10, self.width())
        metrics = self.fontMetrics()
        full = self.full_text()
        if metrics.horizontalAdvance(full) <= width:
            shown = full
        else:
            shown = metrics.elidedText(self._facts, Qt.TextElideMode.ElideRight, width)
        if shown != QLabel.text(self):
            QLabel.setText(self, shown)
        tooltip = full if shown != full else ""
        if tooltip != self._tooltip:
            self._tooltip = tooltip
            self.setToolTip(tooltip)


class PathLabel(QLabel):
    """
    A one-line label for the path of a file. A path too long for the room is cut in its middle,
    so that the file name stays readable, and the whole path is always in the tooltip. The text
    can be selected with the mouse; a copy of a selection over the cut copies what was cut too,
    and "Copy path" in the context menu copies the whole path.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._full = ""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    def setText(self, text: str) -> None:  # pylint: disable=invalid-name
        """Set the whole path; what shows is cut to fit."""
        text = text or ""
        if text == self._full:
            return
        self._full = text
        self.setToolTip(text)
        self.updateGeometry()
        self._elide()

    def full_text(self) -> str:
        """The whole path, before it is cut."""
        return self._full

    def sizeHint(self):  # pylint: disable=invalid-name
        hint = super().sizeHint()
        hint.setWidth(self.fontMetrics().horizontalAdvance(self._full) + 4)
        return hint

    def minimumSizeHint(self):  # pylint: disable=invalid-name
        hint = super().minimumSizeHint()
        hint.setWidth(min(40, self.sizeHint().width()))
        return hint

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        shown = self.fontMetrics().elidedText(
            self._full, Qt.TextElideMode.ElideMiddle, max(10, self.width())
        )
        if shown != super().text():
            super().setText(shown)

    def selected_path_text(self) -> str:
        """
        The selected text as it is in the whole path: a selection over the cut takes in what
        was cut.

        Returns:
            str: The text, empty without a selection.
        """
        if not self.hasSelectedText():
            return ""
        shown, start = super().text(), self.selectionStart()
        end = start + len(self.selectedText())
        cut = shown.find("…") if shown != self._full else -1
        if cut < 0 or not start <= cut < end:
            return self.selectedText()
        return self._full[start : len(self._full) - (len(shown) - end)]

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        if event.matches(QKeySequence.StandardKey.Copy) and self.hasSelectedText():
            QGuiApplication.clipboard().setText(self.selected_path_text())
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):  # pylint: disable=invalid-name
        if not self._full:
            return
        menu = QMenu(self)
        if self.hasSelectedText():
            copy = menu.addAction("Copy")
            copy.triggered.connect(
                lambda: QGuiApplication.clipboard().setText(self.selected_path_text())
            )
        copy_path = menu.addAction("Copy path")
        copy_path.triggered.connect(lambda: QGuiApplication.clipboard().setText(self._full))
        menu.exec(event.globalPos())


class HDF5Viewer(DockAreaWidget):
    """
    Viewer for the scans BEC has written and for HDF5 files in general.

    The scan list, the signals of a scan and the plot are served from BEC's scan history and
    the Data API. The panes are fixed docks of a basic dock area, like those of the other views
    of the application: the scans, the Signals and File tabs, and the plot. The file view lists a file one group at a time and reads one frame, the
    rows in view or a reduced overview of a dataset. A file is opened for each read and
    closed again, without a file lock, and a file that is still being written is not read.
    """

    PLUGIN = True
    RPC = True
    ICON_NAME = "data_exploration"
    USER_ACCESS = [*BECWidget.USER_ACCESS, "open_file", "show_scan"]

    def __init__(self, parent: QWidget | None = None, client=None, config=None, gui_id=None, **kw):
        super().__init__(
            parent=parent,
            client=client,
            config=config,
            gui_id=gui_id,
            title="HDF5 Viewer",
            variant="cards",
            **kw,
        )
        self.get_bec_shortcuts()
        self._entry: ScanEntry | None = None
        self._file_path = ""
        self._file_shown = ""
        self._file_sizes: dict[str, int] = {}
        self._keep_file = False
        self._select_when_listed = ""
        self._curves: dict[CurveKey, tuple[object, bool]] = {}
        #: The curves and the x axis of the last refresh: a change of either ranges the plot.
        self._shown_state: tuple | None = None
        self._plot_note = ""
        self._plot_errors: dict[CurveKey, str] = {}
        self._shown_once = False
        #: The node of the row picked by hand last in the File tab since it came to the front:
        #: only such a dataset opens the file's preview when the scan's plot cannot draw it.
        self._picked_node: H5Node | None = None
        #: A dataset the scan's plot can draw that the File tab was asked to open in its
        #: preview all the same, e.g. one longer than the plot reads by itself.
        self._preview_path = ""
        #: The datasets of the scan files on the scan's plot that are no signals, in the order
        #: they were put on. They stay for the next scan and are read from its file.
        self._file_paths: list[str] = []
        #: Those of them read in full although longer than the plot reads by itself.
        self._file_full: set[str] = set()
        #: Each of them for each scan on the plot, by (scan id, path).
        self._file_curves: dict[tuple[str, str], _FileCurve] = {}
        self._file_channel = f"viewer-{id(self)}-file-curve"
        #: The colour and line style of each history curve, as the last refresh gave them.
        self._curve_styles: dict[CurveKey, tuple[str, str]] = {}

        self.service = H5Service(self)
        self.history_manager = BECHistoryManager(parent=self, client=self.client)

        # Left: the scans
        self.scan_list = ScanList(self)
        self.scan_list.setObjectName("scan_list")

        # Middle: the signals of the scan, or the contents of its file
        self.signal_list = SignalList(self)
        self.signal_list.setObjectName("signal_list")
        self.tree = H5Tree(self.service, self)
        self.tree.setObjectName("file_tree")
        self.details = H5DetailsPanel(self)
        self.details.setObjectName("file_details")
        # The tree and the details of its selection share the File tab: a tab of a dock holds
        # one widget, so this one split stays a splitter.
        self.file_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.file_splitter.addWidget(self.tree)
        self.file_splitter.addWidget(self.details)
        self.file_splitter.setStretchFactor(0, 3)
        self.file_splitter.setStretchFactor(1, 2)
        self.file_splitter.setChildrenCollapsible(False)
        self.open_button = QToolButton(self)
        self.open_button.setObjectName("open_file_button")
        self.open_button.setText("Open file…")
        self.open_button.setIcon(material_icon("folder_open", convert_to_pixmap=False))
        self.open_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.open_button.setAutoRaise(True)
        self.open_button.setToolTip(
            "Open an HDF5 file; one that BEC wrote is listed under Imported"
        )

        # Right: the plot of the signals, or the preview of a dataset
        self.plot_title = QLabel(self)
        font = self.plot_title.font()
        font.setWeight(QFont.Weight.DemiBold)
        self.plot_title.setFont(font)
        self.plot_subtitle = FactsLabel(parent=self)
        mute(self.plot_subtitle)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title_row.addWidget(self.plot_title)
        title_row.addWidget(self.plot_subtitle, 1)
        # Names the curves that could not be read while the others are drawn.
        self.read_note = QWidget(self)
        self.read_note.setObjectName("read_note")
        note_row = QHBoxLayout(self.read_note)
        note_row.setContentsMargins(0, 0, 0, 0)
        note_row.setSpacing(6)
        self.read_note_icon = QLabel(self.read_note)
        self.read_note_icon.setPixmap(material_icon("data_alert", size=(16, 16)))
        self.read_note_text = ElidedLabel(parent=self.read_note)
        self.read_note_button = QPushButton("Try again", self.read_note)
        self.read_note_button.setObjectName("read_note_try_again")
        self.read_note_button.setToolTip("Read the scans of these curves again")
        self.read_note_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.read_note_button.clicked.connect(self._act_on_read_note)
        # A dataset longer than the plot reads: the File tab's preview, made for long data.
        self.read_note_open = QPushButton("Open in the File tab", self.read_note)
        self.read_note_open.setObjectName("read_note_open")
        self.read_note_open.setToolTip(
            "Show this dataset in the File tab's preview, whose overview can be zoomed into"
        )
        self.read_note_open.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.read_note_open.clicked.connect(self._open_large_in_file)
        self.read_note_open.hide()
        self._read_note_path = ""
        note_row.addWidget(self.read_note_icon)
        note_row.addWidget(self.read_note_text, 1)
        note_row.addWidget(self.read_note_button)
        note_row.addWidget(self.read_note_open)
        self.read_note.hide()
        self.add_button, self.add_menu, self._add_reset_timer = self._make_add_button(
            "add_to_plot_button", "Send what this plot shows to another plot"
        )
        self.add_menu.aboutToShow.connect(self._fill_add_menu)
        # Heatmap | Scatter | Lines, for scans that moved two motors.
        self.view_switch = ViewSwitch(self)
        self.view_switch.setObjectName("view_switch")
        self.view_switch.hide()
        self.view_switch.chosen.connect(self._on_view_chosen)
        #: The view the user chose, for grid scans, for the other area scans and for the
        #: other scans of two motors.
        self._view_choice: dict[str, str] = {}
        #: Whether the points of a finished scan of two motors lie on one line, per scan id.
        self._one_line: dict[str, bool] = {}
        #: BEC's readout groups of the finished scans whose file was read, by scan id.
        self._readouts: dict[str, dict[str, str] | None] = {}
        #: The view a scan had while it ran: it keeps it when it ends (never a jump by itself).
        self._kept_view: tuple[str, str] | None = None
        self._map_shown = False
        #: How to give the plot that was replaced last what it showed before.
        self._undo: Undo | None = None
        title_row.addWidget(self.view_switch)
        title_row.addWidget(self.add_button)
        self.waveform = Waveform(parent=self, client=self.client)
        # No size question pops up here: a curve too large to load says so on the plot and
        # offers to load it.
        self.waveform.skip_large_dataset_warning = True
        self.waveform.history_read_failed.connect(self._on_history_read_failed)
        self.plot_state = StatePage(self)
        self.plot_stack = QStackedWidget(self)
        self.plot_stack.addWidget(self.plot_state)
        self.plot_stack.addWidget(self.waveform)
        self.maps = MapPlots(self.plot_stack, client=self.client, parent=self)
        self.maps.ready.connect(self._on_map_ready)
        #: Says that a map is still loading when its data takes long.
        self._map_wait_timer = QTimer(self)
        self._map_wait_timer.setSingleShot(True)
        self._map_wait_timer.setInterval(MAP_WAIT_MS)
        self._map_wait_timer.timeout.connect(self._on_map_slow)
        #: Looks whether the curves of newly picked scans have their data, to show them then.
        self._lines_wait_timer = QTimer(self)
        self._lines_wait_timer.setInterval(LINES_WAIT_POLL_MS)
        self._lines_wait_timer.timeout.connect(self._check_lines_loaded)
        self._lines_wait_started = 0.0
        self.plot_page = QWidget(self)
        plot_layout = QVBoxLayout(self.plot_page)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(6)
        plot_layout.addLayout(title_row)
        plot_layout.addWidget(self.read_note)
        plot_layout.addWidget(self.plot_stack, 1)
        self.preview = H5Preview(self.service, client=self.client, parent=self)
        self.preview.setObjectName("dataset_preview")
        #: The File tab: what its plot draws, by role, over the tree and its details.
        self.file_box = FileBox(self.preview, self.service, self.file_splitter, self)
        # The same button for the dataset shown in the File tab.
        self.file_add_button, self.file_add_menu, self._file_add_reset_timer = (
            self._make_add_button("file_add_to_plot_button", COPY_TOOLTIP)
        )
        self.file_add_menu.aboutToShow.connect(self._fill_file_add_menu)
        self.file_add_button.hide()
        self._copy_channel = f"viewer-copy-{id(self)}"
        self._copying = False
        # While the preview covers the scan's plot: the plot again, the selection stays.
        self.back_button = QToolButton(self)
        self.back_button.setObjectName("back_to_plot_button")
        self.back_button.setText("Back to the plot")
        self.back_button.setIcon(material_icon("arrow_back", convert_to_pixmap=False))
        self.back_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.back_button.setAutoRaise(True)
        self.back_button.setToolTip("Show the scan's plot again; the row stays selected")
        self.back_button.clicked.connect(self._on_back_clicked)
        self.back_button.hide()
        self.preview.add_header_widget(self.back_button)
        self.preview.add_header_widget(self.file_add_button)
        self.preview.shown_changed.connect(self._update_file_add_button)
        self.right_stack = QStackedWidget(self)
        self.right_stack.addWidget(self.plot_page)
        self.right_stack.addWidget(self.preview)
        self.preview.set_reading(False)

        self._build_docks()

        # Bottom: the full path of the file that is read, and how much of it was read.
        self.status_bar = QWidget(self)
        self.status_bar.setObjectName("status_bar")
        self.status_label = PathLabel(self.status_bar)
        self.status_label.setObjectName("status_label")
        mute(self.status_label)
        # The bar keeps its height while there is no file to name.
        self.status_label.setMinimumHeight(self.status_label.fontMetrics().height())
        self.status_note = QLabel(self.status_bar)
        self.status_note.setObjectName("status_note")
        mute(self.status_note)
        status_row = QHBoxLayout(self.status_bar)
        status_row.setContentsMargins(8, 2, 8, 4)
        status_row.setSpacing(6)
        status_row.addWidget(self.status_label)
        status_row.addWidget(self.status_note)
        status_row.addStretch(1)
        self._root_layout.addWidget(self.status_bar)

        # Looks for curves without points once their data is in.
        self._empty_checks = 0
        self._empty_timer = QTimer(self)
        self._empty_timer.setSingleShot(True)
        self._empty_timer.setInterval(EMPTY_CHECK_MS)
        self._empty_timer.timeout.connect(self._check_empty_curves)
        self._busy_timer = QTimer(self)
        self._busy_timer.setSingleShot(True)
        self._busy_timer.setInterval(BUSY_RETRY_MS)
        self._busy_timer.timeout.connect(self._reopen_file)
        # A scan's file looks busy for a few seconds after the scan: its reads come back then.
        self._reread_timer = QTimer(self)
        self._reread_timer.setSingleShot(True)
        self._reread_timer.setInterval(BUSY_RETRY_MS)
        self._reread_timer.timeout.connect(self._reread_shown)
        # Holding an arrow key walks many scans: only the one it stops on is loaded.
        self._pending_entry: ScanEntry | None = None
        self._switch_timer = QTimer(self)
        self._switch_timer.setSingleShot(True)
        self._switch_timer.setInterval(0)
        self._switch_timer.timeout.connect(self._switch_to_pending)
        # A newly picked scan replaces the plot in one step: the pane keeps the picture of the
        # scan before until the new one is drawn, at most SWITCH_HOLD_MS after the click.
        self._held = False
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.setInterval(SWITCH_HOLD_MS)
        self._hold_timer.setTimerType(Qt.TimerType.PreciseTimer)  # never before its time
        # The data may wait in the event queue behind a busy stretch: it runs first.
        self._hold_timer.timeout.connect(lambda: QTimer.singleShot(0, self, self._end_hold))
        #: When a loading page of the plot came on screen.
        self._loading_since = 0.0
        self._hold_poll = QTimer(self)
        self._hold_poll.setInterval(LINES_WAIT_POLL_MS)
        self._hold_poll.timeout.connect(self._release_when_drawn)
        #: How the Data API keys the signals of each finished scan, once asked.
        self._described: dict[str, dict[SourceKey, str]] = {}
        #: The scans opened from their files that are listed, by their imported id.
        self._imported: dict[str, ImportedScan] = {}
        # BEC's client reads the scan history in a thread: the list says so until it is read.
        self._history_waited = 0
        self._history_timer = QTimer(self)
        self._history_timer.setInterval(HISTORY_POLL_MS)
        self._history_timer.timeout.connect(self._poll_history)

        self.scan_list.scan_selected.connect(self._on_scan_selected)
        self.scan_list.view.key_released.connect(self._on_key_released)
        self.scan_list.pins_changed.connect(self._refresh_plot)
        self.scan_list.reload_requested.connect(self._load_history)
        self.scan_list.offer_open_file = True
        self.scan_list.lists_running_scans = True
        self.scan_list.open_file_requested.connect(self._choose_file)
        self.scan_list.remove_requested.connect(self.remove_imported)
        self.scan_list.context_menu_requested.connect(self._show_scan_menu)
        self.signal_list.selection_changed.connect(self._refresh_plot)
        self.signal_list.selection_changed.connect(self._on_plot_choice)
        self.signal_list.dataset_removed.connect(self._on_dataset_removed)
        self.signal_list.reset_requested.connect(self._on_signals_reset)
        self.signal_list.open_requested.connect(self._open_signal_in_file)
        self.signals_dock.dockAreaWidget().currentChanged.connect(self._on_tab_changed)
        self.open_button.clicked.connect(self._choose_file)
        self.tree.node_selected.connect(self.preview.show_node)
        self.tree.node_selected.connect(self._on_tree_node)
        self.tree.node_picked.connect(self._on_tree_picked)
        self.tree.keep_toggled.connect(self._on_tree_keep)
        self.preview.kept_changed.connect(self._update_tree_marks)
        self.preview.kept_changed.connect(self._update_right_page)
        self.preview.shown_changed.connect(self._update_right_page)
        self.file_box.link(
            self._reset_plot,
            self._plot_is_default,
            self._x_owner,
            self._scan_owner,
            self._on_tree_keep,
            y_state=self._file_y_state,
            shown_file=lambda: self._file_shown,
        )
        self.tree.x_toggled.connect(self._on_tree_x)
        self.tree.z_toggled.connect(self._on_tree_z)
        self.tree.file_failed.connect(self._on_file_failed)
        self.tree.file_listed.connect(lambda _path: self._busy_timer.stop())
        self.preview.details_changed.connect(self.details.set_details)
        self.preview.details_changed.connect(lambda _details: self._update_status())
        self.service.bytes_read_changed.connect(lambda _path: self._update_status())
        self.history_manager.scan_history_refreshed.connect(self._on_history_refreshed)
        self.history_manager.scan_history_updated.connect(self._on_history_updated)
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())

        self._switch_to(None)
        self._load_history()

    ################################################################################
    # Public interface
    ################################################################################

    @SafeSlot()
    def open_file(self, file_path: str, dataset: str = "") -> None:
        """
        Show an HDF5 file in the file view.

        The file is opened for each read and closed again: the file of a scan BEC lists as the
        Data API opens it, any other file without a file lock. A file that is still being
        written is not read until its writer is done.

        Args:
            file_path (str): Path of the file.
            dataset (str): Path of a dataset or group inside the file to select.
        """
        file_path = str(Path(file_path).expanduser())
        listed = next(
            (entry for entry in self.scan_list.model.entries() if entry.file_path == file_path),
            None,
        )
        if listed is not None and listed.imported:
            # Opened before: its row is selected again, no second one is added.
            self._select_listed(listed.scan_id, dataset)
            return
        if listed is not None and self.scan_list.select(listed.scan_id):
            self._switch_now()
            self.file_dock.setAsCurrentTab()
            self._show_file(dataset)
            return
        # A file that BEC wrote is listed as an imported scan; which it is, is read off the
        # GUI thread first. Any other file opens in the File tab.
        channel = f"viewer-{id(self)}-import"
        self.service.cancel(channel)
        self.service.request(
            channel,
            file_path,
            lambda ctx: h5_reader.bec_scan_file(file_path, cancel=ctx.cancelled),
            lambda scan: self._on_file_scan(file_path, dataset, scan),
            lambda error: self._on_file_scan_failed(file_path, dataset, error),
        )

    def _on_file_scan(self, file_path: str, dataset: str, scan) -> None:
        """The scan an opened file names is known: list it, or open the file as it is."""
        if scan is None:
            self._open_by_hand(file_path, dataset)
            return
        known = self.scan_list.model.entry(scan.scan_id)
        if known is not None and not known.imported:
            # The scan is in the history: its row, nothing added.
            self._select_listed(known.scan_id, dataset)
            return
        listed = next(
            (
                entry
                for entry in self.scan_list.model.entries()
                if entry.imported and entry.file_path == file_path
            ),
            None,
        )
        if listed is None:
            scan_id = imported_id(file_path)
            imported = ImportedScan(
                scan_id=scan_id,
                file_path=file_path,
                file_scan_id=scan.scan_id,
                scan_number=scan.scan_number,
                dataset_number=scan.dataset_number,
                scan_name=scan.scan_name,
                exit_status=scan.status,
                start_time=scan.start_time,
                end_time=scan.end_time,
                num_points=scan.num_points,
                num_monitored_readouts=scan.num_monitored_readouts,
                stored_data_info=scan.stored_data_info,
                request_inputs=scan.request_inputs,
            )
            self._imported[scan_id] = imported
            register_imported(self.client, imported)
            self.scan_list.add_entry(ScanEntry.from_file_scan(scan_id, scan))
            self._name_listed_files()
            listed = self.scan_list.model.entry(scan_id)
        self._select_listed(listed.scan_id, dataset)

    def _on_file_scan_failed(self, file_path: str, dataset: str, error: H5ReadError) -> None:
        if error.kind == "cancelled":
            return
        # The File tab says what is wrong with the file, as for any file.
        self._open_by_hand(file_path, dataset)

    def _select_listed(self, scan_id: str, dataset: str = "") -> None:
        """Select a listed scan; the tab in front stays, unless a dataset is to be shown."""
        if not self.scan_list.select(scan_id):
            # Hidden by the search or a filter: those make room for it.
            self.scan_list.clear_filter()
            self.scan_list.select(scan_id)
        self._switch_now()
        if dataset:
            self.file_dock.setAsCurrentTab()
            self._show_file(dataset)

    def remove_imported(self, entry: ScanEntry) -> None:
        """
        Take a scan opened from its file off the scan list. The file is not touched.

        Args:
            entry (ScanEntry): The imported scan.
        """
        if not entry.imported:
            return
        self.scan_list.remove_entry(entry.scan_id)
        self._forget_imported(entry.scan_id)
        self._switch_now()

    def _forget_imported(self, scan_id: str) -> None:
        self._imported.pop(scan_id, None)
        forget_imported(self.client, scan_id)
        self._described.pop(scan_id, None)
        self._name_listed_files()

    def _open_by_hand(self, file_path: str, dataset: str = "") -> None:
        """Show a file that is no listed scan in the File tab, with nothing selected."""
        self._keep_file = True
        try:
            self.scan_list.clear_selection()
            self._switch_now()
        finally:
            self._keep_file = False
        self._file_path = file_path
        self._file_shown = ""
        self.file_dock.setAsCurrentTab()
        self._show_file(dataset)

    @SafeSlot()
    def show_scan(self, scan: int | str) -> None:
        """
        Select a scan of the scan history.

        Scan numbers can repeat (e.g. after a counter reset): for a number shared by several
        scans the newest of them is selected. A scan id always names one scan.

        Args:
            scan (int | str): Scan number or scan id.

        Raises:
            ValueError: If the scan is not in the scan history.
        """
        # The scans are listed newest first, so the first match of a number is its newest scan.
        for entry in self.scan_list.model.entries():
            if scan in (entry.scan_id, entry.scan_number):
                self.scan_list.search_edit.clear()
                self.scan_list.ending_buttons["all"].click()
                self.scan_list.select(entry.scan_id)
                self._switch_now()
                return
        raise ValueError(f"Scan {scan} is not in the scan history.")

    ################################################################################
    # Scans
    ################################################################################

    @staticmethod
    def _padded(widget: QWidget, name: str, minimum_width: int) -> QWidget:
        holder = QWidget()
        holder.setObjectName(name)
        holder.setMinimumWidth(minimum_width)
        layout = QVBoxLayout(holder)
        # The cards of the dock area pad their content by 2 px; with these margins the content
        # sits 8 px in from the card's edge and 4 px above its bottom.
        layout.setContentsMargins(6, 6, 6, 2)
        layout.addWidget(widget)
        return holder

    def _build_docks(self) -> None:
        """
        Lay the panes out as fixed docks: the scans on the left, the Signals and File tabs in
        the middle and the plot on the right. Their widths are set once the viewer has its own,
        see ``_open_widths``.
        """
        fixed = {"closable": False, "floatable": False, "movable": False, "return_dock": True}
        # Every pane has the title tab of a dock in the dock area, without its buttons.
        no_buttons = {"menu": False, "float": False, "close": False}
        self.plot_dock = self.new(
            self._padded(self.right_stack, "Plot", 240),
            title_buttons=no_buttons,
            apply_widget_icon=False,
            **fixed,
        )
        self.scans_dock = self.new(
            self._padded(self.scan_list, "Scans", 240),
            where="left",
            title_buttons=no_buttons,
            apply_widget_icon=False,
            **fixed,
        )
        self.signals_dock = self.new(
            self._padded(self.signal_list, "Signals", 300),
            where="right",
            relative_to=self.scans_dock,
            title_buttons=no_buttons,
            apply_widget_icon=False,
            **fixed,
        )
        self.file_dock = self.new(
            self._padded(self.file_box, "File", 300),
            tab_with=self.signals_dock,
            title_buttons=no_buttons,
            apply_widget_icon=False,
            **fixed,
        )
        self.signals_dock.setToolTip("The signals BEC stored for the scan")
        self.file_dock.setToolTip("Everything that is in the scan's file")
        self.signals_dock.tabWidget().setToolTip(self.signals_dock.toolTip())
        self.file_dock.tabWidget().setToolTip(self.file_dock.toolTip())
        # "Open file…" sits in the Scans card, at the right end of its search row: a BEC file
        # becomes a scan of the list.
        self.scan_list.set_search_button(self.open_button)
        self.signals_dock.setAsCurrentTab()
        for dock in (self.plot_dock, self.scans_dock, self.signals_dock, self.file_dock):
            for scroll in dock.findChildren(QScrollArea, "dockWidgetScrollArea"):
                # A click beside the controls of a pane, e.g. on a field that takes no typing,
                # leaves the focus where it was: the pane itself is no focus target.
                scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _open_widths(self) -> None:
        """
        Give the panes their opening widths: the scan list SCAN_LIST_OPEN_WIDTH wide, the middle
        pane MIDDLE_OPEN_WIDTH and the plot all the rest. In a viewer too narrow for that, the
        plot keeps the width its toolbar needs to show every button while the middle pane, and
        then the scans pane, give way down to their minimums. Nothing is stored: a pane dragged
        to another width keeps it until the viewer opens again.

        It runs once the viewer has its real width: a viewer built before it is shown, as in
        bec-app, would otherwise open with the widths of its first, tiny layout.
        """
        areas = [
            dock.dockAreaWidget() for dock in (self.scans_dock, self.signals_dock, self.plot_dock)
        ]
        splitter = areas[2].parentSplitter() if areas[2] is not None else None
        if splitter is None or any(
            area is None or area.parentSplitter() is not splitter for area in areas
        ):
            return
        total = sum(splitter.sizes())
        scans = SCAN_LIST_OPEN_WIDTH + self._room_beside(
            areas[0], self.scan_list, SCAN_LIST_PADDING
        )
        middle = MIDDLE_OPEN_WIDTH
        plot_need = self._plot_toolbar_need(areas[2])
        missing = plot_need - (total - scans - middle)
        for index, area in ((1, areas[1]), (0, areas[0])):
            if missing <= 0:
                break
            width = middle if index == 1 else scans
            give = min(missing, max(0, width - area.minimumSizeHint().width()))
            missing -= give
            if index == 1:
                middle -= give
            else:
                scans -= give
        widths = dict(zip(map(splitter.indexOf, areas), (scans, middle, total - scans - middle)))
        splitter.setSizes([widths.get(index, 0) for index in range(splitter.count())])

    def _plot_toolbar_need(self, plot_area: QWidget) -> int:
        """
        The width the plot's pane needs to show every button of the plot's toolbar.

        The plot page may not be shown yet, so the room beside the toolbar is summed from the
        layout margins between it and the pane's stack, which is laid out.
        """
        toolbar = self.waveform.toolbar
        if toolbar.isVisible():
            return toolbar.sizeHint().width() + self._room_beside(
                plot_area, toolbar, PLOT_TOOLBAR_PADDING
            )
        room = self._room_beside(plot_area, self.right_stack, PLOT_TOOLBAR_PADDING)
        widget = toolbar.parentWidget()
        while widget is not None and widget is not self.right_stack:
            # Plain QWidget.layout: a plot keeps its own layout in an attribute of that name. A
            # stacked layout gives its pages its whole rectangle, whatever its margins.
            layout = QWidget.layout(widget)
            if layout is not None and not isinstance(layout, QStackedLayout):
                margins = layout.contentsMargins()
                room += margins.left() + margins.right()
            widget = widget.parentWidget()
        return toolbar.sizeHint().width() + room

    @staticmethod
    def _room_beside(area: QWidget, widget: QWidget, fallback: int) -> int:
        """The width of a pane that its widget does not get, or the fallback before layout."""
        room = area.width() - widget.width()
        return room if widget.width() > 0 and room >= 0 else fallback

    def _keep_list_widths(self) -> None:
        """
        Let the plot alone give or take the room when the viewer gets narrower or wider: the
        lists keep their widths, down to their minimum, as they did in the old splitter.

        A dock area makes its panes resize in proportion; this runs after it.
        """
        plot_area = self.plot_dock.dockAreaWidget()
        splitter = plot_area.parentSplitter() if plot_area is not None else None
        if splitter is None:
            return
        for index in range(splitter.count()):
            splitter.setStretchFactor(index, 1 if splitter.widget(index) is plot_area else 0)

    def hideEvent(self, event):  # pylint: disable=invalid-name
        """A hidden viewer holds no picture: shown again, it paints what it has."""
        self._release_plot()
        super().hideEvent(event)

    def showEvent(self, event):  # pylint: disable=invalid-name
        """On the first show, once the viewer has its width, open and keep the panes' widths."""
        super().showEvent(event)
        if not self._shown_once:
            self._shown_once = True
            QTimer.singleShot(0, self, self._open_and_keep_widths)

    def _open_and_keep_widths(self) -> None:
        self._open_widths()
        self._keep_list_widths()

    def file_tab_current(self) -> bool:
        """
        Whether the File tab is the one shown in the middle.

        Returns:
            bool: True for the File tab, False for the Signals tab.
        """
        return self.file_dock.isCurrentTab()

    def _load_history(self) -> None:
        self.scan_list.show_loading()
        if not self._history_loaded():
            self._history_waited = 0
            self._history_timer.start(HISTORY_POLL_MS)
            return
        self._read_history()

    def _history_loaded(self) -> bool:
        """Whether BEC's client has read the scan history (it reads it in a thread)."""
        history = getattr(self.client, "history", None)
        loaded = getattr(history, "_scan_history_loaded_event", None)
        return loaded is None or bool(loaded.is_set())

    @SafeSlot()
    def _poll_history(self) -> None:
        if self._history_loaded():
            self._history_timer.stop()
            self._read_history()
            return
        self._history_waited += self._history_timer.interval()
        if self._history_waited >= HISTORY_WAIT_MS and self._history_timer.interval() < 1000:
            # Say so, and keep looking, less often: a late answer still shows the scans.
            self._history_timer.setInterval(1000)
            self.scan_list.show_load_failed(
                f"BEC did not answer within {HISTORY_WAIT_MS // 1000} s."
            )

    def _read_history(self) -> None:
        try:
            self.history_manager.refresh_scan_history()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(f"HDF5 viewer: the scan history could not be read: {exc}")
            self.scan_list.show_load_failed(f"Reading it from BEC failed: {exc}")

    @SafeSlot(list)
    def _on_history_refreshed(self, history: list) -> None:
        # The history answered (also by BEC's callback once its loader read the scans).
        self._history_timer.stop()
        live = [entry for entry in self.scan_list.model.entries() if entry.live]
        self._described.clear()  # asked again for the scans as they are read now
        entries = [ScanEntry.from_history(msg) for msg in history]
        known = {entry.scan_id for entry in entries}
        imported = [entry for entry in self.scan_list.model.entries() if entry.imported]
        # An imported scan that the history lists now is listed from the history only.
        for entry in imported:
            if self._imported_file_id(entry.scan_id) in known:
                self._forget_imported(entry.scan_id)
        imported = [entry for entry in imported if entry.scan_id in self._imported]
        self.scan_list.set_entries(
            entries + [entry for entry in live if entry.scan_id not in known] + imported
        )
        self._name_listed_files()

    @SafeSlot(dict)
    def _on_history_updated(self, msg: dict) -> None:
        for scan_id in list(self._imported):
            if self._imported_file_id(scan_id) == msg.get("scan_id"):
                self.scan_list.remove_entry(scan_id)
                self._forget_imported(scan_id)
        self.scan_list.add_entry(ScanEntry.from_history(msg))
        self._name_listed_files()

    def _imported_file_id(self, scan_id: str) -> str:
        """The scan id the file of an imported scan names."""
        scan = self._imported.get(scan_id)
        return scan.file_scan_id if scan is not None else ""

    def _name_listed_files(self) -> None:
        """
        Tell the reader which files belong to finished scans of the history: it opens them
        as the Data API does, so that the two share the open instead of refusing each other.
        """
        h5_reader.set_listed_files(
            self,
            (
                entry.file_path
                for entry in self.scan_list.model.entries()
                if not entry.live and entry.file_path
            ),
        )

    @SafeSlot(dict, dict)
    def on_scan_status(self, msg: dict, _meta: dict) -> None:
        """
        List the running scan at the top and let it go when it has ended.

        Args:
            msg (dict): Content of a ``ScanStatusMessage``.
            _meta (dict): Metadata of the message.
        """
        scan_id = msg.get("scan_id")
        if not scan_id:
            return
        existing = self.scan_list.model.entry(scan_id)
        if existing is not None and not existing.live:
            return
        status = msg.get("status") or "open"
        if status not in ("open", "paused"):
            # The history entry replaces this one as soon as the file is written.
            self._call_later(LIVE_LINGER_MS, lambda: self._forget_live(scan_id))
            return
        priority = msg.get("readout_priority") or {}
        # Lists in a message may arrive as numpy arrays: no truth tests on them.
        readouts = {
            device: readout for readout, devices in priority.items() for device in _names(devices)
        }
        stored: dict = {}
        kinds: dict[SourceKey, str] = {}
        for kind in ("monitored", "async"):
            for device in _names(priority.get(kind)):
                signal = self._default_entry(device)
                if signal:
                    # The shape is not known before the scan is done.
                    stored[device] = {signal: {"shape": (0,), "dtype": ""}}
                    kinds[(device, signal)] = kind
        entry = ScanEntry(
            scan_id=scan_id,
            scan_number=msg.get("scan_number"),
            scan_name=msg.get("scan_name") or "",
            status=status,
            start_time=float(msg.get("timestamp") or 0.0),
            num_points=msg.get("num_points"),
            motors=tuple(_names(msg.get("scan_report_devices"))),
            stored_data_info=stored,
            signal_kinds=kinds,
            readout_groups=readouts,
            live=True,
        )
        if scan_id not in self._one_line and len(entry.motors) >= 2:
            # Known from the planned positions once, at its start: the Heatmap button is right
            # while the scan runs, and its file need not be read for it after the end.
            on_line = planned_on_one_line(msg.get("info"))
            if on_line is not None:
                self._one_line[scan_id] = on_line
        self.scan_list.add_entry(entry)

    def _default_entry(self, device: str) -> str:
        """The signal of a device that the plots draw when only the device is named."""
        try:
            return self.waveform.entry_validator.validate_signal(device, None)
        except Exception:  # pylint: disable=broad-except
            return ""

    def _forget_live(self, scan_id: str) -> None:
        entry = self.scan_list.model.entry(scan_id)
        if entry is not None and entry.live:
            self.scan_list.model.remove(scan_id)

    def _signal_kinds(self, entry: ScanEntry) -> dict[SourceKey, str]:
        """Ask the Data API how each stored signal is keyed. Nothing is read for this."""
        if entry.signal_kinds:
            return entry.signal_kinds
        if entry.scan_id in self._described:
            return self._described[entry.scan_id]
        sources = [
            (device, signal)
            for device, signals in (entry.stored_data_info or {}).items()
            for signal in signals
        ]
        if not sources:
            return {}
        try:
            described = self.client.data_api.describe(sources, scan=entry.scan_id)
            kinds = {
                key: str(info.kind)
                for key, info in described.items()
                if getattr(info, "available", False) and getattr(info, "kind", None)
            }
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug(f"HDF5 viewer: the Data API could not describe {entry.scan_id}: {exc}")
            return {}
        if not entry.live:
            # A finished scan's signals keep their kind: picked again, it is not asked again.
            self._described[entry.scan_id] = kinds
            while len(self._described) > DESCRIBED_KEPT:
                del self._described[next(iter(self._described))]  # the oldest answer
        return kinds

    def _readouts_of(self, entry: ScanEntry | None) -> dict[str, str] | None:
        """BEC's readout group of each device of a scan, None while not known."""
        if entry is None:
            return None
        if entry.readout_groups:
            return entry.readout_groups
        return self._readouts.get(entry.scan_id) or None

    def _read_readouts(self, entry: ScanEntry | None) -> None:
        """
        Read the readout groups of a finished scan from its file, once and off the GUI thread.
        Until they are known the signal list sorts by the shape of the data.
        """
        if (
            entry is None
            or entry.live
            or entry.readout_groups
            or not entry.file_path
            or entry.scan_id in self._readouts
        ):
            return
        scan_id = entry.scan_id
        self._readouts[scan_id] = None  # being read; an empty answer: the file names none

        def done(readouts: dict[str, str]) -> None:
            self._readouts[scan_id] = readouts
            if self._entry is None or self._entry.scan_id != scan_id:
                return
            if readouts:
                self.signal_list.set_readouts(readouts)
            else:
                self.signal_list.mark_grouped_by_shape()

        def failed(error: H5ReadError) -> None:
            if error.kind in ("cancelled", "busy"):
                # Look again when the scan is picked next time, or soon for a file that
                # was written a moment ago.
                self._readouts.pop(scan_id, None)
                if error.kind == "busy":
                    self._reread_timer.start()
                return
            # A file that is missing or cannot be read: grouped by shape, not tried again.
            logger.debug(
                f"HDF5 viewer: the readout groups of {scan_id} were not read: {error.message}"
            )
            self._readouts[scan_id] = {}
            if self._entry is not None and self._entry.scan_id == scan_id:
                self.signal_list.mark_grouped_by_shape()

        self.service.request(
            f"viewer-{id(self)}-readouts",
            entry.file_path,
            lambda _ctx: h5_reader.readout_groups(entry.file_path),
            done,
            failed,
        )

    def _on_scan_selected(self, entry: ScanEntry | None) -> None:
        # The switch waits for the event loop: row changes that come faster than a scan
        # loads (a held arrow key) end in one load, of the last row.
        self._pending_entry = entry
        self._hold_plot()
        # The scans a held key walks past are not read at all.
        self._switch_timer.start(HOLD_SETTLE_MS if self.scan_list.view.key_held else 0)

    @SafeSlot()
    def _on_key_released(self) -> None:
        if self._switch_timer.isActive():
            # The key is up: load now, still after the input that is queued.
            self._switch_timer.start(0)

    def _switch_now(self) -> None:
        """Do a switch that waits for the event loop now: a call asks for its result at once."""
        if self._switch_timer.isActive():
            self._switch_timer.stop()
            self._switch_to_pending()

    @SafeSlot()
    def _switch_to_pending(self) -> None:
        # The curves of the scan before go and those of this scan come: the RPC registry
        # tells its listeners once for the whole switch, not once per curve.
        with RPCRegister.delayed_broadcast():
            self._switch_to(self._pending_entry)
        self._release_when_drawn()

    # -- one step from the plot of a scan to the plot of another -----------------------------

    def _hold_plot(self) -> None:
        """
        Keep the plot pane as it is on screen while a newly picked scan is read, so that its
        loading states and half-drawn curves never show for the moment the read takes. A
        click during a hold does not lengthen it.
        """
        if self._held or self.right_stack.currentWidget() is not self.plot_page:
            return
        if not self.plot_page.isVisible():
            return
        self._held = True
        self.plot_page.setUpdatesEnabled(False)
        self._hold_timer.start()
        self._hold_poll.start()

    def _plot_waits(self) -> bool:
        """Whether the plot of the picked scans still waits for data that is being read."""
        if self._map_shown:
            return (
                self.plot_stack.currentWidget() is self.plot_state
                and self._map_wait_timer.isActive()
            )
        if self._lines_wait_timer.isActive():
            # Shows the plot at once if its data is in, rather than at the next look.
            self._check_lines_loaded()
        if self._lines_wait_timer.isActive() or self._lines_loading():
            return True
        return any(
            state.job is not None and state.item is None and not state.problem and not state.large
            for state in self._file_curves.values()
        )

    @SafeSlot()
    def _release_when_drawn(self) -> None:
        """End the hold once the picked scans are drawn, or nothing is read for them."""
        if not self._held or self._switch_timer.isActive() or self._plot_waits():
            return
        self._release_plot()

    @SafeSlot()
    def _end_hold(self) -> None:
        """The hold is over: the plot if its data is in by now, else the state of its read."""
        if self._held:
            if self._switch_timer.isActive() and not self.scan_list.view.key_held:
                # A scan picked during the hold waits behind it: the pane shows that scan,
                # never the one picked before it.
                self._switch_now()
            self._plot_waits()  # shows the plot whose data came in the meantime
            self._release_plot()

    @SafeSlot()
    def _release_plot(self) -> None:
        """Paint the plot pane again as it is now: drawn, or the state of its read."""
        self._hold_timer.stop()
        self._hold_poll.stop()
        if not self._held:
            return
        self._held = False
        if isValid(self.plot_page):
            self.plot_page.setUpdatesEnabled(True)
            if self.plot_stack.currentWidget() is self.plot_state:
                self._loading_since = time.monotonic()

    def _show_plot_page(self, page: QWidget) -> None:
        """Put a page on the plot pane; a loading page on screen stays LOADING_KEPT_MS first."""
        current = self.plot_stack.currentWidget()
        if current is page:
            return
        if current is self.plot_state and page is not self.plot_state and not self._held:
            left = LOADING_KEPT_MS / 1000 - (time.monotonic() - self._loading_since)
            if left > 0:
                QTimer.singleShot(int(left * 1000) + 1, self, self._show_wanted_page)
                return
        if page is self.plot_state and not self._held:
            self._loading_since = time.monotonic()
        self.plot_stack.setCurrentWidget(page)

    def _show_wanted_page(self) -> None:
        """After a kept loading page: the plot or map that has come in since, if still wanted."""
        if self.plot_stack.currentWidget() is not self.plot_state:
            return
        if self._map_shown:
            view = self.current_view()
            if self.maps.is_ready(view) and not self._map_wait_timer.isActive():
                self.plot_stack.setCurrentWidget(self.maps.widget(view))
        elif self._curves and not self._lines_wait_timer.isActive() and not self._lines_loading():
            if len(self._lines_failed()) < len(self._curves):
                self.plot_stack.setCurrentWidget(self.waveform)

    def _switch_to(self, entry: ScanEntry | None) -> None:
        self._entry = entry
        self._picked_node = None
        self._busy_timer.stop()
        self._reread_timer.stop()
        if entry is not None:
            self._file_path = entry.file_path
        elif not self._keep_file:
            self._file_path = ""
        self.signal_list.set_scan(
            entry,
            self._signal_kinds(entry) if entry is not None else None,
            self._readouts_of(entry),
        )
        self._read_readouts(entry)
        if entry is not None and self._readouts.get(entry.scan_id) == {}:
            self.signal_list.mark_grouped_by_shape()
        if self.file_tab_current() and not self._keep_file:
            self._show_file()
        self._update_right_page()
        self._update_status()

    ################################################################################
    # Plot of the signals
    ################################################################################

    def _plot_scans(self) -> list[tuple[ScanEntry, int]]:
        """The selected scan in palette slot 0 and the pinned ones in theirs."""
        scans: list[tuple[ScanEntry, int]] = []
        if self._entry is not None:
            scans.append((self._entry, 0))
        for entry, slot in self.scan_list.pinned_entries():
            if self._entry is None or entry.scan_id != self._entry.scan_id:
                scans.append((entry, slot))
        return scans

    @staticmethod
    def _plot_problem(device: str, error: Exception) -> str:
        """Say in plain words why a signal is not on the plot."""
        return f"{device} could not be plotted: {error}"

    def _view_kind(self) -> str:
        entry = self._entry
        if entry is not None and entry.scan_name in GRID_SCANS:
            return "grid"
        return "area" if is_area_scan(entry) else "path"

    def current_view(self) -> str:
        """
        How the selected scan is shown.

        Returns:
            str: ``heatmap`` or ``scatter`` for a map of its two motors, else ``lines``.
        """
        entry = self._entry
        if map_axes(entry) is None:
            return "lines"
        view = self._view_choice.get(self._view_kind(), default_view(entry))
        if view == "heatmap" and self._heatmap_off() and self._kept_view != (entry.scan_id, view):
            fallback = default_view(entry)
            return "scatter" if fallback == "heatmap" else fallback
        return view

    def _heatmap_off(self) -> str:
        """
        Why the selected scan has no heatmap: its points lie on one line. Empty while that is
        not known (a running scan without planned positions) or when the map is over axes the
        user chose.
        """
        entry = self._entry
        axes = map_axes(entry)
        if axes is None or self.signal_list.plane_axes() not in (None, axes):
            return ""
        return ONE_LINE_REASON if self._one_line.get(entry.scan_id) else ""

    def _reread_shown(self) -> None:
        """
        Read again what the shown scan's file was too busy to give: its readout groups and
        whether its points lie on one line. What is already known is not read again, and a
        running scan is not read at all.
        """
        self._read_readouts(self._entry)
        self._check_one_line()
        self._update_file_curves()

    def _check_one_line(self) -> None:
        """
        Find out, once per finished scan of two motors and off the GUI thread, whether its
        points lie on one line. A running scan is not read: its file is still being written.
        """
        entry = self._entry
        axes = map_axes(entry)
        if axes is None or entry.live or entry.scan_id in self._one_line or not entry.file_path:
            return
        paths = {signal.key: signal.dataset_path for signal in self.signal_list.signals()}
        if not all(axis in paths for axis in axes):
            return
        scan_id = entry.scan_id
        self._one_line[scan_id] = False  # until known: the heatmap stays on

        def done(data) -> None:
            self._one_line[scan_id] = points_on_one_line(data.x, data.y)
            if self._one_line[scan_id] and self._entry is not None:
                if self._entry.scan_id == scan_id:
                    self._refresh_plot()

        def failed(error: H5ReadError) -> None:
            if error.kind in ("cancelled", "busy"):
                # Another scan was picked meanwhile: look again when this one is back. A scan
                # that has just ended: look again soon, its file was written a moment ago.
                self._one_line.pop(scan_id, None)
                if error.kind == "busy":
                    self._reread_timer.start()
                return
            logger.debug(f"HDF5 viewer: the positions of {scan_id} were not read: {error.message}")

        x_path, y_path = paths[axes[0]], paths[axes[1]]
        self.service.request(
            f"viewer-{id(self)}-one-line",
            entry.file_path,
            # The DataAPI reads the curves of this file at the same moment.
            lambda ctx: h5_reader.read_map(
                entry.file_path, x_path, x_path, y_path, cancel=ctx.cancelled, like_data_api=True
            ),
            done,
            failed,
        )

    @SafeSlot(str)
    def _on_view_chosen(self, view: str) -> None:
        self._view_choice[self._view_kind()] = view
        self._refresh_plot()

    @SafeSlot()
    def _refresh_plot(self) -> None:
        """Bring the curves of the plot in line with the chosen scans and signals."""
        self._check_one_line()
        view = self.current_view()
        if self._entry is not None and self._entry.live:
            self._kept_view = (self._entry.scan_id, view)
        self.view_switch.setVisible(map_axes(self._entry) is not None)
        self.view_switch.set_off({"heatmap": self._heatmap_off()})
        self.view_switch.set_current(view)
        self.signal_list.set_map(view != "lines", self._view_kind())
        self._sync_file_from_signals()
        # The axes of the map are those of the signal list: the scan's devices unless the
        # user chose others.
        axes = self.signal_list.plane_axes() if view != "lines" else None
        self._map_shown = axes is not None
        self._map_wait_timer.stop()
        self._lines_wait_timer.stop()
        if axes is not None:
            self._show_map(view, axes)
            return
        scans = self._plot_scans()
        y_keys = self.signal_list.y_signals()
        x_key = self.signal_list.x_signal()
        one_scan = len(scans) <= 1
        wanted: dict[CurveKey, tuple[ScanEntry, str, str]] = {}
        colors = theme_colors()
        backs = (colors["bg"], colors["card"])
        for entry, slot in scans:
            # In a comparison the curves of a scan are shades of its colour, its own first.
            shades = None if one_scan else scan_shades(series_color(slot), backs)
            for position, (device, signal) in enumerate(y_keys):
                if signal not in (entry.stored_data_info or {}).get(device, {}):
                    continue
                color = (
                    series_color(position) if one_scan else shades[position % len(shades)].name()
                )
                style = "solid" if one_scan else PEN_STYLES[position % len(PEN_STYLES)]
                wanted[(entry.scan_id, device, signal)] = (entry, color, style)
        self._curve_styles = {key: (color, style) for key, (_entry, color, style) in wanted.items()}

        # The list shows each signal in the colour of its curve for the selected scan.
        self.signal_list.set_colors(
            self._curve_colors(y_keys, scans),
            series_color(0),
            (
                None
                if one_scan
                else {
                    key: PEN_STYLES[position % len(PEN_STYLES)]
                    for position, key in enumerate(y_keys)
                }
            ),
        )
        self._update_plot_title(scans)

        for key in list(self._curves):
            curve, live = self._curves[key]
            if key not in wanted or wanted[key][0].live != live:
                self._drop_curve(key)
        self._plot_note = ""
        self._plot_errors: dict[CurveKey, str] = {}
        self._apply_x(x_key)
        for key, (entry, color, style) in wanted.items():
            if key in self._curves:
                curve = self._curves[key][0]
                curve.set_color(color)
                curve.set_pen_style(style)
                continue
            # Errors come back here instead of as a popup: they are explained under the title.
            options = {
                "device_y": key[1],
                "signal_y": key[2],
                "color": color,
                "pen_style": style,
                "pen_width": 2,
                "_override_slot_params": {"popup_error": False, "raise_error": True},
            }
            if not entry.live:
                options["scan_id"] = entry.scan_id
            try:
                curve = self.waveform.plot(**options)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(f"HDF5 viewer: {key[1]}/{key[2]} could not be plotted: {exc}")
                self._plot_note = self._plot_problem(key[1], exc)
                self._plot_errors[key] = str(exc)
                continue
            if curve is None:
                self._plot_note = f"{key[1]} could not be plotted."
                continue
            self._curves[key] = (curve, entry.live)
        self._update_file_curves(scans, len(y_keys))
        self._tell_scan_list(scans, y_keys)

        if self._show_lines_page(scans):
            pass
        elif self._curves or self._file_curves:
            self.plot_stack.setCurrentWidget(self.waveform)
        elif self._plot_errors:
            # No curve could be made: the scan's data could not be read for it.
            self._show_read_failed(self._plot_errors, self._refresh_plot)
        elif self._entry is None:
            self.plot_state.show_state(
                "query_stats", "No scan picked", "Pick a scan on the left to plot its signals."
            )
            self.plot_stack.setCurrentWidget(self.plot_state)
        elif not self.signal_list.signals():
            self.plot_state.show_state(
                "data_alert",
                "No signals listed for this scan",
                "Its history entry does not say what was stored. "
                "The File tab shows everything that is in its file.",
                (("Go to the File tab", lambda: self.file_dock.setAsCurrentTab()),),
            )
            self.plot_stack.setCurrentWidget(self.plot_state)
        elif not self.signal_list.y_signals() and not self.signal_list.has_default():
            self.plot_state.show_state(
                "show_chart",
                "No default plot",
                "This scan stored no monitored signal besides its motors. "
                "Press Y on a signal to plot it.",
            )
            self.plot_stack.setCurrentWidget(self.plot_state)
        else:
            self.plot_state.show_state(
                "show_chart",
                "Nothing on the plot",
                self._plot_note or "Press Y on a signal to plot it, and X to choose the x axis.",
            )
            self.plot_stack.setCurrentWidget(self.plot_state)
        if self._plot_note:
            self.plot_subtitle.setText(self._plot_note)
        self._range_when_changed()
        self._empty_checks = 0
        self._empty_timer.start()
        self._update_read_note()

    def _range_when_changed(self) -> None:
        """Show every curve again, even after a zoom, once other curves or another x are shown."""
        drawn = frozenset(key for key, state in self._file_curves.items() if state.item is not None)
        shown = (frozenset(self._curves), drawn, self._wanted_x(self.signal_list.x_signal()))
        if shown != self._shown_state:
            self._shown_state = shown
            self.waveform.plot_item.enableAutoRange(x=True, y=True)

    def _show_map(self, view: str, axes) -> None:
        """Show the selected scan as a map of its two motors, coloured by one signal."""
        scans = self._plot_scans()
        self._update_plot_title(scans)
        for key in list(self._curves):
            self._drop_curve(key)
        # A curve has no place on a map: the datasets that are no signal wait for Lines.
        for key in list(self._file_curves):
            self._drop_file_curve(key)
        self.signal_list.set_dataset_chips(())
        self._shown_state = None
        self._empty_timer.stop()
        self._update_read_note()
        y_keys = self.signal_list.y_signals()
        self.signal_list.set_colors({}, series_color(0))
        self.scan_list.set_plot(
            {self._entry.scan_id} if self._entry is not None and y_keys else set(),
            {},
            {
                entry.scan_id: "Not on the plot: the map shows the selected scan only"
                for entry, _slot in scans[1:]
            },
        )
        if not y_keys:
            self.plot_state.show_state(
                "show_chart",
                "Nothing on the map",
                "Press Z on a monitored signal to colour the map by it.",
            )
            self.plot_stack.setCurrentWidget(self.plot_state)
            return
        try:
            plot = self.maps.show(view, self._entry, axes, y_keys[0])
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(f"HDF5 viewer: the map of {y_keys[0]} could not be drawn: {exc}")
            self.plot_state.show_state(
                "data_alert", "The map could not be drawn", f"{y_keys[0][0]}: {exc}"
            )
            self.plot_stack.setCurrentWidget(self.plot_state)
            return
        if self.maps.is_ready(view):
            self.plot_stack.setCurrentWidget(plot)
        elif not (self.maps.recoloured and self.plot_stack.currentWidget() is plot):
            # Never an empty plot with the axes of the scan before, nor its map. Another
            # colour of the same scan keeps the drawn map until the new one replaces it.
            self.plot_state.show_state(
                "hourglass_empty",
                "Loading the map",
                f"{y_keys[0][0]} over {axes[0][0]} and {axes[1][0]}",
            )
            self._show_plot_page(self.plot_state)
            self._map_wait_timer.start()
        if len(scans) > 1:
            self.plot_subtitle.setText(
                "the map shows this scan only  ·  the pinned scans are compared in Lines"
            )

    def _tell_scan_list(self, scans: list[tuple[ScanEntry, int]], y_keys) -> None:
        """
        Tell the scan list which scans have curves and in which colour, read from the curves,
        and why a pinned scan has none.
        """
        colors: dict[str, str] = {}
        for (scan_id, _device, _signal), (curve, _live) in self._curves.items():
            colors.setdefault(scan_id, curve.config.color)
        for (scan_id, _path), state in self._file_curves.items():
            if state.item is not None:
                colors.setdefault(scan_id, state.color)
        reasons = {}
        names = ", ".join(device for device, _signal in y_keys)
        for entry, _slot in scans[1:]:
            if entry.scan_id in colors:
                continue
            if not y_keys:
                reasons[entry.scan_id] = "Not on the plot: no signal is plotted"
            elif self._plot_note:
                reasons[entry.scan_id] = f"Not on the plot: {self._plot_note}"
            else:
                reasons[entry.scan_id] = f"Not on the plot: this scan did not store {names}"
        self.scan_list.set_plot(set(colors), colors, reasons)

    def _lines_loading(self) -> int:
        """How many curves of the plot still wait for the data of a finished scan."""
        waveform = self.waveform
        return sum(
            1
            for curve, live in self._curves.values()
            if not live and waveform.history_curve_waiting(curve.name())
        )

    def _lines_failed(self) -> dict[CurveKey, str]:
        """The curves of finished scans whose stored data could not be read, with the reason."""
        failed = {}
        for key, (curve, live) in self._curves.items():
            error = None if live else self.waveform.history_curve_error(curve.name())
            if error is not None:
                failed[key] = error
        return failed

    def _show_lines_page(self, scans) -> bool:
        """
        Show the loading page while no curve has its data, and the failure page once none
        can get it.

        Returns:
            bool: Whether one of the two pages shows.
        """
        count = len(self._curves)
        if self._file_curves_drawn():
            # Datasets of the file are drawn: the plot shows them while signals load or fail.
            return False
        waiting = self._lines_loading()
        failed = self._lines_failed()
        if count and waiting and waiting + len(failed) == count:
            # No curve has its data yet: not the empty axes of the scans before.
            self.plot_state.show_state(
                "hourglass_empty", "Loading the plot", self._loading_text(scans)
            )
            self._show_plot_page(self.plot_state)
            self._lines_wait_started = time.monotonic()
            self._lines_wait_timer.start()
            return True
        if count and len(failed) == count:
            self._show_read_failed(failed, self._read_lines_again)
            return True
        return False

    def _show_read_failed(self, failed: dict[CurveKey, str], retry: Callable[[], None]) -> None:
        """
        End the loading page once no curve can be drawn: say why and offer what helps.

        A scan without points and a dataset above the size limit are no failed reads: they
        are said as they are, the first without a way to read again.
        """
        self._lines_wait_timer.stop()
        reasons = set(failed.values())
        if reasons == {NO_DATA}:
            devices = dict.fromkeys(key[1] for key in failed)
            self.plot_state.show_state(
                "show_chart",
                "No points in this scan",
                f"The scan stored no values for {', '.join(devices)}.",
            )
        elif TOO_LARGE in reasons and reasons <= {NO_DATA, TOO_LARGE}:
            large = [key[1] for key, error in failed.items() if error == TOO_LARGE]
            self.plot_state.show_state(
                "file_download_off",
                "Not loaded",
                f"{', '.join(dict.fromkeys(large))} {'is' if len(large) == 1 else 'are'} "
                f"larger than the size limit of {self._size_limit_text()}.",
                (("Load it", self._load_large_lines),),
            )
        else:
            (_scan_id, device, _signal), error = next(
                (key, error) for key, error in failed.items() if error not in (NO_DATA, TOO_LARGE)
            )
            self.plot_state.show_state(
                "data_alert",
                "The plot could not be read",
                f"{read_sentence(error, device)}.",
                (("Try again", retry),),
                detail=error,
            )
        self.plot_stack.setCurrentWidget(self.plot_state)

    def _size_limit_text(self) -> str:
        """The Waveform's size limit, as the user set it."""
        return f"{self.waveform.max_dataset_size_mb:g} MB"

    def _load_large_lines(self) -> None:
        """Load the curves that were not loaded for their size, without asking again."""
        waveform = self.waveform
        large: dict[str, list[SourceKey]] = {}
        for (scan_id, device, signal), (curve, live) in self._curves.items():
            if not live and waveform.history_curve_error(curve.name()) == TOO_LARGE:
                large.setdefault(scan_id, []).append((device, signal))
        for scan_id, sources in large.items():
            waveform.load_history_sources(scan_id, sources)
        if not self._show_lines_page(self._plot_scans()) and self._curves:
            self.plot_stack.setCurrentWidget(self.waveform)
        self._update_read_note()

    def _read_lines_again(self) -> None:
        """Read the scans again whose curves failed or still wait; the others stay as they are."""
        waveform = self.waveform
        scans = {
            key[0]
            for key, (curve, live) in self._curves.items()
            if not live
            and (
                waveform.history_curve_error(curve.name()) is not None
                or waveform.history_curve_waiting(curve.name())
            )
        }
        for scan_id in scans:
            waveform.read_history_again(scan_id)
        if not self._show_lines_page(self._plot_scans()) and self._curves:
            self.plot_stack.setCurrentWidget(self.waveform)
        self._update_read_note()

    @SafeSlot(str)
    def _on_history_read_failed(self, _scan_id: str) -> None:
        """A read of the plot failed: end its loading page, or name the curves it lost."""
        if not self._map_shown and self.plot_stack.currentWidget() is self.plot_state:
            self._check_lines_loaded()
        self._update_read_note()

    def _update_read_note(self) -> None:
        """Name the curves that could not be read while others are drawn, with Try again."""
        failed = {} if self._map_shown else self._lines_failed()
        partial = bool(failed) and (len(failed) < len(self._curves) or self._file_curves_drawn())
        unread: dict[SourceKey, str] = {}
        for (scan_id, device, signal), error in failed.items():
            # A signal is shown as not plotted only when none of its curves could be read.
            others = [
                key
                for key in self._curves
                if key[1:] == (device, signal) and key not in failed and key[0] != scan_id
            ]
            if not others:
                unread[(device, signal)] = read_sentence(error, device)
        self.signal_list.set_unread(unread)
        self._update_tree_marks()
        self._update_owner_box()
        long_files = self._long_file_curves()
        self.read_note.setVisible(partial or bool(long_files))
        if not partial and not long_files:
            return
        # A failed read is said first, then a curve too large, then one without points.
        broken = {key: error for key, error in failed.items() if error not in (NO_DATA, TOO_LARGE)}
        large = [key[1] for key, error in failed.items() if error == TOO_LARGE]
        text, button, tooltip, error = "", "", "", ""
        if not partial:
            pass
        elif broken:
            (_scan_id, device, _signal), error = next(iter(broken.items()))
            names = ", ".join(dict.fromkeys(key[1] for key in broken))
            text = f"{names} could not be read. {read_sentence(error, device)}."
            button, tooltip = "Try again", "Read the scans of these curves again"
        elif large:
            names = ", ".join(dict.fromkeys(large))
            verb = "is" if len(set(large)) == 1 else "are"
            text = f"{names} {verb} larger than the size limit of {self._size_limit_text()}."
            button, tooltip = "Load it", "Load these curves without asking again"
            error = TOO_LARGE
        else:
            names = ", ".join(dict.fromkeys(key[1] for key in failed))
            verb = "has" if len({key[1] for key in failed}) == 1 else "have"
            text, button, tooltip, error = f"{names} {verb} no points in this scan.", "", "", ""
        self._read_note_path = ""
        if long_files and not broken:
            # Datasets of the file longer than the plot reads by itself: load them anyway,
            # or look at one in the preview, which is made for long data.
            limit = h5_reader.format_count(COPY_MAX_POINTS)
            labels = self._file_labels()
            names = ", ".join(labels[path] for path in long_files)
            if len(long_files) == 1:
                rows = h5_reader.format_count(next(iter(long_files.values())))
                said = f"{names} has {rows} rows, more than the {limit} the plot reads by itself."
            else:
                said = f"{names} have more rows than the {limit} the plot reads by itself."
            text = f"{text} {said}".strip()
            button, tooltip = "Load it", "Read these curves in full"
            # The selected scan's file is the one the File tab shows.
            scan_id = self._entry.scan_id if self._entry is not None else ""
            own = [
                path
                for path in long_files
                if (scan_id, path) in self._file_curves and self._file_curves[(scan_id, path)].large
            ]
            if len(own) == 1:
                self._read_note_path = own[0]
        self.read_note_open.setVisible(bool(self._read_note_path))
        self.read_note_icon.setPixmap(
            material_icon("data_alert" if broken else "info", size=(16, 16))
        )
        self.read_note_text.setText(text)
        self.read_note_text.setToolTip(error)
        self.read_note_button.setText(button)
        self.read_note_button.setToolTip(tooltip)
        self.read_note_button.setVisible(bool(button))

    def _act_on_read_note(self) -> None:
        """The note's button: load the curves too large, or read the failed ones again."""
        if self.read_note_button.text() == "Load it":
            self._load_large_lines()
            self._load_long_files()
        else:
            self._read_lines_again()

    # -- datasets of the file that are no signals -----------------------------------------

    def _file_x(self) -> FileX:
        """What the datasets that are no signals are read against: the x axis of the plot."""
        mode, entry = self._wanted_x(self.signal_list.x_signal())
        if mode == "timestamp":
            return ("time",)
        if mode in ("index", "auto"):
            # Without a positioner of the scans the plot counts the points.
            return ("index",)
        signal = next((s for s in self.signal_list.signals() if s.key == (mode, entry)), None)
        if signal is None:
            return ("dataset", "", mode)
        return ("dataset", signal.dataset_path, signal.label)

    def _update_file_curves(
        self, scans: list[tuple[ScanEntry, int]] | None = None, y_count: int | None = None
    ) -> None:
        """
        Bring the datasets that are no signals in line with the scans on the plot and its x
        axis: each is read from the file of each scan, after the signals in the colours.
        """
        if self._map_shown:
            return
        if scans is None:
            scans = self._plot_scans()
        if y_count is None:
            y_count = len(self.signal_list.y_signals())
        one_scan = len(scans) <= 1
        colors = theme_colors()
        backs = (colors["bg"], colors["card"])
        x = self._file_x()
        wanted: dict[tuple[str, str], tuple[ScanEntry, str, str]] = {}
        for entry, slot in scans:
            shades = None if one_scan else scan_shades(series_color(slot), backs)
            for offset, path in enumerate(self._file_paths):
                position = y_count + offset
                color = (
                    series_color(position) if one_scan else shades[position % len(shades)].name()
                )
                style = "solid" if one_scan else PEN_STYLES[position % len(PEN_STYLES)]
                wanted[(entry.scan_id, path)] = (entry, color, style)
        for key in list(self._file_curves):
            if key not in wanted:
                self._drop_file_curve(key)
        for key, (entry, color, style) in wanted.items():
            state = self._file_curves.setdefault(key, _FileCurve())
            state.color, state.style = color, style
            problem = ""
            job = None
            if entry.live:
                problem = RUNNING_FILE
            elif not entry.file_path:
                problem = "the scan has no file"
            else:
                job = (entry.file_path, key[1], x, key[1] in self._file_full)
            if job == state.job and (job is not None or problem == state.problem):
                continue
            # Another file or another x: never the values read for the one before.
            self.service.cancel(self._file_read_channel(key))
            self._remove_file_item(state)
            state.job, state.data, state.problem, state.large = job, None, problem, 0
            if job is not None:
                self._read_file_curve(key, state)
        self._draw_file_curves()

    def _file_read_channel(self, key: tuple[str, str]) -> str:
        return f"{self._file_channel}-{key[0]}-{key[1]}"

    def _read_file_curve(self, key: tuple[str, str], state: _FileCurve) -> None:
        """Read a dataset that is no signal off the GUI thread, for the job it has now."""
        job = state.job
        file_path, path, x, full = job

        def current() -> bool:
            return self._file_curves.get(key) is state and state.job == job

        def done(result) -> None:
            if not current():
                return
            if isinstance(result, CurveData):
                state.data = result
            elif isinstance(result, int):
                state.large = result
            else:
                state.problem = result
            self._draw_file_curves()

        def failed(error: H5ReadError) -> None:
            if not current():
                return
            state.problem = "not in this file" if error.kind == "missing" else error.message
            if error.kind == "busy":
                # Just written: read again shortly.
                state.job = None
                self._reread_timer.start()
            self._draw_file_curves()

        self.service.request(
            self._file_read_channel(key),
            file_path,
            lambda ctx: read_file_curve(
                file_path, path, x, full, cancel=ctx.cancelled, progress=ctx.progress
            ),
            done,
            failed,
        )

    def _remove_file_item(self, state: _FileCurve) -> None:
        """Take the curve of a dataset off the plot; the colours of the others stay."""
        item, label = state.item, state.label
        state.item, state.label = None, ""
        if item is None:
            return
        try:
            self.waveform.remove_curve(item.name())
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug(f"HDF5 viewer: the curve {label} was already gone: {exc}")
        self._restore_colors()

    def _drop_file_curve(self, key: tuple[str, str]) -> None:
        state = self._file_curves.pop(key)
        self.service.cancel(self._file_read_channel(key))
        self._remove_file_item(state)

    def _restore_colors(self) -> None:
        """
        Give every curve its colour back: the Waveform gives the curves the colours of its
        palette by count when one is taken off.
        """
        for key, (curve, _live) in self._curves.items():
            if key in self._curve_styles:
                curve.set_color(self._curve_styles[key][0])
        for state in self._file_curves.values():
            if state.item is not None:
                state.item.set_color(state.color)

    def _file_curves_drawn(self) -> bool:
        """Whether a dataset that is no signal is drawn on the plot."""
        return any(state.item is not None for state in self._file_curves.values())

    def _long_file_curves(self) -> dict[str, int]:
        """The datasets left unread for being longer than the plot reads, with their rows."""
        if self._map_shown:
            return {}
        return {
            path: state.large for (_id, path), state in self._file_curves.items() if state.large
        }

    def _file_labels(self) -> dict[str, str]:
        """
        Short names of the datasets that are no signals, as the preview names kept ones: with
        the group above where two would be equal, or equal to a signal on the plot.
        """
        names = {path: dataset_name(path) for path in self._file_paths}
        y = set(self.signal_list.y_signals())
        signals = {signal.label for signal in self.signal_list.signals() if signal.key in y}
        labels = {}
        for path, name in names.items():
            twins = [other for other in names if other != path and names[other] == name]
            labels[path] = dataset_name(path, with_parent=bool(twins) or name in signals)
        return labels

    def _file_curve_labels(self) -> dict[tuple[str, str], str]:
        """Names of the curves of the datasets on the plot, one per scan, none taken twice."""
        names = self._file_labels()
        model = self.scan_list.model
        labels: dict[tuple[str, str], str] = {}
        for scan_id, path in self._file_curves:
            entry = model.entry(scan_id)
            scan = model.scan_label(entry) if entry is not None else scan_id[:8]
            labels[(scan_id, path)] = f"{names[path]}-scan-{scan}"
        taken = list(labels.values())
        for key, label in labels.items():
            if taken.count(label) > 1:
                labels[key] = f"{label}-{key[0][:8]}"
        return labels

    def _draw_file_curves(self) -> None:
        """Draw the datasets that are read, each in its colour, and tell the chips and rows."""
        labels = self._file_curve_labels()
        added = False
        for key, state in self._file_curves.items():
            drawable = state.data is not None and not state.problem and not state.large
            if state.item is not None and (not drawable or state.label != labels[key]):
                self._remove_file_item(state)
            if not drawable:
                continue
            if state.item is not None:
                state.item.set_color(state.color)
                state.item.set_pen_style(state.style)
                continue
            try:
                item = self.waveform.plot(
                    x=np.asarray(state.data.x, dtype=float),
                    y=np.asarray(state.data.y),
                    label=labels[key],
                    color=state.color,
                    pen_style=state.style,
                    pen_width=2,
                    _override_slot_params={"popup_error": False, "raise_error": True},
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(f"HDF5 viewer: {key[1]} could not be drawn: {exc}")
                state.problem = f"it could not be drawn: {exc}"
                continue
            # Long data stays smooth: drawn reduced to the pixels, and only where it is seen.
            item.setDownsampling(auto=True, method="peak")
            item.setClipToView(True)
            state.item, state.label = item, labels[key]
            added = True
        self._update_file_chips()
        if self._map_shown:
            return
        if added:
            self._range_when_changed()
            if self.plot_stack.currentWidget() is self.plot_state and not self._lines_loading():
                self.plot_stack.setCurrentWidget(self.waveform)
            self._tell_scan_list(self._plot_scans(), self.signal_list.y_signals())
        self._update_read_note()

    def _file_problem(self, state: _FileCurve | None) -> str:
        if state is None:
            return ""
        if state.large:
            limit = h5_reader.format_count(COPY_MAX_POINTS)
            return (
                f"not read: {h5_reader.format_count(state.large)} rows, more than the {limit} "
                "the plot reads by itself"
            )
        return state.problem

    def _update_file_chips(self) -> None:
        """The chips of the datasets that are no signals, after the signals' in Y."""
        if self._map_shown:
            self.signal_list.set_dataset_chips(())
            return
        labels = self._file_labels()
        scans = self._plot_scans()
        label = self.scan_list.model.scan_label
        chips = []
        for path in self._file_paths:
            own = self._file_curves.get((scans[0][0].scan_id, path)) if scans else None
            tip = [path]
            if len(scans) > 1:
                drawn = [
                    label(entry)
                    for entry, _slot in scans
                    if (state := self._file_curves.get((entry.scan_id, path))) is not None
                    and state.item is not None
                ]
                if drawn:
                    tip.append(f"Drawn for scan{'s' if len(drawn) > 1 else ''} {', '.join(drawn)}")
                for entry, _slot in scans[1:]:
                    problem = self._file_problem(self._file_curves.get((entry.scan_id, path)))
                    if problem:
                        tip.append(f"Not drawn for scan {label(entry)}: {problem}")
            chips.append(
                ChipInfo(
                    DatasetKey(path),
                    labels[path],
                    removable=True,
                    swatch=Swatch(own.color, own.style) if own is not None else None,
                    tip="\n".join(tip),
                    problem=self._file_problem(own),
                )
            )
        self.signal_list.set_dataset_chips(chips)
        self._update_tree_marks()
        self._update_owner_box()

    def _update_owner_box(self) -> None:
        """Show in the File tab's box what the scan's plot shows, while the box is its."""
        if self._scan_owner() is not None:
            self.file_box.update_box()

    def _toggle_file_curve(self, path: str) -> None:
        """Y on a dataset of the scan's file that is no signal: one more curve, or one less."""
        if path in self._file_paths:
            self._file_paths.remove(path)
            self._file_full.discard(path)
        elif len(self._file_paths) >= KEPT_MAX:
            self.tree.show_note(
                f"{KEPT_MAX} datasets at most besides the signals: take one off first"
            )
            return
        else:
            self._file_paths.append(path)
        self._refresh_plot()
        self._back_to_plot()

    @SafeSlot(str)
    def _on_dataset_removed(self, path: str) -> None:
        """The x of a dataset's chip, in either tab."""
        if path in self._file_paths:
            self._toggle_file_curve(path)

    @SafeSlot()
    def _on_signals_reset(self) -> None:
        """Reset, in either tab: the datasets that are no signals go off the plot too."""
        if not self._file_paths:
            return
        self._file_paths.clear()
        self._file_full.clear()
        self._refresh_plot()

    def _load_long_files(self) -> None:
        """Read the datasets that are longer than the plot reads by itself all the same."""
        self._file_full |= set(self._long_file_curves())
        self._update_file_curves()

    def _open_large_in_file(self) -> None:
        """Show the long dataset of the read note in the File tab's preview."""
        path = self._read_note_path
        if not path:
            return
        self.file_dock.setAsCurrentTab()
        self._preview_path = path
        self.tree.pick_when_selected(path)
        self._show_file(path)

    def _file_y_state(self, node: H5Node) -> tuple[str, str]:
        """Whether a dataset of the scan's file is on its plot, for the list of the Y field."""
        key = self._signal_paths().get(node.path)
        if key is not None:
            return ("on", "on the plot") if key in self.signal_list.y_signals() else ("", "")
        if node.path in self._file_paths:
            return "on", "on the plot"
        if len(self._file_paths) >= KEPT_MAX:
            return "off", f"{KEPT_MAX} datasets at most"
        return "", ""

    def _loading_text(self, scans) -> str:
        labels = [self.scan_list.model.scan_label(entry) for entry, _slot in scans]
        return ("Scan " if len(labels) == 1 else "Scans ") + ", ".join(labels)

    def _check_lines_loaded(self) -> None:
        if self._map_shown or self.plot_stack.currentWidget() is not self.plot_state:
            self._lines_wait_timer.stop()
            return
        waiting = self._lines_loading()
        failed = self._lines_failed()
        if not self._curves or not waiting or waiting + len(failed) < len(self._curves):
            self._lines_wait_timer.stop()
            if self._curves and len(failed) == len(self._curves):
                self._show_read_failed(failed, self._read_lines_again)
            else:
                self._show_plot_page(self.waveform)
            self._update_read_note()
            return
        if (
            time.monotonic() - self._lines_wait_started > MAP_WAIT_MS / 1000
            and self.plot_state.title.text() != "Still loading the plot"
        ):
            self.plot_state.show_state(
                "hourglass_empty",
                "Still loading the plot",
                "The data of this scan has not arrived yet. It shows here as soon as it does.",
                (("Try again", self._read_lines_again),),
            )

    @SafeSlot(str)
    def _on_map_ready(self, view: str) -> None:
        """Show a map once its data is drawn, if it is still the one wanted."""
        if not self._map_shown or self.current_view() != view:
            return
        self._map_wait_timer.stop()
        if self.plot_stack.currentWidget() is self.plot_state:
            self._show_plot_page(self.maps.widget(view))

    def _on_map_slow(self) -> None:
        if self._map_shown and self.plot_stack.currentWidget() is self.plot_state:
            self.plot_state.show_state(
                "hourglass_empty",
                "Still loading the map",
                "The data of this scan has not arrived yet. It shows here as soon as it does.",
            )

    def _check_empty_curves(self) -> None:
        """Say which curves of the legend have nothing to draw, once their data is in."""
        waveform = self.waveform
        if any(
            waveform.history_curve_waiting(curve.name()) for curve, _live in self._curves.values()
        ):
            self._empty_checks += 1
            if self._empty_checks < EMPTY_CHECK_TRIES:
                self._empty_timer.start()
            return
        label = self.scan_list.model.scan_label
        axis = self.waveform.x_mode
        problems = []
        for (scan_id, device, signal), (curve, live) in self._curves.items():
            if live:
                continue
            entry = self.scan_list.model.entry(scan_id)
            name = f"{device} of scan {label(entry) if entry else '?'}"
            values = curve.yData
            error = self.waveform.history_curve_error(curve.name())
            if error == TOO_LARGE:
                problems.append(f"{name}: not loaded, above the size limit")
            elif error == NO_DATA:
                problems.append(f"{name}: no points")
            elif error is not None:
                problems.append(f"{name}: could not be read")
            elif not curve.isVisible():
                problems.append(f"{name}: the x axis {axis} does not fit it")
            elif values is None or len(values) == 0:
                problems.append(f"{name}: no points")
            elif not np.isfinite(np.asarray(values, dtype=float)).any():
                problems.append(f"{name}: no finite values")
        if problems:
            self.plot_subtitle.setText("Nothing to draw for " + "; ".join(problems))

    def _drop_curve(self, key: CurveKey) -> None:
        curve, _live = self._curves.pop(key)
        try:
            self.waveform.remove_curve(curve.name())
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug(f"HDF5 viewer: curve {key} was already gone: {exc}")

    def _wanted_x(self, x_key: SourceKey | None) -> tuple[str, str | None]:
        """
        The x mode of the plot for the X choice of the signal list: the chosen signal or x
        mode (Index, Timestamp), the sample number when only fast signals are on, else the
        positioner of the scans.
        """
        if x_key in X_MODES:
            return (x_key[1], None)
        if x_key is not None:
            return x_key
        y_keys = self.signal_list.y_signals()
        if y_keys and all(self.signal_list.group_of(key) == "fast" for key in y_keys):
            return ("index", None)
        positioner = self._positioner(self._plot_scans())
        return positioner if positioner is not None else ("auto", None)

    @staticmethod
    def _positioner(scans: list[tuple[ScanEntry, int]]) -> tuple[str, str] | None:
        """
        The first motor of the scans as (device, entry), when all of them moved it first and
        stored its readback; else None and the plot chooses.
        """
        if not scans:
            return None
        motors = {entry.motors[0] if entry.motors else "" for entry, _slot in scans}
        if len(motors) != 1:
            return None
        motor = motors.pop()
        if not motor:
            return None
        for entry, _slot in scans:
            if motor not in (entry.stored_data_info or {}).get(motor, {}):
                return None
        return (motor, motor)

    def _apply_x(self, x_key: SourceKey | None) -> None:
        """Give the plot the x axis the signal list says, checked against what it has now."""
        mode, entry = self._wanted_x(x_key)
        auto = x_key is None and entry is not None
        self.signal_list.set_auto_axis(
            f"{mode} (the scan's positioner)" if auto else "", (mode, entry) if auto else None
        )
        waveform = self.waveform
        try:
            if waveform.x_mode != mode:
                waveform.x_mode = mode
            if entry is not None and waveform.signal_x != entry:
                waveform.signal_x = entry
        except Exception as exc:  # pylint: disable=broad-except
            if x_key is None and mode != "auto":
                # The positioner cannot be the axis, e.g. a motor that left the session: the
                # plot chooses, and the list says so.
                logger.info(f"HDF5 viewer: {mode} cannot be the x axis, the plot chooses: {exc}")
                self.signal_list.set_auto_axis("")
                with contextlib.suppress(Exception):
                    waveform.x_mode = "auto"
                return
            logger.warning(f"HDF5 viewer: the x axis could not be set to {x_key}: {exc}")
            self._plot_note = f"{mode} cannot be the x axis here: {exc}"

    def _update_plot_title(self, scans: list[tuple[ScanEntry, int]]) -> None:
        if self._entry is None:
            self.plot_title.setText("")
            self.plot_subtitle.setText("")
            return
        self.plot_title.setText(
            f"Scan {self.scan_list.model.scan_label(self._entry)}  {self._entry.scan_name}".rstrip()
        )
        label = self.scan_list.model.scan_label
        others = [label(entry) for entry, _slot in scans[1:]]
        if others:
            self.plot_subtitle.set_facts(
                f"compared with {', '.join(others)}",
                "one colour per scan, a shade and a line style per signal",
            )
        elif self._entry.live:
            self.plot_subtitle.setText("running  ·  drawn live, its file is not opened")
        else:
            key = control_key_name()
            self.plot_subtitle.set_facts(
                self._entry.summary(), f"pin another scan or {key}-click it to compare"
            )

    ################################################################################
    # File view
    ################################################################################

    def _on_tab_changed(self, _index: int = -1) -> None:
        if self.file_tab_current():
            # Right after the switch the scan's plot stays, whatever row the tree has.
            self._picked_node = None
            self._preview_path = ""
            self._show_file()
            self._sync_file_from_signals()
        self._update_right_page()
        self._update_status()

    # -- one plot for both tabs ----------------------------------------------------------

    def _preview_wanted(self) -> bool:
        """
        Whether the plot pane shows the file's preview rather than the scan's plot.

        The tab in front does not decide it: for a scan, listed or imported, the pane shows its
        plot in both tabs. The File tab shows the preview of another file than the selected
        scan's, and, in the scan's file, of a dataset picked by hand in the tree that the
        scan's plot cannot draw (an image, a table, a text, a single value), or one asked for
        in the preview by name.
        """
        if not self.file_tab_current():
            return False
        if self._entry is not None and self._entry.live:
            # A running scan's file is not opened: its plot stays and the box says why.
            return False
        if not self._file_follows_scan():
            return True
        node = self.preview.node
        if node is None or node != self._picked_node or node.kind != "dataset":
            return False
        if node.path == self._preview_path:
            return True
        return node.path not in self._signal_paths() and not can_keep(node)

    def _update_right_page(self) -> None:
        """Show the scan's plot or the file's preview, as :meth:`_preview_wanted` says."""
        page = self.preview if self._preview_wanted() else self.plot_page
        changed = self.right_stack.currentWidget() is not page
        if changed:
            self._release_plot()
        if changed:
            self.right_stack.setCurrentWidget(page)
        self.back_button.setVisible(page is self.preview and self._file_follows_scan())
        # Out of sight the preview keeps its datasets in step without reading their values.
        self.preview.set_reading(page is self.preview)
        note = ""
        if self.file_tab_current() and self._entry is not None and self._entry.live:
            note = (
                f"Scan {self.scan_list.model.scan_label(self._entry)} is still running: its "
                "file opens here as soon as the scan is done."
            )
        self.file_box.set_viewer_note(note)
        self._update_tree_marks()
        if changed:
            self.file_box.update_box()
            self._update_status()

    def _scan_owner(self) -> SignalList | None:
        """
        The list whose fields the File tab shows while it shows the selected scan's file: the
        fields are then the Signals tab's, so that both tabs change the scan's plot alike, also
        while the preview covers it for a dataset the plot cannot draw.
        """
        return self.signal_list if self._file_follows_scan() else None

    def _on_tree_node(self, _node: H5Node | None) -> None:
        """A row selected in the tree, by hand or by the viewer."""
        self._update_right_page()

    def _on_tree_picked(self, node: H5Node) -> None:
        """A row picked by hand in the tree, also the one selected already."""
        self._picked_node = node
        if node.path != self._preview_path:
            self._preview_path = ""
        self._update_right_page()

    def _back_to_plot(self) -> None:
        """Show the scan's plot again where the preview covers it; the selection stays."""
        if self._picked_node is None and not self._preview_path:
            return
        self._picked_node = None
        self._preview_path = ""
        self._update_right_page()

    @SafeSlot()
    def _on_back_clicked(self) -> None:
        """ "Back to the plot" in the header of the preview."""
        self._back_to_plot()

    @SafeSlot()
    def _on_plot_choice(self) -> None:
        """X or Y changed the scan's plot, in either tab: it shows, not a preview over it."""
        self._back_to_plot()

    @SafeSlot(object)
    def _on_tree_keep(self, node: H5Node) -> None:
        """
        The Y button of a row, or a dataset taken in the File tab's Y field. In the selected
        scan's file Y changes the scan's plot: a signal as Y on its row in Signals (in a map
        the y axis), a dataset that is no signal as one more curve of Lines. In any other file
        the dataset is kept on the File tab's own plot.
        """
        if not self._file_follows_scan():
            self.preview.toggle_kept(node)
            return
        key = self._signal_paths().get(node.path)
        if key is not None:
            self.signal_list.press("Y", key)
            return
        if self.signal_list.role_kind("Y") == "curves":
            self._toggle_file_curve(node.path)

    def _update_tree_marks(self) -> None:
        """
        The filled Y buttons of the tree. In the selected scan's file: the curves of the
        scan's plot in their colours, or in a map the signal that is the y axis, as its row in
        Signals shows it; there the rows that are signals have Z buttons, and the others no Y.
        In any other file: the datasets kept on the File tab's own plot.
        """
        follows = self._file_follows_scan()
        signals = self.signal_list
        in_map = follows and signals.role_kind("Y") == "y"
        z_rows = self._map_z_rows() if in_map and "Z" in signals.row_letters() else {}
        self.tree.set_z_rows(z_rows)
        self.tree.set_y_rows(set(self._map_z_rows()) if in_map else None)
        if not follows:
            self.tree.set_kept(self.preview.kept_colors())
            return
        colors: dict[str, str] = {}
        signal_paths = self._signal_paths()
        if in_map:
            plane = signals.plane_axes()
            if plane is not None:
                for path, key in signal_paths.items():
                    if key == plane[1]:
                        colors[path] = ""
            self.tree.set_kept(colors)
            return
        paths = {key: path for path, key in signal_paths.items()}
        for key in signals.y_signals():
            if key in paths:
                unread = signals.unread_reason(key) is not None
                colors[paths[key]] = "" if unread else signals.signal_color(key)
        scan_id = self._entry.scan_id if self._entry is not None else ""
        for path in self._file_paths:
            state = self._file_curves.get((scan_id, path))
            colors[path] = state.color if state is not None and state.item is not None else ""
        self.tree.set_kept(colors)

    # -- one list of curves for Signals and File ---------------------------------------

    def _curve_colors(
        self, keys: list[SourceKey], scans: list[tuple[ScanEntry, int]]
    ) -> dict[SourceKey, str]:
        """
        The colour of each signal's curve for the selected scan: its own colour with one scan,
        in a comparison its shade of the scan's colour, the line style telling the scans apart.
        """
        if len(scans) <= 1:
            return {key: series_color(position) for position, key in enumerate(keys)}
        colors = theme_colors()
        shades = scan_shades(series_color(scans[0][1]), (colors["bg"], colors["card"]))
        return {key: shades[position % len(shades)].name() for position, key in enumerate(keys)}

    def _file_follows_scan(self) -> bool:
        """Whether the File tab is in front and shows the file of the selected scan."""
        entry = self._entry
        return (
            self.file_tab_current()
            and entry is not None
            and not entry.live
            and bool(entry.file_path)
            and self._file_shown == entry.file_path
        )

    def _signal_paths(self) -> dict[str, SourceKey]:
        """The dataset of each signal that can be a curve, by its path in the scan file."""
        return {
            signal.dataset_path: signal.key
            for signal in self.signal_list.signals()
            if signal.plottable
        }

    def _sync_file_from_signals(self) -> None:
        """
        Give the File tab what the scan's plot shows while it shows the scan's file: its x
        axis, and the Y buttons of the rows filled for the curves.
        """
        if not self._file_follows_scan():
            self.tree.set_x_rows({})
            self._update_tree_marks()
            return
        self._sync_x()
        self._update_tree_marks()
        self.file_box.update_box()

    def _x_owner(self) -> SignalList | None:
        """The list whose x axis the File tab shows and takes, while the two share it."""
        if self._file_follows_scan() and self.signal_list.role_kind("Y") == "curves":
            return self.signal_list
        return None

    def _map_z_rows(self) -> dict[str, ZButton]:
        """
        In a map, the Z buttons of the rows that are signals: filled with the colour of the map
        for the signals that colour it, outlined as a problem for one that could not be read.
        """
        signals = self.signal_list
        on = set(signals.y_signals())
        rows: dict[str, ZButton] = {}
        for signal in signals.signals():
            if not signal.plottable:
                continue
            button = ZButton()
            if signal.key in on:
                problem = signals.unread_reason(signal.key) or ""
                color = "" if problem else signals.swatch_of(signal.key).color
                button = ZButton(color=color, problem=problem)
            path = signal.dataset_path
            rows[path] = rows[path.rsplit("/", 1)[0]] = button
        return rows

    def _map_x_rows(self) -> dict[str, bool]:
        """In a map, the X buttons of the rows that are signals: on for the map's x axis."""
        plane = self.signal_list.plane_axes()
        rows: dict[str, bool] = {}
        for signal in self.signal_list.signals():
            if signal.group == "point" and signal.plottable:
                path = signal.dataset_path
                on = plane is not None and signal.key == plane[0]
                rows[path] = rows[path.rsplit("/", 1)[0]] = on
        return rows

    def _sync_x(self) -> None:
        """
        Plot the File tab against the x axis of Lines: auto, Index, Timestamp or a signal,
        whose dataset is then the x of every curve; and give the rows that are signals the X
        button of the Signals tab.
        """
        if self._x_owner() is None:
            in_map = self._file_follows_scan() and self.signal_list.role_kind("Y") == "y"
            self.tree.set_x_rows(self._map_x_rows() if in_map else {})
            return
        signals = {signal.key: signal for signal in self.signal_list.signals()}
        x = self.signal_list.x_signal()
        rows: dict[str, bool] = {}
        for signal in signals.values():
            if signal.group == "point":
                path = signal.dataset_path
                rows[path] = rows[path.rsplit("/", 1)[0]] = signal.key == x
        self.tree.set_x_rows(rows)
        preview = self.preview
        if x is None:
            if preview.x_choice not in (None, SCAN_AXES):
                preview.set_x(None)
        elif x == INDEX_X:
            preview.set_x("")
        elif x == TIMESTAMP_X:
            preview.set_x(TIME)
        elif x in signals:
            signal = signals[x]
            preview.set_x(signal.dataset_path, signal.label, signal.shape[0] if signal.shape else 0)

    @SafeSlot(str)
    def _on_tree_z(self, path: str) -> None:
        """The Z button of a row that is a signal of a map: as Z on that signal in Signals."""
        for signal in self.signal_list.signals():
            if path in (signal.dataset_path, signal.dataset_path.rsplit("/", 1)[0]):
                self.signal_list.press("Z", signal.key)
                return

    @SafeSlot(str)
    def _on_tree_x(self, path: str) -> None:
        """The X button of a row that is a signal: as X on that signal in Signals."""
        for signal in self.signal_list.signals():
            if path in (signal.dataset_path, signal.dataset_path.rsplit("/", 1)[0]):
                self.signal_list.toggle_x(signal.key)
                return

    def _plot_is_default(self) -> bool:
        """Whether Reset has nothing to do, for the File tab's box."""
        if not self._file_follows_scan():
            return self.file_box.own_default()
        return self.signal_list.box_is_default()

    def _reset_plot(self) -> None:
        """Reset in the File tab: the same as in Signals, the datasets that are no signal too."""
        if not self._file_follows_scan():
            self.file_box.own_reset()
            return
        self.signal_list.reset()

    def _choose_file(self) -> None:
        start = str(Path(self._file_path).parent) if self._file_path else ""
        suffixes = " ".join(f"*{suffix}" for suffix in h5_reader.HDF5_SUFFIXES)
        file_path, _filter = QFileDialog.getOpenFileName(
            self, "Open an HDF5 file", start, f"HDF5 files ({suffixes});;All files (*)"
        )
        if file_path:
            self.open_file(file_path)

    def _open_signal_in_file(self, signal: SignalInfo) -> None:
        self.file_dock.setAsCurrentTab()
        # Asked for by name: a dataset the scan's plot cannot draw, e.g. an image, opens in
        # the file's preview.
        self.tree.pick_when_selected(signal.dataset_path)
        self._show_file(signal.dataset_path)

    def _show_file(self, select_path: str = "") -> None:
        """Show the file of the selected scan, or the opened file, in the tree."""
        entry = self._entry
        self._busy_timer.stop()
        if entry is not None and entry.live:
            self._file_shown = ""
            self.tree.set_file(None)
            self.preview.show_message(
                "hourglass_top",
                f"Scan {self.scan_list.model.scan_label(entry)} is still running",
                "Its file is being written and is not opened. The Signals tab shows the scan "
                "while it runs, and the file opens here as soon as the scan is done.",
                (("Go to the Signals tab", lambda: self.signals_dock.setAsCurrentTab()),),
            )
            return
        file_path = self._file_path
        if not file_path:
            self._file_shown = ""
            self.tree.set_file(None)
            self.preview.show_message(
                "draft",
                "No file",
                "Pick a scan on the left, or open any HDF5 file.",
                (("Open file…", self._choose_file),),
            )
            return
        if file_path == self._file_shown:
            if select_path and self.tree.file_path == file_path:
                self.tree.select_path(select_path)
            elif select_path:
                # The file is being listed: select once it is there.
                self._select_when_listed = select_path
            return
        self._file_shown = file_path
        self._select_when_listed = select_path
        self.tree.set_file(None)
        self.preview.show_node(None)
        self._sync_file_from_signals()

        def listed(files: list[FileSummary]):
            if self._file_shown != file_path:
                return
            for summary in files:
                self._file_sizes[summary.file_path] = summary.size_bytes
            neighbours = tuple(summary.file_path for summary in files[1:])
            self.tree.set_file(file_path, neighbours, self._select_when_listed)
            # The selected scan's file has one plot, the scan's: the File tab's own kept
            # datasets wait for another file.
            entry = self._entry
            ours = entry is not None and not entry.live and entry.file_path == file_path
            self.preview.set_kept_file("" if ours else file_path)
            self._select_when_listed = ""
            self._update_status()

        def failed(error: H5ReadError):
            if self._file_shown == file_path:
                self._on_file_failed(error)

        self.service.request(
            f"viewer-{id(self)}-folder",
            "",
            lambda _ctx: h5_reader.scan_folder_files(file_path),
            listed,
            failed,
        )

    def _reopen_file(self) -> None:
        self._file_shown = ""
        if self.file_tab_current():
            self._show_file()

    def _on_file_failed(self, error: H5ReadError) -> None:
        """Explain in place why the file is not shown, and keep looking while it is written."""
        file_path = self._file_shown

        def read_anyway():
            self.service.allow_busy_file(file_path)
            self._reopen_file()

        self.preview.show_file_error(error, self._reopen_file, read_anyway, waiting=True)
        if error.kind == "busy":
            self._busy_timer.start()

    def _update_status(self) -> None:
        file_path = self._file_path
        node = self.preview.node
        if self.file_tab_current() and node is not None and node.file_path:
            # A link may have led into another file: tell about the file that is read.
            file_path = node.file_path
        if self._entry is not None and self._entry.live:
            # BEC's status of a running scan names no file: the bar stays empty.
            self.status_label.setText("")
            self.status_note.setText("")
            return
        self.status_label.setText(file_path or "")
        size = self._file_sizes.get(file_path) if file_path else None
        note = ""
        if size and self.file_tab_current():
            read = h5_reader.format_bytes(self.service.bytes_read(file_path))
            note = f"{read} of {h5_reader.format_bytes(size)} read"
        elif size:
            note = h5_reader.format_bytes(size)
        self.status_note.setText(f"·  {note}" if note else "")

    ################################################################################
    # Other plots
    ################################################################################

    def curve_sources(self) -> list[CurveSource]:
        """
        The curves on the plot that can go to another plot: those of finished scans.

        Returns:
            list[CurveSource]: (scan id, device, signal) of each.
        """
        return [key for key, (_curve, live) in self._curves.items() if not live]

    def _make_add_button(self, name: str, tool_tip: str) -> tuple[QToolButton, QMenu, QTimer]:
        """A button "Add to plot" with a menu of the other plots, and the timer of its text."""
        button = QToolButton(self)
        button.setObjectName(name)
        button.setText(ADD_BUTTON_TEXT)
        button.setIcon(material_icon("add_chart", convert_to_pixmap=False))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setAutoRaise(True)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolTip(tool_tip)
        menu = QMenu(button)
        button.setMenu(menu)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(ADD_FEEDBACK_MS)
        timer.timeout.connect(lambda: self._end_saying(button))
        return button, menu, timer

    def _fill_menu(
        self, menu: QMenu, header: str, offers: dict[str, Offer | str], say: Callable[[str], None]
    ) -> None:
        """
        Fill the menu of an "Add to plot" button: first what is sent, then the plots of each
        kind to open in the workspace, then the plots that are open, each with what happens.

        Args:
            menu (QMenu): The menu.
            header (str): What is sent, or why nothing can be.
            offers (dict[str, Offer | str]): Per kind of :data:`PLOT_KINDS`, what it gets, or
                why it gets nothing.
            say: Puts a message on the button.
        """
        menu.clear()
        menu.setToolTipsVisible(True)
        undo = self._live_undo()
        if undo is not None:
            menu.addAction(
                material_icon("undo", convert_to_pixmap=False), undo.text
            ).triggered.connect(lambda _=False: self._run_undo(say))
            menu.addSeparator()
        if not any(isinstance(offer, Offer) for offer in offers.values()):
            menu.addAction(header).setEnabled(False)
            return
        self._menu_caption(menu, header)
        area = dock_area_for(self)
        if area is not None:
            menu.addSeparator()
            self._menu_caption(menu, "New plot in the workspace")
            for kind, label in PLOT_KINDS.items():
                offer = offers[kind]
                # The text after a tab stands at the right of the entry.
                if isinstance(offer, str):
                    menu.addAction(f"{label}\t{offer}").setEnabled(False)
                    continue
                action = menu.addAction(f"{label}\t{offer.hint}")
                action.setToolTip(offer.describe)
                action.triggered.connect(
                    lambda _=False, k=kind, o=offer: self._send_to_new(area, k, o, say)
                )
        menu.addSeparator()
        self._menu_caption(menu, "Plots that are open")
        plots = open_plots(self)
        for name, plot, kind in plots:
            offer = offers[kind]
            if isinstance(offer, str):
                menu.addAction(f"{name}\t{offer}").setEnabled(False)
                continue
            action = menu.addAction(f"{name}\t{offer.effect(plot)}")
            action.setToolTip(offer.describe)
            action.triggered.connect(lambda _=False, o=offer, p=plot, n=name: o.send(p, n))
        if not plots:
            menu.addAction("No other plot is open").setEnabled(False)

    @staticmethod
    def _menu_caption(menu: QMenu, text: str) -> None:
        """A line of a menu that names what follows; it cannot be clicked."""
        action = menu.addAction(text)
        font = action.font()
        font.setWeight(QFont.Weight.DemiBold)
        action.setFont(font)
        action.setEnabled(False)

    def _send_to_new(self, dock_area, kind: str, offer: Offer, say):
        try:
            plot = dock_area.new(kind)
        except Exception as exc:  # pylint: disable=broad-except
            say(f"Could not open a new {PLOT_KINDS[kind]}: {exc}")
            return None
        if offer.prepare is not None:
            try:
                offer.prepare(plot)
            except Exception as exc:  # pylint: disable=broad-except
                logger.info(f"HDF5 viewer: the new {kind} keeps its own settings: {exc}")
        return offer.send(plot, plot_name(plot))

    def _add_sources(self, plot: Waveform, name: str | None, sources, say) -> AddResult:
        """Add history curves to another plot and say how it went on the button."""
        result = add_history_curves(plot, sources)
        say(result.message(name or plot_name(plot)), result.message())
        return result

    def _scan_text(self, scan_id: str) -> str:
        """A scan in words for a message: ``scan 20``, or ``the running scan``."""
        if not scan_id:
            return "the running scan"
        entry = self.scan_list.model.entry(scan_id)
        return f"scan {self.scan_list.model.scan_label(entry) if entry else scan_id[:8]}"

    def _curves_offer(
        self, sources: list[CurveSource], say, x: tuple[str, str | None] | None = None
    ) -> Offer:
        names = ", ".join(dict.fromkeys(signal_label(source[1:]) for source in sources))
        lines = "as a line" if len(sources) == 1 else "as lines"

        def prepare(plot: Waveform) -> None:
            # A new plot draws them against what the viewer does; an open one keeps its axis.
            if x is not None and x[0] != "auto":
                plot.x_mode = x[0]
                if x[1] is not None:
                    plot.signal_x = x[1]

        return Offer(
            prepare=prepare,
            describe=f"Adds {names} as history curves, saved with the workspace",
            hint=f"{names} {lines}",
            send=lambda plot, name: self._add_sources(plot, name, sources, say),
            effect=lambda plot: curves_effect(plot, sources),
        )

    def _file_copies(self) -> list[tuple[str, str, CurveData]]:
        """
        The datasets that are no signals as drawn on the plot: the name of a copy of each,
        its path and its values.
        """
        copies = []
        for (_scan_id, path), state in self._file_curves.items():
            if state.item is not None and state.data is not None and state.job is not None:
                copies.append((copy_label(state.job[0], path), path, state.data))
        return copies

    def _copies_names(self, copies: list[tuple[str, str, CurveData]]) -> str:
        labels = self._file_labels()
        return ", ".join(dict.fromkeys(labels.get(path, path) for _label, path, _data in copies))

    def _scan_items_offer(
        self,
        sources: list[CurveSource],
        copies: list[tuple[str, str, CurveData]],
        say,
        x: tuple[str, str | None] | None,
    ) -> Offer:
        """
        What "Add to plot" sends while datasets that are no signals are on the plot: the
        signals as history curves, the datasets as copies of the values drawn.
        """
        count = len(sources) + len(copies)
        what = f"{count} curve{'' if count == 1 else 's'}"

        def prepare(plot: Waveform) -> None:
            # A new plot draws them against what the viewer does; an open one keeps its axis.
            if x is not None and x[0] != "auto":
                plot.x_mode = x[0]
                if x[1] is not None:
                    plot.signal_x = x[1]

        def send(plot: Waveform, name: str) -> AddResult:
            result = add_history_curves(plot, sources) if sources else AddResult()
            copied = False
            for label, _path, data in copies:
                if has_curve(plot, label):
                    result.already += 1
                    continue
                try:
                    plot.plot(
                        x=np.asarray(data.x, dtype=float),
                        y=np.asarray(data.y),
                        label=label,
                        _override_slot_params={"popup_error": False, "raise_error": True},
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    result.errors.append(f"{label}: {exc}")
                else:
                    result.added += 1
                    copied = True
            text = result.message(name or plot_name(plot))
            if copied:
                text += ", copies not saved with the workspace"
            say(text, result.message())
            return result

        describe = f"Adds {what}: the signals as history curves, saved with the workspace"
        describe += "; the datasets as copies, which are not"
        return Offer(
            prepare=prepare,
            describe=(
                describe
                if sources
                else "Adds copies of the datasets, not saved with the " "workspace"
            ),
            hint=what,
            send=send,
            effect=lambda _plot: f"adds {what}",
        )

    def _map_offer(self, source: MapSource, say, shown: bool) -> Offer:
        return Offer(
            describe=f"Shows {source.over()} of {self._scan_text(source.scan_id)}, "
            "saved with the workspace",
            hint="this map" if shown else source.over(),
            send=lambda plot, name: self._send_map(plot, name, source, say),
            effect=lambda plot: (
                "shows it already" if shown_map(plot) == source else "replaces what it shows"
            ),
        )

    def _send_map(self, plot, name: str, source: MapSource, say) -> bool:
        """Let a Heatmap or a ScatterWaveform show a scan's signal; say what it shows now."""
        before = shown_map(plot)
        if before == source:
            say(f"{name} shows it already")
            return False
        try:
            show_map(plot, source)
        except Exception as exc:  # pylint: disable=broad-except
            say(f"Could not show it on {name}: {exc}")
            return False
        scan = self._scan_text(source.scan_id)
        text = f"{name} now shows {signal_label(source.z)} of {scan}"
        short = f"{name} now shows {scan}"
        if before is not None:
            scan_before = self._scan_text(before.scan_id)
            self._undo = Undo(
                plot,
                f"Undo: {name} back to {signal_label(before.z)} of {scan_before}",
                lambda: show_map(plot, before),
                done=f"{name} shows {signal_label(before.z)} of {scan_before} again",
                done_short=f"{name} shows {scan_before} again",
            )
            text += UNDO_SUFFIX
            short += UNDO_SUFFIX
        say(text, short)
        return True

    def _live_undo(self) -> Undo | None:
        """The undo of the last replace, while its plot is still open."""
        undo = self._undo
        if undo is None:
            return None
        if not isValid(undo.plot) or getattr(undo.plot, "_destroyed", False):
            self._undo = None
            return None
        return undo

    def _run_undo(self, say) -> None:
        undo, self._undo = self._live_undo(), None
        if undo is None:
            return
        try:
            undo.restore()
        except Exception as exc:  # pylint: disable=broad-except
            say(f"Could not undo: {exc}")
            return
        say(undo.done, undo.done_short)

    def signal_offers(self) -> tuple[str, dict[str, Offer | str]]:
        """
        What the Signals side sends to other plots: what the plot shows, as lines to a
        Waveform and as a map of the scan's two motors to a Heatmap or a ScatterWaveform.

        Returns:
            tuple[str, dict[str, Offer | str]]: What is sent, in words, and per kind of
            :data:`PLOT_KINDS` the offer or why there is none.
        """
        say = self._say_on_add_button
        offers: dict[str, Offer | str] = {"Image": "needs a 2D dataset"}
        map_source = self._signal_map_source()
        for kind in ("Heatmap", "ScatterWaveform"):
            offers[kind] = (
                self._map_offer(map_source, say, shown=self._map_shown)
                if isinstance(map_source, MapSource)
                else map_source
            )
        if isinstance(map_source, MapSource) and self._heatmap_off():
            offers["Heatmap"] = self._heatmap_off()
        copies: list[tuple[str, str, CurveData]] = []
        if self._map_shown:
            sources = (
                [(map_source.scan_id, *map_source.z)] if isinstance(map_source, MapSource) else []
            )
        else:
            sources = self.curve_sources()
            copies = self._file_copies()
        x = self._wanted_x(self.signal_list.x_signal())
        if copies:
            offers["Waveform"] = self._scan_items_offer(sources, copies, say, x)
        elif sources:
            offers["Waveform"] = self._curves_offer(sources, say, x=x)
        else:
            offers["Waveform"] = "the plot is empty or shows a running scan"
        if self._map_shown and isinstance(map_source, MapSource):
            view = "Heatmap" if self.current_view() == "heatmap" else "Scatter"
            header = f"{view} of {map_source.over()} · {self._scan_text(map_source.scan_id)}"
        elif sources:
            names = ", ".join(dict.fromkeys(signal_label(source[1:]) for source in sources))
            labels = [self._scan_text(scan_id) for scan_id in dict.fromkeys(s[0] for s in sources)]
            scans = (
                labels[0]
                if len(labels) == 1
                else "scans " + ", ".join(label.removeprefix("scan ") for label in labels)
            )
            if copies:
                names += ", " + self._copies_names(copies)
            header = f"Lines of {names} · {scans}"
        elif copies:
            header = f"Lines of {self._copies_names(copies)}"
        else:
            header = "Nothing to add: the plot is empty or shows a running scan"
        return header, offers

    def _signal_map_source(self) -> MapSource | str:
        """The map of the picked scan to send, or why there is none."""
        entry = self._entry
        if entry is None:
            return "pick a scan first"
        axes = self.signal_list.plane_axes()
        if axes is None:
            return "needs a scan of two motors"
        if entry.live:
            return "the scan is still running"
        colour = [key for key in self.signal_list.y_signals() if key not in axes]
        if not colour:
            return "needs a signal for its colour"
        return MapSource(entry.scan_id, axes[0], axes[1], colour[0])

    def _fill_add_menu(self) -> None:
        header, offers = self.signal_offers()
        self._fill_menu(self.add_menu, header, offers, self._say_on_add_button)

    def add_to_plot(self, plot: QWidget, name: str | None = None) -> object:
        """
        Send what the plot of the viewer shows to another plot: lines to a Waveform as history
        curves, the map of the picked scan to a Heatmap or a ScatterWaveform.

        Args:
            plot (QWidget): The other plot.
            name (str | None): Its name, as shown on the button afterwards.

        Returns:
            object: An :class:`AddResult` for a Waveform, else whether the plot took it.
        """
        return self._send(plot, name, self.signal_offers()[1], self._say_on_add_button)

    def add_to_new_plot(self, dock_area, kind: str = "Waveform") -> object:
        """
        Open a new plot in a dock area and send what the plot of the viewer shows to it.

        Args:
            dock_area (BECDockArea): The dock area.
            kind (str): A key of :data:`PLOT_KINDS`.

        Returns:
            object: What the plot's send returned, or None when nothing could be sent.
        """
        offer = self.signal_offers()[1].get(kind)
        if not isinstance(offer, Offer):
            self._say_on_add_button(f"Nothing to send to a {PLOT_KINDS.get(kind, kind)}: {offer}")
            return None
        return self._send_to_new(dock_area, kind, offer, self._say_on_add_button)

    @staticmethod
    def _send(plot: QWidget, name: str | None, offers, say) -> object:
        name = name or plot_name(plot)
        kind = plot_kind(plot)
        offer = offers.get(kind) if kind else "it is no plot the viewer sends to"
        if not isinstance(offer, Offer):
            say(f"Nothing to send to {name}: {offer}")
            return None
        return offer.send(plot, name)

    @staticmethod
    def _say_on(button: QToolButton, timer: QTimer, text: str, width: int, short: str = "") -> None:
        """
        Put a message on an "Add to plot" button for a few seconds, in the ``width`` pixels the
        button may take without widening its pane. The longest text that fits is shown: the
        message, else its ``short`` form, else the message cut. Whatever is not the message
        itself leaves the message in full in the tooltip meanwhile.
        """
        metrics = button.fontMetrics()
        shown = text
        if metrics.horizontalAdvance(text) > width:
            if short and metrics.horizontalAdvance(short) <= width:
                shown = short
            else:
                # The way back stays in sight when the message is cut: it is in the menu.
                tail = UNDO_SUFFIX if text.endswith(UNDO_SUFFIX) else ""
                head = text[: len(text) - len(tail)]
                shown = metrics.elidedText(
                    head, Qt.TextElideMode.ElideRight, width - metrics.horizontalAdvance(tail)
                )
                shown += tail
        button.setText(shown)
        button.setProperty("feedback", text)
        if shown != text:
            if not button.property("tool_tip_before"):
                button.setProperty("tool_tip_before", button.toolTip())
            button.setToolTip(text)
        timer.start()

    @staticmethod
    def _text_room(button: QToolButton, row_width: int, others: list[QWidget]) -> int:
        """
        Pixels a message on ``button`` may take in a row ``row_width`` wide that it shares with
        ``others``: never less than the button's own text. A button not on screen has no row to
        share yet and gets the room it asks for.
        """
        metrics = button.fontMetrics()
        if not button.isVisible():
            return HIDDEN_BUTTON_ROOM
        taken = sum(widget.width() + 8 for widget in others if widget.isVisible())
        chrome = button.sizeHint().width() - metrics.horizontalAdvance(button.text())
        return max(metrics.horizontalAdvance(ADD_BUTTON_TEXT), row_width - taken - chrome)

    @staticmethod
    def _end_saying(button: QToolButton) -> None:
        button.setText(ADD_BUTTON_TEXT)
        button.setProperty("feedback", "")
        before = button.property("tool_tip_before")
        if before:
            button.setToolTip(before)
            button.setProperty("tool_tip_before", "")

    def _say_on_add_button(self, text: str, short: str = "") -> None:
        # The subtitle beside it gives way, down to its least width.
        others = [self.plot_title, self.view_switch]
        row = self.plot_page.width() - self.plot_subtitle.minimumWidth() - 8
        room = self._text_room(self.add_button, row, others)
        self._say_on(self.add_button, self._add_reset_timer, text, room, short)

    ################################################################################
    # The dataset of the File tab on other plots
    ################################################################################

    def file_history_source(self) -> CurveSource | None:
        """
        The history curve of the dataset the File tab shows as a line or a map, if it is one:
        the ``value`` of a BEC signal, 1D, in the file of a listed scan that stored that signal.

        Returns:
            CurveSource | None: (scan id, device, signal), or None for any other dataset.
        """
        if self.preview.view not in ("line", "map"):
            return None
        return self._history_of(self.preview.node)

    def _history_of(self, node: H5Node | None) -> CurveSource | None:
        """The history curve of a 1D dataset of a listed scan's file, if it is one."""
        if node is None or node.kind != "dataset" or node.ndim != 1:
            return None
        signal = signal_of_dataset(node.path)
        if signal is None:
            return None
        entry = self._scan_of_file(node.file_path)
        if entry is None or signal[1] not in (entry.stored_data_info or {}).get(signal[0], {}):
            return None
        return (entry.scan_id, *signal)

    def _scan_of_file(self, file_path: str) -> ScanEntry | None:
        """The listed scan whose file this is, matched by path, newest first."""
        wanted = Path(file_path).resolve()
        for entry in self.scan_list.model.entries():
            if entry.file_path and Path(entry.file_path).resolve() == wanted:
                return entry
        return None

    def _update_file_add_button(self) -> None:
        view = self.preview.view if self.preview.node is not None else ""
        button = self.file_add_button
        button.setVisible(view in ("line", "map", "image"))
        button.setEnabled(not self._copying)
        source = self.file_history_source()
        if source is not None:
            button.setToolTip(
                f"Adds {signal_label(source[1:])} of {self._scan_text(source[0])} to another plot"
            )
        elif view == "map":
            button.setToolTip("Shows this map on another plot")
        else:
            button.setToolTip(COPY_TOOLTIP)

    def file_map_source(self) -> MapSource | str:
        """
        The map of the dataset the File tab shows, as the stored scan's signal over its two
        motors, or why it has none.

        Returns:
            MapSource | str: The map, or why it cannot go to a Heatmap or a ScatterWaveform.
        """
        preview = self.preview
        node, axes = preview.node, preview.scan_axes
        if node is None or axes is None or not preview.map_fits():
            return "needs a signal of a scan of two motors"
        signal = signal_of_dataset(node.path)
        keys = [signal_of_dataset(axis.target or axis.path) for axis in axes.axes]
        entry = self._scan_of_file(node.file_path)
        if entry is None or signal is None or None in keys:
            return "only for scans in the list"
        if entry.live:
            return "the scan is still running"
        stored = entry.stored_data_info or {}
        missing = [key for key in (*keys, signal) if key[1] not in stored.get(key[0], {})]
        if missing:
            return f"the scan's history did not store {signal_label(missing[0])}"
        return MapSource(entry.scan_id, keys[0], keys[1], signal)

    def file_offers(self) -> tuple[str, dict[str, Offer | str]]:
        """
        What the File tab sends to other plots: a line to a Waveform, a map to a Heatmap or a
        ScatterWaveform, a frame to an Image. Signals of listed scans go backed by the scan
        history; anything else as a copy.

        Returns:
            tuple[str, dict[str, Offer | str]]: What is sent, in words, and per kind of
            :data:`PLOT_KINDS` the offer or why there is none.
        """
        say = self._say_on_file_button
        preview = self.preview
        node, view = preview.node, preview.view
        offers: dict[str, Offer | str] = {}
        header = "Show the dataset as a line, map or image first"
        map_source = self.file_map_source()
        for kind in ("Heatmap", "ScatterWaveform"):
            offers[kind] = (
                self._map_offer(map_source, say, shown=preview.view == "map")
                if isinstance(map_source, MapSource)
                else map_source
            )
        history = self.file_history_source()
        line = preview.line_source()
        if history is not None:
            entry = self.scan_list.model.entry(history[0])
            x = self._positioner([(entry, 0)]) if entry is not None else None
            offers["Waveform"] = self._curves_offer([history], say, x=x)
            header = f"Line of {signal_label(history[1:])} · {self._scan_text(history[0])}"
        elif line is not None:
            rows = int(line.node.shape[-1]) if line.node.shape else 1
            if rows > COPY_MAX_POINTS:
                offers["Waveform"] = f"too many rows to copy: {rows:,}"
            else:
                label = copy_label(line.node.file_path, line.node.path, line.index)
                offers["Waveform"] = Offer(
                    describe=COPY_TOOLTIP,
                    hint="a copy of this line",
                    send=lambda plot, name: self._copy_to_plot(plot, name),
                    effect=lambda plot, label=label: (
                        "has it already" if has_curve(plot, label) else "adds a copy"
                    ),
                )
                header = f"Copy of {label}"
        else:
            offers["Waveform"] = "needs a line"
        frame = preview.shown_frame()
        if frame is not None:
            data, index = frame
            label = copy_label(node.file_path, node.path, index)
            offers["Image"] = Offer(
                describe="Shows a copy of this frame. A copy is not saved with the workspace.",
                hint="a copy of this frame",
                send=lambda plot, name: self._send_frame(plot, name, data.data, label),
                effect=lambda _plot: "replaces what it shows",
            )
            header = f"Copy of {label}"
            if data.stride > 1:
                header += f" (every {data.stride}. pixel, as shown)"
        else:
            offers["Image"] = "needs a 2D dataset"
        kept = preview.kept_lines() if view == "line" else []
        if kept:
            items = [self._main_item(history, line), *map(self._kept_item, kept)]
            offers["Waveform"] = self._many_offer(items, history)
            names = ", ".join(item.label for item in items)
            header = f"{len(items)} curves: {names}"
        if view == "map" and isinstance(map_source, MapSource):
            kind = "Heatmap" if preview.map_kind() == "heatmap" else "Scatter"
            header = f"{kind} of {map_source.over()} · {self._scan_text(map_source.scan_id)}"
        elif view == "map" and history is None:
            header = f"Nothing to add: {map_source}"
        return header, offers

    def _main_item(self, history: CurveSource | None, line) -> _SendItem:
        """The selected dataset as the first of the curves sent with the kept ones."""
        label = self.preview.signal_name()
        if history is not None:
            return _SendItem(label, history=history)
        if line is None:
            return _SendItem(label, problem="no line is shown")
        return self._copy_item(label, line.node, line.index, line.x_path or None, False)

    def _kept_item(self, kept: KeptLine) -> _SendItem:
        """A kept dataset the preview draws, as one of the curves sent."""
        history = self._history_of(kept.node)
        if history is not None:
            return _SendItem(kept.label, history=history)
        return self._copy_item(kept.label, kept.node, (), kept.x_path, kept.relative)

    @staticmethod
    def _copy_item(label, node: H5Node, index, x_path, relative) -> _SendItem:
        rows = int(node.shape[-1]) if node.shape else 1
        if rows > COPY_MAX_POINTS:
            return _SendItem(label, problem=f"too many rows to copy: {rows:,}")
        return _SendItem(label, node=node, index=index, x_path=x_path, relative=relative)

    def _many_offer(self, items: list[_SendItem], history: CurveSource | None) -> Offer:
        """What "Add to plot" sends while datasets are kept: every curve the preview draws."""
        count = f"{len(items)} curves"
        x = None
        if history is not None:
            entry = self.scan_list.model.entry(history[0])
            x = self._positioner([(entry, 0)]) if entry is not None else None

        def prepare(plot: Waveform) -> None:
            if x is not None and x[0] != "auto":
                plot.x_mode = x[0]
                if x[1] is not None:
                    plot.signal_x = x[1]

        copies = any(item.node is not None for item in items)
        describe = f"Adds {count}: the selected dataset and the kept ones"
        if copies:
            describe += ". Copies are not saved with the workspace."
        return Offer(
            prepare=prepare,
            describe=describe,
            hint=count,
            send=lambda plot, name: self._send_items(plot, name, items),
            effect=lambda _plot: f"adds {count}",
        )

    def _send_items(self, plot: Waveform, name: str, items: list[_SendItem]) -> AddResult:
        """
        Add curves to a plot one after the other, in their order: history curves at once,
        copies once they are read. What cannot be added is named on the button with why.
        """
        result = AddResult()
        left_out: list[str] = []
        copied = [False]

        def finish() -> None:
            self._copy_finished()
            text = result.message(name)
            short = result.message()
            if left_out:
                text = (
                    f"{text}; left out {'; '.join(left_out)}"
                    if result.added
                    else (f"Could not add to {name}: {'; '.join(left_out)}")
                )
            if copied[0]:
                text += ", copies not saved with the workspace"
            say(text, short)

        def failed_one(item: _SendItem, why: str) -> None:
            left_out.append(f"{item.label} ({why})")
            result.errors.append(f"{item.label}: {why}")

        def step(position: int) -> None:
            if position == len(items):
                finish()
                return
            item = items[position]
            if item.problem:
                failed_one(item, item.problem)
            elif item.history is not None:
                one = add_history_curves(plot, [item.history])
                result.added += one.added
                result.already += one.already
                for error in one.errors:
                    failed_one(item, error)
            else:
                read_copy(position, item)
                return
            step(position + 1)

        def read_copy(position: int, item: _SendItem) -> None:
            node = item.node
            label = copy_label(node.file_path, node.path, item.index)
            if has_curve(plot, label):
                result.already += 1
                step(position + 1)
                return
            rows = int(node.shape[-1]) if node.shape else 1

            def done(curve_data):
                try:
                    plot.plot(
                        x=np.asarray(curve_data.x),
                        y=np.asarray(curve_data.y),
                        label=label,
                        _override_slot_params={"popup_error": False, "raise_error": True},
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    failed_one(item, str(exc))
                else:
                    result.added += 1
                    copied[0] = True
                step(position + 1)

            def failed(error: H5ReadError):
                failed_one(item, error.message)
                step(position + 1)

            self.service.request(
                self._copy_channel,
                node.file_path,
                lambda ctx: h5_reader.read_curve(
                    node.file_path,
                    node.path,
                    item.index,
                    max_points=max(rows, 1),
                    cancel=ctx.cancelled,
                    x_path=item.x_path,
                    relative_x=item.relative,
                ),
                done,
                failed,
            )

        say = self._say_on_file_button
        self._copying = True
        self.file_add_button.setEnabled(False)
        self.file_add_button.setText("Reading…")
        self.file_add_button.setProperty("feedback", "Reading…")
        step(0)
        return result

    def _send_frame(self, plot, name: str, data, label: str) -> bool:
        try:
            restore = show_image_copy(plot, data, label)
        except Exception as exc:  # pylint: disable=broad-except
            self._say_on_file_button(f"Could not show it on {name}: {exc}")
            return False
        self._undo = Undo(
            plot,
            f"Undo: {name} back to what it showed",
            restore,
            done=f"{name} shows again what it showed before",
            done_short=f"{name} is back",
        )
        self._say_on_file_button(
            f"{name} now shows a copy, not saved with the workspace{UNDO_SUFFIX}",
            f"{name} now shows a copy{UNDO_SUFFIX}",
        )
        return True

    def _fill_file_add_menu(self) -> None:
        header, offers = self.file_offers()
        self._fill_menu(self.file_add_menu, header, offers, self._say_on_file_button)

    def add_file_to_plot(self, plot: QWidget, name: str | None = None) -> object:
        """
        Send what the File tab shows to another plot: a BEC signal of a listed scan backed by
        the scan history (as from the Signals tab), anything else as a copy of the values
        shown.

        Args:
            plot (QWidget): The other plot.
            name (str | None): Its name, as shown on the button afterwards.

        Returns:
            object: An :class:`AddResult` for a history curve; None while a copy is read.
        """
        return self._send(plot, name, self.file_offers()[1], self._say_on_file_button)

    def _copy_to_plot(self, plot: Waveform, name: str) -> None:
        line = self.preview.line_source()
        if line is None:
            return
        node = line.node
        label = copy_label(node.file_path, node.path, line.index)
        if has_curve(plot, label):
            self._say_on_file_button(f"Already on {name}")
            return
        rows = int(node.shape[-1]) if node.shape else 1
        if rows > COPY_MAX_POINTS:
            self._say_on_file_button(f"Too many rows to copy to {name}")
            return
        self._copying = True
        self.file_add_button.setEnabled(False)
        self.file_add_button.setText("Reading…")
        self.file_add_button.setProperty("feedback", "Reading…")
        x_path = line.x_path or None

        def done(curve_data):
            self._copy_finished()
            try:
                plot.plot(
                    x=np.asarray(curve_data.x),
                    y=np.asarray(curve_data.y),
                    label=label,
                    _override_slot_params={"popup_error": False, "raise_error": True},
                )
            except Exception as exc:  # pylint: disable=broad-except
                self._say_on_file_button(f"Could not add to {name}: {exc}")
                return
            self._say_on_file_button(
                f"Copied to {name}, not saved with the workspace", "Copied, not saved"
            )

        def failed(error: H5ReadError):
            self._copy_finished()
            self._say_on_file_button(f"Could not copy: {error.message}")

        self.service.request(
            self._copy_channel,
            node.file_path,
            lambda ctx: h5_reader.read_curve(
                node.file_path,
                node.path,
                line.index,
                max_points=max(rows, 1),
                cancel=ctx.cancelled,
                x_path=x_path,
            ),
            done,
            failed,
        )

    def _copy_finished(self) -> None:
        self._copying = False
        self._update_file_add_button()

    def _say_on_file_button(self, text: str, short: str = "") -> None:
        # The header of the preview is narrow: use only the room the other parts leave.
        others = [self.preview.name_label, *self.preview.view_buttons.values()]
        room = self._text_room(self.file_add_button, self.preview.width(), others)
        self._say_on(self.file_add_button, self._file_add_reset_timer, text, room, short)

    def _show_scan_menu(self, entry: ScanEntry, position) -> None:
        self.scan_menu(entry).popup(position)

    def scan_menu(self, entry: ScanEntry) -> QMenu:
        """
        The context menu of a scan: overlay it on another plot.

        Args:
            entry (ScanEntry): The scan.

        Returns:
            QMenu: The menu, not shown yet.
        """
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        overlay = QMenu("Overlay on", menu)
        menu.addMenu(overlay)
        menu.overlay_menu = overlay
        plots = other_plots(self)
        if entry.live:
            overlay.setEnabled(False)
            overlay.setToolTip("A running scan can be overlaid once it is done")
        for name, plot in plots:
            action = overlay.addAction(name)
            action.triggered.connect(
                lambda _=False, e=entry, p=plot, n=name: self.overlay_scan(e, p, n)
            )
        if not plots:
            note = overlay.addAction("No other plot is open")
            note.setEnabled(False)
        if entry.imported:
            remove = menu.addAction("Remove from the list")
            remove.setToolTip("Take the scan off the list; its file stays as it is")
            remove.triggered.connect(lambda _=False, e=entry: self.remove_imported(e))
            menu.remove_action = remove
        return menu

    def overlay_scan(self, entry: ScanEntry, plot: Waveform, name: str | None = None) -> str:
        """
        Add a scan to another plot with the signals that plot shows, as history curves.

        Args:
            entry (ScanEntry): The scan.
            plot (Waveform): The other plot.
            name (str | None): Its name.

        Returns:
            str: What happened, as said in the note under the scan list.
        """
        name = name or plot_name(plot)
        signals = shown_signals(plot)
        stored = entry.stored_data_info or {}
        sources = [
            (entry.scan_id, device, signal)
            for device, signal in signals
            if signal in stored.get(device, {})
        ]
        if not signals:
            text = f"{name} shows no signal to overlay"
        elif not sources:
            text = f"Scan {self.scan_list.model.scan_label(entry)} did not store what {name} shows"
        else:
            text = add_history_curves(plot, sources).message(name)
            missing = len(signals) - len(sources)
            if missing:
                text += f" ({missing} not stored in scan {self.scan_list.model.scan_label(entry)})"
        self.scan_list.flash_note(text)
        return text

    ################################################################################
    # Housekeeping
    ################################################################################

    def pause(self) -> None:
        """
        Stop reading files while the viewer is not shown, e.g. while another view of the main
        application is open. :meth:`resume` picks up what was cut off.
        """
        self._paused_busy = self._busy_timer.isActive()
        self._busy_timer.stop()
        self.tree.pause()
        self.service.cancel(self._copy_channel)
        self._copy_finished()
        channel = self.preview._channel  # pylint: disable=protected-access
        self._paused_preview = self.service.has_pending(channel)
        self.service.cancel_all(channel)

    def resume(self) -> None:
        """Read again what :meth:`pause` cut off."""
        self.tree.resume()
        if getattr(self, "_paused_busy", False):
            self._paused_busy = False
            self._busy_timer.start()
        if getattr(self, "_paused_preview", False):
            self._paused_preview = False
            self.preview.reload()

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        """
        Follow a change of the theme.

        Args:
            theme (str): Name of the theme.
        """
        if not hasattr(self, "scan_list"):
            return
        remute(self)
        self.signal_list.apply_theme()
        self.scan_list.view.viewport().update()
        # The Waveform recolours its curves when it follows the theme itself; give the curves
        # the colours of the scan list and the signal chips again once it has done so.
        QTimer.singleShot(0, self._refresh_plot)

    def cleanup(self):
        """Stop the reads, release the history and scan status subscriptions."""
        self._switch_timer.stop()
        self._release_plot()
        self._history_timer.stop()
        self._busy_timer.stop()
        self._reread_timer.stop()
        self._empty_timer.stop()
        self._map_wait_timer.stop()
        self._lines_wait_timer.stop()
        self._add_reset_timer.stop()
        self._file_add_reset_timer.stop()
        h5_reader.set_listed_files(self, ())
        for scan_id in list(self._imported):
            forget_imported(self.client, scan_id)
        self._imported.clear()
        self.service.cancel(self._copy_channel)
        self.scan_list.cleanup()
        self.tree.cleanup()
        self.file_box.cleanup()
        self.preview.cleanup()
        self.service.cleanup()
        self.history_manager.cleanup()
        # The panes live in docks, and the dock area takes the docks away from this widget
        # before the BECWidget cleanup looks for child widgets: close those in the panes first.
        for child in self.findChildren(BECWidget):
            if isValid(child):
                child.close()
                child.deleteLater()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("light")
    viewer = HDF5Viewer()
    viewer.setWindowTitle("HDF5 Viewer")
    viewer.resize(1400, 820)
    viewer.show()
    for argument in sys.argv[1:2]:
        viewer.open_file(argument)
    sys.exit(app.exec())
