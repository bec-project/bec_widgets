from unittest import mock

import pytest
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import DeviceMessage, VariableMessage

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.widgets.control.device_control.positioner_box import PositionerBox2D

from .conftest import create_widget


@pytest.fixture
def positioner_box_2d(qtbot, mocked_client):
    """Fixture for PositionerBox widget"""
    for name in ("samx", "samy"):
        mocked_client.connector.set_and_publish(
            MessageEndpoints.device_readback(name),
            DeviceMessage(signals=mocked_client.device_manager.devices[name].signals),
        )
    with mock.patch(
        "bec_widgets.widgets.control.device_control.positioner_box.positioner_box_base.PositionerBoxBase._check_device_is_valid",
        return_value=True,
    ):
        db = create_widget(
            qtbot, PositionerBox2D, device_hor="samx", device_ver="samy", client=mocked_client
        )
        qtbot.waitUntil(lambda: db.ui.setpoint_hor.text() != "" and db.ui.setpoint_ver.text() != "")
        yield db


def test_positioner_box_2d(positioner_box_2d):
    """Test init of 2D positioner box"""
    assert positioner_box_2d.device_hor == "samx"
    assert positioner_box_2d.device_ver == "samy"
    data_hor = positioner_box_2d.dev["samx"].read(cached=True)
    data_ver = positioner_box_2d.dev["samy"].read(cached=True)
    # Avoid check for Positioner class from BEC in _init_device

    setpoint_hor_text = positioner_box_2d.ui.setpoint_hor.text()
    setpoint_ver_text = positioner_box_2d.ui.setpoint_ver.text()
    # check that the setpoint is taken correctly after init
    assert float(setpoint_hor_text) == data_hor["samx_setpoint"]["value"]
    assert float(setpoint_ver_text) == data_ver["samy_setpoint"]["value"]

    # check that the precision is taken correctly after init
    precision_hor = positioner_box_2d.dev["samx"].precision
    precision_ver = positioner_box_2d.dev["samy"].precision
    assert setpoint_hor_text == f"{data_hor['samx_setpoint']['value']:.{precision_hor}f}"
    assert setpoint_ver_text == f"{data_ver['samy_setpoint']['value']:.{precision_ver}f}"

    # check that the step size is set according to the device precision
    assert positioner_box_2d.ui.step_size_hor.value() == 10**-precision_hor * 10
    assert positioner_box_2d.ui.step_size_ver.value() == 10**-precision_ver * 10


def test_positioner_box_move_hor_does_not_affect_ver(positioner_box_2d):
    """Test that moving one positioner doesn't affect the other"""
    with mock.patch.object(positioner_box_2d.scans, "mv") as mock_mv:
        positioner_box_2d.ui.step_size_hor.setValue(0.1)
        positioner_box_2d.on_tweak_inc_hor()
        mock_mv.assert_called_once_with(positioner_box_2d.dev["samx"], 0.01, relative=True)
    with mock.patch.object(positioner_box_2d.scans, "mv") as mock_mv:
        positioner_box_2d.ui.step_size_ver.setValue(0.1)
        positioner_box_2d.on_step_dec_ver()
        mock_mv.assert_called_once_with(positioner_box_2d.dev["samy"], -0.1, relative=True)


def test_positioner_box_setpoint_changes(positioner_box_2d: PositionerBox2D):
    """Test positioner box setpoint change"""
    with mock.patch.object(positioner_box_2d.scans, "mv") as mock_mv:
        positioner_box_2d.ui.setpoint_hor.setText("100")
        positioner_box_2d.on_setpoint_change_hor()
        mock_mv.assert_called_once_with(positioner_box_2d.dev["samx"], 100, relative=False)
    with mock.patch.object(positioner_box_2d.scans, "mv") as mock_mv:
        positioner_box_2d.ui.setpoint_ver.setText("100")
        positioner_box_2d.on_setpoint_change_ver()
        mock_mv.assert_called_once_with(positioner_box_2d.dev["samy"], 100, relative=False)


def test_positioner_box_2d_on_stop(positioner_box_2d: PositionerBox2D):
    """Stop button sends both positioners to the immediate stop endpoint."""
    with mock.patch.object(positioner_box_2d.client.connector, "send") as mock_send:
        positioner_box_2d.on_stop()
        msg = VariableMessage(value=["samx", "samy"])
        mock_send.assert_called_once_with(MessageEndpoints.stop_devices(), msg)


