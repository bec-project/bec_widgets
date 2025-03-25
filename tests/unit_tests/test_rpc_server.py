import argparse
from unittest import mock

import pytest
from bec_lib.service_config import ServiceConfig

from bec_widgets.cli.server import GUIServer


@pytest.fixture
def gui_server():
    args = argparse.Namespace(
        config=None, id="gui_id", gui_class="LaunchWindow", gui_class_id="bec", hide=False
    )
    return GUIServer(args=args)


def test_gui_server_start_server_without_service_config(gui_server):
    """
    Test that the server is started with the correct arguments.
    """
    assert gui_server.config is None
    assert gui_server.gui_id == "gui_id"
    assert gui_server.gui_class == "LaunchWindow"
    assert gui_server.gui_class_id == "bec"
    assert gui_server.hide is False


def test_gui_server_get_service_config(gui_server):
    """
    Test that the server is started with the correct arguments.
    """
    assert gui_server._get_service_config().config is ServiceConfig().config


@pytest.mark.parametrize(
    "connections, hide",
    [
        ({}, False),
        ({"launcher": mock.MagicMock()}, False),
        ({"launcher": mock.MagicMock(), "dock_area": mock.MagicMock()}, True),
    ],
)
def test_gui_server_turns_off_the_lights(gui_server, connections, hide):
    with mock.patch.object(gui_server, "launcher_window") as mock_launcher_window:
        with mock.patch.object(gui_server, "app") as mock_app:
            gui_server._turn_off_the_lights(connections)

            if not hide:
                mock_launcher_window.show.assert_called_once()
                mock_launcher_window.activateWindow.assert_called_once()
                mock_launcher_window.raise_.assert_called_once()
                mock_app.setQuitOnLastWindowClosed.assert_called_once_with(True)
            else:
                mock_launcher_window.hide.assert_called_once()
                mock_app.setQuitOnLastWindowClosed.assert_called_once_with(False)
