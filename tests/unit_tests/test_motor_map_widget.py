from unittest.mock import MagicMock, patch

import pytest

from bec_widgets.widgets.motor_map.motor_map_dialog.motor_map_settings import MotorMapSettings
from bec_widgets.widgets.motor_map.motor_map_widget import BECMotorMapWidget

from .client_mocks import mocked_client


@pytest.fixture
def motor_map_widget(qtbot, mocked_client):
    widget = BECMotorMapWidget(client=mocked_client())
    widget.toolbar.widgets["motor_x"].device_combobox.set_device_filter("FakePositioner")
    widget.toolbar.widgets["motor_y"].device_combobox.set_device_filter("FakePositioner")
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


@pytest.fixture
def mock_motor_map(motor_map_widget):
    motor_map_mock = MagicMock()
    motor_map_widget.map = motor_map_mock
    return motor_map_mock


def test_motor_map_widget_init(motor_map_widget):
    assert motor_map_widget is not None
    assert motor_map_widget.client is not None
    assert isinstance(motor_map_widget, BECMotorMapWidget)
    assert motor_map_widget.config.widget_class == "BECMotorMapWidget"

    # check initial state of toolbar actions
    assert motor_map_widget.toolbar.widgets["connect"].action.isEnabled() == True
    assert motor_map_widget.toolbar.widgets["config"].action.isEnabled() == False
    assert motor_map_widget.toolbar.widgets["history"].action.isEnabled() == False
    assert (
        motor_map_widget.toolbar.widgets["motor_x"].device_combobox.config.device_filter
        == "FakePositioner"
    )
    assert (
        motor_map_widget.toolbar.widgets["motor_y"].device_combobox.config.device_filter
        == "FakePositioner"
    )
    assert motor_map_widget.map.motor_x is None
    assert motor_map_widget.map.motor_y is None


###################################
# Toolbar Actions
###################################


def test_motor_map_widget_change_motors_enable_toolbar(motor_map_widget):
    motor_map_widget.change_motors("samx", "samy")
    assert motor_map_widget.map.motor_x == "samx"
    assert motor_map_widget.map.motor_y == "samy"
    assert motor_map_widget.toolbar.widgets["motor_x"].device_combobox.currentText() == "samx"
    assert motor_map_widget.toolbar.widgets["motor_y"].device_combobox.currentText() == "samy"
    assert motor_map_widget.toolbar.widgets["config"].action.isEnabled() == True
    assert motor_map_widget.toolbar.widgets["history"].action.isEnabled() == True


###################################
# Wrapper methods for MotorMap
###################################


def test_change_motors(motor_map_widget, mock_motor_map):
    motor_map_widget.change_motors("motor_x", "motor_y", "motor_x_entry", "motor_y_entry", True)
    mock_motor_map.change_motors.assert_called_once_with(
        "motor_x", "motor_y", "motor_x_entry", "motor_y_entry", True
    )


def test_get_data(motor_map_widget, mock_motor_map):
    motor_map_widget.get_data()
    mock_motor_map.get_data.assert_called_once()


def test_reset_history(motor_map_widget, mock_motor_map):
    motor_map_widget.reset_history()
    mock_motor_map.reset_history.assert_called_once()


def test_set_color(motor_map_widget, mock_motor_map):
    motor_map_widget.set_color("blue")
    mock_motor_map.set_color.assert_called_once_with("blue")


def test_set_max_points(motor_map_widget, mock_motor_map):
    motor_map_widget.set_max_points(100)
    mock_motor_map.set_max_points.assert_called_once_with(100)


def test_set_precision(motor_map_widget, mock_motor_map):
    motor_map_widget.set_precision(2)
    mock_motor_map.set_precision.assert_called_once_with(2)


def test_set_num_dim_points(motor_map_widget, mock_motor_map):
    motor_map_widget.set_num_dim_points(50)
    mock_motor_map.set_num_dim_points.assert_called_once_with(50)


def test_set_background_value(motor_map_widget, mock_motor_map):
    motor_map_widget.set_background_value(128)
    mock_motor_map.set_background_value.assert_called_once_with(128)


def test_set_scatter_size(motor_map_widget, mock_motor_map):
    motor_map_widget.set_scatter_size(10)
    mock_motor_map.set_scatter_size.assert_called_once_with(10)


###################################
# MotorMap Dialog
###################################


def test_motor_map_widget_clicked(motor_map_widget, qtbot):
    motor_map_widget.toolbar.widgets["motor_x"].device_combobox.setCurrentText("samx")
    motor_map_widget.toolbar.widgets["motor_y"].device_combobox.setCurrentText("samy")
    motor_map_widget.toolbar.widgets["connect"].action.trigger()

    qtbot.wait(200)

    assert motor_map_widget.map.motor_x == "samx"
    assert motor_map_widget.map.motor_y == "samy"
    assert motor_map_widget.toolbar.widgets["config"].action.isEnabled() == True
    assert motor_map_widget.toolbar.widgets["history"].action.isEnabled() == True


@pytest.fixture
def motor_map_settings(qtbot):
    widget = MotorMapSettings()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


def test_display_current_settings(motor_map_settings):
    config = {
        "max_points": 100,
        "num_dim_points": 50,
        "precision": 2,
        "scatter_size": 10,
        "background_value": 128,
        "color": (255, 0, 0, 255),
    }

    with patch("bec_widgets.utils.widget_io.WidgetIO.set_value") as mock_set_value:
        with patch.object(motor_map_settings.ui.color, "setColor") as mock_set_color:
            motor_map_settings.display_current_settings(config)
            mock_set_value.assert_any_call(motor_map_settings.ui.max_points, config["max_points"])
            mock_set_value.assert_any_call(
                motor_map_settings.ui.trace_dim, config["num_dim_points"]
            )
            mock_set_value.assert_any_call(motor_map_settings.ui.precision, config["precision"])
            mock_set_value.assert_any_call(
                motor_map_settings.ui.scatter_size, config["scatter_size"]
            )
            mock_set_value.assert_any_call(
                motor_map_settings.ui.background_value, 50
            )  # 128/255*100 = 50
            mock_set_color.assert_called_once_with(config["color"])


def test_accept_changes(motor_map_settings):
    with patch(
        "bec_widgets.utils.widget_io.WidgetIO.get_value", side_effect=[100, 50, 2, 10, 50]
    ) as mock_get_value:
        with patch.object(
            motor_map_settings.ui.color, "get_color", return_value=(255, 0, 0, 255)
        ) as mock_get_color:
            mock_target_widget = MagicMock()
            motor_map_settings.set_target_widget(mock_target_widget)

            motor_map_settings.accept_changes()

            mock_get_value.assert_any_call(motor_map_settings.ui.max_points)
            mock_get_value.assert_any_call(motor_map_settings.ui.trace_dim)
            mock_get_value.assert_any_call(motor_map_settings.ui.precision)
            mock_get_value.assert_any_call(motor_map_settings.ui.scatter_size)
            mock_get_value.assert_any_call(motor_map_settings.ui.background_value)
            mock_get_color.assert_called_once()

            mock_target_widget.set_max_points.assert_called_once_with(100)
            mock_target_widget.set_num_dim_points.assert_called_once_with(50)
            mock_target_widget.set_precision.assert_called_once_with(2)
            mock_target_widget.set_scatter_size.assert_called_once_with(10)
            mock_target_widget.set_background_value.assert_called_once_with(127)
            mock_target_widget.set_color.assert_called_once_with((255, 0, 0, 255))
