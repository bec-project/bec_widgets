"""
A frameless card window that opens next to a widget, with any content widget, and the controller
that opens it on hover or on a click. Used by the status bar pills (click), the client info in the
status bar (hover) and as a rich tooltip.
"""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Callable

import shiboken6
from qtpy.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, QTimer
from qtpy.QtGui import QColor, QCursor, QGuiApplication, QWindow
from qtpy.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.theme_utils import css, theme_colors

# focus the user gave the anchor on purpose, as opposed to Qt focusing it on window activation
KEYBOARD_FOCUS_REASONS = (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason)


class CardAlign(StrEnum):
    """Where a hover card opens relative to its anchor."""

    LEFT = "left"  # left edges aligned
    CENTER = "center"  # centred on the anchor, e.g. a wide label


class CardTrigger(StrEnum):
    """What opens and closes a card of a HoverCardController."""

    HOVER = "hover"  # opens on hover, closes when the cursor has left
    CLICK = "click"  # a click on the anchor opens and closes it; a click elsewhere closes it


class HoverCard(QWidget):
    """
    The frameless card that opens next to a widget, with any content widget. It never takes
    keyboard focus from the main window. A HoverCardController opens and closes it on hover; as a
    rich tooltip its owner shows it with show_near and hides it. A non-activating Tool window
    rather than a ToolTip one, so its buttons take clicks on every platform.

    Args:
        owner(QWidget): The widget the card belongs to (its parent).
        content(QWidget | None): The widget shown in the card; can be set later with set_content.
        width(int | None): Fixed width of the card frame; None follows the content.
        object_name(str): Object name of the card frame, for its style sheet.
        hide_on_leave(bool): Hide the card when the cursor leaves it, like a tooltip.
    """

    def __init__(
        self,
        owner: QWidget,
        content: QWidget | None = None,
        width: int | None = None,
        object_name: str = "status_hover_card",
        hide_on_leave: bool = False,
    ):
        super().__init__(
            owner,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            # the card draws its own rounded shadow; the native one (macOS) is computed for the
            # whole translucent window and shows as a square-cornered band around the card
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        outer = self.outer_layout = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)  # room for the shadow
        self.card = QFrame(self)
        self.card.setObjectName(object_name)
        if width is not None:
            self.card.setFixedWidth(width)
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 70))
        self.card.setGraphicsEffect(shadow)
        self.inner_layout = QVBoxLayout(self.card)
        self.inner_layout.setContentsMargins(14, 14, 14, 14)
        outer.addWidget(self.card)
        self.content: QWidget | None = None
        self.hint: QLabel | None = None
        self.hide_on_leave = hide_on_leave
        if content is not None:
            self.set_content(content)
        self.refresh_style()

    def set_content(self, content: QWidget) -> None:
        """Show a widget in the card, in place of the previous content."""
        if self.content is not None:
            self.inner_layout.removeWidget(self.content)
        self.content = content
        content.setParent(self.card)
        self.inner_layout.insertWidget(0, content)

    def add_hint(self, text: str) -> QLabel:
        """Add a small muted line below the content, e.g. how to dock the widget."""
        if self.hint is None:
            self.hint = QLabel(self.card)
            self.hint.setObjectName("status_card_hint")
            self.inner_layout.addWidget(self.hint)
            self.refresh_style()
        self.hint.setText(text)
        return self.hint

    def show_near(self, global_pos: QPoint, offset: QPoint | None = None) -> None:
        """
        Show the card next to a global position, below and to the right of it by default. It
        flips to the other side of the position where it would leave the screen, and stays on
        the screen.

        Args:
            global_pos(QPoint): The position, e.g. the cursor or the centre of a button.
            offset(QPoint, optional): Distance of the card frame from the position. Defaults to
                QPoint(12, 16).
        """
        self.refresh_style()
        self.adjustSize()
        offset = offset or QPoint(12, 16)
        screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        # the frame sits inside the window's shadow margins
        margins = self.outer_layout.contentsMargins()
        width, height = self.width(), self.height()
        x = global_pos.x() + offset.x() - margins.left()
        y = global_pos.y() + offset.y() - margins.top()
        if x + width > area.right():
            x = global_pos.x() - abs(offset.x()) - width + margins.right()
        if y + height > area.bottom():
            y = global_pos.y() - abs(offset.y()) - height + margins.bottom()
        x = max(area.left(), min(x, area.right() - width + 1))
        y = max(area.top(), min(y, area.bottom() - height + 1))
        self.move(x, y)
        self.show()
        self.raise_()

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        super().leaveEvent(event)
        if self.hide_on_leave:
            self.hide()

    def refresh_style(self) -> None:
        """Re-read the theme colours."""
        colors = theme_colors()
        self.card.setStyleSheet(
            f"#{self.card.objectName()} {{ background: {css(colors['card'])};"
            f" border: 1px solid {css(colors['border'])}; border-radius: 8px; }}"
            f"#status_card_hint {{ color: {css(colors['muted'])}; font-size: 11px; }}"
        )


