import os
import tempfile

import pytest
from qtpy.QtCore import Property
from qtpy.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from bec_widgets.utils.widget_state_manager import WidgetStateManager


class MyLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Internal attribute to hold the color string
        self._customColor = ""

    @Property(str)
    def customColor(self):
        return self._customColor

    @customColor.setter
    def customColor(self, color):
        self._customColor = color


@pytest.fixture
def test_widget(qtbot):
    w = QWidget()
    w.setObjectName("MainWidget")
    layout = QVBoxLayout(w)

    child1 = MyLineEdit(w)
    child1.setObjectName("ChildLineEdit1")
    child1.setText("Hello")
    child1.customColor = "red"

    child2 = MyLineEdit(w)
    child2.setObjectName("ChildLineEdit2")
    child2.setText("World")
    child2.customColor = "blue"

    layout.addWidget(child1)
    layout.addWidget(child2)

    qtbot.addWidget(w)
    qtbot.waitExposed(w)
    return w


def test_save_load_widget_state(test_widget):
    """
    Test saving and loading the state
    """

    manager = WidgetStateManager(test_widget)

    # Before saving, confirm initial properties
    child1 = test_widget.findChild(MyLineEdit, "ChildLineEdit1")
    child2 = test_widget.findChild(MyLineEdit, "ChildLineEdit2")
    assert child1.text() == "Hello"
    assert child1.customColor == "red"
    assert child2.text() == "World"
    assert child2.customColor == "blue"

    # Create a temporary file to save settings
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ini") as tmp_file:
        tmp_filename = tmp_file.name

    # Save the current state
    manager.save_state(tmp_filename)

    # Modify the widget properties
    child1.setText("Changed1")
    child1.customColor = "green"
    child2.setText("Changed2")
    child2.customColor = "yellow"

    assert child1.text() == "Changed1"
    assert child1.customColor == "green"
    assert child2.text() == "Changed2"
    assert child2.customColor == "yellow"

    # Load the previous state
    manager.load_state(tmp_filename)

    # Confirm that the state has been restored
    assert child1.text() == "Hello"
    assert child1.customColor == "red"
    assert child2.text() == "World"
    assert child2.customColor == "blue"

    # Clean up temporary file
    os.remove(tmp_filename)


def test_save_load_without_filename(test_widget, monkeypatch, qtbot):
    """
    Test that the dialog would open if filename is not provided.
    """

    manager = WidgetStateManager(test_widget)

    # Mock QFileDialog.getSaveFileName to return a temporary filename
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ini") as tmp_file:
        tmp_filename = tmp_file.name

    def mock_getSaveFileName(*args, **kwargs):
        return tmp_filename, "INI Files (*.ini)"

    def mock_getOpenFileName(*args, **kwargs):
        return tmp_filename, "INI Files (*.ini)"

    from qtpy.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getSaveFileName", mock_getSaveFileName)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", mock_getOpenFileName)

    # Initial values
    child1 = test_widget.findChild(MyLineEdit, "ChildLineEdit1")
    assert child1.text() == "Hello"

    # Save state without providing filename -> uses dialog mock
    manager.save_state()

    # Change property
    child1.setText("Modified")

    # Load state using dialog mock
    manager.load_state()

    # State should be restored
    assert child1.text() == "Hello"

    # Clean up
    os.remove(tmp_filename)
