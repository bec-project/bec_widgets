"""
The list of scans of the HDF5 viewer.

The list is filled from the scan history that BEC keeps in memory; no file is opened to
show it. Scans can be searched, filtered by how they ended and pinned for comparison.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from numbers import Integral
from pathlib import Path

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
from qtpy.QtGui import QColor, QCursor, QFont, QFontMetrics, QPainter, QPen, QPixmap
from qtpy.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import get_theme_name
from bec_widgets.utils.theme_utils import crisp_pixmap, theme_colors
from bec_widgets.widgets.progress.stage_bar import Tone, mono_font
from bec_widgets.widgets.services.bec_queue.queue_model import HISTORY_STATUS
from bec_widgets.widgets.services.bec_queue.queue_ui import (
    BADGE_ALPHA,
    BADGE_PADDING,
    BADGE_RADIUS,
    GROUP_TITLE_FONT_PX,
    GROUP_TITLE_LETTER_SPACING,
    ROW_BUTTON_ICON_SIZE,
    ROW_BUTTON_SIZE,
    ROW_GAP,
    ROW_HOVER_ALPHA,
    ROW_ICON_SIZE,
    ROW_MARGINS,
    ROW_RADIUS,
    ROW_SELECTED_ALPHA,
    ROW_SPACING,
    row_muted_color,
    tone_color,
)
from bec_widgets.widgets.services.hdf5_viewer.style import (
    blend,
    control_key_name,
    count_text,
    mute,
    readable,
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
#: How long a message stays in the note under the list.
NOTE_FLASH_MS = 3000
#: A read that answers within this time shows no loading page: the list stays blank meanwhile,
#: so that a quick read does not flicker.
LOADING_SHOWN_AFTER_MS = 300
#: The page that says the scans are being read, or could not be read, stays at least this long
#: once shown, so that it can be read and does not flash.
STATE_KEPT_MS = 300
#: Icon, tone and word of a scan that is still going; finished scans use the queue's.
LIVE_STATUS = {
    "open": ("play_circle", Tone.RUN, "Running"),
    "paused": ("pause_circle", Tone.WARN, "Paused"),
}

#: The current scan's ring: its width at the edge of the row, then a gap before the fill.
RING_WIDTH = 2.0
RING_GAP = 1.5
#: Motors and duration show after the name only with at least this much room left.
EXTRAS_MIN_WIDTH = 40
#: The points give way once the name could not show this many letters, then the time.
NAME_KEEPS_POINTS = 12
NAME_KEEPS_TIME = 9
#: A row as tall as the queue's: its button and the margins above and below it.
ROW_HEIGHT = ROW_BUTTON_SIZE + ROW_MARGINS[1] + ROW_MARGINS[3]
#: The status icon sits in a box as wide as the queue's StatusIcon.
LEAD_WIDTH = ROW_ICON_SIZE + 4
#: A day header: a count badge and the margins of a row; the rule above a later day sits in
#: the middle of the space between the parts of a row.
HEAD_HEIGHT = 2 * BADGE_RADIUS + ROW_MARGINS[1] + ROW_MARGINS[3]
RULE_SPACE = ROW_SPACING


def scan_status(entry: "ScanEntry") -> tuple[str, Tone, str]:
    """
    How a scan ended or what it is doing, as the scan queue shows it.

    Args:
        entry (ScanEntry): The scan.

    Returns:
        tuple[str, Tone, str]: Material icon name, tone and word.
    """
    # A scan opened from its file is never running, whatever the file says.
    if entry.live or (entry.status in LIVE_STATUS and not entry.imported):
        return LIVE_STATUS.get(entry.status, LIVE_STATUS["open"])
    word = entry.status.replace("_", " ").capitalize()
    return HISTORY_STATUS.get(entry.status, ("help", Tone.NEUTRAL, word))


def grid_shape(request_inputs: dict) -> tuple[int, ...]:
    """
    The number of steps of each motor of a grid scan, as its argument bundle names them.

    Args:
        request_inputs (dict): The ``request_inputs`` of a scan history or status message.

    Returns:
        tuple[int, ...]: For example ``(12, 8)``; empty when the bundle is not motor, start,
        stop and steps for two motors or more.
    """
    # The bundle may come as a numpy array, its numbers as numpy integers.
    bundle = request_inputs.get("arg_bundle")
    bundle = list(bundle) if bundle is not None else []
    starts = [position for position, arg in enumerate(bundle) if isinstance(arg, str)]
    if len(starts) < 2:
        return ()
    steps = []
    for number, start in enumerate(starts):
        end = starts[number + 1] if number + 1 < len(starts) else len(bundle)
        group = bundle[start:end]
        if len(group) != 4 or isinstance(group[3], bool) or not isinstance(group[3], Integral):
            return ()
        steps.append(int(group[3]))
    return tuple(steps)


#: The group of the scans opened from their files, above the days, and its header.
IMPORTED_GROUP = "imported"
IMPORTED_LABEL = "Imported"


def row_when(entry: "ScanEntry", today: date | None = None) -> str:
    """
    When a scan started, as its row says it: the time under a day header, the date for an
    imported scan, whose header names no day.

    Args:
        entry (ScanEntry): The scan.
        today (date | None): The day it is now, for tests.

    Returns:
        str: For example ``14:23``, ``19 Nov`` or ``19 Nov 2025``; empty when not known.
    """
    if not entry.start_time:
        return ""
    when = datetime.fromtimestamp(entry.start_time)
    if not entry.imported:
        return when.strftime("%H:%M")
    today = date.today() if today is None else today
    if when.year == today.year:
        return f"{when.day} {when:%b}"
    return f"{when.day} {when:%b %Y}"


def day_label(day: date | None, today: date | None = None) -> str:
    """
    Name of a day in a day header.

    Args:
        day (date | None): The day.
        today (date | None): The day it is now, for tests.

    Returns:
        str: ``Today``, ``Yesterday``, ``Mon 16 Nov`` this year or ``16 Nov 2025``.
    """
    if day is None:
        return "No date"
    today = date.today() if today is None else today
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    if day.year == today.year:
        return f"{day:%a} {day.day} {day:%b}"
    return f"{day.day} {day:%b %Y}"


def day_title(label: str, metrics: QFontMetrics, room: int) -> str:
    """
    The text of a day header: the label in capitals, without its weekday when it does not
    fit (``MON 16 NOV`` gives way to ``16 NOV``).

    Args:
        label (str): The day label, see :func:`day_label`.
        metrics (QFontMetrics): Metrics of the header font.
        room (int): Width in px left beside the count badge.

    Returns:
        str: The text to draw.
    """
    text = label.upper()
    words = text.split(" ")
    if len(words) == 3 and words[0].isalpha() and metrics.horizontalAdvance(text) > room:
        return " ".join(words[1:])
    return text


def on_color(fill: QColor) -> QColor:
    """
    Black or white, whichever reads better on a fill.

    Args:
        fill (QColor): The fill.

    Returns:
        QColor: Pure black or pure white.
    """

    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    luminance = (
        0.2126 * linear(fill.redF())
        + 0.7152 * linear(fill.greenF())
        + 0.0722 * linear(fill.blueF())
    )
    on_white = 1.05 / (luminance + 0.05)
    on_black = (luminance + 0.05) / 0.05
    return QColor("#ffffff" if on_white >= on_black else "#000000")


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


def scan_motors(request_inputs: dict) -> tuple[str, ...]:
    """
    The motors a scan moved, in order, as its request names them.

    Most scans name them in their argument bundle (``line_scan``, ``grid_scan``); others take
    them as keyword inputs ``motor1``, ``motor2``, … (``fermat_scan``, ``round_roi_scan``).

    Args:
        request_inputs (dict): The ``request_inputs`` of a scan history or status message.

    Returns:
        tuple[str, ...]: The motor names, each once.
    """
    bundle = request_inputs.get("arg_bundle")
    names = [arg for arg in (list(bundle) if bundle is not None else []) if isinstance(arg, str)]
    inputs = request_inputs.get("inputs") or {}
    keyed = sorted(
        (key, value)
        for key, value in inputs.items()
        if key.startswith("motor") and key[5:].isdigit() and isinstance(value, str)
    )
    names += [value for _key, value in sorted(keyed, key=lambda item: int(item[0][5:]))]
    return tuple(dict.fromkeys(names))


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
    #: BEC's readout group of each device, where the status message of a running scan tells.
    readout_groups: dict = field(default_factory=dict)
    live: bool = False
    #: Steps of each motor of a grid scan, e.g. ``(12, 8)``.
    grid: tuple[int, ...] = ()
    #: Opened from a file that BEC wrote, not listed in the scan history of the session.
    imported: bool = False

    @classmethod
    def from_history(cls, msg: dict) -> ScanEntry:
        """
        Build an entry from a dumped ``ScanHistoryMessage``.

        Args:
            msg (dict): The message content.

        Returns:
            ScanEntry: The entry.
        """
        motors = scan_motors(msg.get("request_inputs") or {})
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
            grid=grid_shape(msg.get("request_inputs") or {}),
        )

    @classmethod
    def from_file_scan(cls, scan_id: str, scan) -> ScanEntry:
        """
        Build the entry of a scan opened from its file, outside the scan history.

        Args:
            scan_id (str): The id the scan is listed by.
            scan: What the file says about the scan, see ``h5_reader.BecScanFile``.

        Returns:
            ScanEntry: The entry.
        """
        request = scan.request_inputs or {}
        return cls(
            scan_id=scan_id,
            scan_number=scan.scan_number,
            scan_name=scan.scan_name,
            status=scan.status or "unknown",
            start_time=scan.start_time,
            end_time=scan.end_time,
            num_points=scan.num_points,
            file_path=scan.file_path,
            motors=scan_motors(request) or tuple(scan.scan_report_devices),
            stored_data_info=scan.stored_data_info,
            grid=grid_shape(request),
            imported=True,
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

    @property
    def day(self) -> date | None:
        """The day the scan started on, or None when that is not known."""
        when = self.start_time or self.end_time
        return datetime.fromtimestamp(when).date() if when else None

    def recorded_points(self) -> int | None:
        """
        How many points the scan recorded, as the readback of its first motor says.

        Returns:
            int | None: The number, or None when the scan stored no motor readback.
        """
        for motor in self.motors:
            meta = (self.stored_data_info.get(motor) or {}).get(motor)
            shape = meta.get("shape") if isinstance(meta, dict) else getattr(meta, "shape", None)
            if shape:
                return int(shape[0])
        return None

    def points_text(self) -> str:
        """
        The points of the scan in a few characters: ``100``, ``12 × 8`` for a grid, or
        ``37/100`` for a scan that ended before its last point.

        Returns:
            str: The text, empty when the number of points is not known.
        """
        planned = self.num_points
        if not planned:
            return ""
        if self.ended_early:
            done = self.recorded_points()
            if done is not None and done < planned:
                return f"{done}/{planned}"
        if self.grid and math.prod(self.grid) == planned:
            return " × ".join(str(steps) for steps in self.grid)
        return str(planned)

    def points_words(self) -> str:
        """
        The points of the scan in words.

        Returns:
            str: For example ``"37 of 100 points"`` or ``"96 points (12 × 8)"``.
        """
        planned = self.num_points
        if not planned:
            return ""
        if self.ended_early:
            done = self.recorded_points()
            if done is not None and done < planned:
                return f"{done} of {planned} points"
        words = "1 point" if planned == 1 else f"{planned} points"
        if self.grid and math.prod(self.grid) == planned:
            words += f" ({' × '.join(str(steps) for steps in self.grid)})"
        return words

    def matches(self, text: str) -> bool:
        """
        Whether the scan fits a search text.

        Args:
            text (str): Words to look for in the number, the name and the motors.

        Returns:
            bool: True when every word is found.
        """
        words = [str(self.scan_number), self.scan_name, *self.motors]
        if self.imported:
            words.append(Path(self.file_path).name)
        haystack = " ".join(words).lower()
        return all(word in haystack for word in text.lower().split())


class ScanListModel(QAbstractListModel):
    """Scans, the newest first, with the colour of the pinned ones."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[ScanEntry] = []
        self._pins: dict[str, int] = {}
        #: Scan numbers listed more than once, worked out when first needed.
        self._repeated: set | None = None
        #: The scans that have a curve on the plot, their colour while two or more do, and
        #: why a pinned scan has none.
        self._on_plot: set[str] = set()
        self._plot_colors: dict[str, str] = {}
        self._off_reasons: dict[str, str] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        entry = self._entries[index.row()]
        if role == ENTRY_ROLE:
            return entry
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
            return self.describe(entry)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self.tooltip(entry)
        return None

    def describe(self, entry: ScanEntry) -> str:
        """
        The scan in one sentence, for screen readers: number, name, status, points, start,
        and whether it is on the plot and pinned. Colour is never the only sign of these.

        Args:
            entry (ScanEntry): The scan.

        Returns:
            str: For example ``"Scan 23 line_scan, completed, 100 points, started 19 Nov 13:52,
            on the plot, pinned for comparison"``.
        """
        parts = [f"Scan {entry.title}", scan_status(entry)[2].lower(), entry.points_words()]
        if entry.start_time:
            parts.append(f"started {format_when(entry.start_time, full=True)}")
        if entry.scan_id in self._on_plot:
            parts.append("on the plot")
        if entry.scan_id in self._pins:
            parts.append("pinned for comparison")
        return ", ".join(part for part in parts if part)

    def tooltip(self, entry: ScanEntry) -> str:
        """
        What the row of a scan says, in full: name, status, points and start, then what
        moved and for how long, why a pinned scan is not on the plot, and the file.

        Args:
            entry (ScanEntry): The scan.

        Returns:
            str: Lines of text.
        """
        number = f"{entry.scan_number}" if entry.scan_number is not None else "?"
        first = [scan_status(entry)[2], entry.points_words()]
        if entry.start_time:
            first.append(f"started {format_when(entry.start_time, full=True)}")
        lines = [f"#{number} {entry.scan_name}".rstrip(), "  ·  ".join(p for p in first if p)]
        moved = []
        if entry.motors:
            moved.append(", ".join(entry.motors))
        if entry.end_time and entry.start_time and not entry.live:
            moved.append(format_duration(entry.end_time - entry.start_time))
        if moved:
            lines.append("  ·  ".join(moved))
        reason = self._off_reasons.get(entry.scan_id) if entry.scan_id in self._pins else None
        if reason:
            lines.append(reason)
        if self.is_repeated(entry) and not entry.imported:
            lines.append(f"Scan id {entry.scan_id}")
        if entry.imported:
            lines.append("Opened from its file, not in the scan history")
        if entry.file_path:
            lines.append(entry.file_path)
        return "\n".join(lines)

    def set_plot(
        self, on_plot: set[str], colors: dict[str, str], reasons: dict[str, str] | None = None
    ) -> None:
        """
        Tell which scans have a curve on the plot and in which colour.

        Args:
            on_plot (set[str]): Ids of the scans with a curve on the plot.
            colors (dict[str, str]): Colour of each such scan; rows are filled with it only
                while two scans or more are on the plot.
            reasons (dict[str, str] | None): Why a pinned scan has no curve, in words.
        """
        on_plot = set(on_plot)
        colors = dict(colors) if len(colors) >= 2 else {}
        reasons = dict(reasons or {})
        if (on_plot, colors, reasons) == (self._on_plot, self._plot_colors, self._off_reasons):
            return
        self._on_plot, self._plot_colors, self._off_reasons = on_plot, colors, reasons
        if self._entries:
            self.dataChanged.emit(self.index(0), self.index(len(self._entries) - 1))

    def plot_color(self, scan_id: str) -> str | None:
        """
        The colour a scan's row is filled with.

        Args:
            scan_id (str): Id of the scan.

        Returns:
            str | None: Its curve colour while two scans or more are on the plot, else None.
        """
        return self._plot_colors.get(scan_id)

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
        # Imported scans come first, under their own header, then the running one.
        return (entry.imported, entry.live, entry.start_time, entry.scan_number or 0)

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


