import numpy as np
import pyqtgraph as pg

from bec_widgets.widgets.plots.motor_map.motor_map import MotorMap
from tests.unit_tests.client_mocks import mocked_client

from .conftest import create_widget


def test_motor_map_initialization(qtbot, mocked_client):
    """Test the initialization of the MotorMap widget."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    # test default values
    assert mm.config.widget_class == "MotorMap"
    assert mm.config.scatter_size == 5
    assert mm.config.max_points == 5000
    assert mm.config.num_dim_points == 100
    assert mm.x_grid is True
    assert mm.y_grid is True


def test_motor_map_select_motor(qtbot, mocked_client):
    """Test selecting motors for the motor map."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    mm.map(x_name="samx", y_name="samy", validate_bec=True)

    assert mm.config.x_motor.name == "samx"
    assert mm.config.y_motor.name == "samy"
    assert mm.config.x_motor.limits == [-10, 10]
    assert mm.config.y_motor.limits == [-5, 5]
    assert mm.config.scatter_size == 5
    assert mm.config.max_points == 5000
    assert mm.config.num_dim_points == 100
    assert mm.x_grid is True
    assert mm.y_grid is True


def test_motor_map_properties(qtbot, mocked_client):
    """Test setting and getting properties of MotorMap."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map(x_name="samx", y_name="samy")

    # Test color property
    mm.color = (100, 150, 200, 255)
    assert mm.color == (100, 150, 200, 255)

    mm.color = "#FF5500"  # Test hex color
    assert mm.color[0] == 255
    assert mm.color[1] == 85
    assert mm.color[2] == 0

    # Test scatter_size property
    mm.scatter_size = 10
    qtbot.wait(200)
    assert mm.scatter_size == 10
    assert mm.config.scatter_size == 10
    assert mm._trace.opts["size"] == 10

    # Test max_points property
    mm.max_points = 2000
    assert mm.max_points == 2000
    assert mm.config.max_points == 2000

    # Test precision property
    mm.precision = 3
    assert mm.precision == 3
    assert mm.config.precision == 3

    # Test num_dim_points property
    mm.num_dim_points = 50
    assert mm.num_dim_points == 50
    assert mm.config.num_dim_points == 50

    # Test background_value property
    mm.background_value = 40
    qtbot.wait(200)
    assert mm.background_value == 40
    assert mm.config.background_value == 40
    filled_rect = mm._limit_map
    rect_color = filled_rect._brush.color().getRgb()
    expected = (40, 40, 40, 150)
    assert rect_color == expected


def test_motor_map_get_limits(qtbot, mocked_client):
    """Test getting motor limits."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map(x_name="samx", y_name="samy")
    expected_limits = {"samx": [-10, 10], "samy": [-5, 5]}

    for motor_name, expected_limit in expected_limits.items():
        actual_limit = mm._get_motor_limit(motor_name)
        assert actual_limit == expected_limit


def test_motor_map_get_init_position(qtbot, mocked_client):
    """Test getting the initial position of motors."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map("samx", "samy")
    mm.precision = 2

    motor_map_dev = mm.client.device_manager.devices

    expected_positions = {
        ("samx", "samx"): motor_map_dev["samx"].read()["samx"]["value"],
        ("samy", "samy"): motor_map_dev["samy"].read()["samy"]["value"],
    }

    for (motor_name, entry), expected_position in expected_positions.items():
        actual_position = mm._get_motor_init_position(motor_name, 2)
        assert actual_position == expected_position


def test_motor_map_reset_history(qtbot, mocked_client):
    """Test resetting the history of motor positions."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map(motor_x="samx", motor_y="samy")

    # Simulate some motor movement history
    mm._buffer = {"x": [1.0, 2.0, 3.0, 4.0], "y": [5.0, 6.0, 7.0, 8.0]}

    # Reset history
    mm.reset_history()

    # Should keep only the last point
    assert len(mm._buffer["x"]) == 1
    assert len(mm._buffer["y"]) == 1
    assert mm._buffer["x"][0] == 4.0
    assert mm._buffer["y"][0] == 8.0


def test_motor_map_on_device_readback(qtbot, mocked_client):
    """Test the motor map updates when receiving device readback."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map(x_name="samx", y_name="samy")

    # Clear the buffer and add initial position
    mm._buffer = {"x": [1.0], "y": [2.0]}

    # Simulate device readback for x motor
    msg_x = {"signals": {"samx": {"value": 3.0}}}
    mm.on_device_readback(msg_x, {})
    qtbot.wait(200)  # Allow time for the update to process

    assert len(mm._buffer["x"]) == 2
    assert len(mm._buffer["y"]) == 2
    assert mm._buffer["x"][1] == 3.0
    assert mm._buffer["y"][1] == 2.0  # Y should remain the same

    # Simulate device readback for y motor
    msg_y = {"signals": {"samy": {"value": 4.0}}}
    mm.on_device_readback(msg_y, {})

    assert len(mm._buffer["x"]) == 3
    assert len(mm._buffer["y"]) == 3
    assert mm._buffer["x"][2] == 3.0  # X should remain the same
    assert mm._buffer["y"][2] == 4.0


def test_motor_map_max_points_limit(qtbot, mocked_client):
    """Test that the buffer doesn't exceed max_points."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map(x_name="samx", y_name="samy")

    # Add more points than max_points
    mm._buffer = {"x": [1.0, 2.0, 3.0, 4.0], "y": [5.0, 6.0, 7.0, 8.0]}

    mm.config.max_points = 3
    # Trigger update that should trim buffer
    mm._update_plot()

    # Check that buffer was trimmed to max_points
    assert len(mm._buffer["x"]) == 3
    assert len(mm._buffer["y"]) == 3
    # Should keep the most recent points
    assert mm._buffer["x"] == [2.0, 3.0, 4.0]
    assert mm._buffer["y"] == [6.0, 7.0, 8.0]


