import threading

import pytest
from bec_lib.bec_service import BECService

from bec_widgets.utils import bec_dispatcher as bec_dispatcher_module


@pytest.fixture()
def threads_check():
    current_threads = set(
        th
        for th in threading.enumerate()
        if "loguru" not in th.name and th is not threading.main_thread()
    )
    yield
    threads_after = set(
        th
        for th in threading.enumerate()
        if "loguru" not in th.name and th is not threading.main_thread()
    )
    additional_threads = threads_after - current_threads
    assert (
        len(additional_threads) == 0
    ), f"Test creates {len(additional_threads)} threads that are not cleaned: {additional_threads}"


@pytest.fixture(autouse=True)
def bec_dispatcher(threads_check):
    bec_dispatcher = bec_dispatcher_module.BECDispatcher()
    yield bec_dispatcher
    bec_dispatcher.disconnect_all()
    # clean BEC client
    bec_dispatcher.client.shutdown()
    # reinitialize singleton for next test
    bec_dispatcher_module._bec_dispatcher = None
