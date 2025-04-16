"""This module contains fixtures that are used in the end-2-end tests."""

import random

import pytest

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
def connected_client_gui_obj(qtbot, gui_id, bec_client_lib):
    """
    Fixture to create a new BECGuiClient object and start a server in the background.

    This fixture should be used if a new gui instance is needed for each test.
    """
    gui = BECGuiClient(gui_id=gui_id)
    try:
        gui.start(wait=True)
        qtbot.waitUntil(lambda: hasattr(gui, "bec"), timeout=5000)
        yield gui
    finally:
        gui.kill_server()


@pytest.fixture(scope="session")
def connected_gui_with_scope_session(qtbot, gui_id, bec_client_lib):
    """
    Fixture to create a new BECGuiClient object and start a server in the background.

    This fixture is scoped to the session, meaning it remains alive for all tests in the session.
    We can use this fixture to create a gui object that is used across multiple tests, and
    simulate a real-world scenario where the gui is not restarted for each test.
    """
    gui = BECGuiClient(gui_id=gui_id)
    try:
        gui.start(wait=True)
        # After the server started, we need to wait until the bec exists in the namespace
        qtbot.waitUntil(lambda: hasattr(gui, "bec"), timeout=5000)
        yield gui
    finally:
        gui.kill_server()