def _hor_buttons(widget: PositionerBox2D):
    return [
        widget.ui.tweak_increase_hor,
        widget.ui.tweak_decrease_hor,
        widget.ui.step_increase_hor,
        widget.ui.step_decrease_hor,
    ]


def _ver_buttons(widget: PositionerBox2D):
    return [
        widget.ui.tweak_increase_ver,
        widget.ui.tweak_decrease_ver,
        widget.ui.step_increase_ver,
        widget.ui.step_decrease_ver,
    ]


def test_controls_default_enabled(positioner_box_2d: PositionerBox2D):
    """By default both axes controls are enabled and UI reflects it."""
    assert positioner_box_2d.enable_controls_hor is True
    assert positioner_box_2d.enable_controls_ver is True
    assert all(w.isEnabled() for w in _hor_buttons(positioner_box_2d))
    assert all(w.isEnabled() for w in _ver_buttons(positioner_box_2d))


def test_disable_enable_controls_and_persist_across_device_change(
    positioner_box_2d: PositionerBox2D, qtbot
):
    """Disabling an axis should disable its buttons and remain disabled after device (re)binding."""
    # Disable horizontal and verify UI
    positioner_box_2d.enable_controls_hor = False
    assert positioner_box_2d.enable_controls_hor is False
    assert all(not w.isEnabled() for w in _hor_buttons(positioner_box_2d))

    # Simulate a horizontal device change; state must persist after queued re-apply
    positioner_box_2d.on_device_change_hor("samx", "samx")
    qtbot.waitUntil(lambda: all(not w.isEnabled() for w in _hor_buttons(positioner_box_2d)))

    # Re-enable and verify UI
    positioner_box_2d.enable_controls_hor = True
    qtbot.waitUntil(lambda: all(w.isEnabled() for w in _hor_buttons(positioner_box_2d)))

    # Disable vertical and verify UI
    positioner_box_2d.enable_controls_ver = False
    assert positioner_box_2d.enable_controls_ver is False
    assert all(not w.isEnabled() for w in _ver_buttons(positioner_box_2d))

    # Simulate a vertical device change; state must persist after queued re-apply
    positioner_box_2d.on_device_change_ver("samy", "samy")
    qtbot.waitUntil(lambda: all(not w.isEnabled() for w in _ver_buttons(positioner_box_2d)))

    # Re-enable and verify UI
    positioner_box_2d.enable_controls_ver = True
    qtbot.waitUntil(lambda: all(w.isEnabled() for w in _ver_buttons(positioner_box_2d)))


def test_stop_only_stops_both_motors(positioner_box_2d):
    """The Stop stops samx and samy; it shows no scan menu and leaves the scan queue alone."""
    stop = positioner_box_2d.ui.stop_button
    assert stop.device_stop and stop.arrow.isHidden()
    stop.setEnabled(True)
    with (
        mock.patch.object(positioner_box_2d.client.connector, "send") as send,
        mock.patch.object(stop.queue, "request_scan_abortion") as abort,
        mock.patch.object(stop.queue, "request_scan_halt") as halt,
    ):
        stop.button.click()
        stop.button.click()
    assert send.call_args_list == 2 * [
        mock.call(MessageEndpoints.stop_devices(), VariableMessage(value=["samx", "samy"]))
    ]
    abort.assert_not_called()
    halt.assert_not_called()
    assert stop.button.text() == "Stop"


def test_positioner_axes_receive_independent_data_api_updates(qtbot, positioner_box_2d):
    widget = positioner_box_2d
    widget.client.connector.set_and_publish(
        MessageEndpoints.device_readback("samx"), DeviceMessage(signals={"samx": {"value": 6.0}})
    )
    qtbot.waitUntil(lambda: widget.ui.readback_hor.text() == "6.000")
    assert widget.ui.readback_ver.text() == "3.000"
    subscriptions = list(widget._readback_subscriptions.values())
    widget.close()
    assert all(subscription._closed for subscription in subscriptions)


def test_positioner_clearing_one_axis_keeps_other_subscription(positioner_box_2d):
    widget = positioner_box_2d
    horizontal = widget._readback_subscriptions[widget.ui.readback_hor]
    vertical = widget._readback_subscriptions[widget.ui.readback_ver]
    widget.device_hor = ""
    assert horizontal._closed
    assert not vertical._closed
    assert widget.ui.readback_ver.text() == "3.000"
    assert all(not button.isEnabled() for button in _hor_buttons(widget))
    assert widget.ui.stop_button.isEnabled()
