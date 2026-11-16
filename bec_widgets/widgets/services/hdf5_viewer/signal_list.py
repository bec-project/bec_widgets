"""
The signals of a scan, grouped by what can be plotted against what.

The list is built from what the scan history says about the stored data. The boxes are BEC's
readout groups; the viewer reads them from the scan file off the GUI thread and the list
sorts by shape until they are known. A signal is put on the plot with its Y button and chosen
as the x axis with its X button. Images, spectra and single values open in the File tab.
"""

from __future__ import annotations

from dataclasses import dataclass

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent, QModelIndex, QPoint, QRect, QRectF, QSize, Qt, Signal
from qtpy.QtGui import QColor, QCursor, QFont, QFontMetrics, QPainter, QPalette
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeConnect, SafeSlot
from bec_widgets.utils.fuzzy_search import close_names, match
from bec_widgets.utils.theme_utils import css, theme_colors
from bec_widgets.widgets.progress.stage_bar import Tone
from bec_widgets.widgets.services.bec_queue.queue_ui import ROW_HOVER_ALPHA, ROW_SELECTED_ALPHA
from bec_widgets.widgets.services.hdf5_viewer.h5_reader import format_shape
from bec_widgets.widgets.services.hdf5_viewer.map_view import is_two_dimensional
from bec_widgets.widgets.services.hdf5_viewer.role_fields import ChipInfo, Role, RoleBox, Swatch
from bec_widgets.widgets.services.hdf5_viewer.role_list import (
    ListEntry,
    Listing,
    RoleTyping,
    elide_marked,
    runs,
)
from bec_widgets.widgets.services.hdf5_viewer.scan_list import ScanEntry, on_color
from bec_widgets.widgets.services.hdf5_viewer.style import (
    HEAD_BAND_HEIGHT,
    HEAD_GAP,
    mix_colors,
    mute,
    muted_color,
    paint_group_head,
    paint_list_row,
    remute,
    tone_color,
)

SIGNAL_ROLE = Qt.ItemDataRole.UserRole + 1
#: The box (see :data:`GROUPS`) of a group row of the list.
BOX_ROLE = Qt.ItemDataRole.UserRole + 2
#: Letters of a signal's name that the filter matched.
MATCH_ROLE = Qt.ItemDataRole.UserRole + 3
#: (title, count) of a group row of the list, as its header shows them.
HEAD_ROLE = Qt.ItemDataRole.UserRole + 4
#: Letters a name keeps before the length beside it gives way.
NAME_KEEPS = 12
#: The narrowest the panel gets.
MIN_WIDTH = 260

#: Tooltip of a scan device whose axis was chosen by the list itself.
AUTO_TIP = "Chosen automatically: the scan moved this device"
#: Note under the box while async signals are on the plot.
ASYNC_NOTE = "Async signals are plotted against their sample number"

SourceKey = tuple[str, str]

#: The x axes of Lines that are no signal: the Waveform's own x modes, as keys of no device.
INDEX_X: SourceKey = ("", "index")
TIMESTAMP_X: SourceKey = ("", "timestamp")
#: Their name, as the Waveform and the File tab call them, and what they are in a few words.
X_MODES: dict[SourceKey, tuple[str, str]] = {
    INDEX_X: ("Index", "point number"),
    TIMESTAMP_X: ("Timestamp", "time of each point"),
}
#: Title of their group in the list of the X field.
X_MODES_TITLE = "Plot axis"

#: The boxes of the list, in the order they are listed, with their title and what they mean.
#: Besides the scan devices they are BEC's readout groups. Images and spectra are listed in the
#: box of their readout group, after its single numbers.
GROUPS = {
    "scan": ("Scan devices", "The devices the scan moved: they are the axes of the plot"),
    "point": ("Monitored", "Read at every scan point: can be plotted against each other"),
    "fast": ("Async", "Recorded at their own rate, plotted against their sample number"),
    "single": ("Baseline", "Read once for the scan, open in the File tab"),
    "other": ("Other", "In no readout group of the scan: read on request or by the device"),
}

#: Added to the tooltip of the boxes when the file does not name its readout groups.
SHAPE_GROUPING_NOTE = (
    "This file does not name its readout groups: the signals are grouped by the shape of "
    "their data."
)

#: The box of each of BEC's readout groups.
READOUT_BOXES = {"monitored": "point", "async": "fast", "baseline": "single"}


@dataclass(frozen=True)
class DatasetKey:
    """The key of the chip of a dataset of the scan's file that is a curve but no signal."""

    #: Path of the dataset inside the file.
    path: str


@dataclass(frozen=True)
class SignalInfo:
    """One stored signal of a scan."""

    device: str
    entry: str
    shape: tuple[int, ...]
    dtype: str
    group: str
    #: The box of the list the signal is shown in, see :data:`GROUPS`.
    box: str = ""

    @property
    def key(self) -> SourceKey:
        """The (device, entry) pair the plots and the Data API use."""
        return (self.device, self.entry)

    @property
    def label(self) -> str:
        """Short name: the device, and the signal where it differs from it."""
        if self.entry == self.device:
            return self.device
        if self.entry.startswith(f"{self.device}_"):
            return f"{self.device} · {self.entry[len(self.device) + 1:]}"
        return f"{self.device} · {self.entry}"

    @property
    def plottable(self) -> bool:
        """Whether the signal can be drawn as a curve."""
        return self.group in ("point", "fast")

    @property
    def dataset_path(self) -> str:
        """Where BEC stores the values of the signal in the scan file."""
        return f"/entry/collection/devices/{self.device}/{self.entry}/value"


def classify(shape: tuple[int, ...], num_points: int | None, kind: str | None = None) -> str:
    """
    Decide the group of a signal from the shape of its stored data.

    Args:
        shape (tuple[int, ...]): Shape of the stored values.
        num_points (int | None): Number of scan points, when known.
        kind (str | None): What the Data API says about the signal: ``monitored``,
            ``async`` or ``unindexed``.

    Returns:
        str: ``point``, ``fast``, ``array`` or ``single``.
    """
    size = 1
    for length in shape:
        size *= length
    if len(shape) >= 2 and size > 1 and min(shape[1:]) > 1:
        return "array"
    if size == 0 and kind in ("monitored", "async"):
        # A running scan: the shape is not known yet, the kind is.
        return "point" if kind == "monitored" else "fast"
    if size <= 1 and (num_points or 0) != 1:
        return "single"
    if kind == "monitored":
        return "point"
    if kind == "async":
        return "fast"
    if num_points and shape and shape[0] == num_points:
        return "point"
    return "fast"


def box_of(
    group: str,
    shape: tuple[int, ...],
    num_points: int | None,
    kind: str | None = None,
    readout: str | None = None,
    readouts_known: bool = False,
) -> str:
    """
    Decide the box of the list a signal is shown in.

    Args:
        group (str): The group of the signal, see :func:`classify`.
        shape (tuple[int, ...]): Shape of the stored values.
        num_points (int | None): Number of scan points, when known.
        kind (str | None): What the Data API says about the signal.
        readout (str | None): BEC's readout group of the device, when known.
        readouts_known (bool): Whether the readout groups of the scan are known, so a device
            in none of them was read otherwise.

    Returns:
        str: ``point``, ``fast``, ``single`` or ``other``.
    """
    if readout is not None:
        return READOUT_BOXES.get(readout, "other")
    if readouts_known:
        return "other"
    if group != "array":
        return group
    # Not known: an image or spectrum goes with the signals keyed like it.
    if kind == "monitored" or (kind is None and num_points and shape[:1] == (num_points,)):
        return "point"
    return "fast"


def signals_of(
    entry: ScanEntry,
    kinds: dict[SourceKey, str] | None = None,
    readouts: dict[str, str] | None = None,
) -> list[SignalInfo]:
    """
    List the stored signals of a scan.

    Args:
        entry (ScanEntry): The scan.
        kinds (dict[SourceKey, str] | None): Kind of each signal as told by the Data API.
        readouts (dict[str, str] | None): BEC's readout group of each device, None when not
            known.

    Returns:
        list[SignalInfo]: The signals, sorted by device and signal name.
    """
    out = []
    for device, signals in sorted((entry.stored_data_info or {}).items()):
        for name, info in sorted(signals.items()):
            if isinstance(info, dict):
                shape, dtype = info.get("shape") or (), info.get("dtype") or ""
            else:
                shape, dtype = getattr(info, "shape", ()), getattr(info, "dtype", "") or ""
            shape = tuple(int(n) for n in shape)
            kind = (kinds or {}).get((device, name))
            readout = (readouts or {}).get(device)
            group = classify(shape, entry.num_points, kind)
            if readout == "baseline" and group != "array":
                # Read once, also in a scan of one point.
                group = "single"
            box = box_of(group, shape, entry.num_points, kind, readout, readouts is not None)
            out.append(SignalInfo(device, name, shape, dtype, group, box))
    return out


