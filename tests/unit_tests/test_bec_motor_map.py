import pytest

from bec_widgets.widgets import BECMotorMap
from bec_widgets.widgets.plots.motor_map import MotorMapConfig
from bec_widgets.widgets.plots.waveform import Signal, SignalData

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
    expected_limits = {"samx": [-10, 10], "samy": [-5, 5]}

    for motor_name, expected_limit in expected_limits.items():
        actual_limit = bec_motor_map._get_motor_limit(motor_name)
        assert actual_limit == expected_limit


def test_motor_map_get_init_position(bec_motor_map):
    bec_motor_map.set_precision(2)

    motor_map_dev = bec_motor_map.client.device_manager.devices

    expected_positions = {
        ("samx", "samx"): motor_map_dev["samx"].read()["samx"]["value"],
        ("samy", "samy"): motor_map_dev["samy"].read()["samy"]["value"],
        ("aptrx", "aptrx"): motor_map_dev["aptrx"].read()["aptrx"]["value"],
        ("aptry", "aptry"): motor_map_dev["aptry"].read()["aptry"]["value"],
    }

    for (motor_name, entry), expected_position in expected_positions.items():
        actual_position = bec_motor_map._get_motor_init_position(motor_name, entry, 2)
        assert actual_position == expected_position


def test_motor_movement_updates_position_and_database(bec_motor_map):
    motor_map_dev = bec_motor_map.client.device_manager.devices

    init_positions = {
        "samx": [motor_map_dev["samx"].read()["samx"]["value"]],
        "samy": [motor_map_dev["samy"].read()["samy"]["value"]],
    }

    bec_motor_map.change_motors("samx", "samy")

    assert bec_motor_map.database_buffer["x"] == init_positions["samx"]
    assert bec_motor_map.database_buffer["y"] == init_positions["samy"]

    # Simulate motor movement for 'samx' only
    new_position_samx = 4.0
    bec_motor_map.on_device_readback({"signals": {"samx": {"value": new_position_samx}}})

    init_positions["samx"].append(new_position_samx)
    init_positions["samy"].append(init_positions["samy"][-1])
    # Verify database update for 'samx'
    assert bec_motor_map.database_buffer["x"] == init_positions["samx"]

    # Verify 'samy' retains its last known position
    assert bec_motor_map.database_buffer["y"] == init_positions["samy"]


def test_scatter_plot_rendering(bec_motor_map):
    motor_map_dev = bec_motor_map.client.device_manager.devices

    init_positions = {
        "samx": [motor_map_dev["samx"].read()["samx"]["value"]],
        "samy": [motor_map_dev["samy"].read()["samy"]["value"]],
    }

    bec_motor_map.change_motors("samx", "samy")

    # Simulate motor movement for 'samx' only
    new_position_samx = 4.0
    bec_motor_map.on_device_readback({"signals": {"samx": {"value": new_position_samx}}})
    bec_motor_map._update_plot()

    # Get the scatter plot item
    scatter_plot_item = bec_motor_map.plot_components["scatter"]

    # Check the scatter plot item properties
    assert len(scatter_plot_item.data) > 0, "Scatter plot data is empty"
    x_data = scatter_plot_item.data["x"]
    y_data = scatter_plot_item.data["y"]
    assert x_data[-1] == new_position_samx, "Scatter plot X data not updated correctly"
    assert (
        y_data[-1] == init_positions["samy"][-1]
    ), "Scatter plot Y data should retain last known position"


def test_plot_visualization_consistency(bec_motor_map):
    bec_motor_map.change_motors("samx", "samy")
    # Simulate updating the plot with new data
    bec_motor_map.on_device_readback({"signals": {"samx": {"value": 5}}})
    bec_motor_map.on_device_readback({"signals": {"samy": {"value": 9}}})
    bec_motor_map._update_plot()

    scatter_plot_item = bec_motor_map.plot_components["scatter"]

    # Check if the scatter plot reflects the new data correctly
    assert (
        scatter_plot_item.data["x"][-1] == 5 and scatter_plot_item.data["y"][-1] == 9
    ), "Plot not updated correctly with new data"
