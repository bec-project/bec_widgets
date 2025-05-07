# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import os
from unittest import mock

import pytest
from bec_lib.endpoints import MessageEndpoints

import bec_widgets
from bec_widgets.applications.launch_window import LaunchWindow
from bec_widgets.widgets.containers.auto_update.auto_updates import AutoUpdates
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow, UILaunchWindow

from .client_mocks import mocked_client

base_path = os.path.dirname(bec_widgets.__file__)


@pytest.fixture
def bec_launch_window(qtbot, mocked_client):
    widget = LaunchWindow(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_launch_window_initialization(bec_launch_window):
    assert isinstance(bec_launch_window, BECMainWindow)


def test_launch_window_launch_ui_file(bec_launch_window):
    # Mock the file dialog to return a specific UI file path
    ui_file_path = os.path.join(
        base_path, "widgets/control/device_control/positioner_box/positioner_box/positioner_box.ui"
    )
    bec_launch_window._open_custom_ui_file = lambda: ui_file_path

    # Call the method to launch the custom UI file
    res = bec_launch_window.launch("custom_ui_file", ui_file=ui_file_path)

    assert isinstance(res, UILaunchWindow)

    # Check if the custom UI file was launched correctly
    assert res.object_name == "positioner_box"
    assert res.windowTitle() == "BEC - positioner_box"

    # We need to manually close the launched window as it is not registered with qtbot.
    # In real usage, the GUIServer would handle this in the sigint handler in case of a ctrl-c initiated shutdown.
    res.close()
    res.deleteLater()


def test_launch_window_launch_ui_file_raises_for_qmainwindow(bec_launch_window):
    # Mock the file dialog to return a specific UI file path
    # the selected file must contain a QMainWindow widget but can be any file
    ui_file_path = os.path.join(base_path, "examples/general_app/general_app.ui")

    # Call the method to launch the custom UI file
    with pytest.raises(ValueError) as excinfo:
        bec_launch_window.launch("custom_ui_file", ui_file=ui_file_path)

    assert "Loading a QMainWindow from a UI file is currently not supported." in str(excinfo.value)


def test_launch_window_launch_default_auto_update(bec_launch_window):
    # Mock the auto update selection
    bec_launch_window.tiles["auto_update"].selector.setCurrentText("Default")

    # Call the method to launch the auto update
    res = bec_launch_window._open_auto_update()

    assert isinstance(res, AutoUpdates)
    assert res.windowTitle() == "BEC - AutoUpdates"

    # We need to manually close the launched window as it is not registered with qtbot.
    # In real usage, the GUIServer would handle this in the sigint handler in case of a ctrl-c initiated shutdown.
    res.close()
    res.deleteLater()


def test_launch_window_launch_plugin_auto_update(bec_launch_window):
    class PluginAutoUpdate(AutoUpdates): ...

    bec_launch_window.available_auto_updates = {"PluginAutoUpdate": PluginAutoUpdate}
    bec_launch_window.tiles["auto_update"].selector.clear()
    bec_launch_window.tiles["auto_update"].selector.addItems(
        list(bec_launch_window.available_auto_updates.keys()) + ["Default"]
    )
    bec_launch_window.tiles["auto_update"].selector.setCurrentText("PluginAutoUpdate")
    res = bec_launch_window._open_auto_update()
    assert isinstance(res, PluginAutoUpdate)
    assert res.windowTitle() == "BEC - PluginAutoUpdate"
    # We need to manually close the launched window as it is not registered with qtbot.
    # In real usage, the GUIServer would handle this in the sigint handler in case of a ctrl-c initiated shutdown.
    res.close()
    res.deleteLater()


@pytest.mark.parametrize(
    "connections, hide",
    [
        ({}, False),
        ({"launcher": mock.MagicMock()}, False),
        ({"launcher": mock.MagicMock(), "dock_area": mock.MagicMock()}, True),
    ],
)
def test_gui_server_turns_off_the_lights(bec_launch_window, connections, hide):
    with (
        mock.patch.object(bec_launch_window, "show") as mock_show,
        mock.patch.object(bec_launch_window, "activateWindow") as mock_activate_window,
        mock.patch.object(bec_launch_window, "raise_") as mock_raise,
        mock.patch.object(bec_launch_window, "hide") as mock_hide,
        mock.patch.object(
            bec_launch_window.app, "setQuitOnLastWindowClosed"
        ) as mock_set_quit_on_last_window_closed,
    ):

        bec_launch_window._turn_off_the_lights(connections)
        if hide:
            mock_hide.assert_called_once()
            mock_set_quit_on_last_window_closed.assert_called_once_with(False)
        else:
            mock_show.assert_called_once()
            mock_activate_window.assert_called_once()
            mock_raise.assert_called_once()
            mock_set_quit_on_last_window_closed.assert_called_once_with(True)


@pytest.mark.parametrize(
    "connections, close_called",
    [
        ({}, True),
        ({"launcher": mock.MagicMock()}, True),
        ({"launcher": mock.MagicMock(), "dock_area": mock.MagicMock()}, False),
    ],
)
def test_launch_window_closes(bec_launch_window, connections, close_called):
    """
    Test that the close event is handled correctly based on the connections.
    If there are no connections or only the launcher connection, the window should close.
    If there are other connections, the window should hide instead of closing.
    """
    close_event = mock.MagicMock()
    with mock.patch.object(
        bec_launch_window.register, "list_all_connections", return_value=connections
    ):
        with mock.patch.object(bec_launch_window, "hide") as mock_hide:
            bec_launch_window.closeEvent(close_event)
            if close_called:
                mock_hide.assert_not_called()
                close_event.accept.assert_called_once()
            else:
                mock_hide.assert_called_once()
                close_event.accept.assert_not_called()
                close_event.ignore.assert_called_once()
