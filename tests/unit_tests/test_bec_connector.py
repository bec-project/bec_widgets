# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import time
from unittest import mock

import pytest
from qtpy.QtCore import QObject
from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.utils.bec_connector import BECConnector
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty
from bec_widgets.utils.error_popups import SafeSlot as Slot

from .client_mocks import mocked_client


class BECConnectorQObject(BECConnector, QObject): ...


class _CleanupBroadcastWidget(BECWidget, QWidget): ...


@pytest.fixture
def bec_connector(mocked_client):
    connector = BECConnectorQObject(client=mocked_client)
    return connector


def test_bec_connector_init(bec_connector):
    assert bec_connector is not None
    assert bec_connector.client is not None
    assert isinstance(bec_connector, BECConnector)
    assert bec_connector.config.widget_class == "BECConnectorQObject"


def test_bec_connector_init_with_gui_id(mocked_client):
    bc = BECConnectorQObject(client=mocked_client, gui_id="test_gui_id")
    assert bc.config.gui_id == "test_gui_id"
    assert bc.gui_id == "test_gui_id"


def test_bec_connector_set_gui_id(bec_connector):
    bec_connector._set_gui_id("test_gui_id")
    assert bec_connector.config.gui_id == "test_gui_id"


def test_bec_connector_sanitize_names(mocked_client):
    class MyWidget(BECConnector, QWidget):
        def __init__(self, parent=None, client=None, **kwargs):
            super().__init__(parent=parent, client=client, **kwargs)

    widget = MyWidget(client=mocked_client)
    widget.setObjectName("Test Name With Spaces")
    assert widget.objectName() == "Test_Name_With_Spaces"
    widget.setObjectName("Test@Name#With$Special%Characters!")
    assert widget.objectName() == "Test_Name_With_Special_Characters_"


def test_bec_connector_change_config(bec_connector):
    bec_connector.on_config_update({"gui_id": "test_gui_id"})
    assert bec_connector.config.gui_id == "test_gui_id"


def test_bec_connector_get_obj_by_id(bec_connector):
    bec_connector._set_gui_id("test_gui_id")
    assert bec_connector.get_obj_by_id("test_gui_id") == bec_connector
    assert bec_connector.get_obj_by_id("test_gui_id_2") is None


def test_bec_connector_update_client(bec_connector, mocked_client):
    client_new = mocked_client
    bec_connector.update_client(client_new)
    assert bec_connector.client == client_new
    assert bec_connector.dev is not None
    assert bec_connector.scans is not None
    assert bec_connector.queue is not None
    assert bec_connector.scan_storage is not None
    assert bec_connector.dap is not None


def test_bec_connector_get_config(bec_connector):
    assert bec_connector.get_config(dict_output=False) == bec_connector.config
    assert bec_connector.get_config() == bec_connector.config.model_dump()


def test_bec_connector_submit_task(bec_connector):
    def test_func():
        time.sleep(2)
        print("done")

    completed = False

    @Slot()
    def complete_func():
        nonlocal completed
        completed = True

    bec_connector.submit_task(test_func, on_complete=complete_func)
    assert not completed
    while not completed:
        QApplication.processEvents()
        time.sleep(0.1)