class _ChipDelegate(QStyledItemDelegate):
    """Draws the X and Y buttons of a signal (X, Y and Z in a two-dimensional scan), or its
    Open button."""

    CHIP = QSize(24, 20)
    GAP = 4

    def __init__(self, owner: SignalList):
        super().__init__(owner.tree)
        self._owner = owner

    def letters(self, signal: SignalInfo) -> list[str]:
        """
        The buttons of a signal, left to right.

        Args:
            signal (SignalInfo): The signal.

        Returns:
            list[str]: ``X``, ``Y`` and ``Z``, only ``Y`` in a picker, or ``Open``.
        """
        if self._owner.picker:
            return ["Y"] if signal.plottable else []
        if not signal.plottable:
            return ["Open"]
        return self._owner.row_letters()

    def chip_rects(self, rect: QRect, signal: SignalInfo) -> dict[str, QRect]:
        """
        Where the buttons of a row are.

        Args:
            rect (QRect): Rectangle of the cell.
            signal (SignalInfo): The signal of the row.

        Returns:
            dict[str, QRect]: Rectangle of each button, by its letter.
        """
        letters = self.letters(signal)
        top = rect.center().y() - self.CHIP.height() // 2
        width = self.CHIP.width()
        slots = []
        for position in range(max(len(letters), 2)):
            right = rect.right() - 4 - position * (width + self.GAP)
            slots.insert(0, QRect(right - width + 1, top, width, self.CHIP.height()))
        if letters == ["Open"]:
            return {"Open": slots[-2].united(slots[-1])}
        return dict(zip(letters, slots[-len(letters) :])) if letters else {}

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(3 * self.CHIP.width() + 2 * self.GAP + 10, self.CHIP.height() + 6)

    def _draw_chip(self, painter: QPainter, rect: QRect, text: str, fill, ink, enabled=True):
        painter.setOpacity(1.0 if enabled else 0.35)
        if fill is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
        else:
            outline = QColor(ink)
            outline.setAlphaF(0.45)
            painter.setPen(outline)
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 5, 5)
        painter.setPen(ink)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.setOpacity(1.0)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        signal: SignalInfo | None = index.sibling(index.row(), 0).data(SIGNAL_ROLE)
        # The list paints the background of the row; the buttons go on top of it.
        if signal is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fills = self._owner.row_fill(signal.key)
        ink = self._owner.ink_of(signal.key)
        font = QFont(option.font)
        font.setWeight(QFont.Weight.DemiBold)
        font.setPointSizeF(option.font.pointSizeF() * 0.9)
        painter.setFont(font)
        owner = self._owner
        axis_ink = QColor("#000000" if ink.lightness() > 128 else "#ffffff")
        axis = owner.axis_of(signal.key)
        point = signal.group == "point"
        for letter, rect in self.chip_rects(option.rect, signal).items():
            if letter == "Open":
                self._draw_chip(painter, rect, "Open", None, ink)
            elif owner.role_kind(letter) in ("x", "y"):
                # An axis: filled with the text colour when it is this one.
                is_on = axis == letter.lower()
                self._draw_chip(
                    painter,
                    rect,
                    letter,
                    QColor(ink) if is_on else None,
                    axis_ink if is_on else ink,
                    enabled=point,
                )
            else:
                # The values: the curves of Lines (Y) or the colour of a map (Z).
                is_on = signal.key in owner.y_signals()
                if is_on and owner.unread_reason(signal.key) is not None:
                    # Asked for but not drawn: an outline in the colour of a problem.
                    self._draw_chip(painter, rect, letter, None, tone_color(Tone.BAD))
                    continue
                if is_on and fills:
                    # On the row in the colour of its curves: the button in black or white,
                    # its letter in that colour.
                    self._draw_chip(painter, rect, letter, QColor(ink), mix_colors(fills))
                    continue
                fill = QColor(owner.swatch_of(signal.key).color) if is_on else None
                self._draw_chip(painter, rect, letter, fill, on_color(fill) if is_on else ink)
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:
        if event.type() != QEvent.Type.MouseButtonRelease:
            return super().editorEvent(event, model, option, index)
        signal: SignalInfo | None = index.sibling(index.row(), 0).data(SIGNAL_ROLE)
        if signal is None:
            return False
        position = event.position().toPoint()
        for letter, rect in self.chip_rects(option.rect, signal).items():
            if rect.contains(position):
                self._owner.press(letter, signal.key)
                return True
        return False

    def helpEvent(self, event, view, option, index) -> bool:
        signal: SignalInfo | None = index.sibling(index.row(), 0).data(SIGNAL_ROLE)
        if signal is None:
            return super().helpEvent(event, view, option, index)
        hit = [
            letter
            for letter, rect in self.chip_rects(option.rect, signal).items()
            if rect.contains(event.pos())
        ]
        if not hit:
            return super().helpEvent(event, view, option, index)
        QToolTip.showText(event.globalPos(), self._owner.chip_tip(hit[0], signal), view)
        return True


class _NameDelegate(QStyledItemDelegate):
    """
    Draws the name of a signal cut in its middle where it is too long, with the letters the
    filter matched in bold and underlined; the rest of the row is drawn by the style.
    """

    def __init__(self, owner: SignalList):
        super().__init__(owner.tree)
        self._owner = owner

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        if index.data(HEAD_ROLE) is None:
            return super().sizeHint(option, index)
        gap = HEAD_GAP if self._owner.head_follows_rows(index) else 0
        # The band is as tall as a row of buttons, the room above comes on top.
        band = max(HEAD_BAND_HEIGHT, _ChipDelegate.CHIP.height() + 6)
        return QSize(super().sizeHint(option, index).width(), band + gap)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        head = index.data(HEAD_ROLE)
        if head is not None:
            # A group: the header of the scan list's days, across the whole row.
            tree = self._owner.tree
            follows = self._owner.head_follows_rows(index)
            rect = QRect(0, option.rect.top(), tree.viewport().width(), option.rect.height())
            paint_group_head(
                painter,
                rect,
                head[0],
                head[1],
                theme_colors()["bg"],
                option.font,
                gap=HEAD_GAP if follows else 0,
                rule=follows,
                open_=tree.isExpanded(index),
            )
            return
        signal: SignalInfo | None = index.data(SIGNAL_ROLE)
        if signal is None:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
        rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, widget)
        rect = rect.adjusted(2, 0, -2, 0)
        positions = tuple(index.data(MATCH_ROLE) or ())
        metrics = QFontMetrics(opt.font)
        shown, positions = elide_marked(text, positions, metrics, rect.width())
        painter.save()
        # The text colour of the theme as the list last read it, or black or white on a row in
        # the colour of its curves.
        painter.setPen(self._owner.ink_of(signal.key))
        strong = QFont(opt.font)
        strong.setWeight(QFont.Weight.Bold)
        strong.setUnderline(True)
        x = rect.left()
        for run, marked in runs(shown, positions):
            font = strong if marked else opt.font
            painter.setFont(font)
            width = QFontMetrics(font).horizontalAdvance(run)
            painter.drawText(
                QRect(x, rect.top(), width + 1, rect.height()), Qt.AlignmentFlag.AlignVCenter, run
            )
            x += width
        painter.restore()


class _LengthDelegate(QStyledItemDelegate):
    """Draws the length of a signal, in black or white on a row in the colour of its curves."""

    def __init__(self, owner: SignalList):
        super().__init__(owner.tree)
        self._owner = owner

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex):
        super().initStyleOption(option, index)
        # The list paints the background of the row.
        option.state &= ~QStyle.StateFlag.State_Selected
        option.state &= ~QStyle.StateFlag.State_MouseOver
        signal: SignalInfo | None = index.sibling(index.row(), 0).data(SIGNAL_ROLE)
        if signal is not None and self._owner.row_fill(signal.key):
            option.palette.setColor(QPalette.ColorRole.Text, self._owner.ink_of(signal.key))


class _SignalTree(QTreeWidget):
    """
    Tree that presses the buttons of the current signal with the X, Y, Z and Enter keys.

    Its rows stay where they are on screen when its top edge moves and its bottom edge does
    not, e.g. when a line of chips comes or goes in the box above it: a click on a role
    button must not move the row under the pointer, or the next click lands on another row.
    This holds while the user works in the list or the box; a box that fills for a new scan
    leaves the list at its top.
    """

    def __init__(self, owner: SignalList):
        super().__init__(owner)
        self._owner = owner
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        #: (top, bottom) in the panel after the last change of geometry, and the height then.
        self._edges: tuple[int, int] | None = None
        self._height = -1
        #: The row under the pointer, as last painted.
        self._hovered = QRect()

    def drawRow(self, painter, option, index):  # pylint: disable=invalid-name
        signal: SignalInfo | None = index.sibling(index.row(), 0).data(SIGNAL_ROLE)
        if signal is not None:
            # As the rows of the scan list: in the colour of the curves while on the plot, a
            # ring for the current row, a shade under the pointer.
            row = QRectF(2, option.rect.top(), self.viewport().width() - 4, option.rect.height())
            selected = self.selectionModel().isRowSelected(index.row(), index.parent())
            viewport = self.viewport()
            pointer = viewport.mapFromGlobal(QCursor.pos())
            hovered = viewport.underMouse() and option.rect.contains(pointer)
            paint_list_row(painter, row, self._owner.row_fill(signal.key), selected, hovered)
        super().drawRow(painter, option, index)

    def _row_rect(self, position: QPoint) -> QRect:
        """The whole row under a point of the viewport, or an empty rectangle."""
        index = self.indexAt(position)
        if not index.isValid():
            return QRect()
        rect = self.visualRect(index)
        return QRect(0, rect.top(), self.viewport().width(), rect.height())

    def mouseMoveEvent(self, event):  # pylint: disable=invalid-name
        # The row under the pointer is shaded whole: repaint the rows it leaves and enters.
        rect = self._row_rect(event.position().toPoint())
        if rect != self._hovered:
            self.viewport().update(self._hovered)
            self.viewport().update(rect)
            self._hovered = rect
        super().mouseMoveEvent(event)

    def viewportEvent(self, event):  # pylint: disable=invalid-name
        if event.type() == QEvent.Type.Leave and not self._hovered.isNull():
            self.viewport().update(self._hovered)
            self._hovered = QRect()
        return super().viewportEvent(event)

    def _current_edges(self) -> tuple[int, int]:
        # Measured in the panel, so that it does not matter how deeply the tree is nested.
        top = self.mapTo(self._owner, QPoint(0, 0)).y()
        return top, top + self.height()

    def moveEvent(self, event):  # pylint: disable=invalid-name
        super().moveEvent(event)
        if self.height() == self._height:
            # A move alone: no resize follows that would take it into account.
            self._edges = self._current_edges()

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        # The base class first brings the range of the scroll bar up to date.
        super().resizeEvent(event)
        self._owner.fit_columns()
        old, new = self._edges, self._current_edges()
        self._edges, self._height = new, self.height()
        if old is None or not self.isVisible():
            return
        if new[1] == old[1] and new[0] != old[0] and self._owner.anchors_rows():
            bar = self.verticalScrollBar()
            bar.setValue(bar.value() + new[0] - old[0])

    #: Keys that move the current row of the list.
    MOVE_KEYS = (
        Qt.Key.Key_Up,
        Qt.Key.Key_Down,
        Qt.Key.Key_PageUp,
        Qt.Key.Key_PageDown,
        Qt.Key.Key_Home,
        Qt.Key.Key_End,
    )

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        if event.key() in self.MOVE_KEYS:
            # The box held its height for a pointer resting on the list; the keyboard gives it
            # back, and the rows stay where they are while it shrinks.
            self._owner.release_top()
        item = self.currentItem()
        signal: SignalInfo | None = item.data(0, SIGNAL_ROLE) if item is not None else None
        if signal is not None:
            letter = {Qt.Key.Key_X: "X", Qt.Key.Key_Y: "Y", Qt.Key.Key_Z: "Z"}.get(event.key())
            if letter is not None and signal.plottable:
                self._owner.press(letter, signal.key)
                return
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                if signal.plottable:
                    self._owner.toggle_y(signal.key)
                elif not self._owner.picker:
                    self._owner.open_requested.emit(signal)
                return
        super().keyPressEvent(event)


