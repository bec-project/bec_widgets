import pytest

from bec_widgets.cli.rpc_register import RPCRegister
from bec_widgets.cli.server import BECWidgetsCLIServer
from bec_widgets.utils import BECDispatcher


@pytest.fixture(autouse=True)
def rpc_register():
    yield RPCRegister()
    RPCRegister.reset_singleton()


@pytest.fixture
def rpc_server(qtbot, bec_client_lib, threads_check):
    dispatcher = BECDispatcher(client=bec_client_lib)  # Has to init singleton with fixture client
    server = BECWidgetsCLIServer(gui_id="figure")
    qtbot.addWidget(server.fig)
    qtbot.waitExposed(server.fig)
    qtbot.wait(1000)  # 1s long to wait until gui is ready
    yield server
    dispatcher.disconnect_all()
    server.client.shutdown()
    server.shutdown()
    dispatcher.reset_singleton()
