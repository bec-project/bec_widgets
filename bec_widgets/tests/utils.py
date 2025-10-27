"""
Shared bodies of the autouse fixtures of the bec_widgets unit tests.

The ``*_fixture`` generators are meant to be wrapped in local fixtures, so that plugin repositories
can run their widget tests against the same mocked BEC client and leak checks, e.g.::

    @pytest.fixture(autouse=True)
    def bec_dispatcher(threads_check):
        yield from bec_widgets.tests.utils.bec_dispatcher_fixture()
"""

from unittest import mock
from unittest.mock import patch

import fakeredis
from bec_lib import service_config
from bec_lib.client import BECClient
from bec_qthemes import apply_theme
from bec_qthemes._theme import Theme
from pytestqt.exceptions import TimeoutError as QtBotTimeoutError
from qtpy.QtCore import QEvent, QEventLoop
from qtpy.QtWidgets import QApplication

from bec_widgets.tests.fake_devices import DEVICES, DMMock
from bec_widgets.utils import bec_dispatcher as bec_dispatcher_module
from bec_widgets.utils import error_popups
from bec_widgets.utils.bec_dispatcher import QtRedisConnector
from bec_widgets.utils.rpc_register import RPCRegister


def process_all_deferred_deletes(qapp):
    qapp.sendPostedEvents(None, QEvent.DeferredDelete)
    qapp.processEvents(QEventLoop.AllEvents)


def qapplication_fixture(qtbot, request, testable_qtimer_class):
    """
    Reset the application to the light theme, then check after the test that all timers are
    stopped and all top-level widgets are closed. The checks are skipped for failed tests, which
    requires a ``pytest_runtest_makereport`` hook that stores ``item.stash["failed"]``.
    """
    qapp = QApplication.instance()
    process_all_deferred_deletes(qapp)

    if (
        not hasattr(qapp, "theme")
        or not isinstance(qapp.theme, Theme)
        or qapp.theme.theme != "light"
    ):
        apply_theme("light")
        qapp.processEvents()

    yield

    # Imported here so that the test session can select the ophyd control layer before ophyd loads
    from ophyd._dummy_shim import _dispatcher

    from bec_widgets.widgets.editors.bec_console.bec_console import _bec_console_registry

    # stop pyepics dispatcher for leaking tests
    _dispatcher.stop()
    _bec_console_registry.clear()
    process_all_deferred_deletes(qapp)
    # if the test failed, we don't want to check for open widgets as
    # it simply pollutes the output
    if request.node.stash._storage.get("failed"):
        print("Test failed, skipping cleanup checks")
        return
    bec_dispatcher = bec_dispatcher_module.BECDispatcher()
    bec_dispatcher.stop_cli_server()

    testable_qtimer_class.check_all_stopped(qtbot)
    qapp.processEvents()
    if hasattr(qapp, "os_listener") and qapp.os_listener:
        qapp.removeEventFilter(qapp.os_listener)
    try:
        qtbot.waitUntil(lambda: qapp.topLevelWidgets() == [])
    except QtBotTimeoutError as exc:
        raise TimeoutError(f"Failed to close all widgets: {qapp.topLevelWidgets()}") from exc


def rpc_register_fixture():
    """Provide the RPCRegister singleton and reset it after the test."""
    yield RPCRegister()
    RPCRegister.reset_singleton()


_REDIS_CONN: QtRedisConnector | None = None


def global_mock_qt_redis_connector(*_, **__):
    global _REDIS_CONN
    if _REDIS_CONN is None:
        _REDIS_CONN = QtRedisConnector(bootstrap="localhost:1", redis_cls=fakeredis.FakeRedis)
    return _REDIS_CONN


def mock_client(*_, **__):
    """Create a BECClient on a shared fakeredis connector, populated with the fake DEVICES."""
    with (
        patch("bec_lib.client.DeviceManagerBase", DMMock),
        patch("bec_lib.client.DAPPlugins"),
        patch("bec_lib.client.Scans"),
        patch("bec_lib.client.ScanManager"),
        patch("bec_lib.bec_service.BECAccess"),
    ):
        client = BECClient(
            config=service_config.ServiceConfig(config={"redis": {"host": "localhost", "port": 1}}),
            connector_cls=global_mock_qt_redis_connector,
        )
        client.start()
    client.device_manager.add_devices(DEVICES)
    return client


def bec_dispatcher_fixture():
    """
    Provide a BECDispatcher backed by :func:`mock_client` and tear it down after the test. The
    wrapping fixture should depend on bec_lib's ``threads_check`` so that the thread check runs
    after the client is shut down.
    """
    with mock.patch.object(bec_dispatcher_module, "BECClient", mock_client):
        bec_dispatcher = bec_dispatcher_module.BECDispatcher()
    yield bec_dispatcher
    bec_dispatcher.disconnect_all()
    # clean BEC client
    bec_dispatcher.client.shutdown()
    # stop the cli server
    bec_dispatcher.stop_cli_server()
    # reinitialize singleton for next test
    bec_dispatcher_module.BECDispatcher.reset_singleton()


def clean_singleton_fixture():
    """Drop the error popup singleton before the test."""
    error_popups._popup_utility_instance = None
    yield
