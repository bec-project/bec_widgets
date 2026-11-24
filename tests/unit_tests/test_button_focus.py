import subprocess
import sys
import textwrap
from unittest import mock

from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QFocusEvent, QKeyEvent
from qtpy.QtWidgets import QLineEdit, QPushButton, QStyle, QStyleFactory, QToolButton

from bec_widgets.utils.button_focus import ButtonFocusStyle, disable_button_keyboard_focus

# the style is application-wide and only read when a button is created: check it in an app of
# its own, so the test application of the other tests keeps its style
APP_CHECK = textwrap.dedent("""
    from qtpy.QtCore import Qt
    from qtpy.QtTest import QTest
    from qtpy.QtWidgets import (
        QApplication, QCheckBox, QComboBox, QLineEdit, QPushButton, QRadioButton, QSpinBox,
        QToolButton, QVBoxLayout, QWidget,
    )

    from bec_widgets.utils.button_focus import ButtonFocusStyle, disable_button_keyboard_focus
    from bec_widgets.widgets.utility.spinbox import decimal_spinbox

    app = QApplication([])


    def wait_for(condition):
        for _ in range(200):
            if condition():
                return
            QTest.qWait(10)
        raise AssertionError(condition)


    platform_style = app.style().name()
    new_fields = lambda: (QLineEdit(), QSpinBox(), QComboBox())
    platform_fields = [f.focusPolicy() for f in new_fields()]  # a macOS combo box is TabFocus
    disable_button_keyboard_focus(app)
    style = app.button_focus_style
    disable_button_keyboard_focus(app)  # a second call keeps the one wrapper
    assert app.button_focus_style is style and isinstance(style, ButtonFocusStyle)
    assert style.baseStyle().name() == platform_style

    explicit = QPushButton()
    explicit.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    for button in (QPushButton(), QToolButton(), QCheckBox(), QRadioButton(), explicit):
        button.ensurePolished()  # QToolButton sets TabFocus itself; polishing replaces it
        assert button.focusPolicy() == Qt.FocusPolicy.ClickFocus, button
    unfocusable = QToolButton()
    unfocusable.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    unfocusable.ensurePolished()
    assert unfocusable.focusPolicy() == Qt.FocusPolicy.NoFocus  # an opt-out stays
    fields = new_fields()
    for field in fields:
        field.ensurePolished()
    assert [f.focusPolicy() for f in fields] == platform_fields  # fields keep their own focus

    # a setpoint field next to Stop, a scan field next to Restore
    form = QWidget()
    layout = QVBoxLayout(form)
    setpoint, stop, other = QLineEdit(form), QPushButton("Stop", form), QLineEdit(form)
    tool, radio = QToolButton(form), QRadioButton("Fast", form)
    search, spin = QLineEdit(form), decimal_spinbox.BECSpinBox(form)
    search.setClearButtonEnabled(True)
    for widget in (setpoint, stop, tool, radio, other, search, spin):
        layout.addWidget(widget)
    events = []
    stop.clicked.connect(lambda: events.append("stop"))
    tool.clicked.connect(lambda: events.append("tool"))
    setpoint.returnPressed.connect(lambda: events.append("move"))
    setpoint.editingFinished.connect(lambda: events.append("edited"))
    form.show()
    form.activateWindow()
    wait_for(form.isActiveWindow)
    window = form.windowHandle()

    setpoint.setFocus()
    wait_for(setpoint.hasFocus)
    QTest.keyClicks(setpoint, "5")
    QTest.mouseClick(stop, Qt.MouseButton.LeftButton)
    assert events == ["edited", "stop"]  # the field is left (and confirmed) before the click
    assert stop.hasFocus()
    for key in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
        QTest.keyClick(window, key)
    assert events == ["edited", "stop"]  # no second stop, and no move from the setpoint

    QTest.mouseClick(tool, Qt.MouseButton.LeftButton)
    QTest.keyClick(window, Qt.Key.Key_Space)
    assert events[-1] == "tool" and events.count("tool") == 1

    stop.setFocus()  # e.g. a dialog that focuses a button itself
    QTest.keyClick(window, Qt.Key.Key_Space)
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert events.count("stop") == 1

    QTest.mouseClick(radio, Qt.MouseButton.LeftButton)  # Qt gives a focused radio TabFocus
    setpoint.setFocus()
    QTest.keyClick(window, Qt.Key.Key_Tab)
    assert other.hasFocus()  # Tab goes from field to field and skips the buttons
    QTest.keyClick(window, Qt.Key.Key_Tab)
    assert search.hasFocus()  # also the tool button and the clicked radio button

    # buttons inside an editor take no focus: the editor keeps it and its keys
    search.setFocus()
    QTest.keyClicks(search, "samx")
    clear = next(b for b in search.findChildren(QToolButton) if b.isVisible())
    clear.setFocus()  # focused by code once: it must still not take the focus on a click
    search.setFocus()
    QTest.mouseClick(clear, Qt.MouseButton.LeftButton)
    assert search.text() == "" and search.hasFocus()
    QTest.keyClick(window, Qt.Key.Key_Space)
    assert search.text() == " "
    decimal_spinbox.QInputDialog.getInt = lambda *args: (2, False)  # cancel the decimals dialog
    spin.setValue(20)
    spin.setFocus()
    QTest.mouseClick(spin.setting_button, Qt.MouseButton.LeftButton)
    assert spin.hasFocus()
    QTest.keyClick(window, Qt.Key.Key_Up)
    assert spin.value() == 21
    print("ok")
    """)