def test_motor_map_crosshair_creation(qtbot, mocked_client):
    """Test the creation of the coordinate crosshair."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    # The Initial state should be None
    assert mm.v_line is None
    assert mm.h_line is None
    assert mm.coord_label is None

    # Create the crosshair
    mm._add_coordinates_crosshair(3.0, 4.0)

    # Check if crosshair elements were created
    assert mm.v_line is not None
    assert mm.h_line is not None
    assert mm.coord_label is not None

    # Test position
    assert mm.v_line.value() == 3.0
    assert mm.h_line.value() == 4.0


def test_motor_map_limit_map(qtbot, mocked_client):
    """Test the creation of the limit map."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    # Create a limit map
    limit_map = mm._make_limit_map([0, 10], [0, 5])

    from qtpy import QtCore

    from bec_widgets.widgets.plots.motor_map.motor_map import FilledRectItem

    assert isinstance(limit_map, FilledRectItem)
    rect = limit_map.boundingRect()
    # For [0,10] on x and [0,5] on y, width=10, height=5
    assert rect == QtCore.QRectF(0, 0, 10, 5)


def test_motor_map_change_limits(qtbot, mocked_client):
    mm = create_widget(qtbot, MotorMap, client=mocked_client)
    mm.map(x_name="samx", y_name="samy")

    # Original mocked limits are
    # samx: [-10, 10]
    # samy: [-5, 5]

    # Original Limits Map
    rect = mm._limit_map.boundingRect()
    assert rect.width() == 20  # -10 to 10 inclusive
    assert rect.height() == 10  # -5 to 5 inclusive
    assert mm.config.x_motor.limits == [-10, 10]
    assert mm.config.y_motor.limits == [-5, 5]

    # Change the limits of the samx motor
    mm.dev["samx"].limits = [-20, 20]
    msg = {"signals": {"high": {"value": 20}, "low": {"value": -20}}}
    mm.on_device_limits(msg, {})
    qtbot.wait(200)  # Allow time for the update to process

    # Check that the limits map was updated
    assert mm.config.x_motor.limits == [-20, 20]
    assert mm.config.y_motor.limits == [-5, 5]
    rect = mm._limit_map.boundingRect()
    assert rect.width() == 40  # -20 to 20 inclusive
    assert rect.height() == 10  # -5 to 5 inclusive -> same as before

    # Change back the limits
    mm.dev["samx"].limits = [-10, 10]


def test_motor_map_get_data(qtbot, mocked_client):
    """Test getting data from the motor map."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    # Set up some test data
    mm._buffer = {"x": [1.0, 2.0, 3.0], "y": [4.0, 5.0, 6.0]}

    # Get data
    data = mm.get_data()

    # Check that the data is correct
    assert "x" in data
    assert "y" in data
    assert data["x"] == [1.0, 2.0, 3.0]
    assert data["y"] == [4.0, 5.0, 6.0]


def test_motor_map_toolbar_selection(qtbot, mocked_client):
    """Test motor selection via the toolbar bundle."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client)

    # Verify toolbar bundle was created during initialization
    assert hasattr(mm, "motor_selection_bundle")
    assert mm.motor_selection_bundle is not None

    mm.motor_selection_bundle.motor_x.setCurrentText("samx")
    mm.motor_selection_bundle.motor_y.setCurrentText("samy")

    assert mm.config.x_motor.name == "samx"
    assert mm.config.y_motor.name == "samy"

    mm.motor_selection_bundle.motor_y.setCurrentText("samz")

    assert mm.config.x_motor.name == "samx"
    assert mm.config.y_motor.name == "samz"


def test_motor_map_settings_dialog(qtbot, mocked_client):
    """Test the settings dialog for the motor map."""
    mm = create_widget(qtbot, MotorMap, client=mocked_client, popups=True)

    assert "popup_bundle" in mm.toolbar.bundles
    for action_id in mm.toolbar.bundles["popup_bundle"]:
        assert mm.toolbar.widgets[action_id].action.isVisible() is True

    # set properties to be fetched by dialog
    mm.map(x_name="samx", y_name="samy")
    mm.precision = 2
    mm.max_points = 1000
    mm.scatter_size = 10
    mm.background_value = 50
    mm.num_dim_points = 20
    mm.color = (255, 0, 0, 255)

    mm.show_motor_map_settings()
    qtbot.wait(200)

    assert mm.motor_map_settings is not None
    assert mm.motor_map_settings.isVisible() is True

    # Check that the settings dialog has the correct values
    assert mm.motor_map_settings.widget.ui.precision.value() == 2
    assert mm.motor_map_settings.widget.ui.max_points.value() == 1000
    assert mm.motor_map_settings.widget.ui.scatter_size.value() == 10
    assert mm.motor_map_settings.widget.ui.background_value.value() == 50
    assert mm.motor_map_settings.widget.ui.num_dim_points.value() == 20
    assert mm.motor_map_settings.widget.ui.color_scatter.get_color(format="RGBA") == (
        255,
        0,
        0,
        255,
    )

    mm.motor_map_settings.close()
    qtbot.wait(200)
    assert mm.motor_map_settings is None
