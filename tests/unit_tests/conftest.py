import pytest

from bec_widgets.cli.rpc_register import RPCRegister
from bec_widgets.qt_utils import error_popups
from bec_widgets.utils import bec_dispatcher as bec_dispatcher_module


@pytest.fixture(autouse=True)
def qapplication(qapp):  # pylint: disable=unused-argument
    yield


@pytest.fixture(autouse=True)
def rpc_register():
    yield RPCRegister()
    RPCRegister.reset_singleton()


@pytest.fixture(autouse=True)
def bec_dispatcher(threads_check):  # pylint: disable=unused-argument
    bec_dispatcher = bec_dispatcher_module.BECDispatcher()
    yield bec_dispatcher
    bec_dispatcher.disconnect_all()
    # clean BEC client
    bec_dispatcher.client.shutdown()
    # reinitialize singleton for next test
    bec_dispatcher_module.BECDispatcher.reset_singleton()


@pytest.fixture(autouse=True)
def clean_singleton():
    error_popups._popup_utility_instance = None
