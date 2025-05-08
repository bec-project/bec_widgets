# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import time

import pytest
from qtpy.QtCore import QObject
from qtpy.QtWidgets import QApplication

from bec_widgets.utils import BECConnector
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
