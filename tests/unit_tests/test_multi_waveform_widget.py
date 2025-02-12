from unittest.mock import MagicMock, patch

import pytest
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication

from bec_widgets.qt_utils.settings_dialog import SettingsDialog
from bec_widgets.utils.colors import apply_theme, get_theme_palette, set_theme
from bec_widgets.widgets.containers.figure.plots.axis_settings import AxisSettings
from bec_widgets.widgets.plots.multi_waveform.multi_waveform_widget import BECMultiWaveformWidget

from .client_mocks import mocked_client


@pytest.fixture
def multi_waveform_widget(qtbot, mocked_client):
    widget = BECMultiWaveformWidget(client=mocked_client())
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


@pytest.fixture
def mock_waveform(multi_waveform_widget):
    waveform_mock = MagicMock()
    multi_waveform_widget.waveform = waveform_mock
    return waveform_mock


def test_multi_waveform_widget_init(multi_waveform_widget):
    assert multi_waveform_widget is not None
    assert multi_waveform_widget.client is not None
    assert isinstance(multi_waveform_widget, BECMultiWaveformWidget)
    assert multi_waveform_widget.config.widget_class == "BECMultiWaveformWidget"


###################################
# Wrapper methods for Waveform
###################################


def test_multi_waveform_widget_set_monitor(multi_waveform_widget, mock_waveform):
    multi_waveform_widget.set_monitor("waveform1d")
    mock_waveform.set_monitor.assert_called_once_with("waveform1d")


def test_multi_waveform_widget_set_curve_highlight_last_active(
    multi_waveform_widget, mock_waveform
):
    multi_waveform_widget.set_curve_highlight(1)
    mock_waveform.set_curve_highlight.assert_called_once_with(-1)


def test_multi_waveform_widget_set_curve_highlight_last_not_active(
    multi_waveform_widget, mock_waveform
):
    multi_waveform_widget.set_highlight_last_curve(False)
    multi_waveform_widget.set_curve_highlight(1)
    mock_waveform.set_curve_highlight.assert_called_with(1)


def test_multi_waveform_widget_set_opacity(multi_waveform_widget, mock_waveform):
    multi_waveform_widget.set_opacity(50)
    mock_waveform.set_opacity.assert_called_once_with(50)


def test_multi_waveform_widget_set_curve_limit(multi_waveform_widget, mock_waveform):
    multi_waveform_widget.set_curve_limit(10)
    mock_waveform.set_curve_limit.assert_called_once_with(
        10, multi_waveform_widget.controls.checkbox_flush_buffer.isChecked()
    )


def test_multi_waveform_widget_set_buffer_flush(multi_waveform_widget, mock_waveform):
    multi_waveform_widget.set_buffer_flush(True)
    mock_waveform.set_curve_limit.assert_called_once_with(
        multi_waveform_widget.controls.spinbox_max_trace.value(), True
    )


def test_multi_waveform_widget_set_highlight_last_curve(multi_waveform_widget, mock_waveform):
    multi_waveform_widget.set_highlight_last_curve(True)
    assert multi_waveform_widget.waveform.config.highlight_last_curve is True
    assert not multi_waveform_widget.controls.slider_index.isEnabled()
    assert not multi_waveform_widget.controls.spinbox_index.isEnabled()
    mock_waveform.set_curve_highlight.assert_called_once_with(-1)


def test_multi_waveform_widget_set_colormap(multi_waveform_widget, mock_waveform):
    multi_waveform_widget.set_colormap("viridis")
    mock_waveform.set_colormap.assert_called_once_with("viridis")


def test_multi_waveform_widget_set_base(multi_waveform_widget, mock_waveform):
    multi_waveform_widget.set(
        title="Test Title",
        x_label="X Label",
        y_label="Y Label",
        x_scale="linear",
        y_scale="log",
        x_lim=(0, 10),
        y_lim=(0, 10),
    )
    mock_waveform.set.assert_called_once_with(
        title="Test Title",
        x_label="X Label",
        y_label="Y Label",
        x_scale="linear",
        y_scale="log",
        x_lim=(0, 10),
        y_lim=(0, 10),
    )


