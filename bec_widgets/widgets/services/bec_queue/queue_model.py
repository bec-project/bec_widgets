"""
Scan queue model of the BECQueue widget: parses the queue status and history, and sends the
queue actions (reorder, remove, rerun, pause, resume).
"""

from __future__ import annotations

import copy
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from bec_lib import messages
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject, QThreadPool, QTimer, Signal

from bec_widgets.utils.bec_connector import Worker
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.progress.scan_progressbar.scan_ui import (
    args_summary,
    metadata_items,
    rpc_call,
    scan_bundle_names,
    scan_display_name,
)
from bec_widgets.widgets.progress.stage_bar import Tone

logger = bec_logger.logger

RUNNING_STATUSES = ("RUNNING", "PAUSED", "DEFERRED_PAUSE")
WAITING_STATUSES = ("PENDING", "IDLE")


class QueueAction(StrEnum):
    """The kind of a queue action, sent with action_sent and action_failed."""

    MOVE = "move"
    REMOVE = "remove"
    RERUN = "rerun"
    PAUSE = "pause"
    RESUME = "resume"
    RESET = "reset"


class QueueMove(StrEnum):
    """Where a waiting scan is moved."""

    UP = "up"
    DOWN = "down"
    TOP = "top"
    BOTTOM = "bottom"


# History status -> (icon name, tone, tooltip word)
HISTORY_STATUS = {
    "COMPLETED": ("check_circle", Tone.OK, "Completed"),
    "closed": ("check_circle", Tone.OK, "Completed"),
    "user_completed": ("flag_circle", Tone.ACCENT, "Finished early"),
    "STOPPED": ("cancel", Tone.BAD, "Stopped"),
    "aborted": ("cancel", Tone.BAD, "Aborted"),
    "halted": ("dangerous", Tone.BAD, "Halted"),
    "CANCELLED": ("block", Tone.NEUTRAL, "Removed before it started"),
}


_REQUEST_ONLY_METADATA = ("RID", "scan_id", "queue_id", "client_info")


@dataclass
class QueueEntry:
    """One queue item, waiting, running or finished."""

    queue_id: str
    status: str
    scan_type: str
    name: str
    args: str = ""
    bundle_names: list[str] = field(default_factory=list)
    metadata: list[tuple[str, str]] = field(default_factory=list)
    rid: str | None = None
    scan_id: str | None = None
    scan_number: int | None = None
    blocks: int = 1
    position: int = 0
    request: Any = None
    exit_status: str | None = None
    started_at: float | None = None
    finished_at: float | None = None

    @property
    def key(self) -> str:
        """Stable identity of the entry across queue updates."""
        return self.queue_id

    @property
    def rpc_command(self) -> str:
        """Formatted command for a device RPC with a known target."""
        if self.scan_type != "device_rpc":
            return ""
        parameter = getattr(self.request, "parameter", None) or {}
        return rpc_call(parameter.get("kwargs"))

    @property
    def rpc_arguments(self) -> str:
        """Formatted arguments without the command name or outer parentheses."""
        return self.rpc_command.partition("(")[2][:-1]

    @property
    def title(self) -> str:
        """Display title, such as "#12 line_scan" or "line_scan +2"."""
        if command := self.rpc_command:
            return command.partition("(")[0]
        number = f"#{self.scan_number} " if self.scan_number is not None else ""
        more = f" +{self.blocks - 1}" if self.blocks > 1 else ""
        return f"{number}{self.name}{more}"

    @property
    def duration(self) -> float | None:
        """Seconds between start and end, if both were seen."""
        if self.started_at is None or self.finished_at is None:
            return None
        return max(0.0, self.finished_at - self.started_at)

    @property
    def history_status(self) -> tuple[str, str, str]:
        """(icon, tone, word) for a finished entry."""
        key = self.exit_status or self.status
        return HISTORY_STATUS.get(key, HISTORY_STATUS.get(self.status, ("help", Tone.NEUTRAL, key)))

    @property
    def can_rerun(self) -> bool:
        """Whether the original scan request is known, so it can be sent again."""
        return self.request is not None and bool(getattr(self.request, "scan_type", None))


