"""Tests for the scan form model and the QML and QWidget ports of ScanControl."""

# pylint: disable=redefined-outer-name, protected-access, missing-function-docstring
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtQuickWidgets import QQuickWidget

from bec_widgets.widgets.control.scan_control.scan_control_qml import ScanControlQML
from bec_widgets.widgets.control.scan_control.scan_control_qwidget import ScanControlQWidget
from bec_widgets.widgets.control.scan_control.scan_control_ux_common import doc_summary
from bec_widgets.widgets.control.scan_control.scan_form_model import (
    ScanFormModel,
    field_type,
    literal_options,
)

from .conftest import create_widget
from .test_scan_control import available_scans_message, scan_history

GRID = available_scans_message.resource["grid_scan"]["gui_config"]
LINE = available_scans_message.resource["line_scan"]["gui_config"]
DEVICES = {"samx": SimpleNamespace(name="samx"), "samy": SimpleNamespace(name="samy")}


@pytest.fixture
def form():
    return ScanFormModel(lambda: sorted(DEVICES), DEVICES.__getitem__)


@pytest.fixture(params=[ScanControlQML, ScanControlQWidget])
def control(request, qtbot, mocked_client):
    mocked_client.connector.set_and_publish(
        MessageEndpoints.available_scans(), available_scans_message
    )
    mocked_client.connector.xadd(
        topic=MessageEndpoints.scan_history(), msg_dict={"data": scan_history}
    )
    widget = create_widget(qtbot, request.param, client=mocked_client)
    widget.resize(460, 640)
    yield widget


def _fill_line_scan(control, device="samx"):
    control.current_scan = "line_scan"
    control.set_field("args:0:device", device)
    control.set_field("args:0:start", "0")
    control.set_field("args:0:stop", "2.5")
    control.set_field("kwargs:steps", "10")


# ---- form model ------------------------------------------------------------------------


def test_field_types_and_literals():
    assert field_type("DeviceBase") == "device"
    assert field_type({"Literal": ("a", None)}) == "literal"
    assert field_type("whatever") == "str"
    assert literal_options({"Literal": ("a", None, "b", "a")}) == ["", "a", "b"]
    assert doc_summary("Run a scan.\n  More.\n\nArgs:\n  x") == "Run a scan. More."


def test_form_loads_minimum_rows_and_defaults(form):
    form.load(GRID)
    assert form.bundle_count == 2
    assert not form.can_remove_bundle()
    assert form.can_add_bundle()
    assert form.value("kwargs:exp_time") == "0"
    assert form.value("kwargs:relative") is False
    assert form.value("kwargs:optim_trajectory") == ""
    groups = form.groups()
    assert [group["kind"] for group in groups] == ["args", "kwargs"]
    assert len(groups[0]["rows"]) == 2
    assert groups[1]["fields"][4]["options"] == ["", "option1", "option2", "option3"]


def test_form_validation_messages(form):
    form.load(LINE)
    errors = form.errors()
    assert errors["args:0:device"] == "Select a device"
    assert errors["args:0:start"] == "Required"
    assert errors["kwargs:steps"] == "Required"
    form.set_value("args:0:device", "nope")
    form.set_value("args:0:start", "abc")
    form.set_value("kwargs:steps", "1.5")
    errors = form.errors()
    assert errors["args:0:device"] == "Unknown device 'nope'"
    assert errors["args:0:start"] == "Enter a number"
    assert errors["kwargs:steps"] == "Enter a whole number"


def test_form_numeric_limits(form):
    config = {
        "kwarg_groups": [
            {"name": "G", "inputs": [{"name": "n", "type": "int", "default": 1, "ge": 1}]}
        ]
    }
    form.load(config)
    form.set_value("kwargs:n", "0")
    assert form.errors() == {"kwargs:n": "Must be ≥ 1"}
    form.set_value("kwargs:n", "")
    assert form.is_valid()
    assert form.kwargs() == {"n": 1}


