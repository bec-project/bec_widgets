from unittest import mock

import pytest

from bec_widgets.widgets.control.device_control.positioner_box import PositionerBox2D

from .client_mocks import mocked_client
from .conftest import create_widget


@pytest.fixture
def positioner_box_2d(qtbot, mocked_client):
    """Fixture for PositionerBox widget"""
    with mock.patch(
        "bec_widgets.widgets.control.device_control.positioner_box._base.positioner_box_base.uuid.uuid4"
    ) as mock_uuid:
        mock_uuid.return_value = "fake_uuid"
        with mock.patch(
            "bec_widgets.widgets.control.device_control.positioner_box._base.positioner_box_base.PositionerBoxBase._check_device_is_valid",
            return_value=True,
        ):
            db = create_widget(
                qtbot, PositionerBox2D, device_hor="samx", device_ver="samy", client=mocked_client
            )
            yield db


def test_positioner_box_2d(positioner_box_2d):
    """Test init of 2D positioner box"""
    assert positioner_box_2d.device_hor == "samx"
    assert positioner_box_2d.device_ver == "samy"
    data_hor = positioner_box_2d.dev["samx"].read()
    data_ver = positioner_box_2d.dev["samy"].read()
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
    with (
        mock.patch.object(positioner_box_2d.dev["samx"], "move") as mock_move_hor,
        mock.patch.object(positioner_box_2d.dev["samy"], "move") as mock_move_ver,
    ):
        positioner_box_2d.ui.step_size_hor.setValue(0.1)
        positioner_box_2d.on_tweak_inc_hor()
        mock_move_hor.assert_called_once_with(0.01, relative=True)
        mock_move_ver.assert_not_called()
    with (
        mock.patch.object(positioner_box_2d.dev["samx"], "move") as mock_move_hor,
        mock.patch.object(positioner_box_2d.dev["samy"], "move") as mock_move_ver,
    ):
        positioner_box_2d.ui.step_size_ver.setValue(0.1)
        positioner_box_2d.on_step_dec_ver()
        mock_move_ver.assert_called_once_with(-0.1, relative=True)
        mock_move_hor.assert_not_called()


def test_positioner_box_setpoint_changes(positioner_box_2d: PositionerBox2D):
    """Test positioner box setpoint change"""
    with mock.patch.object(positioner_box_2d.dev["samx"], "move") as mock_move:
        positioner_box_2d.ui.setpoint_hor.setText("100")
        positioner_box_2d.on_setpoint_change_hor()
        mock_move.assert_called_once_with(100, relative=False)
    with mock.patch.object(positioner_box_2d.dev["samy"], "move") as mock_move:
        positioner_box_2d.ui.setpoint_ver.setText("100")
        positioner_box_2d.on_setpoint_change_ver()
        mock_move.assert_called_once_with(100, relative=False)
