# pylint: disable=missing-module-docstring, missing-function-docstring
from collections import defaultdict
from unittest.mock import MagicMock

import pytest
from qtpy import QtGui

from bec_widgets.widgets import BECMonitor2DScatter

CONFIG_DEFAULT = {
    "plot_settings": {"colormap": "CET-L4", "num_columns": 1},
    "waveform2D": [
        {
            "plot_name": "Waveform 2D Scatter (1)",
            "x_label": "Sam X",
            "y_label": "Sam Y",
            "signals": {
                "x": [{"name": "samx", "entry": "samx"}],
                "y": [{"name": "samy", "entry": "samy"}],
                "z": [{"name": "gauss_bpm", "entry": "gauss_bpm"}],
            },
        },
        {
            "plot_name": "Waveform 2D Scatter (2)",
            "x_label": "Sam X",
            "y_label": "Sam Y",
            "signals": {
                "x": [{"name": "samy", "entry": "samy"}],
                "y": [{"name": "samx", "entry": "samx"}],
                "z": [{"name": "gauss_bpm", "entry": "gauss_bpm"}],
            },
        },
    ],
}

CONFIG_ONE_PLOT = {
    "plot_settings": {"colormap": "CET-L4", "num_columns": 1},
    "waveform2D": [
        {
            "plot_name": "Waveform 2D Scatter (1)",
            "x_label": "Sam X",
            "y_label": "Sam Y",
            "signals": {
                "x": [{"name": "aptrx", "entry": "aptrx"}],
                "y": [{"name": "aptry", "entry": "aptry"}],
                "z": [{"name": "gauss_bpm", "entry": "gauss_bpm"}],
            },
        }
    ],
}


@pytest.fixture(scope="function")
def monitor_2Dscatter(qtbot):
    client = MagicMock()
    widget = BECMonitor2DScatter(client=client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.mark.parametrize("config, number_of_plots", [(CONFIG_DEFAULT, 2), (CONFIG_ONE_PLOT, 1)])
def test_initialization(monitor_2Dscatter, config, number_of_plots):
    config_load = config
    monitor_2Dscatter.on_config_update(config_load)
    assert isinstance(monitor_2Dscatter, BECMonitor2DScatter)
    assert monitor_2Dscatter.client is not None
    assert monitor_2Dscatter.config == config_load
    assert len(monitor_2Dscatter.plot_data) == number_of_plots


@pytest.mark.parametrize("config ", [(CONFIG_DEFAULT), (CONFIG_ONE_PLOT)])
def test_database_initialization(monitor_2Dscatter, config):
    monitor_2Dscatter.on_config_update(config)
    # Check if the database is a defaultdict
    assert isinstance(monitor_2Dscatter.database, defaultdict)
    for axis_dict in monitor_2Dscatter.database.values():
        assert isinstance(axis_dict, defaultdict)
        for signal_list in axis_dict.values():
            assert isinstance(signal_list, defaultdict)

    # Access the elements
    for plot_config in config["waveform2D"]:
        plot_name = plot_config["plot_name"]

        for axis in ["x", "y", "z"]:
            for signal in plot_config["signals"][axis]:
                signal_name = signal["name"]
                assert not monitor_2Dscatter.database[plot_name][axis][signal_name]
                assert isinstance(monitor_2Dscatter.database[plot_name][axis][signal_name], list)


@pytest.mark.parametrize("config ", [(CONFIG_DEFAULT), (CONFIG_ONE_PLOT)])
def test_ui_initialization(monitor_2Dscatter, config):
    monitor_2Dscatter.on_config_update(config)
    assert len(monitor_2Dscatter.plots) == len(config["waveform2D"])
    for plot_config in config["waveform2D"]:
        plot_name = plot_config["plot_name"]
        assert plot_name in monitor_2Dscatter.plots
        plot = monitor_2Dscatter.plots[plot_name]
        assert plot.titleLabel.text == plot_name


def simulate_scan_data(monitor, x_value, y_value, z_value):
    """Helper function to simulate scan data input with three devices."""
    msg = {
        "data": {
            "samx": {"samx": {"value": x_value}},
            "samy": {"samy": {"value": y_value}},
            "gauss_bpm": {"gauss_bpm": {"value": z_value}},
        },
        "scan_id": 1,
    }
    monitor.on_scan_segment(msg, {})


def test_data_update_and_plotting(monitor_2Dscatter, qtbot):
    monitor_2Dscatter.on_config_update(CONFIG_DEFAULT)
    data_sets = [(1, 4, 7), (2, 5, 8), (3, 6, 9)]  # (x, y, z) tuples
    plot_name = "Waveform 2D Scatter (1)"

    for x, y, z in data_sets:
        simulate_scan_data(monitor_2Dscatter, x, y, z)
        qtbot.wait(100)  # Wait for the plot to update

    # Retrieve the plot and check if the number of data points matches
    scatterPlot = monitor_2Dscatter.scatterPlots[plot_name]
    assert len(scatterPlot.data) == len(data_sets)

    # Check if the data in the database matches the sent data
    x_data = [
        point
        for points_list in monitor_2Dscatter.database[plot_name]["x"].values()
        for point in points_list
    ]
    y_data = [
        point
        for points_list in monitor_2Dscatter.database[plot_name]["y"].values()
        for point in points_list
    ]
    z_data = [
        point
        for points_list in monitor_2Dscatter.database[plot_name]["z"].values()
        for point in points_list
    ]

    assert x_data == [x for x, _, _ in data_sets]
    assert y_data == [y for _, y, _ in data_sets]
    assert z_data == [z for _, _, z in data_sets]


def test_color_mapping(monitor_2Dscatter, qtbot):
    monitor_2Dscatter.on_config_update(CONFIG_DEFAULT)
    data_sets = [(1, 4, 7), (2, 5, 8), (3, 6, 9)]  # (x, y, z) tuples
    for x, y, z in data_sets:
        simulate_scan_data(monitor_2Dscatter, x, y, z)
        qtbot.wait(100)  # Wait for the plot to update

    scatterPlot = monitor_2Dscatter.scatterPlots["Waveform 2D Scatter (1)"]

    # Check if colors are applied
    assert all(isinstance(point.brush().color(), QtGui.QColor) for point in scatterPlot.points())
