"""Toolkit-independent core of the reworked log panel.

The QML and QWidget versions of the log panel share everything that is not drawing:

- :class:`LogEntry` is one log message, flattened once at ingest. Multi-line messages keep a
  one-line summary (the exception line for tracebacks) and are expanded on demand.
- :class:`LogFeedModel` is a flat list model of the visible entries. It filters incrementally
  (a live batch only checks the new entries), folds identical consecutive messages into one row
  with a counter, keeps per level and per service counts and knows the search matches, so both
  views render the same rows from the same model.
- :class:`LogPanelBackend` owns the model, the filters, pause and follow-tail state and all user
  actions. Both views call its slots and render :attr:`LogPanelBackend.state`.

Level colours follow the notification rework (``notification_ux_common.severity_color``) so a
warning or error looks the same in a toast, the notification drawer and the log panel.
"""

from __future__ import annotations

import re
import time
import zlib
from bisect import bisect_left
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from bec_lib.logger import bec_logger
from qtpy.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication, QFileDialog

from bec_widgets.utils.quick.host import ThemeTokens, _blend

logger = bec_logger.logger

# level name -> (badge text, group)
LEVELS: dict[str, tuple[str, str]] = {
    "CRITICAL": ("CRIT", "error"),
    "ERROR": ("ERROR", "error"),
    "WARNING": ("WARN", "warning"),
    "SUCCESS": ("OK", "info"),
    "INFO": ("INFO", "info"),
    "DEBUG": ("DEBUG", "debug"),
    "TRACE": ("TRACE", "debug"),
}

# level chips, in display order: key -> label
GROUPS: dict[str, str] = {
    "error": "Errors",
    "warning": "Warnings",
    "info": "Info",
    "debug": "Debug",
}

# time window presets: key -> (label, seconds or None for no limit)
SINCE: dict[str, tuple[str, int | None]] = {
    "all": ("All time", None),
    "5m": ("Last 5 min", 300),
    "15m": ("Last 15 min", 900),
    "1h": ("Last hour", 3600),
    "24h": ("Last 24 h", 86400),
}

UNKNOWN_SERVICE = "unknown"
FOLD_WINDOW_S = 30.0
MAX_BODY_LINES = 400
_TRACE_FILE = re.compile(r'^\s*File "')
_EXCEPTION_LINE = re.compile(r"^[A-Za-z_][\w.]*(Error|Exception|Exit|Interrupt|Warning)\b")


def level_color(tokens: ThemeTokens, level: str) -> QColor:
    """Theme colour of a log level, matching the notification severities."""
    if level == "CRITICAL":
        return QColor(tokens.danger)
    if level == "ERROR":
        return _blend(tokens.warning, tokens.danger, 0.55)
    if level == "WARNING":
        return QColor(tokens.warning)
    if level == "SUCCESS":
        return QColor(tokens.success)
    if level == "INFO":
        return QColor(tokens.accent)
    return QColor(tokens.fg_subtle)


def ink(tokens: ThemeTokens, color: QColor) -> QColor:
    """Readable text version of an accent colour: light accents are darkened on light themes."""
    if tokens.dark or color.lightnessF() < 0.45:
        return QColor(color)
    return color.darker(100 + int((color.lightnessF() - 0.3) * 260))


def group_color(tokens: ThemeTokens, group: str) -> QColor:
    """Colour of a level chip."""
    return level_color(
        tokens, {"error": "ERROR", "warning": "WARNING", "info": "INFO"}.get(group, "DEBUG")
    )


def service_color(tokens: ThemeTokens, service: str) -> QColor:
    """Stable colour per service name so a service is recognisable at a glance."""
    if not service or service == UNKNOWN_SERVICE:
        return QColor(tokens.fg_subtle)
    hue = zlib.crc32(service.encode()) % 360
    if tokens.dark:
        return QColor.fromHsl(hue, 150, 170)
    return QColor.fromHsl(hue, 170, 95)


def classify_line(line: str) -> str:
    """Kind of one message line, used to style tracebacks.

    Returns:
        str: ``head`` (Traceback header), ``file`` (frame location), ``exception`` (raised
        exception) or ``text``.
    """
    stripped = line.strip()
    if stripped.startswith(("Traceback (most recent call last)", "During handling", "The above")):
        return "head"
    if _TRACE_FILE.match(line):
        return "file"
    if _EXCEPTION_LINE.match(stripped):
        return "exception"
    return "text"


