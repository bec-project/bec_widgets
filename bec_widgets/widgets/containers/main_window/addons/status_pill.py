"""
Status-bar pills for the main window: a small state bar that opens a card with its full widget on
hover. A pill item shows a ToolIndicator (severity, summary, badge, progress); subclasses feed the
indicator and give the card its content, e.g. the scan pill with the full ScanProgressBar.

The card and its hover handling live in bec_widgets.utils.hover_card.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from bec_lib.logger import bec_logger
from qtpy.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSettings,
    Qt,
    QTimer,
    Signal,
)
from qtpy.QtGui import QAction, QActionGroup, QPainter, QPen
from qtpy.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QMenu, QSizePolicy, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.hover_card import KEYBOARD_FOCUS_REASONS, HoverCard, HoverCardController
from bec_widgets.utils.theme_utils import theme_colors
from bec_widgets.widgets.progress.stage_bar import BarMode, Chip, StageBar, Tone

logger = bec_logger.logger

# (normal, large) pill widths in pixels; "fill" stretches with a minimum width
PILL_WIDTHS = {"compact": (150, 200), "normal": (280, 380), "wide": (480, 620)}
PILL_FILL_MIN = 220
PILL_MODES = ("compact", "normal", "wide", "fill")


class ToolSeverity(StrEnum):
    """How a status-bar pill rates what it reports."""

    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ToolIndicator:
    """
    What a status-bar pill shows.

    Args:
        severity(ToolSeverity): ok, info, warning or critical; sets the colour of the bar.
        summary(str): The pill label.
        badge(str | None): Short text in a chip next to the pill, e.g. "3 waiting"; None hides it.
        progress(float | None): Filled share 0..1 of something that runs, or None.
        attention(bool): Whether the badge asks for attention (shown in the danger colour).
        tooltip(str): Tooltip of the pill.
        active(bool): Something runs without a known progress; shows the moving stripes. Only
            while it runs, so a long-lived state (a busy server) does not animate all the time.
    """

    severity: ToolSeverity = ToolSeverity.INFO
    summary: str = ""
    badge: str | None = None
    progress: float | None = None
    attention: bool = False
    tooltip: str = ""
    active: bool = False


def stage_mode(indicator: ToolIndicator) -> tuple[BarMode, float]:
    """
    The StageBar mode and filled share for an indicator.

    Returns:
        tuple[BarMode, float]: (mode, fraction).
    """
    severity = ToolSeverity(indicator.severity)
    if severity == ToolSeverity.CRITICAL:
        return BarMode.ERROR, 1.0
    if severity == ToolSeverity.WARNING:
        return BarMode.PAUSED, indicator.progress or 0.0
    if indicator.progress is not None:
        return BarMode.PROGRESS, indicator.progress
    if indicator.active:
        return BarMode.BUSY, 0.0
    if severity == ToolSeverity.OK:
        return BarMode.DONE, 1.0
    return BarMode.IDLE, 0.0


def _default_settings() -> QSettings:
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.containers.dock_area.profile_utils import _app_settings

    return _app_settings()


class Reveal(QObject):
    """
    Slides a widget in and out of a row: its maximum width animates between 0 and its natural
    width while it fades, so the row never jumps. Showing is immediate; hiding waits until the
    widget has not been wanted for HIDE_DELAY_MS, so a state that flips back and forth (e.g. at
    the start of a scan) does not make it blink.
    """

    DURATION_MS = 180
    HIDE_DELAY_MS = 600
    MAX_WIDTH = 16777215

    def __init__(self, widget: QWidget, parent: QObject | None = None):
        super().__init__(parent)
        self.widget = widget
        self._shown = False
        self._effect = QGraphicsOpacityEffect(widget)
        self._effect.setOpacity(0.0)
        widget.setGraphicsEffect(self._effect)
        self._width = QPropertyAnimation(widget, b"maximumWidth", self)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._group = QParallelAnimationGroup(self)
        for anim in (self._width, self._fade):
            anim.setDuration(self.DURATION_MS)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._group.addAnimation(anim)
        self._group.finished.connect(self._on_finished)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(self.HIDE_DELAY_MS)
        self._hide_timer.timeout.connect(self._animate_out)
        widget.setMaximumWidth(0)
        widget.setVisible(False)

    @property
    def shown(self) -> bool:
        """Whether the widget is (being) shown."""
        return self._shown

    @property
    def active(self) -> bool:
        """Whether an animation or the hide delay is running."""
        running = self._group.state() == QParallelAnimationGroup.State.Running
        return running or self._hide_timer.isActive()

    def set_shown(self, shown: bool) -> None:
        """Ask for the widget to be shown or hidden; cheap to call on every update."""
        if shown:
            self._hide_timer.stop()
            if not self._shown:
                self._animate_in()
        elif self._shown and not self._hide_timer.isActive():
            self._hide_timer.start()

    def _animate(self, width: int, opacity: float) -> None:
        self._group.stop()
        self._width.setStartValue(min(self.widget.maximumWidth(), self.widget.sizeHint().width()))
        self._width.setEndValue(width)
        self._fade.setStartValue(self._effect.opacity())
        self._fade.setEndValue(opacity)
        self._group.start()

    def _animate_in(self) -> None:
        self._shown = True
        self.widget.setVisible(True)
        self.widget.setEnabled(True)
        self._animate(self.widget.sizeHint().width(), 1.0)

    def _animate_out(self) -> None:
        self._shown = False
        self.widget.setEnabled(False)
        self._animate(0, 0.0)

    def _on_finished(self) -> None:
        if self._shown:
            self.widget.setMaximumWidth(self.MAX_WIDTH)
        else:
            self.widget.setVisible(False)

    def stop(self) -> None:
        """Stop the animations and the hide delay (before deletion)."""
        self._hide_timer.stop()
        self._group.stop()


class StatusBarPill(StageBar):
    """The StageBar in the status bar: a hover outline, a hand cursor and a settings menu."""

    menu_requested = Signal(QPoint)
    double_clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, height=22)
        self.corner_radius = 5
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self._hovered = False
        self._keyboard_focus = False

    @property
    def hovered(self) -> bool:
        """Whether the hover outline is shown."""
        return self._hovered

    @property
    def keyboard_focus(self) -> bool:
        """
        Whether the user tabbed to the pill. Qt also gives it focus when the window is activated
        (it is often the only Tab widget there), which must not open the card or draw the outline.
        """
        return self._keyboard_focus

    def focusInEvent(self, event):  # pylint: disable=invalid-name
        self._keyboard_focus = event.reason() in KEYBOARD_FOCUS_REASONS
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):  # pylint: disable=invalid-name
        self._keyboard_focus = False
        super().focusOutEvent(event)
        self.update()

    def set_hovered(self, hovered: bool) -> None:
        """Show or clear the hover outline. The owner clears it when the cursor has left, since
        a Leave event does not always arrive (e.g. on macOS while the card window is shown)."""
        if hovered != self._hovered:
            self._hovered = hovered
            self.update()

    def event(self, event):  # pylint: disable=invalid-name
        if event.type() == QEvent.Type.HoverEnter:
            self.set_hovered(True)
        elif event.type() == QEvent.Type.HoverLeave:
            self.set_hovered(False)
        return super().event(event)

    def contextMenuEvent(self, event):  # pylint: disable=invalid-name
        self.menu_requested.emit(event.globalPos())

    def mouseDoubleClickEvent(self, event):  # pylint: disable=invalid-name
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self.double_clicked.emit()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):  # pylint: disable=invalid-name
        super().paintEvent(event)
        if not (self._hovered or self._keyboard_focus):
            return
        rect = self._bar_rect()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(theme_colors()["primary"], 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        radius = min(self.corner_radius or 5, rect.height() / 2)
        painter.drawRoundedRect(QRectF(rect), radius, radius)
        painter.end()


class StatusPillItem(BECWidget, QWidget):
    """
    A status-bar pill with a badge chip and optional widgets next to it, and a card with the full
    widget on hover. Subclasses set the indicator (set_indicator) and the card content, and call
    apply_sizes() once their own widgets exist.

    The pill width (compact, normal, wide, fill) and the large size are chosen in its right-click
    menu and saved per user under the settings prefix.

    Signals:
        fill_changed(bool): The pill switched to or from filling the status bar.
        indicator_changed(object): A new ToolIndicator is shown.
    """

    RPC = False
    PLUGIN = False
    GRACE_MS = HoverCardController.GRACE_MS

    fill_changed = Signal(bool)
    indicator_changed = Signal(object)
    dock_requested = Signal(str)

    # class name of the widget a double-click on the pill opens in the dock area; None: no docking
    DOCK_WIDGET: str | None = None
    DOCK_HINT = "Double-click to add it to the current dock area"

    def __init__(
        self,
        parent: QWidget | None = None,
        client=None,
        settings: Callable[[], QSettings] | None = None,
        settings_prefix: str = "status_pill",
        card_content: QWidget | None = None,
        card_width: int | None = None,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, **kwargs)
        self._settings_factory = settings or _default_settings
        self._settings_prefix = settings_prefix
        self._width_mode = "normal"
        self._large = False
        self._indicator = ToolIndicator()
        self._load_settings()

        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(6, 0, 6, 0)
        self.row.setSpacing(6)
        self.pill = StatusBarPill(self)
        self.pill.menu_requested.connect(self._show_menu)
        self.badge_chip = Chip("", Tone.NEUTRAL, self)
        self.row.addWidget(self.pill, 1)
        self.row.addWidget(self.badge_chip)
        self.badge_reveal = Reveal(self.badge_chip, self)
        self._reveals: list[Reveal] = [self.badge_reveal]

        self._card_content = card_content
        self._card_width = card_width
        self.card = self.create_card()
        self.card.hide()
        self._dock_available: Callable[[], bool] | None = None
        if self.DOCK_WIDGET:
            self.card.add_hint(self.DOCK_HINT).setVisible(False)
            self.pill.double_clicked.connect(self._request_dock)
        self.hover = HoverCardController(
            self.pill,
            self.card,
            keep_open=self.keep_card_open,
            can_open=self._prepare_card,
            on_close=self.on_card_closed,
        )

    def create_card(self) -> HoverCard:
        """The hover card; subclasses may return their own, e.g. with a fixed content widget."""
        return HoverCard(self, self._card_content, width=self._card_width)

    ################################################################################
    # Layout
    ################################################################################

    def add_trailing(self, widget: QWidget, reveal: bool = True) -> Reveal | None:
        """
        Put a widget between the pill and the badge; it counts as part of the pill for the hover.

        Args:
            widget(QWidget): The widget, e.g. a Stop button.
            reveal(bool): Slide it in and out with a Reveal instead of keeping it shown.

        Returns:
            Reveal | None: The Reveal that shows and hides it, if requested.
        """
        self.row.insertWidget(self.row.indexOf(self.badge_chip), widget)
        self.hover.add_extra(widget)
        if not reveal:
            return None
        widget_reveal = Reveal(widget, self)
        self._reveals.append(widget_reveal)
        return widget_reveal

    ################################################################################
    # Settings
    ################################################################################

    def _settings_key(self, name: str) -> str:
        return f"{self._settings_prefix}/{name}"

    def _load_settings(self) -> None:
        try:
            settings = self._settings_factory()
            mode = str(settings.value(self._settings_key("pill_width"), "normal"))
            self._large = settings.value(self._settings_key("large"), False, type=bool)
        except Exception:  # pylint: disable=broad-except
            logger.debug(f"Could not read the {self._settings_prefix} pill settings")
            return
        self._width_mode = mode if mode in PILL_MODES else "normal"

    def _save_settings(self) -> None:
        try:
            settings = self._settings_factory()
            settings.setValue(self._settings_key("pill_width"), self._width_mode)
            settings.setValue(self._settings_key("large"), self._large)
            settings.sync()
        except Exception:  # pylint: disable=broad-except
            logger.debug(f"Could not save the {self._settings_prefix} pill settings")

    @property
    def width_mode(self) -> str:
        """compact, normal, wide or fill."""
        return self._width_mode

    def set_width_mode(self, mode: str) -> None:
        """Choose the pill width and save it."""
        if mode not in PILL_MODES or mode == self._width_mode:
            return
        was_fill = self._width_mode == "fill"
        self._width_mode = mode
        self._save_settings()
        self.apply_sizes()
        if was_fill != (mode == "fill"):
            self.fill_changed.emit(mode == "fill")

    @property
    def large(self) -> bool:
        """Whether the large status bar sizes are used."""
        return self._large

    def set_large(self, large: bool) -> None:
        """Switch between the normal and the large status bar sizes, and save it."""
        if large == self._large:
            return
        self._large = large
        self._save_settings()
        self.apply_sizes()

    def build_menu(self) -> QMenu:
        """The pill's right-click menu: width choice and the large size."""
        menu = QMenu(self)
        menu.addSection("Pill width")
        group = QActionGroup(menu)
        group.setExclusive(True)
        for mode in PILL_MODES:
            action = QAction(mode.capitalize(), menu)
            action.setCheckable(True)
            action.setChecked(mode == self._width_mode)
            action.setData(mode)
            action.triggered.connect(lambda _checked=False, m=mode: self.set_width_mode(m))
            group.addAction(action)
            menu.addAction(action)
        menu.addSeparator()
        large = QAction("Large status bar", menu)
        large.setCheckable(True)
        large.setChecked(self._large)
        large.toggled.connect(self.set_large)
        menu.addAction(large)
        return menu

    @SafeSlot(QPoint)
    def _show_menu(self, pos: QPoint) -> None:
        self.close_card()
        menu = self.build_menu()
        menu.exec(pos)
        menu.deleteLater()

    ################################################################################
    # Sizes and theme
    ################################################################################

    @property
    def bar_height(self) -> int:
        """Height of the pill and the widgets next to it."""
        return 34 if self._large else 22

    def apply_sizes(self) -> None:
        """Apply the pill width mode and the normal/large heights and fonts."""
        height = self.bar_height
        self.pill.set_bar_height(height)
        self.pill.setFixedHeight(height)
        self.pill.label_pixel_size = 15 if self._large else 12
        if self._width_mode == "fill":
            self.pill.setMinimumWidth(PILL_FILL_MIN)
            self.pill.setMaximumWidth(16777215)
            self.pill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        else:
            width = PILL_WIDTHS[self._width_mode][1 if self._large else 0]
            self.pill.setFixedWidth(width)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.badge_chip.setFixedHeight(height)
        self.pill.update()
        self.render_indicator()

    def apply_theme(self, theme: str):
        """Restyle after a theme change."""
        self.card.refresh_style()
        self.badge_chip.refresh_style()
        self.pill.update()

    ################################################################################
    # Indicator
    ################################################################################

    @property
    def indicator(self) -> ToolIndicator:
        """The indicator shown by the pill."""
        return self._indicator

    def set_indicator(self, indicator: ToolIndicator) -> None:
        """Show an indicator; cheap to call on every update."""
        changed = indicator != self._indicator
        self._indicator = indicator
        self.render_indicator()
        if changed:
            self.indicator_changed.emit(indicator)

    def pill_text(self) -> str:
        """The pill label; subclasses may vary it with the width mode."""
        return self._indicator.summary

    @SafeSlot()
    def render_indicator(self) -> None:
        """Draw the current indicator on the pill and the badge."""
        indicator = self._indicator
        mode, fraction = stage_mode(indicator)
        self.pill.set_state(mode, fraction, self.pill_text())
        self._update_tooltip()
        if indicator.badge:
            self.badge_chip.setText(indicator.badge)
            self.badge_chip.set_tone(Tone.BAD if indicator.attention else Tone.NEUTRAL)
        self.badge_reveal.set_shown(bool(indicator.badge))

    ################################################################################
    # Card
    ################################################################################

    def keep_card_open(self) -> bool:
        """Whether the card stays open although the cursor has left; for subclasses."""
        return False

    def set_dock_handler(self, available: Callable[[], bool] | None) -> None:
        """
        Let a double-click on the pill request its DOCK_WIDGET (dock_requested) while
        ``available()`` is True; the window that hosts the pill handles the request.

        Args:
            available(Callable[[], bool] | None): Whether a dock area can take the widget now;
                None hides the button.
        """
        self._dock_available = available
        self._prepare_card()

    @property
    def can_dock(self) -> bool:
        """Whether a double-click on the pill opens its widget in a dock area now."""
        available = self._dock_available
        return bool(self.DOCK_WIDGET) and available is not None and available()

    def _prepare_card(self) -> bool:
        """Show the docking hint before the card opens, if docking works; the card always opens."""
        can_dock = self.can_dock
        if self.card.hint is not None:
            self.card.hint.setVisible(can_dock)
        self.pill.setAccessibleDescription(self.DOCK_HINT if can_dock else "")
        self._update_tooltip()
        return True

    def _update_tooltip(self) -> None:
        """The indicator's tooltip, with the docking hint when a double-click can dock."""
        lines = [self._indicator.tooltip] if self._indicator.tooltip else []
        if self.can_dock:
            lines.append(self.DOCK_HINT)
        tooltip = "\n".join(lines)
        if self.pill.toolTip() != tooltip:
            self.pill.setToolTip(tooltip)

    @SafeSlot()
    def _request_dock(self) -> None:
        if not self.can_dock:
            return
        self.close_card()
        self.dock_requested.emit(self.DOCK_WIDGET)

    def on_card_closed(self) -> None:
        """Called when the card closes, e.g. to drop a pending confirmation; for subclasses."""

    def open_card(self) -> None:
        """Show the card above the pill."""
        self.hover.open()

    def close_card(self) -> None:
        """Hide the card and clear the hover state."""
        self.hover.close()

    @property
    def _poll(self) -> QTimer:
        return self.hover.poll

    @property
    def _outside_since(self) -> float | None:
        return self.hover.outside_since

    def _check_cursor(self) -> None:
        self.hover.check_cursor()

    def hideEvent(self, event):  # pylint: disable=invalid-name
        super().hideEvent(event)
        self.close_card()

    def changeEvent(self, event):  # pylint: disable=invalid-name
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowDeactivate:
            self.hover.anchor_window_deactivated()

    def cleanup(self):
        """Stop the hover poll and the animations and close the card."""
        self.hover.cleanup()
        for widget_reveal in self._reveals:
            widget_reveal.stop()
        self.card.close()
        super().cleanup()
