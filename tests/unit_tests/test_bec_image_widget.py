from unittest.mock import MagicMock, patch

import pyqtgraph as pg
import pytest

from bec_widgets.widgets.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.image.image_widget import BECImageWidget

from .client_mocks import mocked_client


@pytest.fixture
def image_widget(qtbot, mocked_client):
    widget = BECImageWidget(client=mocked_client())
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def mock_image(image_widget):
    image_mock = MagicMock()
    image_widget._image = image_mock
    return image_mock


def test_image_widget_init(image_widget):
    assert image_widget is not None
    assert image_widget.client is not None
    assert isinstance(image_widget, BECImageWidget)
    assert image_widget.config.widget_class == "BECImageWidget"
    assert image_widget._image is not None

    assert (
        BECDeviceFilter.DEVICE
        in image_widget.toolbar.widgets["monitor"].device_combobox.config.device_filter
    )
    assert image_widget.toolbar.widgets["drag_mode"].action.isChecked() == True
    assert image_widget.toolbar.widgets["rectangle_mode"].action.isChecked() == False
    assert image_widget.toolbar.widgets["auto_range"].action.isChecked() == False
    assert image_widget.toolbar.widgets["auto_range_image"].action.isChecked() == True
    assert image_widget.toolbar.widgets["FFT"].action.isChecked() == False
    assert image_widget.toolbar.widgets["transpose"].action.isChecked() == False
    assert image_widget.toolbar.widgets["log"].action.isChecked() == False


###################################
# Toolbar Actions
###################################
def test_toolbar_connect_action(image_widget, mock_image, qtbot):
    combo_device = image_widget.toolbar.widgets["monitor"].device_combobox
    combo_device.setCurrentText("eiger")
    qtbot.wait(200)
    assert combo_device.currentText() == "eiger"
    combo_dim = image_widget.toolbar.widgets["monitor_type"].widget
    combo_dim.setCurrentText("2d")
    qtbot.wait(200)
    assert combo_dim.currentText() == "2d"
    action = image_widget.toolbar.widgets["connect"].action
    action.trigger()
    image_widget._image.image.assert_called_once_with(
        monitor="eiger",
        monitor_type="2d",
        color_map="magma",
        color_bar="full",
        downsample=True,
        opacity=1.0,
        vrange=None,
    )


def test_image_toolbar_drag_mode_action_triggered(image_widget, qtbot):
    action_drag = image_widget.toolbar.widgets["drag_mode"].action
    action_rectangle = image_widget.toolbar.widgets["rectangle_mode"].action
    action_drag.trigger()
    assert action_drag.isChecked() == True
    assert action_rectangle.isChecked() == False


def test_image_toolbar_rectangle_mode_action_triggered(image_widget, qtbot):
    action_drag = image_widget.toolbar.widgets["drag_mode"].action
    action_rectangle = image_widget.toolbar.widgets["rectangle_mode"].action
    action_rectangle.trigger()
    assert action_drag.isChecked() == False
    assert action_rectangle.isChecked() == True


def test_image_toolbar_auto_range(image_widget, mock_image):
    action = image_widget.toolbar.widgets["auto_range"].action
    action.trigger()
    image_widget._image.set_auto_range.assert_called_once_with(True, "xy")


def test_image_toolbar_enable_mouse_pan_mode(qtbot, image_widget):
    action_drag = image_widget.toolbar.widgets["drag_mode"].action
    action_rectangle = image_widget.toolbar.widgets["rectangle_mode"].action

    mock_view_box = MagicMock()
    image_widget._image.plot_item.getViewBox = MagicMock(return_value=mock_view_box)

    image_widget.enable_mouse_pan_mode()

    assert action_drag.isChecked() == True
    assert action_rectangle.isChecked() == False
    mock_view_box.setMouseMode.assert_called_once_with(pg.ViewBox.PanMode)


def test_image_toolbar_auto_range_image(image_widget, mock_image):
    action = image_widget.toolbar.widgets["auto_range_image"].action
    action.trigger()
    assert action.isChecked() == False
    image_widget._image.set_autorange.assert_called_once_with(False)


def test_image_toolbar_FFT(image_widget, mock_image):
    action = image_widget.toolbar.widgets["FFT"].action
    action.trigger()
    assert action.isChecked() == True
    image_widget._image.set_fft.assert_called_once_with(True, None)


def test_image_toolbar_log(image_widget, mock_image):
    action = image_widget.toolbar.widgets["log"].action
    action.trigger()
    assert action.isChecked() == True
    image_widget._image.set_log.assert_called_once_with(True, None)


def test_image_toggle_transpose(image_widget, mock_image):
    action = image_widget.toolbar.widgets["transpose"].action
    action.trigger()
    assert action.isChecked() == True
    image_widget._image.set_transpose.assert_called_once_with(True, None)


def test_image_toolbar_rotation(image_widget, mock_image):
    action_left = image_widget.toolbar.widgets["rotate_left"].action
    action_right = image_widget.toolbar.widgets["rotate_right"].action

    action_left.trigger()
    image_widget._image.set_rotation(1, None)
    action_right.trigger()
    image_widget._image.set_rotation(2, None)

    action_right.trigger()
    image_widget._image.set_rotation(1, None)


###################################
# Wrapper methods for ImageShow
###################################


def test_image_set_image(image_widget, mock_image):
    image_widget.image(monitor="image", monitor_type="2d")
    image_widget._image.image.assert_called_once_with(
        monitor="image",
        monitor_type="2d",
        color_map="magma",
        color_bar="full",
        downsample=True,
        opacity=1.0,
        vrange=None,
    )


def test_image_vrange(image_widget, mock_image):
    image_widget.set_vrange(0, 1)
    image_widget._image.set_vrange.assert_called_once_with(0, 1, None)


def test_image_set_color_map(image_widget, mock_image):
    image_widget.set_color_map("viridis")
    image_widget._image.set_color_map.assert_called_once_with("viridis", None)


def test_image_widget_set_title(image_widget, mock_image):
    image_widget.set_title("Title Label")
    image_widget._image.set_title.assert_called_once_with("Title Label")


def test_image_widget_set_x_label(image_widget, mock_image):
    image_widget.set_x_label("X Label")
    image_widget._image.set_x_label.assert_called_once_with("X Label")


def test_image_widget_set_y_label(image_widget, mock_image):
    image_widget.set_y_label("Y Label")
    image_widget._image.set_y_label.assert_called_once_with("Y Label")


def test_image_widget_set_x_scale(image_widget, mock_image):
    image_widget.set_x_scale("linear")
    image_widget._image.set_x_scale.assert_called_once_with("linear")


def test_image_widget_set_y_scale(image_widget, mock_image):
    image_widget.set_y_scale("log")
    image_widget._image.set_y_scale.assert_called_once_with("log")


def test_image_widget_set_x_lim(image_widget, mock_image):
    image_widget.set_x_lim((0, 10))
    image_widget._image.set_x_lim.assert_called_once_with((0, 10))


def test_image_widget_set_y_lim(image_widget, mock_image):
    image_widget.set_y_lim((0, 10))
    image_widget._image.set_y_lim.assert_called_once_with((0, 10))


def test_image_widget_set_grid(image_widget, mock_image):
    image_widget.set_grid(True, False)
    image_widget._image.set_grid.assert_called_once_with(True, False)


def test_image_widget_lock_aspect_ratio(image_widget, mock_image):
    image_widget.lock_aspect_ratio(True)
    image_widget._image.lock_aspect_ratio.assert_called_once_with(True)


def test_image_widget_export(image_widget, mock_image):
    image_widget.export()
    image_widget._image.export.assert_called_once()
