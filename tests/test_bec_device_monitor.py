from unittest.mock import MagicMock

import pytest
from PyQt5.QtWidgets import QApplication

from bec_widgets.widgets import BECDeviceMonitor

config_device = {
    "plot_settings": {
        "background_color": "black",
        "num_columns": 1,
        "colormap": "plasma",
        "scan_types": False,
    },
    "plot_data": [
        {
            "plot_name": "BPM4i plots vs samx",
            "x": {
                "label": "Motor Y",
                "signals": [{"name": "samx", "entry": "samx"}],
            },
            "y": {
                "label": "bpm4i",
                "signals": [{"name": "bpm4i", "entry": "bpm4i"}],
            },
        },
        {
            "plot_name": "Gauss plots vs samx",
            "x": {
                "label": "Motor X",
                "signals": [{"name": "samx", "entry": "samx"}],
            },
            "y": {
                "label": "Gauss",
                "signals": [
                    {"name": "gauss_adc1", "entry": "gauss_adc1"},
                    {"name": "gauss_adc2", "entry": "gauss_adc2"},
                ],
            },
        },
    ],
}


config_scan = {
    "plot_settings": {
        "background_color": "white",
        "num_columns": 3,
        "colormap": "plasma",
        "scan_types": True,
    },
    "plot_data": {
        "grid_scan": [
            {
                "plot_name": "Grid plot 1",
                "x": {"label": "Motor X", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "BPM",
                    "signals": [
                        {"name": "gauss_bpm", "entry": "gauss_bpm"},
                        {"name": "gauss_adc1", "entry": "gauss_adc1"},
                    ],
                },
            },
            {
                "plot_name": "Grid plot 2",
                "x": {"label": "Motor X", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "BPM",
                    "signals": [
                        {"name": "gauss_bpm", "entry": "gauss_bpm"},
                        {"name": "gauss_adc1", "entry": "gauss_adc1"},
                    ],
                },
            },
            {
                "plot_name": "Grid plot 3",
                "x": {"label": "Motor Y", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "BPM",
                    "signals": [{"name": "gauss_bpm", "entry": "gauss_bpm"}],
                },
            },
            {
                "plot_name": "Grid plot 4",
                "x": {"label": "Motor Y", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "BPM",
                    "signals": [{"name": "gauss_adc3", "entry": "gauss_adc3"}],
                },
            },
        ],
        "line_scan": [
            {
                "plot_name": "Multiple Gauss Plot",
                "x": {"label": "Motor X", "signals": [{"name": "samx"}]},
                "y": {
                    "label": "BPM",
                    "signals": [
                        {"name": "gauss_bpm", "entry": "gauss_bpm"},
                        {"name": "gauss_adc1", "entry": "gauss_adc1"},
                        {"name": "gauss_adc2", "entry": "gauss_adc2"},
                    ],
                },
            },
            {
                "plot_name": "BPM Plot",
                "x": {"label": "Motor X", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "Multi",
                    "signals": [
                        {"name": "gauss_bpm", "entry": "gauss_bpm"},
                        {"name": "bpm4i", "entry": "bpm4i"},
                    ],
                },
            },
        ],
    },
}


def setup_monitor(qtbot, config):
    """Helper function to set up the BECDeviceMonitor widget."""
    client = MagicMock()
    widget = BECDeviceMonitor(config=config, client=client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


@pytest.fixture(scope="module")
def app():
    app = QApplication([])
    yield app


@pytest.fixture
def qtbot(app, qtbot):  # TODO is this needed?
    """A qtbot fixture to ensure that widgets are closed after being used."""
    qtbot.old_widgets = set(app.topLevelWidgets())
    yield qtbot
    new_widgets = set(app.topLevelWidgets()) - qtbot.old_widgets
    for widget in new_widgets:
        widget.close()


@pytest.mark.parametrize(
    "config, scan_type, number_of_plots", [(config_device, False, 2), (config_scan, True, 4)]
)
def test_initialization_with_device_config(qtbot, config, scan_type, number_of_plots):
    widget = setup_monitor(qtbot, config)
    assert isinstance(widget, BECDeviceMonitor)
    assert widget.config == config
    assert widget.client is not None
    assert len(widget.plot_data) == number_of_plots
    assert widget.scan_types == scan_type


@pytest.mark.parametrize(
    "config_initial,config_update", [(config_device, config_scan), (config_scan, config_device)]
)
def test_update_config(qtbot, config_initial, config_update):
    widget = setup_monitor(qtbot, config_initial)
    widget.update_config(config_update)
    assert widget.config == config_update


@pytest.mark.parametrize(
    "config, expected_num_columns, expected_plot_names, expected_coordinates",
    [
        (
            config_device,
            1,
            ["BPM4i plots vs samx", "Gauss plots vs samx"],
            [(0, 0), (1, 0)],
        ),
        (
            config_scan,
            3,
            ["Grid plot 1", "Grid plot 2", "Grid plot 3", "Grid plot 4"],
            [(0, 0), (0, 1), (0, 2), (1, 0)],
        ),
    ],
)
def test_render_initial_plots(
    qtbot, config, expected_num_columns, expected_plot_names, expected_coordinates
):
    widget = setup_monitor(qtbot, config)

    # Validate number of columns
    assert widget.plot_settings["num_columns"] == expected_num_columns
    # Validate the plots are created correctly
    for expected_name in expected_plot_names:
        assert expected_name in widget.plots.keys()

    # Validate the grid_coordinates
    assert widget.grid_coordinates == expected_coordinates