class LogEntry:
    """One log message, flattened for display, filtering and search."""

    __slots__ = (
        "seq",
        "level",
        "badge",
        "group",
        "ts",
        "first_ts",
        "service",
        "function",
        "message",
        "lower",
        "summary",
        "line_count",
        "is_traceback",
        "count",
    )

    def __init__(
        self,
        seq: int,
        level: str,
        ts: float,
        service: str | None,
        message: str,
        function: str | None = None,
    ):
        level = (level or "INFO").upper()
        self.seq = seq
        self.level = level
        self.badge, self.group = LEVELS.get(level, (level[:5] or "LOG", "debug"))
        self.ts = ts or time.time()
        self.first_ts = self.ts
        self.service = service or UNKNOWN_SERVICE
        self.function = function or ""
        message = (message or "").rstrip()
        self.message = message
        self.lower = message.lower()
        lines = [line for line in message.splitlines() if line.strip()]
        self.line_count = len(lines)
        self.is_traceback = "Traceback (most recent call last)" in message
        summary = lines[0].strip() if lines else ""
        if self.is_traceback and summary.startswith("Traceback"):
            # the raised exception says more than the traceback header
            summary = lines[-1].strip()
        self.summary = summary
        self.count = 1

    @classmethod
    def from_record(cls, rec: Any, seq: int) -> LogEntry:
        """Build an entry from a ``logpanel._LogRec`` (the shared BecLogsQueue record)."""
        return cls(seq, rec.level, rec.ts, rec.service_name, rec.message, rec.function)

    @property
    def fold_key(self) -> tuple:
        """Entries with the same key arriving back to back are folded into one row."""
        return (self.level, self.service, self.message)

    def body_lines(self) -> list[tuple[str, str]]:
        """Lines shown when the entry is expanded, as ``(text, kind)``."""
        lines = self.message.splitlines()
        out = [(line.rstrip(), classify_line(line)) for line in lines[:MAX_BODY_LINES]]
        if len(lines) > MAX_BODY_LINES:
            out.append((f"... {len(lines) - MAX_BODY_LINES} more lines (use Copy)", "head"))
        return out

    def copy_text(self) -> str:
        """Plain text of the entry, ready to paste into a logbook or an issue."""
        stamp = datetime.fromtimestamp(self.ts).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        repeat = f" (x{self.count})" if self.count > 1 else ""
        return f"{stamp} [{self.level}] {self.service}: {self.message}{repeat}"


def format_clock(ts: float, now: float | None = None) -> str:
    """Wall clock time, with the date only when it is not today."""
    stamp = datetime.fromtimestamp(ts)
    today = datetime.fromtimestamp(time.time() if now is None else now).date()
    millis = f"{stamp.microsecond // 1000:03d}"
    if stamp.date() == today:
        return f"{stamp:%H:%M:%S}.{millis}"
    return f"{stamp:%b %d %H:%M:%S}"


def format_relative(ts: float, now: float | None = None) -> str:
    """Age such as ``now``, ``42 s ago``, ``5 min ago`` or ``3 h ago``."""
    seconds = max(0, int((time.time() if now is None else now) - ts))
    if seconds < 5:
        return "now"
    if seconds < 60:
        return f"{seconds} s ago"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return f"{seconds // 86400} d ago"


def format_full(ts: float) -> str:
    """Full timestamp for tooltips and copies."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class SearchMatcher:
    """Case-insensitive plain or regular expression search over log messages.

    Args:
        text(str): The search text.
        regex(bool): Interpret ``text`` as a regular expression.

    Attributes:
        error(str): Why the regular expression is invalid, empty when it is fine.
    """

    def __init__(self, text: str, regex: bool = False):
        self.text = text
        self.regex = regex
        self.error = ""
        self._needle = text.lower()
        self._pattern: re.Pattern | None = None
        if regex and text:
            try:
                self._pattern = re.compile(text, re.IGNORECASE)
            except re.error as exc:
                self.error = str(exc)

    @property
    def active(self) -> bool:
        """Whether the search narrows or marks anything."""
        return bool(self.text) and not self.error

    def matches(self, entry: LogEntry) -> bool:
        """Whether the entry's message or service matches."""
        if not self.active:
            return True
        if self._pattern is not None:
            return bool(self._pattern.search(entry.message) or self._pattern.search(entry.service))
        return self._needle in entry.lower or self._needle in entry.service.lower()

    def spans(self, text: str) -> list[tuple[int, int]]:
        """``(start, length)`` of every match in ``text``, for highlighting."""
        if not self.active or not text:
            return []
        if self._pattern is not None:
            return [
                (m.start(), m.end() - m.start())
                for m in self._pattern.finditer(text)
                if m.end() > m.start()
            ][:64]
        out = []
        lower = text.lower()
        start = lower.find(self._needle)
        while start >= 0 and len(out) < 64:
            out.append((start, len(self._needle)))
            start = lower.find(self._needle, start + len(self._needle))
        return out