class SignalList(QWidget):
    """The stored signals of the selected scan, with X and Y buttons."""

    #: The signals on the plot or the x axis changed.
    selection_changed = Signal()
    #: A signal that cannot be plotted should be opened in the File tab.
    open_requested = Signal(object)
    #: Y was pressed on a signal: (device, entry) and whether it is on now.
    y_toggled = Signal(object, bool)
    #: The chip of a dataset that is no signal was taken off the curves: its path.
    dataset_removed = Signal(str)
    #: Reset was asked for: the datasets that are no signal go off the plot as well.
    reset_requested = Signal()

    def __init__(self, parent: QWidget | None = None, picker: bool = False):
        """
        Args:
            parent (QWidget | None): Parent widget.
            picker (bool): Only Y buttons, for picking curves of another plot: no x axis, no
                Open button, no signal chosen by itself, and signals of different groups can
                be on together.
        """
        super().__init__(parent)
        self.picker = picker
        self._signals: dict[SourceKey, SignalInfo] = {}
        #: The rows of the listed signals, and what decides their place and look: the next
        #: scan with the same layout (the usual case when walking through scans of one kind)
        #: keeps the rows and only updates their shapes.
        self._rows: dict[SourceKey, QTreeWidgetItem] = {}
        self._layout: tuple | None = None
        #: Width the lengths beside the names need; None once a length changed.
        self._length: int | None = None
        #: Whether rows are hidden or marked by the filter, so that an empty filter on clean
        #: rows needs no walk through them.
        self._filtered = False
        #: Boxes the user opened or closed, by name: they stay so for every scan.
        self._box_open: dict[str, bool] = {}
        #: Whether the list itself opens or closes boxes (not the user).
        self._opening = False
        self._y: list[SourceKey] = []
        #: Whether the signals on the plot are the scan's default, not a choice of the user.
        self._y_default = False
        #: What the x axis is when no X is chosen, as the plot was told.
        self._auto_axis = ""
        #: Whether the plot is a map (heatmap or scatter); a map has one colour signal.
        self._map = False
        #: The kind of scan the plot shows, as the viewer keeps its views apart.
        self._kind = ""
        #: The curves Lines showed last per kind of scan with a map, as the user chose them.
        self._lines_y: dict[str, list[SourceKey]] = {}
        #: The colour the map had last per kind of scan, as the user chose it.
        self._map_colour: dict[str, SourceKey] = {}
        #: The x axis the user chose, or None for the scan's own.
        self._x: SourceKey | None = None
        #: The y axis the user chose in a two-dimensional scan, or None for the scan's own.
        self._y_axis: SourceKey | None = None
        #: Whether the scan is two-dimensional: X and Y are positions, Z the values.
        self._two_d = False
        self._colors: dict[SourceKey, str] = {}
        #: Line style per signal while several scans are on the plot, else empty.
        self._styles: dict[SourceKey, str] = {}
        #: Signals on the plot whose stored data could not be read, with the reason.
        self._unread: dict[SourceKey, str] = {}
        self._default_color = "#2a78d6"
        self._entry: ScanEntry | None = None
        self._kinds: dict[SourceKey, str] | None = None
        self._readouts: dict[str, str] | None = None
        #: Whether the file of the listed scan does not name its readout groups.
        self._by_shape = False
        #: Why the last X could not be taken; shown in the note until the next change.
        self._refusal = ""
        #: Readbacks of the devices the scan moved, in the order it moved them.
        self._scan_axes: list[SourceKey] = []
        #: The x axis the plot takes when no X is chosen, as the plot was told.
        self._auto_x: SourceKey | None = None
        self._scan_head: QTreeWidgetItem | None = None
        #: The chips of the datasets of the scan's file that are curves but no signals, after
        #: those of the signals in the curves' field.
        self._dataset_chips: tuple[ChipInfo, ...] = ()

        #: What the plot shows, by role; not in a picker, whose plot is another one.
        self.box = RoleBox(self)
        self.box.hide()
        self.reset_axes_button = self.box.reset_button
        self.box.remove_requested.connect(self._remove_from_role)
        self.box.reset_requested.connect(self.reset)
        #: Typing in the fields, and the list under them.
        self.typing = RoleTyping(
            self, self.box, self.role_listing, self.take_role, self._remove_from_role
        )

        self.filter_edit = QLineEdit(self)
        self.filter_edit.setObjectName("signal_filter")
        self.filter_edit.setPlaceholderText("Filter signals")
        self.filter_edit.setAccessibleName("Filter signals")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.addAction(
            material_icon("filter_list", size=(16, 16), convert_to_pixmap=False),
            QLineEdit.ActionPosition.LeadingPosition,
        )

        self.tree = _SignalTree(self)
        self.tree.setObjectName("signal_view")
        self.tree.setColumnCount(3)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(8)
        # A group's header is taller than a row: room above it sets the groups apart.
        self.tree.setUniformRowHeights(False)
        # A click on a header opens or closes the group; a double click does nothing more.
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setMouseTracking(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setAccessibleName("Signals of the scan")
        self._delegate = _ChipDelegate(self)
        self.tree.setItemDelegateForColumn(2, self._delegate)
        self.tree.setItemDelegateForColumn(0, _NameDelegate(self))
        self.tree.setItemDelegateForColumn(1, _LengthDelegate(self))
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 38 if picker else 66)
        header.setMinimumSectionSize(40)

        self.note = QLabel(self)
        self.note.setWordWrap(True)
        mute(self.note)
        self.note.setContentsMargins(6, 2, 6, 2)

        # The box and the notes about the plot, which sit right under it. While the pointer
        # is on the list, the two keep their height when they shrink, until it leaves.
        self.top = QWidget(self)
        self.top.setObjectName("signal_top")
        self.top.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        top_layout = QVBoxLayout(self.top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)
        top_layout.addWidget(self.box)
        top_layout.addWidget(self.note)
        top_layout.addStretch(1)
        self.tree.viewport().installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.top)
        layout.addWidget(self.filter_edit)
        layout.addWidget(self.tree, 1)

        # In place of the list when the filter hides every signal.
        self.filter_empty = QWidget(self)
        self.filter_empty.setObjectName("filter_empty")
        empty_layout = QVBoxLayout(self.filter_empty)
        empty_layout.setContentsMargins(6, 12, 6, 12)
        empty_layout.setSpacing(8)
        self.filter_empty_text = QLabel(self.filter_empty)
        self.filter_empty_text.setWordWrap(True)
        mute(self.filter_empty_text)
        self.clear_filter_button = QPushButton("Clear the filter", self.filter_empty)
        self.clear_filter_button.setObjectName("clear_filter_button")
        self.clear_filter_button.clicked.connect(self.filter_edit.clear)
        empty_layout.addWidget(self.filter_empty_text)
        empty_layout.addWidget(self.clear_filter_button, 0, Qt.AlignmentFlag.AlignLeft)
        empty_layout.addStretch(1)
        self.filter_empty.hide()
        layout.addWidget(self.filter_empty, 1)

        if not picker:
            # The box keeps a chip and the text on a line, and a row its buttons and a name.
            self.setMinimumWidth(MIN_WIDTH)
        self.apply_theme()
        # The list is no BEC widget: it follows a change of the theme itself, also in the
        # picker of another plot.
        app = QApplication.instance()
        if hasattr(app, "theme"):
            SafeConnect(self, app.theme.theme_changed, self._on_theme_changed)
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemExpanded.connect(lambda item: self._on_box_toggled(item, True))
        self.tree.itemCollapsed.connect(lambda item: self._on_box_toggled(item, False))
        self._update_note()

    ################################################################################
    # Public interface
    ################################################################################

    def set_scan(
        self,
        entry: ScanEntry | None,
        kinds: dict[SourceKey, str] | None = None,
        readouts: dict[str, str] | None = None,
    ):
        """
        List the signals of a scan. Signals that were on the plot stay on it when the new
        scan has them too.

        Args:
            entry (ScanEntry | None): The scan, or None to empty the list.
            kinds (dict[SourceKey, str] | None): Kind of each signal as told by the Data API.
            readouts (dict[str, str] | None): BEC's readout group of each device, None while
                not known: the signals are then sorted by the shape of their data.
        """
        self._entry = entry
        self._kinds = kinds
        self._readouts = readouts
        self._by_shape = False
        self.release_top()
        signals = signals_of(entry, kinds, readouts) if entry is not None else []
        self._signals = {signal.key: signal for signal in signals}
        self._scan_axes = self.scan_axes_of(entry, self._signals)
        self._two_d = not self.picker and is_two_dimensional(entry) and len(self._scan_axes) >= 2
        self._fit_buttons()
        # A choice of the user stays for every scan that has its signals; a default is the
        # default of each scan anew.
        self._y = [] if self._y_default else [key for key in self._y if self._plottable(key)]
        self._y_default = False
        if (
            self._x is not None
            and self._x not in X_MODES
            and not (self._x in self._signals and self._signals[self._x].group == "point")
        ):
            self._x = None
        if not self._two_d or not (
            self._y_axis in self._signals and self._signals[self._y_axis].group == "point"
        ):
            self._y_axis = None
        if self.picker:
            self._y = []
        elif not self._y:
            # Nothing of the last plot exists in this scan: start with its first detector.
            default = self._default_y(entry, signals)
            if default is not None:
                self._y = [default]
                self._y_default = True
        self._rebuild(signals)
        self._update_note()
        for field in self.box.fields.values():
            # A newly chosen scan starts at the top of its fields.
            field.set_top()
        self.selection_changed.emit()

    def set_readouts(self, readouts: dict[str, str] | None) -> None:
        """
        Sort the signals of the listed scan into BEC's readout groups once they are known.
        What is on the plot stays.

        Args:
            readouts (dict[str, str] | None): BEC's readout group of each device.
        """
        if self._entry is None or readouts == self._readouts:
            return
        self._readouts = readouts
        signals = signals_of(self._entry, self._kinds, readouts)
        if signals == list(self._signals.values()):
            return
        groups = {key: signal.group for key, signal in self._signals.items()}
        self._signals = {signal.key: signal for signal in signals}
        if all(groups.get(signal.key) == signal.group for signal in signals):
            # Only the boxes moved: the plot stays as it is.
            self._rebuild(signals)
            self._update_note()
            return
        self.set_scan(self._entry, self._kinds, readouts)

    def mark_grouped_by_shape(self) -> None:
        """Say in the tooltips of the boxes that the file does not name its readout groups."""
        if self._by_shape or self._entry is None:
            return
        self._by_shape = True
        self._rebuild(list(self._signals.values()))

    def signals(self) -> list[SignalInfo]:
        """
        The signals of the scan.

        Returns:
            list[SignalInfo]: All listed signals.
        """
        return list(self._signals.values())

    def y_signals(self) -> list[SourceKey]:
        """
        The signals on the plot.

        Returns:
            list[SourceKey]: (device, entry) pairs in the order they were added.
        """
        return list(self._y)

    def y_is_default(self) -> bool:
        """
        Whether the signals on the plot are the scan's default rather than the user's choice.

        Returns:
            bool: True when the list put them on by itself.
        """
        return self._y_default

    def set_map(self, on: bool, kind: str = "") -> None:
        """
        Tell the list that the plot is a map of the scan's x and y axes, or lines again.

        The axes stay what they are, and no choice is lost. A map has one colour: the colour
        the map had last if it is one of the curves, else the first curve with one value per
        scan point, else the scan's default. Lines again show the curves Lines showed last
        for this kind of scan, with the colour of the map added; without such curves the
        colour alone.

        Args:
            on (bool): Whether the plot is a map.
            kind (str): The kind of scan, e.g. ``grid``: choices are kept per kind.
        """
        on = bool(on)
        changed = on != self._map
        self._map = on
        self._kind = kind
        if not on:
            if changed:
                self._to_lines()
                self._refusal = ""
                self._fit_buttons()
                self.tree.viewport().update()
                self._update_scan_rows()
                self._update_note()
            return
        points = [key for key in self._y if self._signals[key].group == "point"]
        if len(self._y) <= 1 and points == self._y and not changed:
            return
        last = self._map_colour.get(kind)
        colour = last if last in points else (points[0] if points else None)
        if colour is not None:
            self._y = [colour]
        else:
            default = self._default_y(self._entry, list(self._signals.values()))
            self._y = [default] if default is not None else []
            self._y_default = default is not None
        self._refusal = ""
        self._fit_buttons()
        self.tree.viewport().update()
        self._update_scan_rows()
        self._update_note()

    def _to_lines(self) -> None:
        """Lines again: the curves Lines showed last for this kind of scan and the colour."""
        if not any(self._plottable(key) for key in self._lines_y.get(self._kind, [])):
            return
        self._y = self._lines_curves()
        self._y_default = False

    def _lines_curves(self) -> list[SourceKey]:
        """
        The curves Lines shows on going back from a map: those it showed last for this kind
        of scan and the colour of the map, or the colour alone.
        """
        colour = self._y[0] if self._y else None
        curves = [key for key in self._lines_y.get(self._kind, []) if self._plottable(key)]
        if not curves:
            return [colour] if colour is not None else []
        group = self._signals[curves[0]].group
        if colour is not None and colour not in curves and self._signals[colour].group == group:
            # Lines cannot mix async curves with values per point: the colour stays out.
            curves.append(colour)
        return curves

    def lines_signals(self) -> list[SourceKey]:
        """
        The curves of Lines, also while the plot is a map: then those Lines shows on going
        back to it.

        Returns:
            list[SourceKey]: (device, entry) pairs in the order of their colours.
        """
        return self._lines_curves() if self._map else list(self._y)

    def set_curves(self, keys: list[SourceKey]) -> None:
        """
        Make these signals the curves of Lines, e.g. as the File tab keeps them. Signals of
        different groups cannot share a plot: the group of the last one added stays. While the
        plot is a map, the map stays and Lines shows them on going back to it.

        Args:
            keys (list[SourceKey]): (device, entry) of the curves, in order.
        """
        keys = [key for key in dict.fromkeys(keys) if self._plottable(key)]
        before = self.lines_signals()
        if keys:
            added = [key for key in keys if key not in before]
            group = self._signals[(added or keys)[-1]].group
            keys = [key for key in keys if self._signals[key].group == group]
        if keys == before:
            return
        if self._map:
            self._lines_y[self._kind] = keys
            return
        self._y = keys
        self._y_default = False
        if keys and self._signals[keys[0]].group != "point" and self._x not in X_MODES:
            self._x = None
        self._changed()

    def _remember(self) -> None:
        """Keep what the user chose for the plot of this kind of scan, for the other view."""
        if self.picker or not self._two_d or self._y_default:
            return
        if self._map:
            if self._y:
                self._map_colour[self._kind] = self._y[0]
        else:
            self._lines_y[self._kind] = list(self._y)

    def row_letters(self) -> list[str]:
        """
        The buttons of a row that can be plotted: X and Y in Lines, X, Y and Z in a map.

        Returns:
            list[str]: The letters, left to right.
        """
        return ["X", "Y", "Z"] if self._two_d and self._map else ["X", "Y"]

    def _fit_buttons(self) -> None:
        """Give the column of buttons the room of the buttons the rows have now."""
        width = 38 if self.picker else (94 if len(self.row_letters()) == 3 else 66)
        if self.tree.header().sectionSize(2) != width:
            self.tree.header().resizeSection(2, width)

    def _toggle_map_y(self, key: SourceKey) -> None:
        """In a map the signal pressed becomes the colour; only signals per point can be one."""
        signal = self._signals[key]
        if signal.group != "point":
            self._refusal = (
                f"A map colours each scan point by one value: {signal.label} has more. "
                "Switch to Lines to plot it."
            )
            self._update_note()
            return
        self._y_default = False
        self._y = [] if key in self._y else [key]
        self._changed()
        self.y_toggled.emit(key, key in self._y)

    def is_two_dimensional(self) -> bool:
        """
        Whether the scan moved two motors, so that its signals have X, Y and Z buttons.

        Returns:
            bool: True for a scan of two stored motors or more (an area scan or any other).
        """
        return self._two_d

    def plane_axes(self) -> tuple[SourceKey, SourceKey] | None:
        """
        The x and the y axis of a two-dimensional scan: the scan's devices unless the user
        chose others.

        Returns:
            tuple[SourceKey, SourceKey] | None: (device, entry) of x and y, or None for a scan
            that is not two-dimensional.
        """
        if not self._two_d:
            return None
        return (self._signal_x() or self._scan_axes[0], self._y_axis or self._scan_axes[1])

    def _signal_x(self) -> SourceKey | None:
        """The signal chosen as x; None also while an x mode such as Index is chosen."""
        return None if self._x in X_MODES else self._x

    def _mode_x(self) -> SourceKey | None:
        """The x mode chosen for Lines (Index or Timestamp), or None. A map has none."""
        return self._x if self._x in X_MODES and not self._map else None

    def press(self, letter: str, key: SourceKey) -> None:
        """
        Press a button of a signal.

        Args:
            letter (str): ``X``, ``Y``, ``Z`` or ``Open``.
            key (SourceKey): (device, entry) of the signal.
        """
        if self.tree.viewport().underMouse():
            # A click in the list: what it takes away above must not pull the rows up.
            self._hold_top()
        if letter == "Open":
            signal = self._signals.get(key)
            if signal is not None:
                self.open_requested.emit(signal)
        elif self.picker:
            if letter == "Y":
                self.toggle_y(key)
        else:
            kind = self.role_kind(letter)
            if kind == "x":
                self.toggle_x(key)
            elif kind == "y":
                self.toggle_y_axis(key)
            elif kind in ("curves", "colour"):
                self.toggle_y(key)

    def chip_tip(self, letter: str, signal: SignalInfo) -> str:
        """
        Tooltip of a button of a signal.

        Args:
            letter (str): ``X``, ``Y``, ``Z`` or ``Open``.
            signal (SignalInfo): The signal.

        Returns:
            str: What the button does.
        """
        if letter == "Open":
            return "Open in the File tab (Enter)"
        if self.picker:
            return "Add to the plot, or take it off (Y)"
        point = signal.group == "point"
        kind = self.role_kind(letter)
        if kind == "x":
            return (
                "Use as the x axis (X)"
                if point
                else "Async signals are plotted against their sample number"
            )
        if kind == "y":
            return "Use as the y axis (Y)" if point else "An async signal cannot be an axis"
        unread = self._unread.get(signal.key) if signal.key in self.y_signals() else None
        if unread is not None:
            return f"Not drawn: {unread}. Press {letter} to take it off the plot."
        if kind == "colour":
            return "Colour the map by it (Z)"
        return "Show on the plot (Y)"

    def set_auto_axis(self, text: str, key: SourceKey | None = None) -> None:
        """
        Name the x axis that signals with one value per point get when no X is chosen.

        Args:
            text (str): E.g. "samx (the scan's positioner)", or empty for "chosen by the plot".
            key (SourceKey | None): (device, entry) of that axis, when it is a listed signal.
        """
        if text == self._auto_axis and key == self._auto_x:
            return
        self._auto_axis = text
        self._auto_x = key
        self.tree.viewport().update()
        self._update_scan_rows()
        self._update_note()

    @staticmethod
    def scan_axes_of(entry: ScanEntry | None, signals: dict[SourceKey, SignalInfo]) -> list:
        """
        The readbacks of the devices a scan moved, where it stored one value per scan point
        for them; the scan devices of the list.

        Args:
            entry (ScanEntry | None): The scan.
            signals (dict[SourceKey, SignalInfo]): Its listed signals.

        Returns:
            list[SourceKey]: (device, entry) of each, in the order the scan moved them.
        """
        if entry is None:
            return []
        keys = []
        for motor in entry.motors:
            signal = signals.get((motor, motor))
            if signal is not None and signal.group == "point":
                keys.append(signal.key)
        return keys

    def scan_axes(self) -> list[SourceKey]:
        """
        The readbacks of the devices the scan moved, listed as its scan devices.

        Returns:
            list[SourceKey]: (device, entry) of each, in the order the scan moved them.
        """
        return list(self._scan_axes)

    def axis_of(self, key: SourceKey) -> str:
        """
        Which axis a signal is on the plot.

        Args:
            key (SourceKey): (device, entry) of the signal.

        Returns:
            str: ``x`` or ``y``, or empty when it is no axis.
        """
        plane = self.plane_axes()
        if plane is not None:
            if key == plane[0] and self._mode_x() is None:
                return "x"
            if key == plane[1]:
                return "y"
            return ""
        if self._x is not None:
            return "x" if key == self._x else ""
        return "x" if key == self._auto_x else ""

    def axes_are_auto(self) -> bool:
        """
        Whether the axes are the scan's devices, as the list chose them.

        Returns:
            bool: False once the user chose another x (or y) axis.
        """
        x = self._signal_x() if self._map else self._x
        return x is None and self._y_axis is None

    def reset_axes(self) -> None:
        """Go back to the scan's devices as the axes."""
        if self.axes_are_auto():
            return
        self._x = None
        self._y_axis = None
        self._changed()

    def is_default(self) -> bool:
        """
        Whether the plot is the scan's default: its devices as the axes and its default curve.

        Returns:
            bool: False once the user chose another axis or other curves.
        """
        if not self.axes_are_auto():
            return False
        if self._y_default:
            return True
        default = self._default_y(self._entry, list(self._signals.values()))
        return self._y == ([default] if default is not None else [])

    def reset(self) -> None:
        """
        Go back to the scan's default: its devices as the axes and its default curve. The
        datasets that are no signal go off the plot as well, by whoever put them on.
        """
        self.reset_requested.emit()
        if self.is_default():
            return
        default = self._default_y(self._entry, list(self._signals.values()))
        self._x = None
        self._y_axis = None
        self._y = [default] if default is not None else []
        self._y_default = default is not None
        self._lines_y.pop(self._kind, None)
        self._map_colour.pop(self._kind, None)
        self._changed()

    def x_signal(self) -> SourceKey | None:
        """
        The signal chosen as the x axis, or the x mode chosen for Lines.

        Returns:
            SourceKey | None: (device, entry), :data:`INDEX_X` or :data:`TIMESTAMP_X`, or None
            when the plot chooses the axis.
        """
        return self._x

    def toggle_y(self, key: SourceKey) -> None:
        """
        Put a signal on the plot or take it off.

        Signals of different groups cannot share a plot: putting on a signal of another
        group takes the signals of the first group off.

        Args:
            key (SourceKey): (device, entry) of the signal.
        """
        if not self._plottable(key):
            return
        if self._map:
            if self.axis_of(key):
                self._refusal = (
                    f"{self._signals[key].label} is an axis of the map. "
                    "Press Z on another signal to colour the map by it."
                )
                self._update_note()
                return
            self._toggle_map_y(key)
            return
        self._y_default = False
        if key in self._y:
            self._y.remove(key)
        elif self.picker:
            self._y.append(key)
        else:
            group = self._signals[key].group
            self._y = [other for other in self._y if self._signals[other].group == group]
            self._y.append(key)
            if group != "point" and self._x not in X_MODES:
                self._x = None
        self._changed()
        self.y_toggled.emit(key, key in self._y)

    def set_y_signals(self, keys: list[SourceKey]) -> None:
        """
        Show which signals are on, without announcing it, e.g. to follow another plot.

        Args:
            keys (list[SourceKey]): (device, entry) of the signals that are on.
        """
        self._y = [key for key in keys if key in self._signals]
        self._y_default = False
        self.tree.viewport().update()
        self._update_note()

    def toggle_x(self, key: SourceKey) -> None:
        """
        Choose a signal as the x axis, or go back to the axis the plot chooses.

        Args:
            key (SourceKey): (device, entry) of a signal with one value per scan point, or
                :data:`INDEX_X` or :data:`TIMESTAMP_X`.
        """
        if key in X_MODES:
            self._toggle_x_mode(key)
            return
        signal = self._signals.get(key)
        if signal is None or signal.group != "point":
            return
        if self._two_d:
            self._choose_plane_axis(key, "x")
            return
        if self._x != key and any(self._signals[other].group != "point" for other in self._y):
            # A motor has one value per scan point, a fast signal many: it cannot be their x.
            # The fast signals stay on the plot against their sample number.
            self._refusal = (
                f"{signal.label} can only be the x axis of monitored signals. "
                "The async signals on the plot stay against their sample number."
            )
            self._update_note()
            return
        if self._x is None and key == self._auto_x:
            # It is the axis already; a plot always has one, so it cannot be taken off.
            return
        self._x = None if self._x == key else key
        self._changed()

    def _toggle_x_mode(self, key: SourceKey) -> None:
        """Make Index or Timestamp the x axis of Lines, or go back to the axis of the scan."""
        state, words = self.x_mode_state(key)
        if state == "off":
            self._refusal = f"{X_MODES[key][0]} cannot be the x axis here: {words}."
            self._update_note()
            return
        self._x = None if self._x == key else key
        self._changed()

    def x_mode_state(self, key: SourceKey) -> tuple[str, str]:
        """
        Whether Index or Timestamp can be the x axis now, as :meth:`role_state` says it.

        Args:
            key (SourceKey): :data:`INDEX_X` or :data:`TIMESTAMP_X`.

        Returns:
            tuple[str, str]: ``("", "")``, ``("on", words)`` or ``("off", reason)``.
        """
        if self._map:
            return "off", f"{X_MODES_TITLE} · only in Lines"
        # They pair no values, so they suit async curves too: Index is their sample number.
        if self._x == key:
            return "on", "the x axis now"
        return "", ""

    def toggle_y_axis(self, key: SourceKey) -> None:
        """
        Choose a signal as the y axis of a two-dimensional scan.

        Args:
            key (SourceKey): (device, entry) of a signal with one value per scan point.
        """
        signal = self._signals.get(key)
        if not self._two_d or signal is None or signal.group != "point":
            return
        self._choose_plane_axis(key, "y")

    def _choose_plane_axis(self, key: SourceKey, axis: str) -> None:
        """
        Make a signal the x or the y axis of a two-dimensional scan. The axis it was swaps
        places with it; an axis cannot be taken off, only replaced.
        """
        x, y = self.plane_axes()
        if (x if axis == "x" else y) == key:
            return
        if self._map and key in self._y:
            # The colour of each point cannot also be where the point is.
            self._refusal = (
                f"{self._signals[key].label} is the colour of the map. "
                "Press Z on another signal first to use it as an axis."
            )
            self._update_note()
            return
        if axis == "x":
            x, y = key, (x if y == key else y)
        else:
            x, y = (y if x == key else x), key
        if not self._map and any(self._signals[other].group != "point" for other in self._y):
            # Fast signals on the plot keep their sample number in Lines.
            self._refusal = (
                f"{self._signals[key].label} can only be an axis of monitored signals. "
                "The async signals on the plot stay against their sample number."
            )
            self._update_note()
            return
        if (x, y) == (self._scan_axes[0], self._scan_axes[1]):
            self._x, self._y_axis = None, None
        else:
            self._x, self._y_axis = x, y
        self._changed()

    def set_colors(
        self, colors: dict[SourceKey, str], default: str, styles: dict[SourceKey, str] | None = None
    ) -> None:
        """
        Tell the list how each signal is drawn, so that its button and its chip match.

        Args:
            colors (dict[SourceKey, str]): Colour per signal on the plot.
            default (str): Colour of a signal that has none of its own.
            styles (dict[SourceKey, str] | None): Line style per signal while several scans
                are on the plot: each signal then has one curve per scan, in a shade of the
                colour of its scan, and the style is the second cue.
        """
        styles = dict(styles or {})
        if (dict(colors), default, styles) == (self._colors, self._default_color, self._styles):
            return
        self._colors = dict(colors)
        self._default_color = default
        self._styles = styles
        self.tree.viewport().update()
        self._update_box()

    def swatch_of(self, key: SourceKey) -> Swatch:
        """
        How a signal on the plot is drawn: the swatch of its chip and the fill of its button.

        One scan on the plot: a solid line in the signal's colour. Several scans: the
        signal's line style in the colour of its curve for the selected scan.

        Args:
            key (SourceKey): (device, entry) of the signal.

        Returns:
            Swatch: Its colour and line style.
        """
        return Swatch(self.signal_color(key), self._styles.get(key, "solid"))

    def set_unread(self, unread: dict[SourceKey, str]) -> None:
        """
        Tell the list which signals are on the plot in name only: their data could not be read.
        Their Y button is drawn as an outline in the colour of a problem, not as a curve.

        Args:
            unread (dict[SourceKey, str]): The reason per signal, in the user's words.
        """
        if unread == self._unread:
            return
        self._unread = dict(unread)
        self.tree.viewport().update()
        self._update_box()

    def unread_reason(self, key: SourceKey) -> str | None:
        """
        Why a signal on the plot has no curve to show.

        Args:
            key (SourceKey): (device, entry) of the signal.

        Returns:
            str | None: The reason, or None when its data was read or is not asked for.
        """
        return self._unread.get(key)

    def signal_color(self, key: SourceKey) -> str:
        """
        Colour of the Y button of a signal.

        Args:
            key (SourceKey): (device, entry) of the signal.

        Returns:
            str: Colour as ``#rrggbb``.
        """
        return self._colors.get(key, self._default_color)

    def roles(self) -> list[Role]:
        """
        The roles of the plot and the signals that have them, as the box on top shows them.

        Returns:
            list[Role]: X and Y for a scan of one motor. For a scan of two motors also Z: in
            Lines Y holds the curves and Z is not used; in a map Y is the y axis and Z the
            colour. Empty in a picker and without signals.
        """
        if self.picker or self._entry is None or not self._signals:
            return []
        plane = self.plane_axes()
        if plane is None:
            x_chip = self._x_chip()
            return [self._axis_role("X", "x axis", x_chip), self._curves_role("Y")]
        mode = self._mode_x()
        x_chip = self._x_mode_chip(mode) if mode else self._plane_chip(plane[0])
        x_role = self._axis_role("X", "x axis", x_chip)
        if not self._map:
            # Lines draw every curve against x; the colour waits for a map.
            z_role = Role(
                "Z",
                axis=False,
                multi=False,
                caption="colour",
                chips=(),
                name="The colour of a map",
                hint="",
                can_be="can colour the map",
                inactive="Not used in Lines",
            )
            return [x_role, self._curves_role("Y"), z_role]
        chips = tuple(
            ChipInfo(
                key,
                self._signals[key].label,
                self._y_default,
                False,
                self.swatch_of(key),
                problem=self._unread.get(key, ""),
            )
            for key in self._y
        )
        colour = chips[0].label if chips else "none"
        return [
            x_role,
            self._axis_role("Y", "y axis", self._plane_chip(plane[1])),
            Role(
                "Z",
                axis=False,
                multi=False,
                caption="colour",
                chips=chips,
                name=f"The colour of the map: {colour}",
                hint="Type to colour the map by another signal",
                can_be="can colour the map",
            ),
        ]

    def _axis_role(self, letter: str, caption: str, chip: ChipInfo | None) -> Role:
        name = chip.label if chip is not None else "none"
        return Role(
            letter,
            axis=True,
            multi=False,
            caption=caption,
            chips=(chip,) if chip is not None else (),
            name=f"The {caption.split(',')[0]}: {name}",
            hint="Type to choose another signal",
            can_be=f"can be the {caption.split(',')[0]}",
        )

    def set_dataset_chips(self, chips) -> None:
        """
        Show the datasets of the scan's file that are curves but no signals, after the
        signals in the field of the curves. Their x asks for :attr:`dataset_removed`, and
        Reset shows while there are any.

        Args:
            chips (Iterable[ChipInfo]): One per dataset, keyed by its :class:`DatasetKey`.
        """
        chips = tuple(chips)
        if chips == self._dataset_chips:
            return
        self._dataset_chips = chips
        self._update_box()

    def dataset_chips(self) -> tuple[ChipInfo, ...]:
        """The chips of the datasets that are curves but no signals, as the box shows them."""
        return self._dataset_chips

    def box_is_default(self) -> bool:
        """Whether Reset has nothing to do: the scan's default, and no dataset on the plot."""
        return self.is_default() and not self._dataset_chips

    def _curves_role(self, letter: str) -> Role:
        chips = tuple(
            ChipInfo(
                key,
                self._signals[key].label,
                auto=self._y_default,
                removable=True,
                swatch=self.swatch_of(key),
                tip=(
                    "Put on the plot by default: the first monitored signal of the scan"
                    if self._y_default
                    else ""
                ),
                problem=self._unread.get(key, ""),
            )
            for key in self._y
        )
        chips += self._dataset_chips
        count = len(chips)
        return Role(
            letter,
            axis=False,
            multi=True,
            caption="",
            chips=chips,
            name=f"The curves on the plot, {count} curve{'' if count == 1 else 's'}",
            hint="Type to add a signal",
            can_be="can be a curve",
            placeholder="Add a signal…",
        )

    def _x_chip(self) -> ChipInfo | None:
        """The x axis of a line plot: the chosen signal, the scan's device, or what the plot
        takes when no listed signal is the axis."""
        if self._x in X_MODES:
            return self._x_mode_chip(self._x)
        if self._y and self._signals[self._y[0]].group == "fast":
            return ChipInfo(None, "sample number", auto=True, tip=ASYNC_NOTE)
        key = self._x if self._x is not None else self._auto_x
        if key in self._signals:
            auto = self._x is None
            return ChipInfo(key, self._signals[key].label, auto=auto, tip=AUTO_TIP if auto else "")
        if self._auto_axis:
            return ChipInfo(None, self._auto_axis, auto=True)
        if self._entry is not None and not self._entry.motors:
            return ChipInfo(None, "point number", auto=True, tip="The scan moved no device")
        return ChipInfo(None, "chosen by the plot", auto=True)

    @staticmethod
    def _x_mode_chip(key: SourceKey) -> ChipInfo:
        name, words = X_MODES[key]
        return ChipInfo(None, name, tip=f"{name}: the {words} on the x axis")

    def _plane_chip(self, key: SourceKey) -> ChipInfo:
        auto = self.axes_are_auto()
        return ChipInfo(key, self._signals[key].label, auto=auto, tip=AUTO_TIP if auto else "")

    def anchors_rows(self) -> bool:
        """
        Whether the rows of the list stay in place when the box above changes its height:
        while the pointer is on the list or a field of the box has the focus.
        """
        if self.tree.viewport().underMouse():
            return True
        focus = QApplication.focusWidget()
        return focus is not None and self.box.isAncestorOf(focus)

    def apply_theme(self) -> None:
        """
        Read the theme's colours: the current row of the list gets the selected tint of the
        scan queue, its text stays in the text colour.
        """
        colors = theme_colors()
        palette = self.tree.palette()
        # The theme draws the list without a background of its own, over the panel's.
        base = colors["bg"]
        tint = QColor(colors["primary"])
        a = ROW_SELECTED_ALPHA
        # Laid over the background, so that every part of a row can fill with it.
        row = QColor(
            round(tint.red() * a + base.red() * (1 - a)),
            round(tint.green() * a + base.green() * (1 - a)),
            round(tint.blue() * a + base.blue() * (1 - a)),
        )
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            palette.setColor(group, QPalette.ColorRole.Highlight, row)
            palette.setColor(group, QPalette.ColorRole.HighlightedText, colors["fg"])
        self.tree.setPalette(palette)
        # The list paints the background of its rows as the scan list does (see drawRow); the
        # theme's style sheet paints none of its own.
        self.tree.setStyleSheet(
            f"QTreeView::item:hover, QTreeView::item:selected,"
            f" QTreeView::item:selected:!active {{ background: transparent;"
            f" color: {css(colors['fg'])}; }}"
            " QTreeView::branch:hover, QTreeView::branch:selected,"
            " QTreeView::branch:selected:!active { background: transparent; }"
            " QTreeView { selection-background-color: transparent; }"
        )
        self._hover = QColor(colors["fg"])
        self._hover.setAlphaF(ROW_HOVER_ALPHA)
        self._row_colors = (row, QColor(colors["fg"]))
        self.box.update()
        self.tree.viewport().update()

    @SafeSlot(str)
    @SafeSlot()
    def _on_theme_changed(self, _theme: str | None = None) -> None:
        self.apply_theme()
        remute(self)
        muted = muted_color()
        for item in self._rows.values():
            item.setForeground(1, muted)
        # Line styles are drawn in the text colour, which the theme changed.
        self._update_box()

    def row_fill(self, key: SourceKey) -> list[QColor]:
        """
        The colours the row of a signal is painted in, as the rows of the scans on the plot in
        the scan list: those of its curves while it is a curve on the plot.

        Args:
            key (SourceKey): (device, entry) of the signal.

        Returns:
            list[QColor]: The colour of its curve for the selected scan, or nothing for a
            signal that is no curve or whose data could not be read.
        """
        if self.picker or self.role_kind("Y") != "curves" or key not in self._y:
            return []
        if self.unread_reason(key) is not None:
            return []
        return [QColor(self.signal_color(key))]

    def ink_of(self, key: SourceKey) -> QColor:
        """
        The colour of the text of a signal's row.

        Args:
            key (SourceKey): (device, entry) of the signal.

        Returns:
            QColor: Black or white on a row in the colour of its curves, else the text colour.
        """
        fills = self.row_fill(key)
        if fills:
            return on_color(mix_colors(fills))
        return QColor(self.row_colors()[1])

    def hover_color(self) -> QColor:
        """The shade of a row under the pointer, as in the scan queue."""
        return self._hover

    def row_colors(self) -> tuple[QColor, QColor]:
        """The tint of the current row, as in the scan queue, and the colour of text."""
        return self._row_colors

    def _hold_top(self) -> None:
        """Keep the box and its notes at their height until the pointer leaves the list."""
        self.top.setMinimumHeight(self.top.height())

    def release_top(self) -> None:
        """Give back the height the box and its notes held while the pointer was on the list."""
        if self.top.minimumHeight():
            self.top.setMinimumHeight(0)

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        if watched is self.tree.viewport() and event.type() in (
            QEvent.Type.Leave,
            QEvent.Type.Hide,
        ):
            self.release_top()
        return super().eventFilter(watched, event)

    def _update_box(self) -> None:
        """Show what the plot shows now in the box on top."""
        if self.picker:
            return
        roles = self.roles()
        letters = list(self.box.fields)
        self.box.set_roles(roles, not self.box_is_default())
        if list(self.box.fields) != letters:
            # Tab goes through the fields, Reset, the filter and the list, in this order.
            chain = [field.edit for field in self.box.fields.values()]
            chain += [self.box.reset_button, self.filter_edit, self.tree]
            for first, second in zip(chain, chain[1:]):
                QWidget.setTabOrder(first, second)
            self.typing.attach()
        elif self.typing.is_open():
            self.typing.refresh()

    def _remove_from_role(self, letter: str, key: SourceKey) -> None:
        """The x of a chip: take a curve off the plot."""
        if isinstance(key, DatasetKey):
            self.dataset_removed.emit(key.path)
            return
        if key is not None and key in self._y:
            self.toggle_y(key)

    def remove_from_role(self, letter: str, key: SourceKey) -> None:
        """
        The x of a chip in another box that shows these fields: as the x of the chip here.

        Args:
            letter (str): The field.
            key (SourceKey): The key of the chip.
        """
        self._remove_from_role(letter, key)

    ################################################################################
    # Typing in the fields of the box
    ################################################################################

    #: What a signal becomes in each kind of role, for the list's messages.
    ROLE_WORDS = {
        "curves": "can be a curve",
        "x": "can be the x axis",
        "y": "can be the y axis",
        "colour": "can colour the map",
    }

    def role_kind(self, letter: str) -> str:
        """
        What a field of the box stands for.

        Args:
            letter (str): ``X``, ``Y`` or ``Z``.

        Returns:
            str: ``x``, ``y`` (the y axis of a map), ``curves``, ``colour`` (of a map) or
            ``none`` (Z in Lines).
        """
        if letter == "X":
            return "x"
        if letter == "Y":
            return "y" if self._two_d and self._map else "curves"
        return "colour" if self._map else "none"

    def _group_title(self, signal: SignalInfo) -> str:
        if signal.key in self._scan_axes:
            return GROUPS["scan"][0]
        return GROUPS.get(signal.box, GROUPS["other"])[0]

    def role_state(self, kind: str, signal: SignalInfo) -> tuple[str, str]:
        """
        Whether a signal can take a role.

        Args:
            kind (str): See :meth:`role_kind`.
            signal (SignalInfo): The signal.

        Returns:
            tuple[str, str]: ``("", "")`` when it can, ``("on", words)`` when it has the role,
            e.g. "on the plot", and ``("off", reason)`` when it cannot, e.g.
            "Async · cannot be an axis".
        """
        group = self._group_title(signal)
        key = signal.key
        point = signal.group == "point"
        if kind in ("x", "y"):
            if signal.group in ("single", "array"):
                return "off", f"{group} · {self._not_drawn(signal)}"
            if not point:
                return "off", f"{group} · cannot be an axis"
            if not self._map and any(self._signals[o].group != "point" for o in self._y):
                # Async curves keep their sample number: no signal is the x axis.
                return "off", f"{group} · not with async curves"
            if self.axis_of(key) == kind:
                return "on", f"the {kind} axis now"
            if self._map and key in self._y:
                return "off", f"{group} · the colour now"
            return "", ""
        if kind == "colour":
            if key in self._y:
                return "on", "the colour now"
            if signal.group == "fast":
                return "off", f"{group} · many values per point"
            if not point:
                return "off", f"{group} · {self._not_drawn(signal)}"
            if self.axis_of(key):
                return "off", f"{group} · an axis of the map"
            return "", ""
        if key in self._y:
            return "on", "on the plot"
        if not signal.plottable:
            return "off", f"{group} · {self._not_drawn(signal)}"
        return "", ""

    @staticmethod
    def _not_drawn(signal: SignalInfo) -> str:
        if signal.group == "single":
            return "one value, see File"
        if signal.group == "array":
            return "an image, see File"
        return "not a curve"

    def _listed_signals(self) -> list[SignalInfo]:
        """The signals in the order of the list: the scan devices, then each group."""
        scan = [self._signals[key] for key in self._scan_axes]
        rest = [s for s in self._signals.values() if s.key not in set(self._scan_axes)]
        order = {group: index for index, group in enumerate(GROUPS)}
        rest.sort(key=lambda s: (order.get(s.box, len(order)), s.group == "array"))
        return scan + rest

    def role_listing(self, letter: str, text: str) -> Listing:
        """
        The list under a field: what fits a typed text, or everything that can take the role.

        Args:
            letter (str): The field, ``X``, ``Y`` or ``Z``.
            text (str): What was typed; empty for the full list.

        Returns:
            Listing: Its lines and the line Enter takes.
        """
        kind = self.role_kind(letter)
        if kind == "none":
            # The field does not apply to the plot shown and takes no typing.
            return Listing((), None)
        can_be = self.ROLE_WORDS[kind]
        signals = self._listed_signals()
        states = {s.key: self.role_state(kind, s) for s in signals}
        modes = list(X_MODES) if kind == "x" else []
        states.update({key: self.x_mode_state(key) for key in modes})
        if not text.strip():
            return self._full_listing(signals, states, can_be, modes)
        fits = []
        # The x modes come first among names that fit as well.
        for position, key in enumerate(modes):
            fit = match(text, X_MODES[key][0])
            if fit is not None:
                fits.append((fit.rank, position - len(modes), key, fit.positions))
        for position, signal in enumerate(signals):
            fit = match(text, signal.label)
            if fit is not None:
                fits.append((fit.rank, position, signal.key, fit.positions))
        fits.sort(key=lambda item: (item[0], item[1]))
        can = [f for f in fits if states[f[2]][0] != "off"]
        cannot = [f for f in fits if states[f[2]][0] == "off"]
        entries = [
            (
                self._x_mode_entry(f[2], f[3], states[f[2]])
                if f[2] in X_MODES
                else self._typed_entry(self._signals[f[2]], f[3], states[f[2]])
            )
            for f in can + cannot
        ]
        if not entries:
            return self._no_fit_listing(text, signals, states)
        mark = next((i for i, e in enumerate(entries) if e.takeable), None)
        return Listing(tuple(entries), mark)

    def _typed_entry(
        self, signal: SignalInfo, positions: tuple[int, ...], state: tuple[str, str]
    ) -> ListEntry:
        shape = format_shape(signal.shape) if signal.shape != (0,) else ""
        group = self._group_title(signal)
        if state[0] == "on":
            right, short = state[1], ""
        elif state[0] == "off":
            right, short = state[1], state[1].split(" · ", 1)[-1]
        else:
            right = f"{group} · {shape}" if shape else group
            short = group
        return ListEntry("entry", signal.label, signal.key, positions, right, short, state=state[0])

    @staticmethod
    def _x_mode_entry(
        key: SourceKey, positions: tuple[int, ...], state: tuple[str, str]
    ) -> ListEntry:
        name, words = X_MODES[key]
        if state[0]:
            right, short = state[1], state[1].split(" · ", 1)[-1]
        else:
            right, short = words, words
        return ListEntry("entry", name, key, positions, right, short, state=state[0])

    def _full_listing(self, signals, states, can_be: str, modes: list[SourceKey] = ()) -> Listing:
        entries: list[ListEntry] = []
        # The x modes of Lines stand above the signals, in a group of their own.
        modes = [key for key in modes if states[key][0] != "off"]
        if modes:
            entries.append(ListEntry("head", X_MODES_TITLE, count=len(modes)))
            entries += [self._x_mode_entry(key, (), states[key]) for key in modes]
        groups: dict[str, list[SignalInfo]] = {}
        for signal in signals:
            if states[signal.key][0] != "off":
                groups.setdefault(self._group_title(signal), []).append(signal)
        for title, members in groups.items():
            entries.append(ListEntry("head", title, count=len(members)))
            for signal in members:
                state = states[signal.key]
                shape = format_shape(signal.shape) if signal.shape != (0,) else ""
                right = state[1] if state[0] == "on" else shape
                entries.append(
                    ListEntry("entry", signal.label, signal.key, (), right, state=state[0])
                )
        count = sum(len(members) for members in groups.values())
        if not count and not modes:
            return Listing((ListEntry("message", self._why_none(can_be), strong=True),), None)
        return Listing(tuple(entries), None)

    def _why_none(self, can_be: str) -> str:
        """One line on why no signal can take a role."""
        if can_be.startswith("can be the") and any(
            self._signals[o].group != "point" for o in self._y
        ):
            return f"No signal {can_be} while async curves are on the plot"
        return f"No signal of this scan {can_be}"

    def _no_fit_listing(self, text: str, signals, states) -> Listing:
        typed = text.strip()
        entries = [
            ListEntry("message", f"No signal of this scan fits “{typed}”", strong=True),
            ListEntry("message", "The File tab lists everything the file holds."),
        ]
        by_label = {}
        for signal in signals:
            if states[signal.key][0] != "off":
                by_label.setdefault(signal.label, signal)
        close = [by_label[name] for name in close_names(typed, list(by_label))]
        if not close:
            return Listing(tuple(entries), None)
        entries.append(ListEntry("head", "Similar names", count=len(close)))
        entries += [self._typed_entry(s, (), states[s.key]) for s in close]
        return Listing(tuple(entries), None)

    def take_role(self, letter: str, key: SourceKey) -> None:
        """
        Give a signal the role of a field, as chosen in its list.

        Args:
            letter (str): The field, ``X``, ``Y`` or ``Z``.
            key (SourceKey): (device, entry) of the signal.
        """
        kind = self.role_kind(letter)
        if key in X_MODES:
            if kind == "x" and self.x_mode_state(key)[0] == "":
                self.toggle_x(key)
            return
        signal = self._signals.get(key)
        if kind == "none" or signal is None or self.role_state(kind, signal)[0] != "":
            return
        if kind == "x":
            self.toggle_x(key)
        elif kind == "y":
            self.toggle_y_axis(key)
        else:
            self.toggle_y(key)

    ################################################################################
    # Internals
    ################################################################################

    def _plottable(self, key: SourceKey) -> bool:
        return key in self._signals and self._signals[key].plottable

    @staticmethod
    def _default_y(entry: ScanEntry | None, signals: list[SignalInfo]) -> SourceKey | None:
        """
        The first signal by name with one value per point that is not a scanned motor, as
        BEC's live plot takes the first monitored device. A motor alone is no default: it
        would be drawn against itself.
        """
        motors = set(entry.motors) if entry is not None else set()
        for signal in signals:
            if signal.group == "point" and signal.device not in motors:
                return signal.key
        return None

    def has_default(self) -> bool:
        """
        Whether the scan has a signal to show by default.

        Returns:
            bool: False when it stored nothing per point but its motors.
        """
        return self._default_y(self._entry, list(self._signals.values())) is not None

    def _layout_of(self, signals: list[SignalInfo]) -> tuple:
        """What decides the rows of the list: their keys, boxes, names and icons."""
        return (
            tuple(self._scan_axes),
            self._by_shape,
            tuple(
                (
                    signal.key,
                    signal.box,
                    signal.group,
                    signal.label,
                    signal.group == "array" and self._shows_frames(signal),
                )
                for signal in signals
            ),
        )

    def _update_rows(self) -> None:
        """Give the kept rows the signals of the listed scan: their shapes and dtypes."""
        for key, item in self._rows.items():
            signal = self._signals[key]
            if item.data(0, SIGNAL_ROLE) == signal:
                continue
            item.setData(0, SIGNAL_ROLE, signal)
            length = format_shape(signal.shape) if signal.shape != (0,) else ""
            if item.text(1) != length:
                item.setText(1, length)
                self._length = None
            item.setToolTip(0, self._row_tip(signal))

    def _row_tip(self, signal: SignalInfo) -> str:
        tip = f"{signal.device} / {signal.entry}  ·  {signal.dtype}"
        if signal.group == "array":
            frames = self._shows_frames(signal)
            tip += "  ·  an image per reading" if frames else "  ·  a spectrum per reading"
        return tip

    def _rebuild(self, signals: list[SignalInfo]) -> None:
        layout = self._layout_of(signals)
        if layout == self._layout and self._rows:
            self._update_rows()
            self._update_scan_rows()
            self._apply_filter(self.filter_edit.text(), note=False)
            self.fit_columns()
            return
        self._layout = layout
        self._rows = {}
        self.tree.clear()
        self._filtered = False
        self._scan_head = None
        scan_keys = set(self._scan_axes)
        # The theme's colours are read once per rebuild, not once per row.
        muted = muted_color()
        for group, (title, tip) in GROUPS.items():
            if group == "scan":
                members = [self._signals[key] for key in self._scan_axes]
            else:
                # Single numbers first, then the images and spectra of the readout group.
                members = sorted(
                    (
                        signal
                        for signal in signals
                        if signal.box == group and signal.key not in scan_keys
                    ),
                    key=lambda signal: signal.group == "array",
                )
            if not members:
                continue
            head = QTreeWidgetItem(self.tree, [f"{title}  ({len(members)})", "", ""])
            head.setData(0, HEAD_ROLE, (title, len(members)))
            head.setFirstColumnSpanned(True)
            head.setFlags(Qt.ItemFlag.ItemIsEnabled)
            head.setToolTip(0, f"{tip}\n{SHAPE_GROUPING_NOTE}" if self._by_shape else tip)
            font = head.font(0)
            font.setWeight(QFont.Weight.DemiBold)
            head.setFont(0, font)
            if group == "scan":
                self._scan_head = head
            for signal in members:
                shape = format_shape(signal.shape) if signal.shape != (0,) else ""
                item = QTreeWidgetItem(head, [signal.label, shape, ""])
                item.setData(0, SIGNAL_ROLE, signal)
                self._rows[signal.key] = item
                if signal.group == "array":
                    frames = self._shows_frames(signal)
                    item.setIcon(
                        0,
                        material_icon(
                            "image" if frames else "show_chart",
                            size=(16, 16),
                            convert_to_pixmap=False,
                        ),
                    )
                item.setToolTip(0, self._row_tip(signal))
                item.setTextAlignment(
                    1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                item.setForeground(1, muted)
            head.setData(0, BOX_ROLE, group)
            # The long lists of single values start closed, unless the user opened them.
            default = group not in ("single", "other") or len(members) <= 12
            self._set_open(head, self._box_open.get(group, default))
        # Measured once the rows are all there: a resize while they are made measures fewer.
        self._length = None
        self._update_scan_rows()
        self._apply_filter(self.filter_edit.text(), note=False)
        self.fit_columns()

    @staticmethod
    def _shows_frames(signal: SignalInfo) -> bool:
        """Whether each reading of an image or spectrum signal is an image."""
        return len(signal.shape) >= 3 and min(signal.shape[-2:]) > 1

    def _update_scan_rows(self) -> None:
        """Mark the scan devices whose axis the list chose."""
        head = self._scan_head
        if head is None:
            return
        auto = self.axes_are_auto()
        muted = muted_color()
        highlight = QColor(self.palette().color(QPalette.ColorRole.Highlight))
        for row in range(head.childCount()):
            item = head.child(row)
            signal: SignalInfo = item.data(0, SIGNAL_ROLE)
            shape = format_shape(signal.shape) if signal.shape != (0,) else ""
            marked = auto and bool(self.axis_of(signal.key))
            # A running scan has no length yet: the mark stands alone.
            length = (f"auto  ·  {shape}" if shape else "auto") if marked else shape
            if item.text(1) != length:
                item.setText(1, length)
                self._length = None
            tip = AUTO_TIP if marked else f"{signal.device} / {signal.entry}  ·  {signal.dtype}"
            item.setToolTip(0, tip)
            item.setToolTip(1, tip)
            item.setForeground(1, highlight if marked else muted)

    def _set_open(self, head: QTreeWidgetItem, open_: bool) -> None:
        """Open or close a box for the user, without taking it for the user's choice."""
        self._opening = True
        try:
            head.setExpanded(open_)
        finally:
            self._opening = False

    def _on_box_toggled(self, item: QTreeWidgetItem, open_: bool) -> None:
        box = item.data(0, BOX_ROLE)
        if box and not self._opening:
            self._box_open[box] = open_

    def fit_columns(self) -> None:
        """
        Give the names their room: the length beside them hides once a name could not show
        :data:`NAME_KEEPS` letters, and comes back when the panel is wide enough again.
        """
        tree = self.tree
        metrics = QFontMetrics(tree.font())
        keep = metrics.averageCharWidth() * NAME_KEEPS
        if self._length is None:
            # Measured from the texts once per change of the lengths, not on every resize or
            # scan; the texts are there also while the column is hidden or not laid out yet.
            self._length = self.length_width()
        length = self._length
        room = tree.viewport().width() - tree.header().sectionSize(2) - tree.indentation() - 16
        hide = room - length < keep
        if tree.isColumnHidden(1) != hide:
            tree.setColumnHidden(1, hide)

    def length_width(self) -> int:
        """
        The width the lengths beside the names need: the widest of them with the margins of
        a cell.

        Returns:
            int: Width in pixels, 0 without lengths.
        """
        metrics = QFontMetrics(self.tree.font())
        widest = max(
            (metrics.horizontalAdvance(item.text(1)) for item in self._rows.values()), default=0
        )
        if not widest:
            return 0
        margin = self.tree.style().pixelMetric(
            QStyle.PixelMetric.PM_FocusFrameHMargin, None, self.tree
        )
        return widest + 2 * (margin + 1)

    def _apply_filter(self, text: str, note: bool = True) -> None:
        """Show the signals whose name fits the text, as the fields of the box find them,
        with the matched letters marked.

        Args:
            text (str): The text of the filter.
            note (bool): Whether to bring the box and the note up to date, False where the
                caller does that after.
        """
        typed = bool(text.strip())
        total = 0
        if not typed and not self._filtered:
            # Every row shows already and nothing is marked.
            self.filter_empty.setVisible(False)
            self.tree.setVisible(True)
            if note:
                self._update_note()
            return
        self._filtered = typed
        for row in range(self.tree.topLevelItemCount()):
            head = self.tree.topLevelItem(row)
            shown = 0
            for child_row in range(head.childCount()):
                child = head.child(child_row)
                signal: SignalInfo = child.data(0, SIGNAL_ROLE)
                fit = match(text, signal.label) if typed else None
                visible = not typed or fit is not None
                child.setData(0, MATCH_ROLE, fit.positions if fit is not None else ())
                child.setHidden(not visible)
                shown += visible
            head.setHidden(shown == 0)
            total += shown
            if typed and shown:
                self._set_open(head, True)
        empty = typed and total == 0 and bool(self._signals)
        if empty:
            self.filter_empty_text.setText(f"No signal of this scan fits “{text.strip()}”.")
        self.filter_empty.setVisible(empty)
        self.tree.setVisible(not empty)
        if note:
            self._update_note()

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """A click on a group's header opens or closes the group."""
        if item.data(0, HEAD_ROLE) is not None:
            item.setExpanded(not item.isExpanded())

    def head_follows_rows(self, index: QModelIndex) -> bool:
        """
        Whether a group's header has a shown group above it, and so room and a line above.

        Args:
            index (QModelIndex): The header's index in the tree.

        Returns:
            bool: False for the first group shown.
        """
        for row in range(index.row()):
            if not self.tree.topLevelItem(row).isHidden():
                return True
        return False

    def _on_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        signal: SignalInfo | None = item.data(0, SIGNAL_ROLE)
        if signal is None or column == 2:
            return
        if signal.plottable:
            self.toggle_y(signal.key)
        else:
            self.open_requested.emit(signal)

    def group_of(self, key: SourceKey) -> str:
        """
        The group of a listed signal.

        Args:
            key (SourceKey): (device, entry) of the signal.

        Returns:
            str: ``point``, ``fast``, ``array`` or ``single``, or empty when it is not listed.
        """
        signal = self._signals.get(key)
        return signal.group if signal is not None else ""

    def _changed(self) -> None:
        self._refusal = ""
        self._remember()
        self.tree.viewport().update()
        self._update_scan_rows()
        self._update_note()
        self.selection_changed.emit()

    def _update_note(self) -> None:
        """Bring the box up to date and say under it what it does not show."""
        self._update_box()
        self.note.setText(self._note_text())
        self.note.setVisible(bool(self.note.text()))

    def _note_text(self) -> str:
        """
        A note about the plot: why a choice was refused, how async signals are drawn, or
        what to do with an empty list. What the plot shows is in the box, not here.
        """
        if self._entry is None:
            return "Pick a scan to see its signals."
        if not self._signals:
            return "This scan's history entry lists no stored signals."
        if self._refusal:
            return self._refusal
        if self.picker:
            count = len(self._y)
            if not count:
                return "Press Y on a signal to add it to the plot."
            return f"{'1 signal' if count == 1 else f'{count} signals'} of this scan on the plot"
        if not self._y:
            if self._map:
                return "Press Z on a signal to colour the map by it."
            return "Press Y on a signal to plot it."
        if not self._map and self._signals[self._y[0]].group == "fast":
            return ASYNC_NOTE
        return ""
