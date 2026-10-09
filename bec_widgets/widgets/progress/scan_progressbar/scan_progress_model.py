"""Presentation model shared by the QML and QWidget versions of the modern scan progress bar."""

from __future__ import annotations

from bec_lib.endpoints import MessageEndpoints
from bec_qthemes._theme import ACCENT_COLORS
from qtpy.QtCore import Property, QObject, QTimer, Signal
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QApplication

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.progress.progress_backend import BECProgressTracker, ProgressSnapshot

# BEC scan status -> display state
STATUS_TO_STATE = {
    "open": "running",
    "paused": "paused",
    "aborted": "aborted",
    "halted": "halted",
    "closed": "done",
    "user_completed": "done",
}

STATE_LABELS = {
    "idle": "Idle",
    "running": "Running",
    "paused": "Paused",
    "aborted": "Aborted",
    "halted": "Halted",
    "done": "Done",
}

# Theme color key used for each state (bec_qthemes palette keys)
STATE_COLOR_KEYS = {
    "idle": "DISABLED_FG",
    "running": "ACCENT_DEFAULT",
    "paused": "ACCENT_WARNING",
    "aborted": "ACCENT_HIGHLIGHT",
    "halted": "ACCENT_EMERGENCY",
    "done": "ACCENT_SUCCESS",
}

STATE_ICONS = {
    "idle": "radio_button_unchecked",
    "running": "play_circle",
    "paused": "pause_circle",
    "aborted": "cancel",
    "halted": "report",
    "done": "check_circle",
}


def current_theme_colors() -> dict[str, QColor]:
    """
    Colours of the active bec_qthemes theme, or a palette-based fallback when no theme is applied.

    Returns:
        dict[str, QColor]: Theme colours keyed by bec_qthemes palette key.
    """
    app = QApplication.instance()
    if hasattr(app, "theme"):
        return dict(app.theme._colors)
    palette = app.palette()
    colors = {k: QColor(v) for k, v in ACCENT_COLORS["dark"].items()}
    colors["FG"] = palette.color(QPalette.ColorRole.WindowText)
    colors["DISABLED_FG"] = palette.color(QPalette.ColorRole.PlaceholderText)
    return colors


def format_duration(seconds: float | None) -> str:
    """
    Format a duration compactly: ``m:ss`` below one hour, ``h:mm:ss`` above.

    Args:
        seconds(float | None): Duration in seconds.

    Returns:
        str: The formatted duration, or an em dash if unknown.
    """
    if seconds is None:
        return "—"
    seconds = max(0, int(round(seconds)))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02}:{secs:02}"
    return f"{minutes}:{secs:02}"


def format_count(value: float) -> str:
    """Format a point count without a trailing ``.0``."""
    if float(value).is_integer():
        return f"{int(value)}"
    return f"{value:.1f}"


