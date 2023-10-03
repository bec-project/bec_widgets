from unittest.mock import MagicMock

import pyqtgraph as pg
import pytest

from bec_widgets.examples.extreme.extreme import PlotApp


def setup_plot_app(qtbot, config):
    """Helper function to setup the PlotApp widget."""
    client = MagicMock()
    widget = PlotApp(config=config, client=client)
    qtbot.addWidget(widget)
    return widget


config_device_mode_all_filled = {
    "plot_settings": {
        "background_color": "black",
        "num_columns": 2,
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
                "signals": [{"name": "gauss_bpm", "entry": "gauss_bpm"}],
            },
        },
    ],
}

config_device_mode_no_entry = {
    "plot_settings": {
        "background_color": "white",
        "num_columns": 1,
        "colormap": "plasma",
        "scan_types": False,
    },
    "plot_data": [
        {
            "plot_name": "BPM4i plots vs samx",
            "x": {
                "label": "Motor Y",
                "signals": [{"name": "samx"}],  # Entry is missing
            },
            "y": {
                "label": "bpm4i",
                "signals": [{"name": "bpm4i"}],  # Entry is missing
            },
        },
        {
            "plot_name": "Gauss plots vs samx",
            "x": {
                "label": "Motor X",
                "signals": [{"name": "samx"}],  # Entry is missing
            },
            "y": {
                "label": "Gauss",
                "signals": [{"name": "gauss_bpm"}],  # Entry is missing
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
    },
}


@pytest.mark.parametrize(
    "config, plot_setting_bg, num_plot ,pg_background",
    [
        (config_device_mode_all_filled, "black", 2, "k"),
        (config_device_mode_no_entry, "white", 2, "w"),
        (config_scan_mode, "white", 4, "w"),
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
            config_device_mode_all_filled,
            2,
            2,
            ["BPM4i plots vs samx", "Gauss plots vs samx"],
            [(0, 0), (0, 1)],
        ),
        (
            config_device_mode_all_filled,
            5,
            2,
            ["BPM4i plots vs samx", "Gauss plots vs samx"],
            [(0, 0), (0, 1)],
        ),  # num_columns greater than number of plots
        (
            config_device_mode_no_entry,
            1,
            1,
            ["BPM4i plots vs samx", "Gauss plots vs samx"],
            [(0, 0), (1, 0)],
        ),
        (
            config_device_mode_no_entry,
            2,
            2,
            ["BPM4i plots vs samx", "Gauss plots vs samx"],
            [(0, 0), (0, 1)],
        ),
        (
            config_device_mode_no_entry,
            5,
            2,
            ["BPM4i plots vs samx", "Gauss plots vs samx"],
            [(0, 0), (0, 1)],
        ),  # num_columns greater than number of plots,
        (
            config_scan_mode,
            2,
            2,
            [
                "Grid plot 1",
                "Grid plot 2",
                "Grid plot 3",
                "Grid plot 4",
            ],
            [(0, 0), (0, 1), (1, 0), (1, 1)],
        ),
        (
            config_scan_mode,
            3,
            3,
            [
                "Grid plot 1",
                "Grid plot 2",
                "Grid plot 3",
                "Grid plot 4",
            ],
            [(0, 0), (0, 1), (0, 2), (1, 0)],
        ),
        (
            config_scan_mode,
            5,
            4,
            [
                "Grid plot 1",
                "Grid plot 2",
                "Grid plot 3",
                "Grid plot 4",
            ],
            [(0, 0), (0, 1), (0, 2), (0, 3)],
        ),  # num_columns greater than number of plots
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


def mock_getitem(dev_name):
    """Helper function to mock the __getitem__ method of the 'dev' object.""" ""
    mock_instance = MagicMock()
    if dev_name == "samx":
        mock_instance._hints = "samx"
    elif dev_name == "bpm4i":
        mock_instance._hints = "bpm4i"
    elif dev_name == "gauss_bpm":
        mock_instance._hints = "gauss_bpm"

    return mock_instance


@pytest.mark.parametrize(
    "config, msg, metadata, expected_data, mock_hints",
    [
        # Case: msg does not have 'scanID'
        (config_device_mode_all_filled, {"data": {}}, {}, {}, None),
        # Case: scan_types is False, msg contains all valid fields, and entry is present in config
        (
            config_device_mode_all_filled,
            {
                "data": {
                    "samx": {"samx": {"value": 10}},
                    "bpm4i": {"bpm4i": {"value": 5}},
                    "gauss_bpm": {"gauss_bpm": {"value": 7}},
                },
                "scanID": 1,
            },
            {},
            {
                ("samx", "samx", "bpm4i", "bpm4i"): {"x": [10], "y": [5]},
                ("samx", "samx", "gauss_bpm", "gauss_bpm"): {"x": [10], "y": [7]},
            },
            None,
        ),
        # Case: scan_types is False, msg contains all valid fields and entry is missing in config, should use hints
        (
            config_device_mode_no_entry,
            {
                "data": {
                    "samx": {"samx": {"value": 10}},
                    "bpm4i": {"bpm4i": {"value": 5}},
                    "gauss_bpm": {"gauss_bpm": {"value": 7}},
                },
                "scanID": 1,
            },
            {},
            {
                ("samx", "samx", "bpm4i", "bpm4i"): {"x": [10], "y": [5]},
                ("samx", "samx", "gauss_bpm", "gauss_bpm"): {"x": [10], "y": [7]},
            },
            {"samx": "samx", "bpm4i": "bpm4i", "gauss_bpm": "gauss_bpm"},
        ),
    ],
)
def test_on_scan_segment(qtbot, config, msg, metadata, expected_data, mock_hints):
    plot_app = setup_plot_app(qtbot, config)

    # Initialize and run test
    plot_app.init_curves = MagicMock()
    plot_app.data = {}
    plot_app.scanID = 0

    plot_app.dev.__getitem__.side_effect = mock_getitem

    plot_app.on_scan_segment(msg, metadata)
    assert plot_app.data == expected_data


@pytest.mark.parametrize(
    "config, msg, metadata, expected_exception_message",
    [
        # Case: scan_types is True, but metadata does not contain 'scan_name'
        (
            config_scan_mode,
            {"data": {}, "scanID": 1},
            {},  # No 'scan_name' in metadata
            "Scan name not found in metadata. Please check the scan_name in the YAML config or in bec configuration.",
        ),
        # Case: scan_types is True, metadata contains non-existing 'scan_name'
        (
            config_scan_mode,
            {"data": {}, "scanID": 1},
            {"scan_name": "non_existing_scan"},
            "Scan name non_existing_scan not found in the YAML config. Please check the scan_name in the YAML config "
            "or in bec configuration.",
        ),
    ],
)
def test_on_scan_segment_error_handling(qtbot, config, msg, metadata, expected_exception_message):
    plot_app = setup_plot_app(qtbot, config)

    # Initialize
    plot_app.init_curves = MagicMock()
    plot_app.data = {}
    plot_app.scanID = 0

    plot_app.dev.__getitem__.side_effect = mock_getitem

    with pytest.raises(ValueError) as exc_info:
        plot_app.on_scan_segment(msg, metadata)
    assert str(exc_info.value) == expected_exception_message
