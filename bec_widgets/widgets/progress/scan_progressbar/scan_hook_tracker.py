"""
Live state of the running scan, built from scan status, scan progress and scan hook messages.

Scan hook messages (``MessageEndpoints.scan_hook``) name the current step, when it started and the
current instruction; the latest one is stored, so a widget opened mid-scan reads it. For a scan
that reports no hooks, the tracker still follows the scan status and the measurement progress,
but cannot name the current step or the current instruction.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject, QThreadPool, QTimer, Signal

from bec_widgets.utils.bec_connector import Worker
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.progress.scan_progressbar.scan_ui import scan_display_name

logger = bec_logger.logger

SCAN_SEQUENCE = (
    "prepare_scan",
    "open_scan",
    "stage",
    "pre_scan",
    "scan_core",
    "post_scan",
    "unstage",
    "close_scan",
)

HOOK_NAMES = {
    "prepare_scan": "Preparing",
    "open_scan": "Opening scan",
    "stage": "Staging",
    "pre_scan": "Pre-scan",
    "scan_core": "Measuring",
    "post_scan": "Completing",
    "unstage": "Unstaging",
    "close_scan": "Closing",
    "on_exception": "Cleaning up",
}

FINISHED_STATUSES = ("closed", "aborted", "halted", "user_completed")

_ACTION_VERBS = {
    "set": "Moving",
    "stage": "Staging",
    "unstage": "Unstaging",
    "trigger": "Triggering",
    "read": "Reading",
    "kickoff": "Kicking off",
    "complete": "Completing",
    "pre_scan": "Pre-scan on",
    "baseline_reading": "Reading baseline",
    "open_scan": "Opening scan",
    "close_scan": "Closing scan",
    "wait": "Waiting",
}
_SILENT_ACTIONS = ("scan_report_instruction", "publish_data_as_read", "broadcast_scan_device_info")


def hook_label(hook: str | None) -> str:
    """Return the friendly name of a scan hook, falling back to the hook name itself."""
    if not hook:
        return ""
    return HOOK_NAMES.get(hook, hook.replace("_", " ").capitalize())


def format_duration(seconds: float | None) -> str:
    """Format seconds as m:ss, or h:mm:ss for an hour or more."""
    if seconds is None:
        return ""
    seconds = max(0, int(round(seconds)))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def queued_scan_ids(content: dict) -> set[str]:
    """The scan ids of all requests in a ScanQueueStatusMessage content, running or waiting."""
    ids = set()
    for queue in (_get(content, "queue") or {}).values():
        for info in _get(queue, "info") or []:
            ids.update(scan_id for scan_id in _get(info, "scan_id") or [] if scan_id)
    return ids


def queue_entry_status(content: dict, scan_id: str) -> str | None:
    """
    The status of the queue entry that runs scan_id, else None. It is the scan worker's own
    state: "PAUSED" during a pause, "RUNNING" again after a resume, while the status of the
    queue itself stays "RUNNING" during a (hard) pause.
    """
    for queue in (_get(content, "queue") or {}).values():
        for info in _get(queue, "info") or []:
            if scan_id in (_get(info, "scan_id") or []):
                return str(_get(info, "status") or "")
    return None


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _device_list(device: Any) -> list[str]:
    if device is None:
        return []
    if isinstance(device, (list, tuple)):
        return [str(dev) for dev in device]
    return [str(device)]


def _join_devices(devices: list[str], limit: int = 3) -> str:
    if len(devices) <= limit:
        return ", ".join(devices)
    return f"{', '.join(devices[:limit])} +{len(devices) - limit}"


def describe_instructions(instructions: list[Any], waiting: bool = False) -> str:
    """
    Turn device instructions into one short line, such as "Moving samx to -5".

    Args:
        instructions(list): DeviceInstructionMessage objects or their dict form.
        waiting(bool): Whether the scan waits for these instructions to finish.

    Returns:
        str: The description, or an empty string if nothing is worth showing.
    """
    by_action: dict[str, list[Any]] = {}
    for instr in instructions or []:
        action = _get(instr, "action")
        if not action or action in _SILENT_ACTIONS:
            continue
        by_action.setdefault(action, []).append(instr)
    if not by_action:
        return ""

    action, items = list(by_action.items())[-1]
    devices: list[str] = []
    for item in items:
        devices.extend(dev for dev in _device_list(_get(item, "device")) if dev not in devices)
    parameter = _get(items[-1], "parameter") or {}

    if action == "rpc":
        func = parameter.get("func", "")
        text = f"Calling {_join_devices(devices)}.{func}()" if devices else f"Calling {func}()"
    elif action == "set" and len(devices) == 1 and "value" in parameter:
        target = _format_value(parameter["value"])
        if waiting:
            return f"Waiting for {devices[0]} to reach {target}"
        text = f"Moving {devices[0]} to {target}"
    elif action in ("open_scan", "close_scan", "baseline_reading") or not devices:
        text = _ACTION_VERBS.get(action, action.replace("_", " ").capitalize())
    else:
        verb = _ACTION_VERBS.get(action, action.replace("_", " ").capitalize())
        text = f"{verb} {_join_devices(devices)}"

    if waiting:
        if devices:
            return f"Waiting for {_join_devices(devices)} ({action.replace('_', ' ')})"
        return f"Waiting · {text}"
    return text


@dataclass
class HookTiming:
    """Accumulated time spent in one hook of the running scan."""

    hook: str
    nested: bool = False
    total: float = 0.0
    count: int = 0
    started_at: float | None = None
    status: str = "running"
    parent: str | None = None

    def duration(self, now: float | None = None) -> float:
        """Total time in this hook, including the current visit when it is still running."""
        if self.started_at is not None and now is not None:
            return self.total + max(0.0, now - self.started_at)
        return self.total


@dataclass
class ScanRunState:
    """Everything the progress widgets show about one scan."""

    scan_id: str
    rid: str | None = None
    scan_number: int | None = None
    scan_name: str | None = None
    status: str = "open"
    user_metadata: dict = field(default_factory=dict)
    request_inputs: dict = field(default_factory=dict)
    num_points: int | None = None

    hook: str | None = None
    top_hook: str | None = None
    hook_error: str | None = None
    hook_started_local: float | None = None
    instruction: str = ""
    waiting: bool = False
    wait_started_local: float | None = None

    progress_value: float | None = None
    progress_max: float | None = None
    measure_started_local: float | None = None

    started_local: float = field(default_factory=time.monotonic)
    finished_local: float | None = None
    has_hooks: bool = False
    status_seen: bool = False
    progress_seen: bool = False
    lost: bool = False
    timings: dict[str, HookTiming] = field(default_factory=dict)
    _clock_offset: float = 0.0

    @property
    def display_name(self) -> str:
        """The scan's name: the user's scan_name when set, else the scan type."""
        return scan_display_name(self.user_metadata, self.scan_name)

    @property
    def finished(self) -> bool:
        """Whether the scan has ended, successfully or not."""
        return self.status in FINISHED_STATUSES

    @property
    def measuring(self) -> bool:
        """Whether the scan is in its measurement step (or has progress without hook info)."""
        if self.has_hooks:
            return self.top_hook == "scan_core"
        return self.progress_value is not None

    @property
    def next_hook(self) -> str | None:
        """The next top-level hook in the scan sequence, or None after the last one."""
        if self.top_hook not in SCAN_SEQUENCE:
            return SCAN_SEQUENCE[0] if not self.has_hooks else None
        index = SCAN_SEQUENCE.index(self.top_hook)
        if index + 1 < len(SCAN_SEQUENCE):
            return SCAN_SEQUENCE[index + 1]
        return None

    def elapsed(self, now: float | None = None) -> float:
        """Seconds since the scan started, frozen once it finished."""
        end = self.finished_local or (now if now is not None else time.monotonic())
        return max(0.0, end - self.started_local)

    def hook_elapsed(self, now: float | None = None) -> float:
        """Seconds spent in the current hook."""
        if self.hook_started_local is None:
            return 0.0
        now = now if now is not None else time.monotonic()
        return max(0.0, now - self.hook_started_local)

    def wait_elapsed(self, now: float | None = None) -> float | None:
        """Seconds the scan has been waiting on the current instructions, if it waits."""
        if not self.waiting or self.wait_started_local is None:
            return None
        now = now if now is not None else time.monotonic()
        return max(0.0, now - self.wait_started_local)

    def remaining(self, now: float | None = None) -> float | None:
        """Estimated seconds left in the measurement, from the progress so far."""
        if not self.progress_value or not self.progress_max or self.measure_started_local is None:
            return None
        now = now if now is not None else time.monotonic()
        spent = max(0.0, now - self.measure_started_local)
        left = max(0.0, self.progress_max - self.progress_value)
        return spent / self.progress_value * left

    def step_times(self) -> list[HookTiming]:
        """
        Hook timings in scan order: the steps of the scan sequence, each followed by the hooks
        that ran nested inside it.
        """
        steps = [t for t in self.timings.values() if not t.nested]
        order = {hook: index for index, hook in enumerate(SCAN_SEQUENCE)}
        steps.sort(key=lambda t: order.get(t.hook, len(SCAN_SEQUENCE)))
        result = [t for t in self.timings.values() if t.nested and t.parent is None]
        for step in steps:
            result.append(step)
            result.extend(t for t in self.timings.values() if t.nested and t.parent == step.hook)
        return result

    def server_now(self) -> float:
        """Current time on the server clock, estimated from the last live message."""
        return time.time() - self._clock_offset

    def _local(self, server_time: float) -> float:
        """The time.monotonic() value of a time on the server clock."""
        return time.monotonic() - max(0.0, self.server_now() - server_time)

    def _enter_hook(self, hook: str, timestamp: float) -> None:
        nested = hook not in SCAN_SEQUENCE and hook != "on_exception"
        timing = self.timings.get(hook)
        if timing is None:
            parent = self.top_hook if nested else None
            timing = self.timings[hook] = HookTiming(hook=hook, nested=nested, parent=parent)
        timing.count += 1
        timing.started_at = timestamp
        timing.status = "running"

    def _leave_hook(self, hook: str, timestamp: float, status: str = "completed") -> None:
        timing = self.timings.get(hook)
        if timing is None or timing.started_at is None:
            return
        timing.total += max(0.0, timestamp - timing.started_at)
        timing.started_at = None
        timing.status = status

    @staticmethod
    def is_top_hook(hook: str | None) -> bool:
        """Whether a hook is a step of the scan sequence rather than one nested inside a step."""
        return hook in SCAN_SEQUENCE or hook == "on_exception"

    def _enter_step(self, hook: str, started_at: float) -> None:
        """A new top-level step restarts the step timer and clears the previous instruction."""
        if self.hook and not self.is_top_hook(self.hook):
            self._leave_hook(self.hook, started_at)
        if self.top_hook:
            self._leave_hook(self.top_hook, started_at)
        self._enter_hook(hook, started_at)
        self.top_hook = hook
        self.hook_started_local = self._local(started_at)
        self.instruction = ""
        self.waiting = False
        self.wait_started_local = None
        if hook == "scan_core":
            self.measure_started_local = self.hook_started_local

    def apply_hook(self, content: dict, live: bool = True) -> None:
        """
        Update the state from one ScanHookMessage content.

        A top-level step (prepare_scan ... close_scan, on_exception) is timed from when the server
        started it. Nested hooks (scan modifiers) keep the step running; inside scan_core they are
        not timed separately, because the measurement progress already covers them.

        Args:
            content(dict): The message content.
            live(bool): False for the stored message read at startup, whose timestamp may be old
                and says nothing about the clock offset to the server.
        """
        now = time.monotonic()
        timestamp = content.get("timestamp") or time.time()
        if live:
            self._clock_offset = time.time() - timestamp
        hook = content.get("hook")
        status = content.get("status", "running")
        self.has_hooks = True

        if self.is_top_hook(hook):
            if status == "running":
                if hook != self.top_hook:
                    self._enter_step(hook, content.get("hook_started_at") or timestamp)
                elif self.hook and not self.is_top_hook(self.hook):
                    self._leave_hook(self.hook, timestamp)
                self.hook = hook
            else:
                self._leave_hook(hook, timestamp, status)
                if status == "error":
                    self.hook_error = hook
        elif hook:
            if status == "running" and hook != self.hook:
                if self.hook and not self.is_top_hook(self.hook):
                    self._leave_hook(self.hook, timestamp)
                if self.top_hook != "scan_core":
                    self._enter_hook(hook, timestamp)
                self.hook = hook
            elif status in ("completed", "interrupted", "error") and hook == self.hook:
                self._leave_hook(hook, timestamp, status)

        waiting = bool(content.get("waiting"))
        instructions = content.get("instructions") or []
        if instructions:
            text = describe_instructions(instructions, waiting=waiting)
            if text:
                self.instruction = text
        if waiting:
            wait_started_at = content.get("wait_started_at")
            if not self.waiting or wait_started_at is not None:
                offset = timestamp - wait_started_at if wait_started_at else 0.0
                if not live and wait_started_at:
                    offset = max(0.0, self.server_now() - wait_started_at)
                self.wait_started_local = now - max(0.0, offset)
            self.waiting = True
        else:
            self.waiting = False
            self.wait_started_local = None

    def apply_status(self, content: dict, metadata: dict) -> None:
        """Update the state from one ScanStatusMessage content."""
        self.status_seen = True
        self.status = content.get("status", self.status)
        for attr in ("scan_number", "scan_name", "num_points"):
            value = content.get(attr)
            if value is not None:
                setattr(self, attr, value)
        if content.get("user_metadata"):
            self.user_metadata = dict(content["user_metadata"])
        if content.get("request_inputs"):
            self.request_inputs = dict(content["request_inputs"])
        self.rid = self.rid or metadata.get("RID")
        if self.finished and self.finished_local is None:
            self.finished_local = time.monotonic()
            # steps still open when an abort or halt ended the scan were interrupted, not failed;
            # a step that failed has already reported "error" itself
            ended = self.status in ("closed", "user_completed")
            end_status = "completed" if ended else "interrupted"
            for hook in (self.hook, self.top_hook):
                if hook:
                    self._leave_hook(hook, self.server_now(), end_status)
            self.waiting = False

    def end_lost(self) -> None:
        """End the scan as aborted: it left the queue without a final status (e.g. a restart)."""
        self.lost = True
        self.apply_status({"status": "aborted"}, {})

    def clear_lost(self, status: str | None) -> None:
        """A real status arrived for a scan ended as lost: it wins over the inferred end."""
        self.lost = False
        if status not in FINISHED_STATUSES:
            self.finished_local = None  # it still runs
        elif status in ("closed", "user_completed"):
            for timing in self.timings.values():
                if timing.status == "interrupted":
                    timing.status = "completed"

    def resume(self) -> None:
        """The scan runs again after a pause; BEC sends no new scan status for it."""
        if self.status == "paused":
            self.status = "open"

    def apply_progress(self, content: dict) -> None:
        """Update the measurement progress from one ProgressMessage content."""
        self.progress_seen = True
        self.progress_value = content.get("value", 0)
        self.progress_max = content.get("max_value") or self.num_points
        if self.measure_started_local is None:
            self.measure_started_local = time.monotonic()


class _InitialRead(QObject):
    """Carries the stored scan messages read at startup to the GUI thread."""

    done = Signal(object)


def _read_initial_state(connector, result: _InitialRead) -> None:
    """Read the stored scan status, hook, progress and queue status; runs in the thread pool."""
    stored = {}
    for name, endpoint in (
        ("status", MessageEndpoints.scan_status()),
        ("hook", MessageEndpoints.scan_hook()),
        ("progress", MessageEndpoints.scan_progress()),
        ("queue", MessageEndpoints.scan_queue_status()),
    ):
        try:
            msg = connector.get(endpoint)
        except Exception:  # pylint: disable=broad-except
            logger.debug(f"Could not read {endpoint.endpoint}")
            msg = None
        stored[name] = msg if msg is not None and hasattr(msg, "content") else None
    try:
        result.done.emit(stored)
    except RuntimeError:
        pass  # the tracker was deleted meanwhile


class ScanHookTracker(QObject):
    """
    Follow the running scan and emit its state on every change.

    Signals:
        changed(object): A ScanRunState, or None before any scan was seen.
        tick(): Emitted every 250 ms while a scan runs, to refresh live timers.

    At start it reads the stored scan status, and the stored scan hook and progress of that scan,
    so a widget opened mid-scan shows the current step, its instruction and the real progress at
    once. Steps that ended before it was opened are not known and not listed.

    The stored messages are read in the thread pool, so creating a widget never waits for Redis;
    a live message that arrives meanwhile is newer and wins.

    A scan that leaves the queue without a final status, e.g. because the BEC server was
    restarted while it ran, is ended as aborted after LOST_SCAN_GRACE_MS, so the views do not
    stay on its last progress. A paused scan counts as running again once its queue entry runs
    again or it reports its next step.
    """

    # a finished scan can leave the queue just before its final status arrives
    LOST_SCAN_GRACE_MS = 2000

    changed = Signal(object)
    tick = Signal()

    def __init__(self, client, bec_dispatcher, parent: QObject | None = None):
        super().__init__(parent=parent)
        self.client = client
        self.bec_dispatcher = bec_dispatcher
        self.state: ScanRunState | None = None
        self._connected = False
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.tick.emit)
        self._lost_check = QTimer(self)
        self._lost_check.setSingleShot(True)
        self._lost_check.setInterval(self.LOST_SCAN_GRACE_MS)
        self._lost_check.timeout.connect(self._end_lost_scan)
        self._queued: set[str] | None = None
        self._lost_scan_id: str | None = None
        self.loaded = False  # the stored state was read (or there was none)
        self._closed = False
        # parented, so it is deleted with the tracker on the GUI thread, never in the thread pool
        self._initial = _InitialRead(self)
        self._initial.done.connect(self._on_initial_state)
        self._initial_worker: Worker | None = None

    def start(self) -> None:
        """Subscribe to the scan endpoints and load the current scan, if any."""
        if self._connected:
            return
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.bec_dispatcher.connect_slot(self.on_scan_progress, MessageEndpoints.scan_progress())
        self.bec_dispatcher.connect_slot(self.on_scan_hook, MessageEndpoints.scan_hook())
        self.bec_dispatcher.connect_slot(self.on_queue_status, MessageEndpoints.scan_queue_status())
        self._connected = True
        self._initial_worker = Worker(_read_initial_state, self.client.connector, self._initial)
        QThreadPool.globalInstance().start(self._initial_worker)

    @SafeSlot(object)
    def _on_initial_state(self, stored: dict) -> None:
        self._initial_worker = None
        if self._closed:
            return
        self.loaded = True
        msg = stored.get("status")
        if msg is None:
            return  # no scan ran yet
        state = self.state
        if state is not None and (state.status_seen or state.scan_id != msg.content.get("scan_id")):
            return  # a live status is newer, or the stored one is of an older scan
        # a live hook alone leaves the number, name and metadata to the stored status; what came
        # in live is newer than what is stored
        self.on_scan_status(msg.content, msg.metadata)
        state = self.state
        if state is None or state.finished:
            return
        hook = stored.get("hook")
        if (
            not state.has_hooks
            and hook is not None
            and hook.content.get("scan_id") == state.scan_id
        ):
            state.apply_hook(hook.content, live=False)
        progress = stored.get("progress")
        if (
            not state.progress_seen
            and progress is not None
            and progress.metadata.get("scan_id") == state.scan_id
        ):
            state.apply_progress(progress.content)
        queue = stored.get("queue")
        if queue is not None and self._queued is None:
            # a stored "open" of a scan the queue no longer has: ended after the same grace
            # period as a live update, as it may just have finished between the two reads
            self.on_queue_status(queue.content, queue.metadata)
        self._emit()

    def _state_for(self, scan_id: str | None, rid: str | None = None) -> ScanRunState | None:
        if not scan_id:
            return self.state
        if self.state is None or self.state.scan_id != scan_id:
            self.state = ScanRunState(scan_id=scan_id, rid=rid)
        elif rid and not self.state.rid:
            self.state.rid = rid
        return self.state

    def _emit(self) -> None:
        if self.state is not None and not self.state.finished:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
        self.changed.emit(self.state)

    @SafeSlot(dict, dict)
    def on_scan_status(self, content: dict, metadata: dict) -> None:
        """Handle a ScanStatusMessage."""
        scan_id = content.get("scan_id")
        if not scan_id:
            return
        if self.state is not None and self.state.scan_id != scan_id:
            if content.get("status") != "open":
                return
        state = self._state_for(scan_id, metadata.get("RID"))
        if state.lost:
            state.clear_lost(content.get("status"))
        state.apply_status(content, metadata)
        self._emit()

    @SafeSlot(dict, dict)
    def on_scan_progress(self, content: dict, metadata: dict) -> None:
        """Handle a scan ProgressMessage."""
        scan_id = metadata.get("scan_id")
        if self.state is None or (scan_id and scan_id != self.state.scan_id):
            return  # progress of a scan whose status was not seen
        if self.state.finished:
            return
        self.state.apply_progress(content)
        self._emit()

    @SafeSlot(dict, dict)
    def on_scan_hook(self, content: dict, metadata: dict) -> None:
        """Handle a ScanHookMessage."""
        scan_id = content.get("scan_id")
        if not scan_id:
            return
        if self.state is not None and self.state.scan_id == scan_id and self.state.finished:
            return
        state = self._state_for(scan_id, metadata.get("RID"))
        state.resume()  # a paused scan reports no step until it runs again
        state.apply_hook(content)
        self._emit()

    @SafeSlot(dict, dict)
    def on_queue_status(self, content: dict, _metadata: dict) -> None:
        """Handle a ScanQueueStatusMessage: notice a running scan that left the queue."""
        self._queued = queued_scan_ids(content)
        state = self.state
        if (
            state is not None
            and state.status == "paused"
            and queue_entry_status(content, state.scan_id) == "RUNNING"
        ):
            state.resume()
            self._emit()
        if state is None or state.finished or state.scan_id in self._queued:
            self._lost_check.stop()
        elif not self._lost_check.isActive() or self._lost_scan_id != state.scan_id:
            self._lost_scan_id = state.scan_id
            self._lost_check.start()

    def _end_lost_scan(self) -> None:
        state = self.state
        if state is None or state.finished or state.scan_id != self._lost_scan_id:
            return  # it ended normally, or another scan started meanwhile
        if self._queued is None or state.scan_id in self._queued:
            return
        state.end_lost()
        self._emit()

    def cleanup(self) -> None:
        """Stop the timers, drop a startup read still running and disconnect from all endpoints."""
        self._closed = True
        self._timer.stop()
        self._lost_check.stop()
        if not self._connected:
            return
        self.bec_dispatcher.disconnect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.bec_dispatcher.disconnect_slot(self.on_scan_progress, MessageEndpoints.scan_progress())
        self.bec_dispatcher.disconnect_slot(self.on_scan_hook, MessageEndpoints.scan_hook())
        self.bec_dispatcher.disconnect_slot(
            self.on_queue_status, MessageEndpoints.scan_queue_status()
        )
        self._connected = False