ROLES = [
    "seq",
    "level",
    "group",
    "badge",
    "levelColor",
    "levelInk",
    "rowTint",
    "time",
    "timeFull",
    "service",
    "serviceColor",
    "function",
    "summary",
    "summarySpans",
    "lineCount",
    "isTraceback",
    "expanded",
    "bodyLines",
    "count",
    "matched",
    "current",
]


class LogFeedModel(QAbstractListModel):
    """Flat list model of the log entries that pass the current filters.

    Args:
        max_entries(int): Entries kept in memory. Older ones are dropped in chunks.
        parent: Parent QObject.
    """

    TRIM_CHUNK = 1000
    counts_changed = Signal()

    def __init__(self, max_entries: int = 20000, parent: QObject | None = None):
        super().__init__(parent)
        self.max_entries = max_entries
        self._entries: list[LogEntry] = []
        self._rows: list[LogEntry] = []
        self._seq = 0
        self._roles = {Qt.ItemDataRole.UserRole + 1 + i: key for i, key in enumerate(ROLES)}
        self._role_ids = {key: role for role, key in self._roles.items()}
        # filters
        self.groups: set[str] = set(GROUPS)
        self.services: set[str] | None = None
        self.since_key = "all"
        self._since_ts: float | None = None
        self.matcher = SearchMatcher("")
        self.search_mode = "filter"
        # presentation
        self.time_mode = "clock"
        self.expanded: set[int] = set()
        self.current_seq: int | None = None
        self._matches: list[LogEntry] = []
        self.match_pos = -1
        # counts over the entries passing every filter but the level filter
        self.group_counts: dict[str, int] = dict.fromkeys(GROUPS, 0)
        self.service_counts: dict[str, int] = {}
        self.tokens = ThemeTokens()
        self._row_tint: dict[str, QColor] = {}
        self._level_colors: dict[str, QColor] = {}
        self._level_inks: dict[str, QColor] = {}
        self._service_colors: dict[str, QColor] = {}
        self.refresh_theme()

    # ------------------------------------------------------------------ Qt model API
    # pylint: disable=invalid-name,missing-function-docstring
    def roleNames(self) -> dict[int, QByteArray]:
        return {role: QByteArray(key.encode()) for role, key in self._roles.items()}

    def roleNames_ids(self) -> dict[str, int]:
        """Role id of every role name."""
        return dict(self._role_ids)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        entry = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return entry.summary
        key = self._roles.get(role)
        if key is None:
            return None
        return self.role_value(entry, key)

    def role_value(self, entry: LogEntry, key: str) -> Any:
        """Value of one role for ``entry``."""
        # pylint: disable=too-many-return-statements
        if key == "summary":
            return entry.summary
        if key == "time":
            return self.time_text(entry)
        if key == "badge":
            return entry.badge
        if key == "levelColor":
            return self.level_color(entry.level)
        if key == "levelInk":
            return self.level_ink(entry.level)
        if key == "rowTint":
            return self._row_tint.get(entry.level, QColor(0, 0, 0, 0))
        if key == "service":
            return entry.service
        if key == "serviceColor":
            return self.service_color(entry.service)
        if key == "summarySpans":
            return [list(span) for span in self.matcher.spans(entry.summary)]
        if key == "lineCount":
            return entry.line_count
        if key == "expanded":
            return entry.seq in self.expanded
        if key == "bodyLines":
            if entry.seq not in self.expanded:
                return []
            return [
                {"text": text, "kind": kind, "spans": [list(s) for s in self.matcher.spans(text)]}
                for text, kind in entry.body_lines()
            ]
        if key == "count":
            return entry.count
        if key == "matched":
            return (
                self.search_mode == "highlight"
                and self.matcher.active
                and self.matcher.matches(entry)
            )
        if key == "current":
            return entry.seq == self.current_seq
        if key == "timeFull":
            full = format_full(entry.ts)
            if entry.count > 1:
                full += f"  (first {format_full(entry.first_ts)}, {entry.count} times)"
            return full
        if key == "isTraceback":
            return entry.is_traceback
        return getattr(entry, key, None)

    # ------------------------------------------------------------------ helpers for views
    def entry(self, row: int) -> LogEntry | None:
        """Entry shown in ``row``."""
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def row_of(self, entry: LogEntry) -> int:
        """Row of a visible entry, -1 when it is filtered out."""
        row = bisect_left(self._rows, entry.seq, key=lambda e: e.seq)
        if row < len(self._rows) and self._rows[row] is entry:
            return row
        return -1

    @property
    def total(self) -> int:
        """Entries in memory, visible or not."""
        return len(self._entries)

    @property
    def rows(self) -> list[LogEntry]:
        """Visible entries, in row order."""
        return self._rows

    @property
    def entries(self) -> list[LogEntry]:
        """All entries in memory, oldest first."""
        return self._entries

    def time_text(self, entry: LogEntry) -> str:
        """Time column text in the current time mode."""
        if self.time_mode == "relative":
            return format_relative(entry.ts)
        return format_clock(entry.ts)

    def level_color(self, level: str) -> QColor:
        """Cached theme colour of a level."""
        color = self._level_colors.get(level)
        if color is None:
            color = self._level_colors[level] = level_color(self.tokens, level)
        return color

    def level_ink(self, level: str) -> QColor:
        """Cached readable text colour of a level, for badges and counters."""
        color = self._level_inks.get(level)
        if color is None:
            color = self._level_inks[level] = ink(self.tokens, self.level_color(level))
        return color

    def service_color(self, service: str) -> QColor:
        """Cached colour of a service."""
        color = self._service_colors.get(service)
        if color is None:
            color = self._service_colors[service] = service_color(self.tokens, service)
        return color

    def row_tint(self, level: str) -> QColor | None:
        """Background tint of error and critical rows, None for the other levels."""
        return self._row_tint.get(level)

    def refresh_theme(self) -> None:
        """Re-read the theme colours."""
        self.tokens = ThemeTokens()
        self._level_colors.clear()
        self._level_inks.clear()
        self._service_colors.clear()
        self._row_tint = {
            "CRITICAL": self.tokens.soft(self.tokens.danger, 0.14 if self.tokens.dark else 0.09),
            "ERROR": self.tokens.soft(
                self.level_color("ERROR"), 0.10 if self.tokens.dark else 0.07
            ),
        }
        self._touch_all()

    def _touch_all(self, keys: Iterable[str] | None = None) -> None:
        if not self._rows:
            return
        roles = [self._role_ids[k] for k in keys] if keys else []
        self.dataChanged.emit(self.index(0, 0), self.index(len(self._rows) - 1, 0), roles)

    def _touch_entry(self, entry: LogEntry, keys: Iterable[str] | None = None) -> None:
        row = self.row_of(entry)
        if row >= 0:
            index = self.index(row, 0)
            roles = [self._role_ids[k] for k in keys] if keys else []
            self.dataChanged.emit(index, index, roles)

    # ------------------------------------------------------------------ filtering
    def _passes_common(self, entry: LogEntry) -> bool:
        if self.services is not None and entry.service not in self.services:
            return False
        if self._since_ts is not None and entry.ts < self._since_ts:
            return False
        if self.search_mode == "filter" and not self.matcher.matches(entry):
            return False
        return True

    def _accepts(self, entry: LogEntry) -> bool:
        return entry.group in self.groups and self._passes_common(entry)

    def refilter(self) -> None:
        """Rebuild the visible rows, the counts and the search matches from scratch."""
        counts = dict.fromkeys(GROUPS, 0)
        rows = []
        for entry in self._entries:
            if not self._passes_common(entry):
                continue
            counts[entry.group] = counts.get(entry.group, 0) + 1
            if entry.group in self.groups:
                rows.append(entry)
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()
        self.group_counts = counts
        self._rebuild_matches()
        self.counts_changed.emit()

    def _rebuild_matches(self) -> None:
        if self.search_mode == "highlight" and self.matcher.active:
            self._matches = [e for e in self._rows if self.matcher.matches(e)]
        else:
            self._matches = []
        self.match_pos = min(self.match_pos, len(self._matches) - 1)

    @property
    def match_count(self) -> int:
        """Number of search matches among the visible rows (highlight mode)."""
        return len(self._matches)

    def step_match(self, step: int) -> int:
        """Move to the next (``step=1``) or previous (``-1``) match; return its row or -1."""
        if not self._matches:
            return -1
        self.match_pos = (self.match_pos + step) % len(self._matches)
        entry = self._matches[self.match_pos]
        self.set_current(entry)
        return self.row_of(entry)

    def set_current(self, entry: LogEntry | None) -> None:
        """Mark one entry as the current row."""
        previous = self.current_seq
        self.current_seq = entry.seq if entry is not None else None
        if previous is not None:
            old = self._find(previous)
            if old is not None:
                self._touch_entry(old, ["current"])
        if entry is not None:
            self._touch_entry(entry, ["current"])

    def current_row(self) -> int:
        """Row of the current entry, -1 when there is none or it is filtered out."""
        if self.current_seq is None:
            return -1
        entry = self._find(self.current_seq)
        return -1 if entry is None else self.row_of(entry)

    def _find(self, seq: int) -> LogEntry | None:
        row = bisect_left(self._rows, seq, key=lambda e: e.seq)
        if row < len(self._rows) and self._rows[row].seq == seq:
            return self._rows[row]
        return None

    def set_since(self, key: str) -> None:
        """Only show entries newer than a preset age."""
        self.since_key = key if key in SINCE else "all"
        seconds = SINCE[self.since_key][1]
        self._since_ts = None if seconds is None else time.time() - seconds
        self.refilter()

    def reset_filters(self, matcher: SearchMatcher, mode: str) -> None:
        """Show every level, service and time, with the given (usually empty) search."""
        self.groups = set(GROUPS)
        self.services = None
        self.since_key = "all"
        self._since_ts = None
        self.set_search(matcher, mode)

    def set_search(self, matcher: SearchMatcher, mode: str) -> None:
        """Apply a new search."""
        self.matcher = matcher
        self.search_mode = mode
        self.match_pos = -1
        self.refilter()

    # ------------------------------------------------------------------ ingest
    def append_entries(self, entries: list[LogEntry]) -> int:
        """Add new entries, folding repeats. Returns the number of rows inserted."""
        fresh: list[LogEntry] = []
        last = self._entries[-1] if self._entries else None
        for entry in entries:
            if (
                last is not None
                and last.fold_key == entry.fold_key
                and 0 <= entry.ts - last.ts <= FOLD_WINDOW_S
            ):
                last.count += 1
                last.ts = entry.ts
                if not fresh or fresh[-1] is not last:
                    self._touch_entry(last, ["count", "time", "timeFull"])
                continue
            fresh.append(entry)
            self._entries.append(entry)
            last = entry
        if not fresh:
            return 0
        visible = []
        for entry in fresh:
            self.service_counts[entry.service] = self.service_counts.get(entry.service, 0) + 1
            if not self._passes_common(entry):
                continue
            self.group_counts[entry.group] = self.group_counts.get(entry.group, 0) + 1
            if entry.group in self.groups:
                visible.append(entry)
        if visible:
            first = len(self._rows)
            self.beginInsertRows(QModelIndex(), first, first + len(visible) - 1)
            self._rows.extend(visible)
            self.endInsertRows()
            if self.search_mode == "highlight" and self.matcher.active:
                self._matches.extend(e for e in visible if self.matcher.matches(e))
        self._trim()
        self.counts_changed.emit()
        return len(visible)

    def next_seq(self) -> int:
        """Sequence number for the next entry."""
        self._seq += 1
        return self._seq

    def _trim(self) -> None:
        overflow = len(self._entries) - self.max_entries
        if overflow < self.TRIM_CHUNK:
            return
        dropped = self._entries[:overflow]
        del self._entries[:overflow]
        cutoff = dropped[-1].seq
        for entry in dropped:
            self.service_counts[entry.service] -= 1
            if self.service_counts[entry.service] <= 0:
                del self.service_counts[entry.service]
            if self._passes_common(entry):
                self.group_counts[entry.group] -= 1
            self.expanded.discard(entry.seq)
        visible = bisect_left(self._rows, cutoff + 1, key=lambda e: e.seq)
        if visible:
            self.beginRemoveRows(QModelIndex(), 0, visible - 1)
            del self._rows[:visible]
            self.endRemoveRows()
        if self._matches:
            kept = bisect_left(self._matches, cutoff + 1, key=lambda e: e.seq)
            del self._matches[:kept]
            self.match_pos = max(-1, self.match_pos - kept)

    def clear(self) -> None:
        """Forget every entry."""
        self.beginResetModel()
        self._entries.clear()
        self._rows.clear()
        self._matches.clear()
        self.expanded.clear()
        self.match_pos = -1
        self.current_seq = None
        self.service_counts.clear()
        self.group_counts = dict.fromkeys(GROUPS, 0)
        self.endResetModel()
        self.counts_changed.emit()

    # ------------------------------------------------------------------ expand / time mode
    def toggle_expanded(self, row: int) -> bool:
        """Expand or collapse a multi-line entry. Returns the new state."""
        entry = self.entry(row)
        if entry is None or entry.line_count <= 1:
            return False
        if entry.seq in self.expanded:
            self.expanded.discard(entry.seq)
        else:
            self.expanded.add(entry.seq)
        self._touch_entry(entry, ["expanded", "bodyLines"])
        return entry.seq in self.expanded

    def set_time_mode(self, mode: str) -> None:
        """``clock`` or ``relative`` timestamps."""
        self.time_mode = mode
        self._touch_all(["time"])

    def tick(self) -> None:
        """Refresh relative timestamps."""
        if self.time_mode == "relative":
            self._touch_all(["time"])


