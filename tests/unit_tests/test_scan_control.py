# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
from unittest.mock import MagicMock

import pytest
from qtpy.QtWidgets import QLineEdit

from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets import ScanControl
from tests.unit_tests.test_msgs.available_scans_message import available_scans_message


class FakePositioner:
    """Fake minimal positioner class for testing."""

    def __init__(self, name, enabled=True):
        self.name = name
        self.enabled = enabled

    def __contains__(self, item):
        return item == self.name


def get_mocked_device(device_name):
    """Helper function to mock the devices"""
    if device_name == "samx":
        return FakePositioner(name="samx", enabled=True)


@pytest.fixture(scope="function")
def mocked_client():
    # Create a MagicMock object
    client = MagicMock()

    # Mock the producer.get method to return the packed message
    client.producer.get.return_value = available_scans_message

    # # Mock the device_manager.devices attribute to return a mock object for samx
    client.device_manager.devices = MagicMock()
    client.device_manager.devices.__contains__.side_effect = lambda x: x == "samx"
    client.device_manager.devices.samx = get_mocked_device("samx")

    return client


@pytest.fixture(scope="function")
def scan_control(qtbot, mocked_client):  # , mock_dev):
    widget = ScanControl(client=mocked_client)
    # widget.dev.samx = MagicMock()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_populate_scans(scan_control, mocked_client):
    # The comboBox should be populated with all scan from the message right after initialization
    expected_scans = available_scans_message.resource.keys()
    assert scan_control.comboBox_scan_selection.count() == len(expected_scans)
    for scan in expected_scans:  # Each scan should be in the comboBox
        assert scan_control.comboBox_scan_selection.findText(scan) != -1


@pytest.mark.parametrize(
    "scan_name", ["line_scan", "grid_scan"]
)  # TODO now only for line_scan and grid_scan, later for all loaded scans
def test_on_scan_selected(scan_control, scan_name):
    # Expected scan info from the message signature
    expected_scan_info = available_scans_message.resource[scan_name]

    # Select a scan from the comboBox
    scan_control.comboBox_scan_selection.setCurrentText(scan_name)

    # Check labels and widgets in args table
    for index, (arg_key, arg_value) in enumerate(expected_scan_info["arg_input"].items()):
        label = scan_control.args_table.horizontalHeaderItem(index)
        assert label.text().lower() == arg_key  # labes

        for row in range(expected_scan_info["arg_bundle_size"]["min"]):
            widget = scan_control.args_table.cellWidget(row, index)
            assert widget is not None  # Confirm that a widget exists
            expected_widget_type = scan_control.WIDGET_HANDLER.get(arg_value, None)
            assert isinstance(widget, expected_widget_type)  # Confirm the widget type matches

    # kwargs
    kwargs_from_signature = [
        param for param in expected_scan_info["signature"] if param["kind"] == "KEYWORD_ONLY"
    ]

    # Check labels and widgets in kwargs grid layout
    for index, kwarg_info in enumerate(kwargs_from_signature):
        label_widget = scan_control.kwargs_layout.itemAtPosition(1, index).widget()
        assert label_widget.text() == kwarg_info["name"].capitalize()
        widget = scan_control.kwargs_layout.itemAtPosition(2, index).widget()
        expected_widget_type = scan_control.WIDGET_HANDLER.get(kwarg_info["annotation"], QLineEdit)
        assert isinstance(widget, expected_widget_type)


@pytest.mark.parametrize("scan_name", ["line_scan", "grid_scan"])
def test_add_remove_bundle(scan_control, scan_name):
    # Expected scan info from the message signature
    expected_scan_info = available_scans_message.resource[scan_name]

    # Select a scan from the comboBox
    scan_control.comboBox_scan_selection.setCurrentText(scan_name)

    # Initial number of args row
    initial_num_of_rows = scan_control.args_table.rowCount()

    # Check initial row count of args table
    assert scan_control.args_table.rowCount() == expected_scan_info["arg_bundle_size"]["min"]

    # Try to remove default number of args row
    scan_control.pushButton_remove_bundle.click()
    assert scan_control.args_table.rowCount() == expected_scan_info["arg_bundle_size"]["min"]

    # Try to add two bundles
    scan_control.pushButton_add_bundle.click()
    scan_control.pushButton_add_bundle.click()

    # check the case where no max number of args are defined
    # TODO do check also for the case where max number of args are defined
    if expected_scan_info["arg_bundle_size"]["max"] is None:
        assert scan_control.args_table.rowCount() == initial_num_of_rows + 2

    # Remove one bundle
    scan_control.pushButton_remove_bundle.click()

    # check the case where no max number of args are defined
    if expected_scan_info["arg_bundle_size"]["max"] is None:
        assert scan_control.args_table.rowCount() == initial_num_of_rows + 1


def test_run_line_scan_with_parameters(scan_control, mocked_client):
    scan_name = "line_scan"
    kwargs = {"exp_time": 0.1, "steps": 10, "relative": True, "burst_at_each_point": 1}
    args = {"device": "samx", "start": -5, "stop": 5}

    # Select a scan from the comboBox
    scan_control.comboBox_scan_selection.setCurrentText(scan_name)

    # Set kwargs in the UI
    for label_index in range(
        scan_control.kwargs_layout.rowCount() + 1
    ):  # from some reason rowCount() returns 1 less than the actual number of rows
        label_item = scan_control.kwargs_layout.itemAtPosition(1, label_index)
        if label_item:
            label_widget = label_item.widget()
            kwarg_key = WidgetIO.get_value(label_widget).lower()
            if kwarg_key in kwargs:
                widget_item = scan_control.kwargs_layout.itemAtPosition(2, label_index)
                if widget_item:
                    widget = widget_item.widget()
                    WidgetIO.set_value(widget, kwargs[kwarg_key])

    # Set args in the UI
    for col_index in range(scan_control.args_table.columnCount()):
        header_item = scan_control.args_table.horizontalHeaderItem(col_index)
        if header_item:
            arg_key = header_item.text().lower()
            if arg_key in args:
                for row_index in range(scan_control.args_table.rowCount()):
                    widget = scan_control.args_table.cellWidget(row_index, col_index)
                    WidgetIO.set_value(widget, args[arg_key])

    # Mock the scan function
    mocked_scan_function = MagicMock()
    setattr(mocked_client.scans, scan_name, mocked_scan_function)

    # Run the scan
    scan_control.button_run_scan.click()

    # Retrieve the actual arguments passed to the mock
    called_args, called_kwargs = mocked_scan_function.call_args

    # Check if the scan function was called correctly
    expected_device = (
        mocked_client.device_manager.devices.samx
    )  # This is the FakePositioner instance
    expected_args_list = [expected_device, args["start"], args["stop"]]
    assert called_args == tuple(
        expected_args_list
    ), "The positional arguments passed to the scan function do not match expected values."
    assert (
        called_kwargs == kwargs
    ), "The keyword arguments passed to the scan function do not match expected values."
