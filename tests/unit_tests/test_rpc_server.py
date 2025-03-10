from unittest import mock

import pytest

from bec_widgets.cli.server import _start_server
from bec_widgets.widgets.containers.figure import BECFigure


@pytest.fixture
def mocked_cli_server():
    with mock.patch("bec_widgets.cli.server.BECWidgetsCLIServer") as mock_server:
        with mock.patch("bec_widgets.cli.server.ServiceConfig") as mock_config:
            with mock.patch("bec_lib.logger.bec_logger.configure") as mock_logger:
                yield mock_server, mock_config, mock_logger


def test_rpc_server_start_server_without_service_config(mocked_cli_server):
    """
    Test that the server is started with the correct arguments.
    """
    mock_server, mock_config, _ = mocked_cli_server

    _start_server("gui_id", BECFigure, config=None)
    mock_server.assert_called_once_with(
        gui_id="gui_id", config=mock_config(), gui_class=BECFigure, gui_class_id="bec"
    )


@pytest.mark.parametrize(
    "config, call_config",
    [
        ("/path/to/config.yml", {"config_path": "/path/to/config.yml"}),
        ({"key": "value"}, {"config": {"key": "value"}}),
    ],
)
def test_rpc_server_start_server_with_service_config(mocked_cli_server, config, call_config):
    """
    Test that the server is started with the correct arguments.
    """
    mock_server, mock_config, _ = mocked_cli_server
    config = mock_config(**call_config)
    _start_server("gui_id", BECFigure, config=config)
    mock_server.assert_called_once_with(
        gui_id="gui_id", config=config, gui_class=BECFigure, gui_class_id="bec"
    )
