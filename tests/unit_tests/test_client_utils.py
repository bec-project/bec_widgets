from contextlib import contextmanager
from unittest import mock

import pytest

from bec_widgets.cli.client import BECFigure
from bec_widgets.cli.client_utils import BECGuiClient, _start_plot_process
from bec_widgets.tests.utils import FakeDevice


@pytest.fixture
def cli_figure():
    fig = BECFigure(gui_id="test")
    with mock.patch.object(fig, "_run_rpc") as mock_rpc_call:
        with mock.patch.object(fig, "gui_is_alive", return_value=True):
            yield fig, mock_rpc_call


def test_rpc_call_plot(cli_figure):
    fig, mock_rpc_call = cli_figure
    fig.plot(x_name="samx", y_name="bpm4i")
    mock_rpc_call.assert_called_with("plot", x_name="samx", y_name="bpm4i")


def test_rpc_call_accepts_device_as_input(cli_figure):
    dev1 = FakeDevice("samx")
    dev2 = FakeDevice("bpm4i")
    fig, mock_rpc_call = cli_figure
    fig.plot(x_name=dev1, y_name=dev2)
    mock_rpc_call.assert_called_with("plot", x_name="samx", y_name="bpm4i")


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
        _start_plot_process("gui_id", BECFigure, config)
        command = ["bec-gui-server", "--id", "gui_id", "--gui_class", "BECFigure", "--hide"]
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
        mixin.gui_is_alive = mock.MagicMock()
        mixin.gui_is_alive.side_effect = [True]

        try:
            with mock.patch.object(mixin, "_start_update_script"):
                yield mixin
        finally:
            mixin.close()

    with bec_client_mixin() as mixin:
        with mock.patch("bec_widgets.cli.client_utils._start_plot_process") as mock_start_plot:
            mock_start_plot.return_value = [mock.MagicMock(), mock.MagicMock()]
            mixin.start_server(
                wait=False
            )  # the started event will not be set, wait=True would block forever
            mock_start_plot.assert_called_once_with(
                "gui_id", BECGuiClient, mixin._client._service_config.config, logger=mock.ANY
            )
            mixin._start_update_script.assert_called_once()
