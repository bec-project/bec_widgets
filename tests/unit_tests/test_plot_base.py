# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import
from unittest import mock

import pytest
from qtpy.QtGui import QFontInfo

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

    assert plot_base.plot_item.titleLabel.text == "Test Title"
    assert plot_base.config.axis.title == "Test Title"
    assert plot_base.plot_item.getAxis("bottom").labelText == "Test x Label"
    assert plot_base.config.axis.x_label == "Test x Label"
    assert plot_base.plot_item.getAxis("left").labelText == "Test y Label"
    assert plot_base.config.axis.y_label == "Test y Label"
    assert plot_base.config.axis.x_lim == (1, 100)
    assert plot_base.config.axis.y_lim == (5, 500)
    assert plot_base.plot_item.ctrl.xGridCheck.isChecked() == True
    assert plot_base.plot_item.ctrl.yGridCheck.isChecked() == True
    assert plot_base.plot_item.ctrl.logXCheck.isChecked() == True
    assert plot_base.plot_item.ctrl.logYCheck.isChecked() == True

    # Check the font size by mocking the set functions
    # I struggled retrieving it from the QFont object directly
    # thus I mocked the set functions to check internally the functionality
    with (
        mock.patch.object(plot_base.plot_item, "setLabel") as mock_set_label,
        mock.patch.object(plot_base.plot_item, "setTitle") as mock_set_title,
    ):
        plot_base.set_x_label("Test x Label", 20)
        plot_base.set_y_label("Test y Label", 16)
        assert mock_set_label.call_count == 2
        assert plot_base.config.axis.x_label_size == 20
        assert plot_base.config.axis.y_label_size == 16
        col = plot_base.get_text_color()
        calls = []
        style = {"color": col, "font-size": "20pt"}
        calls.append(mock.call("bottom", "Test x Label", **style))
        style = {"color": col, "font-size": "16pt"}
        calls.append(mock.call("left", "Test y Label", **style))
        assert mock_set_label.call_args_list == calls
        plot_base.set_title("Test Title", 16)
        style = {"color": col, "size": "16pt"}
        call = mock.call("Test Title", **style)
        assert mock_set_title.call_args == call


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

    assert plot_base.plot_item.titleLabel.text == "Test Title"
    assert plot_base.config.axis.title == "Test Title"
    assert plot_base.plot_item.getAxis("bottom").labelText == "Test x Label"
    assert plot_base.config.axis.x_label == "Test x Label"
    assert plot_base.plot_item.getAxis("left").labelText == "Test y Label"
    assert plot_base.config.axis.y_label == "Test y Label"
    assert plot_base.config.axis.x_lim == (1, 100)
    assert plot_base.config.axis.y_lim == (5, 500)
    assert plot_base.plot_item.ctrl.logXCheck.isChecked() == True
    assert plot_base.plot_item.ctrl.logYCheck.isChecked() == True
