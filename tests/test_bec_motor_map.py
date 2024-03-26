import pytest

from bec_widgets.widgets import BECMotorMap
from bec_widgets.widgets.plots.motor_map import MotorMapConfig
from bec_widgets.widgets.plots.waveform1d import Signal, SignalData

from .client_mocks import mocked_client


@pytest.fixture(scope="function")
def bec_motor_map(qtbot, mocked_client):
    widget = BECMotorMap(client=mocked_client, gui_id="BECMotorMap_test")
    # qtbot.addWidget(widget)
    # qtbot.waitExposed(widget)
    yield widget


def test_motor_map_init(bec_motor_map):
    default_config = MotorMapConfig(widget_class="BECMotorMap", gui_id="BECMotorMap_test")

    assert bec_motor_map.config == default_config


def test_motor_map_change_motors(bec_motor_map):
    bec_motor_map.change_motors("samx", "samy")

    assert bec_motor_map.config.signals.x == SignalData(name="samx", entry="samx", limits=[-10, 10])
    assert bec_motor_map.config.signals.y == SignalData(name="samy", entry="samy", limits=[-5, 5])


def test_motor_map_get_limits(bec_motor_map):
    expected_limits = {
        "samx": [-10, 10],
        "samy": [-5, 5],
    }

    for motor_name, expected_limit in expected_limits.items():
        actual_limit = bec_motor_map._get_motor_limit(motor_name)
        assert actual_limit == expected_limit
