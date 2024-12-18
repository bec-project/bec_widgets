from unittest import mock

import pytest
from pytestqt.exceptions import TimeoutError as QtBotTimeoutError
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QApplication

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.qt_utils import error_popups
from bec_widgets.utils import bec_dispatcher as bec_dispatcher_module


class TestableQTimer(QTimer):
    _instances = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        TestableQTimer._instances.append(self)

    @classmethod
    def check_all_stopped(cls, qtbot):
        try:
            qtbot.waitUntil(lambda: all(not timer.isActive() for timer in cls._instances))
        except QtBotTimeoutError as exc:
            raise TimeoutError("Failed to stop all timers") from exc
        cls._instances = []


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    item.stash["failed"] = rep.failed


@pytest.fixture(autouse=True)
def qapplication(qtbot, request):  # pylint: disable=unused-argument
    with mock.patch("qtpy.QtCore.QTimer", new=TestableQTimer):
        yield

        # if the test failed, we don't want to check for open widgets as
        # it simply pollutes the output
        if request.node.stash._storage.get("failed"):
            print("Test failed, skipping cleanup checks")
            return

        TestableQTimer.check_all_stopped(qtbot)

    qapp = QApplication.instance()
    qapp.processEvents()
    if hasattr(qapp, "os_listener") and qapp.os_listener:
        qapp.removeEventFilter(qapp.os_listener)
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
