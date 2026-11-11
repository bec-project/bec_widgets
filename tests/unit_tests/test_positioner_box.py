from unittest import mock

import pytest
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import DeviceMessage, VariableMessage
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QValidator
from qtpy.QtWidgets import QPushButton

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.tests.fake_devices import Positioner
from bec_widgets.widgets.control.buttons.stop_button.stop_button import StopButton
from bec_widgets.widgets.control.device_control.positioner_box import (
    PositionerBox,
    PositionerControlLine,
)
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox

from .conftest import create_widget


class PositionerWithoutPrecision(Positioner):
    """just placeholder for testing embedded isinstance check in DeviceCombobox"""

    def __init__(self, precision, name="test", limits=None, read_value=1.0, enabled=True):
        super().__init__(name, limits=limits, read_value=read_value, enabled=enabled)
        self._precision = precision

    @property
    def precision(self):
        return self._precision


@pytest.fixture
def positioner_box(qtbot, mocked_client):
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
        db = create_widget(qtbot, PositionerBox, device="samx", client=mocked_client)
        qtbot.waitUntil(lambda: db.ui.setpoint.text() != "")
        yield db


def test_positioner_box(positioner_box):
    """Test init of positioner box"""
    assert positioner_box.device == "samx"
    data = positioner_box.dev["samx"].read(cached=True)
    # Avoid check for Positioner class from BEC in _init_device

    setpoint_text = positioner_box.ui.setpoint.text()
    # check that the setpoint is taken correctly after init
    assert float(setpoint_text) == data["samx_setpoint"]["value"]

    # check that the precision is taken correctly after isnit
    precision = positioner_box.dev["samx"].precision
    assert setpoint_text == f"{data['samx_setpoint']['value']:.{precision}f}"

    # check that the step size is set according to the device precision
    assert positioner_box.ui.step_size.value() == 10**-precision * 10


def test_positioner_box_update_limits(positioner_box):
    """Test update of limits"""
    positioner_box._limits = None
    positioner_box.update_limits([0, 10])
    assert positioner_box._limits == [0, 10]
    assert positioner_box.setpoint_validator.bottom() == 0
    assert positioner_box.setpoint_validator.top() == 10
    assert positioner_box.setpoint_validator.validate("100", 0) == (
        QValidator.State.Intermediate,
        "100",
        0,
    )

    positioner_box.update_limits(None)
    assert positioner_box._limits is None
    assert positioner_box.setpoint_validator.validate("100", 0) == (
        QValidator.State.Acceptable,
        "100",
        0,
    )


def test_positioner_box_on_stop(positioner_box):
    """Test on stop button"""
    with mock.patch.object(positioner_box.client.connector, "send") as mock_send:
        positioner_box.on_stop()
        msg = VariableMessage(value=["samx"])
        mock_send.assert_called_once_with(MessageEndpoints.stop_devices(), msg)


def test_positioner_box_setpoint_change(positioner_box):
    """Test positioner box setpoint change"""
    with mock.patch.object(positioner_box.scans, "mv") as mock_mv:
        positioner_box.ui.setpoint.setText("100")
        positioner_box.on_setpoint_change()
        mock_mv.assert_called_once_with(positioner_box.dev["samx"], 100, relative=False)


def test_positioner_box_on_tweak_right(positioner_box):
    """Test tweak right button"""
    with mock.patch.object(positioner_box.scans, "mv") as mock_mv:
        positioner_box.ui.step_size.setValue(0.1)
        positioner_box.on_tweak_right()
        mock_mv.assert_called_once_with(
            positioner_box.dev["samx"], positioner_box._get_setpoint() + 0.1, relative=False
        )


def test_positioner_box_on_tweak_left(positioner_box):
    """Test tweak left button"""
    with mock.patch.object(positioner_box.scans, "mv") as mock_mv:
        positioner_box.ui.step_size.setValue(0.1)
        positioner_box.on_tweak_left()
        mock_mv.assert_called_once_with(
            positioner_box.dev["samx"], positioner_box._get_setpoint() - 0.1, relative=False
        )


