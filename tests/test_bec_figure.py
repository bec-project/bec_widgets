# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import
import os

import numpy as np
import pytest
from unittest.mock import MagicMock

from .client_mocks import mocked_client
from bec_widgets.widgets import BECFigure


@pytest.fixture
def bec_figure(qtbot, mocked_client):
    widget = BECFigure(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


def test_bec_figure_init(bec_figure):
    assert bec_figure is not None
    assert bec_figure.client is not None
    assert isinstance(bec_figure, BECFigure)
    assert bec_figure.config.widget_class == "BECFigure"


def test_bec_figure_init_with_config(mocked_client):
    config = {
        "widget_class": "BECFigure",
        "gui_id": "test_gui_id",
        "theme": "dark",
    }
    widget = BECFigure(client=mocked_client, config=config)
    assert widget.config.gui_id == "test_gui_id"
    assert widget.config.theme == "dark"


def test_bec_figure_add_remove_plot(bec_figure):
    initial_count = len(bec_figure._widgets)

    # Adding 3 widgets -  2 WaveformBase and 1 PlotBase
    w0 = bec_figure.add_plot()
    w1 = bec_figure.add_plot()
    w2 = bec_figure.add_widget(widget_type="PlotBase")

    # Check if the widgets were added
    assert len(bec_figure._widgets) == initial_count + 3
    assert "widget_1" in bec_figure._widgets
    assert "widget_2" in bec_figure._widgets
    assert "widget_3" in bec_figure._widgets
    assert bec_figure._widgets["widget_1"].config.widget_class == "BECWaveform1D"
    assert bec_figure._widgets["widget_2"].config.widget_class == "BECWaveform1D"
    assert bec_figure._widgets["widget_3"].config.widget_class == "BECPlotBase"

    # Check accessing positions by the grid in figure
    assert bec_figure[0, 0] == w0
    assert bec_figure[1, 0] == w1
    assert bec_figure[2, 0] == w2

    # Removing 1 widget
    bec_figure.remove(widget_id="widget_1")
    assert len(bec_figure._widgets) == initial_count + 2
    assert "widget_1" not in bec_figure._widgets
    assert "widget_3" in bec_figure._widgets
    assert bec_figure._widgets["widget_2"].config.widget_class == "BECWaveform1D"


def test_access_widgets_access_errors(bec_figure):
    bec_figure.add_plot(row=0, col=0)

    # access widget by non-existent coordinates
    with pytest.raises(ValueError) as excinfo:
        bec_figure[0, 2]
        assert "No widget at coordinates (0, 2)" in str(excinfo.value)

    # access widget by non-existent widget_id
    with pytest.raises(KeyError) as excinfo:
        bec_figure["non_existent_widget"]
        assert "Widget with id 'non_existent_widget' not found" in str(excinfo.value)

    # access widget by wrong type
    with pytest.raises(TypeError) as excinfo:
        bec_figure[1.2]
        assert (
            "Key must be a string (widget id) or a tuple of two integers (grid coordinates)"
            in str(excinfo.value)
        )


def test_add_plot_to_occupied_position(bec_figure):
    bec_figure.add_plot(row=0, col=0)

    with pytest.raises(ValueError) as excinfo:
        bec_figure.add_plot(row=0, col=0)
        assert "Position at row 0 and column 0 is already occupied." in str(excinfo.value)


def test_remove_plots(bec_figure):
    w1 = bec_figure.add_plot(row=0, col=0)
    w2 = bec_figure.add_plot(row=0, col=1)
    w3 = bec_figure.add_plot(row=1, col=0)
    w4 = bec_figure.add_plot(row=1, col=1)

    assert bec_figure[0, 0] == w1
    assert bec_figure[0, 1] == w2
    assert bec_figure[1, 0] == w3
    assert bec_figure[1, 1] == w4

    # remove by coordinates
    bec_figure[0, 0].remove()
    assert "widget_1" not in bec_figure._widgets

    # remove by widget_id
    bec_figure.remove(widget_id="widget_2")
    assert "widget_2" not in bec_figure._widgets

    # remove by widget object
    w3.remove()
    assert "widget_3" not in bec_figure._widgets

    # check the remaining widget 4
    assert bec_figure[0, 0] == w4
    assert bec_figure["widget_4"] == w4
    assert "widget_4" in bec_figure._widgets
    assert len(bec_figure._widgets) == 1


def test_remove_plots_by_coordinates_ints(bec_figure):
    w1 = bec_figure.add_plot(row=0, col=0)
    w2 = bec_figure.add_plot(row=0, col=1)

    bec_figure.remove(0, 0)
    assert "widget_1" not in bec_figure._widgets
    assert "widget_2" in bec_figure._widgets
    assert bec_figure[0, 0] == w2
    assert len(bec_figure._widgets) == 1


def test_remove_plots_by_coordinates_tuple(bec_figure):
    w1 = bec_figure.add_plot(row=0, col=0)
    w2 = bec_figure.add_plot(row=0, col=1)

    bec_figure.remove(coordinates=(0, 0))
    assert "widget_1" not in bec_figure._widgets
    assert "widget_2" in bec_figure._widgets
    assert bec_figure[0, 0] == w2
    assert len(bec_figure._widgets) == 1


def test_remove_plot_by_id_error(bec_figure):
    bec_figure.add_plot(row=0, col=0)

    with pytest.raises(ValueError) as excinfo:
        bec_figure.remove(widget_id="non_existent_widget")
        assert "Widget with ID 'non_existent_widget' does not exist." in str(excinfo.value)


def test_remove_plot_by_coordinates_error(bec_figure):
    bec_figure.add_plot(row=0, col=0)

    with pytest.raises(ValueError) as excinfo:
        bec_figure.remove(0, 1)
        assert "No widget at coordinates (0, 1)" in str(excinfo.value)


def test_remove_plot_by_providing_nothing(bec_figure):
    bec_figure.add_plot(row=0, col=0)

    with pytest.raises(ValueError) as excinfo:
        bec_figure.remove()
        assert "Must provide either widget_id or coordinates for removal." in str(excinfo.value)


# def test_change_theme(bec_figure): #TODO do no work at python 3.12
#     bec_figure.change_theme("dark")
#     assert bec_figure.config.theme == "dark"
#     assert bec_figure.backgroundBrush().color().name() == "#000000"
#     bec_figure.change_theme("light")
#     assert bec_figure.config.theme == "light"
#     assert bec_figure.backgroundBrush().color().name() == "#ffffff"
#     bec_figure.change_theme("dark")
#     assert bec_figure.config.theme == "dark"
#     assert bec_figure.backgroundBrush().color().name() == "#000000"


def test_change_layout(bec_figure):
    w1 = bec_figure.add_plot(row=0, col=0)
    w2 = bec_figure.add_plot(row=0, col=1)
    w3 = bec_figure.add_plot(row=1, col=0)
    w4 = bec_figure.add_plot(row=1, col=1)

    bec_figure.change_layout(max_columns=1)

    assert np.shape(bec_figure.grid) == (4, 1)
    assert bec_figure[0, 0] == w1
    assert bec_figure[1, 0] == w2
    assert bec_figure[2, 0] == w3
    assert bec_figure[3, 0] == w4

    bec_figure.change_layout(max_rows=1)

    assert np.shape(bec_figure.grid) == (1, 4)
    assert bec_figure[0, 0] == w1
    assert bec_figure[0, 1] == w2
    assert bec_figure[0, 2] == w3
    assert bec_figure[0, 3] == w4


def test_clear_all(bec_figure):
    bec_figure.add_plot(row=0, col=0)
    bec_figure.add_plot(row=0, col=1)
    bec_figure.add_plot(row=1, col=0)
    bec_figure.add_plot(row=1, col=1)

    bec_figure.clear_all()

    assert len(bec_figure._widgets) == 0
    assert np.shape(bec_figure.grid) == (0,)
