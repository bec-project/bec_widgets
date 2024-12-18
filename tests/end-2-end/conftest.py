import random
import time
from contextlib import contextmanager

import pytest
from bec_lib.endpoints import MessageEndpoints

from bec_widgets.cli.client_utils import BECGuiClient, _start_plot_process
from bec_widgets.utils import BECDispatcher
from bec_widgets.widgets.containers.figure import BECFigure


# make threads check in autouse, **will be executed at the end**; better than
# having it in fixtures for each test, since it prevents from needing to
# 'manually' shutdown bec_client_lib (for example) to make it happy, whereas
# whereas in fact bec_client_lib makes its on cleanup
@pytest.fixture(autouse=True)
def threads_check_fixture(threads_check):
    return


@pytest.fixture
def gui_id():
    return f"figure_{random.randint(0,100)}"  # make a new gui id each time, to ensure no 'gui is alive' zombie key can perturbate


@contextmanager
def plot_server(gui_id, klass, client_lib):
    dispatcher = BECDispatcher(client=client_lib)  # Has to init singleton with fixture client
    process, _ = _start_plot_process(gui_id, klass, client_lib._client._service_config.config_path)
    try:
        while client_lib._client.connector.get(MessageEndpoints.gui_heartbeat(gui_id)) is None:
            time.sleep(0.3)
        yield gui_id
    finally:
        process.terminate()
        process.wait()
        dispatcher.disconnect_all()
        dispatcher.reset_singleton()


@pytest.fixture
def connected_client_figure(gui_id, bec_client_lib):
    with plot_server(gui_id, BECFigure, bec_client_lib) as server:
        yield server


@pytest.fixture
def connected_client_gui_obj(gui_id, bec_client_lib):
    gui = BECGuiClient(gui_id=gui_id)
    try:
        gui.start_server(wait=True)
        yield gui
    finally:
        gui.close()


@pytest.fixture
def connected_client_dock(gui_id, bec_client_lib):
    gui = BECGuiClient(gui_id=gui_id)
    gui._auto_updates_enabled = False
    try:
        gui.start_server(wait=True)
        yield gui.main
    finally:
        gui.close()


@pytest.fixture
def connected_client_dock_w_auto_updates(gui_id, bec_client_lib):
    gui = BECGuiClient(gui_id=gui_id)
    try:
        gui.start_server(wait=True)
        yield gui, gui.main
    finally:
        gui.close()
