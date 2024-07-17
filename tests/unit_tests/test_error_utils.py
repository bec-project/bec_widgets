from unittest.mock import patch

import pytest
import pytestqt
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


@pytest.mark.parametrize("global_pop", [False, True])
@patch.object(QMessageBox, "exec_", return_value=QMessageBox.Ok)
def test_slot_with_popup_on_error(mock_exec, widget, qtbot, global_pop):
    error_utility = ErrorPopupUtility()
    error_utility.enable_global_error_popups(global_pop)

    with qtbot.waitSignal(error_utility.error_occurred, timeout=200) as blocker:
        widget.method_with_error_handling()

    assert blocker.signal_triggered
    assert mock_exec.called


@pytest.mark.parametrize("global_pop", [False, True])
@patch.object(QMessageBox, "exec_", return_value=QMessageBox.Ok)
def test_slot_no_popup_by_default_on_error(mock_exec, widget, qtbot, capsys, global_pop):
    error_utility = ErrorPopupUtility()
    error_utility.enable_global_error_popups(global_pop)

    try:
        with qtbot.waitSignal(error_utility.error_occurred, timeout=200) as blocker:
            widget.method_without_error_handling()
    except pytestqt.exceptions.TimeoutError:
        assert not global_pop

    if global_pop:
        assert blocker.signal_triggered
        assert mock_exec.called
    else:
        assert not blocker.signal_triggered
        assert not mock_exec.called
        stdout, stderr = capsys.readouterr()
        assert "ValueError" in stderr
