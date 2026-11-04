"""
Scan progress widget: what the running scan does now, what comes next, and one Stop.
"""

from __future__ import annotations

import time

from bec_lib.logger import bec_logger
from qtpy.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from qtpy.QtGui import QFontInfo, QPainter, QPen
from qtpy.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.flow_layout import FlowLayoutWidget
from bec_widgets.utils.theme_utils import css, theme_colors
from bec_widgets.widgets.control.buttons.stop_button.stop_button import StopAction, StopButton
from bec_widgets.widgets.progress.scan_progressbar.scan_hook_tracker import (
    ScanHookTracker,
    ScanRunState,
    format_duration,
    hook_label,
)
from bec_widgets.widgets.progress.scan_progressbar.scan_ui import (
    ElidedLabel,
    MetaChip,
    metadata_items,
    request_inputs_summary,
    scan_bundle_names,
)
from bec_widgets.widgets.progress.stage_bar import BarMode, Chip, StageBar, Tone, mono_font

logger = bec_logger.logger

# During the measurement a wait time is only shown once a device has kept the scan waiting this
# long; the per-point waits are short and their timer would only blink.
MEASURE_WAIT_SHOWN_AFTER_S = 2.0

# outcome word and tone of a finished scan, shared by every view of it (bar, chip, status bar)
_FINISHED_CHIPS = {
    "closed": ("Done", Tone.OK),
    "user_completed": ("Finished early", Tone.OK),
    "aborted": ("Aborted", Tone.BAD),
    "halted": ("Halted", Tone.BAD),
}


def describe_state(state: ScanRunState | None, now: float | None = None) -> dict:
    """
    Compute every text and mode the progress widget shows for a scan state.

    Kept free of widgets so other views of the scan and tests can share it.

    Args:
        state(ScanRunState | None): The scan state, or None before any scan.
        now(float, optional): time.monotonic() to evaluate the timers at.

    Returns:
        dict: title, chip, chip_tone, bar_mode, bar_fraction, bar_text, instruction, next, can_stop.
    """
    now = now if now is not None else time.monotonic()
    if state is None:
        return {
            "title": "No scan yet",
            "chip": "Idle",
            "chip_tone": Tone.NEUTRAL,
            "bar_mode": BarMode.IDLE,
            "bar_fraction": 0.0,
            "bar_text": "Waiting for a scan",
            "instruction": "",
            "next": "",
            "can_stop": False,
        }

    number = f"#{state.scan_number} " if state.scan_number is not None else ""
    title = f"{number}{state.display_name}"
    step = hook_label(state.top_hook) if state.top_hook else ""

    if state.finished:
        chip, tone = _FINISHED_CHIPS.get(state.status, ("Failed", Tone.BAD))
        took = format_duration(state.elapsed(now))
        # where a scan that did not end normally stopped, as a step display name ("Measuring")
        where = hook_label(state.hook_error or state.top_hook) if tone != Tone.OK and step else ""
        next_text = f"Took {took}"
        if state.lost:
            # no final status: the scan server went away (e.g. a restart), so its run time is
            # not known either
            took = ""
            next_text = "The scan server stopped while the scan ran"
        detail = took or "scan server stopped"
        bar_text = f"{chip} in {where} · {detail}" if where else f"{chip} · {detail}"
        return {
            "outcome": chip,
            "where": where,
            "took": took,
            "title": title,
            "chip": chip,
            "chip_tone": tone,
            "bar_mode": BarMode.DONE if tone == Tone.OK else BarMode.ERROR,
            "bar_fraction": 1.0,
            "bar_text": bar_text,
            "instruction": "",
            "next": next_text,
            "can_stop": False,
        }

    if state.status == "paused":
        chip, tone, mode = "Paused", Tone.WARN, BarMode.PAUSED
    else:
        chip, tone, mode = (step or "Running"), Tone.RUN, BarMode.BUSY

    fraction = 0.0
    total = state.progress_max or state.num_points
    if state.measuring and total:
        value = state.progress_value or 0
        fraction = value / total
        pct = int(round(fraction * 100))
        left = state.remaining(now)
        left_text = f" · {format_duration(left)} left" if left is not None else ""
        bar_text = f"Point {int(value)} of {int(total)} · {pct}%{left_text}"
        if mode != BarMode.PAUSED:
            mode = BarMode.PROGRESS
    elif state.has_hooks:
        bar_text = f"{step or 'Running'} · {format_duration(state.hook_elapsed(now))}"
    else:
        bar_text = f"Running · {format_duration(state.elapsed(now))}"

    instruction = state.instruction
    wait = state.wait_elapsed(now)
    if state.top_hook == "scan_core":
        if wait is not None and wait < MEASURE_WAIT_SHOWN_AFTER_S:
            wait = None  # per-point waits are short; only time a device the scan is stuck on
    elif state.hook and state.hook != state.top_hook:
        instruction = f"[{state.hook}] {instruction}".strip()
    if wait is not None:
        instruction = f"{instruction or 'Waiting'} · {format_duration(wait)}"

    next_text = ""
    if state.has_hooks:
        nxt = state.next_hook
        next_text = f"Next: {hook_label(nxt)}  {nxt}" if nxt else "Last step"

    return {
        "title": title,
        "chip": chip,
        "chip_tone": tone,
        "bar_mode": mode,
        "bar_fraction": fraction,
        "bar_text": bar_text,
        "instruction": instruction,
        "next": next_text,
        "can_stop": True,
    }