###################################
# Toolbar interactions
###################################


def test_toolbar_connect_action_triggered(multi_waveform_widget, qtbot):
    action_connect = multi_waveform_widget.toolbar.widgets["connect"].action
    device_combobox = multi_waveform_widget.toolbar.widgets["monitor"].device_combobox
    device_combobox.addItem("test_monitor")
    device_combobox.setCurrentText("test_monitor")

    with patch.object(multi_waveform_widget, "set_monitor") as mock_set_monitor:
        action_connect.trigger()
        mock_set_monitor.assert_called_once_with(monitor="test_monitor")


def test_toolbar_drag_mode_action_triggered(multi_waveform_widget, qtbot):
    action_drag = multi_waveform_widget.toolbar.widgets["drag_mode"].action
    action_rectangle = multi_waveform_widget.toolbar.widgets["rectangle_mode"].action
    action_drag.trigger()
    assert action_drag.isChecked() == True
    assert action_rectangle.isChecked() == False


def test_toolbar_rectangle_mode_action_triggered(multi_waveform_widget, qtbot):
    action_drag = multi_waveform_widget.toolbar.widgets["drag_mode"].action
    action_rectangle = multi_waveform_widget.toolbar.widgets["rectangle_mode"].action
    action_rectangle.trigger()
    assert action_drag.isChecked() == False
    assert action_rectangle.isChecked() == True


def test_toolbar_auto_range_action_triggered(multi_waveform_widget, mock_waveform, qtbot):
    action = multi_waveform_widget.toolbar.widgets["auto_range"].action
    action.trigger()
    qtbot.wait(200)
    mock_waveform.set_auto_range.assert_called_once_with(True, "xy")


###################################
# Control Panel interactions
###################################


def test_controls_opacity_slider(multi_waveform_widget, mock_waveform):
    multi_waveform_widget.controls.slider_opacity.setValue(75)
    mock_waveform.set_opacity.assert_called_with(75)
    assert multi_waveform_widget.controls.spinbox_opacity.value() == 75


def test_controls_opacity_spinbox(multi_waveform_widget, mock_waveform):
    multi_waveform_widget.controls.spinbox_opacity.setValue(25)
    mock_waveform.set_opacity.assert_called_with(25)
    assert multi_waveform_widget.controls.slider_opacity.value() == 25


def test_controls_max_trace_spinbox(multi_waveform_widget, mock_waveform):
    multi_waveform_widget.controls.spinbox_max_trace.setValue(15)
    mock_waveform.set_curve_limit.assert_called_with(
        15, multi_waveform_widget.controls.checkbox_flush_buffer.isChecked()
    )


def test_controls_flush_buffer_checkbox(multi_waveform_widget, mock_waveform):
    multi_waveform_widget.controls.checkbox_flush_buffer.setChecked(True)
    mock_waveform.set_curve_limit.assert_called_with(
        multi_waveform_widget.controls.spinbox_max_trace.value(), True
    )


def test_controls_highlight_checkbox(multi_waveform_widget, mock_waveform):
    multi_waveform_widget.controls.checkbox_highlight.setChecked(False)
    assert multi_waveform_widget.waveform.config.highlight_last_curve is False
    assert multi_waveform_widget.controls.slider_index.isEnabled()
    assert multi_waveform_widget.controls.spinbox_index.isEnabled()
    index = multi_waveform_widget.controls.spinbox_index.value()
    mock_waveform.set_curve_highlight.assert_called_with(index)


###################################
# Axis Settings Dialog Tests
###################################


def show_axis_dialog(qtbot, multi_waveform_widget):
    axis_dialog = SettingsDialog(
        multi_waveform_widget,
        settings_widget=AxisSettings(),
        window_title="Axis Settings",
        config=multi_waveform_widget.waveform._config_dict["axis"],
    )
    qtbot.addWidget(axis_dialog)
    qtbot.waitExposed(axis_dialog)
    return axis_dialog


