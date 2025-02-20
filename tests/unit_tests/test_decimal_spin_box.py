# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import
import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QInputDialog

from bec_widgets.widgets.utility.spinbox.decimal_spinbox import BECSpinBox


@pytest.fixture
def spinbox_fixture(qtbot):
    widget = BECSpinBox()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_spinbox_initial_values(spinbox_fixture):
    """
    Test the default properties of the BECSpinBox.
    """
    spinbox = spinbox_fixture
    assert spinbox.decimals() == 2
    assert spinbox.minimum() == -2147483647
    assert spinbox.maximum() == 2147483647
    assert spinbox.setting_button is not None


def test_change_decimals_ui(spinbox_fixture, monkeypatch, qtbot):
    """
    Test that clicking on the setting button triggers the QInputDialog to change decimals.
    We'll simulate a user entering a new decimals value in the dialog.
    """
    spinbox = spinbox_fixture

    def mock_get_int(*args, **kwargs):
        return (5, True)

    monkeypatch.setattr(QInputDialog, "getInt", mock_get_int)
    assert spinbox.decimals() == 2

    qtbot.mouseClick(spinbox.setting_button, Qt.LeftButton)
    assert spinbox.decimals() == 5


def test_change_decimals_cancel(spinbox_fixture, monkeypatch, qtbot):
    """
    Test that if the user cancels the decimals dialog, the decimals do not change.
    """
    spinbox = spinbox_fixture

    def mock_get_int(*args, **kwargs):
        return (0, False)

    monkeypatch.setattr(QInputDialog, "getInt", mock_get_int)

    old_decimals = spinbox.decimals()
    qtbot.mouseClick(spinbox.setting_button, Qt.LeftButton)
    assert spinbox.decimals() == old_decimals


def test_spinbox_value_change(spinbox_fixture):
    """
    Test that the spinbox accepts user input and updates its value accordingly.
    """
    spinbox = spinbox_fixture
    assert spinbox.value() == 0.0
    spinbox.setValue(123.456)
    assert spinbox.value() == 123.46
