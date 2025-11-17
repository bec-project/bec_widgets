from unittest import mock

import pytest
from bec_lib.messages import ScanHistoryMessage, _StoredDataInfo
from qtpy import QtCore

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.widgets.services.scan_history_browser.components import (
    ScanHistoryDeviceViewer,
    ScanHistoryMetadataViewer,
    ScanHistoryView,
)
from bec_widgets.widgets.services.scan_history_browser.scan_history_browser import (
    ScanHistoryBrowser,
)


@pytest.fixture
def scan_history_msg():
    """Fixture to create a mock ScanHistoryMessage."""
    yield ScanHistoryMessage(
        scan_id="test_scan",
        dataset_number=1,
        scan_number=1,
        scan_name="Test Scan",
        file_path="/path/to/scan",
        start_time=1751957906.3310962,
        end_time=1751957907.3310962,  # 1s later
        exit_status="closed",
        num_points=10,
        request_inputs={"some_input": "value"},
        stored_data_info={
            "device2": {
                "device2_signal1": _StoredDataInfo(shape=(10,)),
                "device2_signal2": _StoredDataInfo(shape=(20,)),
                "device2_signal3": _StoredDataInfo(shape=(25,)),
            },
            "device3": {"device3_signal1": _StoredDataInfo(shape=(1,))},
        },
    )


@pytest.fixture
def scan_history_msg_2():
    """Fixture to create a second mock ScanHistoryMessage."""
    yield ScanHistoryMessage(
        scan_id="test_scan_2",
        dataset_number=2,
        scan_number=2,
        scan_name="Test Scan 2",
        file_path="/path/to/scan_2",
        start_time=1751957908.3310962,
        end_time=1751957909.3310962,  # 1s later
        exit_status="closed",
        num_points=5,
        request_inputs={"some_input": "new_value"},
        stored_data_info={
            "device0": {
                "device0_signal1": _StoredDataInfo(shape=(15,)),
                "device0_signal2": _StoredDataInfo(shape=(25,)),
                "device0_signal3": _StoredDataInfo(shape=(3,)),
                "device0_signal4": _StoredDataInfo(shape=(20,)),
            },
            "device2": {
                "device2_signal1": _StoredDataInfo(shape=(10,)),
                "device2_signal2": _StoredDataInfo(shape=(20,)),
                "device2_signal3": _StoredDataInfo(shape=(25,)),
                "device2_signal4": _StoredDataInfo(shape=(30,)),
            },
            "device1": {"device1_signal1": _StoredDataInfo(shape=(25,))},
        },
    )


