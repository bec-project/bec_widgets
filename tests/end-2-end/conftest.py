"""This module contains fixtures that are used in the end-2-end tests."""

import random
from typing import Any, Generator

import pytest
from bec_lib.client import BECClient
from bec_lib.redis_connector import RedisConnector
from bec_lib.service_config import ServiceConfig
from bec_lib.tests.utils import wait_for_empty_queue

from bec_widgets.cli.client_utils import BECGuiClient, _start_plot_process
from bec_widgets.utils import BECDispatcher

# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


@pytest.fixture(autouse=True)
def threads_check_fixture(threads_check):
    """
    Fixture to check if threads are still alive at the end of the test.

    This should always run to avoid leaked threads within our application.
    The fixture is set to autouse, meaning it will run for every test.
    """
    return


@pytest.fixture
def gui_id():
    """New gui id each time, to ensure no 'gui is alive' zombie key can perturbate"""
    return f"figure_{random.randint(0,100)}"  # make a new gui id each time, to ensure no 'gui is alive' zombie key can perturbate


@pytest.fixture
def connected_client_gui_obj(gui_id, bec_client_lib):
    """
    Fixture to create a new BECGuiClient object and start a server in the background.

    This fixture should be used if a new gui instance is needed for each test.
    """
    gui = BECGuiClient(gui_id=gui_id)
    try:
        gui.start(wait=True)
        yield gui
    finally:
        gui.kill_server()


@pytest.fixture(scope="session")
def bec_client_lib_with_demo_config_session(
    bec_redis_fixture, bec_services_config_file_path, bec_servers
):
    """Session-scoped fixture to create a BECClient object with a demo configuration."""
    config = ServiceConfig(bec_services_config_file_path)
    bec = BECClient(config, RedisConnector, forced=True, wait_for_server=True)
    bec.start()
    bec.config.load_demo_config()
    try:
        yield bec
    finally:
        bec.shutdown()


@pytest.fixture(scope="session")
def bec_client_lib_session(bec_client_lib_with_demo_config_session):
    """Session-scoped fixture to create a BECClient object with a demo configuration."""
    bec = bec_client_lib_with_demo_config_session
    bec.queue.request_queue_reset()
    bec.queue.request_scan_continuation()
    wait_for_empty_queue(bec)
    yield bec


@pytest.fixture(scope="session")
def connected_gui_and_bec_with_scope_session(bec_client_lib_session):
    """
    Fixture to create a new BECGuiClient object and start a server in the background.

    This fixture is scoped to the session, meaning it remains alive for all tests in the session.
    We can use this fixture to create a gui object that is used across multiple tests, and
    simulate a real-world scenario where the gui is not restarted for each test.

    Returns:
        The gui object as for the CLI and bec_client_lib object.
    """
    gui_id = "GUIMainWindow_TEST"
    gui = BECGuiClient(gui_id=gui_id)
    try:
        gui.start(wait=True)
        yield gui
    finally:
        gui.kill_server()