def test_bec_connector_change_object_name(bec_connector):
    # Store the original object name and RPC register state
    original_name = bec_connector.objectName()
    original_gui_id = bec_connector.gui_id

    # Call the method with a new name
    new_name = "new_test_name"
    bec_connector.change_object_name(new_name)

    # Process events to allow the single shot timer to execute
    QApplication.processEvents()

    # Verify that the object name was changed correctly
    assert bec_connector.objectName() == new_name
    assert bec_connector.object_name == new_name

    # Verify that the object is registered in the RPC register with the new name
    assert bec_connector.rpc_register.object_is_registered(bec_connector)

    # Verify that the object with the original name is no longer registered
    # The object should still have the same gui_id
    assert bec_connector.gui_id == original_gui_id
    # Check that no object with the original name exists in the RPC register
    all_objects = bec_connector.rpc_register.list_all_connections().values()
    assert not any(obj.objectName() == original_name for obj in all_objects)

    # Store the current name for the next test
    previous_name = bec_connector.objectName()

    # Test with spaces and hyphens
    name_with_spaces_and_hyphens = "test name-with-hyphens"
    expected_name = "test_name_with_hyphens"
    bec_connector.change_object_name(name_with_spaces_and_hyphens)

    # Process events to allow the single shot timer to execute
    QApplication.processEvents()

    # Verify that the object name was changed correctly with replacements
    assert bec_connector.objectName() == expected_name
    assert bec_connector.object_name == expected_name

    # Verify that the object is still registered in the RPC register after the second name change
    assert bec_connector.rpc_register.object_is_registered(bec_connector)

    # Verify that the object with the previous name is no longer registered
    all_objects = bec_connector.rpc_register.list_all_connections().values()
    assert not any(obj.objectName() == previous_name for obj in all_objects)


def test_bec_widget_cleanup_broadcasts_after_children_are_unregistered(mocked_client, qtbot):
    parent = _CleanupBroadcastWidget(client=mocked_client, object_name="cleanup_parent")
    child = _CleanupBroadcastWidget(
        parent=parent, client=mocked_client, object_name="cleanup_child"
    )
    qtbot.addWidget(parent)

    observed_connections = []

    # Keep a strong reference: registry callbacks are weakly referenced.
    def _observe_connections(connections):
        observed_connections.append(set(connections))

    parent.rpc_register.add_callback(_observe_connections)

    parent.close()

    assert parent._destroyed is True
    assert child.gui_id not in parent.rpc_register.list_all_connections()
    assert all(
        parent.gui_id in snapshot or child.gui_id not in snapshot
        for snapshot in observed_connections
    )


def test_bec_connector_export_settings():

    class MyWidget(BECConnector, QWidget):
        def __init__(self, parent=None, client=None, **kwargs):
            super().__init__(parent=parent, client=client, **kwargs)
            self.setWindowTitle("My Widget")
            self._my_str_property = "default"

        @SafeProperty(str)
        def my_str_property(self) -> str:
            return self._my_str_property

        @my_str_property.setter
        def my_str_property(self, value: str):
            self._my_str_property = value

        @property
        def my_int_property(self) -> int:
            return 42

    widget = MyWidget(client=mocked_client)
    out = widget.export_settings()
    assert len(out) == 1
    assert out["my_str_property"] == "default"

    config = {"my_str_property": "new_value"}
    widget.load_settings(config)
    assert widget.my_str_property == "new_value"


def test_bec_connector_terminate_registration_no_qapp_instance(qtbot):
    """Constructing a BECConnector without a QApplication (possible for QObject-only
    connectors) must not raise, and must leave nothing registered: there is no
    aboutToQuit to wire, so the exit handler is not recorded either."""
    import bec_widgets.utils.bec_connector as m

    fresh_client = mock.MagicMock(name="fresh_client")
    assert fresh_client not in BECConnector.EXIT_HANDLERS
    try:
        with mock.patch.object(m.QApplication, "instance", return_value=None):
            BECConnectorQObject(client=fresh_client)  # must not raise
        assert fresh_client not in BECConnector.EXIT_HANDLERS
    finally:
        BECConnector.EXIT_HANDLERS.pop(fresh_client, None)


def test_bec_connector_terminate_registered_once_qapp_exists(qtbot):
    """A connector created without a QApplication must not block the registration of a
    later connector for the same client: once an application exists, teardown is wired."""
    import bec_widgets.utils.bec_connector as m

    fresh_client = mock.MagicMock(name="late_app_client")
    try:
        with mock.patch.object(m.QApplication, "instance", return_value=None):
            BECConnectorQObject(client=fresh_client)

        # now an application exists (qtbot guarantees one) -> handler gets wired
        BECConnectorQObject(client=fresh_client)
        assert fresh_client in BECConnector.EXIT_HANDLERS

        fresh_client.shutdown.reset_mock()
        QApplication.instance().aboutToQuit.emit()
        assert fresh_client.shutdown.called, "client teardown must run on aboutToQuit"
    finally:
        handler = BECConnector.EXIT_HANDLERS.pop(fresh_client, None)
        if handler is not None:
            QApplication.instance().aboutToQuit.disconnect(handler)