def test_positioner_box_setpoint_out_of_range(positioner_box):
    """Test setpoint out of range"""
    positioner_box.update_limits([0, 10])
    positioner_box.ui.setpoint.setText("100")
    positioner_box.on_setpoint_change()
    assert positioner_box.ui.setpoint.text() == "100"
    assert positioner_box.ui.setpoint.hasAcceptableInput() == False


def test_positioner_control_line(qtbot, mocked_client):
    """Test PositionerControlLine.
    Inherits from PositionerBox, but the layout is changed. Check dimensions only
    """
    with mock.patch(
        "bec_widgets.widgets.control.device_control.positioner_box.positioner_box.positioner_box.PositionerBox._check_device_is_valid",
        return_value=True,
    ):
        db = PositionerControlLine(device="samx", client=mocked_client)
        qtbot.addWidget(db)

        assert db.ui.device_box.height() == db.height()
        assert db.ui.device_box.height() >= db.dimensions[0]
        assert db.ui.device_box.width() == 600


def test_positioner_box_open_dialog_selection(qtbot, positioner_box):
    """Test open positioner edit"""

    # Use a timer to close the dialog after it opens
    def close_dialog():
        # pylint: disable=protected-access
        assert positioner_box._dialog is not None
        qtbot.waitUntil(lambda: positioner_box._dialog.isVisible() is True, timeout=1000)
        line_edit = positioner_box._dialog.findChild(DeviceComboBox)
        line_edit.setCurrentText("samy")
        close_button = positioner_box._dialog.findChild(QPushButton)
        assert close_button.text() == "Close"
        qtbot.mouseClick(close_button, Qt.LeftButton)

    # Execute the timer after the dialog opens to close it
    QTimer.singleShot(100, close_dialog)
    qtbot.mouseClick(positioner_box.ui.tool_button, Qt.LeftButton)
    assert positioner_box.device == "samy"


def test_device_validity_check_rejects_non_positioner():
    # isinstance checks for PositionerBox are mocked out in the mock client
    positioner_box = mock.MagicMock(spec=PositionerBox)
    positioner_box.dev = {"test": 5.123}
    assert not PositionerBox._check_device_is_valid(positioner_box, "test")


def test_positioner_box_device_without_precision(qtbot, positioner_box):
    """Test positioner box with device without precision"""

    for ii, mock_return in enumerate([None, 2, 2.0, True, "tmp"]):
        dev_name = f"samy_{ii}"
        device = PositionerWithoutPrecision(
            precision=mock_return, name=dev_name, limits=[-5, 5], read_value=3.0
        )
        positioner_box.bec_dispatcher.client.device_manager.add_devices(devices=[device])

        positioner_box.device = dev_name

        def check_title():
            return positioner_box.ui.device_box.title() == dev_name

        qtbot.waitUntil(check_title, timeout=3000)
        if isinstance(mock_return, (int, float)):
            mock_return = int(mock_return)
            assert positioner_box.ui.step_size.value() == 10**-mock_return * 10
        else:
            assert positioner_box.ui.step_size.value() == 10**-8 * 10


@pytest.mark.parametrize("box_class", [PositionerBox, PositionerControlLine])
def test_stop_only_stops_the_motor(qtbot, mocked_client, box_class):
    """The Stop looks like the Scan Control Stop without its menu and only stops samx."""
    with mock.patch(
        "bec_widgets.widgets.control.device_control.positioner_box.positioner_box_base.PositionerBoxBase._check_device_is_valid",
        return_value=True,
    ):
        box = create_widget(qtbot, box_class, device="samx", client=mocked_client)
    stop = box.ui.stop
    assert isinstance(stop, StopButton)
    assert stop.device_stop and stop.arrow.isHidden()
    assert stop.toolTip() == "Stop"
    stop.setEnabled(True)
    with (
        mock.patch.object(box.client.connector, "send") as send,
        mock.patch.object(stop.queue, "request_scan_abortion") as abort,
        mock.patch.object(stop.queue, "request_scan_halt") as halt,
    ):
        stop.button.click()
        stop.button.click()
    assert send.call_args_list == 2 * [
        mock.call(MessageEndpoints.stop_devices(), VariableMessage(value=["samx"]))
    ]
    abort.assert_not_called()
    halt.assert_not_called()
    assert stop.button.text() == "Stop"


