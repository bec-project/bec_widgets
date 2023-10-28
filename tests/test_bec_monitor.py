from unittest.mock import MagicMock

import pytest
from PyQt5.QtWidgets import QApplication

from bec_widgets.widgets import BECMonitor

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


config_device_no_entry = {
    "plot_settings": {
        "background_color": "white",
        "num_columns": 5,  # Number of columns higher than the actual number of plots
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
                    ],
                },
            },
            {
                "plot_name": "Grid plot 2",
                "x": {"label": "Motor X", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "BPM",
                    "signals": [
                        {"name": "gauss_adc1", "entry": "gauss_adc1"},
                    ],
                },
            },
            {
                "plot_name": "Grid plot 3",
                "x": {"label": "Motor Y", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "BPM",
                    "signals": [{"name": "gauss_adc2", "entry": "gauss_adc2"}],
                },
            },
            {
                "plot_name": "Grid plot 4",
                "x": {"label": "Motor Y", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "BPM",
                    "signals": [{"name": "bpm4i", "entry": "bpm4i"}],
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
    widget = BECMonitor(config=config, client=client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


@pytest.fixture(scope="module")  # TODO is this needed?
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
    "config, scan_type, number_of_plots",
    [
        (config_device, False, 2),
        (config_scan, True, 4),
        (config_device_no_entry, False, 2),
    ],
)
def test_initialization_with_device_config(qtbot, config, scan_type, number_of_plots):
    widget = setup_monitor(qtbot, config)
    assert isinstance(widget, BECMonitor)
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


def mock_getitem(dev_name):
    """Helper function to mock the __getitem__ method of the 'dev'."""
    mock_instance = MagicMock()
    if dev_name == "samx":
        mock_instance._hints = "samx"
    elif dev_name == "bpm4i":
        mock_instance._hints = "bpm4i"
    elif dev_name == "gauss_bpm":
        mock_instance._hints = "gauss_bpm"

    return mock_instance


# mocked messages and metadatas
msg_1 = {
    "data": {
        "samx": {"samx": {"value": 10}},
        "bpm4i": {"bpm4i": {"value": 5}},
        "gauss_bpm": {"gauss_bpm": {"value": 6}},
        "gauss_adc1": {"gauss_adc1": {"value": 8}},
        "gauss_adc2": {"gauss_adc2": {"value": 9}},
    },
    "scanID": 1,
}
metadata_grid = {"scan_name": "grid_scan"}
metadata_line = {"scan_name": "line_scan"}


@pytest.mark.parametrize(
    "config, msg, metadata, expected_data",
    [
        # case: msg does not have 'scanid'
        (config_device, {"data": {}}, {}, {}),
        # case: scan_types is false, msg contains all valid fields, and entry is present in config
        (
            config_device,
            msg_1,
            {},
            {
                ("samx", "samx", "bpm4i", "bpm4i"): {"x": [10], "y": [5]},
                ("samx", "samx", "gauss_adc1", "gauss_adc1"): {"x": [10], "y": [8]},
                ("samx", "samx", "gauss_adc2", "gauss_adc2"): {"x": [10], "y": [9]},
            },
        ),
        # case: scan_types is false, msg contains all valid fields and entry is missing in config, should use hints
        (
            config_device_no_entry,
            msg_1,
            {},
            {
                ("samx", "samx", "bpm4i", "bpm4i"): {"x": [10], "y": [5]},
                ("samx", "samx", "gauss_bpm", "gauss_bpm"): {"x": [10], "y": [6]},
            },
        ),
        # case: scan_types is true, msg contains all valid fields, metadata contains scan "line_scan:"
        (
            config_scan,
            msg_1,
            metadata_line,
            {
                ("samx", "samx", "bpm4i", "bpm4i"): {"x": [10], "y": [5]},
                ("samx", "samx", "gauss_bpm", "gauss_bpm"): {"x": [10], "y": [6]},
                ("samx", "samx", "gauss_adc1", "gauss_adc1"): {"x": [10], "y": [8]},
                ("samx", "samx", "gauss_adc2", "gauss_adc2"): {"x": [10], "y": [9]},
            },
        ),
        (
            config_scan,
            msg_1,
            metadata_grid,
            {
                ("samx", "samx", "bpm4i", "bpm4i"): {"x": [10], "y": [5]},
                ("samx", "samx", "gauss_adc1", "gauss_adc1"): {"x": [10], "y": [8]},
                ("samx", "samx", "gauss_adc2", "gauss_adc2"): {"x": [10], "y": [9]},
                ("samx", "samx", "gauss_bpm", "gauss_bpm"): {"x": [10], "y": [6]},
            },
        ),
    ],
)
def test_on_scan_segment(qtbot, config, msg, metadata, expected_data):
    plot_app = setup_monitor(qtbot, config)

    # Initialize and run test
    # plot_app.init_curves = MagicMock()
    plot_app.data = {}
    plot_app.scanID = 0

    # Get hints
    plot_app.dev.__getitem__.side_effect = mock_getitem

    plot_app.on_scan_segment(msg, metadata)
    assert plot_app.data == expected_data