class StepTimesPopup(QFrame):
    """
    Hover card listing how long each hook of the scan took.

    It refreshes while open, so its rows are updated in place and it never shrinks while shown;
    rebuilding or resizing it on every tick makes it flicker.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("step_times_popup")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 10, 12, 10)
        self._layout.setSpacing(6)
        self._title = QLabel(self)
        self._title.setFont(mono_font(0, bold=True))
        self._layout.addWidget(self._title)
        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(3)
        self._layout.addLayout(self._grid)
        self._row_widgets: list[tuple[QLabel, _ShareBar, QLabel]] = []
        self._name_styles: dict[QLabel, str] = {}
        self.rows: list[tuple[str, str]] = []
        self.refresh_style()

    def refresh_style(self) -> None:
        """Re-read the theme colours."""
        colors = theme_colors()
        self.setStyleSheet(
            f"#step_times_popup {{ background: {css(colors['card'])};"
            f" border: 1px solid {css(colors['border'])}; border-radius: 8px; }}"
            f"QLabel {{ color: {css(colors['fg'])}; text-decoration: none; }}"
        )
        self._name_styles.clear()

    def _row(self, index: int) -> tuple[QLabel, _ShareBar, QLabel]:
        while len(self._row_widgets) <= index:
            row = len(self._row_widgets)
            name = QLabel(self)
            name.setFont(mono_font(-1))
            share = _ShareBar(self)
            took = QLabel(self)
            took.setFont(mono_font(-1))
            took.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            took.setMinimumWidth(took.fontMetrics().horizontalAdvance("0000.0 s ×000"))
            self._grid.addWidget(name, row, 0)
            self._grid.addWidget(share, row, 1)
            self._grid.addWidget(took, row, 2)
            self._row_widgets.append((name, share, took))
        return self._row_widgets[index]

    def set_state(self, state: ScanRunState | None) -> None:
        """Fill the card from a scan state."""
        colors = theme_colors()
        self.rows = []
        timings = state.step_times() if state is not None and state.timings else []
        if not timings:
            self._title.setText("No step times yet")
        else:
            number = f" · #{state.scan_number}" if state.scan_number is not None else ""
            self._title.setText(f"Step times{number}   {format_duration(state.elapsed())}")
        server_now = state.server_now() if timings and not state.finished else None
        longest = max((t.duration(server_now) for t in timings), default=0) or 1
        for index, timing in enumerate(timings):
            name, share, took = self._row(index)
            seconds = timing.duration(server_now)
            name.setText(("  " if timing.nested else "") + timing.hook)
            if timing.status == "error":
                style = f"color: {css(colors['bad'])};"
            elif timing.started_at is not None:
                style = f"color: {css(colors['run'])}; font-weight: 600;"
            else:
                style = ""
            if self._name_styles.get(name) != style:
                self._name_styles[name] = style
                name.setStyleSheet(style)
            share.set_share(seconds / longest, timing.status)
            count = f" ×{timing.count}" if timing.count > 1 else ""
            took.setText(f"{seconds:.1f} s{count}")
            for widget in (name, share, took):
                widget.setVisible(True)
            self.rows.append((timing.hook, took.text()))
        for name, share, took in self._row_widgets[len(timings) :]:
            for widget in (name, share, took):
                widget.setVisible(False)
        self._fit()

    def _fit(self) -> None:
        """Grow to fit the content; only shrink while hidden."""
        hint = self.sizeHint()
        if self.isVisible():
            width = max(hint.width(), self.width())
        else:
            width = hint.width()
        if (width, hint.height()) != (self.width(), self.height()):
            right = self.geometry().right()
            self.resize(width, hint.height())
            if self.isVisible():
                self.move(right - width + 1, self.y())


class _ShareBar(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._share = 0.02
        self._status = ""
        self.setFixedSize(90, 8)

    def set_share(self, share: float, status: str) -> None:
        """Set the filled share (0 to 1) and repaint when it changed."""
        share = max(0.02, min(1.0, share))
        if abs(share - self._share) > 0.002 or status != self._status:
            self._share, self._status = share, status
            self.update()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        colors = theme_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        track = colors["fg"]
        track.setAlphaF(0.08)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 3, 3)
        painter.setBrush(colors["bad"] if self._status == "error" else colors["primary"])
        painter.drawRoundedRect(QRectF(0, 0, self.width() * self._share, self.height()), 3, 3)
        painter.end()


class StepTimesLabel(QLabel):
    """A "Step times" label that shows the StepTimesPopup while hovered or clicked."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Step times", parent)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.setToolTip("")
        self.popup = StepTimesPopup(self)
        self._state: ScanRunState | None = None

    def paintEvent(self, event):  # pylint: disable=invalid-name
        """Draw the text, then a dotted underline (style sheets cannot style an underline)."""
        super().paintEvent(event)
        metrics = self.fontMetrics()
        width = min(metrics.horizontalAdvance(self.text()), self.contentsRect().width())
        rect = self.contentsRect()
        if self.alignment() & Qt.AlignmentFlag.AlignRight:
            left = rect.right() - width
        elif self.alignment() & Qt.AlignmentFlag.AlignHCenter:
            left = rect.left() + (rect.width() - width) // 2
        else:
            left = rect.left()
        text_top = rect.top() + (rect.height() - metrics.height()) // 2
        y = min(rect.bottom(), text_top + metrics.ascent() + 2)
        painter = QPainter(self)
        painter.setPen(QPen(theme_colors()["muted"], 1, Qt.PenStyle.DotLine))
        painter.drawLine(left, y, left + width, y)
        painter.end()

    def set_state(self, state: ScanRunState | None) -> None:
        """Remember the state and refresh the card if it is open."""
        self._state = state
        if self.popup.isVisible():
            self.popup.set_state(state)

    def show_popup(self) -> None:
        """Open the card next to the label."""
        if self.popup.isVisible():
            return
        self.popup.set_state(self._state)
        anchor = self.mapToGlobal(QPoint(self.width(), self.height() + 4))
        self.popup.move(anchor.x() - self.popup.width(), anchor.y())
        self.popup.show()

    def refresh_style(self) -> None:
        """Re-read the theme colours of the card."""
        self.popup.refresh_style()

    def enterEvent(self, event):  # pylint: disable=invalid-name
        super().enterEvent(event)
        self.show_popup()

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        super().leaveEvent(event)
        self.popup.hide()

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        if self.popup.isVisible():
            self.popup.hide()
        else:
            self.show_popup()
        super().mousePressEvent(event)


