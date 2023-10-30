import os
import yaml

import pytest
from unittest.mock import MagicMock

from bec_widgets.widgets import BECMonitor


def load_test_config(config_name):
    """Helper function to load config from yaml file."""
    config_path = os.path.join(os.path.dirname(__file__), "test_configs", f"{config_name}.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config


@pytest.fixture(scope="function")
def monitor(qtbot):
    client = MagicMock()
    widget = BECMonitor(client=client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.mark.parametrize(
    "config_name, scan_type, number_of_plots",
    [
        ("config_device", False, 2),
        ("config_device_no_entry", False, 2),
        ("config_scan", True, 4),
    ],
)
def test_initialization_with_device_config(monitor, config_name, scan_type, number_of_plots):
    config = load_test_config(config_name)
    monitor.update_config(config)
    assert isinstance(monitor, BECMonitor)
    assert monitor.config == config
    assert monitor.client is not None
    assert len(monitor.plot_data) == number_of_plots
    assert monitor.scan_types == scan_type


@pytest.mark.parametrize(
    "config_initial,config_update",
    [("config_device", "config_scan"), ("config_scan", "config_device")],
)
def test_update_config(monitor, config_initial, config_update):
    config_initial = load_test_config(config_initial)
    config_update = load_test_config(config_update)
    monitor.update_config(config_initial)
    assert monitor.config == config_initial
    monitor.update_config(config_update)
    assert monitor.config == config_update


@pytest.mark.parametrize(
    "config_name, expected_num_columns, expected_plot_names, expected_coordinates",
    [
        (
            "config_device",
            1,
            ["BPM4i plots vs samx", "Gauss plots vs samx"],
            [(0, 0), (1, 0)],
        ),
        (
            "config_scan",
            3,
            ["Grid plot 1", "Grid plot 2", "Grid plot 3", "Grid plot 4"],
            [(0, 0), (0, 1), (0, 2), (1, 0)],
        ),
    ],
)
def test_render_initial_plots(
    monitor, config_name, expected_num_columns, expected_plot_names, expected_coordinates
):
    config = load_test_config(config_name)
    monitor.update_config(config)

    assert monitor.config == config
    # Validate number of columns
    assert monitor.plot_settings["num_columns"] == expected_num_columns

    # Validate the plots are created correctly
    for expected_name in expected_plot_names:
        assert expected_name in monitor.plots.keys()

    # Validate the grid_coordinates
    assert monitor.grid_coordinates == expected_coordinates


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


# mocked messages and metadata
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
    "config_name, msg, metadata, expected_data",
    [
        # case: msg does not have 'scanid'
        ("config_device", {"data": {}}, {}, {}),
        # case: scan_types is false, msg contains all valid fields, and entry is present in config
        (
            "config_device",
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
            "config_device_no_entry",
            msg_1,
            {},
            {
                ("samx", "samx", "bpm4i", "bpm4i"): {"x": [10], "y": [5]},
                ("samx", "samx", "gauss_bpm", "gauss_bpm"): {"x": [10], "y": [6]},
            },
        ),
        # case: scan_types is true, msg contains all valid fields, metadata contains scan "line_scan:"
        (
            "config_scan",
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
            "config_scan",
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
def test_on_scan_segment(monitor, config_name, msg, metadata, expected_data):
    config = load_test_config(config_name)
    monitor.update_config(config)
    # Get hints
    monitor.dev.__getitem__.side_effect = mock_getitem

    monitor.on_scan_segment(msg, metadata)
    assert monitor.data == expected_data
