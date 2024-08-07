from unittest.mock import MagicMock, patch

import pyqtgraph as pg
import pytest

from bec_widgets.widgets.waveform.waveform_widget import BECWaveformWidget

from .client_mocks import mocked_client


@pytest.fixture
def waveform_widget(qtbot, mocked_client):
    widget = BECWaveformWidget(client=mocked_client())
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def mock_waveform(waveform_widget):
    waveform_mock = MagicMock()
    waveform_widget.waveform = waveform_mock
    return waveform_mock


def test_waveform_widget_init(waveform_widget):
    assert waveform_widget is not None
    assert waveform_widget.client is not None
    assert isinstance(waveform_widget, BECWaveformWidget)
    assert waveform_widget.config.widget_class == "BECWaveformWidget"


###################################
# Wrapper methods for Waveform
###################################


def test_waveform_widget_get_curve(waveform_widget, mock_waveform):
    waveform_widget.get_curve("curve_id")
    waveform_widget.waveform.get_curve.assert_called_once_with("curve_id")


def test_waveform_widget_set_colormap(waveform_widget, mock_waveform):
    waveform_widget.set_colormap("colormap")
    waveform_widget.waveform.set_colormap.assert_called_once_with("colormap")


def test_waveform_widget_set_x(waveform_widget, mock_waveform):
    waveform_widget.set_x("samx", "samx")
    waveform_widget.waveform.set_x.assert_called_once_with("samx", "samx")


def test_waveform_plot_data(waveform_widget, mock_waveform):
    waveform_widget.plot(x=[1, 2, 3], y=[1, 2, 3])
    waveform_widget.waveform.plot.assert_called_once_with(
        arg1=None,
        x=[1, 2, 3],
        y=[1, 2, 3],
        x_name=None,
        y_name=None,
        z_name=None,
        x_entry=None,
        y_entry=None,
        z_entry=None,
        color=None,
        color_map_z="plasma",
        label=None,
        validate=True,
        dap=None,
    )


def test_waveform_plot_scan_curves(waveform_widget, mock_waveform):
    waveform_widget.plot(x_name="samx", y_name="samy", dap="GaussianModel")
    waveform_widget.waveform.plot.assert_called_once_with(
        arg1=None,
        x=None,
        y=None,
        x_name="samx",
        y_name="samy",
        z_name=None,
        x_entry=None,
        y_entry=None,
        z_entry=None,
        color=None,
        color_map_z="plasma",
        label=None,
        validate=True,
        dap="GaussianModel",
    )


def test_waveform_widget_add_dap(waveform_widget, mock_waveform):
    waveform_widget.add_dap(x_name="samx", y_name="bpm4i")
    waveform_widget.waveform.add_dap.assert_called_once_with(
        x_name="samx",
        y_name="bpm4i",
        x_entry=None,
        y_entry=None,
        color=None,
        dap="GaussianModel",
        validate_bec=True,
    )


def test_waveform_widget_get_dap_params(waveform_widget, mock_waveform):
    waveform_widget.get_dap_params()
    waveform_widget.waveform.get_dap_params.assert_called_once()


def test_waveform_widget_get_dap_summary(waveform_widget, mock_waveform):
    waveform_widget.get_dap_summary()
    waveform_widget.waveform.get_dap_summary.assert_called_once()


def test_waveform_widget_remove_curve(waveform_widget, mock_waveform):
    waveform_widget.remove_curve("curve_id")
    waveform_widget.waveform.remove_curve.assert_called_once_with("curve_id")


def test_waveform_widget_scan_history(waveform_widget, mock_waveform):
    waveform_widget.scan_history(0)
    waveform_widget.waveform.scan_history.assert_called_once_with(0, None)


def test_waveform_widget_get_all_data(waveform_widget, mock_waveform):
    waveform_widget.get_all_data()
    waveform_widget.waveform.get_all_data.assert_called_once()


def test_waveform_widget_set_title(waveform_widget, mock_waveform):
    waveform_widget.set_title("Title")
    waveform_widget.waveform.set_title.assert_called_once_with("Title")


def test_waveform_widget_set_base(waveform_widget, mock_waveform):
    waveform_widget.set(
        title="Test Title",
        x_label="X Label",
        y_label="Y Label",
        x_scale="linear",
        y_scale="log",
        x_lim=(0, 10),
        y_lim=(0, 10),
        legend_label_size=12,
    )
    waveform_widget.waveform.set.assert_called_once_with(
        title="Test Title",
        x_label="X Label",
        y_label="Y Label",
        x_scale="linear",
        y_scale="log",
        x_lim=(0, 10),
        y_lim=(0, 10),
        legend_label_size=12,
    )