def test_form_args_kwargs_conversion(form):
    form.load(LINE)
    form.set_value("args:0:device", "samx")
    form.set_value("args:0:start", "0")
    form.set_value("args:0:stop", "2")
    form.set_value("kwargs:steps", "10")
    assert form.is_valid()
    assert form.args(bec_object=False) == ["samx", 0.0, 2.0]
    assert form.args()[0] is DEVICES["samx"]
    kwargs = form.kwargs()
    assert kwargs["steps"] == 10 and kwargs["relative"] is False and kwargs["exp_time"] == 0


def test_form_rows_add_remove_and_restore(form):
    form.load(LINE)
    assert form.add_bundle()
    form.set_value("args:1:device", "samy")
    assert form.selected_devices() == ["samy"]
    assert form.remove_bundle(0)
    assert form.bundle_count == 1
    assert form.value("args:0:device") == "samy"
    form.set_args(["samx", 0, 1, "samy", 2, 3])
    assert form.bundle_count == 2
    assert form.args(bec_object=False) == ["samx", 0.0, 1.0, "samy", 2.0, 3.0]
    form.set_kwargs({"steps": 5, "unknown": 1, "relative": True})
    assert form.value("kwargs:steps") == "5"
    assert form.value("kwargs:relative") is True


def test_form_device_selected_signal(form, qtbot):
    form.load(LINE)
    with qtbot.waitSignal(form.device_selected) as blocker:
        form.set_value("args:0:device", "samx")
    assert blocker.args == ["samx"]


def test_form_units_from_reference(form):
    config = {
        "arg_group": {
            "name": "A",
            "min": 1,
            "max": None,
            "inputs": [
                {"name": "device", "type": "device"},
                {"name": "start", "type": "float", "reference_units": "device"},
                {"name": "width", "type": "float", "units": "mm"},
            ],
        }
    }
    form.load(config)
    form.set_value("args:0:device", "samx")
    with patch(
        "bec_widgets.widgets.control.scan_control.scan_form_model.device_units", return_value="deg"
    ):
        fields = form.groups()[0]["rows"][0]
    assert fields[1]["units"] == "deg"
    assert fields[2]["units"] == "mm"


# ---- ports -----------------------------------------------------------------------------


def test_ports_populate_and_select(control):
    assert control.visible_scans() == ["line_scan", "grid_scan"]
    assert control.current_scan == "line_scan"
    control.current_scan = "GRID_SCAN"
    assert control.current_scan == "grid_scan"
    control.current_scan = "unknown"
    assert control.current_scan == "grid_scan"
    assert control.view_state()["summary"] == "Run a grid scan over one or more devices."


def test_ports_allowed_scans_filter(control):
    control.allowed_scans = ["grid_scan"]
    assert control.visible_scans() == ["grid_scan"]
    assert control.current_scan == "grid_scan"
    control.allowed_scans = []
    assert control.config.allowed_scans is None
    assert control.allowed_scans == ["line_scan", "grid_scan"]


def test_ports_errors_appear_after_edit_or_start(control):
    assert control.view_state()["errors"] == {}
    control.set_field("args:0:start", "x")
    assert control.view_state()["errors"] == {"args:0:start": "Enter a number"}
    scans = SimpleNamespace(line_scan=MagicMock())
    with patch.object(control, "scans", scans):
        control.run_scan()
    scans.line_scan.assert_not_called()
    state = control.view_state()
    assert "args:0:device" in state["errors"]
    assert state["hint"].endswith("need a value")


def test_ports_run_scan(control, qtbot):
    _fill_line_scan(control)
    scans = SimpleNamespace(line_scan=MagicMock())
    with (
        patch.object(control, "scans", scans),
        qtbot.waitSignal(control.scan_started),
        qtbot.waitSignal(control.scan_args) as args_signal,
    ):
        control.run_scan()
    args, kwargs = scans.line_scan.call_args
    assert args[0] is control.dev["samx"]
    assert args[1:] == (0.0, 2.5)
    assert kwargs["steps"] == 10
    assert "metadata" in kwargs
    assert args_signal.args[0][1:] == [0.0, 2.5]


def test_ports_device_selected_signal(control, qtbot):
    control.current_scan = "line_scan"
    with qtbot.waitSignal(control.device_selected) as blocker:
        control.set_field("args:0:device", "samx")
    assert blocker.args == ["samx"]


