# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
# pylint: disable=missing-function-docstring,redefined-outer-name,protected-access
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import Qt

from bec_widgets.widgets.control.scan_control.modern.form_core import FieldSpec, ScanFormSpec
from bec_widgets.widgets.control.scan_control.modern.scan_control_qml import ScanControlQml
from bec_widgets.widgets.control.scan_control.modern.scan_control_widgets import (
    DeviceEdit,
    NumberEdit,
    ScanControlModern,
)

from .test_scan_control import available_scans_message, scan_history


@pytest.fixture(params=[ScanControlQml, ScanControlModern], ids=["qml", "widgets"])
def control(request, qtbot, mocked_client):
    mocked_client.connector.set_and_publish(
        MessageEndpoints.available_scans(), available_scans_message
    )
    mocked_client.connector.xadd(
        topic=MessageEndpoints.scan_history(), msg_dict={"data": scan_history}
    )
    widget = request.param(client=mocked_client)
    qtbot.addWidget(widget)
    widget.resize(520, 720)
    widget.show()
    qtbot.waitExposed(widget)
    yield widget


def fill_devices(control, *devices):
    for row, device in enumerate(devices):
        control.form.set_arg_value(row, "device", device)


def test_lists_supported_scans_and_selects_first(control):
    assert sorted(control.visible_scans) == ["grid_scan", "line_scan"]
    assert control.current_scan in control.visible_scans


def test_grid_scan_starts_with_minimum_rows(control):
    control.current_scan = "grid_scan"
    assert len(control.form.arg_rows) == 2
    assert not control.form.can_remove_row()
    control.form.add_row()
    assert len(control.form.arg_rows) == 3
    control.form.remove_row(0)
    control.form.remove_row(0)
    assert len(control.form.arg_rows) == 2


def test_start_needs_valid_devices(control):
    control.current_scan = "line_scan"
    assert not control.can_start()
    assert control.problems()[0] == "Choose a device"
    control.form.set_arg_value(0, "device", "nope")
    assert control.problems()[0] == "Unknown device 'nope'"
    fill_devices(control, "samx")
    assert control.can_start()


def test_get_scan_parameters(control):
    control.current_scan = "line_scan"
    fill_devices(control, "samx")
    control.form.set_arg_value(0, "start", "-1.5")
    control.form.set_arg_value(0, "stop", 2)
    control.form.set_kwarg_value("steps", 12)
    args, kwargs = control.get_scan_parameters(bec_object=False)
    assert args == ["samx", -1.5, 2.0]
    assert kwargs["steps"] == 12
    assert kwargs["relative"] is False
    assert kwargs["metadata"]["scan_name"] == "line_scan"
    args, _ = control.get_scan_parameters()
    assert args[0] is control.dev.samx


def test_optional_literal_defaults_to_none(control):
    control.current_scan = "grid_scan"
    assert control.get_scan_parameters(False)[1]["optim_trajectory"] is None
    control.form.set_kwarg_value("optim_trajectory", "option2")
    assert control.get_scan_parameters(False)[1]["optim_trajectory"] == "option2"


def test_run_scan_submits_and_emits(control, qtbot):
    control.current_scan = "line_scan"
    fill_devices(control, "samx")
    scans = SimpleNamespace(line_scan=MagicMock())
    with patch.object(control, "scans", scans), qtbot.waitSignal(control.scan_started):
        control.run_scan()
    scans.line_scan.assert_called_once()
    assert scans.line_scan.call_args.args[0] is control.dev.samx


def test_run_scan_refuses_incomplete_form(control):
    control.current_scan = "line_scan"
    scans = SimpleNamespace(line_scan=MagicMock())
    with patch.object(control, "scans", scans):
        control.run_scan()
    scans.line_scan.assert_not_called()


def test_stop_aborts_then_halts(control):
    queue = MagicMock()
    with patch.object(control, "queue", queue):
        control.stop_scan()
        queue.request_scan_abortion.assert_called_once()
        assert control.stop_armed
        control.stop_scan()
        queue.request_scan_halt.assert_called_once()


def test_parameters_are_remembered_per_scan(control):
    control.current_scan = "line_scan"
    fill_devices(control, "samy")
    control.form.set_kwarg_value("exp_time", 0.25)
    control.current_scan = "grid_scan"
    assert control.form.kwargs["exp_time"] == 0.25  # shared keyword carries over
    control.current_scan = "line_scan"
    assert control.form.arg_rows[0]["device"] == "samy"