@dataclass(frozen=True)
class DayHead:
    """The header painted above the first listed scan of a day."""

    label: str
    count: int
    first: bool
    #: Whether the header says that the scans are listed newest first.
    newest_first: bool = False


@dataclass
class RowParts:
    """Where the texts of a row go once the row's width is known."""

    number: str
    name: str
    name_rect: QRect
    extras: str = ""
    extras_rect: QRect = field(default_factory=QRect)
    points: str = ""
    points_rect: QRect = field(default_factory=QRect)
    time: str = ""
    time_rect: QRect = field(default_factory=QRect)


class ScanDelegate(QStyledItemDelegate):
    """
    Draws a scan in one line, in the look of a finished row of the scan queue: status icon,
    ``#number name``, points and start time, and a pin. The first listed scan of a day carries
    the day's header above it.

    While two scans or more are on the plot, a row is filled with its curve colour; the
    current scan has a ring in the primary colour.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmaps: dict[tuple, QPixmap] = {}

    # -------------------------------------------------------------- geometry

    def head(self, index: QModelIndex) -> DayHead | None:
        """
        The day header above a row.

        Args:
            index (QModelIndex): Index of the row in the view's model.

        Returns:
            DayHead | None: The header, or None for a row that is not the first of its day.
        """
        return getattr(self.parent(), "heads", {}).get(index.row())

    def head_height(self, index: QModelIndex) -> int:
        """
        Height of the day header above a row.

        Args:
            index (QModelIndex): Index of the row in the view's model.

        Returns:
            int: Pixels; zero for a row without a header.
        """
        head = self.head(index)
        if head is None:
            return 0
        return HEAD_HEIGHT + (0 if head.first else RULE_SPACE)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(160, self.head_height(index) + ROW_HEIGHT + ROW_GAP)

    def row_rect(self, rect: QRect, index: QModelIndex) -> QRect:
        """
        The scan's own row inside the item, below its day header.

        Args:
            rect (QRect): Rectangle of the item.
            index (QModelIndex): Its index.

        Returns:
            QRect: Rectangle of the row.
        """
        return QRect(rect.left(), rect.top() + self.head_height(index), rect.width(), ROW_HEIGHT)

    @staticmethod
    def pin_rect(row: QRect) -> QRect:
        """
        Where the pin of a row is drawn and clicked.

        Args:
            row (QRect): Rectangle of the row.

        Returns:
            QRect: Rectangle of the pin button.
        """
        return QRect(
            row.right() + 1 - ROW_MARGINS[2] - ROW_BUTTON_SIZE,
            row.top() + (row.height() - ROW_BUTTON_SIZE) // 2,
            ROW_BUTTON_SIZE,
            ROW_BUTTON_SIZE,
        )

    @staticmethod
    def lead_rect(row: QRect) -> QRect:
        """
        Where the status icon of a row sits.

        Args:
            row (QRect): Rectangle of the row.

        Returns:
            QRect: Rectangle of the icon's box.
        """
        return QRect(
            row.left() + ROW_MARGINS[0],
            row.top() + (row.height() - LEAD_WIDTH) // 2,
            LEAD_WIDTH,
            LEAD_WIDTH,
        )

    def row_parts(self, row: QRect, entry: ScanEntry) -> RowParts:
        """
        Lay out the texts of a row. The number and the pin never give way; the points go
        first, once the name could not show its first letters, then the time; only then is
        the name cut at its end.

        Args:
            row (QRect): Rectangle of the row.
            entry (ScanEntry): The scan.

        Returns:
            RowParts: The texts and where each goes.
        """
        name_metrics = QFontMetrics(mono_font(0))
        small_metrics = QFontMetrics(mono_font(-1))
        top, height = row.top() + ROW_MARGINS[1], row.height() - ROW_MARGINS[1] - ROW_MARGINS[3]
        left = self.lead_rect(row).right() + 1 + ROW_SPACING
        right = self.pin_rect(row).left() - ROW_SPACING
        number = f"#{entry.scan_number if entry.scan_number is not None else '?'} "
        number_width = name_metrics.horizontalAdvance(number)
        when = row_when(entry)
        time_width = small_metrics.horizontalAdvance(when if entry.imported else "00:00")
        points = entry.points_text()
        points_width = small_metrics.horizontalAdvance(points)
        name = entry.scan_name

        def room(with_points: bool, with_time: bool) -> int:
            end = right
            if with_time:
                end -= time_width + ROW_SPACING
            if with_points:
                end -= points_width + ROW_SPACING
            return end - left - number_width

        def needs(letters: int) -> int:
            return name_metrics.horizontalAdvance(name[:letters])

        show_time, show_points = bool(when), bool(points)
        if show_points and room(True, show_time) < needs(NAME_KEEPS_POINTS):
            show_points = False
        if show_time and room(show_points, True) < needs(NAME_KEEPS_TIME):
            show_time = False
        name_room = max(0, room(show_points, show_time))
        name_width = name_metrics.horizontalAdvance(name)
        shown_name = (
            name
            if name_width <= name_room
            else name_metrics.elidedText(name, Qt.TextElideMode.ElideRight, name_room)
        )
        parts = RowParts(
            number=number,
            name=shown_name,
            name_rect=QRect(left, top, number_width + min(name_width, name_room), height),
        )
        end = right
        if show_time:
            parts.time = when
            parts.time_rect = QRect(end - time_width, top, time_width, height)
            end = parts.time_rect.left() - ROW_SPACING
        if show_points:
            parts.points = points
            parts.points_rect = QRect(end - points_width, top, points_width, height)
            end = parts.points_rect.left() - ROW_SPACING
        spare = end - parts.name_rect.right() - ROW_SPACING
        if name_width <= name_room and spare >= EXTRAS_MIN_WIDTH:
            moved = []
            if entry.motors:
                moved.append(", ".join(entry.motors))
            if entry.end_time and entry.start_time and not entry.live:
                moved.append(format_duration(entry.end_time - entry.start_time))
            # Parts are left out whole, never cut.
            for count in range(len(moved), 0, -1):
                text = "  ·  ".join(moved[:count])
                if small_metrics.horizontalAdvance(text) <= spare:
                    parts.extras = text
                    parts.extras_rect = QRect(
                        parts.name_rect.right() + 1 + ROW_SPACING, top, spare, height
                    )
                    break
        return parts

    # -------------------------------------------------------------- painting

    def _pixmap(self, name: str, size: int, color: QColor, filled: bool, widget) -> QPixmap:
        ratio = widget.devicePixelRatioF() if widget is not None else 1.0
        key = (name, size, color.name(), filled, ratio)
        pixmap = self._pixmaps.get(key)
        if pixmap is None:
            pixmap = crisp_pixmap(name, size, color, filled=filled, widget=widget)
            self._pixmaps[key] = pixmap
        return pixmap

    @staticmethod
    def _pointer(widget) -> QPoint | None:
        if widget is None:
            return None
        viewport = widget.viewport() if hasattr(widget, "viewport") else widget
        return viewport.mapFromGlobal(QCursor.pos())

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        entry: ScanEntry = index.data(ENTRY_ROLE)
        model: ScanListModel = index.model().sourceModel()
        widget = option.widget
        colors = theme_colors()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        head = self.head(index)
        if head is not None:
            self._paint_head(painter, option, head, colors)
        row = self.row_rect(option.rect, index)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        pointer = self._pointer(widget) if option.state & QStyle.StateFlag.State_MouseOver else None
        hovered = pointer is not None and row.contains(pointer)
        fill_name = model.plot_color(entry.scan_id)
        fill = QColor(fill_name) if fill_name else None

        body = QRectF(row)
        if selected:
            ring = QRectF(row).adjusted(
                RING_WIDTH / 2, RING_WIDTH / 2, -RING_WIDTH / 2, -RING_WIDTH / 2
            )
            painter.setPen(QPen(colors["primary"], RING_WIDTH))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(ring, ROW_RADIUS - RING_WIDTH / 2, ROW_RADIUS - RING_WIDTH / 2)
            inset = RING_WIDTH + RING_GAP
            body = QRectF(row).adjusted(inset, inset, -inset, -inset)
        radius = ROW_RADIUS - (RING_WIDTH + RING_GAP if selected else 0)
        painter.setPen(Qt.PenStyle.NoPen)
        if fill is not None:
            painter.setBrush(fill)
            painter.drawRoundedRect(body, radius, radius)
        elif selected:
            tint = QColor(colors["primary"])
            tint.setAlphaF(ROW_SELECTED_ALPHA)
            painter.setBrush(tint)
            painter.drawRoundedRect(body, radius, radius)
        if hovered:
            shade = QColor(colors["fg"])
            shade.setAlphaF(ROW_HOVER_ALPHA)
            painter.setBrush(shade)
            painter.drawRoundedRect(body, radius, radius)

        # On a coloured row everything is black or white; nothing is muted there.
        ink = on_color(fill) if fill is not None else QColor(colors["fg"])
        muted = ink if fill is not None else row_muted_color(colors, selected)
        icon, tone, _word = scan_status(entry)
        lead = self.lead_rect(row)
        pixmap = self._pixmap(
            icon, ROW_ICON_SIZE, ink if fill is not None else tone_color(tone), True, widget
        )
        painter.drawPixmap(
            lead.center().x() - ROW_ICON_SIZE // 2 + 1,
            lead.center().y() - ROW_ICON_SIZE // 2 + 1,
            pixmap,
        )

        parts = self.row_parts(row, entry)
        align_left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        align_right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        painter.setFont(mono_font(0))
        painter.setPen(ink)
        painter.drawText(parts.name_rect, align_left, parts.number + parts.name)
        painter.setFont(mono_font(-1))
        painter.setPen(muted)
        if parts.extras:
            painter.drawText(parts.extras_rect, align_left, parts.extras)
        if parts.points:
            painter.drawText(parts.points_rect, align_right, parts.points)
        if parts.time:
            painter.drawText(parts.time_rect, align_right, parts.time)

        pinned = entry.scan_id in model.pins()
        if getattr(widget, "pinnable", True) and (pinned or hovered or selected):
            pin = self.pin_rect(row)
            if hovered and pin.contains(pointer):
                shade = QColor(ink)
                shade.setAlphaF(ROW_HOVER_ALPHA * 2)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(shade)
                painter.drawRoundedRect(QRectF(pin), ROW_RADIUS, ROW_RADIUS)
            pixmap = self._pixmap(
                "keep", ROW_BUTTON_ICON_SIZE, ink if pinned else muted, pinned, widget
            )
            painter.drawPixmap(
                pin.center().x() - ROW_BUTTON_ICON_SIZE // 2 + 1,
                pin.center().y() - ROW_BUTTON_ICON_SIZE // 2 + 1,
                pixmap,
            )
        painter.restore()

    @staticmethod
    def _title_font(base: QFont) -> QFont:
        font = QFont(base)
        font.setPixelSize(GROUP_TITLE_FONT_PX)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, GROUP_TITLE_LETTER_SPACING)
        return font

    def _paint_head(self, painter: QPainter, option: QStyleOptionViewItem, head: DayHead, colors):
        """A day header like the queue's group titles: uppercase muted title, count badge."""
        rect = option.rect
        top = rect.top()
        left = rect.left() + ROW_MARGINS[0]
        right = rect.right() - ROW_MARGINS[2]
        if not head.first:
            line = top + RULE_SPACE // 2
            painter.setPen(QPen(colors["border"], 1))
            painter.drawLine(left, line, right, line)
            top += RULE_SPACE
        title = QRect(left, top, right - left, HEAD_HEIGHT)
        font = self._title_font(option.font)
        badge_font = QFont(option.font)
        badge_font.setWeight(QFont.Weight.DemiBold)
        count = count_text(head.count)
        badge_width = max(
            2 * BADGE_RADIUS, QFontMetrics(badge_font).horizontalAdvance(count) + 2 * BADGE_PADDING
        )
        text = day_title(head.label, QFontMetrics(font), title.width() - ROW_SPACING - badge_width)
        painter.setFont(font)
        painter.setPen(colors["muted"])
        painter.drawText(title, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        text_width = QFontMetrics(font).horizontalAdvance(text)

        badge = QRectF(
            left + text_width + ROW_SPACING,
            title.center().y() + 1 - BADGE_RADIUS,
            badge_width,
            2 * BADGE_RADIUS,
        )
        fill = QColor(colors["primary"])
        fill.setAlphaF(BADGE_ALPHA)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(badge, BADGE_RADIUS, BADGE_RADIUS)
        painter.setFont(badge_font)
        # The count reads on its pill as in the headers of the signal list.
        painter.setPen(
            readable(colors["primary"], blend(colors["primary"], colors["bg"], BADGE_ALPHA))
        )
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, count)

        if head.newest_first:
            hint_font = QFont(option.font)
            hint_font.setPixelSize(GROUP_TITLE_FONT_PX)
            hint = "newest first"
            room = right - int(badge.right()) - ROW_SPACING
            if QFontMetrics(hint_font).horizontalAdvance(hint) <= room:
                painter.setFont(hint_font)
                painter.setPen(colors["muted"])
                painter.drawText(
                    title, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, hint
                )

    # -------------------------------------------------------------- events

    def editorEvent(self, event, model, option, index) -> bool:
        if not getattr(self.parent(), "pinnable", True):
            return super().editorEvent(event, model, option, index)
        if event.type() == QEvent.Type.MouseButtonRelease and self.pin_rect(
            self.row_rect(option.rect, index)
        ).contains(event.position().toPoint()):
            entry: ScanEntry = index.data(ENTRY_ROLE)
            model.sourceModel().toggle_pin(entry.scan_id)
            return True
        return super().editorEvent(event, model, option, index)

    def helpEvent(self, event, view, option, index) -> bool:
        if not index.isValid():
            return super().helpEvent(event, view, option, index)
        # pylint: disable=import-outside-toplevel
        from qtpy.QtWidgets import QToolTip

        row = self.row_rect(option.rect, index)
        position = event.pos()
        entry: ScanEntry = index.data(ENTRY_ROLE)
        if not row.contains(position):
            QToolTip.hideText()
            return True
        if getattr(view, "pinnable", True) and self.pin_rect(row).contains(position):
            pinned = entry.scan_id in index.model().sourceModel().pins()
            text = (
                "Take this scan off the plot (P)"
                if pinned
                else f"Keep this scan on the plot to compare (P or {control_key_name()}-click)"
            )
        elif self.lead_rect(row).contains(position):
            text = scan_status(entry)[2]
        else:
            text = index.data(Qt.ItemDataRole.ToolTipRole)
        QToolTip.showText(event.globalPos(), text, view, row)
        return True


