# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
from unittest.mock import MagicMock, patch

import pytest
from bec_lib.devicemanager import DeviceContainer
from bec_widgets.examples.motor_movement.motor_control_compilations import (
    MotorControlApp,
    MotorControlMap,
    MotorControlPanel,
    MotorControlPanelAbsolute,
    MotorControlPanelRelative,
)

from bec_widgets.widgets.motor_control.motor_control import MotorActions, MotorThread
from bec_widgets.widgets.motor_control.motor_table.motor_table import MotorCoordinateTable
from bec_widgets.widgets.motor_control.movement_absolute.movement_absolute import (
    MotorControlAbsolute,
)
from bec_widgets.widgets.motor_control.movement_relative.movement_relative import (
    MotorControlRelative,
)
from bec_widgets.widgets.motor_control.selection.selection import MotorControlSelection

from .client_mocks import mocked_client

CONFIG_DEFAULT = {
    "motor_control": {
        "motor_x": "samx",
        "motor_y": "samy",
        "step_size_x": 3,
        "step_size_y": 3,
        "precision": 4,
        "step_x_y_same": False,
        "move_with_arrows": False,
    },
    "plot_settings": {
        "colormap": "Greys",
        "scatter_size": 5,
        "max_points": 1000,
        "num_dim_points": 100,
        "precision": 2,
        "num_columns": 1,
        "background_value": 25,
    },
    "motors": [
        {
            "plot_name": "Motor Map",
            "x_label": "Motor X",
            "y_label": "Motor Y",
            "signals": {
                "x": [{"name": "samx", "entry": "samx"}],
                "y": [{"name": "samy", "entry": "samy"}],
            },
        }
    ],
}


#######################################################
# Motor Thread
#######################################################
@pytest.fixture
def motor_thread(mocked_client):
    """Fixture for MotorThread with a mocked client."""
    return MotorThread(client=mocked_client)


def test_motor_thread_initialization(mocked_client):
    motor_thread = MotorThread(client=mocked_client)
    assert motor_thread.client == mocked_client
    assert isinstance(motor_thread.dev, DeviceContainer)


def test_get_all_motors_names(mocked_client):
    motor_thread = MotorThread(client=mocked_client)
    motor_names = motor_thread.get_all_motors_names()
    expected_names = ["samx", "samy", "aptrx", "aptry"]
    assert sorted(motor_names) == sorted(expected_names)
    assert all(name in motor_names for name in expected_names)
    assert len(motor_names) == len(expected_names)  # Ensure only these motors are returned


def test_get_coordinates(mocked_client):
    motor_thread = MotorThread(client=mocked_client)
    motor_x, motor_y = "samx", "samy"
    x, y = motor_thread.get_coordinates(motor_x, motor_y)

    assert x == mocked_client.device_manager.devices[motor_x].readback.get()
    assert y == mocked_client.device_manager.devices[motor_y].readback.get()


def test_move_motor_absolute_by_run(mocked_client):
    motor_thread = MotorThread(client=mocked_client)
    motor_thread.motor_x = "samx"
    motor_thread.motor_y = "samy"
    motor_thread.target_coordinates = (5.0, -3.0)
    motor_thread.action = MotorActions.MOVE_ABSOLUTE
    motor_thread.run()

    assert mocked_client.device_manager.devices["samx"].read_value == 5.0
    assert mocked_client.device_manager.devices["samy"].read_value == -3.0


def test_move_motor_relative_by_run(mocked_client):
    motor_thread = MotorThread(client=mocked_client)

    initial_value = motor_thread.dev["samx"].read()["samx"]["value"]
    move_value = 2.0
    expected_value = initial_value + move_value
    motor_thread.motor = "samx"
    motor_thread.value = move_value
    motor_thread.action = MotorActions.MOVE_RELATIVE
    motor_thread.run()

    assert mocked_client.device_manager.devices["samx"].read_value == expected_value


def test_motor_thread_move_absolute(motor_thread):
    motor_x = "samx"
    motor_y = "samy"
    target_x = 5.0
    target_y = -3.0

    motor_thread.move_absolute(motor_x, motor_y, (target_x, target_y))
    motor_thread.wait()

    assert motor_thread.dev[motor_x].read()["samx"]["value"] == target_x
    assert motor_thread.dev[motor_y].read()["samy"]["value"] == target_y


