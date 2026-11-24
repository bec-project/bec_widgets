"""
Buttons that Space and Enter never press.

Qt's Fusion style (the default on Linux) gives a clicked button the keyboard focus, so a later
Space or Enter presses it again, e.g. queues a scan again or stops one. ``ButtonFocusStyle``
changes that for every button of the application:

- a click still moves the focus to the button, so a field being edited loses it as before: it
  emits ``editingFinished``, and a later Enter no longer reaches it (e.g. no motor move after
  Stop);
- Space, Select, Return and Enter on a button do nothing, also when it got the focus
  programmatically;
- Tab skips buttons, also a radio button after a click (Qt lets Tab enter a radio group at its
  focused button). Buttons that take no focus at all (e.g. the clear button of a line edit or a
  spin box's settings button) keep it that way. Fields, spin boxes and combo boxes keep their
  focus and keys; arrow keys still move the check within a focused radio group.
"""

from __future__ import annotations

from qtpy.QtCore import QEvent, Qt
from qtpy.QtWidgets import QAbstractButton, QApplication, QProxyStyle, QStyle

ACTIVATION_KEYS = frozenset(
    (Qt.Key.Key_Space, Qt.Key.Key_Select, Qt.Key.Key_Return, Qt.Key.Key_Enter)
)
KEY_EVENTS = (QEvent.Type.KeyPress, QEvent.Type.KeyRelease)
NO_TAB_FOCUS = ~Qt.FocusPolicy.TabFocus.value


class ButtonFocusStyle(QProxyStyle):
    """The platform style, but buttons take the focus on a click only and ignore Space/Enter."""

    # pylint: disable=invalid-name
    def styleHint(self, hint, option=None, widget=None, return_data=None):
        """Click focus as the default policy of buttons; every other hint unchanged."""
        if hint == QStyle.StyleHint.SH_Button_FocusPolicy:
            return Qt.FocusPolicy.ClickFocus.value
        return super().styleHint(hint, option, widget, return_data)

    def polish(self, widget):  # pylint: disable=arguments-renamed
        """
        Give every button click focus (also those that set a policy themselves, e.g. QToolButton
        sets TabFocus) and filter its activation keys. A button that takes no focus keeps that.
        """
        if isinstance(widget, QAbstractButton):
            if widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
                widget.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
            widget.installEventFilter(self)
        return super().polish(widget)

    def unpolish(self, widget):  # pylint: disable=arguments-renamed
        """Stop filtering a button that leaves this style."""
        if isinstance(widget, QAbstractButton):
            widget.removeEventFilter(self)
        return super().unpolish(widget)

    def eventFilter(self, obj, event):
        """Swallow Space, Select, Return and Enter on buttons; keep Tab off them."""
        if not isinstance(obj, QAbstractButton):
            return False
        if event.type() == QEvent.Type.FocusOut:
            # a focused auto-exclusive button (radio) adds TabFocus to itself on focus in
            obj.setFocusPolicy(Qt.FocusPolicy(obj.focusPolicy().value & NO_TAB_FOCUS))
            return False
        return event.type() in KEY_EVENTS and event.key() in ACTIVATION_KEYS


def disable_button_keyboard_focus(app: QApplication) -> None:
    """
    Wrap the application's style in ButtonFocusStyle. Call it right after creating the
    QApplication: buttons read the focus hint when they are created.

    Args:
        app(QApplication): the application whose buttons Space and Enter should not press.
    """
    if isinstance(getattr(app, "button_focus_style", None), ButtonFocusStyle):
        return
    name = app.style().name()  # e.g. "fusion" or "macos"; empty for an unnamed custom style
    style = ButtonFocusStyle(name) if name else ButtonFocusStyle()
    app.setStyle(style)
    app.button_focus_style = style  # type: ignore[attr-defined]
