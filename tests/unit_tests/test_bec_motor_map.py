import numpy as np
import pytest
from bec_lib.messages import DeviceMessage

from bec_widgets.widgets.figure import BECFigure
from bec_widgets.widgets.figure.plots.motor_map.motor_map import BECMotorMap, MotorMapConfig
from bec_widgets.widgets.figure.plots.waveform.waveform_curve import SignalData

from .client_mocks import mocked_client
from .conftest import create_widget


def test_motor_map_init(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    default_config = MotorMapConfig(widget_class="BECMotorMap")

    mm = bec_figure.motor_map(config=default_config.model_dump())
    default_config.gui_id = mm.gui_id

    assert mm.config == default_config


def test_motor_map_change_motors(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    mm = bec_figure.motor_map("samx", "samy")

    assert mm.motor_x == "samx"
    assert mm.motor_y == "samy"
    assert mm.config.signals.x == SignalData(name="samx", entry="samx", limits=[-10, 10])
    assert mm.config.signals.y == SignalData(name="samy", entry="samy", limits=[-5, 5])

    mm.change_motors("samx", "samz")

    assert mm.config.signals.x == SignalData(name="samx", entry="samx", limits=[-10, 10])
    assert mm.config.signals.y == SignalData(name="samz", entry="samz", limits=[-8, 8])


def test_motor_map_get_limits(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    mm = bec_figure.motor_map("samx", "samy")
    expected_limits = {"samx": [-10, 10], "samy": [-5, 5]}

    for motor_name, expected_limit in expected_limits.items():
        actual_limit = mm._get_motor_limit(motor_name)
        assert actual_limit == expected_limit


def test_motor_map_get_init_position(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    mm = bec_figure.motor_map("samx", "samy")
    mm.set_precision(2)

    motor_map_dev = mm.client.device_manager.devices

    expected_positions = {
        ("samx", "samx"): motor_map_dev["samx"].read()["samx"]["value"],
        ("samy", "samy"): motor_map_dev["samy"].read()["samy"]["value"],
    }

    for (motor_name, entry), expected_position in expected_positions.items():
        actual_position = mm._get_motor_init_position(motor_name, entry, 2)
        assert actual_position == expected_position


def test_motor_movement_updates_position_and_database(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    mm = bec_figure.motor_map("samx", "samy")
    motor_map_dev = mm.client.device_manager.devices

    init_positions = {
        "samx": [motor_map_dev["samx"].read()["samx"]["value"]],
        "samy": [motor_map_dev["samy"].read()["samy"]["value"]],
    }

    mm.change_motors("samx", "samy")

    assert mm.database_buffer["x"] == init_positions["samx"]
    assert mm.database_buffer["y"] == init_positions["samy"]

    # Simulate motor movement for 'samx' only
    new_position_samx = 4.0
    msg = DeviceMessage(signals={"samx": {"value": new_position_samx}}, metadata={})
    mm.on_device_readback(msg.content, msg.metadata)

    init_positions["samx"].append(new_position_samx)
    init_positions["samy"].append(init_positions["samy"][-1])
    # Verify database update for 'samx'
    assert mm.database_buffer["x"] == init_positions["samx"]

    # Verify 'samy' retains its last known position
    assert mm.database_buffer["y"] == init_positions["samy"]


def test_scatter_plot_rendering(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    mm = bec_figure.motor_map("samx", "samy")
    motor_map_dev = mm.client.device_manager.devices

    init_positions = {
        "samx": [motor_map_dev["samx"].read()["samx"]["value"]],
        "samy": [motor_map_dev["samy"].read()["samy"]["value"]],
    }

    mm.change_motors("samx", "samy")

    # Simulate motor movement for 'samx' only
    new_position_samx = 4.0
    msg = DeviceMessage(signals={"samx": {"value": new_position_samx}}, metadata={})
    mm.on_device_readback(msg.content, msg.metadata)
    mm._update_plot()

    # Get the scatter plot item
    scatter_plot_item = mm.plot_components["scatter"]

    # Check the scatter plot item properties
    assert len(scatter_plot_item.data) > 0, "Scatter plot data is empty"
    x_data = scatter_plot_item.data["x"]
    y_data = scatter_plot_item.data["y"]
    assert x_data[-1] == new_position_samx, "Scatter plot X data not updated correctly"
    assert (
        y_data[-1] == init_positions["samy"][-1]
    ), "Scatter plot Y data should retain last known position"


def test_plot_visualization_consistency(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    mm = bec_figure.motor_map("samx", "samy")
    mm.change_motors("samx", "samy")
    # Simulate updating the plot with new data
    msg = DeviceMessage(signals={"samx": {"value": 5}}, metadata={})
    mm.on_device_readback(msg.content, msg.metadata)
    msg = DeviceMessage(signals={"samy": {"value": 9}}, metadata={})
    mm.on_device_readback(msg.content, msg.metadata)
    mm._update_plot()

    scatter_plot_item = mm.plot_components["scatter"]

    # Check if the scatter plot reflects the new data correctly
    assert (
        scatter_plot_item.data["x"][-1] == 5 and scatter_plot_item.data["y"][-1] == 9
    ), "Plot not updated correctly with new data"


def test_change_background_value(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    mm = bec_figure.motor_map("samx", "samy")

    assert mm.config.background_value == 25
    assert np.all(mm.plot_components["limit_map"].image == 25.0)

    mm.set_background_value(50)
    qtbot.wait(200)

    assert mm.config.background_value == 50
    assert np.all(mm.plot_components["limit_map"].image == 50.0)


def test_motor_map_init_from_config(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    config = {
        "widget_class": "BECMotorMap",
        "gui_id": "mm_id",
        "parent_id": bec_figure.gui_id,
        "row": 0,
        "col": 0,
        "axis": {
            "title": "Motor position: (-0.0, 0.0)",
            "title_size": None,
            "x_label": "Motor X (samx)",
            "x_label_size": None,
            "y_label": "Motor Y (samy)",
            "y_label_size": None,
            "legend_label_size": None,
            "x_scale": "linear",
            "y_scale": "linear",
            "x_lim": None,
            "y_lim": None,
            "x_grid": True,
            "y_grid": True,
        },
        "signals": {
            "source": "device_readback",
            "x": {
                "name": "samx",
                "entry": "samx",
                "unit": None,
                "modifier": None,
                "limits": [-10.0, 10.0],
            },
            "y": {
                "name": "samy",
                "entry": "samy",
                "unit": None,
                "modifier": None,
                "limits": [-5.0, 5.0],
            },
            "z": None,
            "dap": None,
        },
        "color": (255, 255, 255, 255),
        "scatter_size": 5,
        "max_points": 50,
        "num_dim_points": 10,
        "precision": 5,
        "background_value": 50,
    }
    mm = bec_figure.motor_map(config=config)
    config["gui_id"] = mm.gui_id

    assert mm._config_dict == config


def test_motor_map_set_scatter_size(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    mm = bec_figure.motor_map("samx", "samy")

    assert mm.config.scatter_size == 5
    assert mm.plot_components["scatter"].opts["size"] == 5

    mm.set_scatter_size(10)
    qtbot.wait(200)

    assert mm.config.scatter_size == 10
    assert mm.plot_components["scatter"].opts["size"] == 10


def test_motor_map_change_precision(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    mm = bec_figure.motor_map("samx", "samy")

    assert mm.config.precision == 2
    mm.set_precision(10)
    assert mm.config.precision == 10


def test_motor_map_set_color(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    mm = bec_figure.motor_map("samx", "samy")

    assert mm.config.color == (255, 255, 255, 255)

    mm.set_color((0, 0, 0, 255))
    qtbot.wait(200)
    assert mm.config.color == (0, 0, 0, 255)


def test_motor_map_get_data_max_points(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    mm = bec_figure.motor_map("samx", "samy")
    motor_map_dev = mm.client.device_manager.devices

    init_positions = {
        "samx": [motor_map_dev["samx"].read()["samx"]["value"]],
        "samy": [motor_map_dev["samy"].read()["samy"]["value"]],
    }
    msg = DeviceMessage(signals={"samx": {"value": 5.0}}, metadata={})
    mm.on_device_readback(msg.content, msg.metadata)
    msg = DeviceMessage(signals={"samy": {"value": 9.0}}, metadata={})
    mm.on_device_readback(msg.content, msg.metadata)
    msg = DeviceMessage(signals={"samx": {"value": 6.0}}, metadata={})
    mm.on_device_readback(msg.content, msg.metadata)
    msg = DeviceMessage(signals={"samy": {"value": 7.0}}, metadata={})
    mm.on_device_readback(msg.content, msg.metadata)

    expected_x = [init_positions["samx"][-1], 5.0, 5.0, 6.0, 6.0]
    expected_y = [init_positions["samy"][-1], init_positions["samy"][-1], 9.0, 9.0, 7.0]
    get_data = mm.get_data()

    assert mm.database_buffer["x"] == expected_x
    assert mm.database_buffer["y"] == expected_y
    assert get_data["x"] == expected_x
    assert get_data["y"] == expected_y

    mm.set_max_points(3)
    qtbot.wait(200)
    get_data = mm.get_data()
    assert len(get_data["x"]) == 3
    assert len(get_data["y"]) == 3
    assert get_data["x"] == expected_x[-3:]
    assert get_data["y"] == expected_y[-3:]
    assert mm.database_buffer["x"] == expected_x[-3:]
    assert mm.database_buffer["y"] == expected_y[-3:]