@pytest.fixture
def scan_history_device_viewer(qtbot, mocked_client):
    widget = ScanHistoryDeviceViewer(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def scan_history_metadata_viewer(qtbot, mocked_client):
    widget = ScanHistoryMetadataViewer(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def scan_history_view(qtbot, mocked_client):
    widget = ScanHistoryView(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def scan_history_browser(qtbot, mocked_client):
    """Fixture to create a ScanHistoryBrowser widget."""
    widget = ScanHistoryBrowser(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_scan_history_device_viewer_receive_msg(
    qtbot, scan_history_device_viewer, scan_history_msg, scan_history_msg_2
):
    """Test updating devices from scan history."""
    # Update with first scan history message
    assert scan_history_device_viewer.scan_history_msg is None
    assert scan_history_device_viewer.signal_model.signals == []
    assert scan_history_device_viewer.signal_model.rowCount() == 0
    scan_history_device_viewer.update_devices_from_scan_history(
        scan_history_msg.content, scan_history_msg.metadata
    )
    assert scan_history_device_viewer.scan_history_msg == scan_history_msg
    assert scan_history_device_viewer.device_combo.currentText() == "device2"
    assert scan_history_device_viewer.signal_model.signals == [
        ("device2_signal3", _StoredDataInfo(shape=(25,))),
        ("device2_signal2", _StoredDataInfo(shape=(20,))),
        ("device2_signal1", _StoredDataInfo(shape=(10,))),
    ]
    current_index = scan_history_device_viewer.signal_combo.currentIndex()
    assert current_index == 0
    signal_name = scan_history_device_viewer.signal_combo.model().data(
        scan_history_device_viewer.signal_combo.model().index(current_index, 0), QtCore.Qt.UserRole
    )
    assert signal_name == "device2_signal3"

    ## Update of second message should not change the device if still available
    new_msg = scan_history_msg_2
    scan_history_device_viewer.update_devices_from_scan_history(new_msg.content, new_msg.metadata)
    assert scan_history_device_viewer.scan_history_msg == new_msg
    assert scan_history_device_viewer.signal_model.signals == [
        ("device2_signal4", _StoredDataInfo(shape=(30,))),
        ("device2_signal3", _StoredDataInfo(shape=(25,))),
        ("device2_signal2", _StoredDataInfo(shape=(20,))),
        ("device2_signal1", _StoredDataInfo(shape=(10,))),
    ]
    assert scan_history_device_viewer.device_combo.currentText() == "device2"
    current_index = scan_history_device_viewer.signal_combo.currentIndex()
    assert current_index == 1
    signal_name = scan_history_device_viewer.signal_combo.model().data(
        scan_history_device_viewer.signal_combo.model().index(current_index, 0), QtCore.Qt.UserRole
    )
    assert signal_name == "device2_signal3"


def test_scan_history_device_viewer_clear_view(qtbot, scan_history_device_viewer, scan_history_msg):
    """Test clearing the device viewer."""
    scan_history_device_viewer.update_devices_from_scan_history(scan_history_msg.content)
    assert scan_history_device_viewer.scan_history_msg == scan_history_msg
    scan_history_device_viewer.clear_view()
    assert scan_history_device_viewer.scan_history_msg is None
    assert scan_history_device_viewer.device_combo.model().rowCount() == 0


def test_scan_history_device_viewer_on_request_plotting_clicked(
    qtbot, scan_history_device_viewer, scan_history_msg
):
    """Test the request plotting button click."""
    scan_history_device_viewer.update_devices_from_scan_history(scan_history_msg.content)

    plotting_callback_args = []

    def plotting_callback(device_name, signal_name, msg):
        """Callback to check if the request plotting signal is emitted."""
        plotting_callback_args.append((device_name, signal_name, msg))

    scan_history_device_viewer.request_history_plot.connect(plotting_callback)
    qtbot.mouseClick(scan_history_device_viewer.request_plotting_button, QtCore.Qt.LeftButton)
    qtbot.waitUntil(lambda: len(plotting_callback_args) > 0, timeout=5000)
    # scan_id
    assert plotting_callback_args[0][0] == scan_history_msg.scan_id
    # device_name
    assert plotting_callback_args[0][1] in scan_history_msg.stored_data_info.keys()
    # signal_name
    assert (
        plotting_callback_args[0][2]
        in scan_history_msg.stored_data_info[plotting_callback_args[0][1]].keys()
    )


def test_scan_history_metadata_viewer_receive_msg(
    qtbot, scan_history_metadata_viewer, scan_history_msg
):
    """Test the initialization of ScanHistoryMetadataViewer."""
    assert scan_history_metadata_viewer.scan_history_msg is None
    assert scan_history_metadata_viewer.title() == "No Scan Selected"
    scan_history_metadata_viewer.update_view(scan_history_msg.content)
    assert scan_history_metadata_viewer.scan_history_msg == scan_history_msg
    assert scan_history_metadata_viewer.title() == f"Metadata - Scan {scan_history_msg.scan_number}"
    for row, k in enumerate(scan_history_metadata_viewer._scan_history_msg_labels.keys()):
        if k == "elapsed_time":
            scan_history_metadata_viewer.layout().itemAtPosition(row, 1).widget().text() == "1.000s"
        if k == "scan_name":
            scan_history_metadata_viewer.layout().itemAtPosition(
                row, 1
            ).widget().text() == "Test Scan"


def test_scan_history_metadata_viewer_clear_view(
    qtbot, scan_history_metadata_viewer, scan_history_msg
):
    """Test clearing the metadata viewer."""
    scan_history_metadata_viewer.update_view(scan_history_msg.content)
    assert scan_history_metadata_viewer.scan_history_msg == scan_history_msg
    scan_history_metadata_viewer.clear_view()
    assert scan_history_metadata_viewer.scan_history_msg is None
    assert scan_history_metadata_viewer.title() == "No Scan Selected"


def test_scan_history_view(qtbot, scan_history_view, scan_history_msg):
    """Test the initialization of ScanHistoryView."""
    assert scan_history_view.scan_history == []
    assert scan_history_view.topLevelItemCount() == 0
    header = scan_history_view.headerItem()
    assert [header.text(i) for i in range(header.columnCount())] == [
        "Scan Nr",
        "Scan Name",
        "Status",
    ]


def test_scan_history_view_add_remove_scan(qtbot, scan_history_view, scan_history_msg):
    """Test adding a scan to the ScanHistoryView."""
    scan_history_view.update_history(scan_history_msg.model_dump())
    assert len(scan_history_view.scan_history) == 1
    assert scan_history_view.scan_history[0] == scan_history_msg
    assert scan_history_view.topLevelItemCount() == 1
    tree_item = scan_history_view.topLevelItem(0)
    tree_item.text(0) == str(scan_history_msg.scan_number)
    tree_item.text(1) == scan_history_msg.scan_name
    tree_item.text(2) == ""

    # remove scan
    def remove_callback(msg):
        """Callback to check if the no_scan_selected signal is emitted."""
        assert msg == scan_history_msg

    scan_history_view.remove_scan(0)
    assert len(scan_history_view.scan_history) == 0
    assert scan_history_view.topLevelItemCount() == 0


def test_scan_history_view_current_scan_item_changed(
    qtbot, scan_history_view, scan_history_msg, scan_history_device_viewer
):
    """Test the current scan item changed signal."""
    scan_history_view.update_history(scan_history_msg.model_dump())
    scan_history_msg.scan_id = "test_scan_2"
    scan_history_view.update_history(scan_history_msg.model_dump())
    scan_history_msg.scan_id = "test_scan_3"
    scan_history_view.update_history(scan_history_msg.model_dump())
    assert len(scan_history_view.scan_history) == 3

    def scan_selected_callback(msg):
        """Callback to check if the scan_selected signal is emitted."""
        return msg == scan_history_msg

    scan_history_view.scan_selected.connect(scan_selected_callback)

    qtbot.mouseClick(
        scan_history_view.viewport(),
        QtCore.Qt.LeftButton,
        pos=scan_history_view.visualItemRect(scan_history_view.topLevelItem(0)).center(),
    )


def test_scan_history_view_refresh(qtbot, scan_history_view, scan_history_msg, scan_history_msg_2):
    """Test the refresh method of ScanHistoryView."""
    scan_history_view.update_history(scan_history_msg.model_dump())
    scan_history_view.update_history(scan_history_msg_2.model_dump())
    assert len(scan_history_view.scan_history) == 2
    with mock.patch.object(
        scan_history_view.bec_scan_history_manager, "refresh_scan_history"
    ) as mock_refresh:
        scan_history_view.refresh()
        mock_refresh.assert_called_once()
        assert len(scan_history_view.scan_history) == 0
        assert scan_history_view.topLevelItemCount() == 0


def test_scan_history_update_full_history(
    qtbot, scan_history_view, scan_history_msg, scan_history_msg_2
):
    """Test the update_full_history method of ScanHistoryView."""
    # Wait spinner should be visible
    scan_history_view.update_full_history(
        [scan_history_msg.model_dump(), scan_history_msg_2.model_dump()]
    )
    assert len(scan_history_view.scan_history) == 2
    assert scan_history_view.topLevelItemCount() == 2
    assert scan_history_view.scan_history[0] == scan_history_msg_2  # new first item
    assert scan_history_view.scan_history[1] == scan_history_msg  # old second item
    # Wait spinner should be hidden
    assert scan_history_view._overlay_widget.isVisible() is False
    assert scan_history_view._spinner.isVisible() is False


def test_scan_history_browser(qtbot, scan_history_browser, scan_history_msg, scan_history_msg_2):
    """Test the initialization of ScanHistoryBrowser."""
    assert isinstance(scan_history_browser.scan_history_view, ScanHistoryView)
    assert isinstance(scan_history_browser.scan_history_metadata_viewer, ScanHistoryMetadataViewer)
    assert isinstance(scan_history_browser.scan_history_device_viewer, ScanHistoryDeviceViewer)

    # Add 2 scans to the history browser, new item will be added to the top
    scan_history_browser.scan_history_view.update_history(scan_history_msg.model_dump())
    scan_history_browser.scan_history_view.update_history(scan_history_msg_2.model_dump())

    assert len(scan_history_browser.scan_history_view.scan_history) == 2
    assert scan_history_browser.scan_history_view.topLevelItemCount() == 2
    # Click on first scan item history to select it
    # TODO #771 ; Multiple clicks to the QTreeView item fail, but only in the CI, not locally.
    # Simulate a mouse click without qtbot.mouseClick as this is unstable and currently fails in CI
    item = scan_history_browser.scan_history_view.topLevelItem(0)
    scan_history_browser.scan_history_view.setCurrentItem(item)
    scan_history_browser.scan_history_view.itemClicked.emit(item, 0)

    assert scan_history_browser.scan_history_view.currentIndex().row() == 0

    # Both metadata and device viewers should be updated with the first scan
    qtbot.waitUntil(
        lambda: scan_history_browser.scan_history_metadata_viewer.scan_history_msg
        == scan_history_msg_2,
        timeout=2000,
    )
    qtbot.waitUntil(
        lambda: scan_history_browser.scan_history_device_viewer.scan_history_msg
        == scan_history_msg_2,
        timeout=2000,
    )

    callback_args = []

    def plotting_callback(device_name, signal_name, msg):
        """Callback to check if the request plotting signal is emitted."""
        # device_name should be the first device
        callback_args.append((device_name, signal_name, msg))

    scan_history_browser.scan_history_device_viewer.request_history_plot.connect(plotting_callback)
    # Test emit plotting request
    qtbot.mouseClick(
        scan_history_browser.scan_history_device_viewer.request_plotting_button,
        QtCore.Qt.LeftButton,
    )
    qtbot.waitUntil(lambda: len(callback_args) > 0, timeout=5000)
    assert callback_args[0][0] == scan_history_msg_2.scan_id
    device_name = callback_args[0][1]
    signal_name = callback_args[0][2]
    assert device_name in scan_history_msg_2.stored_data_info.keys()
    assert signal_name in scan_history_msg_2.stored_data_info[device_name].keys()

    # Test clearing the view, removing both scans
    scan_history_browser.scan_history_view.remove_scan(-1)
    scan_history_browser.scan_history_view.remove_scan(-1)

    assert len(scan_history_browser.scan_history_view.scan_history) == 0
    assert scan_history_browser.scan_history_view.topLevelItemCount() == 0

    qtbot.waitUntil(
        lambda: scan_history_browser.scan_history_metadata_viewer.scan_history_msg is None,
        timeout=2000,
    )
    qtbot.waitUntil(
        lambda: scan_history_browser.scan_history_device_viewer.scan_history_msg is None,
        timeout=2000,
    )
