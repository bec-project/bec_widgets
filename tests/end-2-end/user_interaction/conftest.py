"""
End-2-End test fixtures for module scoped testing. The fixtures overwrite the default versions used
for the function scoped tests. The fixtures will only be created once for this entire module, meaning
that any test can be used to test user interaction and potential leakage of threads or other resources across
different widgets.
"""

import random

import pytest
from bec_ipython_client import BECIPythonClient
from bec_lib.redis_connector import RedisConnector
from bec_lib.service_config import ServiceConfig
from bec_lib.tests.utils import wait_for_empty_queue
from pytestqt.plugin import QtBot

from bec_widgets.cli.client_utils import BECGuiClient

# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


@pytest.fixture(scope="module")
def gui_id():
    """New gui id each time, to ensure no 'gui is alive' zombie key can perturbate"""
    return f"figure_{random.randint(0,100)}"


@pytest.fixture(scope="module")
def bec_ipython_client_with_demo_config(
    bec_redis_fixture, bec_services_config_file_path, bec_servers
):
    """Fixture to create a BECIPythonClient with a demo config."""
    config = ServiceConfig(bec_services_config_file_path)
    bec = BECIPythonClient(config, RedisConnector, forced=True)
    bec.start()
    bec.config.load_demo_config()
    try:
        yield bec
    finally:
        bec.shutdown()
        bec._client._reset_singleton()


@pytest.fixture(scope="module")
def bec_client_lib(bec_ipython_client_with_demo_config):
    """Fixture to create a BECIPythonClient with a demo config."""
    bec = bec_ipython_client_with_demo_config
    bec.queue.request_queue_reset()
    bec.queue.request_scan_continuation()
    wait_for_empty_queue(bec)
    yield bec


@pytest.fixture(scope="module")
def qtbot_scope_module(qapp, request):
    """
    Fixture used to create a QtBot instance for using during testing.

    Make sure to call addWidget for each top-level widget you create to ensure
    that they are properly closed after the test ends.
    """
    result = QtBot(request)
    return result


@pytest.fixture(scope="module")
def connected_client_gui_obj(qtbot_scope_module, gui_id, bec_client_lib):
    """
    Fixture to create a new BECGuiClient object and start a server in the background.

    This fixture is scoped to the session, meaning it remains alive for all tests in the session.
    We can use this fixture to create a gui object that is used across multiple tests, and
    simulate a real-world scenario where the gui is not restarted for each test.
    """
    gui = BECGuiClient(gui_id=gui_id)
    try:
        gui.start(wait=True)
        qtbot_scope_module.waitUntil(lambda: hasattr(gui, "bec"), timeout=5000)
        yield gui
    finally:
        gui.kill_server()