def test_waveform_widget_set_x_label(waveform_widget, mock_waveform):
    waveform_widget.set_x_label("X Label")
    waveform_widget.waveform.set_x_label.assert_called_once_with("X Label")


def test_waveform_widget_set_y_label(waveform_widget, mock_waveform):
    waveform_widget.set_y_label("Y Label")
    waveform_widget.waveform.set_y_label.assert_called_once_with("Y Label")


def test_waveform_widget_set_x_scale(waveform_widget, mock_waveform):
    waveform_widget.set_x_scale("linear")
    waveform_widget.waveform.set_x_scale.assert_called_once_with("linear")


def test_waveform_widget_set_y_scale(waveform_widget, mock_waveform):
    waveform_widget.set_y_scale("log")
    waveform_widget.waveform.set_y_scale.assert_called_once_with("log")


def test_waveform_widget_set_x_lim(waveform_widget, mock_waveform):
    waveform_widget.set_x_lim((0, 10))
    waveform_widget.waveform.set_x_lim.assert_called_once_with((0, 10))


def test_waveform_widget_set_y_lim(waveform_widget, mock_waveform):
    waveform_widget.set_y_lim((0, 10))
    waveform_widget.waveform.set_y_lim.assert_called_once_with((0, 10))


def test_waveform_widget_set_legend_label_size(waveform_widget, mock_waveform):
    waveform_widget.set_legend_label_size(12)
    waveform_widget.waveform.set_legend_label_size.assert_called_once_with(12)


def test_waveform_widget_set_auto_range(waveform_widget, mock_waveform):
    waveform_widget.set_auto_range(True, "xy")
    waveform_widget.waveform.set_auto_range.assert_called_once_with(True, "xy")


def test_waveform_widget_set_grid(waveform_widget, mock_waveform):
    waveform_widget.set_grid(True, False)
    waveform_widget.waveform.set_grid.assert_called_once_with(True, False)


def test_waveform_widget_lock_aspect_ratio(waveform_widget, mock_waveform):
    waveform_widget.lock_aspect_ratio(True)
    waveform_widget.waveform.lock_aspect_ratio.assert_called_once_with(True)


def test_waveform_widget_export(waveform_widget, mock_waveform):
    waveform_widget.export()
    waveform_widget.waveform.export.assert_called_once()


###################################
# ToolBar interactions
###################################


def test_toolbar_drag_mode_action_triggered(waveform_widget, qtbot):
    action_drag = waveform_widget.toolbar.widgets["drag_mode"].action
    action_rectangle = waveform_widget.toolbar.widgets["rectangle_mode"].action
    action_drag.trigger()
    assert action_drag.isChecked() == True
    assert action_rectangle.isChecked() == False


def test_toolbar_rectangle_mode_action_triggered(waveform_widget, qtbot):
    action_drag = waveform_widget.toolbar.widgets["drag_mode"].action
    action_rectangle = waveform_widget.toolbar.widgets["rectangle_mode"].action
    action_rectangle.trigger()
    assert action_drag.isChecked() == False
    assert action_rectangle.isChecked() == True


def test_toolbar_auto_range_action_triggered(waveform_widget, mock_waveform, qtbot):
    action = waveform_widget.toolbar.widgets["auto_range"].action
    action.trigger()
    qtbot.wait(200)
    waveform_widget.waveform.set_auto_range.assert_called_once_with(True, "xy")


def test_toolbar_fit_params_action_triggered(qtbot, waveform_widget):
    action = waveform_widget.toolbar.widgets["fit_params"].action
    with patch(
        "bec_widgets.widgets.waveform.waveform_widget.FitSummaryWidget"
    ) as MockFitSummaryWidget:
        mock_dialog_instance = MockFitSummaryWidget.return_value
        action.trigger()
        mock_dialog_instance.show.assert_called_once()


def test_enable_mouse_pan_mode(qtbot, waveform_widget):
    action_drag = waveform_widget.toolbar.widgets["drag_mode"].action
    action_rectangle = waveform_widget.toolbar.widgets["rectangle_mode"].action

    mock_view_box = MagicMock()
    waveform_widget.waveform.plot_item.getViewBox = MagicMock(return_value=mock_view_box)

    waveform_widget.enable_mouse_pan_mode()

    assert action_drag.isChecked() == True
    assert action_rectangle.isChecked() == False
    mock_view_box.setMouseMode.assert_called_once_with(pg.ViewBox.PanMode)
