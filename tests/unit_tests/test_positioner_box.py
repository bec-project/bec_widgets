from unittest import mock

import pytest
from bec_lib.device import Positioner
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import ScanQueueMessage
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QValidator
from qtpy.QtWidgets import QPushButton

from bec_widgets.widgets.device_line_edit.device_line_edit import DeviceLineEdit
from bec_widgets.widgets.positioner_box.positioner_box import PositionerBox
from bec_widgets.widgets.positioner_box.positioner_control_line import PositionerControlLine

from .client_mocks import mocked_client


@pytest.fixture
def positioner_box(qtbot, mocked_client):
    """Fixture for PositionerBox widget"""
    with mock.patch("bec_widgets.widgets.positioner_box.positioner_box.uuid.uuid4") as mock_uuid:
        mock_uuid.return_value = "fake_uuid"
        with mock.patch(
            "bec_widgets.widgets.positioner_box.positioner_box.PositionerBox._check_device_is_valid",
            return_value=True,
        ):
            db = PositionerBox(device="samx", client=mocked_client)
            qtbot.addWidget(db)
            yield db


def test_positioner_box(positioner_box):
    """Test init of positioner box"""
    assert positioner_box.device == "samx"
    data = positioner_box.dev["samx"].read()
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
        params = {"device": "samx", "rpc_id": "fake_uuid", "func": "stop", "args": [], "kwargs": {}}
        msg = ScanQueueMessage(
            scan_type="device_rpc",
            parameter=params,
            queue="emergency",
            metadata={"RID": "fake_uuid", "response": False},
        )
        mock_send.assert_called_once_with(MessageEndpoints.scan_queue_request(), msg)


def test_positioner_box_setpoint_change(positioner_box):
    """Test positioner box setpoint change"""
    with mock.patch.object(positioner_box.dev["samx"], "move") as mock_move:
        positioner_box.ui.setpoint.setText("100")
        positioner_box.on_setpoint_change()
        mock_move.assert_called_once_with(100, relative=False)


def test_positioner_box_on_tweak_right(positioner_box):
    """Test tweak right button"""
    with mock.patch.object(positioner_box.dev["samx"], "move") as mock_move:
        positioner_box.ui.step_size.setValue(0.1)
        positioner_box.on_tweak_right()
        mock_move.assert_called_once_with(0.1, relative=True)


def test_positioner_box_on_tweak_left(positioner_box):
    """Test tweak left button"""
    with mock.patch.object(positioner_box.dev["samx"], "move") as mock_move:
        positioner_box.ui.step_size.setValue(0.1)
        positioner_box.on_tweak_left()
        mock_move.assert_called_once_with(-0.1, relative=True)


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
    with mock.patch("bec_widgets.widgets.positioner_box.positioner_box.uuid.uuid4") as mock_uuid:
        mock_uuid.return_value = "fake_uuid"
        with mock.patch(
            "bec_widgets.widgets.positioner_box.positioner_box.PositionerBox._check_device_is_valid",
            return_value=True,
        ):
            db = PositionerControlLine(device="samx", client=mocked_client)
            qtbot.addWidget(db)

            assert db.ui.device_box.height() == 60
            assert db.ui.device_box.width() == 600


def test_positioner_box_open_dialog_selection(qtbot, positioner_box):
    """Test open positioner edit"""

    # Use a timer to close the dialog after it opens
    def close_dialog():
        # pylint: disable=protected-access
        assert positioner_box._dialog is not None
        qtbot.waitUntil(lambda: positioner_box._dialog.isVisible() is True, timeout=1000)
        line_edit = positioner_box._dialog.findChild(DeviceLineEdit)
        line_edit.setText("samy")
        close_button = positioner_box._dialog.findChild(QPushButton)
        assert close_button.text() == "Close"
        qtbot.mouseClick(close_button, Qt.LeftButton)

    # Execute the timer after the dialog opens to close it
    QTimer.singleShot(100, close_dialog)
    qtbot.mouseClick(positioner_box.ui.tool_button, Qt.LeftButton)
    assert positioner_box.device == "samy"
