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
            "plot_name": "BPM4i plots vs samy",
            "x": {
                "label": "Motor Y",
                "signals": [{"name": "samy", "entry": "samy"}],
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
                "signals": [{"name": "samy", "entry": "samy"}],
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
            "plot_name": "BPM4i plots vs samy",
            "x": {
                "label": "Motor Y",
                "signals": [{"name": "samy"}],  # Entry is missing
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
                "signals": [{"name": "samy"}],  # Entry is missing
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
        (config_device_mode_all_filled, "black", 2, "k"),
        (config_device_mode_no_entry, "white", 2, "w"),
        (
            config_scan_mode,
            "white",
            3,
            "w",
        ),
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
            ["BPM4i plots vs samy", "Gauss plots vs samx"],
            [(0, 0), (0, 1)],
        ),
        (
            config_device_mode_all_filled,
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


@pytest.mark.parametrize(
    "msg, metadata, expected_data",
    [
        # Case: msg does not have 'scanID'
        ({"data": {}}, {}, {}),
        # Case: msg contains all valid fields for multiple plots
        (
            {
                "data": {
                    "samy": {"samy": {"value": 10}},
                    "bpm4i": {"bpm4i": {"value": 5}},
                    "gauss_bpm": {"gauss_bpm": {"value": 7}},
                },
                "scanID": 1,
            },
            {},
            {
                ("samy", "samy", "bpm4i", "bpm4i"): {"x": [10], "y": [5]},
                ("samy", "samy", "gauss_bpm", "gauss_bpm"): {"x": [10], "y": [7]},
            },
        ),
    ],
)
def test_on_scan_segment_device_mode_all_entries_in_config(qtbot, msg, metadata, expected_data):
    """
    Ideal case when user fills config with both name and entry for all signals
    and both name and entry is included in msg as well.
    """
    plot_app = setup_plot_app(qtbot, config_device_mode_all_filled)

    # Create an instance of class and pass in the mock object for 'dev'
    plot_app.init_curves = MagicMock()
    plot_app.data = {}
    plot_app.scanID = 0

    plot_app.on_scan_segment(msg, metadata)
    assert plot_app.data == expected_data


def mock_getitem(dev_name):
    mock_instance = MagicMock()
    # Here we match the dev_name to the corresponding hints
    if dev_name == "samy":
        mock_instance._hints = "samy"
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
        # Case: msg contains all valid fields
        (
            config_device_mode_all_filled,
            {
                "data": {
                    "samy": {"samy": {"value": 10}},
                    "bpm4i": {"bpm4i": {"value": 5}},
                    "gauss_bpm": {"gauss_bpm": {"value": 7}},
                },
                "scanID": 1,
            },
            {},
            {
                ("samy", "samy", "bpm4i", "bpm4i"): {"x": [10], "y": [5]},
                ("samy", "samy", "gauss_bpm", "gauss_bpm"): {"x": [10], "y": [7]},
            },
            None,
        ),
        # Case: msg contains all valid fields and entry is missing in config, should use hints
        (
            config_device_mode_no_entry,
            {
                "data": {
                    "samy": {"samy": {"value": 10}},
                    "bpm4i": {"bpm4i": {"value": 5}},
                    "gauss_bpm": {"gauss_bpm": {"value": 7}},
                },
                "scanID": 1,
            },
            {},
            {
                ("samy", "samy", "bpm4i", "bpm4i"): {"x": [10], "y": [5]},
                ("samy", "samy", "gauss_bpm", "gauss_bpm"): {"x": [10], "y": [7]},
            },
            {"samy": "samy", "bpm4i": "bpm4i", "gauss_bpm": "gauss_bpm"},
        ),
    ],
)
def test_on_scan_segment_device_mode_with_hints(
    qtbot, config, msg, metadata, expected_data, mock_hints
):
    plot_app = setup_plot_app(qtbot, config)

    # if mock_hints:
    #     with patch.object(plot_app.dev, "__getitem__", autospec=True) as mock_dev_getitem:
    #         mock_instance = MagicMock()
    #         for k, v in mock_hints.items():
    #             mock_instance._hints = v
    #             mock_dev_getitem.side_effect = (
    #                 lambda dev_name: mock_instance if dev_name == k else None
    #             )

    # plot_app.dev.__getitem__.return_value._hints = "samy"

    # Initialize and run test
    plot_app.init_curves = MagicMock()
    plot_app.data = {}
    plot_app.scanID = 0

    # with patch.object(plot_app.dev, "__getitem__", side_effect=mock_getitem):
    #     plot_app.on_scan_segment(msg, metadata)

    plot_app.dev.__getitem__.side_effect = mock_getitem

    plot_app.on_scan_segment(msg, metadata)
    assert plot_app.data == expected_data


# def test_on_scan_segment_device_mode(qtbot, msg, metadata, expected_data):
#     plot_app = setup_plot_app(qtbot, config_device_mode_all_filled)
#
#     # with patch("bec_widgets.examples.extreme.extreme.dev") as dev:
#     # plot_app.dev.__getitem__.return_value._hints = {
#     #     "samy": MagicMock(_hints=["samy"]),
#     #     "bpm4i": MagicMock(_hints=["bpm4i"]),
#     # }
#     # print(plot_app.dev.__getitem__.return_value._hints)
#     # dev = {
#     #     "samy": MagicMock(_hints=["samy"]),
#     #     "bpm4i": MagicMock(_hints=["bpm4i"]),
#     # }
#
#     # Create an instance of class and pass in the mock object for 'dev'
#     plot_app.init_curves = MagicMock()
#     plot_app.data = {}
#     plot_app.scanID = 0
#
#     plot_app.on_scan_segment(msg, metadata)
#     assert plot_app.data == expected_data
