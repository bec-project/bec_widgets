import pytest

from bec_widgets.cli.client import BECFigure
from bec_widgets.cli.server import BECWidgetsCLIServer
from bec_widgets.utils.bec_dispatcher import _BECDispatcher


@pytest.fixture
def rpc_server(qtbot):
    # make a new dispatcher (not using the singleton), since the server is supposed to run in another process
    dispatcher = _BECDispatcher()
    server = BECWidgetsCLIServer(gui_id="id_test", dispatcher=dispatcher)
    qtbot.addWidget(server.fig)
    qtbot.waitExposed(server.fig)
    qtbot.wait(200)
    yield server
    server.client.shutdown()


def test_rpc_waveform1d(rpc_server, qtbot):
    fig = BECFigure(rpc_server.gui_id)
    ax = fig.add_plot()
    curve = ax.add_curve_custom([1, 2, 3], [1, 2, 3])
    curve.set_color("red")
    curve = ax.curves[0]
    curve.set_color("blue")
