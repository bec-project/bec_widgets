"""
The scan pill for the main window status bar: a small live progress bar, a Stop button, the number
of waiting scans, and the full ScanProgressBar in a card that opens on hover.
"""

from __future__ import annotations

import time
from typing import Callable

from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import QObject, QSettings, QThreadPool, Signal
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_connector import Worker
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.hover_card import HoverCard
from bec_widgets.widgets.containers.main_window.addons.status_pill import (  # noqa: F401
    PILL_FILL_MIN,
    PILL_MODES,
    PILL_WIDTHS,
    Reveal,
    StatusPillItem,
    ToolIndicator,
    ToolSeverity,
)
from bec_widgets.widgets.control.buttons.stop_button.stop_button import StopButton
from bec_widgets.widgets.progress.scan_progressbar.scan_hook_tracker import (
    ScanRunState,
    format_duration,
    hook_label,
)
from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar import (
    ScanProgressBar,
    describe_state,
)
from bec_widgets.widgets.progress.stage_bar import BarMode

SETTINGS_PREFIX = "scan_status"
SETTINGS_WIDTH = f"{SETTINGS_PREFIX}/pill_width"
SETTINGS_LARGE = f"{SETTINGS_PREFIX}/large"


def pill_labels(state: ScanRunState | None, now: float | None = None) -> tuple[str, str, str]:
    """
    The three label lengths of the status-bar scan pill: (short, medium, long).

    short: the step only ("Staging 0:03", "43%", "Done", "Failed").
    medium: with the scan number ("#12 · Staging · 0:03", "#12 · 43% · 1:20 left").
    long: everything that fits a wide bar, including the instruction and the next step.

    Args:
        state(ScanRunState | None): The scan state, or None while the queue is idle.
        now(float, optional): time.monotonic() to evaluate the timers at.
    """
    now = now if now is not None else time.monotonic()
    if state is None:
        return ("Queue idle",) * 3
    number = f"#{state.scan_number}" if state.scan_number is not None else ""
    name = state.display_name
    title = f"{number} {name}".strip()

    def join(*parts: str) -> str:
        return " · ".join(p for p in parts if p)

    if state.finished:
        # the same outcome word, step name and duration as the big widget (describe_state)
        info = describe_state(state, now)
        outcome, where, took = info["outcome"], info["where"], info["took"]
        if where:
            medium = f"{number} {outcome.lower()} in {where}".strip()
            return outcome, join(medium, took), join(title, f"{outcome} in {where}", took)
        return (
            outcome,
            join(f"{number} {outcome.lower()}".strip(), took),
            join(title, outcome, took),
        )

    nxt = state.next_hook if state.has_hooks else None
    next_text = f"next: {nxt}" if nxt else ""
    total = state.progress_max or state.num_points
    if state.measuring and total:
        value = int(state.progress_value or 0)
        pct = f"{int(round(value / total * 100))}%"
        left = state.remaining(now)
        left_text = f"{format_duration(left)} left" if left is not None else ""
        if state.status == "paused":
            return f"Paused {pct}", join(number, "Paused", pct), join(title, "Paused", pct)
        return (
            pct,
            join(number, pct, left_text),
            join(title, f"Point {value} of {int(total)}", pct, left_text, next_text),
        )

    step = "Paused" if state.status == "paused" else hook_label(state.top_hook) or "Running"
    timer = format_duration(state.hook_elapsed(now) if state.has_hooks else state.elapsed(now))
    instruction = state.instruction
    return (
        f"{step} {timer}",
        join(number, step, timer),
        join(title, step, timer, instruction, next_text),
    )


def scan_indicator(state: ScanRunState | None, waiting: int = 0) -> ToolIndicator:
    """
    The pill indicator for a scan state: the same step, outcome and progress as the big widget.

    Args:
        state(ScanRunState | None): The scan state, or None while the queue is idle.
        waiting(int): How many scans wait in the queue.
    """
    info = describe_state(state)
    mode = BarMode(info["bar_mode"]) if state is not None else BarMode.IDLE
    severity = {
        BarMode.DONE: ToolSeverity.OK,
        BarMode.ERROR: ToolSeverity.CRITICAL,
        BarMode.PAUSED: ToolSeverity.WARNING,
    }.get(mode, ToolSeverity.INFO)
    progress = info["bar_fraction"] if mode in (BarMode.PROGRESS, BarMode.PAUSED) else None
    return ToolIndicator(
        severity=severity,
        summary=pill_labels(state)[1],
        badge=f"{waiting} waiting" if waiting > 0 else None,
        progress=progress,
        active=mode == BarMode.BUSY,
    )


class _QueueStatusRead(QObject):
    """Carries the queue status read at startup to the GUI thread."""

    done = Signal(object)


def _read_queue_status(connector, result: _QueueStatusRead) -> None:
    """Read the stored queue status; runs in the thread pool and touches no widget."""
    try:
        msg = connector.get(MessageEndpoints.scan_queue_status())
    except Exception:  # pylint: disable=broad-except
        msg = None
    try:
        result.done.emit(msg)
    except RuntimeError:
        pass  # the pill was deleted meanwhile


class ScanProgressCard(HoverCard):
    """The hover card of the scan pill, with the full ScanProgressBar."""

    def __init__(self, owner: "ScanStatusItem"):
        super().__init__(owner, width=400, object_name="scan_status_card")
        self.progress = ScanProgressBar(
            parent=self.card,
            client=owner.client,
            fill_height=False,
            rpc_exposed=False,
            rpc_passthrough_children=False,
        )
        self.progress.layout().setContentsMargins(0, 0, 0, 0)  # pylint: disable=no-member
        self.set_content(self.progress)


