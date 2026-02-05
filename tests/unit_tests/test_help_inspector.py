# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

from unittest import mock

import pytest
from qtpy import QtCore, QtWidgets

from bec_widgets.utils.help_inspector.help_inspector import HelpInspector
from bec_widgets.utils.widget_io import WidgetHierarchy
from bec_widgets.widgets.control.buttons.button_abort.button_abort import AbortButton


@pytest.fixture
def help_inspector(qtbot, mocked_client):
    widget = HelpInspector(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def abort_button(qtbot):
    widget = AbortButton()
    widget.setToolTip("This is an abort button.")

    def get_help_md():
        return "This is **markdown** help text for the abort button."

    widget.get_help_md = get_help_md  # type: ignore

    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)

    yield widget


def test_help_inspector_button(help_inspector):
    """Test the HelpInspector widget."""
    assert not help_inspector._active
    help_inspector._button.click()
    assert help_inspector._active
    assert help_inspector._button.isChecked()
    cursor = QtWidgets.QApplication.overrideCursor()
    assert cursor is not None
    assert cursor.shape() == QtCore.Qt.CursorShape.WhatsThisCursor
    help_inspector._button.click()
    assert not help_inspector._active
    assert not help_inspector._button.isChecked()
    assert QtWidgets.QApplication.overrideCursor() is None


def test_help_inspector_register_callback(help_inspector):
    """Test registering a callback in the HelpInspector widget."""

    assert len(help_inspector._callbacks) == 3  # default callbacks

    def my_callback(widget):
        pass

    cb_id = help_inspector.register_callback(my_callback)
    assert len(help_inspector._callbacks) == 4
    assert help_inspector._callbacks[cb_id] == my_callback

    cb_id2 = help_inspector.register_callback(my_callback)
    assert len(help_inspector._callbacks) == 5
    assert help_inspector._callbacks[cb_id2] == my_callback

    help_inspector.unregister_callback(cb_id)
    assert len(help_inspector._callbacks) == 4

    help_inspector.unregister_callback(cb_id2)
    assert len(help_inspector._callbacks) == 3


def test_help_inspector_escape_key(qtbot, help_inspector):
    """Test that pressing the Escape key deactivates the HelpInspector."""
    help_inspector._button.click()
    assert help_inspector._active
    qtbot.keyClick(help_inspector, QtCore.Qt.Key.Key_Escape)
    assert not help_inspector._active
    assert not help_inspector._button.isChecked()
    assert QtWidgets.QApplication.overrideCursor() is None


def test_help_inspector_event_filter(help_inspector, abort_button):
    """Test the event filter of the HelpInspector."""
    # Test nothing happens when not active
    obj = mock.MagicMock(spec=QtWidgets.QWidget)
    event = mock.MagicMock(spec=QtCore.QEvent)
    assert help_inspector._active is False
    with mock.patch.object(
        QtWidgets.QWidget, "eventFilter", return_value=False
    ) as super_event_filter:
        help_inspector.eventFilter(obj, event)  # should do nothing and return False
        super_event_filter.assert_called_once_with(obj, event)
        super_event_filter.reset_mock()

        help_inspector._active = True
        with mock.patch.object(help_inspector, "_toggle_mode") as mock_toggle:
            # Key press Escape
            event.type = mock.MagicMock(return_value=QtCore.QEvent.KeyPress)
            event.key = mock.MagicMock(return_value=QtCore.Qt.Key.Key_Escape)
            help_inspector.eventFilter(obj, event)
            mock_toggle.assert_called_once_with(False)
            mock_toggle.reset_mock()

            # Click on itself
            event.type = mock.MagicMock(return_value=QtCore.QEvent.MouseButtonPress)
            event.button = mock.MagicMock(return_value=QtCore.Qt.LeftButton)
            event.globalPos = mock.MagicMock(return_value=QtCore.QPoint(1, 1))
            with mock.patch.object(
                help_inspector._app, "widgetAt", side_effect=[help_inspector, abort_button]
            ):
                # Return for self call
                help_inspector.eventFilter(obj, event)
                mock_toggle.assert_called_once_with(False)
                mock_toggle.reset_mock()
                # Run Callback for abort_button
                callback_data = []

                def _my_callback(widget):
                    callback_data.append(widget)

                help_inspector.register_callback(_my_callback)

                help_inspector.eventFilter(obj, event)
                mock_toggle.assert_not_called()
                assert len(callback_data) == 1
                assert callback_data[0] == abort_button
                callback_data.clear()
