from unittest import mock

import pytest
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import ScanQueueMessage
from qtpy.QtGui import QValidator

from bec_widgets.widgets.device_box.device_box import DeviceBox

from .client_mocks import mocked_client


@pytest.fixture
def device_box(qtbot, mocked_client):
    with mock.patch("bec_widgets.widgets.device_box.device_box.uuid.uuid4") as mock_uuid:
        mock_uuid.return_value = "fake_uuid"
        db = DeviceBox(device="samx", client=mocked_client)
        qtbot.addWidget(db)
        yield db


def test_device_box(device_box):
    assert device_box.device == "samx"
    data = device_box.dev["samx"].read()

    setpoint_text = device_box.ui.setpoint.text()
    # check that the setpoint is taken correctly after init
    assert float(setpoint_text) == data["samx_setpoint"]["value"]

    # check that the precision is taken correctly after init
    precision = device_box.dev["samx"].precision
    assert setpoint_text == f"{data['samx_setpoint']['value']:.{precision}f}"

    # check that the step size is set according to the device precision
    assert device_box.ui.step_size.value() == 10**-precision * 10


def test_device_box_update_limits(device_box):
    device_box._limits = None
    device_box.update_limits([0, 10])
    assert device_box._limits == [0, 10]
    assert device_box.setpoint_validator.bottom() == 0
    assert device_box.setpoint_validator.top() == 10
    assert device_box.setpoint_validator.validate("100", 0) == (
        QValidator.State.Intermediate,
        "100",
        0,
    )

    device_box.update_limits(None)
    assert device_box._limits is None
    assert device_box.setpoint_validator.validate("100", 0) == (
        QValidator.State.Acceptable,
        "100",
        0,
    )


def test_device_box_on_stop(device_box):
    with mock.patch.object(device_box.client.connector, "send") as mock_send:
        device_box.on_stop()
        params = {"device": "samx", "rpc_id": "fake_uuid", "func": "stop", "args": [], "kwargs": {}}
        msg = ScanQueueMessage(
            scan_type="device_rpc",
            parameter=params,
            queue="emergency",
            metadata={"RID": "fake_uuid", "response": False},
        )
        mock_send.assert_called_once_with(MessageEndpoints.scan_queue_request(), msg)


def test_device_box_setpoint_change(device_box):
    with mock.patch.object(device_box.dev["samx"], "move") as mock_move:
        device_box.ui.setpoint.setText("100")
        device_box.on_setpoint_change()
        mock_move.assert_called_once_with(100, relative=False)


def test_device_box_on_tweak_right(device_box):
    with mock.patch.object(device_box.dev["samx"], "move") as mock_move:
        device_box.ui.step_size.setValue(0.1)
        device_box.on_tweak_right()
        mock_move.assert_called_once_with(0.1, relative=True)


def test_device_box_on_tweak_left(device_box):
    with mock.patch.object(device_box.dev["samx"], "move") as mock_move:
        device_box.ui.step_size.setValue(0.1)
        device_box.on_tweak_left()
        mock_move.assert_called_once_with(-0.1, relative=True)


def test_device_box_setpoint_out_of_range(device_box):
    device_box.update_limits([0, 10])
    device_box.ui.setpoint.setText("100")
    device_box.on_setpoint_change()
    assert device_box.ui.setpoint.text() == "100"
    assert device_box.ui.setpoint.hasAcceptableInput() == False
