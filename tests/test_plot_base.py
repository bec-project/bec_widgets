# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import
import pytest
from .client_mocks import mocked_client
from .test_bec_figure import bec_figure


def test_init_plot_base(bec_figure):
    plot_base = bec_figure.add_widget(widget_type="PlotBase", widget_id="test_plot")
    assert plot_base is not None
    assert plot_base.config.widget_class == "BECPlotBase"
    assert plot_base.config.gui_id == "test_plot"


def test_plot_base_axes_by_separate_methods(bec_figure):
    plot_base = bec_figure.add_widget(widget_type="PlotBase", widget_id="test_plot")

    plot_base.set_title("Test Title")
    plot_base.set_x_label("Test x Label")
    plot_base.set_y_label("Test y Label")
    plot_base.set_x_lim(1, 100)
    plot_base.set_y_lim(5, 500)
    plot_base.set_grid(True, True)
    plot_base.set_x_scale("log")
    plot_base.set_y_scale("log")

    assert plot_base.titleLabel.text == "Test Title"
    assert plot_base.config.axis.title == "Test Title"
    assert plot_base.getAxis("bottom").labelText == "Test x Label"
    assert plot_base.config.axis.x_label == "Test x Label"
    assert plot_base.getAxis("left").labelText == "Test y Label"
    assert plot_base.config.axis.y_label == "Test y Label"
    assert plot_base.config.axis.x_lim == (1, 100)
    assert plot_base.config.axis.y_lim == (5, 500)
    assert plot_base.ctrl.xGridCheck.isChecked() == True
    assert plot_base.ctrl.yGridCheck.isChecked() == True
    assert plot_base.ctrl.logXCheck.isChecked() == True
    assert plot_base.ctrl.logYCheck.isChecked() == True


def test_plot_base_axes_added_by_kwargs(bec_figure):
    plot_base = bec_figure.add_widget(widget_type="PlotBase", widget_id="test_plot")

    plot_base.set(
        title="Test Title",
        x_label="Test x Label",
        y_label="Test y Label",
        x_lim=(1, 100),
        y_lim=(5, 500),
        x_scale="log",
        y_scale="log",
    )

    assert plot_base.titleLabel.text == "Test Title"
    assert plot_base.config.axis.title == "Test Title"
    assert plot_base.getAxis("bottom").labelText == "Test x Label"
    assert plot_base.config.axis.x_label == "Test x Label"
    assert plot_base.getAxis("left").labelText == "Test y Label"
    assert plot_base.config.axis.y_label == "Test y Label"
    assert plot_base.config.axis.x_lim == (1, 100)
    assert plot_base.config.axis.y_lim == (5, 500)
    assert plot_base.ctrl.logXCheck.isChecked() == True
    assert plot_base.ctrl.logYCheck.isChecked() == True