class ScanStatusItem(StatusPillItem):
    """
    Status-bar scan pill, Stop button and waiting count, with the full ScanProgressBar on hover.

    One ScanHookTracker (the card's ScanProgressBar) drives both the pill and the card. The pill
    width (compact, normal, wide, fill) and the large size are chosen in its right-click menu
    and saved per user.
    """

    DOCK_WIDGET = "ScanProgressBar"

    def __init__(
        self,
        parent: QWidget | None = None,
        client=None,
        settings: Callable[[], QSettings] | None = None,
        **kwargs,
    ):
        super().__init__(
            parent=parent,
            client=client,
            settings=settings,
            settings_prefix=SETTINGS_PREFIX,
            **kwargs,
        )
        self.get_bec_shortcuts()
        self._state: ScanRunState | None = None
        self._waiting = 0
        # the shared Stop: a click aborts, then offers Emergency Stop; the arrow has Finish / halt
        self.stop_button = StopButton(
            parent=self, client=self.client, rpc_exposed=False, rpc_passthrough_children=False
        )
        self.stop_reveal = self.add_trailing(self.stop_button)
        self.waiting_chip = self.badge_chip
        self.waiting_reveal = self.badge_reveal
        self.tracker = self.card.progress.tracker
        self.tracker.changed.connect(self._on_state)
        self.tracker.tick.connect(self._update_indicator)

        self.bec_dispatcher.connect_slot(self.on_queue_status, MessageEndpoints.scan_queue_status())
        # the waiting count until the first live queue status: read in the background
        self._queue_status_live = False
        self._closed = False
        self._queue_read = _QueueStatusRead()
        self._queue_read.done.connect(self._on_queue_status_read)
        self._queue_read_worker: Worker | None = None
        self._load_waiting()
        self.apply_sizes()
        self._on_state(self.tracker.state)

    def create_card(self) -> HoverCard:
        return ScanProgressCard(self)

    ################################################################################
    # Sizes and theme
    ################################################################################

    def apply_sizes(self) -> None:
        """Apply the pill width mode and the normal/large heights and fonts, Stop included."""
        if hasattr(self, "stop_button"):
            self._style_stop()
        super().apply_sizes()

    def _style_stop(self) -> None:
        large = self.large
        self.stop_button.set_size(
            height=34 if large else 22,
            font_px=14 if large else 11,
            icon_px=16 if large else 12,
            radius=5,
            pad=8,
        )

    def apply_theme(self, theme: str):
        """Restyle after a theme change."""
        self._style_stop()
        super().apply_theme(theme)

    ################################################################################
    # State
    ################################################################################

    @SafeSlot(object)
    def _on_state(self, state: ScanRunState | None) -> None:
        self._state = state
        self._update_indicator()

    @SafeSlot()
    def _update_indicator(self) -> None:
        state = getattr(self, "_state", None)
        self.set_indicator(scan_indicator(state, getattr(self, "_waiting", 0)))
        if hasattr(self, "stop_button"):
            self.stop_button.request_id = state.rid if state is not None else None
            self.stop_reveal.set_shown(describe_state(state)["can_stop"])

    def pill_text(self) -> str:
        """The label for the current width mode."""
        short, medium, long = pill_labels(getattr(self, "_state", None))
        return {"compact": short, "normal": medium}.get(self.width_mode, long)

    ################################################################################
    # Waiting count
    ################################################################################

    def _load_waiting(self) -> None:
        self._queue_read_worker = Worker(
            _read_queue_status, self.client.connector, self._queue_read
        )
        QThreadPool.globalInstance().start(self._queue_read_worker)

    @SafeSlot(object)
    def _on_queue_status_read(self, msg) -> None:
        self._queue_read_worker = None
        # a live update is newer than the stored status; after cleanup nothing is shown
        if self._closed or self._queue_status_live:
            return
        if msg is not None and hasattr(msg, "content"):
            self._count_waiting(msg.content)

    @SafeSlot(dict, dict)
    def on_queue_status(self, content: dict, _metadata: dict) -> None:
        """Count the waiting scans of the primary queue."""
        self._queue_status_live = True
        self._count_waiting(content)

    def _count_waiting(self, content: dict) -> None:
        primary = (content.get("queue") or {}).get("primary")
        infos = getattr(primary, "info", None) or (
            primary.get("info") if isinstance(primary, dict) else []
        )
        waiting = 0
        for info in infos or []:
            status = getattr(info, "status", None)
            if status is None and isinstance(info, dict):
                status = info.get("status")
            if str(status) == "PENDING":
                waiting += 1
        self.set_waiting(waiting)

    def set_waiting(self, count: int) -> None:
        """Show how many scans wait in the queue; hidden at zero."""
        self._waiting = count
        self._update_indicator()

    ################################################################################
    # Card
    ################################################################################

    def keep_card_open(self) -> bool:
        """Keep the card while a stop waits for confirmation."""
        return not self.card.progress.confirm_frame.isHidden()

    def on_card_closed(self) -> None:
        """Drop a pending stop confirmation."""
        self.card.progress.cancel_stop()

    def cleanup(self):
        """Unsubscribe and close the card's progress bar, then the pill."""
        self._closed = True  # a queue status read still in flight is dropped
        self.bec_dispatcher.disconnect_slot(
            self.on_queue_status, MessageEndpoints.scan_queue_status()
        )
        self.card.progress.close()
        super().cleanup()
