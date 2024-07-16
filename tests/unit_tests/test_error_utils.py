from unittest.mock import patch

import pytest
from qtpy.QtWidgets import QMessageBox

from bec_widgets.qt_utils.error_popups import ErrorPopupUtility, ExampleWidget


@pytest.fixture
def widget(qtbot):
    test_widget = ExampleWidget()
    qtbot.addWidget(test_widget)
    qtbot.waitExposed(test_widget)
    yield test_widget
    test_widget.close()


@patch.object(QMessageBox, "exec_", return_value=QMessageBox.Ok)
def test_show_error_message_global(mock_exec, widget, qtbot):
    error_utility = ErrorPopupUtility()
    error_utility.enable_global_error_popups(True)

    with qtbot.waitSignal(error_utility.error_occurred, timeout=1000) as blocker:
        error_utility.error_occurred.emit("Test Error", "This is a test error message.", widget)

    assert mock_exec.called
    assert blocker.signal_triggered


@patch.object(QMessageBox, "exec_", return_value=QMessageBox.Ok)
def test_decorated_function(mock_exec, widget, qtbot):
    error_utility = ErrorPopupUtility()
    error_utility.enable_global_error_popups(False)

    with pytest.raises(ValueError) as excinfo:
        with qtbot.waitSignal(error_utility.error_occurred, timeout=1000) as blocker:
            widget.method_with_error_handling()

    assert blocker.signal_triggered
    assert mock_exec.called


@patch.object(QMessageBox, "exec_", return_value=QMessageBox.Ok)
def test_not_decorated_function(mock_exec, widget, qtbot):
    error_utility = ErrorPopupUtility()
    error_utility.enable_global_error_popups(False)

    with pytest.raises(ValueError) as excinfo:
        with qtbot.waitSignal(error_utility.error_occurred, timeout=1000) as blocker:
            widget.method_without_error_handling()

    assert not blocker.signal_triggered
    assert not mock_exec.called