class _ScanListView(QListView):
    """
    List view that adds scans to the comparison: the P key pins the current scan, a click with
    Ctrl (Cmd on macOS) pins or unpins the clicked one, a click with Shift pins every scan
    between the current one and the clicked one. A plain click selects. Day headers cannot be
    selected: a click on one does nothing.
    """

    #: Whether scans can be pinned for comparison in this list.
    pinnable = True
    #: A held key was let go (its last, real release).
    key_released = Signal()
    #: Delete was pressed on an imported scan: the :class:`ScanEntry`.
    remove_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        #: The day header above each row that starts a day, by row of the view's model.
        self.heads: dict[int, DayHead] = {}
        self._hovered_rect = QRect()
        #: Whether the current row is moving by a held key (an auto-repeated press).
        self.key_held = False

    def _on_head(self, index: QModelIndex, position: QPoint) -> bool:
        rect = self.visualRect(index)
        return position.y() < rect.top() + self.itemDelegate().head_height(index)

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        self.key_held = False
        position = event.position().toPoint()
        index = self.indexAt(position)
        if index.isValid() and self._on_head(index, position):
            event.accept()
            return
        if not self.pinnable:
            super().mousePressEvent(event)
            return
        modifiers = event.modifiers()
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

    def mouseDoubleClickEvent(self, event):  # pylint: disable=invalid-name
        position = event.position().toPoint()
        index = self.indexAt(position)
        if index.isValid() and self._on_head(index, position):
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):  # pylint: disable=invalid-name
        super().mouseMoveEvent(event)
        # The hover look depends on where in the item the pointer is: header, row or pin.
        index = self.indexAt(event.position().toPoint())
        rect = self.visualRect(index) if index.isValid() else QRect()
        for changed in (self._hovered_rect, rect):
            if not changed.isNull():
                self.viewport().update(changed)
        self._hovered_rect = rect

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        super().leaveEvent(event)
        if not self._hovered_rect.isNull():
            self.viewport().update(self._hovered_rect)
        self._hovered_rect = QRect()

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        # Set before the row moves: the row signal is emitted inside the press.
        self.key_held = event.isAutoRepeat()
        if event.key() == Qt.Key.Key_P and self.pinnable and self.currentIndex().isValid():
            entry: ScanEntry = self.currentIndex().data(ENTRY_ROLE)
            self.model().sourceModel().toggle_pin(entry.scan_id)
            return
        if (
            event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace)
            and self.currentIndex().isValid()
            and self.currentIndex().data(ENTRY_ROLE).imported
        ):
            self.remove_requested.emit(self.currentIndex().data(ENTRY_ROLE))
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):  # pylint: disable=invalid-name
        super().keyReleaseEvent(event)
        if not event.isAutoRepeat():
            self.key_held = False
            self.key_released.emit()

    def focusOutEvent(self, event):  # pylint: disable=invalid-name
        # The release of a held key may go to another widget.
        self.key_held = False
        super().focusOutEvent(event)