class ScanProgressModel(QObject):
    """
    View-agnostic state of the current scan's progress.

    Wraps ``BECProgressTracker`` and the scan status endpoint, and exposes ready-to-display
    properties. Both the QML view and the QWidget view render from this object only.
    """

    changed = Signal()
    progress_started = Signal()
    progress_finished = Signal()

    def __init__(self, bec_dispatcher, parent: QObject | None = None):
        super().__init__(parent=parent)
        self._dispatcher = bec_dispatcher
        self._state = "idle"
        self._value = 0.0
        self._maximum = 0.0
        self._scan_number: int | None = None
        self._scan_name = ""
        self._reason = ""
        self._scan_id: str | None = None
        self._elapsed: float | None = None
        self._remaining: float | None = None

        self.tracker = BECProgressTracker(bec_dispatcher, parent=self)
        self.tracker.progress_started.connect(self._on_started)
        self.tracker.progress_updated.connect(self._on_snapshot)
        self.tracker.progress_finished.connect(self._on_finished)
        self.tracker.start()
        self._dispatcher.connect_slot(self._on_scan_status, MessageEndpoints.scan_status())

        # Elapsed/remaining tick once per second while a scan runs
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._tick)

    ################################################################################
    # Inputs

    @SafeSlot(object)
    def _on_started(self, _snapshot: ProgressSnapshot):
        self._tick_timer.start()
        self.progress_started.emit()

    @SafeSlot(object)
    def _on_snapshot(self, snapshot: ProgressSnapshot):
        if snapshot.is_new_scan:
            self._reason = ""
            self._elapsed = 0.0
            self._remaining = None
            if snapshot.scan_id != self._scan_id:
                self._scan_name = ""
        self._scan_id = snapshot.scan_id or self._scan_id
        self._scan_number = snapshot.scan_number
        self._value = float(snapshot.value)
        self._maximum = float(snapshot.max_value)
        state = STATUS_TO_STATE.get(str(snapshot.status).lower(), "running")
        if snapshot.done and state == "running":
            state = "done"
        # A final scan status (aborted/halted) wins over a late "open" progress message
        if snapshot.is_new_scan or self._state not in ("aborted", "halted"):
            self._state = state
        self._read_task_times()
        self.changed.emit()

    @SafeSlot(object)
    def _on_finished(self, _snapshot: ProgressSnapshot):
        self._tick_timer.stop()
        if self._state in ("running", "paused"):
            self._state = "done"
        self._remaining = 0.0
        self.changed.emit()
        self.progress_finished.emit()

    @SafeSlot(dict, dict)
    def _on_scan_status(self, msg_content: dict, metadata: dict):
        scan_id = msg_content.get("scan_id")
        status = msg_content.get("status")
        if status == "open":
            if scan_id != self._scan_id:
                self._scan_id = scan_id
                self._reason = ""
            self._scan_name = msg_content.get("scan_name") or self._scan_name
            if msg_content.get("scan_number") is not None:
                self._scan_number = msg_content.get("scan_number")
            self.changed.emit()
            return
        if scan_id is None or scan_id != self._scan_id:
            return
        new_state = STATUS_TO_STATE.get(status)
        if new_state is None:
            return
        self._state = new_state
        self._reason = msg_content.get("reason") or ""
        if new_state in ("aborted", "halted", "done"):
            self._tick_timer.stop()
        self.changed.emit()

    @SafeSlot()
    def _tick(self):
        self._read_task_times()
        self.changed.emit()

    def _read_task_times(self):
        task = self.tracker.task
        if task is None:
            return
        task.update_elapsed_time()
        self._elapsed = task._elapsed_time
        if self._state == "paused" or not task.speed or not task.remaining:
            self._remaining = None if self._state != "done" else 0.0
        else:
            self._remaining = task.remaining / task.speed

    ################################################################################
    # Outputs

    @Property(str, notify=changed)
    def state(self) -> str:
        """Display state: idle, running, paused, aborted, halted or done."""
        return self._state

    @Property(str, notify=changed)
    def stateLabel(self) -> str:
        label = STATE_LABELS[self._state]
        if self._reason == "alarm" and self._state in ("aborted", "halted"):
            label = f"{label} by alarm"
        return label

    @Property(str, notify=changed)
    def stateColorKey(self) -> str:
        return STATE_COLOR_KEYS[self._state]

    @Property(str, notify=changed)
    def stateIcon(self) -> str:
        return STATE_ICONS[self._state]

    @Property(bool, notify=changed)
    def active(self) -> bool:
        return self._state in ("running", "paused")

    @Property(str, notify=changed)
    def title(self) -> str:
        """Scan identity, e.g. ``Scan 42 · line_scan``."""
        if self._state == "idle" and self._scan_number is None:
            return "No scan yet"
        parts = [f"Scan {self._scan_number}" if self._scan_number is not None else "Scan"]
        if self._scan_name:
            parts.append(self._scan_name)
        return " · ".join(parts)

    @Property(float, notify=changed)
    def value(self) -> float:
        return self._value

    @Property(float, notify=changed)
    def maximum(self) -> float:
        return self._maximum

    @Property(float, notify=changed)
    def fraction(self) -> float:
        """Progress between 0 and 1."""
        if self._maximum <= 0:
            return 1.0 if self._state == "done" else 0.0
        return min(1.0, max(0.0, self._value / self._maximum))

    @Property(bool, notify=changed)
    def indeterminate(self) -> bool:
        """True while a scan runs but the number of points is not known yet."""
        return self._state == "running" and self._maximum <= 0

    @Property(str, notify=changed)
    def percentText(self) -> str:
        if self._state == "idle" or self.indeterminate:
            return ""
        return f"{int(self.fraction * 100)} %"

    @Property(str, notify=changed)
    def countText(self) -> str:
        if self._state == "idle" or self._maximum <= 0:
            return ""
        return f"{format_count(self._value)} / {format_count(self._maximum)}"

    @Property(str, notify=changed)
    def elapsedText(self) -> str:
        if self._state == "idle" or self._elapsed is None:
            return ""
        return format_duration(self._elapsed)

    @Property(str, notify=changed)
    def timeText(self) -> str:
        """The single time hint shown at the right of the bar."""
        if self._state == "idle":
            return ""
        if self._state == "running":
            if self._remaining is None:
                return "estimating…"
            return f"{format_duration(self._remaining)} left"
        if self._state == "paused":
            return f"paused at {format_duration(self._elapsed)}"
        return f"took {format_duration(self._elapsed)}"

    @Property(str, notify=changed)
    def toolTip(self) -> str:
        if self._state == "idle":
            return "No scan has reported progress yet."
        lines = [f"{self.title} — {self.stateLabel}"]
        if self.countText:
            lines.append(f"Points: {self.countText} ({self.percentText})")
        lines.append(f"Elapsed: {format_duration(self._elapsed)}")
        if self._state == "running":
            lines.append(f"Remaining: {format_duration(self._remaining)}")
        return "\n".join(lines)

    def cleanup(self):
        """Disconnect from BEC and stop timers."""
        self._tick_timer.stop()
        self.tracker.cleanup()
        self._dispatcher.disconnect_slot(self._on_scan_status, MessageEndpoints.scan_status())
