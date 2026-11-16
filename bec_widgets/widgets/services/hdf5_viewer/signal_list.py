"""
The signals of a scan, grouped by what can be plotted against what.

The list is built from what the scan history says about the stored data; no file is opened
to show it. A signal is put on the plot with its Y button and chosen as the x axis with
its X button. Images and single values open in the file view.
"""

from __future__ import annotations

from dataclasses import dataclass

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent, QModelIndex, QRect, QSize, Qt, Signal
from qtpy.QtGui import QColor, QFont, QPainter, QPalette
from qtpy.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QLineEdit,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.widgets.services.hdf5_viewer.h5_reader import format_shape
from bec_widgets.widgets.services.hdf5_viewer.scan_list import ScanEntry

SIGNAL_ROLE = Qt.ItemDataRole.UserRole + 1

SourceKey = tuple[str, str]

#: The groups, in the order they are listed, with their title and what they mean.
GROUPS = {
    "point": ("One value per scan point", "Can be plotted against each other"),
    "fast": ("Fast signals", "Recorded at their own rate, plotted against their sample number"),
    "array": ("Images and spectra", "Open in the file view"),
    "single": ("Single values", "Recorded once for the scan, open in the file view"),
}


@dataclass(frozen=True)
class SignalInfo:
    """One stored signal of a scan."""

    device: str
    entry: str
    shape: tuple[int, ...]
    dtype: str
    group: str

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