def _entry_from_info(info: Any, position: int = 0, scans: Any = None) -> QueueEntry | None:
    blocks = list(getattr(info, "request_blocks", None) or [])
    first = blocks[0] if blocks else None
    request = getattr(first, "msg", None) if first is not None else None
    scan_type = getattr(request, "scan_type", "") or ""
    metadata = dict(getattr(request, "metadata", {}) or {})
    user_metadata = dict(metadata.get("user_metadata") or {})
    scan_ids = list(getattr(info, "scan_id", None) or [])
    scan_id = getattr(first, "scan_id", None) or (scan_ids[0] if scan_ids else None)
    scan_numbers = [n for n in (getattr(info, "scan_number", None) or []) if n is not None]
    scan_number = getattr(first, "scan_number", None)
    if scan_number is None and scan_numbers:
        scan_number = scan_numbers[0]
    bundle_names = scan_bundle_names(scans, scan_type)
    return QueueEntry(
        queue_id=getattr(info, "queue_id", ""),
        status=str(getattr(info, "status", "")),
        scan_type=scan_type,
        name=scan_display_name(user_metadata, scan_type, fallback="request"),
        args=args_summary(getattr(request, "parameter", None), bundle_names),
        bundle_names=bundle_names,
        metadata=metadata_items(user_metadata),
        rid=getattr(first, "RID", None) or metadata.get("RID"),
        scan_id=scan_id,
        scan_number=scan_number,
        blocks=max(1, len(blocks)),
        position=position,
        request=request,
    )


class _ReadResult(QObject):
    """Carries the result of a background queue read to the GUI thread."""

    done = Signal(int, object)


def _read_queue_state(
    connector,
    result: _ReadResult,
    generation: int,
    with_queue: bool,
    known: set,
    count: int,
    scans: Any = None,
) -> None:
    """
    Read the queue status, the queue history and, for scans not in known, the scan history
    times. Runs in the thread pool: only Redis reads and message decoding, no Qt objects.
    """
    payload: dict = {"queue": None, "history": None, "times": {}, "missing": set()}
    if with_queue:
        try:
            msg = connector.get(MessageEndpoints.scan_queue_status())
        except Exception:  # pylint: disable=broad-except
            msg = None
        if msg is not None and hasattr(msg, "content"):
            payload["queue"] = msg.content
    try:
        history = connector.lrange(MessageEndpoints.scan_queue_history(), 0, count - 1)
    except Exception:  # pylint: disable=broad-except
        logger.debug("Could not read the queue history")
        history = None
    if history is not None:
        finished = []
        for item in history:
            info = getattr(item, "info", None)
            if info is None:
                continue
            entry = _entry_from_info(info, scans=scans)
            if entry is None:
                continue
            entry.status = str(getattr(item, "status", entry.status))
            finished.append(entry)
        payload["history"] = finished
        missing = {e.scan_id for e in finished if e.scan_id and e.scan_id not in known}
        if missing:
            times = _read_history_times(connector, count)
            if times is not None:
                # the file writer can publish a scan's history entry after the queue moved it
                # to the history, so a scan not found yet is looked up again by the model
                payload["times"] = {sid: times[sid] for sid in missing if sid in times}
                payload["missing"] = missing - set(times)
    try:
        result.done.emit(generation, payload)
    except RuntimeError:
        logger.debug("Queue read finished after its model was deleted")


def _read_history_times(connector, count: int) -> dict | None:
    try:
        msgs = connector.get_last(MessageEndpoints.scan_history(), key="data", count=count)
    except Exception:  # pylint: disable=broad-except
        logger.debug("Could not read the scan history")
        return None
    if msgs is None:
        msgs = []
    elif not isinstance(msgs, list):
        msgs = [msgs]
    return {
        getattr(m, "scan_id", None): (
            getattr(m, "start_time", None),
            getattr(m, "end_time", None),
            getattr(m, "exit_status", None),
        )
        for m in msgs
    }