class HoverCardController(QObject):
    """
    Opens a HoverCard above an anchor widget, on hover or on a click (trigger). It is kept on the
    screen of the anchor and follows it when either moves or changes size. It closes on Esc and
    when the application is deactivated.

    Hover: the card stays open while the cursor is over the anchor, the card, the gap between them
    or one of the extra widgets, while the anchor has keyboard focus, or while a popup or dialog of
    the card is open, and closes GRACE_MS after the cursor has left. Only a cursor poll decides
    inside or outside: Enter and Leave events are not reliable while the card window is shown
    (e.g. on macOS).

    Click: a left click on the anchor, or Space / Enter while it has keyboard focus, opens and
    closes the card. A click anywhere else in the anchor's window closes it, except on one of the
    extra widgets or while a popup or dialog of the card is open; so does resizing that window
    or switching to another one. When the window is moved, the card moves with the pill. The
    cursor leaving does not close it.

    Args:
        anchor(QWidget): The widget the card opens above; its Enter or a click on it opens the
            card.
        card(HoverCard): The card window.
        keep_open(Callable[[], bool] | None): Asked on each poll; True keeps the card open.
        can_open(Callable[[], bool] | None): Asked before opening; False keeps the card closed.
        on_close(Callable[[], None] | None): Called when the card closes.
        align(CardAlign): LEFT aligns the card to the anchor's left edge, CENTER centres it on
            the anchor (for a wide anchor such as the client info label).
        trigger(CardTrigger): HOVER opens the card on hover, CLICK on a click on the anchor.
    """

    GRACE_MS = 250  # how long the cursor may be outside before the card closes
    POLL_MS = 90  # cursor check while hovered or open
    HOVER_TOLERANCE = 4  # px around anchor, extras and card that still count as inside
    GAP = 8  # px between the anchor and the card

    def __init__(
        self,
        anchor: QWidget,
        card: HoverCard,
        keep_open: Callable[[], bool] | None = None,
        can_open: Callable[[], bool] | None = None,
        on_close: Callable[[], None] | None = None,
        align: CardAlign | str = CardAlign.LEFT,
        trigger: CardTrigger | str = CardTrigger.HOVER,
    ):
        super().__init__(anchor)
        self.anchor = anchor
        self.card = card
        self.align = CardAlign(align)
        self.trigger = CardTrigger(trigger)
        self._click_window: QWindow | None = None  # watched for clicks outside while open
        self._click_window_size = QSize()
        self._focus_widget: QWidget | None = None  # watched for Esc while the card is open
        self._keep_open = keep_open
        self._can_open = can_open
        self._on_close = on_close
        self._extras: list[QWidget] = []
        self._outside_since: float | None = None
        self.poll = QTimer(self)
        self.poll.setInterval(self.POLL_MS)
        self.poll.timeout.connect(self.check_cursor)
        for widget in (anchor, card):
            widget.installEventFilter(self)
        app = QGuiApplication.instance()
        self._app_connected = app is not None
        if app is not None:
            app.applicationStateChanged.connect(self._on_application_state)

    @property
    def outside_since(self) -> float | None:
        """time.monotonic() when the cursor left, or None while it is inside."""
        return self._outside_since

    def add_extra(self, widget: QWidget) -> None:
        """Count a widget next to the anchor as inside, e.g. a Stop button; it does not open it."""
        self._extras.append(widget)
        widget.installEventFilter(self)

    def start_watching(self) -> None:
        """Start the cursor poll; repeated (sometimes synthetic) Enter events do not restart it."""
        if not self.poll.isActive():
            self._outside_since = None
            self.poll.start()

    @property
    def click_trigger(self) -> bool:
        """Whether a click opens and closes the card (instead of hover)."""
        return self.trigger == CardTrigger.CLICK

    def open(self) -> None:
        """Show the card above the anchor."""
        if self._can_open is not None and not self._can_open():
            return
        if self.click_trigger:
            self._watch_clicks()
        else:
            self.start_watching()
        if self.card.isVisible():
            return
        self.card.refresh_style()  # the theme may have changed while it was closed
        self.card.adjustSize()
        self.place()
        self.card.show()
        self._set_anchor_state("set_expanded", True)

    def toggle(self) -> None:
        """Open the card, or close it when it is open."""
        if self.card.isVisible():
            self.close()
        else:
            self.open()

    def close(self) -> None:
        """Hide the card and stop watching the cursor."""
        if self._on_close is not None:
            self._on_close()
        self.leave()

    def leave(self) -> None:
        """Hide the card without the on_close hook (the cursor left)."""
        self.poll.stop()
        self._outside_since = None
        self._unwatch_clicks()
        self.card.hide()
        self._set_anchor_state("set_expanded", False)
        # a click closes the card with the cursor still on the anchor: keep its hover outline
        # (real bounds: from just outside no Leave would come to clear it)
        hovered = self.click_trigger and self._over(self.anchor, tolerance=0)
        self._set_anchor_state("set_hovered", hovered)

    def _set_anchor_state(self, setter: str, value: bool) -> None:
        method = getattr(self.anchor, setter, None)
        if callable(method) and shiboken6.isValid(self.anchor):
            method(value)

    def _watch_clicks(self) -> None:
        """Watch the anchor's window for a click outside the anchor and the extras, and moves."""
        window = self.anchor.window().windowHandle()
        if window is self._click_window:
            return
        self._unwatch_clicks()
        if window is not None:
            window.installEventFilter(self)
            self._click_window = window
            self._click_window_size = window.size()
            app = QApplication.instance()
            app.focusChanged.connect(self._follow_focus)
            self._follow_focus(None, app.focusWidget())

    def _window_resized(self) -> bool:
        """Whether the watched window changed size since the card opened; Qt also sends Resize
        events without a change, e.g. when the window is exposed."""
        window = self._click_window
        return window is not None and window.size() != self._click_window_size

    def _unwatch_clicks(self) -> None:
        window, self._click_window = self._click_window, None
        if window is not None:
            try:
                QApplication.instance().focusChanged.disconnect(self._follow_focus)
            except (TypeError, RuntimeError):
                pass
            if shiboken6.isValid(window):
                window.removeEventFilter(self)
        self._follow_focus(None, None)

    @SafeSlot(object, object)
    def _follow_focus(self, _old: QWidget | None, new: QWidget | None) -> None:
        """
        Watch the focused widget of the anchor's window: Qt offers Esc to its shortcuts (e.g. the
        one of the Log Panel) before the window sees the key press.
        """
        widget, self._focus_widget = self._focus_widget, None
        if widget is not None and shiboken6.isValid(widget):
            widget.removeEventFilter(self)
        if new is None or new in (self.anchor, self.card, *self._extras):
            return  # filtered anyway, and their filter must stay
        if self._click_window is not None and new.window().windowHandle() is self._click_window:
            new.installEventFilter(self)
            self._focus_widget = new

    def _over(self, widget: QWidget, tolerance: int | None = None) -> bool:
        """Whether the cursor is over a shown widget (with HOVER_TOLERANCE by default)."""
        rect = self._global_rect(widget, tolerance)
        return widget.isVisible() and rect.contains(QCursor.pos())

    def _click_outside(self, event) -> bool:
        """Whether a mouse press in the anchor's window is outside the anchor and the extras."""
        pos = event.globalPosition().toPoint()
        inside = [self.anchor, *self._extras]
        if any(w.isVisible() and self._global_rect(w, tolerance=0).contains(pos) for w in inside):
            return False
        return not self.own_window_open()

    def place(self) -> None:
        """
        Put the card above the anchor, left-aligned to it (or centred), with its bottom at the
        anchor, and keep it inside the available geometry of the anchor's screen.
        """
        margin = self.card.outer_layout.contentsMargins()
        top_left = self.anchor.mapToGlobal(QPoint(0, 0))
        if self.align == CardAlign.CENTER:
            x = top_left.x() + (self.anchor.width() - self.card.width()) // 2
        else:
            x = top_left.x() - margin.left()
        y = top_left.y() - self.card.height() + margin.bottom() - self.GAP
        screen = self.anchor.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            x = max(area.left(), min(x, area.right() - self.card.width() + 1))
            y = max(area.top(), min(y, area.bottom() - self.card.height() + 1))
        self.card.move(x, y)

    def _global_rect(self, widget: QWidget, tolerance: int | None = None) -> QRect:
        """The widget's rect on screen, grown by tolerance (default HOVER_TOLERANCE)."""
        rect = QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())
        tol = self.HOVER_TOLERANCE if tolerance is None else tolerance
        return rect.adjusted(-tol, -tol, tol, tol)

    def hovered(self) -> bool:
        """Whether the cursor is over the anchor, an extra, the card, or the gap to the card."""
        pos = QCursor.pos()
        widgets = [self.anchor, *self._extras]
        rects = [self._global_rect(w) for w in widgets if w.isVisible()]
        if self.card.isVisible():
            card = self._global_rect(self.card.card)
            anchor = self._global_rect(self.anchor)
            rects.append(card)
            rects.append(
                QRect(anchor.left(), card.bottom(), anchor.width(), anchor.top() - card.bottom())
            )
        return any(rect.contains(pos) for rect in rects)

    def _owns(self, widget: QWidget | None) -> bool:
        owner = widget.parentWidget() if widget is not None else None
        if owner is None:
            return False
        roots = [self.card, self.anchor, *self._extras]
        host = self.anchor.parentWidget()
        if host is not None:
            roots.append(host)
        return any(owner is root or root.isAncestorOf(owner) for root in roots)

    def own_window_open(self) -> bool:
        """
        Whether a popup or a modal dialog of the card or the anchor is open, e.g. the arrow menu
        of a Stop in the card or a confirmation dialog of its content.
        """
        return self._owns(QApplication.activePopupWidget()) or self._owns(
            QApplication.activeModalWidget()
        )

    def _anchor_has_keyboard_focus(self) -> bool:
        return bool(getattr(self.anchor, "keyboard_focus", False))

    @SafeSlot()
    def check_cursor(self) -> None:
        """The poll: close the card GRACE_MS after the cursor has left."""
        if self.hovered() or self._anchor_has_keyboard_focus() or self.own_window_open():
            self._outside_since = None
            return
        if self._keep_open is not None and self._keep_open():
            return
        now = time.monotonic()
        if self._outside_since is None:
            self._outside_since = now
        elif now - self._outside_since >= self.GRACE_MS / 1000:
            self.leave()

    @SafeSlot(object)
    def _on_application_state(self, state) -> None:
        if state != Qt.ApplicationState.ApplicationActive:
            self.close()

    def _click_event(self, obj, event) -> bool | None:
        """
        Handle an event of the click trigger; True consumes it, False passes it on and None
        leaves it to the shared handling in eventFilter.
        """
        kind = event.type()
        if (
            kind == QEvent.Type.ShortcutOverride
            and event.key() == Qt.Key.Key_Escape
            and self.card.isVisible()
            and obj is QApplication.focusWidget()
        ):
            event.accept()  # no Esc shortcut while the card is open: the key press closes it
            return True
        if obj is self._click_window:
            if kind == QEvent.Type.MouseButtonPress and self._click_outside(event):
                self.close()
            elif kind == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self.close()  # the card never has focus: Esc anywhere in the window closes it
                return True
            elif kind == QEvent.Type.Resize and self._window_resized():
                self.close()  # the window was resized, maximized or restored: the card goes away
            elif kind == QEvent.Type.Move and self.card.isVisible():
                self.place()  # the window was dragged: the card goes with the pill
            return False
        if obj is self.anchor:
            if kind == QEvent.Type.Enter:
                if self.anchor.isVisible():
                    self._set_anchor_state("set_hovered", True)
                return False
            if kind == QEvent.Type.Leave:
                self._set_anchor_state("set_hovered", False)
                return False
            if kind == QEvent.Type.FocusIn:
                return False  # tabbing to the pill only outlines it
            if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.toggle()
                return False
            if kind == QEvent.Type.KeyPress and event.key() in (
                Qt.Key.Key_Space,
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
            ):
                if not event.isAutoRepeat():  # a held key toggles once
                    self.toggle()
                return True
        if kind == QEvent.Type.Enter:
            return False  # neither the card nor an extra opens it
        return None

    def eventFilter(self, obj, event):  # pylint: disable=invalid-name
        kind = event.type()
        if kind == QEvent.Type.WindowDeactivate and obj in (self.anchor, self.card):
            # e.g. another window of the app took the focus; Qt sends it to every widget of the
            # window, and the new active window is only known once the event is through
            QTimer.singleShot(0, self, self._check_activation)
        if self.click_trigger:
            handled = self._click_event(obj, event)
            if handled is not None:
                return handled or super().eventFilter(obj, event)
        # Qt can deliver a late Enter to a widget that was hidden or closed in the meantime
        if kind == QEvent.Type.Enter and obj is self.anchor and self.anchor.isVisible():
            self._set_anchor_state("set_hovered", True)
            self.open()
        elif kind == QEvent.Type.Enter and obj is self.card:
            self.open()
        elif kind == QEvent.Type.Enter and obj in self._extras:
            self.start_watching()
        elif kind == QEvent.Type.Leave and obj is self.anchor and not self.card.isVisible():
            self._set_anchor_state("set_hovered", False)
        elif (
            kind == QEvent.Type.FocusIn
            and obj is self.anchor
            and event.reason() in KEYBOARD_FOCUS_REASONS
        ):
            self.open()
        elif kind == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.close()
            return True
        elif kind in (QEvent.Type.Move, QEvent.Type.Resize) and self.card.isVisible():
            # the card grows with its content, and the anchor moves when a widget next to it
            # slides in: keep the card bottom-anchored above the anchor
            if obj is self.anchor or obj is self.card:
                self.place()
        return super().eventFilter(obj, event)

    @SafeSlot()
    def _check_activation(self) -> None:
        """Close once another window is active than the anchor's, the card or its own windows."""
        if not self.card.isVisible() or not shiboken6.isValid(self.anchor):
            return
        if self.anchor.isActiveWindow() or self.card.isActiveWindow() or self.own_window_open():
            return
        self.close()

    def cleanup(self) -> None:
        """Stop the poll, close the card and stop listening to the anchor, card and extras."""
        self.poll.stop()
        self._unwatch_clicks()
        for widget in (self.anchor, self.card, *self._extras):
            if shiboken6.isValid(widget):
                widget.removeEventFilter(self)
        app = QGuiApplication.instance()
        if app is not None and self._app_connected:
            self._app_connected = False
            try:
                app.applicationStateChanged.disconnect(self._on_application_state)
            except (TypeError, RuntimeError):
                pass
        self.card.hide()
