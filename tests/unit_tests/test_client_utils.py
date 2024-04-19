from unittest import mock

import pytest

from bec_widgets.cli.client import BECFigure

from .client_mocks import FakeDevice


@pytest.fixture
def cli_figure():
    fig = BECFigure(gui_id="test")
    with mock.patch.object(fig, "_run_rpc") as mock_rpc_call:
        with mock.patch.object(fig, "gui_is_alive", return_value=True):
            yield fig, mock_rpc_call


def test_rpc_call_plot(cli_figure):
    fig, mock_rpc_call = cli_figure
    fig.plot("samx", "bpm4i")
    mock_rpc_call.assert_called_with("plot", "samx", "bpm4i")


def test_rpc_call_accepts_device_as_input(cli_figure):
    dev1 = FakeDevice("samx")
    dev2 = FakeDevice("bpm4i")
    fig, mock_rpc_call = cli_figure
    fig.plot(dev1, dev2)
    mock_rpc_call.assert_called_with("plot", "samx", "bpm4i")
