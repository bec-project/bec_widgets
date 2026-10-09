"""Tests for the QML and QWidget ports of the positioner box."""

# pylint: disable=redefined-outer-name, protected-access, missing-function-docstring
from unittest import mock

import pytest
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import VariableMessage
from qtpy.QtQuickWidgets import QQuickWidget

from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_qml import (
    PositionerBoxQML,
)
from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_qwidget import (
    PositionerBoxQWidget,
)
from bec_widgets.widgets.control.device_control.positioner_box.positioner_ux_common import (
    format_step,
    parse_readback,
)

from .conftest import create_widget

MOVING = {
    "signals": {
        "samx": {"value": 2.5},
        "samx_setpoint": {"value": 6.0},
        "samx_motor_is_moving": {"value": 1},
    }
}


@pytest.fixture(params=[PositionerBoxQML, PositionerBoxQWidget])
def box(request, qtbot, mocked_client):
    mocked_client.device_manager.devices["samx"].limits = [-10, 10]
    widget = create_widget(qtbot, request.param, device="samx", client=mocked_client)
    yield widget


def test_parse_readback():
    parsed = parse_readback("samx", ["samx"], MOVING["signals"])
    assert parsed == {"readback": 2.5, "setpoint": 6.0, "moving": True}
    parsed = parse_readback("samx", ["samx"], {"samx_motor_done_move": {"value": 1}})
    assert parsed == {"readback": None, "setpoint": None, "moving": False}
    assert format_step(0.01) == "0.01"


def test_init_reads_cached_values(box):
    data = box.dev["samx"].read(cached=True)
    precision = box.dev["samx"].precision
    state = box.view_state()
    assert box.device == "samx"
    assert state["setpointText"] == f"{data['samx_setpoint']['value']:.{precision}f}"
    assert box.step_size == pytest.approx(10**-precision * 10)
    assert state["hasLimits"]
    assert state["limitLowText"] == "-10.000"


def test_readback_updates_state_and_emits(box, qtbot):
    with qtbot.waitSignal(box.position_update) as blocker:
        box.on_device_readback(MOVING, {})
    assert blocker.args == [2.5]
    state = box.view_state()
    assert state["status"] == "Moving"
    assert state["moving"]
    assert state["showTarget"]
    assert state["position"] == pytest.approx(0.625)
    assert state["target"] == pytest.approx(0.8)


def test_status_idle_and_at_limit(box):
    box.on_device_readback(
        {"signals": {"samx": {"value": 10.0}, "samx_motor_is_moving": {"value": 0}}}, {}
    )
    assert box.view_state()["status"] == "At limit"
    box.on_device_readback({"signals": {"samx": {"value": 1.0}}}, {})
    assert box.view_state()["status"] == "Idle"


def test_validate_and_move(box):
    assert box.validate_target("abc") == "Enter a number"
    assert box.validate_target("100").startswith("Outside limits")
    assert box.validate_target("5") == ""
    with mock.patch.object(box.scans, "mv") as mock_mv:
        assert not box.move_to("100")
        mock_mv.assert_not_called()
        assert box.view_state()["error"].startswith("Outside limits")
        assert box.move_to("5")
        mock_mv.assert_called_once_with(box.dev["samx"], 5.0, relative=False)
        assert box.view_state()["error"] == ""


def test_tweak_uses_setpoint_or_relative(box):
    box.step_size = 0.1
    with mock.patch.object(box.scans, "mv") as mock_mv:
        box.on_tweak_right()
        mock_mv.assert_called_once_with(box.dev["samx"], 0.1, relative=True)
    with mock.patch.object(box.scans, "mv") as mock_mv:
        box.on_tweak_left()
        mock_mv.assert_called_once_with(box.dev["samx"], -0.1, relative=True)
    with (
        mock.patch.object(box, "_get_setpoint", return_value=2.0),
        mock.patch.object(box.scans, "mv") as mock_mv,
    ):
        box.on_tweak_right()
        mock_mv.assert_called_once_with(box.dev["samx"], pytest.approx(2.1), relative=False)


def test_stop(box):
    with mock.patch.object(box.client.connector, "send") as mock_send:
        box.on_stop()
        mock_send.assert_called_once_with(
            MessageEndpoints.stop_devices(), VariableMessage(value=["samx"])
        )


def test_switch_device_and_hide_selection(box, qtbot):
    with qtbot.waitSignal(box.device_changed) as blocker:
        box.set_positioner("samy")
    assert blocker.args == ["samx", "samy"]
    assert box.view_state()["device"] == "samy"
    assert "samy" in box.positioner_names()
    box.hide_device_selection = True
    assert not box.view_state()["selectable"]
    box.show_device_selection(True)
    assert box.view_state()["selectable"]


def test_empty_box(qtbot, mocked_client):
    for cls in (PositionerBoxQML, PositionerBoxQWidget):
        widget = create_widget(qtbot, cls, client=mocked_client)
        state = widget.view_state()
        assert not state["hasDevice"]
        assert state["status"] == "No device"
        assert not widget.move_to("1")


def test_qml_view_loads_and_backend(qtbot, mocked_client):
    widget = create_widget(qtbot, PositionerBoxQML, device="samx", client=mocked_client)
    assert widget.view.status() == QQuickWidget.Status.Ready
    assert widget.view.errors() == []
    backend = widget.backend
    assert backend.state["device"] == "samx"
    backend.refreshPositioners()
    assert "samx" in backend.positioners
    assert backend.validate("x") == "Enter a number"
    backend.setStep(0.5)
    assert widget.step_size == 0.5
    with mock.patch.object(widget, "on_tweak_left") as tweak_left:
        backend.tweak(-1)
        tweak_left.assert_called_once()


def test_qwidget_controls(qtbot, mocked_client):
    mocked_client.device_manager.devices["samx"].limits = [-10, 10]
    widget = create_widget(qtbot, PositionerBoxQWidget, device="samx", client=mocked_client)
    widget.target_input.setText("100")
    assert widget.target_input.property("invalid")
    assert not widget.go_button.isEnabled()
    assert widget.error_label.text().startswith("Outside limits")
    widget.target_input.setText("3")
    assert widget.go_button.isEnabled()
    with mock.patch.object(widget.scans, "mv") as mock_mv:
        widget.go_button.click()
        mock_mv.assert_called_once_with(widget.dev["samx"], 3.0, relative=False)
    assert widget.target_input.text() == ""
    widget.step_input.setText("0.5")
    widget.step_input.editingFinished.emit()
    assert widget.step_size == 0.5
    assert widget.tweak_right.text() == "+0.5"
    widget.on_device_readback(MOVING, {})
    assert widget.status_pill.text == "Moving"
    assert widget.status_pill.pulsing
