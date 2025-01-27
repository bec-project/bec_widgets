import os
import tempfile

import pytest
from qtpy.QtCore import Property
from qtpy.QtWidgets import QCheckBox, QGroupBox, QLineEdit, QVBoxLayout, QWidget

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


# A specialized widget that has a property declared with stored=False
class MyLineEditStoredFalse(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._noStoreProperty = ""

    @Property(str, stored=False)
    def noStoreProperty(self):
        return self._noStoreProperty

    @noStoreProperty.setter
    def noStoreProperty(self, value):
        self._noStoreProperty = value


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

    # A widget that we want to skip settings
    skip_widget = QCheckBox("Skip Widget", w)
    skip_widget.setObjectName("SkipCheckBox")
    skip_widget.setChecked(True)
    skip_widget.setProperty("skip_settings", True)

    layout.addWidget(child1)
    layout.addWidget(child2)
    layout.addWidget(skip_widget)

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


def test_skip_settings(test_widget):
    """
    Verify that a widget with skip_settings=True is not saved/loaded.
    """
    manager = WidgetStateManager(test_widget)

    skip_checkbox = test_widget.findChild(QCheckBox, "SkipCheckBox")
    # Double check initial state
    assert skip_checkbox.isChecked() is True

    with tempfile.NamedTemporaryFile(delete=False, suffix=".ini") as tmp_file:
        tmp_filename = tmp_file.name

    # Save state
    manager.save_state(tmp_filename)

    # Change skip checkbox state
    skip_checkbox.setChecked(False)
    assert skip_checkbox.isChecked() is False

    # Load state
    manager.load_state(tmp_filename)

    # The skip checkbox should not revert because it was never saved.
    assert skip_checkbox.isChecked() is False

    os.remove(tmp_filename)


def test_property_stored_false(qtbot):
    """
    Verify that a property with stored=False is not saved.
    """
    w = QWidget()
    w.setObjectName("TestStoredFalse")
    layout = QVBoxLayout(w)

    stored_false_widget = MyLineEditStoredFalse(w)
    stored_false_widget.setObjectName("NoStoreLineEdit")
    stored_false_widget.setText("VisibleText")  # normal text property is stored
    stored_false_widget.noStoreProperty = "ShouldNotBeStored"
    layout.addWidget(stored_false_widget)

    qtbot.addWidget(w)
    qtbot.waitExposed(w)

    manager = WidgetStateManager(w)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".ini") as tmp_file:
        tmp_filename = tmp_file.name

    # Save the current state
    manager.save_state(tmp_filename)

    # Modify the properties
    stored_false_widget.setText("ChangedText")
    stored_false_widget.noStoreProperty = "ChangedNoStore"

    # Load the previous state
    manager.load_state(tmp_filename)

    # The text should have reverted
    assert stored_false_widget.text() == "VisibleText"
    # The noStoreProperty should remain changed, as it was never saved.
    assert stored_false_widget.noStoreProperty == "ChangedNoStore"

    os.remove(tmp_filename)


def test_skip_parent_settings(qtbot):
    """
    Demonstrates that if a PARENT widget has skip_settings=True, all its
    children (even if they do NOT have skip_settings=True) also get skipped.
    """
    main_widget = QWidget()
    main_widget.setObjectName("TopWidget")
    layout = QVBoxLayout(main_widget)

    # Create a parent widget with skip_settings=True
    parent_group = QGroupBox("ParentGroup", main_widget)
    parent_group.setObjectName("ParentGroupBox")
    parent_group.setProperty("skip_settings", True)  # The crucial setting

    child_layout = QVBoxLayout(parent_group)

    child_line_edit_1 = MyLineEdit(parent_group)
    child_line_edit_1.setObjectName("ChildLineEditA")
    child_line_edit_1.setText("OriginalA")

    child_line_edit_2 = MyLineEdit(parent_group)
    child_line_edit_2.setObjectName("ChildLineEditB")
    child_line_edit_2.setText("OriginalB")

    child_layout.addWidget(child_line_edit_1)
    child_layout.addWidget(child_line_edit_2)
    parent_group.setLayout(child_layout)

    layout.addWidget(parent_group)
    main_widget.setLayout(layout)

    qtbot.addWidget(main_widget)
    qtbot.waitExposed(main_widget)

    manager = WidgetStateManager(main_widget)

    # Create a temp file to hold settings
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ini") as tmp_file:
        tmp_filename = tmp_file.name

    # Save the state
    manager.save_state(tmp_filename)

    # Change child widget values
    child_line_edit_1.setText("ChangedA")
    child_line_edit_2.setText("ChangedB")

    # Load state
    manager.load_state(tmp_filename)

    # Because the PARENT has skip_settings=True, none of its children get saved or loaded
    # Hence, the changes remain and do NOT revert
    assert child_line_edit_1.text() == "ChangedA"
    assert child_line_edit_2.text() == "ChangedB"

    os.remove(tmp_filename)
