from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QColorDialog

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.utility.visual.color_button_native.color_button_native import (
    ColorButtonNative,
)


def test_color_button_native(qtbot):
    cb = create_widget(qtbot, ColorButtonNative)

    # Check if the instance is created successfully
    assert cb is not None

    # Check if the button has a default color
    assert cb.color is not None

    # Check if the button can change color
    new_color = QColor(255, 0, 0)  # Red
    cb.set_color(new_color)
    assert cb.color == new_color.name()


def test_color_dialog_applies_chosen_color(qtbot, monkeypatch):
    """Clicking the button should open the dialog and apply the selected color."""
    cb = create_widget(qtbot, ColorButtonNative)
    chosen_color = QColor(0, 255, 0)  # Green

    # Force QColorDialog.getColor to return our chosen color
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args, **kwargs: chosen_color)

    # Expect the color_changed signal during the click
    with qtbot.waitSignal(cb.color_changed, timeout=1000):
        qtbot.mouseClick(cb, Qt.LeftButton)

    assert cb.color == chosen_color.name()


def test_color_dialog_cancel_keeps_color(qtbot, monkeypatch):
    """If the dialog returns an invalid color, the button color should stay the same."""
    cb = create_widget(qtbot, ColorButtonNative)
    original_color = cb.color

    # Simulate cancel: return an invalid QColor
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args, **kwargs: QColor())

    qtbot.mouseClick(cb, Qt.LeftButton)

    # No signal emitted, color unchanged
    assert cb.color == original_color


# Additional tests for color property getter/setter
def test_color_property_getter_setter_hex(qtbot):
    """Verify the color property works correctly with hex strings."""
    cb = create_widget(qtbot, ColorButtonNative)

    # Confirm default value is a valid hex string
    default_color = cb.color
    assert (
        isinstance(default_color, str) and default_color.startswith("#") and len(default_color) == 7
    )

    # Use property setter with a new hex color
    new_color_hex = "#123456"
    with qtbot.waitSignal(cb.color_changed, timeout=1000):
        cb.color = new_color_hex

    # Getter should reflect the new value
    assert cb.color == new_color_hex
    # Button text should update as well
    assert cb.text() == new_color_hex


def test_color_property_setter_qcolor(qtbot):
    """Verify the color property accepts QColor and emits the signal."""
    cb = create_widget(qtbot, ColorButtonNative)
    q_color = QColor(200, 100, 50)

    with qtbot.waitSignal(cb.color_changed, timeout=1000):
        cb.color = q_color

    assert cb.color == q_color.name()
    assert cb.text() == q_color.name()