def test_ports_remember_parameters_per_scan(control):
    _fill_line_scan(control)
    control.current_scan = "grid_scan"
    control.current_scan = "line_scan"
    args, kwargs = control.get_scan_parameters(bec_object=False)
    assert args == ["samx", 0.0, 2.5]
    assert kwargs["steps"] == 10


def test_ports_restore_last_executed(control, qtbot):
    control.current_scan = "line_scan"
    control.request_last_executed_scan_parameters()
    qtbot.waitUntil(lambda: not control.view_state()["restoreBusy"], timeout=5000)
    qtbot.waitUntil(lambda: control.form.value("args:0:device") == "samx", timeout=5000)
    args, kwargs = control.get_scan_parameters(bec_object=False)
    assert args == ["samx", 0.0, 2.0]
    assert kwargs["steps"] == 10
    assert kwargs["exp_time"] == 2


def test_ports_stop_is_two_stage(control):
    queue = MagicMock()
    with patch.object(control, "queue", queue):
        control.stop_scan()
        queue.request_scan_abortion.assert_called_once()
        assert control.view_state()["stopLabel"] == "Emergency Stop"
        control.stop_scan()
        queue.request_scan_halt.assert_called_once()
    control._reset_emergency_stop()
    assert control.view_state()["stopLabel"] == "Stop"


def test_ports_hide_flags(control):
    for prop, key in [
        ("hide_arg_box", "showArgs"),
        ("hide_kwarg_boxes", "showKwargs"),
        ("hide_scan_control_buttons", "showButtons"),
        ("hide_metadata", "showMetadata"),
        ("hide_scan_selection_combobox", "showSelector"),
        ("hide_scan_selector_settings_button", "showFilter"),
        ("hide_add_remove_buttons", "showRowButtons"),
    ]:
        setattr(control, prop, True)
        assert getattr(control, prop)
        assert control.view_state()[key] is False
        setattr(control, prop, False)
        assert control.view_state()[key] is True


def test_ports_metadata_dialog(control):
    control.show_metadata_dialog()
    assert control._metadata_dialog.isVisible()
    assert control._metadata_form.parent() is control._metadata_dialog
    control._metadata_dialog.close()


def test_ports_export_properties(control):
    names = set(control._get_bec_meta_objects())
    assert {"current_scan", "allowed_scans", "hide_arg_box", "hide_metadata"} <= names


def test_qml_view_and_backend(qtbot, mocked_client):
    mocked_client.connector.set_and_publish(
        MessageEndpoints.available_scans(), available_scans_message
    )
    widget = create_widget(qtbot, ScanControlQML, client=mocked_client)
    assert widget.view.status() == QQuickWidget.Status.Ready
    assert widget.view.errors() == []
    backend = widget.backend
    assert [group["kind"] for group in backend.groups] == ["args", "kwargs", "kwargs"]
    assert "samx" in backend.devices
    backend.selectScan("grid_scan")
    assert backend.state["current"] == "grid_scan"
    backend.addRow()
    assert len(backend.groups[0]["rows"]) == 3
    backend.removeRow(0)
    assert len(backend.groups[0]["rows"]) == 2
    backend.setField("kwargs:exp_time", "x")
    assert backend.state["errors"] == {"kwargs:exp_time": "Enter a number"}


def test_qwidget_editors(qtbot, mocked_client):
    mocked_client.connector.set_and_publish(
        MessageEndpoints.available_scans(), available_scans_message
    )
    widget = create_widget(qtbot, ScanControlQWidget, client=mocked_client)
    widget.resize(460, 640)
    widget.show()
    qtbot.waitExposed(widget)
    editor = widget.editors["args:0:start"]
    editor.editor.setText("abc")
    editor.editor.textEdited.emit("abc")
    assert editor.error.text() == "Enter a number"
    assert editor.editor.property("invalid")
    widget.editors["args:0:device"].editor.setCurrentText("samx")
    assert widget.form.value("args:0:device") == "samx"
    widget.current_scan = "grid_scan"
    switch = widget.editors["kwargs:relative"].editor
    switch.click()
    assert widget.form.value("kwargs:relative") is True
    assert widget.start_button.text() == "Start grid_scan"
    assert len(widget.group_cards) == 2