def test_motor_thread_move_relative(motor_thread):
    motor_name = "samx"
    move_value = 2.0

    initial_value = motor_thread.dev[motor_name].read()["samx"]["value"]
    motor_thread.move_relative(motor_name, move_value)
    motor_thread.wait()

    expected_value = initial_value + move_value
    assert motor_thread.dev[motor_name].read()["samx"]["value"] == expected_value


#######################################################
# Motor Control Widgets - MotorControlSelection
#######################################################
@pytest.fixture(scope="function")
def motor_selection_widget(qtbot, mocked_client, motor_thread):
    """Fixture for creating a MotorControlSelection widget with a mocked client."""
    widget = MotorControlSelection(
        client=mocked_client, config=CONFIG_DEFAULT, motor_thread=motor_thread
    )
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


def test_initialization_and_population(motor_selection_widget):
    assert motor_selection_widget.comboBox_motor_x.count() == 4
    assert motor_selection_widget.comboBox_motor_x.itemText(0) == "samx"
    assert motor_selection_widget.comboBox_motor_y.itemText(1) == "samy"
    assert motor_selection_widget.comboBox_motor_x.itemText(2) == "aptrx"
    assert motor_selection_widget.comboBox_motor_y.itemText(3) == "aptry"


def test_selection_and_signal_emission(motor_selection_widget):
    # Connect signal to a custom slot to capture the emitted values
    emitted_values = []

    def capture_emitted_values(motor_x, motor_y):
        emitted_values.append((motor_x, motor_y))

    motor_selection_widget.selected_motors_signal.connect(capture_emitted_values)

    # Select motors
    motor_selection_widget.comboBox_motor_x.setCurrentIndex(0)  # Select 'samx'
    motor_selection_widget.comboBox_motor_y.setCurrentIndex(1)  # Select 'samy'
    motor_selection_widget.pushButton_connecMotors.click()  # Emit the signal

    # Verify the emitted signal
    assert emitted_values == [
        ("samx", "samy")
    ], "The emitted signal did not match the expected values"


def test_configuration_update(motor_selection_widget):
    new_config = {"motor_control": {"motor_x": "samy", "motor_y": "samx"}}
    motor_selection_widget.on_config_update(new_config)
    assert motor_selection_widget.comboBox_motor_x.currentText() == "samy"
    assert motor_selection_widget.comboBox_motor_y.currentText() == "samx"


def test_enable_motor_controls(motor_selection_widget):
    motor_selection_widget.enable_motor_controls(False)
    assert not motor_selection_widget.comboBox_motor_x.isEnabled()
    assert not motor_selection_widget.comboBox_motor_y.isEnabled()

    motor_selection_widget.enable_motor_controls(True)
    assert motor_selection_widget.comboBox_motor_x.isEnabled()
    assert motor_selection_widget.comboBox_motor_y.isEnabled()


#######################################################
# Motor Control Widgets - MotorControlAbsolute
#######################################################


@pytest.fixture(scope="function")
def motor_absolute_widget(qtbot, mocked_client, motor_thread):
    widget = MotorControlAbsolute(
        client=mocked_client, config=CONFIG_DEFAULT, motor_thread=motor_thread
    )
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


def test_absolute_initialization(motor_absolute_widget):
    motor_absolute_widget.change_motors("samx", "samy")
    motor_absolute_widget.on_config_update(CONFIG_DEFAULT)
    assert motor_absolute_widget.motor_x == "samx", "Motor X not initialized correctly"
    assert motor_absolute_widget.motor_y == "samy", "Motor Y not initialized correctly"
    assert motor_absolute_widget.precision == CONFIG_DEFAULT["motor_control"]["precision"]