def test_positioner_readback_and_tweak_use_data_api(qtbot, positioner_box):
    device = positioner_box.dev["samx"]
    with mock.patch.object(device, "read", side_effect=AssertionError("direct read")):
        positioner_box.client.connector.set_and_publish(
            MessageEndpoints.device_readback("samx"),
            DeviceMessage(signals={"samx": {"value": 4.5}, "samx_setpoint": {"value": 5.0}}),
        )
        qtbot.waitUntil(lambda: positioner_box.ui.readback.text() == "4.500")
        qtbot.waitUntil(lambda: positioner_box._get_setpoint() == 5.0)
        positioner_box.force_update_readback()
        qtbot.waitUntil(lambda: positioner_box.ui.readback.text() == "4.500")
        with mock.patch.object(positioner_box.scans, "mv") as mock_mv:
            positioner_box.ui.step_size.setValue(0.1)
            positioner_box.on_tweak_right()
            mock_mv.assert_called_once_with(device, 5.1, relative=False)


def test_positioner_rebind_drops_queued_old_values(qtbot, positioner_box):
    old = next(iter(positioner_box._readback_subscriptions.values()))
    positioner_box.client.connector.set_and_publish(
        MessageEndpoints.device_readback("samx"), DeviceMessage(signals={"samx": {"value": 8.0}})
    )
    positioner_box.device = "samy"
    qtbot.waitUntil(lambda: positioner_box.ui.readback.text() == "3.000")
    assert old._closed
    positioner_box.close()
    assert not positioner_box._readback_subscriptions


def test_positioner_tweaks_relative_without_a_setpoint(qtbot, positioner_box):
    positioner_box._device_values["samx"].clear()
    with mock.patch.object(positioner_box.scans, "mv") as mock_mv:
        positioner_box.ui.step_size.setValue(0.1)
        positioner_box.on_tweak_right()
        mock_mv.assert_called_once_with(positioner_box.dev["samx"], 0.1, relative=True)


def test_positioner_uses_declared_auxiliary_signal_names(qtbot, positioner_box, monkeypatch):
    device = positioner_box.dev["samx"]
    signal_info = {
        "readback": {"obj_name": "samx", "kind_str": "hinted"},
        "target_alias": {
            "component_name": "setpoint",
            "obj_name": "actual_target",
            "kind_str": "normal",
        },
        "moving_alias": {
            "component_name": "motor_is_moving",
            "obj_name": "motion_flag",
            "kind_str": "normal",
        },
    }
    monkeypatch.setitem(device._info, "signals", signal_info)
    positioner_box.client.connector.set_and_publish(
        MessageEndpoints.device_readback("samx"),
        DeviceMessage(
            signals={
                "samx": {"value": 1.0},
                "actual_target": {"value": 7.0},
                "motion_flag": {"value": True},
            }
        ),
    )
    positioner_box.force_update_readback()
    qtbot.waitUntil(lambda: positioner_box.ui.setpoint.text() == "7.000")
    assert positioner_box._get_setpoint() == 7.0
    assert positioner_box.ui.spinner_widget.toolTip() == "Device is moving"


def test_positioner_empty_device_closes_subscription(positioner_box):
    subscription = next(iter(positioner_box._readback_subscriptions.values()))
    positioner_box.device = ""
    assert subscription._closed
    assert not positioner_box._readback_subscriptions
    assert not positioner_box.ui.setpoint.isEnabled()
    assert positioner_box._get_setpoint() is None
