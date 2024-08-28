# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
from unittest.mock import MagicMock

import pytest
from bec_lib.messages import AvailableResourceMessage

from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.scan_control import ScanControl

from .client_mocks import mocked_client

available_scans_message = AvailableResourceMessage(
    resource={
        "line_scan": {
            "class": "LineScan",
            "base_class": "ScanBase",
            "arg_input": {"device": "device", "start": "float", "stop": "float"},
            "gui_config": {
                "scan_class_name": "LineScan",
                "arg_group": {
                    "name": "Scan Arguments",
                    "bundle": 3,
                    "arg_inputs": {"device": "device", "start": "float", "stop": "float"},
                    "inputs": [
                        {
                            "arg": True,
                            "name": "device",
                            "type": "device",
                            "display_name": "Device",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                        {
                            "arg": True,
                            "name": "start",
                            "type": "float",
                            "display_name": "Start",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                        {
                            "arg": True,
                            "name": "stop",
                            "type": "float",
                            "display_name": "Stop",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                    ],
                    "min": 1,
                    "max": None,
                },
                "kwarg_groups": [
                    {
                        "name": "Movement Parameters",
                        "inputs": [
                            {
                                "arg": False,
                                "name": "steps",
                                "type": "int",
                                "display_name": "Steps",
                                "tooltip": "Number of steps",
                                "default": None,
                                "expert": False,
                            },
                            {
                                "arg": False,
                                "name": "relative",
                                "type": "bool",
                                "display_name": "Relative",
                                "tooltip": "If True, the start and end positions are relative to the current position",
                                "default": False,
                                "expert": False,
                            },
                        ],
                    },
                    {
                        "name": "Acquisition Parameters",
                        "inputs": [
                            {
                                "arg": False,
                                "name": "exp_time",
                                "type": "float",
                                "display_name": "Exp Time",
                                "tooltip": "Exposure time in s",
                                "default": 0,
                                "expert": False,
                            },
                            {
                                "arg": False,
                                "name": "burst_at_each_point",
                                "type": "int",
                                "display_name": "Burst At Each Point",
                                "tooltip": "Number of acquisition per point",
                                "default": 1,
                                "expert": False,
                            },
                        ],
                    },
                ],
            },
            "required_kwargs": ["steps", "relative"],
            "arg_bundle_size": {"bundle": 3, "min": 1, "max": None},
        },
        "grid_scan": {
            "class": "Scan",
            "base_class": "ScanBase",
            "arg_input": {"device": "device", "start": "float", "stop": "float", "steps": "int"},
            "gui_config": {
                "scan_class_name": "Scan",
                "arg_group": {
                    "name": "Scan Arguments",
                    "bundle": 4,
                    "arg_inputs": {
                        "device": "device",
                        "start": "float",
                        "stop": "float",
                        "steps": "int",
                    },
                    "inputs": [
                        {
                            "arg": True,
                            "name": "device",
                            "type": "device",
                            "display_name": "Device",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                        {
                            "arg": True,
                            "name": "start",
                            "type": "float",
                            "display_name": "Start",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                        {
                            "arg": True,
                            "name": "stop",
                            "type": "float",
                            "display_name": "Stop",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                        {
                            "arg": True,
                            "name": "steps",
                            "type": "int",
                            "display_name": "Steps",
                            "tooltip": None,
                            "default": None,
                            "expert": False,
                        },
                    ],
                    "min": 2,
                    "max": None,
                },
                "kwarg_groups": [
                    {
                        "name": "Scan Parameters",
                        "inputs": [
                            {
                                "arg": False,
                                "name": "exp_time",
                                "type": "float",
                                "display_name": "Exp Time",
                                "tooltip": "Exposure time in seconds",
                                "default": 0,
                                "expert": False,
                            },
                            {
                                "arg": False,
                                "name": "settling_time",
                                "type": "float",
                                "display_name": "Settling Time",
                                "tooltip": "Settling time in seconds",
                                "default": 0,
                                "expert": False,
                            },
                            {
                                "arg": False,
                                "name": "burst_at_each_point",
                                "type": "int",
                                "display_name": "Burst At Each Point",
                                "tooltip": "Number of exposures at each point",
                                "default": 1,
                                "expert": False,
                            },
                            {
                                "arg": False,
                                "name": "relative",
                                "type": "bool",
                                "display_name": "Relative",
                                "tooltip": "If True, the motors will be moved relative to their current position",
                                "default": False,
                                "expert": False,
                            },
                        ],
                    }
                ],
            },
            "required_kwargs": ["relative"],
            "arg_bundle_size": {"bundle": 4, "min": 2, "max": None},
        },
        "not_supported_scan_class": {"base_class": "NotSupportedScanClass"},
    }
)


@pytest.fixture(scope="function")
def scan_control(qtbot, mocked_client):  # , mock_dev):
    mocked_client.connector.set("scans/available_scans", available_scans_message)
    widget = ScanControl(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_populate_scans(scan_control, mocked_client):
    expected_scans = ["line_scan", "grid_scan"]
    items = [
        scan_control.comboBox_scan_selection.itemText(i)
        for i in range(scan_control.comboBox_scan_selection.count())
    ]

    assert scan_control.comboBox_scan_selection.count() == 2
    assert sorted(items) == sorted(expected_scans)


def test_current_scan(scan_control, mocked_client):
    current_scan = scan_control.current_scan
    wrong_scan = "error_scan"
    scan_control.current_scan = wrong_scan
    assert scan_control.current_scan == current_scan
    new_scan = "grid_scan" if current_scan == "line_scan" else "line_scan"
    scan_control.current_scan = new_scan
    assert scan_control.current_scan == new_scan


@pytest.mark.parametrize("scan_name", ["line_scan", "grid_scan"])
def test_on_scan_selected(scan_control, scan_name):
    expected_scan_info = available_scans_message.resource[scan_name]
    scan_control.comboBox_scan_selection.setCurrentText(scan_name)

    # Check arg_box labels and widgets
    for index, (arg_key, arg_value) in enumerate(expected_scan_info["arg_input"].items()):
        label = scan_control.arg_box.layout.itemAtPosition(0, index).widget()
        assert label.text().lower() == arg_key

        for row in range(1, expected_scan_info["arg_bundle_size"]["min"] + 1):
            widget = scan_control.arg_box.layout.itemAtPosition(row, index).widget()
            assert widget is not None  # Confirm that a widget exists
            expected_widget_type = scan_control.arg_box.WIDGET_HANDLER.get(arg_value, None)
            assert isinstance(widget, expected_widget_type)  # Confirm the widget type matches

    # Check kwargs boxes
    kwargs_group = [param for param in expected_scan_info["gui_config"]["kwarg_groups"]]
    print(kwargs_group)

    for kwarg_box, kwarg_group in zip(scan_control.kwarg_boxes, kwargs_group):
        assert kwarg_box.title() == kwarg_group["name"]
        for index, kwarg_info in enumerate(kwarg_group["inputs"]):
            label = kwarg_box.layout.itemAtPosition(0, index).widget()
            assert label.text() == kwarg_info["display_name"]
            widget = kwarg_box.layout.itemAtPosition(1, index).widget()
            expected_widget_type = kwarg_box.WIDGET_HANDLER.get(kwarg_info["type"], None)
            assert isinstance(widget, expected_widget_type)


@pytest.mark.parametrize("scan_name", ["line_scan", "grid_scan"])
def test_add_remove_bundle(scan_control, scan_name, qtbot):
    expected_scan_info = available_scans_message.resource[scan_name]
    scan_control.comboBox_scan_selection.setCurrentText(scan_name)

    # Initial number of args row
    initial_num_of_rows = scan_control.arg_box.count_arg_rows()

    assert initial_num_of_rows == expected_scan_info["arg_bundle_size"]["min"]

    scan_control.button_add_bundle.click()
    scan_control.button_add_bundle.click()

    if expected_scan_info["arg_bundle_size"]["max"] is None:
        assert scan_control.arg_box.count_arg_rows() == initial_num_of_rows + 2

    # Remove one bundle
    scan_control.button_remove_bundle.click()
    qtbot.wait(200)

    assert scan_control.arg_box.count_arg_rows() == initial_num_of_rows + 1


def test_run_line_scan_with_parameters(scan_control, mocked_client):
    scan_name = "line_scan"
    kwargs = {"exp_time": 0.1, "steps": 10, "relative": True, "burst_at_each_point": 1}
    args = {"device": "samx", "start": -5, "stop": 5}

    scan_control.comboBox_scan_selection.setCurrentText(scan_name)

    # Set kwargs in the UI
    for kwarg_box in scan_control.kwarg_boxes:
        for widget in kwarg_box.widgets:
            for key, value in kwargs.items():
                if widget.arg_name == key:
                    WidgetIO.set_value(widget, value)
                    break
    # Set args in the UI
    for widget in scan_control.arg_box.widgets:
        for key, value in args.items():
            if widget.arg_name == key:
                WidgetIO.set_value(widget, value)
                break

    # Mock the scan function
    mocked_scan_function = MagicMock()
    setattr(mocked_client.scans, scan_name, mocked_scan_function)

    # Run the scan
    scan_control.button_run_scan.click()

    # Retrieve the actual arguments passed to the mock
    called_args, called_kwargs = mocked_scan_function.call_args

    # Check if the scan function was called correctly
    expected_device = mocked_client.device_manager.devices.samx
    expected_args_list = [expected_device, args["start"], args["stop"]]
    assert called_args == tuple(expected_args_list)
    assert called_kwargs == kwargs