def test_absolute_save_current_coordinates(motor_absolute_widget):
    motor_x_value = motor_absolute_widget.client.device_manager.devices["samx"].read()["samx"][
        "value"
    ]
    motor_y_value = motor_absolute_widget.client.device_manager.devices["samy"].read()["samy"][
        "value"
    ]
    motor_absolute_widget.change_motors("samx", "samy")

    emitted_coordinates = []

    def capture_emit(x_y):
        emitted_coordinates.append(x_y)

    motor_absolute_widget.coordinates_signal.connect(capture_emit)

    # Trigger saving current coordinates
    motor_absolute_widget.ui.pushButton_save.click()

    assert emitted_coordinates == [(motor_x_value, motor_y_value)]


def test_absolute_set_absolute_coordinates(motor_absolute_widget):
    motor_absolute_widget.ui.spinBox_absolute_x.setValue(5)
    motor_absolute_widget.ui.spinBox_absolute_y.setValue(10)

    # Connect to the coordinates_signal to capture emitted values
    emitted_values = []

    def capture_coordinates(x_y):
        emitted_values.append(x_y)

    motor_absolute_widget.coordinates_signal.connect(capture_coordinates)

    # Simulate button click for absolute movement
    motor_absolute_widget.ui.pushButton_set.click()

    assert emitted_values == [(5, 10)]


def test_absolute_go_absolute_coordinates(motor_absolute_widget):
    motor_absolute_widget.change_motors("samx", "samy")

    motor_absolute_widget.ui.spinBox_absolute_x.setValue(5)
    motor_absolute_widget.ui.spinBox_absolute_y.setValue(10)

    with patch(
        "bec_widgets.widgets.motor_control.motor_control.MotorThread.move_absolute",
        new_callable=MagicMock,
    ) as mock_move_absolute:
        motor_absolute_widget.ui.pushButton_go_absolute.click()
        mock_move_absolute.assert_called_once_with("samx", "samy", (5, 10))


def test_change_motor_absolute(motor_absolute_widget):
    motor_absolute_widget.change_motors("aptrx", "aptry")

    assert motor_absolute_widget.motor_x == "aptrx"
    assert motor_absolute_widget.motor_y == "aptry"

    motor_absolute_widget.change_motors("samx", "samy")

    assert motor_absolute_widget.motor_x == "samx"
    assert motor_absolute_widget.motor_y == "samy"


def test_set_precision(motor_absolute_widget):
    motor_absolute_widget.on_config_update(CONFIG_DEFAULT)
    motor_absolute_widget.set_precision(2)

    assert motor_absolute_widget.ui.spinBox_absolute_x.decimals() == 2
    assert motor_absolute_widget.ui.spinBox_absolute_y.decimals() == 2


#######################################################
# Motor Control Widgets - MotorControlRelative
#######################################################
@pytest.fixture(scope="function")
def motor_relative_widget(qtbot, mocked_client, motor_thread):
    widget = MotorControlRelative(
        client=mocked_client, config=CONFIG_DEFAULT, motor_thread=motor_thread
    )
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


def test_initialization_and_config_update(motor_relative_widget):
    motor_relative_widget.on_config_update(CONFIG_DEFAULT)

    assert motor_relative_widget.motor_x == CONFIG_DEFAULT["motor_control"]["motor_x"]
    assert motor_relative_widget.motor_y == CONFIG_DEFAULT["motor_control"]["motor_y"]
    assert motor_relative_widget.precision == CONFIG_DEFAULT["motor_control"]["precision"]

    # Simulate a configuration update
    new_config = {
        "motor_control": {
            "motor_x": "new_motor_x",
            "motor_y": "new_motor_y",
            "precision": 2,
            "step_size_x": 5,
            "step_size_y": 5,
            "step_x_y_same": True,
            "move_with_arrows": True,
        }
    }
    motor_relative_widget.on_config_update(new_config)

    assert motor_relative_widget.motor_x == "new_motor_x"
    assert motor_relative_widget.motor_y == "new_motor_y"
    assert motor_relative_widget.precision == 2


