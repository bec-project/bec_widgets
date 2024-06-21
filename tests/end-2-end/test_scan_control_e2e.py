import time

import pytest

from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.scan_control import ScanControl


@pytest.fixture(scope="function")
def scan_control(qtbot, bec_client_lib):  # , mock_dev):
    widget = ScanControl(client=bec_client_lib)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_scan_control_populate_scans_e2e(scan_control):
    expected_scans = [
        "grid_scan",
        "fermat_scan",
        "round_scan",
        "cont_line_scan",
        "cont_line_fly_scan",
        "round_scan_fly",
        "round_roi_scan",
        "time_scan",
        "monitor_scan",
        "acquire",
        "line_scan",
    ]
    items = [
        scan_control.comboBox_scan_selection.itemText(i)
        for i in range(scan_control.comboBox_scan_selection.count())
    ]
    assert scan_control.comboBox_scan_selection.count() == len(expected_scans)
    assert sorted(items) == sorted(expected_scans)


def test_run_line_scan_with_parameters_e2e(scan_control, bec_client_lib, qtbot):
    client = bec_client_lib
    queue = client.queue

    scan_name = "line_scan"
    kwargs = {"exp_time": 0.01, "steps": 10, "relative": True, "burst_at_each_point": 1}
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

    # Run the scan
    scan_control.button_run_scan.click()
    time.sleep(2)

    last_scan = queue.scan_storage.storage[-1]
    assert last_scan.status_message.info["scan_name"] == scan_name
    assert last_scan.status_message.info["exp_time"] == kwargs["exp_time"]
    assert last_scan.status_message.info["scan_motors"] == [args["device"]]
    assert last_scan.status_message.info["num_points"] == kwargs["steps"]