class ScanQueueModel(QObject):
    """
    Follows the primary scan queue and its history.

    Signals:
        changed(): The running, waiting or finished lists changed.
        action_sent(QueueAction, str, str): (kind, entry key, message) after an action was sent;
            kind is move, remove, rerun, pause, resume or reset.
        action_failed(QueueAction, str, str): (kind, entry key, reason) when an action was
            refused.
    """

    changed = Signal()
    # object, not str: a str signal would hand the slots a plain str instead of the QueueAction
    action_sent = Signal(object, str, str)
    action_failed = Signal(object, str, str)

    HISTORY_LENGTH = 50
    # a scan not in BEC's scan history yet is looked up again this often, at most this many times
    HISTORY_RETRY_MS = 3000
    HISTORY_RETRIES = 5
    MOVE_CONFIRM_S = 3.0

    def __init__(self, client, bec_dispatcher, parent: QObject | None = None):
        super().__init__(parent=parent)
        self.client = client
        self.bec_dispatcher = bec_dispatcher
        self.running: QueueEntry | None = None
        self.waiting: list[QueueEntry] = []
        self.finished: list[QueueEntry] = []
        self.queue_state: str = "RUNNING"
        self._queue_offset = 0
        self._known_ids: set[str] = set()
        self._scan_times: dict[str, dict] = {}
        self._history_times: dict[str, tuple] = {}
        self._history_misses: dict[str, int] = {}
        self.last_rerun_rid: str | None = None
        # moves sent and not answered yet, oldest first, as (key, deadline)
        self._pending_moves: deque[tuple[str, float]] = deque()
        self._server_waiting: list[QueueEntry] = []
        self._wanted_order: list[str] | None = None
        self._wanted_until = 0.0
        self._connected = False
        # Redis reads run in the thread pool; a result is used only if its generation is current
        self.loaded = False
        # parented, so it is deleted with the model on the GUI thread, never in the thread pool
        self._read_result = _ReadResult(self)
        self._read_result.done.connect(self._on_read_done)
        self._history_retry = QTimer(self)
        self._history_retry.setSingleShot(True)
        self._history_retry.setInterval(self.HISTORY_RETRY_MS)
        self._history_retry.timeout.connect(self.reload_history)
        self._read_generation = 0
        self._reading = False
        self._read_again = False
        self._read_queue_again = False
        self._queue_updates = 0
        self._read_queue_mark = 0
        self._worker: Worker | None = None

    ################################################################################
    # Subscriptions
    ################################################################################

    def start(self) -> None:
        """Subscribe to queue and scan status and load the current state."""
        if self._connected:
            return
        self.bec_dispatcher.connect_slot(self.on_queue_status, MessageEndpoints.scan_queue_status())
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.bec_dispatcher.connect_slot(
            self.on_order_response, MessageEndpoints.scan_queue_order_change_response()
        )
        self._connected = True
        self.refresh()

    def cleanup(self) -> None:
        """Disconnect from all endpoints and drop the result of a read still in flight."""
        self._read_generation += 1
        self._reading = self._read_again = self._read_queue_again = False
        self._history_retry.stop()
        if not self._connected:
            return
        self.bec_dispatcher.disconnect_slot(
            self.on_queue_status, MessageEndpoints.scan_queue_status()
        )
        self.bec_dispatcher.disconnect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.bec_dispatcher.disconnect_slot(
            self.on_order_response, MessageEndpoints.scan_queue_order_change_response()
        )
        self._connected = False

    def refresh(self) -> None:
        """Read the queue status and history from Redis in the background."""
        self._start_read(with_queue=True)

    def reload_history(self) -> None:
        """Read the finished queue items from the queue history list in the background."""
        self._start_read(with_queue=False)

    def _start_read(self, with_queue: bool) -> None:
        if self._reading:
            # one read at a time; a request during it is folded into a single read after it
            self._read_again = True
            self._read_queue_again = self._read_queue_again or with_queue
            return
        self._reading = True
        self._read_generation += 1
        self._read_queue_mark = self._queue_updates
        known = {sid for sid, t in self._scan_times.items() if t.get("start")}
        known |= set(self._history_times)
        known |= {
            sid for sid, misses in self._history_misses.items() if misses >= self.HISTORY_RETRIES
        }
        self._worker = Worker(
            _read_queue_state,
            self.client.connector,
            self._read_result,
            self._read_generation,
            with_queue,
            known,
            self.HISTORY_LENGTH,
            getattr(self.client, "scans", None),
        )
        QThreadPool.globalInstance().start(self._worker)

    @SafeSlot(int, object)
    def _on_read_done(self, generation: int, payload: dict) -> None:
        if generation != self._read_generation:
            return  # superseded, or the model was cleaned up meanwhile
        self._reading = False
        self._worker = None
        # a queue status read before a live update is older than what is shown already
        if payload["queue"] is not None and self._read_queue_mark == self._queue_updates:
            self._apply_queue(payload["queue"])
        finished = payload["history"]
        if finished is not None:
            self._history_times.update(payload["times"])
            self._count_history_misses(finished, payload["missing"])
            for entry in finished:
                self._add_times(entry)
            self._add_history_times(finished)
            self.finished = finished
        self.loaded = True
        if self._read_again:
            with_queue = self._read_queue_again
            self._read_again = self._read_queue_again = False
            self._start_read(with_queue)
        self.changed.emit()

    def _count_history_misses(self, entries: list[QueueEntry], missing: set[str]) -> None:
        """Look up scans not in the scan history yet again later; a few times, then give up."""
        shown = {e.scan_id for e in entries}
        self._history_misses = {
            sid: misses for sid, misses in self._history_misses.items() if sid in shown
        }
        for sid in missing:
            self._history_misses[sid] = self._history_misses.get(sid, 0) + 1
        if any(self._history_misses.get(sid, 0) < self.HISTORY_RETRIES for sid in missing):
            self._history_retry.start()

    def _add_history_times(self, entries: list[QueueEntry]) -> None:
        """Fill start, end and exit status the widget did not see live from BEC's scan history."""
        self._history_times = {
            e.scan_id: self._history_times[e.scan_id]
            for e in entries
            if e.scan_id in self._history_times
        }
        for entry in entries:
            if entry.started_at is not None or entry.scan_id not in self._history_times:
                continue
            entry.started_at, end, exit_status = self._history_times[entry.scan_id]
            entry.finished_at = entry.finished_at or end
            entry.exit_status = entry.exit_status or exit_status

    def _add_times(self, entry: QueueEntry) -> None:
        times = self._scan_times.get(entry.scan_id or "")
        if not times:
            return
        entry.started_at = times.get("start")
        entry.finished_at = times.get("end")
        entry.exit_status = times.get("exit")

    @SafeSlot(dict, dict)
    def on_scan_status(self, content: dict, _metadata: dict) -> None:
        """Remember start and end times of scans for the history durations."""
        scan_id = content.get("scan_id")
        if not scan_id:
            return
        status = content.get("status")
        stamp = content.get("timestamp") or time.time()
        times = self._scan_times.setdefault(scan_id, {})
        if status == "open":
            times.setdefault("start", stamp)
        elif status in ("closed", "aborted", "halted", "user_completed"):
            times["end"] = stamp
            times["exit"] = status
        if len(self._scan_times) > 4 * self.HISTORY_LENGTH:
            for old in list(self._scan_times)[: self.HISTORY_LENGTH]:
                self._scan_times.pop(old, None)

    @SafeSlot(dict, dict)
    def on_order_response(self, content: dict, _metadata: dict) -> None:
        """
        Undo the shown reorder and report it when the scan server refused it. The response names
        no request and is broadcast to all clients, so it is matched to the oldest move still
        waiting for one; a response with no move waiting belongs to another client.
        """
        now = time.monotonic()
        while self._pending_moves and self._pending_moves[0][1] < now:
            self._pending_moves.popleft()
        if not self._pending_moves:
            return
        key, _deadline = self._pending_moves.popleft()
        if content.get("accepted", True):
            return
        reason = content.get("message") or "The queue refused the move"
        self._wanted_order = None
        self.waiting = self._numbered(list(self._server_waiting))
        self.changed.emit()
        self.action_failed.emit(QueueAction.MOVE, key, reason)

    @SafeSlot(dict, dict)
    def on_queue_status(self, content: dict, _metadata: dict) -> None:
        """Handle a ScanQueueStatusMessage."""
        before = self._known_ids
        self._queue_updates += 1
        self._apply_queue(content)
        if before - self._known_ids:
            # an item left the queue; the server writes its history entry before removing it
            self.reload_history()
        self.changed.emit()

    def _apply_queue(self, content: dict) -> None:
        queues = content.get("queue", {}) or {}
        primary = queues.get("primary")
        if primary is None:
            self.running, self.waiting, self._known_ids = None, [], set()
            return
        self.queue_state = str(getattr(primary, "status", "RUNNING"))
        infos = list(getattr(primary, "info", None) or [])
        # every item still in the queue, finished ones included: a finished item is only removed
        # after its history entry was written, so its removal is when the history is complete
        self._known_ids = {getattr(info, "queue_id", "") for info in infos}
        running = None
        waiting = []
        self._queue_offset = 0
        for index, info in enumerate(infos):
            entry = _entry_from_info(
                info, position=index, scans=getattr(self.client, "scans", None)
            )
            if entry is None:
                continue
            if entry.status in RUNNING_STATUSES and running is None:
                running = entry
                self._queue_offset = index + 1
            elif entry.status in WAITING_STATUSES:
                waiting.append(entry)
        self.running = running
        self._server_waiting = list(waiting)
        self.waiting = self._numbered(self._apply_wanted_order(waiting))

    @staticmethod
    def _numbered(waiting: list[QueueEntry]) -> list[QueueEntry]:
        for pos, entry in enumerate(waiting, start=1):
            entry.position = pos
        return waiting

    def _apply_wanted_order(self, waiting: list[QueueEntry]) -> list[QueueEntry]:
        """
        Show a reorder the user asked for until the queue reports it, so the rows move at once
        and do not jump back while the server works through several quick moves.
        """
        wanted = self._wanted_order
        if wanted is None:
            return waiting
        keys = [e.key for e in waiting]
        if keys == [k for k in wanted if k in keys] or time.monotonic() > self._wanted_until:
            self._wanted_order = None
            return waiting
        by_key = {e.key: e for e in waiting}
        ordered = [by_key[k] for k in wanted if k in by_key]
        return ordered + [e for e in waiting if e.key not in wanted]

    ################################################################################
    # Lookups
    ################################################################################

    def entry(self, key: str) -> QueueEntry | None:
        """Find an entry by key among waiting, running and finished."""
        for entry in [*self.waiting, *([self.running] if self.running else []), *self.finished]:
            if entry.key == key:
                return entry
        return None

    def waiting_index(self, key: str) -> int:
        """Index of a waiting entry, or -1."""
        for index, entry in enumerate(self.waiting):
            if entry.key == key:
                return index
        return -1

    ################################################################################
    # Actions
    ################################################################################

    def move(self, key: str, action: QueueMove | str) -> bool:
        """
        Reorder a waiting scan. The running scan always stays first.

        Args:
            key(str): The entry key.
            action(QueueMove | str): up, down, top or bottom.

        Returns:
            bool: True if a request was sent.
        """
        action = QueueMove(action)
        index = self.waiting_index(key)
        if index < 0:
            return False
        target = {
            QueueMove.UP: index - 1,
            QueueMove.DOWN: index + 1,
            QueueMove.TOP: 0,
            QueueMove.BOTTOM: len(self.waiting) - 1,
        }.get(action, index)
        target = max(0, min(target, len(self.waiting) - 1))
        if target == index:
            return False
        entry = self.waiting[index]
        if not entry.scan_id:
            logger.warning(f"Cannot move {entry.title}: it has no scan id yet")
            return False
        # the widget shows and indexes the primary queue, not the client's default scan queue
        self.client.queue.request_queue_order_modification(
            scan_id=entry.scan_id,
            action="move_to",
            position=target + self._queue_offset,
            queue="primary",
        )
        self._pending_moves.append((key, time.monotonic() + self.MOVE_CONFIRM_S))
        waiting = list(self.waiting)
        waiting.insert(target, waiting.pop(index))
        self._wanted_order = [e.key for e in waiting]
        self._wanted_until = time.monotonic() + self.MOVE_CONFIRM_S
        self.waiting = self._numbered(waiting)
        words = {
            QueueMove.UP: "up",
            QueueMove.DOWN: "down",
            QueueMove.TOP: "to the top",
            QueueMove.BOTTOM: "to the bottom",
        }
        self.action_sent.emit(QueueAction.MOVE, key, f"Moved {entry.title} {words.get(action, '')}")
        self.changed.emit()
        return True

    def remove(self, key: str) -> bool:
        """Remove a waiting scan from the queue."""
        index = self.waiting_index(key)
        if index < 0:
            return False
        entry = self.waiting[index]
        if not entry.rid:
            return False
        self.client.queue.request_scan_abortion(request_id=entry.rid)
        self.action_sent.emit(QueueAction.REMOVE, key, f"Removed {entry.title}")
        return True

    def rerun(self, entry: QueueEntry | str) -> str | None:
        """
        Queue a new scan with the same request as an existing entry.

        Args:
            entry(QueueEntry | str): The entry or its key.

        Returns:
            str | None: The new request id.
        """
        if isinstance(entry, str):
            entry = self.entry(entry)
        if entry is None or not entry.can_rerun:
            return None
        request = entry.request
        metadata = {
            k: copy.deepcopy(v)
            for k, v in (getattr(request, "metadata", {}) or {}).items()
            if k not in _REQUEST_ONLY_METADATA
        }
        rid = str(uuid.uuid4())
        metadata["RID"] = rid
        client_info = dict((getattr(request, "metadata", {}) or {}).get("client_info") or {})
        client_info["acl_user"] = getattr(self.client, "username", client_info.get("acl_user"))
        metadata["client_info"] = client_info
        msg = messages.ScanQueueMessage(
            scan_type=request.scan_type,
            parameter=copy.deepcopy(request.parameter),
            queue=getattr(request, "queue", "primary"),
            metadata=metadata,
        )
        self.client.connector.send(MessageEndpoints.scan_queue_request(self.client.username), msg)
        self.last_rerun_rid = rid
        self.action_sent.emit(QueueAction.RERUN, entry.key, f"Queued {entry.name} again")
        return rid

    def pause(self) -> None:
        """Pause the queue; the running scan pauses at its next safe point. Needs a running scan."""
        if self.running is None:
            return
        # sent directly: request_scan_interruption aborts instead when the running item has no
        # scan id (umv, mv, a device RPC), while the server holds the queue after such an item
        msg = messages.ScanQueueModificationMessage(
            request_id=self.running.rid, action="deferred_pause", parameter={}
        )
        self.client.connector.send(MessageEndpoints.scan_queue_modification_request(), msg)
        self.action_sent.emit(QueueAction.PAUSE, "", "Queue pauses at the next safe point")

    def resume(self) -> None:
        """Resume a paused queue."""
        self.client.queue.request_scan_continuation()
        self.action_sent.emit(QueueAction.RESUME, "", "Queue resumed")

    def reset(self) -> None:
        """
        Reset the queue: the scan server pauses it, stops the running scan and the devices it
        uses, and removes every waiting scan.
        """
        self.client.queue.request_queue_reset()
        self.action_sent.emit(QueueAction.RESET, "", "Queue reset")

    @property
    def paused(self) -> bool:
        """Whether the queue is paused or locked."""
        return self.queue_state in ("PAUSED", "LOCKED")