def test_restore_last_scan_parameters(control, qtbot):
    control.current_scan = "line_scan"
    control.request_last_executed_scan_parameters()
    qtbot.waitUntil(lambda: not control.is_restoring)
    args, kwargs = control.get_scan_parameters(bec_object=False)
    assert args == ["samx", 0.0, 2.0]
    assert kwargs["steps"] == 10


def test_device_selected_signal(control, qtbot):
    control.current_scan = "grid_scan"
    emitted = []
    control.device_selected.connect(emitted.append)
    fill_devices(control, "samx", "samy")
    assert emitted == ["samx", "samx samy"]


def test_allowed_scans_filter(control):
    control.allowed_scans = ["grid_scan"]
    assert control.visible_scans == ["grid_scan"]
    assert control.current_scan == "grid_scan"
    control.allowed_scans = []
    assert sorted(control.visible_scans) == ["grid_scan", "line_scan"]


def test_invalid_metadata_blocks_start(control):
    control.current_scan = "line_scan"
    fill_devices(control, "samx")
    control.metadata.set_extras([["sample_temp", "300"]])
    assert control.get_scan_parameters(False)[1]["metadata"]["sample_temp"] == "300"
    control.metadata.errors = {"comment": "broken"}
    assert "Metadata Comment: broken" in control.problems()


def test_hide_options(control):
    control.hide_scan_control_buttons = True
    control.hide_metadata = True
    assert control.hide_scan_control_buttons and control.hide_metadata
    control.show_scan_control_buttons(True)
    assert not control.hide_scan_control_buttons


def test_field_spec_limits_and_choices():
    spec = FieldSpec.from_input(
        {"name": "n", "type": "int", "gt": 0, "le": 10, "default": None, "display_name": "N"}
    )
    assert (spec.minimum, spec.maximum, spec.initial_value()) == (1, 10, 1)
    choice = FieldSpec.from_input({"name": "c", "type": {"Literal": ["b", "a", None]}})
    assert choice.choices == ["b", "a", ""]
    assert FieldSpec.from_input({"name": "x", "type": "complex"}) is None
    assert ScanFormSpec().kwarg_fields == []


# ---------------------------------------------------------------------- view specific


@pytest.fixture
def qml_control(qtbot, mocked_client):
    mocked_client.connector.set_and_publish(
        MessageEndpoints.available_scans(), available_scans_message
    )
    widget = ScanControlQml(client=mocked_client)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    yield widget


def test_qml_view_loads_and_bridge_writes_back(qml_control):
    assert qml_control.view.rootObject() is not None
    bridge = qml_control.bridge
    bridge.selectScan("grid_scan")
    assert bridge.currentScan == "grid_scan"
    assert bridge.rowCount == 2
    bridge.setArg(1, "device", "samz")
    assert bridge.argRows[1]["values"]["device"] == "samz"
    bridge.addRow()
    assert bridge.rowCount == 3
    bridge.setKwarg("exp_time", 0.5)
    assert bridge.kwargs["values"]["exp_time"] == 0.5
    assert "Row 1: Choose a device" in bridge.problems


@pytest.fixture
def widget_control(qtbot, mocked_client):
    mocked_client.connector.set_and_publish(
        MessageEndpoints.available_scans(), available_scans_message
    )
    widget = ScanControlModern(client=mocked_client)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    yield widget


def test_widget_view_edits_update_form(widget_control, qtbot):
    widget_control.current_scan = "line_scan"
    device = widget_control._arg_editors[0]["device"]
    assert isinstance(device, DeviceEdit)
    device.setEditText("samx")
    device.lineEdit().editingFinished.emit()
    assert widget_control.form.arg_rows[0]["device"] == "samx"
    start = widget_control._arg_editors[0]["start"]
    assert isinstance(start, NumberEdit)
    start.setText("3.25")
    start.editingFinished.emit()
    assert widget_control.form.arg_rows[0]["start"] == 3.25
    assert widget_control.start_button.isEnabled()
    widget_control.add_row_button.click()
    assert len(widget_control._arg_editors) == 2


def test_widget_view_rejects_unknown_scan_name(widget_control, qtbot):
    picker = widget_control.scan_picker
    picker.lineEdit().setText("no_such_scan")
    picker.lineEdit().editingFinished.emit()
    assert picker.currentText() == widget_control.current_scan


def test_widget_number_edit_steps_with_arrow_keys(widget_control, qtbot):
    widget_control.current_scan = "line_scan"
    steps = widget_control._kwarg_editors["steps"]
    steps.setFocus()
    qtbot.keyClick(steps, Qt.Key.Key_Up)
    assert widget_control.form.kwargs["steps"] == 1