def test_bec_connector_submit_task_failure_removes_worker(bec_connector, qtbot):
    """A task that raises must not leak the worker
    reference, must emit failed, and must not call on_complete."""
    import threading

    failures = []
    completed = []
    # the worker starts before submit_task returns, so the raise is gated until the
    # failed connection below exists - otherwise this test races its own setup
    connected = threading.Event()

    def boom():
        connected.wait(timeout=5)
        raise RuntimeError("task failed on purpose")

    worker = bec_connector.submit_task(boom, on_complete=lambda: completed.append(True))
    worker.signals.failed.connect(lambda msg: failures.append(msg))
    connected.set()

    qtbot.waitUntil(lambda: worker not in bec_connector._workers, timeout=5000)
    qtbot.waitUntil(lambda: len(failures) == 1, timeout=5000)
    assert completed == []
    assert "task failed on purpose" in failures[0]


def test_bec_connector_parent_id_returns_none_on_error(bec_connector):
    """parent_id must swallow only Exception and
    return None explicitly."""
    with mock.patch.object(
        bec_connector, "_get_rpc_parent_ancestor", side_effect=ValueError("broken hierarchy")
    ):
        assert bec_connector.parent_id is None


def test_bec_connector_worker_completion_does_not_retain_owner(qtbot, mocked_client):
    """The worker-discard closure is held strongly
    by the Qt signal connection and captures the owner; without disconnecting
    itself it forms a C++-anchored reference cycle that keeps the owner (and
    widget) alive forever."""
    import gc
    import weakref

    connector = _CleanupBroadcastWidget(client=mocked_client)
    connector.submit_task(lambda: None)
    qtbot.waitUntil(lambda: not connector._workers, timeout=5000)

    ref = weakref.ref(connector)
    connector.close()
    connector.deleteLater()
    qtbot.wait(20)
    del connector
    for _ in range(3):
        gc.collect()

    assert ref() is None, "connector kept alive by worker completion closure"


def test_bec_connector_on_failed_never_misses_fast_failures(bec_connector, qtbot):
    """``on_failed`` passed to submit_task is connected before the worker starts, so
    even a task that raises immediately cannot emit ``failed`` before the connection
    exists. Connecting to ``worker.signals.failed`` after submit_task returns cannot
    give this guarantee."""
    failures = []

    def boom():
        raise RuntimeError("instant failure")

    for _ in range(20):
        bec_connector.submit_task(boom, on_failed=lambda msg: failures.append(msg))

    qtbot.waitUntil(lambda: len(failures) == 20, timeout=5000)
    qtbot.waitUntil(lambda: not bec_connector._workers, timeout=5000)
    assert all("instant failure" in msg for msg in failures)


def test_bec_connector_worker_outcome_survives_deleted_signal_source(bec_connector, qtbot, capfd):
    """At application shutdown the WorkerSignals C++ object can die before a late worker
    finishes; the outcome emit must not escape Worker.run into the thread pool."""
    import threading

    import shiboken6

    gate = threading.Event()
    worker = bec_connector.submit_task(lambda: gate.wait(timeout=5))
    shiboken6.delete(worker.signals)
    gate.set()

    qtbot.wait(300)  # let the worker finish and attempt both emits
    stderr = capfd.readouterr().err
    assert "Error calling Python override of QRunnable::run()" not in stderr
    # the discard connection died with the signal source; drop the worker manually
    if worker in bec_connector._workers:
        bec_connector._workers.remove(worker)
