import argparse

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
