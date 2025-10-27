from pytestqt.exceptions import TimeoutError as QtBotTimeoutError
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QApplication

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils import bec_dispatcher as bec_dispatcher_module
from bec_widgets.utils import error_popups


class TestableQTimer(QTimer):
    _instances: list[tuple[QTimer, str]] = []
    _current_test_name: str = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        TestableQTimer._instances.append((self, TestableQTimer._current_test_name))

    @classmethod
    def check_all_stopped(cls, qtbot):
        def _is_done_or_deleted(t: QTimer):
            try:
                return not t.isActive()
            except RuntimeError as e:
                return "already deleted" in e.args[0]

        try:
            qtbot.waitUntil(lambda: all(_is_done_or_deleted(timer) for timer, _ in cls._instances))
        except QtBotTimeoutError as exc:
            active_timers = list(filter(lambda t: t[0].isActive(), cls._instances))
            (t.stop() for t, _ in cls._instances)
            raise TimeoutError(f"Failed to stop all timers: {active_timers}") from exc
        cls._instances = []


def qapplication_fixture(qtbot, request, testable_qtimer_class):
    yield

    if request.node.stash._storage.get("failed"):
        print("Test failed, skipping cleanup checks")
        return

    bec_dispatcher = bec_dispatcher_module.BECDispatcher()
    bec_dispatcher.stop_cli_server()

    testable_qtimer_class.check_all_stopped(qtbot)
    qapp = QApplication.instance()
    qapp.processEvents()
    if hasattr(qapp, "os_listener") and qapp.os_listener:
        qapp.removeEventFilter(qapp.os_listener)
    try:
        qtbot.waitUntil(lambda: qapp.topLevelWidgets() == [])
    except QtBotTimeoutError as exc:
        raise TimeoutError(f"Failed to close all widgets: {qapp.topLevelWidgets()}") from exc


def rpc_register_fixture():
    try:
        yield RPCRegister()
    finally:
        RPCRegister.reset_singleton()


def bec_dispatcher_fixture(threads_check):
    bec_dispatcher = bec_dispatcher_module.BECDispatcher()
    try:
        yield bec_dispatcher
    finally:
        bec_dispatcher.disconnect_all()
        bec_dispatcher.client.shutdown()
        bec_dispatcher.stop_cli_server()
        bec_dispatcher_module.BECDispatcher.reset_singleton()


def clean_singleton_fixture():
    error_popups._popup_utility_instance = None
    yield
