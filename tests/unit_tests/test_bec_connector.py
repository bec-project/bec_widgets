# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import gc
import time
from functools import partial
from multiprocessing import Process
from unittest.mock import MagicMock, call, patch

import pytest
from PySide6.QtWidgets import QWidget
from qtpy.QtCore import QObject
from qtpy.QtWidgets import QApplication

from bec_widgets.utils import BECConnector
from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot as Slot

from .client_mocks import mocked_client


class BECConnectorQObject(BECConnector, QObject): ...


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


def test_bec_connector_terminate_run_on_about_to_quit(qtbot, bec_connector):
    assert BECConnector.EXIT_HANDLERS.get(0) is not None
    terminate_mock = MagicMock()
    bec_connector.__class__.EXIT_HANDLERS[0] = terminate_mock
    bec_connector._run_exit_handlers()
    qtbot.waitUntil(lambda: terminate_mock.call_count == 1)


def test_bec_connector_terminate_run_once_and_only_once(qtbot, bec_connector):
    terminate_mock = MagicMock()
    bec_connector.__class__.EXIT_HANDLERS[0] = terminate_mock
    _conn_2 = BECConnectorQObject(client=mocked_client)
    _conn_3 = BECConnectorQObject(client=mocked_client)
    bec_connector._run_exit_handlers()
    qtbot.waitUntil(lambda: terminate_mock.call_count == 1)


def test_bec_connector_exit_handlers_run_in_order(qtbot, bec_connector):
    handler = MagicMock()
    bec_connector.__class__.EXIT_HANDLERS[0] = handler

    def h1():
        handler(prio=1)

    def h2():
        handler(prio=2)

    def h3():
        handler(prio=3)

    bec_connector._add_exit_handler(h3, 5)
    bec_connector._add_exit_handler(h2, 10)
    bec_connector._add_exit_handler(h1, 15)
    bec_connector._run_exit_handlers()
    qtbot.waitUntil(lambda: handler.call_count == 4)
    handler.assert_has_calls([call(prio=1), call(prio=2), call(prio=3), call()])


@pytest.fixture
def mock_widget_with_exit_handlers(bec_connector, mocked_client):
    with patch.object(mocked_client, "connector", bec_connector):
        handler = MagicMock()
        bec_connector.__class__.EXIT_HANDLERS[0] = handler

        class DropWeakrefWidget(BECWidget, QWidget):
            def __init__(
                self,
                client=None,
                config: ConnectionConfig = None,
                gui_id: str | None = None,
                theme_update: bool = False,
                start_busy: bool = False,
                busy_text: str = "Loading…",
                **kwargs,
            ):
                super().__init__(
                    client, config, gui_id, theme_update, start_busy, busy_text, **kwargs
                )
                self.setup_on_exit()
                self.client.connector.add_exit_handler(self._on_exit_stored_ref, 5)
                self.client.connector.add_exit_handler(self.instance_on_exit, 7)

            def setup_on_exit(self):
                def _on_exit():
                    self.backgroundRole()  # access some Qt thing just to fail test if c++ object is deleted
                    handler("called by DropWeakrefWidget in stored reference to function")

                self._on_exit_stored_ref = _on_exit

            def instance_on_exit(self):
                self.backgroundRole()  # access some Qt thing just to fail test if c++ object is deleted
                handler("called by DropWeakrefWidget in instance method")

        widget = DropWeakrefWidget(client=mocked_client)
        return widget, handler


def test_connector_exit_handlers_doesnt_drop_when_widget_lives(
    qtbot, bec_connector, mock_widget_with_exit_handlers
):
    widget, handler = mock_widget_with_exit_handlers
    qtbot.addWidget(widget)

    def h1():
        handler(prio=1)

    bec_connector._add_exit_handler(h1, 15)

    bec_connector._run_exit_handlers()
    qtbot.waitUntil(lambda: handler.call_count == 4)
    handler.assert_has_calls(
        [
            call(prio=1),
            call("called by DropWeakrefWidget in instance method"),
            call("called by DropWeakrefWidget in stored reference to function"),
            call(),  # from root cleanup
        ]
    )


def test_connector_exit_handlers_drops_when_widget_dies(
    qtbot, bec_connector, mock_widget_with_exit_handlers
):
    widget, handler = mock_widget_with_exit_handlers
    qtbot.addWidget(widget)

    def h1():
        handler(prio=1)

    bec_connector._add_exit_handler(h1, 15)

    widget.deleteLater()
    qtbot.wait(100)
    QApplication.processEvents()
    del widget
    qtbot.wait(100)
    gc.collect()
    qtbot.wait(100)

    bec_connector._run_exit_handlers()
    qtbot.waitUntil(lambda: handler.call_count == 2)
    handler.assert_has_calls([call(prio=1), call()])
