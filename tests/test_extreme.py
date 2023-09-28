import pyqtgraph as pg
import pytest

from bec_widgets.examples.extreme.extreme import PlotApp


def setup_plot_app(qtbot, config):
    """Helper function to setup the PlotApp widget."""
    widget = PlotApp(config)
    qtbot.addWidget(widget)
    return widget


config_device_mode = {
    "plot_settings": {
        "background_color": "black",
        "num_columns": 2,
        "colormap": "plasma",
        "scan_types": False,
    },
    "plot_data": [
        {
            "plot_name": "BPM4i plots vs samy",
            "x": {
                "label": "Motor Y",
                "signals": [{"name": "samy"}],
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
                "signals": [{"name": "samx"}],
            },
            "y": {
                "label": "Gauss",
                "signals": [{"name": "gauss_bpm", "entry": "gauss_bpm"}],
            },
        },
    ],
}

config_scan_mode = config = {
    "plot_settings": {
        "background_color": "white",
        "num_columns": 3,
        "colormap": "plasma",
        "scan_types": True,
    },
    "plot_data": {
        "line_scan": [
            {
                "plot_name": "BPM plot",
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
                "plot_name": "Multi",
                "x": {"label": "Motor X", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "Multi",
                    "signals": [
                        {"name": "gauss_bpm", "entry": "gauss_bpm"},
                        {"name": "samx", "entry": ["samx", "samx_setpoint"]},
                    ],
                },
            },
        ],
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
                "x": {"label": "Motor Y", "signals": [{"name": "samy", "entry": "samy"}]},
                "y": {
                    "label": "BPM",
                    "signals": [{"name": "gauss_bpm", "entry": "gauss_bpm"}],
                },
            },
            {
                "plot_name": "Grid plot 4",
                "x": {"label": "Motor Y", "signals": [{"name": "samy", "entry": "samy"}]},
                "y": {
                    "label": "BPM",
                    "signals": [{"name": "gauss_adc3", "entry": "gauss_adc3"}],
                },
            },
        ],
    },
}


@pytest.mark.parametrize(
    "config, plot_setting_bg, num_plot ,pg_background",
    [
        (config_device_mode, "black", 2, "k"),
        # (config_scan_mode, "white", 5, "w") #TODO fix the extreme plot function to be able to init the plot before scan mode
    ],
)
def test_init_config(qtbot, config, plot_setting_bg, num_plot, pg_background):
    plot_app = setup_plot_app(qtbot, config)
    assert plot_app.plot_settings["background_color"] == plot_setting_bg
    assert len(plot_app.plot_data) == num_plot
    assert pg.getConfigOption("background") == pg_background


@pytest.mark.parametrize(
    "config, num_columns_input, expected_num_columns, expected_plot_names, expected_coordinates",
    [
        (
            config_device_mode,
            2,
            2,
            ["BPM4i plots vs samy", "Gauss plots vs samx"],
            [(0, 0), (0, 1)],
        ),
        (
            config_device_mode,
            5,
            2,
            ["BPM4i plots vs samy", "Gauss plots vs samx"],
            [(0, 0), (0, 1)],
        ),  # num_columns greater than number of plots
        # (config_scan_mode, 3, 3, ["BPM plot", "Multi", "Grid plot 1", "Grid plot 2", "Grid plot 3", "Grid plot 4"], [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]),
    ],
)
def test_init_ui(
    qtbot,
    config,
    num_columns_input,
    expected_num_columns,
    expected_plot_names,
    expected_coordinates,
):
    plot_app = setup_plot_app(qtbot, config)
    plot_app.init_ui(num_columns_input)

    # Validate number of columns
    assert plot_app.plot_settings["num_columns"] == expected_num_columns

    # Validate the plots are created correctly
    for expected_name in expected_plot_names:
        assert expected_name in plot_app.plots.keys()

    # Validate the grid_coordinates
    assert plot_app.grid_coordinates == expected_coordinates
