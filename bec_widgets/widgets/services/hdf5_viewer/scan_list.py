"""
The list of scans of the HDF5 viewer.

The list is filled from the scan history that BEC keeps in memory; no file is opened to
show it. Scans can be searched, filtered by how they ended and pinned for comparison.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

from bec_qthemes import material_icon
from qtpy.QtCore import (
    QAbstractListModel,
    QEvent,
    QModelIndex,
    QPoint,
    QRect,
    QRectF,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    Signal,
)
from qtpy.QtGui import QColor, QFont, QFontMetrics, QPainter, QPalette, QPen
from qtpy.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import get_theme_name
from bec_widgets.widgets.progress.stage_bar import Tone
from bec_widgets.widgets.services.hdf5_viewer.style import (
    control_key_name,
    mute,
    muted_color,
    tone_color,
)

ENTRY_ROLE = Qt.ItemDataRole.UserRole + 1

#: Colours of the scans in a comparison, for the light and the dark theme.
SERIES_COLORS = {
    "light": [
        "#2a78d6",
        "#eb6834",
        "#1baf7a",
        "#eda100",
        "#e87ba4",
        "#008300",
        "#6250d6",
        "#e34948",
    ],
    "dark": [
        "#3987e5",
        "#d95926",
        "#199e70",
        "#c98500",
        "#d55181",
        "#0ca30c",
        "#9085e9",
        "#e66767",
    ],
}
#: How a scan ended, in words. A scan that ran to its end carries no label.
#: The words and tones of the scan queue for how a scan ended or what it is doing.
STATUS_LABELS = {
    "open": "Running",
    "paused": "Paused",
    "aborted": "Aborted",
    "halted": "Halted",
    "user_completed": "Finished early",
}
#: How long a message stays in the note under the list.
NOTE_FLASH_MS = 3000
STATUS_TONES = {
    "open": Tone.RUN,
    "paused": Tone.WARN,
    "aborted": Tone.BAD,
    "halted": Tone.BAD,
    "user_completed": Tone.ACCENT,
}


def series_color(slot: int) -> str:
    """
    Colour of the n-th scan or signal of a plot in the current theme.

    Args:
        slot (int): Position in the palette; it repeats after eight.

    Returns:
        str: Colour as ``#rrggbb``.
    """
    palette = SERIES_COLORS["dark" if get_theme_name() == "dark" else "light"]
    return palette[slot % len(palette)]


def format_duration(seconds: float) -> str:
    """
    Readable length of time.

    Args:
        seconds (float): Number of seconds.

    Returns:
        str: For example ``"48 s"``, ``"3 min 12 s"`` or ``"2 h 05 min"``.
    """
    seconds = max(0, int(round(seconds)))
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min {seconds % 60:02d} s"
    return f"{seconds // 3600} h {seconds % 3600 // 60:02d} min"


def format_when(timestamp: float, now: float | None = None, full: bool = False) -> str:
    """
    Readable point in time: the clock time for today, the date with it otherwise.

    Args:
        timestamp (float): Seconds since the epoch.
        now (float | None): Current time, for tests.
        full (bool): Always give the date and the time, e.g. to tell apart scans that share
            a number.

    Returns:
        str: For example ``"14:32"`` or ``"12 Nov 14:32"``.
    """
    if not timestamp:
        return ""
    when = datetime.fromtimestamp(timestamp)
    today = datetime.fromtimestamp(time.time() if now is None else now)
    if full:
        fmt = "%d %b %H:%M" if when.year == today.year else "%d %b %Y %H:%M"
        return when.strftime(fmt).lstrip("0")
    if when.date() == today.date():
        return when.strftime("%H:%M")
    if when.year == today.year:
        return when.strftime("%d %b %H:%M").lstrip("0")
    return when.strftime("%d %b %Y").lstrip("0")


@dataclass
class ScanEntry:
    """What the viewer knows about one scan, taken from its history or status message."""

    scan_id: str
    scan_number: int | None = None
    scan_name: str = ""
    status: str = "closed"
    start_time: float = 0.0
    end_time: float = 0.0
    num_points: int | None = None
    file_path: str = ""
    motors: tuple[str, ...] = ()
    stored_data_info: dict = field(default_factory=dict)
    #: How each signal is keyed, where the status message of a running scan tells.
    signal_kinds: dict = field(default_factory=dict)
    live: bool = False

    @classmethod
    def from_history(cls, msg: dict) -> ScanEntry:
        """
        Build an entry from a dumped ``ScanHistoryMessage``.

        Args:
            msg (dict): The message content.

        Returns:
            ScanEntry: The entry.
        """
        inputs = msg.get("request_inputs") or {}
        bundle = inputs.get("arg_bundle") or []
        motors = tuple(dict.fromkeys(arg for arg in bundle if isinstance(arg, str)))
        return cls(
            scan_id=msg["scan_id"],
            scan_number=msg.get("scan_number"),
            scan_name=msg.get("scan_name") or "",
            status=msg.get("exit_status") or "closed",
            start_time=float(msg.get("start_time") or 0.0),
            end_time=float(msg.get("end_time") or 0.0),
            num_points=msg.get("num_points"),
            file_path=msg.get("file_path") or "",
            motors=motors,
            stored_data_info=msg.get("stored_data_info") or {},
        )

    @property
    def title(self) -> str:
        """Scan number and name, as shown in the list and above the plot."""
        number = f"{self.scan_number}" if self.scan_number is not None else "?"
        return f"{number}  {self.scan_name}".rstrip()

    @property
    def ended_early(self) -> bool:
        """Whether the scan was stopped, halted or ended by the user before its end."""
        return self.status in ("aborted", "halted", "user_completed")

    def summary(self) -> str:
        """
        One line about the scan: what moved, how many points, how long.

        Returns:
            str: For example ``"samx  ·  200 points  ·  1 min 12 s"``.
        """
        return "  ·  ".join(self.summary_parts())

    def summary_parts(self) -> list[str]:
        """
        The parts of :meth:`summary`, the most important first.

        Returns:
            list[str]: For example ``["samx", "200 points", "1 min 12 s"]``.
        """
        parts = []
        if self.motors:
            parts.append(", ".join(self.motors[:3]) + ("…" if len(self.motors) > 3 else ""))
        if self.num_points:
            parts.append("1 point" if self.num_points == 1 else f"{self.num_points} points")
        if self.end_time and self.start_time and not self.live:
            parts.append(format_duration(self.end_time - self.start_time))
        return parts

    def matches(self, text: str) -> bool:
        """
        Whether the scan fits a search text.

        Args:
            text (str): Words to look for in the number, the name and the motors.

        Returns:
            bool: True when every word is found.
        """
        haystack = " ".join([str(self.scan_number), self.scan_name, *self.motors]).lower()
        return all(word in haystack for word in text.lower().split())


class ScanListModel(QAbstractListModel):
    """Scans, the newest first, with the colour of the pinned ones."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[ScanEntry] = []
        self._pins: dict[str, int] = {}
        #: Scan numbers listed more than once, worked out when first needed.
        self._repeated: set | None = None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        entry = self._entries[index.row()]
        if role == ENTRY_ROLE:
            return entry
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
            status = STATUS_LABELS.get(entry.status, "")
            pinned = "pinned" if entry.scan_id in self._pins else ""
            return ", ".join(
                part for part in (f"Scan {entry.title}", entry.summary(), status, pinned) if part
            )
        if role == Qt.ItemDataRole.ToolTipRole:
            if self.is_repeated(entry):
                started = format_when(entry.start_time, full=True)
                lines = [f"Scan {entry.scan_number}, started {started}", f"Scan id {entry.scan_id}"]
                return "\n".join([*lines, entry.file_path] if entry.file_path else lines)
            return entry.file_path or None
        return None

    def is_repeated(self, entry: ScanEntry) -> bool:
        """
        Whether another listed scan has the same number. Scan numbers can repeat, e.g. after a
        counter reset; the scan id is what tells scans apart.

        Args:
            entry (ScanEntry): The scan.

        Returns:
            bool: True when its number is listed more than once.
        """
        if self._repeated is None:
            seen: set = set()
            self._repeated = set()
            for other in self._entries:
                if other.scan_number in seen:
                    self._repeated.add(other.scan_number)
                seen.add(other.scan_number)
        return entry.scan_number is not None and entry.scan_number in self._repeated

    def scan_label(self, entry: ScanEntry) -> str:
        """
        How a scan is named in texts: its number, with its start time when the number is listed
        more than once.

        Args:
            entry (ScanEntry): The scan.

        Returns:
            str: For example ``"11"`` or ``"11 (14 Nov 09:12)"``.
        """
        number = f"{entry.scan_number}" if entry.scan_number is not None else "?"
        if self.is_repeated(entry):
            return f"{number} ({format_when(entry.start_time, full=True)})"
        return number

    def set_entries(self, entries: list[ScanEntry]) -> None:
        """
        Replace all scans.

        Args:
            entries (list[ScanEntry]): The scans in any order.
        """
        self.beginResetModel()
        self._entries = sorted(entries, key=self._sort_key, reverse=True)
        self._repeated = None
        known = {entry.scan_id for entry in self._entries}
        self._pins = {scan_id: slot for scan_id, slot in self._pins.items() if scan_id in known}
        self.endResetModel()

    @staticmethod
    def _sort_key(entry: ScanEntry) -> tuple:
        return (entry.live, entry.start_time, entry.scan_number or 0)

    def upsert(self, entry: ScanEntry) -> None:
        """
        Add a scan or replace the entry with the same scan id.

        Args:
            entry (ScanEntry): The scan.
        """
        for row, existing in enumerate(self._entries):
            if existing.scan_id == entry.scan_id:
                self._entries[row] = entry
                self._repeated = None
                index = self.index(row)
                self.dataChanged.emit(index, index)
                return
        row = 0
        key = self._sort_key(entry)
        while row < len(self._entries) and self._sort_key(self._entries[row]) > key:
            row += 1
        self.beginInsertRows(QModelIndex(), row, row)
        self._repeated = None
        self._entries.insert(row, entry)
        self.endInsertRows()
        if self.is_repeated(entry):
            # The other scans with this number now show their date too.
            self.dataChanged.emit(self.index(0), self.index(len(self._entries) - 1))

    def remove(self, scan_id: str) -> None:
        """
        Remove a scan.

        Args:
            scan_id (str): Id of the scan.
        """
        for row, existing in enumerate(self._entries):
            if existing.scan_id == scan_id:
                self.beginRemoveRows(QModelIndex(), row, row)
                del self._entries[row]
                self._repeated = None
                self.endRemoveRows()
                self._pins.pop(scan_id, None)
                return

    def entry(self, scan_id: str) -> ScanEntry | None:
        """
        Find a scan.

        Args:
            scan_id (str): Id of the scan.

        Returns:
            ScanEntry | None: The scan, or None when it is not listed.
        """
        return next((entry for entry in self._entries if entry.scan_id == scan_id), None)

    def entries(self) -> list[ScanEntry]:
        """
        All scans, the newest first.

        Returns:
            list[ScanEntry]: The scans.
        """
        return list(self._entries)

    def pins(self) -> dict[str, int]:
        """
        The pinned scans and the palette slot of each.

        Returns:
            dict[str, int]: Scan id to slot, in the order of pinning.
        """
        return dict(self._pins)

    def toggle_pin(self, scan_id: str) -> None:
        """
        Pin a scan for comparison, or let it go.

        Args:
            scan_id (str): Id of the scan.
        """
        if scan_id in self._pins:
            del self._pins[scan_id]
        else:
            used = set(self._pins.values())
            # Slot 0 belongs to the scan that is selected.
            self._pins[scan_id] = next(slot for slot in range(1, 64) if slot not in used)
        for row, entry in enumerate(self._entries):
            if entry.scan_id == scan_id:
                index = self.index(row)
                self.dataChanged.emit(index, index)

    def pin_scans(self, scan_ids: list[str]) -> None:
        """
        Pin several scans for comparison at once. Scans that are pinned already stay pinned.

        Args:
            scan_ids (list[str]): Ids of the scans.
        """
        added = False
        for scan_id in scan_ids:
            if scan_id in self._pins:
                continue
            used = set(self._pins.values())
            self._pins[scan_id] = next(slot for slot in range(1, 64) if slot not in used)
            added = True
        if added and self._entries:
            self.dataChanged.emit(self.index(0), self.index(len(self._entries) - 1))

    def clear_pins(self) -> None:
        """Let all pinned scans go."""
        self._pins.clear()
        if self._entries:
            self.dataChanged.emit(self.index(0), self.index(len(self._entries) - 1))