class ScanList(QWidget):
    """Searchable list of scans with pins for comparison."""

    #: The selected scan changed: a :class:`ScanEntry`, or None.
    scan_selected = Signal(object)
    #: The set of pinned scans changed.
    pins_changed = Signal()
    #: A context menu was asked for on a scan: the :class:`ScanEntry` and the global position.
    context_menu_requested = Signal(object, QPoint)
    #: The user asked to read the scan history again after it could not be read.
    reload_requested = Signal()
    #: The user asked to open a file while there are no scans.
    open_file_requested = Signal()
    #: The user asked to take an imported scan off the list: the :class:`ScanEntry`.
    remove_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None, pinnable: bool = True):
        """
        Args:
            parent (QWidget | None): Parent widget.
            pinnable (bool): Whether scans can be pinned for comparison.
        """
        super().__init__(parent)
        self._current_id: str | None = None
        self._quiet = False
        #: Why the scan history could not be read, while it could not.
        self._load_error = ""
        #: Whether the scans are still being read: until the first answer the list is not empty.
        self._loading = True
        #: Whether the empty list offers to open a file.
        self.offer_open_file = False
        #: Whether a running scan is listed from its start (else only once it has run).
        self.lists_running_scans = False
        self.model = ScanListModel(self)
        self.filter_model = ScanFilterModel(self)
        self.filter_model.setSourceModel(self.model)

        self.search_edit = QLineEdit(self)
        self.search_edit.setObjectName("scan_search")
        self.search_edit.setPlaceholderText("Search scans")
        self.search_edit.setAccessibleName("Search scans")
        self.search_edit.setToolTip("Search by scan number, scan name or motor")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.addAction(
            material_icon("search", size=(16, 16), convert_to_pixmap=False),
            QLineEdit.ActionPosition.LeadingPosition,
        )

        # The search field and, at its right end, a button set by the owner of the list.
        self._search_row = QHBoxLayout()
        self._search_row.setContentsMargins(0, 0, 0, 0)
        self._search_row.setSpacing(4)
        self._search_row.addWidget(self.search_edit, 1)
        self._search_button: QToolButton | None = None
        self._search_button_tip = ""
        self._search_button_width = 0

        self.ending_group = QButtonGroup(self)
        self.ending_group.setExclusive(True)
        self.ending_buttons: dict[str, QToolButton] = {}
        self._ending_words: dict[str, tuple[str, str]] = {}
        self._counts = {"all": 0, "finished": 0, "early": 0}
        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(4)
        self._chips = chips
        for key, label, tip in (
            ("all", "All", "Show every scan"),
            ("finished", "Finished", "Only scans that ran to their end"),
            ("early", "Ended early", "Only scans that were stopped, halted or ended by hand"),
        ):
            button = QToolButton(self)
            button.setObjectName(f"scan_filter_{key}")
            button.setText(label)
            button.setToolTip(tip)
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setChecked(key == "all")
            button.clicked.connect(lambda _checked=False, key=key: self._set_ending(key))
            self.ending_group.addButton(button)
            self.ending_buttons[key] = button
            self._ending_words[key] = (label, tip)
            chips.addWidget(button)
        chips.addStretch(1)

        # The scans pinned for comparison, with the way to let them go.
        self.pin_bar = QWidget(self)
        self.pin_bar.setObjectName("pin_bar")
        pin_line = QHBoxLayout(self.pin_bar)
        pin_line.setContentsMargins(6, 0, 0, 0)
        pin_line.setSpacing(ROW_SPACING)
        self.pin_label = QLabel(self.pin_bar)
        self.pin_label.setObjectName("pin_label")
        self.unpin_button = QToolButton(self.pin_bar)
        self.unpin_button.setObjectName("unpin_all_button")
        self.unpin_button.setText("Unpin all")
        self.unpin_button.setAutoRaise(True)
        self.unpin_button.setToolTip("Take all pinned scans off the plot")
        self.unpin_button.clicked.connect(self.model.clear_pins)
        self.unpin_button.hide()
        pin_line.addWidget(self.pin_label, 1)
        pin_line.addWidget(self.unpin_button)
        self.pin_bar.hide()

        self.view = _ScanListView(self)
        self.view.setObjectName("scan_view")
        self.view.pinnable = pinnable
        self.view.setModel(self.filter_model)
        self.delegate = ScanDelegate(self.view)
        self.view.setItemDelegate(self.delegate)
        # Rows that start a day are taller: they carry the day's header.
        self.view.setUniformItemSizes(False)
        self.view.setMouseTracking(True)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setAccessibleName("Scans")
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._on_context_menu)
        self.view.remove_requested.connect(self.remove_requested)

        # The footer: always the count, and the hint only when the whole line fits.
        self.note = QLabel(self)
        self.note.setObjectName("scan_note")
        self.note.setWordWrap(True)
        mute(self.note)
        self.hint = QLabel(f"{control_key_name()}-click or P to compare", self)
        self.hint.setObjectName("scan_hint")
        mute(self.hint)
        # Texts that give way never hold the panel wide.
        for label in (self.hint, self.pin_label):
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        footer = QHBoxLayout()
        footer.setContentsMargins(6, 2, 6, 2)
        footer.setSpacing(ROW_SPACING)
        footer.addWidget(self.note, 1)
        footer.addWidget(self.hint)
        self._footer = footer
        self.hint.setVisible(pinnable)
        self._pinnable = pinnable

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(self._search_row)
        layout.addLayout(chips)
        layout.addWidget(self.pin_bar)
        # In place of the list when it shows nothing: what is the case and the way out.
        # pylint: disable=import-outside-toplevel
        from bec_widgets.widgets.services.hdf5_viewer.h5_preview import StatePage

        self.state = StatePage(self)
        self.state.setObjectName("scan_list_state")
        # Shown while a read has not answered for long: nothing, so a quick read does not flicker.
        self.blank = QWidget(self)
        self.blank.setObjectName("scan_list_blank")
        self.blank.setAccessibleName("Reading the scan history")
        self.list_stack = QStackedWidget(self)
        self.list_stack.addWidget(self.view)
        self.list_stack.addWidget(self.state)
        self.list_stack.addWidget(self.blank)
        layout.addWidget(self.list_stack, 1)
        layout.addLayout(footer)

        self.search_edit.textChanged.connect(self._on_search)
        self.view.selectionModel().currentChanged.connect(self._on_current_changed)
        self.model.dataChanged.connect(self._on_model_changed)
        self.model.modelReset.connect(self._update_note)
        self.model.rowsInserted.connect(self._update_note)
        self.model.rowsRemoved.connect(self._update_note)
        for signal in (
            self.filter_model.modelReset,
            self.filter_model.rowsInserted,
            self.filter_model.rowsRemoved,
            self.filter_model.layoutChanged,
        ):
            signal.connect(self._update_heads)
        for signal in (self.model.modelReset, self.model.rowsInserted, self.model.rowsRemoved):
            signal.connect(self._update_counts)
        self._pins_seen = self.model.pins()
        # A message in the note, e.g. the result of an action, stays this long.
        self._note_timer = QTimer(self)
        self._note_timer.setSingleShot(True)
        self._note_timer.setInterval(NOTE_FLASH_MS)
        self._note_timer.timeout.connect(self._update_note)
        self._loading_timer = QTimer(self)
        self._loading_timer.setSingleShot(True)
        self._loading_timer.setInterval(LOADING_SHOWN_AFTER_MS)
        self._loading_timer.timeout.connect(self._update_note)
        self._loading_timer.start()
        self._state_kept = QTimer(self)
        self._state_kept.setSingleShot(True)
        self._state_kept.setInterval(STATE_KEPT_MS)
        self._state_kept.timeout.connect(self._update_note)
        self._update_note()
        self._update_counts()

    def cleanup(self) -> None:
        """Stop the timers of the note and of the loading page."""
        self._note_timer.stop()
        self._loading_timer.stop()
        self._state_kept.stop()

    def flash_note(self, text: str) -> None:
        """
        Say something in the note under the list for a few seconds, then go back to the count.

        Args:
            text (str): What to say.
        """
        self.note.setText(text)
        self._note_timer.start()
        self.hint.hide()

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
        self._load_error = ""
        self._loading = False
        self._loading_timer.stop()
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
        self._update_counts()
        if first and self.filter_model.rowCount():
            self.view.setCurrentIndex(self.filter_model.index(0, 0))
        elif self._current_id == entry.scan_id:
            self.scan_selected.emit(entry)

    def remove_entry(self, scan_id: str) -> None:
        """
        Take a scan off the list. When it was selected, the selection goes where the list puts
        it at the start: on the newest scan of the history, else on the first row.

        Args:
            scan_id (str): Id of the scan.
        """
        if self.model.entry(scan_id) is None:
            return
        was_current = self._current_id == scan_id
        self._quiet = True
        try:
            self.model.remove(scan_id)
        finally:
            self._quiet = False
        self._update_counts()
        # Its pin went with it.
        self._on_model_changed()
        if not was_current:
            return
        self._current_id = None
        rows = [self.filter_model.index(row, 0) for row in range(self.filter_model.rowCount())]
        target = next((index for index in rows if not index.data(ENTRY_ROLE).imported), None)
        if target is None and rows:
            target = rows[0]
        if target is None:
            self._quiet = True
            try:
                self.view.setCurrentIndex(self.filter_model.index(-1, 0))
            finally:
                self._quiet = False
            self.scan_selected.emit(None)
            return
        self.view.setCurrentIndex(target)
        self.view.scrollTo(target)
        if self._current_id is None:
            # The cursor was on that row already: say the selection anyway.
            entry = target.data(ENTRY_ROLE)
            self._current_id = entry.scan_id
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

    def show_load_failed(self, reason: str) -> None:
        """
        Say that the scan history could not be read, with a way to try again. The next
        :meth:`set_entries` ends this state.

        Args:
            reason (str): Why, in one sentence.
        """
        self._load_error = reason
        self._loading = False
        self._loading_timer.stop()
        self._update_note()

    def show_loading(self) -> None:
        """Say that the scans are being read; :meth:`set_entries` or a failure ends it."""
        self._load_error = ""
        self._loading = True
        self._loading_timer.start()
        self._update_note()

    def clear_filter(self) -> None:
        """Clear the search and list scans of every ending again; the list keeps a current row."""
        self.search_edit.clear()
        self.ending_buttons["all"].click()
        if not self.view.currentIndex().isValid() and self.filter_model.rowCount():
            self.view.setCurrentIndex(self.filter_model.index(0, 0))

    def set_plot(
        self, on_plot: set[str], colors: dict[str, str], reasons: dict[str, str] | None = None
    ) -> None:
        """
        Tell the list which scans have a curve on the plot and in which colour.

        Args:
            on_plot (set[str]): Ids of the scans with a curve on the plot.
            colors (dict[str, str]): Curve colour of each; rows are filled with it only while
                two scans or more are on the plot.
            reasons (dict[str, str] | None): Why a pinned scan has no curve, in words.
        """
        self.model.set_plot(on_plot, colors, reasons)

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
        self._update_counts()

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
            self.pin_bar.setVisible(bool(pins))
            self._fit_texts()
            self.pins_changed.emit()

    def _update_heads(self, *_args) -> None:
        """Find the first listed scan of each day and how many scans of that day follow."""
        proxy = self.filter_model
        runs: list[list] = []
        for row in range(proxy.rowCount()):
            entry = proxy.index(row, 0).data(ENTRY_ROLE)
            # The imported scans are one group above the days, whatever their day.
            day = IMPORTED_GROUP if entry.imported else entry.day
            if runs and runs[-1][1] == day:
                runs[-1][2] += 1
            else:
                runs.append([row, day, 1])
        today = date.today()
        first_day = next(
            (number for number, run in enumerate(runs) if run[1] != IMPORTED_GROUP), -1
        )
        heads = {
            row: DayHead(
                IMPORTED_LABEL if day == IMPORTED_GROUP else day_label(day, today),
                count,
                number == 0,
                number == first_day,
            )
            for number, (row, day, count) in enumerate(runs)
        }
        if heads != self.view.heads:
            self.view.heads = heads
            # Rows that gained or lost a header change their height.
            self.view.scheduleDelayedItemsLayout()

    def _update_counts(self, *_args) -> None:
        """Count the scans each ending filter would list with the current search."""
        text = self.filter_model._text  # pylint: disable=protected-access
        counts = {"all": 0, "finished": 0, "early": 0}
        for entry in self.model._entries:  # pylint: disable=protected-access
            if text and not entry.matches(text):
                continue
            counts["all"] += 1
            if entry.live:
                continue
            counts["early" if entry.ended_early else "finished"] += 1
        self._counts = counts
        self._fit_texts()

    def set_search_button(self, button: QToolButton) -> None:
        """
        Put a button at the right end of the search row, as tall as the field. It shows its
        text while the field keeps room for its whole placeholder beside it, else its icon alone
        with the text as its tooltip. It comes after the field in the keyboard order.

        Args:
            button (QToolButton): The button, with its text, icon and tooltip set.
        """
        self._search_button = button
        self._search_button_tip = button.toolTip()
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setFixedHeight(self.search_edit.sizeHint().height())
        self._search_row.addWidget(button)
        QWidget.setTabOrder(self.search_edit, button)
        QWidget.setTabOrder(button, self.ending_buttons["all"])
        self._fit_search_button()

    def search_field_need(self) -> int:
        """
        The width the search field needs to show its whole placeholder: the text measured in
        its font, plus what the field keeps beside the text (its icon, margins and frame).

        Returns:
            int: The width in pixels.
        """
        edit = self.search_edit
        metrics = edit.fontMetrics()
        # QLineEdit's size hint is 17 "x" wide plus everything beside the text.
        beside = edit.sizeHint().width() - 17 * metrics.horizontalAdvance("x")
        return beside + metrics.horizontalAdvance(edit.placeholderText()) + 2

    def _fit_search_button(self) -> None:
        button = self._search_button
        if button is None:
            return
        if button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon:
            self._search_button_width = button.sizeHint().width()
        fits = (
            self.width()
            >= self.search_field_need() + self._search_row.spacing() + self._search_button_width
        )
        style = (
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            if fits
            else Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        if button.toolButtonStyle() != style:
            button.setToolButtonStyle(style)
        button.setToolTip(self._search_button_tip if fits else button.text())

    def _fit_texts(self) -> None:
        """
        Choose the texts that fit the width: the filter counts only when all three fit, the
        long words of the pin bar when they fit, the footer hint only when the whole line does,
        the text of the search row's button when the field keeps its room.
        """
        self._fit_search_button()
        width = self.width()
        # Filters: labels with their counts, or labels only; the counts stay in the tooltip
        # and the accessible name.
        needed = self._chips.spacing() * (len(self.ending_buttons) - 1)
        wanted = {}
        for key, button in self.ending_buttons.items():
            label, _tip = self._ending_words[key]
            wanted[key] = f"{label} {count_text(self._counts[key])}"
            metrics = button.fontMetrics()
            needed += (
                button.sizeHint().width()
                - metrics.horizontalAdvance(button.text())
                + metrics.horizontalAdvance(wanted[key])
            )
        # While the history is read, or when it holds no scan, a 0 is not known or says
        # nothing: the labels only. A search that leaves nothing keeps its zeros.
        known = not self._loading and self.model.rowCount() > 0
        with_counts = known and needed <= width
        for key, button in self.ending_buttons.items():
            label, tip = self._ending_words[key]
            count = self._counts[key]
            text = wanted[key] if with_counts else label
            if button.text() != text:
                metrics = button.fontMetrics()
                # The counts must not hold the panel wide: a button needs room for its label.
                button.setMinimumWidth(
                    button.sizeHint().width()
                    - metrics.horizontalAdvance(button.text())
                    + metrics.horizontalAdvance(label)
                )
                button.setText(text)
            scans = "1 scan" if count == 1 else f"{count_text(count)} scans"
            button.setToolTip(f"{tip}  ·  {scans}" if known else tip)
            button.setAccessibleName(f"{label}, {scans}" if known else label)

        pins = len(self.model.pins())
        if pins:
            long_text = f"{count_text(pins)} pinned for comparison"
            room = width - self.unpin_button.sizeHint().width() - ROW_SPACING - 6
            fits = self.pin_label.fontMetrics().horizontalAdvance(long_text) <= room
            self.pin_label.setText(long_text if fits else f"{count_text(pins)} pinned")

        if self._pinnable:
            margins = self._footer.contentsMargins()
            line = (
                self.note.fontMetrics().horizontalAdvance(self.note.text())
                + self._footer.spacing()
                + self.hint.fontMetrics().horizontalAdvance(self.hint.text())
                + margins.left()
                + margins.right()
            )
            self.hint.setVisible(not self._note_timer.isActive() and line <= width)

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._fit_texts()

    def _update_note(self, *_args) -> None:
        if self._note_timer.isActive():
            return
        total = self.model.rowCount()
        shown = self.filter_model.rowCount()
        if total == 0 and self._loading:
            self.note.setText("" if self._loading_timer.isActive() else "Reading scans…")
        elif total == 0:
            self.note.setText("No scans")
        elif shown < total:
            self.note.setText(f"{count_text(shown)} of {count_text(total)} scans")
        else:
            self.note.setText("1 scan" if total == 1 else f"{count_text(total)} scans")
        self._show_state(total, shown)
        self._fit_texts()

    def _show_state(self, total: int, shown: int) -> None:
        """Show the list, or in its place what is the case and the way out of it."""
        focus = self.window().focusWidget()
        had_focus = focus is not None and (
            focus in (self.state, self.blank) or self.state.isAncestorOf(focus)
        )
        if total and self._state_kept.isActive() and self.list_stack.currentWidget() is self.state:
            # The scans came in just after the page about reading them showed: it stays a moment.
            return
        if total == 0 and self._loading and self._loading_timer.isActive():
            # A read that answers soon shows nothing in between.
            self.list_stack.setCurrentWidget(self.blank)
            if had_focus:
                self.blank.setFocus()
            return
        if total == 0 and self._loading:
            state = ("hourglass_empty", "Reading the scan history…", "", ())
        elif total == 0 and self._load_error:
            state = (
                "error",
                "The scan history could not be read",
                self._load_error,
                (("Try again", self.reload_requested.emit),),
            )
        elif total == 0:
            when = "starts" if self.lists_running_scans else "has run"
            state = (
                "history",
                "No scans yet",
                f"A scan shows up here as soon as it {when}."
                + (" A file can be opened meanwhile." if self.offer_open_file else ""),
                (("Open file…", self.open_file_requested.emit),) if self.offer_open_file else (),
            )
        elif shown == 0:
            state = (
                "search_off",
                "No scan fits the filter",
                self._filter_words(total),
                (("Clear the filter", self.clear_filter),),
            )
        else:
            self.list_stack.setCurrentWidget(self.view)
            # The way out was taken: the focus goes on to the list, never nowhere.
            if had_focus:
                self.view.setFocus()
            return
        appears = not (
            self.list_stack.currentWidget() is self.state and self.state.title.text() == state[1]
        )
        if not appears and self.state.text.text() == state[2]:
            # The same state again (e.g. a key typed into the search): nothing to rebuild.
            return
        if appears and state[0] in ("hourglass_empty", "error"):
            self._state_kept.start()
        self.state.show_state(*state)
        self.state.setAccessibleName(
            f"{state[1]}. {state[2]}".strip(". ") if state[2] else state[1]
        )
        self.list_stack.setCurrentWidget(self.state)
        if had_focus:
            # The button that had the focus was rebuilt: the focus stays on its successor.
            buttons = self.state._actions  # pylint: disable=protected-access
            if buttons:
                # A new button is shown by its layout only later; focus needs it shown now.
                buttons[0].show()
                buttons[0].setFocus()
            else:
                self.state.setFocus()

    def _filter_words(self, total: int) -> str:
        """What hides the scans, e.g. All 1,054 are hidden by “grid” and “Ended early”."""
        reasons = []
        text = self.search_edit.text().strip()
        if text:
            reasons.append(f"“{text}”")
        ending = self.filter_model._ending  # pylint: disable=protected-access
        if ending in ("finished", "early"):
            reasons.append(f"“{self._ending_words[ending][0]}”")
        scans = "The only scan is" if total == 1 else f"All {count_text(total)} are"
        return f"{scans} hidden by {' and '.join(reasons)}."