def test_move_motor_relative(motor_relative_widget):
    motor_relative_widget.on_config_update(CONFIG_DEFAULT)
    # Set step sizes
    motor_relative_widget.ui.spinBox_step_x.setValue(1)
    motor_relative_widget.ui.spinBox_step_y.setValue(1)

    # Mock the move_relative method
    motor_relative_widget.motor_thread.move_relative = MagicMock()

    # Simulate button clicks
    motor_relative_widget.ui.toolButton_right.click()
    motor_relative_widget.motor_thread.move_relative.assert_called_with(
        motor_relative_widget.motor_x, 1
    )

    motor_relative_widget.ui.toolButton_left.click()
    motor_relative_widget.motor_thread.move_relative.assert_called_with(
        motor_relative_widget.motor_x, -1
    )

    motor_relative_widget.ui.toolButton_up.click()
    motor_relative_widget.motor_thread.move_relative.assert_called_with(
        motor_relative_widget.motor_y, 1
    )

    motor_relative_widget.ui.toolButton_down.click()
    motor_relative_widget.motor_thread.move_relative.assert_called_with(
        motor_relative_widget.motor_y, -1
    )


def test_precision_update(motor_relative_widget):
    # Capture emitted precision values
    emitted_values = []

    def capture_precision(precision):
        emitted_values.append(precision)

    motor_relative_widget.precision_signal.connect(capture_precision)

    # Update precision
    motor_relative_widget.ui.spinBox_precision.setValue(1)

    assert emitted_values == [1]
    assert motor_relative_widget.ui.spinBox_step_x.decimals() == 1
    assert motor_relative_widget.ui.spinBox_step_y.decimals() == 1


def test_sync_step_sizes(motor_relative_widget):
    motor_relative_widget.on_config_update(CONFIG_DEFAULT)
    motor_relative_widget.ui.checkBox_same_xy.setChecked(True)

    # Change step size for X
    motor_relative_widget.ui.spinBox_step_x.setValue(2)

    assert motor_relative_widget.ui.spinBox_step_y.value() == 2


def test_change_motor_relative(motor_relative_widget):
    motor_relative_widget.on_config_update(CONFIG_DEFAULT)
    motor_relative_widget.change_motors("aptrx", "aptry")

    assert motor_relative_widget.motor_x == "aptrx"
    assert motor_relative_widget.motor_y == "aptry"


#######################################################
# Motor Control Widgets - MotorCoordinateTable
#######################################################
@pytest.fixture(scope="function")
def motor_coordinate_table(qtbot, mocked_client, motor_thread):
    widget = MotorCoordinateTable(
        client=mocked_client, config=CONFIG_DEFAULT, motor_thread=motor_thread
    )
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


def test_delete_selected_row(motor_coordinate_table):
    # Add a coordinate
    motor_coordinate_table.add_coordinate((1.0, 2.0))
    motor_coordinate_table.add_coordinate((3.0, 4.0))

    # Select the row
    motor_coordinate_table.ui.table.selectRow(0)

    # Delete the selected row
    motor_coordinate_table.delete_selected_row()
    assert motor_coordinate_table.ui.table.rowCount() == 1


def test_add_coordinate_and_table_update(motor_coordinate_table):
    # Disable Warning message popups for test
    motor_coordinate_table.warning_message = False

    # Add coordinate in Individual mode
    motor_coordinate_table.add_coordinate((1.0, 2.0))
    assert motor_coordinate_table.ui.table.rowCount() == 1

    # Check if the coordinates match
    x_item_individual = motor_coordinate_table.ui.table.cellWidget(
        0, 3
    )  # Assuming X is in column 3
    y_item_individual = motor_coordinate_table.ui.table.cellWidget(
        0, 4
    )  # Assuming Y is in column 4
    assert float(x_item_individual.text()) == 1.0
    assert float(y_item_individual.text()) == 2.0

    # Switch to Start/Stop and add coordinates
    motor_coordinate_table.ui.comboBox_mode.setCurrentIndex(1)  # Switch mode

    motor_coordinate_table.add_coordinate((3.0, 4.0))
    motor_coordinate_table.add_coordinate((5.0, 6.0))
    assert motor_coordinate_table.ui.table.rowCount() == 1


def test_plot_coordinates_signal(motor_coordinate_table):
    # Connect to the signal
    def signal_emitted(coordinates, reference_tag, color):
        nonlocal received
        received = True
        assert len(coordinates) == 1  # Assuming one coordinate was added
        assert reference_tag in ["Individual", "Start", "Stop"]
        assert color in ["green", "blue", "red"]

    received = False
    motor_coordinate_table.plot_coordinates_signal.connect(signal_emitted)

    # Add a coordinate and check signal
    motor_coordinate_table.add_coordinate((1.0, 2.0))
    assert received