def test_buttons_ignore_space_and_enter_and_fields_keep_their_focus():
    result = subprocess.run(
        [sys.executable, "-c", APP_CHECK], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr[-3000:]
    assert result.stdout.strip().endswith("ok")


def test_button_focus_style_answers_click_focus_for_buttons_only():
    style = ButtonFocusStyle("fusion")
    hint = QStyle.StyleHint.SH_Button_FocusPolicy
    assert style.styleHint(hint) == Qt.FocusPolicy.ClickFocus.value
    other = QStyle.StyleHint.SH_ToolTip_WakeUpDelay
    assert style.styleHint(other) == style.baseStyle().styleHint(other)  # the platform's


def test_polish_filters_activation_keys_on_buttons_only(qtbot):
    style = ButtonFocusStyle("fusion")
    button, field = QToolButton(), QLineEdit()
    qtbot.addWidget(button)
    qtbot.addWidget(field)
    for widget in (button, field):
        style.polish(widget)
    assert button.focusPolicy() == Qt.FocusPolicy.ClickFocus  # QToolButton itself says TabFocus
    assert field.focusPolicy() == Qt.FocusPolicy.StrongFocus

    def key(kind, code):
        return QKeyEvent(kind, code, Qt.KeyboardModifier.NoModifier)

    for code in (Qt.Key.Key_Space, Qt.Key.Key_Select, Qt.Key.Key_Return, Qt.Key.Key_Enter):
        for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            assert style.eventFilter(button, key(kind, code))
            assert not style.eventFilter(field, key(kind, code))
    assert not style.eventFilter(button, key(QEvent.Type.KeyPress, Qt.Key.Key_A))
    assert not style.eventFilter(button, QEvent(QEvent.Type.Enter))

    # Qt adds Tab to a focused radio button; leaving it takes only that away again
    button.setFocusPolicy(
        Qt.FocusPolicy(Qt.FocusPolicy.ClickFocus.value | Qt.FocusPolicy.TabFocus.value)
    )
    assert not style.eventFilter(button, QFocusEvent(QEvent.Type.FocusOut))
    assert button.focusPolicy() == Qt.FocusPolicy.ClickFocus

    unfocusable = QToolButton()
    qtbot.addWidget(unfocusable)
    unfocusable.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    style.polish(unfocusable)
    assert unfocusable.focusPolicy() == Qt.FocusPolicy.NoFocus
    style.eventFilter(unfocusable, QFocusEvent(QEvent.Type.FocusOut))  # e.g. after setFocus()
    assert unfocusable.focusPolicy() == Qt.FocusPolicy.NoFocus

    clicks = []
    pushed = QPushButton()
    qtbot.addWidget(pushed)
    pushed.clicked.connect(lambda: clicks.append(True))
    style.polish(pushed)
    qtbot.keyClick(pushed, Qt.Key.Key_Space)
    assert not clicks  # the filter is installed on the button
    style.unpolish(pushed)
    qtbot.keyClick(pushed, Qt.Key.Key_Space)
    assert clicks == [True]  # and removed again


def test_disable_wraps_the_platform_style_once():
    for name in ("fusion", ""):  # an unnamed custom style falls back to the platform default
        app = mock.MagicMock(spec=["style", "setStyle"])
        app.style.return_value = QStyleFactory.create("fusion")
        app.style.return_value.name = lambda name=name: name
        disable_button_keyboard_focus(app)
        disable_button_keyboard_focus(app)
        app.setStyle.assert_called_once()
        assert app.button_focus_style is app.setStyle.call_args.args[0]
        assert isinstance(app.button_focus_style, ButtonFocusStyle)
