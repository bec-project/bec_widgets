# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import
from unittest import mock

import pytest

from bec_widgets.widgets.containers.figure import BECFigure

from .client_mocks import mocked_client
from .conftest import create_widget


def test_init_plot_base(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    plot_base = bec_figure.add_widget(widget_type="BECPlotBase", widget_id="test_plot")
    assert plot_base is not None
    assert plot_base.config.widget_class == "BECPlotBase"
    assert plot_base.config.gui_id == plot_base.gui_id


def test_plot_base_axes_by_separate_methods(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    plot_base = bec_figure.add_widget(widget_type="BECPlotBase", widget_id="test_plot")

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


def test_plot_base_axes_added_by_kwargs(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    plot_base = bec_figure.add_widget(widget_type="BECPlotBase", widget_id="test_plot")

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


def test_lock_aspect_ratio(qtbot, mocked_client):
    """
    Test locking and unlocking the aspect ratio of the plot.
    """
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    plot_base = bec_figure.add_widget(widget_type="BECPlotBase", widget_id="test_plot")

    # Lock the aspect ratio
    plot_base.lock_aspect_ratio(True)
    assert plot_base.plot_item.vb.state["aspectLocked"] == 1

    # Unlock the aspect ratio
    plot_base.lock_aspect_ratio(False)
    assert plot_base.plot_item.vb.state["aspectLocked"] == 0


def test_set_auto_range(qtbot, mocked_client):
    """
    Test enabling and disabling auto range for the plot.
    """
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    plot_base = bec_figure.add_widget(widget_type="BECPlotBase", widget_id="test_plot")

    # Enable auto range for both axes
    plot_base.set_auto_range(True, axis="xy")
    assert plot_base.plot_item.vb.state["autoRange"] == [True, True]

    # Disable auto range for x-axis
    plot_base.set_auto_range(False, axis="x")
    assert plot_base.plot_item.vb.state["autoRange"] == [False, True]

    # Disable auto range for y-axis
    plot_base.set_auto_range(False, axis="y")
    assert plot_base.plot_item.vb.state["autoRange"] == [False, False]


def test_set_outer_axes(qtbot, mocked_client):
    """
    Test showing and hiding the outer axes of the plot.
    """
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    plot_base = bec_figure.add_widget(widget_type="BECPlotBase", widget_id="test_plot")

    # Show outer axes
    plot_base.set_outer_axes(True)
    assert plot_base.plot_item.getAxis("top").isVisible()
    assert plot_base.plot_item.getAxis("right").isVisible()
    assert plot_base.config.axis.outer_axes is True

    # Hide outer axes
    plot_base.set_outer_axes(False)
    assert not plot_base.plot_item.getAxis("top").isVisible()
    assert not plot_base.plot_item.getAxis("right").isVisible()
    assert plot_base.config.axis.outer_axes is False


def test_toggle_crosshair(qtbot, mocked_client):
    """
    Test toggling the crosshair on and off.
    """
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    plot_base = bec_figure.add_widget(widget_type="BECPlotBase", widget_id="test_plot")

    # Toggle crosshair on
    plot_base.toggle_crosshair()
    assert plot_base.crosshair is not None

    # Toggle crosshair off
    plot_base.toggle_crosshair()
    assert plot_base.crosshair is None


def test_invalid_scale_input(qtbot, mocked_client):
    """
    Test setting an invalid scale for x and y axes.
    """
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    plot_base = bec_figure.add_widget(widget_type="BECPlotBase", widget_id="test_plot")

    with pytest.raises(ValueError):
        plot_base.set_x_scale("invalid_scale")

    with pytest.raises(ValueError):
        plot_base.set_y_scale("invalid_scale")


def test_set_x_lim_invalid_arguments(qtbot, mocked_client):
    """
    Test passing invalid arguments to set_x_lim.
    """
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    plot_base = bec_figure.add_widget(widget_type="BECPlotBase", widget_id="test_plot")

    with pytest.raises(ValueError):
        plot_base.set_x_lim(1)

    with pytest.raises(ValueError):
        plot_base.set_x_lim((1, 2, 3))


def test_set_y_lim_invalid_arguments(qtbot, mocked_client):
    """
    Test passing invalid arguments to set_y_lim.
    """
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    plot_base = bec_figure.add_widget(widget_type="BECPlotBase", widget_id="test_plot")

    with pytest.raises(ValueError):
        plot_base.set_y_lim(1)

    with pytest.raises(ValueError):
        plot_base.set_y_lim((1, 2, 3))


def test_remove_plot(qtbot, mocked_client):
    """
    Test removing the plot widget from the figure.
    """
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    with mock.patch.object(bec_figure, "remove") as mock_remove:
        plot_base = bec_figure.add_widget(widget_type="BECPlotBase", widget_id="test_plot")
        plot_base.remove()
        mock_remove.assert_called_once_with(widget_id=plot_base.gui_id)


def test_add_fps_monitor(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    plot_base = bec_figure.add_widget(widget_type="BECPlotBase", widget_id="test_plot")

    plot_base.enable_fps_monitor(True)

    assert plot_base.fps_monitor is not None
    assert plot_base.fps_monitor.view_box is plot_base.plot_item.getViewBox()
    assert plot_base.fps_monitor.timer.isActive() == True
    assert plot_base.fps_monitor.timer.interval() == 1000
    assert plot_base.fps_monitor.sigFpsUpdate is not None
    assert plot_base.fps_monitor.sigFpsUpdate.connect is not None


def test_hook_unhook_fps_monitor(qtbot, mocked_client):
    bec_figure = create_widget(qtbot, BECFigure, client=mocked_client)
    plot_base = bec_figure.add_widget(widget_type="BECPlotBase", widget_id="test_plot")

    plot_base.enable_fps_monitor(True)
    assert plot_base.fps_monitor is not None

    plot_base.enable_fps_monitor(False)
    assert plot_base.fps_monitor is None

    plot_base.enable_fps_monitor(True)
    assert plot_base.fps_monitor is not None