# def test_move_motor_action(motor_coordinate_table,qtbot):#TODO enable again after table refactor
#     # Add a coordinate
#     motor_coordinate_table.add_coordinate((1.0, 2.0))
#
#     # Mock the motor thread move_absolute function
#     motor_coordinate_table.motor_thread.move_absolute = MagicMock()
#
#     # Trigger the move action
#     move_button = motor_coordinate_table.table.cellWidget(0, 1)
#     move_button.click()
#
#     motor_coordinate_table.motor_thread.move_absolute.assert_called_with(
#         motor_coordinate_table.motor_x, motor_coordinate_table.motor_y, (1.0, 2.0)
#     )


def test_plot_coordinates_signal_individual(motor_coordinate_table, qtbot):
    motor_coordinate_table.warning_message = False
    motor_coordinate_table.set_precision(3)
    motor_coordinate_table.ui.comboBox_mode.setCurrentIndex(0)

    # This list will store the signals emitted during the test
    emitted_signals = []

    def signal_emitted(coordinates, reference_tag, color):
        emitted_signals.append((coordinates, reference_tag, color))

    motor_coordinate_table.plot_coordinates_signal.connect(signal_emitted)

    # Add new coordinates
    motor_coordinate_table.add_coordinate((1.0, 2.0))
    qtbot.wait(100)

    # Verify the signals
    assert len(emitted_signals) > 0, "No signals were emitted."

    for coordinates, reference_tag, color in emitted_signals:
        assert len(coordinates) > 0, "Coordinates list is empty."
        assert reference_tag == "Individual"
        assert color == "green"
        assert motor_coordinate_table.ui.table.cellWidget(0, 3).text() == "1.000"
        assert motor_coordinate_table.ui.table.cellWidget(0, 4).text() == "2.000"


#######################################################
# MotorControl examples compilations
#######################################################
@pytest.fixture(scope="function")
def motor_app(qtbot, mocked_client):
    widget = MotorControlApp(config=CONFIG_DEFAULT, client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_motor_app_initialization(motor_app):
    assert isinstance(motor_app, MotorControlApp)
    assert motor_app.client is not None
    assert motor_app.config == CONFIG_DEFAULT


@pytest.fixture(scope="function")
def motor_control_map(qtbot, mocked_client):
    widget = MotorControlMap(config=CONFIG_DEFAULT, client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_motor_control_map_initialization(motor_control_map):
    assert isinstance(motor_control_map, MotorControlMap)
    assert motor_control_map.client is not None
    assert motor_control_map.config == CONFIG_DEFAULT


@pytest.fixture(scope="function")
def motor_control_panel(qtbot, mocked_client):
    widget = MotorControlPanel(config=CONFIG_DEFAULT, client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_motor_control_panel_initialization(motor_control_panel):
    assert isinstance(motor_control_panel, MotorControlPanel)
    assert motor_control_panel.client is not None
    assert motor_control_panel.config == CONFIG_DEFAULT


@pytest.fixture(scope="function")
def motor_control_panel_absolute(qtbot, mocked_client):
    widget = MotorControlPanelAbsolute(config=CONFIG_DEFAULT, client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_motor_control_panel_absolute_initialization(motor_control_panel_absolute):
    assert isinstance(motor_control_panel_absolute, MotorControlPanelAbsolute)
    assert motor_control_panel_absolute.client is not None
    assert motor_control_panel_absolute.config == CONFIG_DEFAULT


@pytest.fixture(scope="function")
def motor_control_panel_relative(qtbot, mocked_client):
    widget = MotorControlPanelRelative(config=CONFIG_DEFAULT, client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_motor_control_panel_relative_initialization(motor_control_panel_relative):
    assert isinstance(motor_control_panel_relative, MotorControlPanelRelative)
    assert motor_control_panel_relative.client is not None
    assert motor_control_panel_relative.config == CONFIG_DEFAULT
