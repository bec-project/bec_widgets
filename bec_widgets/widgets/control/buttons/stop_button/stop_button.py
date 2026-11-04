from __future__ import annotations

import math
from enum import StrEnum
from typing import Callable

from qtpy.QtCore import QEvent, QSize, Qt, QTimer
from qtpy.QtGui import QAction, QColor, QFont, QFontInfo, QFontMetricsF, QIcon, QPainter, QPen
from qtpy.QtWidgets import (
    QAbstractButton,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.theme_utils import crisp_icon, css, theme_colors


class StopAction(StrEnum):
    """The ways a StopButton ends a scan."""

    ABORT = "abort"  # stop it; it is kept as aborted
    FINISH = "finish"  # end it now and keep it as completed
    HALT = "halt"  # emergency stop without cleanup


class _ArrowButton(QToolButton):
    """The narrow dropdown segment of the StopButton, with a quiet inset divider on its left."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.divider_color = QColor(0, 0, 0, 0)

    def paintEvent(self, event):  # pylint: disable=invalid-name
        super().paintEvent(event)
        inset = round(self.height() * 0.25)
        painter = QPainter(self)
        painter.setPen(QPen(self.divider_color, 1))
        painter.drawLine(0, inset, 0, self.height() - inset)
        painter.end()


class StopButton(BECWidget, QWidget):
    """
    A button that stops the current scan.

    A click aborts the scan; for the next two seconds the button turns into "Emergency Stop",
    and a click there halts it (an emergency stop without cleanup). The arrow next to it opens
    a menu with the other ways to end a scan: finish it now and keep it as completed, abort it,
    or halt it at once.

    It looks the same everywhere: a light red button with a red outline that fills with red
    under the cursor, and a dark red Emergency Stop. Its host only decides the size (set_size),
    e.g. the form button height in ScanControl or the height of a progress bar next to it.
    """

    PLUGIN = True
    ICON_NAME = "dangerous"
    RPC = False
    ABORT_LABEL = "Stop"
    EMERGENCY_STOP_LABEL = "Emergency Stop"
    EMERGENCY_STOP_SHORT_LABEL = "E-Stop"  # when the button may not grow (e.g. next to a tall bar)
    EMERGENCY_STOP_TIMEOUT_MS = 2000
    ICON_GAP = 4  # Qt's gap between a push button's icon and its text
    WIDTH_SLACK = 4  # spare width so the label never touches the arrow's divider

    def __init__(self, parent=None, client=None, config=None, gui_id=None, toolbar=False, **kwargs):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)

        self.get_bec_shortcuts()
        self._toolbar = toolbar
        self._hovered: set[str] = set()  # the parts under the cursor, for their icon colour
        self.request_id: str | None = None  # the scan to stop; None stops the current one
        # a host may intercept an action, e.g. to ask for confirmation first; it returns True
        # when it handled the action and the button should not act on its own
        self.action_handler: Callable[[StopAction], bool] | None = None
        self.compact_emergency = False
        self._device_stop = False

        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._emergency_stop_active = False
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._deactivate_emergency_stop)

        self.menu = self._build_menu()
        self.button: QAbstractButton
        if toolbar:
            self.button = QToolButton(self)
            self.button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            self.button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
            self.button.setMenu(self.menu)
        else:
            self.button = QPushButton(self)
            self.button.setAttribute(Qt.WidgetAttribute.WA_Hover)
            # like a plain push button: shares a row evenly with its neighbours (e.g. Start)
            self.button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.button.setObjectName("bec_stop_button")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setText(self.ABORT_LABEL)
        self.button.setToolTip(self.ABORT_LABEL)
        self.button.clicked.connect(self.stop_scan)
        self.layout.addWidget(self.button)

        self.arrow = _ArrowButton(self)
        self.arrow.setObjectName("bec_stop_arrow")
        self.arrow.setCursor(Qt.CursorShape.PointingHandCursor)
        self.arrow.setToolTip("More ways to end the scan")
        self.arrow.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.arrow.setMenu(self.menu)
        self.arrow.setVisible(not toolbar)
        self.layout.addWidget(self.arrow)
        for part in (self.button, self.arrow):
            part.installEventFilter(self)
            part.pressed.connect(self._refresh_icons)
            part.released.connect(self._refresh_icons)

        self._size = {"height": None, "font_px": None, "icon_px": None, "radius": 4, "pad": 10}
        self.refresh_style()

    @SafeProperty(bool)
    def device_stop(self) -> bool:
        """
        Stop devices instead of a scan, e.g. the Stop of a motor box: no menu with the ways to end
        a scan, and a click does nothing to the scan queue (no abort, no Emergency Stop). The
        host stops its devices on button.clicked.
        """
        return self._device_stop

    @device_stop.setter
    def device_stop(self, device_stop: bool) -> None:
        self._device_stop = bool(device_stop)
        self.arrow.setVisible(not self._device_stop and not self._toolbar)
        if self._toolbar:
            self.button.setMenu(None if self._device_stop else self.menu)
        if self._device_stop and self._emergency_stop_active:
            self._reset_timer.stop()
            self._deactivate_emergency_stop()
        self.refresh_style()

    def _build_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        self.finish_action = QAction("Finish scan now", menu)
        self.finish_action.setToolTip("End the scan now and keep it as completed")
        self.finish_action.triggered.connect(lambda: self._act(StopAction.FINISH))
        self.abort_action = QAction("Abort scan", menu)
        self.abort_action.setToolTip("Stop the scan; it is kept as aborted")
        self.abort_action.triggered.connect(lambda: self._act(StopAction.ABORT))
        self.halt_action = QAction("Emergency stop (halt)", menu)
        self.halt_action.setToolTip("Halt at once, without cleanup")
        self.halt_action.triggered.connect(lambda: self._act(StopAction.HALT))
        for action in (self.finish_action, self.abort_action, self.halt_action):
            menu.addAction(action)
        return menu

    ################################################################################
    # Look
    ################################################################################

    def set_size(
        self,
        height: int | None = None,
        font_px: float | None = None,
        icon_px: int | None = None,
        radius: int = 4,
        pad: int = 10,
    ) -> None:
        """
        Size the button for its host, e.g. a status bar row or a stretched progress bar.
        Without a height it keeps the height of the theme's push buttons.
        """
        size = {"height": height, "font_px": font_px, "icon_px": icon_px, "radius": radius}
        size["pad"] = pad
        if size != self._size:
            self._size = size
            self.refresh_style()

    def set_stretch(self, stretch: bool) -> None:
        """Let the button take all the height its row gives it (e.g. next to a tall bar)."""
        vertical = QSizePolicy.Policy.Expanding if stretch else QSizePolicy.Policy.Fixed
        self.setSizePolicy(QSizePolicy.Policy.Minimum, vertical)
        for part in (self.button, self.arrow):
            part.setSizePolicy(part.sizePolicy().horizontalPolicy(), vertical)
            if stretch:
                part.setMinimumHeight(0)
                part.setMaximumHeight(16777215)

    def _font_px(self) -> float:
        return self._size["font_px"] or QFontInfo(self.button.font()).pixelSize()

    def icon_size_px(self) -> int:
        """
        The stop icon size: the square of the material icon fills about 60% of its box, so a box
        of 1.35 cap heights draws a square of about 0.8 cap heights next to the text.
        """
        if self._size["icon_px"]:
            return self._size["icon_px"]
        font = QFont(self.button.font())
        font.setPixelSize(max(1, round(self._font_px())))
        return max(10, round(QFontMetricsF(font).capHeight() * 1.35))

    def arrow_width(self) -> int:
        """Width of the dropdown arrow segment, growing gently with the text."""
        return max(16, min(24, round(self._font_px() * 1.3)))

    def label_width(self, label: str, with_icon: bool = True) -> float:
        """
        The width the main part needs for a label as it is drawn: the text in the polished font
        (with the size and weight from the style sheet), the icon and its gap, both paddings and
        the border.
        """
        self.button.ensurePolished()
        text = QFontMetricsF(self.button.font()).horizontalAdvance(label)
        icon = self.icon_size_px() + self.ICON_GAP if with_icon else 0
        return text + icon + 2 * self._size["pad"] + 2

    def required_width(self) -> int:
        """
        The width the button needs to show its widest label without clipping: "Stop" with its
        icon, and the Emergency Stop label it switches to (the short one without icon when
        compact_emergency is set), plus the arrow. Each label takes the larger of its measured
        width and Qt's size hint, with WIDTH_SLACK to spare so it never touches the divider.
        """
        button = self.button
        text, icon = button.text(), button.icon()
        widths = []
        emergency = (
            self.EMERGENCY_STOP_SHORT_LABEL if self.compact_emergency else self.EMERGENCY_STOP_LABEL
        )
        for label, with_icon in ((self.ABORT_LABEL, True), (emergency, not self.compact_emergency)):
            button.setText(label)
            if not with_icon:
                button.setIcon(QIcon())
            elif button.icon().isNull():
                button.setIcon(icon)
            button.ensurePolished()
            measured = self.label_width(label, with_icon)
            widths.append(max(measured, button.sizeHint().width()) + self.WIDTH_SLACK)
            button.setIcon(icon)
        button.setText(text)
        button.setIcon(icon)
        if self._device_stop:
            return math.ceil(max(widths))
        arrow = self.arrow.width() if self.arrow.isVisible() else self.arrow_width()
        return math.ceil(max(widths)) + max(arrow, self.arrow_width())

    def refresh_style(self) -> None:
        """Re-read the theme colours and apply the current size and state."""
        if self._toolbar:
            self._refresh_toolbar_style()
        else:
            self._refresh_style()

    def _arrow_icon(self, color: QColor) -> None:
        size = max(12, round(self.arrow_width() * 0.8))
        self.arrow.setIcon(crisp_icon("arrow_drop_down", size, color, False, self.arrow))
        self.arrow.setIconSize(QSize(size, size))

    def _refresh_toolbar_style(self) -> None:
        colors = theme_colors()
        color = colors["on_primary"] if self._emergency_stop_active else colors["bad"]
        self.button.setIcon(crisp_icon("stop", 16, color, True, self.button))
        bad = css(colors["bad"])
        self.button.setStyleSheet(
            f"#bec_stop_button {{ background: {bad}; }}" if self._emergency_stop_active else ""
        )

    def style_colors(self) -> dict[str, QColor]:
        """
        The colours of the current state: background, outline and text at rest, under the
        cursor (hover) and pressed. At rest the button is a light red with a red outline; under
        the cursor it fills with red. While Emergency Stop shows it is a dark red with a light
        label in every state.
        """
        colors = theme_colors()
        bad, on_fill = QColor(colors["bad"]), QColor(colors["on_primary"])
        if self._emergency_stop_active:
            fill = bad.darker(150)
            return {
                "background": fill,
                "border": fill,
                "text": on_fill,
                "hover_background": bad.darker(130),
                "hover_text": on_fill,
                "pressed_background": bad.darker(170),
            }
        tint, outline = QColor(bad), QColor(bad)
        tint.setAlphaF(0.12)
        outline.setAlphaF(0.8)
        return {
            "background": tint,
            "border": outline,
            "text": bad,
            "hover_background": bad,
            "hover_text": on_fill,
            "pressed_background": bad.darker(115),
        }

    def _refresh_style(self) -> None:
        colors = theme_colors()
        look = self.style_colors()
        size = self._size
        emergency = self._emergency_stop_active
        radius = size["radius"]
        font = f" font-size: {size['font_px']:.1f}px;" if size["font_px"] else ""
        weight = "bold" if emergency else "600"
        # without a host height the theme's push button padding keeps it as tall as its
        # neighbours (e.g. Start in ScanControl); only the sides are set
        if size["height"]:
            padding = f" padding: 0 {size['pad']}px;"
        else:
            padding = f" padding-left: {size['pad']}px; padding-right: {size['pad']}px;"
        part = (
            f" background: {css(look['background'])}; color: {css(look['text'])};"
            f" border: 1px solid {css(look['border'])};"
        )
        hover, hover_text = css(look["hover_background"]), css(look["hover_text"])
        pressed = css(look["pressed_background"])
        states = {
            "hover": f"background: {hover}; border-color: {hover}; color: {hover_text};",
            "pressed": f"background: {pressed}; border-color: {pressed}; color: {hover_text};",
            "disabled": (
                f"color: {css(colors['muted'], 0.5)}; border-color: {css(colors['border'])};"
                " background: transparent;"
            ),
        }

        def state_rules(name: str) -> str:
            return "".join(f"#{name}:{state} {{ {rule} }}" for state, rule in states.items())

        if not self._device_stop:
            # joined to the arrow on its right
            corners = (
                " border-right: none;"
                f" border-top-left-radius: {radius}px; border-bottom-left-radius: {radius}px;"
                " border-top-right-radius: 0; border-bottom-right-radius: 0;"
            )
        else:
            corners = f" border-radius: {radius}px;"
        self.button.setStyleSheet(
            f"#bec_stop_button {{{part}{corners}"
            f"{padding} font-weight: {weight};{font} }}" + state_rules("bec_stop_button")
        )
        self.arrow.setStyleSheet(
            f"#bec_stop_arrow {{{part} border-left: none;"
            f" border-top-right-radius: {radius}px; border-bottom-right-radius: {radius}px;"
            " border-top-left-radius: 0; border-bottom-left-radius: 0; padding: 0; }"
            + state_rules("bec_stop_arrow")
            + "#bec_stop_arrow::menu-indicator { image: none; width: 0; }"
        )
        divider = QColor(colors["on_primary"] if emergency else colors["muted"])
        if not self.isEnabled():
            divider = QColor(colors["border"])
        divider.setAlphaF(0.4)
        self.arrow.divider_color = divider
        self._refresh_icons()
        self.arrow.setFixedWidth(self.arrow_width())
        if size["height"]:
            for part_widget in (self.button, self.arrow):
                part_widget.setFixedHeight(size["height"])
        else:
            # the main part sizes itself like any themed push button; the arrow follows it
            self.arrow.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    @SafeSlot()
    def _refresh_icons(self) -> None:
        """Icons in the text colour of each part: red at rest, light under the cursor or down."""
        if self._toolbar:
            return
        look = self.style_colors()
        down = {"button": self.button.isDown(), "arrow": self.arrow.isDown()}

        def color(part: str) -> QColor:
            return look["hover_text"] if part in self._hovered or down[part] else look["text"]

        self._arrow_icon(color("arrow"))
        icon_px = self.icon_size_px()
        if self._emergency_stop_active and self.compact_emergency:
            self.button.setIcon(QIcon())  # the short label alone fits the kept width
        else:
            self.button.setIcon(crisp_icon("stop", icon_px, color("button"), True, self.button))
        self.button.setIconSize(QSize(icon_px, icon_px))

    def eventFilter(self, obj, event):  # pylint: disable=invalid-name
        if obj in (self.button, self.arrow) and event.type() in (
            QEvent.Type.Enter,
            QEvent.Type.Leave,
        ):
            part = "button" if obj is self.button else "arrow"
            if event.type() == QEvent.Type.Enter:
                self._hovered.add(part)
            else:
                self._hovered.discard(part)
            self._refresh_icons()
        return super().eventFilter(obj, event)

    def changeEvent(self, event):  # pylint: disable=invalid-name
        super().changeEvent(event)
        if event.type() == event.Type.EnabledChange:
            self.refresh_style()  # the divider follows the enabled state

    def apply_theme(self, theme: str):
        """Restyle after a theme change."""
        self.refresh_style()

    def click(self) -> None:
        """Click the main part of the button (abort, or halt while Emergency Stop shows)."""
        self.button.click()

    ################################################################################
    # Actions
    ################################################################################

    @SafeSlot(object)
    def _act(self, action: StopAction) -> None:
        handler = self.action_handler
        if callable(handler) and handler(action):  # pylint: disable=not-callable
            return
        self.perform(action)

    def perform(self, action: StopAction | str) -> None:
        """
        Run an action on the scan: abort, finish (keep as completed) or halt.

        Args:
            action(StopAction | str): abort, finish or halt.
        """
        request_id = self.request_id
        action = StopAction(action)
        if action == StopAction.HALT:
            self.queue.request_scan_halt(request_id=request_id)
        elif action == StopAction.FINISH:
            self.queue.request_set_completed(request_id=request_id)
            return
        else:
            self.queue.request_scan_abortion(request_id=request_id)
        self._activate_emergency_stop()

    @SafeSlot()
    def stop_scan(self):
        """
        Abort the scan by default, then temporarily offer an emergency stop.

        The scan is the one in request_id; with None, the current scan is targeted. As a device
        stop the button leaves the scan alone; its host stops the devices.
        """
        if self._device_stop:
            return
        self._act(StopAction.HALT if self._emergency_stop_active else StopAction.ABORT)

    def _activate_emergency_stop(self) -> None:
        self._emergency_stop_active = True
        compact = self.compact_emergency
        self._set_button_label(
            self.EMERGENCY_STOP_SHORT_LABEL if compact else self.EMERGENCY_STOP_LABEL
        )
        self.button.setToolTip(self.EMERGENCY_STOP_LABEL)
        self.refresh_style()
        self._reset_timer.start(self.EMERGENCY_STOP_TIMEOUT_MS)

    def _deactivate_emergency_stop(self) -> None:
        self._emergency_stop_active = False
        self._set_button_label(self.ABORT_LABEL)
        self.refresh_style()

    def _set_button_label(self, label: str) -> None:
        self.button.setText(label)
        self.button.setToolTip(label)

    def cleanup(self):
        """Stop and dispose the emergency-stop reset timer before widget teardown."""
        self._reset_timer.stop()
        self._reset_timer.timeout.disconnect(self._deactivate_emergency_stop)
        self._reset_timer.deleteLater()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication, QVBoxLayout

    from bec_widgets.widgets.control.buttons.stop_button.stop_button import StopButton

    class MyGui(QWidget):
        def __init__(self):
            super().__init__()
            self.setLayout(QVBoxLayout())
            # Create and add the StopButton to the layout
            self.stop_button = StopButton()
            self.layout().addWidget(self.stop_button)

    # Example of how this custom GUI might be used:
    app = QApplication([])
    my_gui = MyGui()
    my_gui.show()
    sys.exit(app.exec_())