def test_axis_dialog_with_axis_limits(qtbot, multi_waveform_widget):
    multi_waveform_widget.set(
        title="Test Title",
        x_label="X Label",
        y_label="Y Label",
        x_scale="linear",
        y_scale="log",
        x_lim=(0, 10),
        y_lim=(0, 10),
    )

    axis_dialog = show_axis_dialog(qtbot, multi_waveform_widget)

    assert axis_dialog is not None
    assert axis_dialog.widget.ui.plot_title.text() == "Test Title"
    assert axis_dialog.widget.ui.x_label.text() == "X Label"
    assert axis_dialog.widget.ui.y_label.text() == "Y Label"
    assert axis_dialog.widget.ui.x_scale.currentText() == "linear"
    assert axis_dialog.widget.ui.y_scale.currentText() == "log"
    assert axis_dialog.widget.ui.x_min.value() == 0
    assert axis_dialog.widget.ui.x_max.value() == 10
    assert axis_dialog.widget.ui.y_min.value() == 0
    assert axis_dialog.widget.ui.y_max.value() == 10


def test_axis_dialog_set_properties(qtbot, multi_waveform_widget):
    axis_dialog = show_axis_dialog(qtbot, multi_waveform_widget)

    axis_dialog.widget.ui.plot_title.setText("New Title")
    axis_dialog.widget.ui.x_label.setText("New X Label")
    axis_dialog.widget.ui.y_label.setText("New Y Label")
    axis_dialog.widget.ui.x_scale.setCurrentText("log")
    axis_dialog.widget.ui.y_scale.setCurrentText("linear")
    axis_dialog.widget.ui.x_min.setValue(5)
    axis_dialog.widget.ui.x_max.setValue(15)
    axis_dialog.widget.ui.y_min.setValue(5)
    axis_dialog.widget.ui.y_max.setValue(15)

    axis_dialog.accept()

    assert multi_waveform_widget.waveform.config.axis.title == "New Title"
    assert multi_waveform_widget.waveform.config.axis.x_label == "New X Label"
    assert multi_waveform_widget.waveform.config.axis.y_label == "New Y Label"
    assert multi_waveform_widget.waveform.config.axis.x_scale == "log"
    assert multi_waveform_widget.waveform.config.axis.y_scale == "linear"
    assert multi_waveform_widget.waveform.config.axis.x_lim == (5, 15)
    assert multi_waveform_widget.waveform.config.axis.y_lim == (5, 15)


###################################
# Theme Update Test
###################################


def test_multi_waveform_widget_theme_update(qtbot, multi_waveform_widget):
    """Test theme update for multi waveform widget."""
    qapp = QApplication.instance()

    # Set the theme to dark
    set_theme("dark")
    palette = get_theme_palette()
    waveform_color_dark = multi_waveform_widget.waveform.plot_item.getAxis("left").pen().color()
    bg_color = multi_waveform_widget.fig.backgroundBrush().color()

    assert bg_color == QColor(20, 20, 20)
    assert waveform_color_dark == palette.text().color()

    # Set the theme to light
    set_theme("light")
    palette = get_theme_palette()
    waveform_color_light = multi_waveform_widget.waveform.plot_item.getAxis("left").pen().color()
    bg_color = multi_waveform_widget.fig.backgroundBrush().color()
    assert bg_color == QColor(233, 236, 239)
    assert waveform_color_light == palette.text().color()

    assert waveform_color_dark != waveform_color_light

    # Set the theme to auto and simulate OS theme change
    set_theme("auto")
    qapp.theme_signal.theme_updated.emit("dark")
    apply_theme("dark")

    waveform_color = multi_waveform_widget.waveform.plot_item.getAxis("left").pen().color()
    bg_color = multi_waveform_widget.fig.backgroundBrush().color()
    assert bg_color == QColor(20, 20, 20)
    assert waveform_color == waveform_color_dark