class ScanProgressBar(BECWidget, QWidget):
    """
    Live progress of the running scan.

    Shows the current step with busy stripes and a step timer, real progress while measuring,
    the current device instruction with its wait time, the next step, and a Stop for the
    whole scan. Hover "Step times" to see how long each step took.
    """

    PLUGIN = True
    ICON_NAME = "av_timer"
    RPC = True

    state_changed = Signal(object)

    # share of the bar row the bar label is sized for; the Stop button takes at most
    # STOP_ROW_MAX of the row and grows to at most STOP_SCALE_MAX of its normal size
    STOP_ROW_SHARE = 0.8
    STOP_ROW_MAX = 0.22
    STOP_SCALE_MAX = 1.5
    # space between the bar and the Stop button, normal and next to a stretched bar
    BAR_ROW_SPACING = 8
    BAR_ROW_SPACING_STRETCHED = 12

    def __init__(
        self,
        parent: QWidget | None = None,
        client=None,
        config=None,
        gui_id: str | None = None,
        show_details: bool = True,
        fill_height: bool = True,
        show_stop_button: bool = True,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, config=config, gui_id=gui_id, **kwargs)
        self.get_bec_shortcuts()
        self._show_details = show_details
        self._fill_height = fill_height
        self._show_stop_button = show_stop_button
        self._confirm_before_stop = False
        self._pending_action = StopAction.ABORT
        self._state: ScanRunState | None = None
        self._details_key: tuple | None = None

        self._build_ui()
        self._confirm_timer = QTimer(self)
        self._confirm_timer.setSingleShot(True)
        self._confirm_timer.setInterval(6000)
        self._confirm_timer.timeout.connect(self.cancel_stop)

        self.tracker = ScanHookTracker(self.client, self.bec_dispatcher, parent=self)
        self.tracker.changed.connect(self._on_state)
        self.tracker.tick.connect(self._refresh_live)
        self.tracker.start()
        self._render()

    ################################################################################
    # UI
    ################################################################################

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # the title row holds the title and the scan parameters, also as a tooltip on it and the
        # metadata chips; the elided title shows its own full text when cut
        self.header_row = QWidget(self)
        header = QHBoxLayout(self.header_row)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        self.title_label = ElidedLabel(parent=self.header_row)
        self.title_label.setFont(mono_font(0, bold=True))
        self.title_label.setMinimumHeight(self.title_label.fontMetrics().height())
        # the scan arguments follow the title and take what is left, elided
        self.args_label = ElidedLabel(parent=self.header_row)
        self.args_label.setFont(mono_font(-1))
        self.state_chip = Chip("Idle", Tone.NEUTRAL, self.header_row)
        header.addWidget(self.title_label, 1)
        header.addWidget(self.args_label, 1)
        header.addWidget(self.state_chip)
        layout.addWidget(self.header_row)

        self.chips = FlowLayoutWidget(self, horizontal_spacing=4, vertical_spacing=4)
        layout.addWidget(self.chips)

        bar_row = QHBoxLayout()
        bar_row.setSpacing(self.BAR_ROW_SPACING)
        self.bar = StageBar(self, height=26)
        self.stop_button = StopButton(
            parent=self, client=self.client, rpc_exposed=False, rpc_passthrough_children=False
        )
        self.stop_button.action_handler = self._on_stop_action
        self._stop_base_size = QFontInfo(self.stop_button.button.font()).pixelSize()
        self._stop_key: tuple | None = None
        self.bar.sizing_changed.connect(self._style_stop_button)
        bar_row.addWidget(self.bar, 1)
        bar_row.addWidget(self.stop_button)
        self.stop_button.setVisible(self._show_stop_button)
        layout.addLayout(bar_row)
        self._layout = layout
        self._bar_row = bar_row
        self._apply_fill_height()

        self.confirm_frame = QFrame(self)
        self.confirm_frame.setObjectName("scan_progress_confirm")
        confirm = QHBoxLayout(self.confirm_frame)
        confirm.setContentsMargins(8, 4, 4, 4)
        confirm.setSpacing(6)
        self.confirm_label = ElidedLabel(parent=self.confirm_frame)
        self.confirm_label.setMinimumHeight(self.confirm_label.fontMetrics().height())
        self.confirm_stop_button = QPushButton("Stop scan", self.confirm_frame)
        self.confirm_stop_button.setProperty("variant", "danger")
        self.confirm_stop_button.clicked.connect(self.stop_scan)
        self.confirm_cancel_button = QPushButton("Cancel", self.confirm_frame)
        self.confirm_cancel_button.clicked.connect(self.cancel_stop)
        confirm.addWidget(self.confirm_label, 1)
        confirm.addWidget(self.confirm_stop_button)
        confirm.addWidget(self.confirm_cancel_button)
        self.confirm_frame.setVisible(False)
        layout.addWidget(self.confirm_frame)

        self.instruction_label = ElidedLabel(parent=self)
        self.instruction_label.setFont(mono_font(-1))
        self.instruction_label.setMinimumHeight(self.instruction_label.fontMetrics().height())
        layout.addWidget(self.instruction_label)

        self.footer = QFrame(self)
        self.footer.setObjectName("scan_progress_footer")
        footer = QHBoxLayout(self.footer)
        footer.setContentsMargins(0, 6, 0, 0)
        footer.setSpacing(8)
        self.next_label = ElidedLabel(parent=self.footer)
        self.next_label.setMinimumHeight(self.next_label.fontMetrics().height())
        self.step_times = StepTimesLabel(self.footer)
        footer.addWidget(self.next_label, 1)
        footer.addWidget(self.step_times)
        layout.addWidget(self.footer)

        self._apply_styles()

    def _apply_styles(self) -> None:
        colors = theme_colors()
        muted = css(colors["muted"])
        self.args_label.setStyleSheet(f"color: {muted};")
        self.instruction_label.setStyleSheet(f"color: {muted};")
        self.next_label.setStyleSheet(f"color: {muted};")
        self.step_times.setStyleSheet(f"color: {muted};")
        self.footer.setStyleSheet(
            f"#scan_progress_footer {{ border-top: 1px solid {css(colors['border'], 0.6)}; }}"
        )
        self._style_stop_button(force=True)
        self.confirm_frame.setStyleSheet(
            f"#scan_progress_confirm {{ background: {css(colors['bad'], 0.10)};"
            f" border: 1px solid {css(colors['bad'], 0.45)}; border-radius: 6px; }}"
        )
        self.state_chip.refresh_style()

    @SafeSlot()
    def _style_stop_button(self, force: bool = False) -> None:
        """
        Size the Stop button with the bar: on a stretched bar it takes the bar's height and its
        text grows like the bar label; unstretched it keeps its normal look at the bar's height.

        The scale comes from the bar height and the width of the whole bar row (bar and button),
        not from the bar's own width: the button's width changes the bar's width, and following
        that would make the two resize each other in a loop.
        """
        stretched = self.bar.stretched
        row_width = self._bar_row.geometry().width() or self.width()
        scale = self.bar.label_scale(self.bar.height(), row_width * self.STOP_ROW_SHARE)
        bar_height = self.bar.get_bar_height()
        key = (scale, stretched, row_width, bar_height)
        if key == self._stop_key and not force:
            return
        self._stop_key = key
        # the button grows more gently than the label and stays a small part of the row
        stop = self.stop_button
        stop.set_stretch(stretched)
        stop.compact_emergency = stretched
        self._bar_row.setSpacing(
            self.BAR_ROW_SPACING_STRETCHED if stretched else self.BAR_ROW_SPACING
        )
        target = min(self.STOP_SCALE_MAX, 1.0 + (scale - 1.0) * 0.5)
        if not stretched:
            # both parts take the bar's exact height, so their outlines line up with the bar
            self._size_stop(1.0 if target <= 1.0 else target, height=bar_height)
            stop.setMinimumWidth(0)
            stop.setMaximumWidth(16777215)
            self.bar.scale_width = row_width * self.STOP_ROW_SHARE
            return
        # fit to the box: the largest scale whose widest label ("Stop" or "E-Stop") fits the
        # cap, measured by Qt with the real fonts; at the base scale it takes what it needs
        cap = int(row_width * self.STOP_ROW_MAX)
        candidate = target
        while True:
            self._size_stop(candidate)
            needed = stop.required_width()
            if needed <= cap or candidate <= 1.0:
                break
            candidate = max(1.0, candidate - 0.1)
        width = min(cap, needed) if needed <= cap else needed
        stop.setFixedWidth(width)
        # the bar label is sized for the room the bar really has next to the button
        spacing = self._bar_row.spacing()
        self.bar.scale_width = max(80, row_width - width - spacing)
        self.bar.update()

    def _size_stop(self, stop_scale: float, height: int | None = None) -> None:
        self.stop_button.set_size(
            height=height,
            font_px=self._stop_base_size * stop_scale if stop_scale > 1.0 else None,
            radius=6 if stop_scale <= 1.0 else min(10, round(6 * stop_scale)),
            pad=round(10 * stop_scale),
        )

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._style_stop_button()

    def apply_theme(self, theme: str):
        """Restyle after a theme change."""
        self._apply_styles()
        self.step_times.refresh_style()
        self._details_key = None
        self._render()

    ################################################################################
    # Properties
    ################################################################################

    @SafeProperty(bool)
    def show_details(self) -> bool:
        """
        Show the scan's user metadata as chips under the title (e.g. "sample LaB6"). Scans
        without user metadata show no chips either way; the scan arguments always follow the
        title.
        """
        return self._show_details

    @show_details.setter
    def show_details(self, show: bool) -> None:
        self._show_details = show
        self._details_key = None
        self._render()

    @SafeProperty(int)
    def bar_height(self) -> int:
        """Height of the progress bar in pixels, for large screens."""
        return self.bar.get_bar_height()

    @bar_height.setter
    def bar_height(self, height: int) -> None:
        self.bar.set_bar_height(height)
        self._style_stop_button()

    @SafeProperty(bool)
    def fill_height(self) -> bool:
        """Let the bar take all spare vertical space, with its label scaled to the bar."""
        return self._fill_height

    @fill_height.setter
    def fill_height(self, fill: bool) -> None:
        self._fill_height = fill
        self._apply_fill_height()

    def _apply_fill_height(self) -> None:
        self.bar.set_fill_height(self._fill_height)
        self._layout.setStretchFactor(self._bar_row, 1 if self._fill_height else 0)

    @SafeProperty(bool)
    def show_stop_button(self) -> bool:
        """Show the Stop button next to the bar; hidden, the bar takes its width."""
        return self._show_stop_button

    @show_stop_button.setter
    def show_stop_button(self, show: bool) -> None:
        self._show_stop_button = show
        if not show:
            self.cancel_stop()
        self.stop_button.setVisible(show)

    @property
    def state(self) -> ScanRunState | None:
        """The scan state currently shown."""
        return self._state

    ################################################################################
    # Rendering
    ################################################################################

    @SafeSlot(object)
    def _on_state(self, state: ScanRunState | None) -> None:
        if self._state is not state:
            self.cancel_stop()
            self.bar.reset_reserved()
        self._state = state
        self._render()
        self.state_changed.emit(state)

    @SafeSlot()
    def _refresh_live(self) -> None:
        self._render()

    def _render(self) -> None:
        info = describe_state(self._state)
        # as wide as its text, so the arguments start right after it
        self.title_label.setMaximumWidth(
            self.title_label.fontMetrics().horizontalAdvance(info["title"]) + 2
        )
        self.title_label.setText(info["title"])
        self.state_chip.setText(info["chip"])
        self.state_chip.set_tone(info["chip_tone"])
        self.bar.set_state(info["bar_mode"], info["bar_fraction"], info["bar_text"])
        self.stop_button.setEnabled(info["can_stop"])
        self.stop_button.request_id = self._state.rid if self._state is not None else None
        if not info["can_stop"] and self.confirm_frame.isVisible():
            self.cancel_stop()
        self.instruction_label.setText(info["instruction"])
        self.next_label.setText(info["next"])
        self.step_times.setVisible(bool(self._state and self._state.timings))
        self.step_times.set_state(self._state)
        # keep the footer while a scan is shown so the widget does not change height mid-scan
        self.footer.setVisible(self._state is not None)
        self._render_details()

    def _render_details(self) -> None:
        state = self._state
        args = ""
        if state is not None:
            names = scan_bundle_names(getattr(self.client, "scans", None), state.scan_name)
            args = request_inputs_summary(state.request_inputs, names)
        self.args_label.setText(args)
        if state is not None and state.scan_name and state.display_name != state.scan_name:
            # a scan with its own name: the scan type is still one hover away
            args = f"{state.scan_name}: {args}" if args else state.scan_name
        items = metadata_items(state.user_metadata) if state else []
        key = (self._show_details, args, tuple(items))
        if key == self._details_key:
            return
        self._details_key = key
        self.header_row.setToolTip(args)
        self.chips.setToolTip(args)
        flow = self.chips.flow_layout
        while flow.count():
            item = flow.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for k, v in items:
            flow.addWidget(MetaChip(k, v, self.chips))
        self.chips.setVisible(self._show_details and bool(items))

    ################################################################################
    # Stop
    ################################################################################

    def _on_stop_action(self, action: StopAction) -> bool:
        """
        StopButton hook: with confirm_before_stop, abort and finish ask first. Halt never asks.

        Returns:
            bool: True when the confirmation row took over the action.
        """
        if self._confirm_before_stop and action in (StopAction.ABORT, StopAction.FINISH):
            self.ask_stop(action)
            return True
        return False

    @SafeSlot()
    def ask_stop(self, action: StopAction | str = StopAction.ABORT) -> None:
        """Ask for confirmation before stopping (abort) or finishing the scan."""
        if not self._show_stop_button or self._state is None or self._state.finished:
            return
        info = describe_state(self._state)
        action = StopAction(action)
        self._pending_action = action
        if action == StopAction.FINISH:
            self.confirm_label.setText(f"Finish scan {info['title']} now?")
            self.confirm_stop_button.setText("Finish now")
        else:
            self.confirm_label.setText(f"Stop scan {info['title']}?")
            self.confirm_stop_button.setText("Stop scan")
        self.confirm_frame.setVisible(True)
        self.stop_button.setVisible(False)
        self._confirm_timer.start()

    @SafeSlot()
    def cancel_stop(self) -> None:
        """Close the stop confirmation without stopping."""
        self._confirm_timer.stop()
        self.confirm_frame.setVisible(False)
        self.stop_button.setVisible(self._show_stop_button)

    @SafeSlot()
    def stop_scan(self) -> None:
        """Run the confirmed action (abort by default) on the scan shown in the widget."""
        state = self._state
        action = self._pending_action
        self.cancel_stop()
        if state is None or state.finished:
            return
        logger.info(f"{action} scan {state.scan_number} ({state.rid})")
        self.stop_button.request_id = state.rid
        self.stop_button.perform(action)
        if action == StopAction.ABORT:
            self.state_chip.setText("Stopping…")
            self.state_chip.set_tone(Tone.BAD)

    @SafeProperty(bool)
    def confirm_before_stop(self) -> bool:
        """Ask in a confirmation row before aborting or finishing (off: act at once)."""
        return self._confirm_before_stop

    @confirm_before_stop.setter
    def confirm_before_stop(self, confirm: bool) -> None:
        self._confirm_before_stop = confirm
        if not confirm:
            self.cancel_stop()

    def cleanup(self):
        """Stop the timers and disconnect the tracker."""
        self._confirm_timer.stop()
        self.tracker.cleanup()
        self.bar.cleanup()
        self.step_times.popup.close()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = ScanProgressBar()
    widget.resize(460, 220)
    widget.show()
    sys.exit(app.exec_())