class LogPanelBackend(QObject):
    """State and actions of the reworked log panel, shared by the QML and QWidget views.

    Args:
        parent: Parent QObject, usually the panel widget.
        use_queue(bool): Feed the panel from the shared ``BecLogsQueue`` (live BEC logs). Tests,
            demos and benchmarks pass False and call :meth:`ingest` directly.
        max_entries(int): Entries kept in memory.

    Signals:
        changed(): :attr:`state` changed.
        scroll_to_end(): The view should show the newest row (follow tail).
        reveal_row(int): The view should scroll to this row (search navigation).
        toast(str): Short feedback for the user, e.g. "Copied 3 lines".
        focus_search(): The view should focus its search field (Ctrl+F).
    """

    changed = Signal()
    scroll_to_end = Signal()
    reveal_row = Signal(int)
    toast = Signal(str)
    focus_search = Signal()

    SEARCH_DEBOUNCE_MS = 150

    def __init__(self, parent: QObject | None = None, use_queue: bool = True, max_entries=20000):
        super().__init__(parent)
        self.model = LogFeedModel(max_entries=max_entries, parent=self)
        self._state: dict = {}
        self._search_text = ""
        self._search_mode = "filter"
        self._regex = False
        self.paused = False
        self._pending: list[Any] = []
        self.follow = True
        self.new_below = 0
        self._queue = None
        self._search_timer = QTimer(self, singleShot=True, interval=self.SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._apply_search)
        self._tick_timer = QTimer(self, interval=10000)
        self._tick_timer.timeout.connect(self.model.tick)
        self.model.counts_changed.connect(self._publish)
        self.model.rowsInserted.connect(self._on_rows_inserted)
        if use_queue:
            self._attach_queue()
        self._publish()

    # ------------------------------------------------------------------ data in
    def _attach_queue(self) -> None:
        # pylint: disable=import-outside-toplevel
        from bec_widgets.widgets.utility.logpanel.logpanel import BecLogsQueue

        self._queue = BecLogsQueue.instance()
        self._queue.attach()
        self.ingest(self._queue.snapshot_records())
        self._queue.new_records.connect(self.ingest)

    @Slot(list)
    def ingest(self, records: list) -> None:
        """Add ``logpanel._LogRec`` records or ready :class:`LogEntry` objects."""
        if self.paused:
            self._pending.extend(records)
            self._publish()
            return
        entries = [
            r if isinstance(r, LogEntry) else LogEntry.from_record(r, self.model.next_seq())
            for r in records
        ]
        self.model.append_entries(entries)

    def _on_rows_inserted(self, _parent, first: int, last: int) -> None:
        if self.follow:
            self.scroll_to_end.emit()
        else:
            self.new_below += last - first + 1
            self._publish()

    # ------------------------------------------------------------------ state for the views
    @property
    def state(self) -> dict:
        """Everything the views need to render the toolbar, chips and banners."""
        return self._state

    def _publish(self) -> None:
        model = self.model
        tokens = model.tokens
        groups = [
            {
                "key": key,
                "label": label,
                "count": model.group_counts.get(key, 0),
                "active": key in model.groups,
                "color": group_color(tokens, key),
                "ink": ink(tokens, group_color(tokens, key)),
            }
            for key, label in GROUPS.items()
        ]
        services = [
            {
                "name": name,
                "count": count,
                "active": model.services is None or name in model.services,
                "color": model.service_color(name),
            }
            for name, count in sorted(model.service_counts.items(), key=lambda kv: kv[0].lower())
        ]
        if model.services is None:
            services_label = "All services"
        elif len(model.services) == 1:
            services_label = next(iter(model.services))
        else:
            services_label = f"{len(model.services)} services"
        filtered = (
            model.groups != set(GROUPS)
            or model.services is not None
            or model.since_key != "all"
            or (self._search_mode == "filter" and model.matcher.active)
        )
        self._state = {
            "groups": groups,
            "services": services,
            "servicesLabel": services_label,
            "servicesFiltered": model.services is not None,
            "since": model.since_key,
            "sinceLabel": SINCE[model.since_key][0],
            "sinceOptions": [{"key": k, "label": v[0]} for k, v in SINCE.items()],
            "search": self._search_text,
            "searchMode": self._search_mode,
            "regex": self._regex,
            "regexError": model.matcher.error,
            "matchCount": model.match_count,
            "matchPos": model.match_pos + 1,
            "shown": model.rowCount(),
            "total": model.total,
            "summary": self._summary_text(filtered),
            "filtered": filtered,
            "paused": self.paused,
            "pending": len(self._pending),
            "follow": self.follow,
            "newBelow": self.new_below,
            "timeMode": model.time_mode,
            "empty": model.total == 0,
            "exceptionInk": model.level_ink("ERROR"),
        }
        self.changed.emit()

    def _summary_text(self, filtered: bool) -> str:
        shown, total = self.model.rowCount(), self.model.total
        if not filtered:
            return f"{total:,} entries"
        return f"{shown:,} of {total:,} entries"

    # ------------------------------------------------------------------ filters
    # pylint: disable=invalid-name,missing-function-docstring
    @Slot(str)
    def toggleGroup(self, key: str) -> None:
        groups = set(self.model.groups)
        groups ^= {key}
        self.model.groups = groups
        self.model.refilter()

    @Slot(str)
    def soloGroup(self, key: str) -> None:
        self.model.groups = {key} if self.model.groups != {key} else set(GROUPS)
        self.model.refilter()

    @Slot(str)
    def toggleService(self, name: str) -> None:
        current = (
            set(self.model.service_counts)
            if self.model.services is None
            else set(self.model.services)
        )
        current ^= {name}
        self._set_services(None if current >= set(self.model.service_counts) else current)

    @Slot(str)
    def soloService(self, name: str) -> None:
        self._set_services({name})

    @Slot(str)
    def hideService(self, name: str) -> None:
        current = (
            set(self.model.service_counts)
            if self.model.services is None
            else set(self.model.services)
        )
        self._set_services(current - {name})

    @Slot()
    def allServices(self) -> None:
        self._set_services(None)

    def _set_services(self, services: set[str] | None) -> None:
        self.model.services = services
        self.model.refilter()

    @Slot(str)
    def setSince(self, key: str) -> None:
        self.model.set_since(key)

    @Slot(str)
    def setSearch(self, text: str) -> None:
        self._search_text = text
        if text:
            self._search_timer.start()
        else:
            self._search_timer.stop()
            self._apply_search()

    @Slot(str)
    def setSearchMode(self, mode: str) -> None:
        self._search_mode = "highlight" if mode == "highlight" else "filter"
        self._apply_search()

    @Slot(bool)
    def setRegex(self, regex: bool) -> None:
        self._regex = regex
        self._apply_search()

    def _apply_search(self) -> None:
        self._search_timer.stop()
        self.model.set_search(SearchMatcher(self._search_text, self._regex), self._search_mode)
        if self.follow:
            self.scroll_to_end.emit()

    @Slot()
    def nextMatch(self) -> None:
        self._step_match(1)

    @Slot()
    def prevMatch(self) -> None:
        self._step_match(-1)

    def _step_match(self, step: int) -> None:
        # stop following first so a pending search does not scroll back to the newest row
        self.follow = False
        if self._search_timer.isActive():
            self._apply_search()
        row = self.model.step_match(step)
        if row >= 0:
            self.reveal_row.emit(row)
        self._publish()

    @Slot()
    def resetFilters(self) -> None:
        self._search_text = ""
        self.model.reset_filters(SearchMatcher(""), self._search_mode)

    # ------------------------------------------------------------------ live / follow
    @Slot()
    def togglePause(self) -> None:
        self.setPaused(not self.paused)

    @Slot(bool)
    def setPaused(self, paused: bool) -> None:
        if paused == self.paused:
            return
        self.paused = paused
        if not paused and self._pending:
            pending, self._pending = self._pending, []
            self.ingest(pending)
        self._publish()

    @Slot(bool)
    def setFollow(self, follow: bool) -> None:
        if follow == self.follow:
            return
        self.follow = follow
        if follow:
            self.new_below = 0
        self._publish()

    @Slot(result=bool)
    def isFollowing(self) -> bool:
        """Whether the view should keep showing the newest row (read by QML)."""
        return self.follow

    @Slot()
    def jumpToLatest(self) -> None:
        self.follow = True
        self.new_below = 0
        self.scroll_to_end.emit()
        self._publish()

    # ------------------------------------------------------------------ rows
    @Slot(int)
    def toggleExpanded(self, row: int) -> None:
        self.model.toggle_expanded(row)

    @Slot(int)
    def setCurrent(self, row: int) -> None:
        self.model.set_current(self.model.entry(row))

    @Slot(int)
    def copyRow(self, row: int) -> None:
        entry = self.model.entry(row)
        if entry is not None:
            self._to_clipboard(entry.copy_text(), "Copied 1 entry")

    @Slot(int)
    def copyMessage(self, row: int) -> None:
        entry = self.model.entry(row)
        if entry is not None:
            self._to_clipboard(entry.message, "Copied message")

    def copy_rows(self, rows: Iterable[int]) -> None:
        """Copy several rows, e.g. a QWidget multi-selection."""
        entries = [e for e in (self.model.entry(r) for r in sorted(rows)) if e is not None]
        if entries:
            self._to_clipboard(
                "\n".join(e.copy_text() for e in entries), f"Copied {len(entries)} entries"
            )

    @Slot()
    def copyVisible(self) -> None:
        self.copy_rows(range(self.model.rowCount()))

    def visible_text(self) -> str:
        """Plain text of every visible row."""
        return "\n".join(e.copy_text() for e in self.model.rows)

    @Slot()
    def exportVisible(self) -> None:
        default = f"bec_logs_{datetime.now():%Y%m%d_%H%M%S}.log"
        path, _ = QFileDialog.getSaveFileName(
            None, "Export logs", default, "Log files (*.log *.txt)"
        )
        if path:
            self.export_to(Path(path))

    def export_to(self, path: Path) -> None:
        """Write the visible rows to ``path``."""
        path.write_text(self.visible_text() + "\n", encoding="utf-8")
        self.toast.emit(f"Saved {self.model.rowCount():,} entries to {path.name}")

    def _to_clipboard(self, text: str, message: str) -> None:
        QApplication.clipboard().setText(text)
        self.toast.emit(message)

    @Slot()
    def clear(self) -> None:
        self._pending.clear()
        self.new_below = 0
        self.model.clear()

    @Slot()
    def toggleTimeMode(self) -> None:
        mode = "relative" if self.model.time_mode == "clock" else "clock"
        self.model.set_time_mode(mode)
        if mode == "relative":
            self._tick_timer.start()
        else:
            self._tick_timer.stop()
        self._publish()

    def refresh_theme(self) -> None:
        """Re-read theme colours after a theme switch."""
        self.model.refresh_theme()
        self._publish()

    def cleanup(self) -> None:
        """Stop timers and detach from the shared log queue."""
        self._search_timer.stop()
        self._tick_timer.stop()
        if self._queue is not None:
            try:
                self._queue.new_records.disconnect(self.ingest)
            except (RuntimeError, TypeError):
                pass
            self._queue.detach()
            self._queue = None

    stateMap = Property("QVariantMap", lambda self: self._state, notify=changed)
    feed = Property(QObject, lambda self: self.model, constant=True)


def make_entries(model: LogFeedModel, specs: Iterable[tuple]) -> list[LogEntry]:
    """Build entries from ``(level, ts, service, message[, function])`` tuples (demos and tests)."""
    return [LogEntry(model.next_seq(), *spec) for spec in specs]