class ScanFilterModel(QSortFilterProxyModel):
    """Keeps the scans that fit the search text and the chosen ending."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self._ending = "all"

    def set_text(self, text: str) -> None:
        """
        Keep the scans that fit a search text.

        Args:
            text (str): Words to look for.
        """
        self._text = text.strip()
        self.invalidate()

    def set_ending(self, ending: str) -> None:
        """
        Keep the scans with one kind of ending.

        Args:
            ending (str): ``all``, ``finished`` or ``early``.
        """
        self._ending = ending
        self.invalidate()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        entry: ScanEntry = self.sourceModel().index(source_row, 0).data(ENTRY_ROLE)
        if entry.live:
            return not self._text or entry.matches(self._text)
        if self._ending == "finished" and entry.ended_early:
            return False
        if self._ending == "early" and not entry.ended_early:
            return False
        return not self._text or entry.matches(self._text)


def fit_parts(parts: list[str], metrics: QFontMetrics, width: int) -> str:
    """
    Join as many of ``parts`` as fit into ``width``, leaving out the last ones first.

    A part is never cut in the middle, except the first one when even it does not fit.

    Args:
        parts (list[str]): The parts, the most important first.
        metrics (QFontMetrics): Metrics of the font the text is drawn in.
        width (int): Room in pixels.

    Returns:
        str: The text to draw.
    """
    for count in range(len(parts), 0, -1):
        text = "  ·  ".join(parts[:count])
        if metrics.horizontalAdvance(text) <= width:
            return text
    return metrics.elidedText(parts[0], Qt.TextElideMode.ElideRight, width) if parts else ""


class ScanDelegate(QStyledItemDelegate):
    """Draws a scan in two lines, with how it ended and a pin."""

    ROW_HEIGHT = 46
    PIN_SIZE = 18
    MARGIN = 8

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(160, self.ROW_HEIGHT)

    def pin_rect(self, rect: QRect) -> QRect:
        """
        Where the pin of a row is drawn and clicked.

        Args:
            rect (QRect): Rectangle of the row.

        Returns:
            QRect: Rectangle of the pin.
        """
        size = self.PIN_SIZE + 8
        return QRect(
            rect.right() - self.MARGIN - size + 4, rect.center().y() - size // 2, size, size
        )

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        entry: ScanEntry = index.data(ENTRY_ROLE)
        model: ScanListModel = index.model().sourceModel()
        slot = model.pins().get(entry.scan_id)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        palette = option.palette
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # The selected scan keeps its text colour on a tint, so that the bar in the colour
        # it has in the plot stays visible.
        if selected or hovered:
            tint = QColor(palette.color(QPalette.ColorRole.Highlight))
            tint.setAlpha(52 if selected else 22)
            painter.fillRect(option.rect, tint)
        text_color = palette.color(QPalette.ColorRole.Text)
        muted = muted_color() if not selected else QColor(text_color)
        if selected:
            muted.setAlphaF(0.66)

        rect = option.rect.adjusted(self.MARGIN + 6, 5, -self.MARGIN, -5)
        # A bar in the colour the scan has in the plot.
        color_slot = 0 if selected else slot
        if color_slot is not None:
            bar = QRect(option.rect.left() + 3, option.rect.top() + 6, 4, option.rect.height() - 12)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(series_color(color_slot)))
            painter.drawRoundedRect(bar, 2, 2)

        pin_rect = self.pin_rect(option.rect)
        pinnable = getattr(option.widget, "pinnable", True)
        if pinnable and (slot is not None or hovered or selected):
            icon_color = text_color if slot is not None else muted
            pixmap = material_icon(
                "keep",
                size=(self.PIN_SIZE, self.PIN_SIZE),
                color=icon_color.name(),
                filled=slot is not None,
            )
            painter.setOpacity(1.0 if slot is not None else 0.7)
            painter.drawPixmap(
                pin_rect.center().x() - self.PIN_SIZE // 2,
                pin_rect.center().y() - self.PIN_SIZE // 2,
                pixmap,
            )
            painter.setOpacity(1.0)
        rect.setRight(pin_rect.left() - 4)

        bold = QFont(option.font)
        bold.setWeight(QFont.Weight.DemiBold)
        metrics = QFontMetrics(option.font)
        line_height = metrics.height()
        top = QRect(rect.left(), rect.top(), rect.width(), line_height)
        bottom = QRect(rect.left(), rect.bottom() - line_height + 1, rect.width(), line_height)

        # A number listed more than once is told apart by the date and time of each scan.
        repeated = model.is_repeated(entry)
        when = format_when(
            entry.start_time if repeated else (entry.end_time or entry.start_time), full=repeated
        )
        when_width = metrics.horizontalAdvance(when) + 6
        painter.setPen(muted)
        painter.setFont(option.font)
        align_right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        align_left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        painter.drawText(top, align_right, when)

        painter.setPen(text_color)
        painter.setFont(bold)
        number = f"{entry.scan_number}" if entry.scan_number is not None else "?"
        number_width = QFontMetrics(bold).horizontalAdvance(number) + 8
        painter.drawText(top, align_left, number)
        painter.setFont(option.font)
        name_rect = top.adjusted(number_width, 0, -when_width, 0)
        name = metrics.elidedText(entry.scan_name, Qt.TextElideMode.ElideRight, name_rect.width())
        painter.drawText(name_rect, align_left, name)

        status = STATUS_LABELS.get(entry.status, "")
        status_width = 0
        if status:
            # Drawn like the Chip of the scan queue: tone text on a tint of it, with a rim.
            tone = tone_color(STATUS_TONES.get(entry.status, Tone.NEUTRAL))
            status_width = metrics.horizontalAdvance(status) + 16
            pill = QRectF(
                bottom.right() - status_width + 1.5,
                bottom.top() + 0.5,
                status_width - 1,
                line_height,
            )
            fill, rim = QColor(tone), QColor(tone)
            fill.setAlphaF(0.16)
            rim.setAlphaF(0.45)
            painter.setPen(QPen(rim, 1))
            painter.setBrush(fill)
            painter.drawRoundedRect(pill, 9, 9)
            painter.setPen(tone)
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, status)
        painter.setPen(muted)
        summary_rect = bottom.adjusted(0, 0, -(status_width + 6), 0)
        painter.drawText(
            summary_rect,
            align_left,
            fit_parts(entry.summary_parts(), metrics, summary_rect.width()),
        )
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:
        if not getattr(self.parent(), "pinnable", True):
            return super().editorEvent(event, model, option, index)
        if event.type() == QEvent.Type.MouseButtonRelease and self.pin_rect(option.rect).contains(
            event.position().toPoint()
        ):
            entry: ScanEntry = index.data(ENTRY_ROLE)
            model.sourceModel().toggle_pin(entry.scan_id)
            return True
        return super().editorEvent(event, model, option, index)

    def helpEvent(self, event, view, option, index) -> bool:
        pinnable = getattr(view, "pinnable", True)
        if pinnable and index.isValid() and self.pin_rect(option.rect).contains(event.pos()):
            entry: ScanEntry = index.data(ENTRY_ROLE)
            pinned = entry.scan_id in index.model().sourceModel().pins()
            view.setToolTip("")
            # pylint: disable=import-outside-toplevel
            from qtpy.QtWidgets import QToolTip

            QToolTip.showText(
                event.globalPos(),
                (
                    "Take this scan off the plot (P)"
                    if pinned
                    else f"Keep this scan on the plot to compare (P or {control_key_name()}-click)"
                ),
                view,
            )
            return True
        return super().helpEvent(event, view, option, index)


class _ScanListView(QListView):
    """
    List view that adds scans to the comparison: the P key pins the current scan, a click with
    Ctrl (Cmd on macOS) pins or unpins the clicked one, a click with Shift pins every scan
    between the current one and the clicked one. A plain click selects.
    """

    #: Whether scans can be pinned for comparison in this list.
    pinnable = True

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        if not self.pinnable:
            super().mousePressEvent(event)
            return
        modifiers = event.modifiers()
        index = self.indexAt(event.position().toPoint())
        wanted = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        current = self.currentIndex()
        if (
            event.button() != Qt.MouseButton.LeftButton
            or not modifiers & wanted
            or not index.isValid()
            or not current.isValid()
        ):
            super().mousePressEvent(event)
            return
        source: ScanListModel = self.model().sourceModel()
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            low, high = sorted((current.row(), index.row()))
            rows = [row for row in range(low, high + 1) if row != current.row()]
            source.pin_scans([self.model().index(row, 0).data(ENTRY_ROLE).scan_id for row in rows])
        elif index != current:
            source.toggle_pin(index.data(ENTRY_ROLE).scan_id)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_P and self.pinnable and self.currentIndex().isValid():
            entry: ScanEntry = self.currentIndex().data(ENTRY_ROLE)
            self.model().sourceModel().toggle_pin(entry.scan_id)
            return
        super().keyPressEvent(event)


class ScanList(QWidget):
    """Searchable list of scans with pins for comparison."""

    #: The selected scan changed: a :class:`ScanEntry`, or None.
    scan_selected = Signal(object)
    #: The set of pinned scans changed.
    pins_changed = Signal()
    #: A context menu was asked for on a scan: the :class:`ScanEntry` and the global position.
    context_menu_requested = Signal(object, QPoint)

    def __init__(self, parent: QWidget | None = None, pinnable: bool = True):
        """
        Args:
            parent (QWidget | None): Parent widget.
            pinnable (bool): Whether scans can be pinned for comparison.
        """
        super().__init__(parent)
        self._current_id: str | None = None
        self._quiet = False
        self.model = ScanListModel(self)
        self.filter_model = ScanFilterModel(self)
        self.filter_model.setSourceModel(self.model)

        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Search scans")
        self.search_edit.setAccessibleName("Search scans")
        self.search_edit.setToolTip("Search by scan number, scan name or motor")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.addAction(
            material_icon("search", size=(16, 16), convert_to_pixmap=False),
            QLineEdit.ActionPosition.LeadingPosition,
        )

        self.ending_group = QButtonGroup(self)
        self.ending_group.setExclusive(True)
        self.ending_buttons: dict[str, QToolButton] = {}
        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(4)
        for key, label, tip in (
            ("all", "All", "Show every scan"),
            ("finished", "Finished", "Only scans that ran to their end"),
            ("early", "Ended early", "Only scans that were stopped, halted or ended by hand"),
        ):
            button = QToolButton(self)
            button.setText(label)
            button.setToolTip(tip)
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setChecked(key == "all")
            button.clicked.connect(lambda _checked=False, key=key: self._set_ending(key))
            self.ending_group.addButton(button)
            self.ending_buttons[key] = button
            chips.addWidget(button)
        chips.addStretch(1)
        self.unpin_button = QToolButton(self)
        self.unpin_button.setText("Unpin all")
        self.unpin_button.setAutoRaise(True)
        self.unpin_button.setToolTip("Let all pinned scans go")
        self.unpin_button.clicked.connect(self.model.clear_pins)
        self.unpin_button.hide()
        chips.addWidget(self.unpin_button)

        self.view = _ScanListView(self)
        self.view.pinnable = pinnable
        self.view.setModel(self.filter_model)
        self.delegate = ScanDelegate(self.view)
        self.view.setItemDelegate(self.delegate)
        self.view.setUniformItemSizes(True)
        self.view.setMouseTracking(True)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setAccessibleName("Scans")
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._on_context_menu)

        self.note = QLabel(self)
        self.note.setWordWrap(True)
        mute(self.note)
        self.note.setContentsMargins(6, 2, 6, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.search_edit)
        layout.addLayout(chips)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.note)

        self.search_edit.textChanged.connect(self._on_search)
        self.view.selectionModel().currentChanged.connect(self._on_current_changed)
        self.model.dataChanged.connect(self._on_model_changed)
        self.model.modelReset.connect(self._update_note)
        self.model.rowsInserted.connect(self._update_note)
        self.model.rowsRemoved.connect(self._update_note)
        self._pins_seen = self.model.pins()
        # A message in the note, e.g. the result of an action, stays this long.
        self._note_timer = QTimer(self)
        self._note_timer.setSingleShot(True)
        self._note_timer.setInterval(NOTE_FLASH_MS)
        self._note_timer.timeout.connect(self._update_note)
        self._update_note()

    def cleanup(self) -> None:
        """Stop the timer of the note."""
        self._note_timer.stop()

    def flash_note(self, text: str) -> None:
        """
        Say something in the note under the list for a few seconds, then go back to the count.

        Args:
            text (str): What to say.
        """
        self.note.setText(text)
        self._note_timer.start()

    def _on_context_menu(self, position: QPoint) -> None:
        index = self.view.indexAt(position)
        if index.isValid():
            self.context_menu_requested.emit(
                index.data(ENTRY_ROLE), self.view.viewport().mapToGlobal(position)
            )

    ################################################################################
    # Public interface
    ################################################################################

    def set_entries(self, entries: list[ScanEntry]) -> None:
        """
        Replace all scans and keep the selection where the scan is still listed.

        Args:
            entries (list[ScanEntry]): The scans.
        """
        current_id = self._current_id
        self._quiet = True
        try:
            self.model.set_entries(entries)
            kept = current_id is not None and self.model.entry(current_id) is not None
            if kept:
                self._show_current()
        finally:
            self._quiet = False
        if kept:
            self.scan_selected.emit(self.model.entry(current_id))
        elif self.filter_model.rowCount():
            self._current_id = None
            self.view.setCurrentIndex(self.filter_model.index(0, 0))
        else:
            self.clear_selection()

    def add_entry(self, entry: ScanEntry) -> None:
        """
        Add a scan, or update the one with the same id.

        Args:
            entry (ScanEntry): The scan.
        """
        first = self.model.rowCount() == 0
        self.model.upsert(entry)
        if first and self.filter_model.rowCount():
            self.view.setCurrentIndex(self.filter_model.index(0, 0))
        elif self._current_id == entry.scan_id:
            self.scan_selected.emit(entry)

    def current_entry(self) -> ScanEntry | None:
        """
        The selected scan. It stays selected while a search or a filter hides it.

        Returns:
            ScanEntry | None: The scan, or None when none is selected.
        """
        return self.model.entry(self._current_id) if self._current_id is not None else None

    def clear_selection(self) -> None:
        """Select no scan."""
        had_selection = self._current_id is not None
        self._current_id = None
        self._quiet = True
        try:
            self.view.setCurrentIndex(self.filter_model.index(-1, 0))
        finally:
            self._quiet = False
        if had_selection:
            self.scan_selected.emit(None)

    def select(self, scan_id: str) -> bool:
        """
        Select a scan.

        Args:
            scan_id (str): Id of the scan.

        Returns:
            bool: False when the scan is not in the list as it is filtered now.
        """
        for row in range(self.filter_model.rowCount()):
            index = self.filter_model.index(row, 0)
            if index.data(ENTRY_ROLE).scan_id == scan_id:
                self.view.setCurrentIndex(index)
                self.view.scrollTo(index)
                return True
        return False

    def pinned_entries(self) -> list[tuple[ScanEntry, int]]:
        """
        The pinned scans with the palette slot of each.

        Returns:
            list[tuple[ScanEntry, int]]: Scan and slot, in the order of pinning.
        """
        out = []
        for scan_id, slot in self.model.pins().items():
            entry = self.model.entry(scan_id)
            if entry is not None:
                out.append((entry, slot))
        return out

    ################################################################################
    # Internals
    ################################################################################

    def _set_ending(self, key: str) -> None:
        self._filter(lambda: self.filter_model.set_ending(key))

    def _on_search(self, text: str) -> None:
        self._filter(lambda: self.filter_model.set_text(text))

    def _filter(self, change) -> None:
        """Change what is listed without changing which scan is selected."""
        self._quiet = True
        try:
            change()
            self._show_current()
        finally:
            self._quiet = False
        self._update_note()

    def _show_current(self) -> None:
        """Put the cursor on the selected scan, or nowhere while it is not listed."""
        if self._current_id is None or not self.select(self._current_id):
            self.view.setCurrentIndex(self.filter_model.index(-1, 0))

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        self.view.viewport().update()
        if self._quiet or not current.isValid():
            return
        entry: ScanEntry = current.data(ENTRY_ROLE)
        if entry.scan_id != self._current_id:
            self._current_id = entry.scan_id
            self.scan_selected.emit(entry)

    def _on_model_changed(self, *_args) -> None:
        pins = self.model.pins()
        if pins != self._pins_seen:
            self._pins_seen = pins
            self.unpin_button.setVisible(bool(pins))
            self.pins_changed.emit()

    def _update_note(self, *_args) -> None:
        if self._note_timer.isActive():
            return
        total = self.model.rowCount()
        shown = self.filter_model.rowCount()
        if total == 0:
            self.note.setText("No scans yet. A scan shows up here when it is done.")
        elif shown == 0:
            self.note.setText("No scan fits. Clear the search or choose “All”.")
        elif shown < total:
            self.note.setText(f"{shown} of {total} scans")
        else:
            self.note.setText("1 scan" if total == 1 else f"{total} scans")
