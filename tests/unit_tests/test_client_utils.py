from contextlib import contextmanager
from unittest import mock

import pytest

from bec_widgets.cli.client import BECDockArea
from bec_widgets.cli.client_utils import BECGuiClient, _start_plot_process


@pytest.fixture
def cli_dock_area():
    dock_area = BECDockArea(gui_id="test")
    with mock.patch.object(dock_area, "_run_rpc") as mock_rpc_call:
        with mock.patch.object(dock_area, "_gui_is_alive", return_value=True):
            yield dock_area, mock_rpc_call


def test_rpc_call_new_dock(cli_dock_area):
    dock_area, mock_rpc_call = cli_dock_area
    dock_area.new(name="test")
    mock_rpc_call.assert_called_with("new", name="test")


@pytest.mark.parametrize(
    "config, call_config",
    [
        (None, None),
        ("/path/to/config.yml", "/path/to/config.yml"),
        ({"key": "value"}, '{"key": "value"}'),
    ],
)
def test_client_utils_start_plot_process(config, call_config):
    with mock.patch("bec_widgets.cli.client_utils.subprocess.Popen") as mock_popen:
        _start_plot_process("gui_id", "bec", config, gui_class="BECDockArea")
        command = [
            "bec-gui-server",
            "--id",
            "gui_id",
            "--gui_class",
            "BECDockArea",
            "--gui_class_id",
            "bec",
            "--hide",
        ]
        if call_config:
            command.extend(["--config", call_config])
        mock_popen.assert_called_once_with(
            command,
            text=True,
            start_new_session=True,
            stdout=mock.ANY,
            stderr=mock.ANY,
            env=mock.ANY,
        )


def test_client_utils_passes_client_config_to_server(bec_dispatcher):
    """
    Test that the client config is passed to the server. This ensures that
    changes to the client config (either through config files or plugins) are
    reflected in the server.
    """

    @contextmanager
    def bec_client_mixin():
        mixin = BECGuiClient()
        mixin._client = bec_dispatcher.client
        mixin._gui_id = "gui_id"
        mixin._gui_is_alive = mock.MagicMock()
        mixin._gui_is_alive.side_effect = [True]

        try:
            yield mixin
        finally:
            mixin.kill_server()

    with bec_client_mixin() as mixin:
        with mock.patch("bec_widgets.cli.client_utils._start_plot_process") as mock_start_plot:
            mock_start_plot.return_value = [mock.MagicMock(), mock.MagicMock()]
            mixin._start_server(
                wait=False
            )  # the started event will not be set, wait=True would block forever
            mock_start_plot.assert_called_once_with(
                "gui_id",
                gui_class_id="bec",
                config=mixin._client._service_config.config,
                logger=mock.ANY,
            )
