import time

import pytest

try:
    from bec_testing_plugin.scans.metadata_schema.custom_test_scan_schema import CustomScanSchema
except ImportError:
    pytest.skip(reason="Requires plugin repo!", allow_module_level=True)

from qtpy.QtWidgets import QGridLayout

from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.control.scan_control import ScanControl


@pytest.fixture(scope="function")
def scan_control(qtbot, bec_client_lib):  # , mock_dev):
    widget = ScanControl(client=bec_client_lib)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.mark.parametrize(
    ["md", "valid"],
    [
        ({"treatment_description": "soaking", "treatment_temperature_k": 123}, True),
        ({"treatment_description": "soaking", "treatment_temperature_k": "wrong type"}, False),
        ({"treatment_description": "soaking", "wrong key": 123}, False),
        (
            {
                "sample_name": "test sample",
                "treatment_description": "soaking",
                "treatment_temperature_k": 123,
            },
            True,
        ),
    ],
)
def test_scan_metadata_for_custom_scan(
    scan_control: ScanControl, bec_client_lib, qtbot, md: dict, valid: bool
):
    client = bec_client_lib
    queue = client.queue

    scan_name = "custom_testing_scan"
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

    assert scan_control._metadata_form._md_schema == CustomScanSchema
    assert not scan_control.button_run_scan.isEnabled()

    def do_test():
        # Set the metadata
        grid: QGridLayout = scan_control._metadata_form._form_grid.layout()
        for i in range(grid.rowCount() - 1):  # type: ignore
            field_name = grid.itemAtPosition(i, 0).widget().property("_model_field_name")
            if (value_to_set := md.pop(field_name, None)) is not None:
                grid.itemAtPosition(i, 1).widget().setValue(value_to_set)
        # all values should be used
        assert md == {}
        assert scan_control.button_run_scan.isEnabled()

        # Run the scan
        scan_control.button_run_scan.click()
        time.sleep(2)

        last_scan = queue.scan_storage.storage[-1]
        assert last_scan.status_message.info["scan_name"] == scan_name
        assert last_scan.status_message.info["exp_time"] == kwargs["exp_time"]
        assert last_scan.status_message.info["num_points"] == kwargs["steps"]

    if valid:
        do_test()
    else:
        with pytest.raises(Exception):
            do_test()
