"""
Data layer of the BEC queue widget: turns queue status, queue history and scan progress into rows
for the QML view, and exposes queue state and actions to QML through :class:`QueueController`.

Nothing here talks to BEC directly; the widget shell feeds messages in and performs the requests
the controller emits. That keeps this module testable without a client.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field, fields

from bec_lib import messages
from qtpy.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    Qt,
    Signal,
    Slot,
)

ACTIVE_STATUSES = ("RUNNING", "PAUSED", "DEFERRED_PAUSE")
WAITING_STATUSES = ("PENDING", "IDLE")
IDLE_STATUSES = ("STOPPED", "COMPLETED", "IDLE")

# status -> (label, tone, material icon). Tones map to theme colours in QML; colour is only used
# for states that need attention, normal states stay neutral.
STATE_STYLES: dict[str, tuple[str, str, str]] = {
    "RUNNING": ("Running", "busy", "play_arrow"),
    "DEFERRED_PAUSE": ("Pausing", "warn", "pause"),
    "PAUSED": ("Paused", "warn", "pause"),
    "PENDING": ("Queued", "neutral", "schedule"),
    "IDLE": ("Queued", "neutral", "schedule"),
    "COMPLETED": ("Done", "ok", "check"),
    "STOPPED": ("Stopped", "warn", "stop"),
    "CANCELLED": ("Removed", "stale", "close"),
}
REASON_LABELS = {"user": "by user", "alarm": "alarm", "restart": "restarted"}


@dataclass
class QueueRow:  # pylint: disable=too-many-instance-attributes
    """One row of the queue view."""

    key: str
    section: str  # "Now", "Waiting" or "Recent"
    queue_id: str
    request_id: str = ""
    scan_id: str = ""
    scan_number: str = ""
    title: str = ""
    subtitle: str = ""
    sample: str = ""
    status: str = ""
    state_label: str = ""
    tone: str = "neutral"
    icon: str = "help"
    details: str = ""
    can_move_up: bool = False
    can_move_down: bool = False
    progress: float = -1.0
    progress_text: str = ""
    removing: bool = False
    extra: dict = field(default_factory=dict)


def _fmt_num(value) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def describe_parameters(msg: messages.ScanQueueMessage) -> str:
    """
    Summarise a scan request in one short line, e.g. ``samx −5 → 5 · 41 steps · 0.1 s``.

    Args:
        msg(messages.ScanQueueMessage): The scan request.

    Returns:
        str: The summary; empty if nothing useful can be said.
    """
    parameter = msg.parameter or {}
    args = parameter.get("args", {})
    kwargs = parameter.get("kwargs", {})
    parts: list[str] = []
    if isinstance(args, dict):
        for device, values in list(args.items())[:3]:
            if isinstance(values, (list, tuple)) and len(values) >= 2:
                text = f"{device} {_fmt_num(values[0])} → {_fmt_num(values[1])}"
                if len(values) >= 3:
                    text += f" ({_fmt_num(values[2])})"
                parts.append(text.replace("-", "−"))
            else:
                parts.append(str(device))
    if "steps" in kwargs:
        parts.append(f"{kwargs['steps']} steps")
    elif "step" in kwargs:
        parts.append(f"step {_fmt_num(kwargs['step'])}")
    if "exp_time" in kwargs:
        parts.append(f"{_fmt_num(kwargs['exp_time'])} s")
    if kwargs.get("relative"):
        parts.append("relative")
    return " · ".join(parts)


def _fmt_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    if seconds >= 3600:
        return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
    return f"{seconds // 60}:{seconds % 60:02d}"


@dataclass
class ProgressState:
    """Latest progress of the running scan, as received from the scan_progress endpoint."""

    scan_id: str | None = None
    value: float = 0
    max_value: float = 0
    started: float = 0.0
    updated: float = 0.0

    def fraction(self) -> float:
        """Return the progress as a fraction, or -1 if unknown."""
        if self.max_value <= 0:
            return -1.0
        return max(0.0, min(1.0, self.value / self.max_value))

    def text(self) -> str:
        """Return e.g. ``12 / 41 · 0:35 · ≈ 1:20 left``."""
        if self.max_value <= 0:
            return ""
        out = f"{int(self.value)} / {int(self.max_value)}"
        elapsed = self.updated - self.started
        if elapsed > 0:
            out += f" · {_fmt_duration(elapsed)}"
            if 0 < self.value < self.max_value:
                remaining = elapsed / self.value * (self.max_value - self.value)
                out += f" · ≈ {_fmt_duration(remaining)} left"
        return out


def _entry_row(  # pylint: disable=too-many-locals
    entry: messages.QueueInfoEntry, section: str, status: str
) -> QueueRow:
    titles, types, numbers, subtitles, samples, metadata, rids = [], [], [], [], [], [], []
    for block in entry.request_blocks:
        msg = block.msg
        user_metadata = msg.metadata.get("user_metadata", {}) or {}
        types.append(msg.scan_type)
        titles.append(user_metadata.get("scan_name") or msg.scan_type)
        if block.scan_number is not None:
            numbers.append(str(block.scan_number))
        if summary := describe_parameters(msg):
            subtitles.append(summary)
        if sample := user_metadata.get("sample_name"):
            samples.append(str(sample))
        if user_metadata:
            metadata.append(user_metadata)
        if block.RID:
            rids.append(block.RID)

    label, tone, icon = STATE_STYLES.get(status, (status.title() or "Unknown", "stale", "help"))
    if status == "STOPPED" and entry.reason:
        label = "Aborted" if entry.reason == "user" else "Stopped"
        label += f" · {REASON_LABELS.get(entry.reason, entry.reason)}"
        tone = "err" if entry.reason == "alarm" else "warn"

    title = ", ".join(dict.fromkeys(titles))
    subtitle_parts = []
    if title not in types:
        subtitle_parts.append(", ".join(types))
    subtitle_parts.extend(subtitles)
    details = ""
    if metadata:
        details = json.dumps(metadata[0] if len(metadata) == 1 else metadata, indent=2)
    scan_ids = [sid for sid in entry.scan_id if sid]
    return QueueRow(
        key=f"{section}:{entry.queue_id}",
        section=section,
        queue_id=entry.queue_id,
        request_id=rids[0] if rids else "",
        scan_id=scan_ids[0] if scan_ids else "",
        scan_number=", ".join(numbers),
        title=title,
        subtitle=" · ".join(subtitle_parts),
        sample=", ".join(dict.fromkeys(samples)),
        status=status,
        state_label=label,
        tone=tone,
        icon=icon,
        details=details,
    )


def build_rows(
    queue: messages.ScanQueueStatus | None,
    history: list[messages.ScanQueueHistoryMessage],
    progress: ProgressState | None = None,
    removing: set[str] | None = None,
    max_recent: int = 5,
) -> list[QueueRow]:
    """
    Build the rows of the queue view.

    Args:
        queue(messages.ScanQueueStatus | None): The primary queue, if any.
        history(list[messages.ScanQueueHistoryMessage]): Finished queue items, newest first.
        progress(ProgressState | None): Progress of the running scan.
        removing(set[str] | None): Request ids with a pending remove request.
        max_recent(int): Number of history rows to show.

    Returns:
        list[QueueRow]: Rows in display order: Now, Waiting, Recent.
    """
    removing = removing or set()
    now_rows: list[QueueRow] = []
    waiting_rows: list[QueueRow] = []
    in_queue: set[str] = set()
    for entry in queue.info if queue else []:
        in_queue.add(entry.queue_id)
        status = entry.status
        if status in WAITING_STATUSES:
            waiting_rows.append(_entry_row(entry, "Waiting", status))
        else:
            row = _entry_row(entry, "Now", status)
            if progress and status in ACTIVE_STATUSES:
                if progress.scan_id is None or progress.scan_id in entry.scan_id:
                    row.progress = progress.fraction()
                    row.progress_text = progress.text()
            now_rows.append(row)
    for index, row in enumerate(waiting_rows):
        row.can_move_up = index > 0 and bool(row.scan_id)
        row.can_move_down = index < len(waiting_rows) - 1 and bool(row.scan_id)
        row.removing = row.request_id in removing
    for row in now_rows:
        row.removing = row.request_id in removing

    recent_rows: list[QueueRow] = []
    for msg in history:
        if len(recent_rows) >= max_recent:
            break
        if msg.queue_id in in_queue:
            continue
        recent_rows.append(_entry_row(msg.info, "Recent", msg.status))
    return now_rows + waiting_rows + recent_rows


class QueueListModel(QAbstractListModel):
    """
    List model of :class:`QueueRow` items.

    Updates are applied as inserts, moves and removals keyed by row, so QML can animate them and
    keep hover and focus on rows that did not change.
    """

    ROLE_NAMES = [f.name for f in fields(QueueRow) if f.name != "extra"]

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._rows: list[QueueRow] = []
        self._roles = {Qt.ItemDataRole.UserRole + i: n for i, n in enumerate(self.ROLE_NAMES)}

    # pylint: disable=invalid-name
    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the number of rows."""
        return 0 if parent.isValid() else len(self._rows)

    def roleNames(self) -> dict[int, QByteArray]:
        """Return the QML role names: the QueueRow fields in camelCase."""
        return {role: QByteArray(_camel(name).encode()) for role, name in self._roles.items()}

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Return the value of ``role`` for the row at ``index``."""
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        name = self._roles.get(role)
        if name is None:
            return None
        return getattr(self._rows[index.row()], name)

    def rows(self) -> list[QueueRow]:
        """Return a copy of the current rows."""
        return list(self._rows)

    def set_rows(self, new_rows: list[QueueRow]):
        """
        Replace the rows with ``new_rows`` using minimal inserts, moves and removals.

        Args:
            new_rows(list[QueueRow]): The rows to show.
        """
        new_keys = {row.key for row in new_rows}
        for i in reversed(range(len(self._rows))):
            if self._rows[i].key not in new_keys:
                self.beginRemoveRows(QModelIndex(), i, i)
                del self._rows[i]
                self.endRemoveRows()
        for target, row in enumerate(new_rows):
            current = [r.key for r in self._rows]
            if target < len(current) and current[target] == row.key:
                if asdict(self._rows[target]) != asdict(row):
                    self._rows[target] = row
                    idx = self.index(target)
                    self.dataChanged.emit(idx, idx)
                continue
            if row.key in current:
                source = current.index(row.key)
                self.beginMoveRows(QModelIndex(), source, source, QModelIndex(), target)
                moved = self._rows.pop(source)
                self._rows.insert(target, moved)
                self.endMoveRows()
                self._rows[target] = row
                idx = self.index(target)
                self.dataChanged.emit(idx, idx)
            else:
                self.beginInsertRows(QModelIndex(), target, target)
                self._rows.insert(target, row)
                self.endInsertRows()


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


class QueueController(QObject):
    """
    State and actions of the queue view, exposed to QML as ``queue``.

    The widget shell feeds it with :meth:`set_queue`, :meth:`set_history` and
    :meth:`set_progress`, and connects the ``*_requested`` signals to BEC requests.
    """

    changed = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    abort_requested = Signal(str)
    halt_requested = Signal()
    remove_requested = Signal(str)
    move_requested = Signal(str, str)
    clear_requested = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._model = QueueListModel(self)
        self._queue: messages.ScanQueueStatus | None = None
        self._history: list[messages.ScanQueueHistoryMessage] = []
        self._progress = ProgressState()
        self._removing: set[str] = set()
        self._show_recent = True
        self._toolbar_visible = True

    # ------------------------------------------------------------------ inputs

    def set_queue(self, queue: messages.ScanQueueStatus | None):
        """Set the primary queue status. Clears pending removals: the server has answered."""
        self._queue = queue
        self._removing.clear()
        self._rebuild()

    def set_history(self, history: list[messages.ScanQueueHistoryMessage]):
        """Set the queue history, newest first."""
        self._history = list(history)
        self._rebuild()

    def set_progress(self, scan_id: str | None, value: float, max_value: float, done: bool):
        """Update the progress of the running scan."""
        now = time.monotonic()
        if scan_id != self._progress.scan_id or not self._progress.started:
            self._progress = ProgressState(scan_id=scan_id, started=now)
        self._progress.value = value
        self._progress.max_value = max_value
        self._progress.updated = now
        if done:
            self._progress = ProgressState()
        self._rebuild()

    def _rebuild(self):
        self._model.set_rows(
            build_rows(
                self._queue,
                self._history if self._show_recent else [],
                self._progress,
                self._removing,
            )
        )
        self.changed.emit()

    # ------------------------------------------------------------------ derived state

    def current_row(self) -> QueueRow | None:
        """Return the row of the running scan, if any."""
        return next((r for r in self._model.rows() if r.section == "Now"), None)

    def _get_state(self) -> str:
        if self._queue is None:
            return "idle"
        if self._queue.status == "LOCKED":
            return "locked"
        if self._queue.status == "PAUSED":
            return "paused"
        if any(e.status in ACTIVE_STATUSES for e in self._queue.info):
            return "running"
        return "idle"

    def _get_lock_reason(self) -> str:
        if self._queue is None:
            return ""
        return "; ".join(lock.reason for lock in self._queue.locks if lock.reason)

    def _count(self, section: str) -> int:
        return sum(1 for r in self._model.rows() if r.section == section)

    def _get_model(self) -> QueueListModel:
        return self._model

    def _running_count(self) -> int:
        return self._count("Now")

    def _waiting_count(self) -> int:
        return self._count("Waiting")

    def _recent_count(self) -> int:
        return self._count("Recent")

    def _current_label(self) -> str:
        row = self.current_row()
        if row is None:
            return ""
        return f"scan {row.scan_number}" if row.scan_number else row.title

    def _get_last_finished(self) -> str:
        if not self._history:
            return ""
        last = _entry_row(self._history[0].info, "Recent", self._history[0].status)
        name = f"scan {last.scan_number}" if last.scan_number else last.title
        return f"{name} · {last.state_label.lower()}"

    def _get_show_recent(self) -> bool:
        return self._show_recent

    def _set_show_recent(self, value: bool):
        if value != self._show_recent:
            self._show_recent = value
            self._rebuild()

    def _get_toolbar_visible(self) -> bool:
        return self._toolbar_visible

    def set_toolbar_visible(self, value: bool):
        """Show or hide the header bar with the queue state and controls."""
        if value != self._toolbar_visible:
            self._toolbar_visible = value
            self.changed.emit()

    # pylint: disable=missing-function-docstring
    model = Property(QObject, _get_model, constant=True)
    state = Property(str, _get_state, notify=changed)
    lockReason = Property(str, _get_lock_reason, notify=changed)
    runningCount = Property(int, _running_count, notify=changed)
    waitingCount = Property(int, _waiting_count, notify=changed)
    recentCount = Property(int, _recent_count, notify=changed)
    currentLabel = Property(str, _current_label, notify=changed)
    lastFinished = Property(str, _get_last_finished, notify=changed)
    showRecent = Property(bool, _get_show_recent, _set_show_recent, notify=changed)
    toolbarVisible = Property(bool, _get_toolbar_visible, set_toolbar_visible, notify=changed)

    # ------------------------------------------------------------------ actions from QML

    @Slot()
    def pause(self):
        self.pause_requested.emit()

    @Slot()
    def resume(self):
        self.resume_requested.emit()

    @Slot()
    def abortCurrent(self):  # pylint: disable=invalid-name
        row = self.current_row()
        self.abort_requested.emit(row.request_id if row else "")

    @Slot()
    def halt(self):
        self.halt_requested.emit()

    @Slot(str)
    def remove(self, request_id: str):
        if not request_id:
            return
        self._removing.add(request_id)
        self._rebuild()
        self.remove_requested.emit(request_id)

    @Slot(str)
    def moveUp(self, scan_id: str):  # pylint: disable=invalid-name
        if scan_id:
            self.move_requested.emit(scan_id, "move_up")

    @Slot(str)
    def moveDown(self, scan_id: str):  # pylint: disable=invalid-name
        if scan_id:
            self.move_requested.emit(scan_id, "move_down")

    @Slot()
    def clear(self):
        self.clear_requested.emit()
