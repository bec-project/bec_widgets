import pytest

from bec_widgets.cli.client import BECFigure, BECImageShow, BECMotorMap, BECWaveform
from bec_widgets.cli.server import BECWidgetsCLIServer
from bec_widgets.utils import BECDispatcher
from bec_widgets.widgets.plots.waveform import Signal, SignalData


@pytest.fixture
def rpc_server(qtbot, bec_client_lib):
    dispatcher = BECDispatcher(client=bec_client_lib)  # Has to init singleton with fixture client
    server = BECWidgetsCLIServer(gui_id="id_test")
    qtbot.addWidget(server.fig)
    qtbot.waitExposed(server.fig)
    qtbot.wait(1000)  # 1s long to wait until gui is ready
    yield server
    server.client.shutdown()


def test_rpc_waveform1d_custom_curve(rpc_server, qtbot):
    fig = BECFigure(rpc_server.gui_id)
    fig_server = rpc_server.fig

    ax = fig.add_plot()
    curve = ax.add_curve_custom([1, 2, 3], [1, 2, 3])
    curve.set_color("red")
    curve = ax.curves[0]
    curve.set_color("blue")

    assert len(fig_server.widgets) == 1
    assert len(fig_server.widgets["widget_1"].curves) == 1


def test_rpc_plotting_shortcuts(rpc_server, qtbot):
    fig = BECFigure(rpc_server.gui_id)
    fig_server = rpc_server.fig

    plt = fig.plot("samx", "bpm4i")
    im = fig.image("eiger")
    motor_map = fig.motor_map("samx", "samy")

    # Checking if classes are correctly initialised
    assert len(fig_server.widgets) == 3
    assert plt.__class__.__name__ == "BECWaveform"
    assert plt.__class__ == BECWaveform
    assert im.__class__.__name__ == "BECImageShow"
    assert im.__class__ == BECImageShow
    assert motor_map.__class__.__name__ == "BECMotorMap"
    assert motor_map.__class__ == BECMotorMap

    # # check if the correct devices are set
    # plt_curve_config = plt.curves[0].get_config()
    # assert plt_curve_config["signals"] == {
    #     "source": "scan_segment",
    #     "x": {"name": "samx", "entry": "samx", "unit": None, "modifier": None, "limits": None},
    #     "y": {"name": "bpm4i", "entry": "bpm4i", "unit": None, "modifier": None, "limits": None},
    #     "z": None,
    # }
    #
    # im_config = im.get_config()
