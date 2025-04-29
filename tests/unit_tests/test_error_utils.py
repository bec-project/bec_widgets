from unittest.mock import patch

import pytest
from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject, Signal
from qtpy.QtWidgets import QMessageBox

from bec_widgets.utils.error_popups import ErrorPopupUtility, ExampleWidget, SafeProperty, SafeSlot


class TestSafePropertyClass(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._my_value = 10  # internal store

    @SafeProperty(int, default=-1)
    def my_value(self) -> int:
        # artificially raise if it's 999 for testing
        if self._my_value == 999:
            raise ValueError("Invalid internal state in getter!")
        return self._my_value

    @my_value.setter
    def my_value(self, val: int):
        # artificially raise if user sets -999 for testing
        if val == -999:
            raise ValueError("Invalid user input in setter!")
        self._my_value = val


class TestSafeSlotEmitter(QObject):
    test_signal = Signal()


class TestSafeSlotClass(QObject):
    """
    Test class to demonstrate the use of SafeSlot decorator.
    """

    def __init__(self, parent=None, signal_obj: TestSafeSlotEmitter | None = None):
        super().__init__(parent)
        assert signal_obj is not None, "Signal object must be provided"
        signal_obj.test_signal.connect(self.method_without_sender_verification)
        signal_obj.test_signal.connect(self.method_with_sender_verification)
        self._method_without_verification_called = False
        self._method_with_verification_called = False

    @SafeSlot()
    def method_without_sender_verification(self):
        self._method_without_verification_called = True

    @SafeSlot(verify_sender=True)
    def method_with_sender_verification(self):
        self._method_with_verification_called = True


@pytest.fixture
def widget(qtbot):
    test_widget = ExampleWidget()
    qtbot.addWidget(test_widget)
    qtbot.waitExposed(test_widget)
    yield test_widget
    test_widget.close()


@patch.object(QMessageBox, "exec_", return_value=QMessageBox.Ok)
def test_show_error_message_global(mock_exec, widget, qtbot):
    """
    Test that an error popup is shown if global error popups are enabled
    and the error_occurred signal is emitted manually.
    """
    error_utility = ErrorPopupUtility()
    error_utility.enable_global_error_popups(True)

    with qtbot.waitSignal(error_utility.error_occurred, timeout=1000) as blocker:
        error_utility.error_occurred.emit("Test Error", "This is a test error message.", widget)

    assert blocker.signal_triggered
    assert mock_exec.called


@pytest.mark.parametrize("global_pop", [False, True])
@patch.object(QMessageBox, "exec_", return_value=QMessageBox.Ok)
def test_slot_with_popup_on_error(mock_exec, widget, qtbot, global_pop):
    """
    If the slot is decorated with @SafeSlot(popup_error=True),
    we always expect a popup on error (and a signal) even if global popups are off.
    """
    error_utility = ErrorPopupUtility()
    error_utility.enable_global_error_popups(global_pop)

    with qtbot.waitSignal(error_utility.error_occurred, timeout=500) as blocker:
        widget.method_with_error_handling()

    assert blocker.signal_triggered
    assert mock_exec.called  # Because popup_error=True forces popup


@pytest.mark.parametrize("global_pop", [False, True])
@patch.object(bec_logger.logger, "error")
@patch.object(QMessageBox, "exec_", return_value=QMessageBox.Ok)
def test_slot_no_popup_by_default_on_error(mock_exec, mock_log_error, widget, qtbot, global_pop):
    """
    If the slot is decorated with @SafeSlot() (no popup_error=True),
    we never show a popup, even if global popups are on,
    because the code does not check 'enable_error_popup' for normal slots.
    """
    error_utility = ErrorPopupUtility()
    error_utility.enable_global_error_popups(global_pop)

    # We do NOT expect a popup or signal in either case, since code only logs
    with qtbot.assertNotEmitted(error_utility.error_occurred):
        widget.method_without_error_handling()

    assert not mock_exec.called

    # Confirm logger.error(...) was called
    mock_log_error.assert_called_once()
    logged_msg = mock_log_error.call_args[0][0]
    assert "ValueError" in logged_msg
    assert "SafeSlot error in slot" in logged_msg


@pytest.mark.parametrize("global_pop", [False, True])
@patch.object(bec_logger.logger, "error")
@patch.object(QMessageBox, "exec_", return_value=QMessageBox.Ok)
def test_safe_property_getter_error(mock_exec, mock_log_error, qtbot, global_pop):
    """
    If a property getter raises an error, we log it by default.
    (No popup is shown unless code specifically calls it.)
    """
    error_utility = ErrorPopupUtility()
    error_utility.enable_global_error_popups(global_pop)

    test_obj = TestSafePropertyClass()
    test_obj._my_value = 999  # triggers ValueError in getter => logs => returns default (-1)

    val = test_obj.my_value
    assert val == -1

    # No popup => mock_exec not called
    assert not mock_exec.called

    # logger.error(...) is called once
    mock_log_error.assert_called_once()
    logged_msg = mock_log_error.call_args[0][0]
    assert "SafeProperty error in GETTER" in logged_msg
    assert "ValueError" in logged_msg


@pytest.mark.parametrize("global_pop", [False, True])
@patch.object(bec_logger.logger, "error")
@patch.object(QMessageBox, "exec_", return_value=QMessageBox.Ok)
def test_safe_property_setter_error(mock_exec, mock_log_error, qtbot, global_pop):
    """
    If a property setter raises an error, we log it by default.
    (No popup is shown unless code specifically calls it.)
    """
    error_utility = ErrorPopupUtility()
    error_utility.enable_global_error_popups(global_pop)

    test_obj = TestSafePropertyClass()
    # Setting to -999 triggers setter error => logs => property returns None
    test_obj.my_value = -999

    # No popup => mock_exec not called
    assert not mock_exec.called

    # logger.error(...) is called once
    mock_log_error.assert_called_once()
    logged_msg = mock_log_error.call_args[0][0]
    assert "SafeProperty error in SETTER" in logged_msg
    assert "ValueError" in logged_msg


@pytest.mark.timeout(100)
def test_safe_slot_emit(qtbot):
    """
    Test that the signal is emitted correctly.
    """
    signal_obj = TestSafeSlotEmitter()
    test_obj = TestSafeSlotClass(signal_obj=signal_obj)
    signal_obj.test_signal.emit()

    qtbot.waitUntil(lambda: test_obj._method_without_verification_called, timeout=1000)
    qtbot.waitUntil(lambda: test_obj._method_with_verification_called, timeout=1000)

    test_obj.deleteLater()

    test_obj = TestSafeSlotClass(signal_obj=signal_obj)
    test_obj.method_without_sender_verification()
    test_obj.method_with_sender_verification()

    assert test_obj._method_without_verification_called is True
    assert test_obj._method_with_verification_called is False

    test_obj.deleteLater()
    signal_obj.deleteLater()
