# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import time

import pytest
from qtpy.QtWidgets import QApplication

from bec_widgets.utils import BECConnector
from bec_widgets.utils.error_popups import SafeSlot as Slot

from .client_mocks import mocked_client


@pytest.fixture
def bec_connector(mocked_client):
    connector = BECConnector(client=mocked_client)
    return connector


def test_bec_connector_init(bec_connector):
    assert bec_connector is not None
    assert bec_connector.client is not None
    assert isinstance(bec_connector, BECConnector)
    assert bec_connector.config.widget_class == "BECConnector"


def test_bec_connector_init_with_gui_id(mocked_client):
    bc = BECConnector(client=mocked_client, gui_id="test_gui_id")
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