def signals_of(entry: ScanEntry, kinds: dict[SourceKey, str] | None = None) -> list[SignalInfo]:
    """
    List the stored signals of a scan.

    Args:
        entry (ScanEntry): The scan.
        kinds (dict[SourceKey, str] | None): Kind of each signal as told by the Data API.

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
            out.append(
                SignalInfo(device, name, shape, dtype, classify(shape, entry.num_points, kind))
            )
    return out


class _ChipDelegate(QStyledItemDelegate):
    """Draws the X and Y buttons of a signal, or its Open button."""

    CHIP = QSize(24, 20)
    GAP = 4

    def __init__(self, owner: SignalList):
        super().__init__(owner.tree)
        self._owner = owner

    def chip_rects(self, rect: QRect) -> tuple[QRect, QRect]:
        """
        Where the two buttons of a row are.

        Args:
            rect (QRect): Rectangle of the cell.

        Returns:
            tuple[QRect, QRect]: Rectangle of the X and of the Y button.
        """
        top = rect.center().y() - self.CHIP.height() // 2
        y_rect = QRect(
            rect.right() - 4 - self.CHIP.width(), top, self.CHIP.width(), self.CHIP.height()
        )
        x_rect = y_rect.translated(-(self.CHIP.width() + self.GAP), 0)
        return x_rect, y_rect

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(2 * self.CHIP.width() + self.GAP + 10, self.CHIP.height() + 6)

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
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            painter.fillRect(option.rect, option.palette.highlight())
        if signal is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ink = option.palette.color(
            QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        )
        font = QFont(option.font)
        font.setWeight(QFont.Weight.DemiBold)
        font.setPointSizeF(option.font.pointSizeF() * 0.9)
        painter.setFont(font)
        x_rect, y_rect = self.chip_rects(option.rect)
        if not signal.plottable:
            open_rect = x_rect.united(y_rect)
            self._draw_chip(painter, open_rect, "Open", None, ink)
            painter.restore()
            return
        owner = self._owner
        on = QColor("#ffffff")
        x_on = owner.x_signal() == signal.key
        x_fill = QColor(ink) if x_on else None
        x_ink = QColor("#000000" if ink.lightness() > 128 else "#ffffff") if x_on else ink
        self._draw_chip(painter, x_rect, "X", x_fill, x_ink, enabled=signal.group == "point")
        y_on = signal.key in owner.y_signals()
        y_color = owner.signal_color(signal.key)
        y_fill = QColor(y_color) if y_on else None
        self._draw_chip(painter, y_rect, "Y", y_fill, on if y_on else ink)
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:
        if event.type() != QEvent.Type.MouseButtonRelease:
            return super().editorEvent(event, model, option, index)
        signal: SignalInfo | None = index.sibling(index.row(), 0).data(SIGNAL_ROLE)
        if signal is None:
            return False
        x_rect, y_rect = self.chip_rects(option.rect)
        position = event.position().toPoint()
        if not signal.plottable:
            if x_rect.united(y_rect).contains(position):
                self._owner.open_requested.emit(signal)
                return True
            return False
        if x_rect.contains(position):
            self._owner.toggle_x(signal.key)
            return True
        if y_rect.contains(position):
            self._owner.toggle_y(signal.key)
            return True
        return False

    def helpEvent(self, event, view, option, index) -> bool:
        signal: SignalInfo | None = index.sibling(index.row(), 0).data(SIGNAL_ROLE)
        if signal is None:
            return super().helpEvent(event, view, option, index)
        x_rect, y_rect = self.chip_rects(option.rect)
        if not signal.plottable:
            text = "Open in the file view (Enter)"
        elif x_rect.contains(event.pos()):
            text = (
                "Use as the x axis (X)"
                if signal.group == "point"
                else "Fast signals are plotted against their sample number"
            )
        elif y_rect.contains(event.pos()):
            text = "Show on the plot (Y)"
        else:
            return super().helpEvent(event, view, option, index)
        QToolTip.showText(event.globalPos(), text, view)
        return True


class _SignalTree(QTreeWidget):
    """Tree that toggles the buttons of the current signal with the X, Y and Enter keys."""

    def __init__(self, owner: SignalList):
        super().__init__(owner)
        self._owner = owner

    def keyPressEvent(self, event):
        item = self.currentItem()
        signal: SignalInfo | None = item.data(0, SIGNAL_ROLE) if item is not None else None
        if signal is not None:
            if event.key() == Qt.Key.Key_Y and signal.plottable:
                self._owner.toggle_y(signal.key)
                return
            if event.key() == Qt.Key.Key_X and signal.plottable:
                self._owner.toggle_x(signal.key)
                return
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                if signal.plottable:
                    self._owner.toggle_y(signal.key)
                else:
                    self._owner.open_requested.emit(signal)
                return
        super().keyPressEvent(event)


class SignalList(QWidget):
    """The stored signals of the selected scan, with X and Y buttons."""

    #: The signals on the plot or the x axis changed.
    selection_changed = Signal()
    #: A signal that cannot be plotted should be opened in the file view.
    open_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._signals: dict[SourceKey, SignalInfo] = {}
        self._y: list[SourceKey] = []
        self._x: SourceKey | None = None
        self._colors: dict[SourceKey, str] = {}
        self._default_color = "#2a78d6"
        self._entry: ScanEntry | None = None

        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText("Filter signals")
        self.filter_edit.setAccessibleName("Filter signals")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.addAction(
            material_icon("filter_list", size=(16, 16), convert_to_pixmap=False),
            QLineEdit.ActionPosition.LeadingPosition,
        )

        self.tree = _SignalTree(self)
        self.tree.setColumnCount(3)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(8)
        self.tree.setUniformRowHeights(True)
        self.tree.setMouseTracking(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setAccessibleName("Signals of the scan")
        self._delegate = _ChipDelegate(self)
        self.tree.setItemDelegateForColumn(2, self._delegate)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 66)
        header.setMinimumSectionSize(40)

        self.note = QLabel(self)
        self.note.setWordWrap(True)
        self.note.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self.note.setContentsMargins(6, 2, 6, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.filter_edit)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.note)

        self.filter_edit.textChanged.connect(self._apply_filter)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self._update_note()

    ################################################################################
    # Public interface
    ################################################################################

    def set_scan(self, entry: ScanEntry | None, kinds: dict[SourceKey, str] | None = None):
        """
        List the signals of a scan. Signals that were on the plot stay on it when the new
        scan has them too.

        Args:
            entry (ScanEntry | None): The scan, or None to empty the list.
            kinds (dict[SourceKey, str] | None): Kind of each signal as told by the Data API.
        """
        self._entry = entry
        signals = signals_of(entry, kinds) if entry is not None else []
        self._signals = {signal.key: signal for signal in signals}
        self._y = [key for key in self._y if self._plottable(key)]
        if self._x is not None and not (
            self._x in self._signals and self._signals[self._x].group == "point"
        ):
            self._x = None
        if not self._y:
            # Nothing of the last plot exists in this scan: start with its first detector.
            default = self._default_y(entry, signals)
            if default is not None:
                self._y = [default]
        self._rebuild(signals)
        self._update_note()
        self.selection_changed.emit()

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

    def x_signal(self) -> SourceKey | None:
        """
        The signal chosen as the x axis.

        Returns:
            SourceKey | None: (device, entry), or None when the plot chooses the axis.
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
        if key in self._y:
            self._y.remove(key)
        else:
            group = self._signals[key].group
            self._y = [other for other in self._y if self._signals[other].group == group]
            self._y.append(key)
            if group != "point":
                self._x = None
        self._changed()

    def toggle_x(self, key: SourceKey) -> None:
        """
        Choose a signal as the x axis, or go back to the axis the plot chooses.

        Args:
            key (SourceKey): (device, entry) of a signal with one value per scan point.
        """
        signal = self._signals.get(key)
        if signal is None or signal.group != "point":
            return
        self._x = None if self._x == key else key
        if self._x is not None:
            self._y = [other for other in self._y if self._signals[other].group == "point"]
        self._changed()

    def set_colors(self, colors: dict[SourceKey, str], default: str) -> None:
        """
        Tell the list in which colour each signal is drawn, so that its Y button matches.

        Args:
            colors (dict[SourceKey, str]): Colour per signal on the plot.
            default (str): Colour of a signal that has none of its own.
        """
        self._colors = dict(colors)
        self._default_color = default
        self.tree.viewport().update()

    def signal_color(self, key: SourceKey) -> str:
        """
        Colour of the Y button of a signal.

        Args:
            key (SourceKey): (device, entry) of the signal.

        Returns:
            str: Colour as ``#rrggbb``.
        """
        return self._colors.get(key, self._default_color)

    ################################################################################
    # Internals
    ################################################################################

    def _plottable(self, key: SourceKey) -> bool:
        return key in self._signals and self._signals[key].plottable

    @staticmethod
    def _default_y(entry: ScanEntry | None, signals: list[SignalInfo]) -> SourceKey | None:
        """The first signal with one value per point that is not a scanned motor."""
        motors = set(entry.motors) if entry is not None else set()
        points = [signal for signal in signals if signal.group == "point"]
        for signal in points:
            if signal.device not in motors:
                return signal.key
        return points[0].key if points else None

    def _rebuild(self, signals: list[SignalInfo]) -> None:
        self.tree.clear()
        for group, (title, tip) in GROUPS.items():
            members = [signal for signal in signals if signal.group == group]
            if not members:
                continue
            head = QTreeWidgetItem(self.tree, [f"{title}  ({len(members)})", "", ""])
            head.setFirstColumnSpanned(True)
            head.setFlags(Qt.ItemFlag.ItemIsEnabled)
            head.setToolTip(0, tip)
            font = head.font(0)
            font.setWeight(QFont.Weight.DemiBold)
            head.setFont(0, font)
            for signal in members:
                shape = format_shape(signal.shape) if signal.shape != (0,) else ""
                item = QTreeWidgetItem(head, [signal.label, shape, ""])
                item.setData(0, SIGNAL_ROLE, signal)
                item.setToolTip(0, f"{signal.device} / {signal.entry}  ·  {signal.dtype}")
                item.setTextAlignment(
                    1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                item.setForeground(1, self.palette().brush(QPalette.ColorRole.PlaceholderText))
            # The long lists of single values start closed.
            head.setExpanded(group != "single" or len(members) <= 12)
        self._apply_filter(self.filter_edit.text())

    def _apply_filter(self, text: str) -> None:
        words = text.lower().split()
        for row in range(self.tree.topLevelItemCount()):
            head = self.tree.topLevelItem(row)
            shown = 0
            for child_row in range(head.childCount()):
                child = head.child(child_row)
                signal: SignalInfo = child.data(0, SIGNAL_ROLE)
                haystack = f"{signal.device} {signal.entry}".lower()
                visible = all(word in haystack for word in words)
                child.setHidden(not visible)
                shown += visible
            head.setHidden(shown == 0)
            if words and shown:
                head.setExpanded(True)
        self._update_note()

    def _on_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        signal: SignalInfo | None = item.data(0, SIGNAL_ROLE)
        if signal is None or column == 2:
            return
        if signal.plottable:
            self.toggle_y(signal.key)
        else:
            self.open_requested.emit(signal)

    def _changed(self) -> None:
        self.tree.viewport().update()
        self._update_note()
        self.selection_changed.emit()

    def _update_note(self) -> None:
        if self._entry is None:
            self.note.setText("Pick a scan to see its signals.")
            return
        if not self._signals:
            self.note.setText("This scan's history entry lists no stored signals.")
            return
        hidden = self.filter_edit.text().strip() and all(
            self.tree.topLevelItem(row).isHidden() for row in range(self.tree.topLevelItemCount())
        )
        if hidden:
            self.note.setText("No signal fits the filter.")
            return
        if not self._y:
            self.note.setText("Press Y on a signal to plot it.")
            return
        if self._x is not None:
            axis = self._signals[self._x].label
        elif self._signals[self._y[0]].group == "fast":
            axis = "sample number"
        else:
            axis = "chosen by the plot"
        count = "1 signal" if len(self._y) == 1 else f"{len(self._y)} signals"
        self.note.setText(f"{count} on the plot  ·  x axis: {axis}")
