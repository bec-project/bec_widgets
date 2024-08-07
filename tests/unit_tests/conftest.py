import pytest
from pytestqt.exceptions import TimeoutError as QtBotTimeoutError
from qtpy.QtWidgets import QApplication

from bec_widgets.cli.rpc_register import RPCRegister
from bec_widgets.qt_utils import error_popups
from bec_widgets.utils import bec_dispatcher as bec_dispatcher_module


@pytest.fixture(autouse=True)
def qapplication(qtbot):  # pylint: disable=unused-argument
    yield

    qapp = QApplication.instance()
    qapp.quit()
    qapp.processEvents()
    try:
        qtbot.waitUntil(lambda: qapp.topLevelWidgets() == [])
    except QtBotTimeoutError as exc:
        raise TimeoutError(f"Failed to close all widgets: {qapp.topLevelWidgets()}") from exc


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


def create_widget(qtbot, widget, *args, **kwargs):
    """
    Create a widget and add it to the qtbot for testing. This is a helper function that
    should be used in all tests that require a widget to be created.
    DO NOT CREATE WIDGETS DIRECTLY IN A FIXTURE!

    Args:
        qtbot (fixture): pytest-qt fixture
        widget (QWidget): widget class to be created
        *args: positional arguments for the widget
        **kwargs: keyword arguments for the widget

    Returns:
        QWidget: the created widget

    """
    widget = widget(*args, **kwargs)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget
