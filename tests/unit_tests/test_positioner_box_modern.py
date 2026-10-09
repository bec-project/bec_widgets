from unittest import mock

import pytest
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import VariableMessage

from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_modern import (
    PositionerBoxQML,
    PositionerBoxWidgets,
)
from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_modern.positioner_box_modern_base import (
    MOVING_ACTIVE,
    MOVING_IDLE,
)

from .conftest import create_widget


@pytest.fixture(params=[PositionerBoxQML, PositionerBoxWidgets], ids=["qml", "qwidget"])
def box(request, qtbot, mocked_client):
    yield create_widget(qtbot, request.param, device="samx", client=mocked_client)


def _readback(box, value, setpoint, moving):
    box.on_device_readback(
        {
            "signals": {
                "samx": {"value": value},
                "samx_setpoint": {"value": setpoint},
                "samx_motor_is_moving": {"value": moving},
            }
        },
        {},
    )


def test_init_reads_cached_values(box):
    data = box.dev["samx"].read(cached=True)
    precision = box.dev["samx"].precision
    assert box.device == "samx"
    assert box.readback_text == f"{data['samx']['value']:.{precision}f}"
    assert box.step_size == pytest.approx(10**-precision * 10)
    assert box.has_limits
    assert box.low_text == f"{-10:.{precision}f}"


def test_readback_updates_state_and_emits_position(box, qtbot):
    with qtbot.waitSignal(box.position_update) as blocker:
        _readback(box, 2.0, 5.5, True)
    assert blocker.args == [2.0]
    assert box._moving == MOVING_ACTIVE
    assert box.has_target
    assert box.position_fraction == pytest.approx(0.6)
    assert box.target_fraction == pytest.approx(0.775)

    _readback(box, 5.5, 5.5, False)
    assert box._moving == MOVING_IDLE
    assert not box.has_target
    assert box.target_fraction == -1


def test_readback_outside_limits_is_flagged(box):
    _readback(box, 12.0, 12.0, False)
    assert box.out_of_limits
    assert box.position_fraction == 1.0


@pytest.mark.parametrize(
    "text, error",
    [("", ""), ("3", ""), ("abc", "Enter a number"), ("nan", "Enter a number"), ("100", "Outside")],
)
def test_validate_target(box, text, error):
    result = box.validate_target(text)
    assert result.startswith(error) if error else result == ""


def test_move_to_text_only_sends_valid_targets(box):
    with mock.patch.object(box.scans, "mv") as mock_mv:
        assert not box.move_to_text("100")
        assert not box.move_to_text("abc")
        assert not box.move_to_text(" ")
        mock_mv.assert_not_called()
        assert box.move_to_text("3.5")
        mock_mv.assert_called_once_with(box.dev["samx"], 3.5, relative=False)


@pytest.mark.parametrize("direction", [1, -1])
def test_tweak(box, direction):
    box.set_step_text("0.5")
    with mock.patch.object(box.scans, "mv") as mock_mv:
        with mock.patch.object(box, "_get_setpoint", return_value=None):
            box.tweak(direction)
        mock_mv.assert_called_once_with(box.dev["samx"], 0.5 * direction, relative=True)
        mock_mv.reset_mock()
        with mock.patch.object(box, "_get_setpoint", return_value=2.0):
            box.tweak(direction)
        mock_mv.assert_called_once_with(box.dev["samx"], 2.0 + 0.5 * direction, relative=False)


def test_step_size_editing(box):
    box.set_step_text("0.5")
    assert box.step_size == 0.5
    box.set_step_text("-1")
    box.set_step_text("abc")
    assert box.step_size == 0.5
    box.scale_step(10)
    assert box.step_text == "5"
    box.scale_step(0.1)
    box.scale_step(0.1)
    assert box.step_text == "0.05"


def test_stop(box):
    with mock.patch.object(box.client.connector, "send") as mock_send:
        box.on_stop()
    mock_send.assert_called_once_with(
        MessageEndpoints.stop_devices(), VariableMessage(value=["samx"])
    )


def test_set_positioner_switches_subscription(box, qtbot):
    with (
        mock.patch.object(box.bec_dispatcher, "connect_slot") as connect,
        mock.patch.object(box.bec_dispatcher, "disconnect_slot") as disconnect,
    ):
        with qtbot.waitSignal(box.device_changed) as blocker:
            box.set_positioner("samy")
    assert blocker.args == ["samx", "samy"]
    disconnect.assert_called_once_with(
        box.on_device_readback, MessageEndpoints.device_readback("samx")
    )
    connect.assert_called_once_with(
        box.on_device_readback, MessageEndpoints.device_readback("samy")
    )
    assert box.high_text == f"{5:.3f}"


def test_set_positioner_rejects_non_positioner(box):
    box.set_positioner("bpm4i")
    assert box.device == "samx"


def test_no_limits(box):
    box.set_positioner("aptrx")
    assert not box.has_limits
    assert box.position_fraction == -1
    assert box.validate_target("1e6") == ""


def test_device_picker_filters_and_picks(box):
    assert "samx" in box.positioner_names()
    assert "bpm4i" not in box.positioner_names()
    box.open_device_picker(box.mapToGlobal(box.rect().topLeft()))
    picker = box._picker
    picker.search.setText("samy")
    visible = [
        picker.list.item(i).text()
        for i in range(picker.list.count())
        if not picker.list.item(i).isHidden()
    ]
    assert visible == ["samy"]
    picker.search.returnPressed.emit()
    assert box.device == "samy"


def test_hide_device_selection(box):
    box.hide_device_selection = True
    assert not box.device_selectable
    box.open_device_picker(box.mapToGlobal(box.rect().topLeft()))
    assert box._picker is None
    box.show_device_selection(True)
    assert box.device_selectable


def test_qwidget_view_shows_inline_error(qtbot, mocked_client):
    box = create_widget(qtbot, PositionerBoxWidgets, device="samx", client=mocked_client)
    box.setpoint.setText("100")
    assert not box.go.isEnabled()
    assert box.move_error.text().startswith("Outside limits")
    box.setpoint.setText("4")
    assert box.go.isEnabled()
    assert box.move_error.text() == ""
    with mock.patch.object(box.scans, "mv") as mock_mv:
        box.go.click()
    mock_mv.assert_called_once_with(box.dev["samx"], 4.0, relative=False)
    assert box.setpoint.text() == ""


def test_qml_view_binds_to_state(qtbot, mocked_client):
    box = create_widget(qtbot, PositionerBoxQML, device="samx", client=mocked_client)
    root = box.view.rootObject()
    assert root is not None
    field = root.findChild(object, "targetField")
    field.setProperty("text", "100")
    assert root.property("moveError").startswith("Outside limits")
    _readback(box, 2.0, 5.5, True)
    assert root.property("isMoving")
