# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
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


class FakeDevice:
    """Fake minimal positioner class for testing."""

    def __init__(self, name, enabled=True):
        self.name = name
        self.enabled = enabled
        self.signals = {self.name: {"value": 1.0}}
        self.description = {self.name: {"source": self.name}}

    def __contains__(self, item):
        return item == self.name

    @property
    def _hints(self):
        return [self.name]

    def set_value(self, fake_value: float = 1.0) -> None:
        """
        Setup fake value for device readout
        Args:
            fake_value(float): Desired fake value
        """
        self.signals[self.name]["value"] = fake_value

    def describe(self) -> dict:
        """
        Get the description of the device
        Returns:
            dict: Description of the device
        """
        return self.description


def get_mocked_device(device_name: str):
    """
    Helper function to mock the devices
    Args:
        device_name(str): Name of the device to mock
    """
    return FakeDevice(name=device_name, enabled=True)


@pytest.fixture(scope="function")
def mocked_client():
    # Create a dictionary of mocked devices
    device_names = ["samx", "gauss_bpm", "gauss_adc1", "gauss_adc2", "gauss_adc3", "bpm4i"]
    mocked_devices = {name: get_mocked_device(name) for name in device_names}

    # Create a MagicMock object
    client = MagicMock()

    # Mock the device_manager.devices attribute
    client.device_manager.devices = MagicMock()
    client.device_manager.devices.__getitem__.side_effect = lambda x: mocked_devices.get(x)
    client.device_manager.devices.__contains__.side_effect = lambda x: x in mocked_devices

    # Set each device as an attribute of the mock
    for name, device in mocked_devices.items():
        setattr(client.device_manager.devices, name, device)

    return client


@pytest.fixture(scope="function")
def monitor(bec_dispatcher, qtbot, mocked_client):
    # client = MagicMock()
    widget = BECMonitor(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.mark.parametrize(
    "config_name, scan_type, number_of_plots",
    [
        ("config_device", False, 2),
        ("config_device_no_entry", False, 2),
        # ("config_scan", True, 4),
    ],
)
def test_initialization_with_device_config(monitor, config_name, scan_type, number_of_plots):
    config = load_test_config(config_name)
    monitor.on_config_update(config)
    assert isinstance(monitor, BECMonitor)
    assert monitor.client is not None
    assert len(monitor.plot_data) == number_of_plots
    assert monitor.scan_types == scan_type


@pytest.mark.parametrize(
    "config_initial,config_update",
    [("config_device", "config_scan"), ("config_scan", "config_device")],
)
def test_on_config_update(monitor, config_initial, config_update):
    config_initial = load_test_config(config_initial)
    config_update = load_test_config(config_update)
    # validated config has to be compared
    config_initial_validated = monitor.validator.validate_monitor_config(
        config_initial
    ).model_dump()
    config_update_validated = monitor.validator.validate_monitor_config(config_update).model_dump()
    monitor.on_config_update(config_initial)
    assert monitor.config == config_initial_validated
    monitor.on_config_update(config_update)
    assert monitor.config == config_update_validated


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
    monitor.on_config_update(config)

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


def mock_get_scan_storage(scan_id, data):
    """Helper function to mock the __getitem__ method of the 'dev'."""
    mock_instance = MagicMock()
    mock_instance.get_scan_storage.return_value = data
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
        # case: msg does not have 'scanID'
        (
            "config_device",
            {"data": {}},
            {},
            {
                "scan_segment": {
                    "bpm4i": {"bpm4i": []},
                    "gauss_adc1": {"gauss_adc1": []},
                    "gauss_adc2": {"gauss_adc2": []},
                    "samx": {"samx": []},
                }
            },
        ),
        # case: scan_types is false, msg contains all valid fields, and entry is present in config
        (
            "config_device",
            msg_1,
            {},
            {
                "scan_segment": {
                    "bpm4i": {"bpm4i": [5]},
                    "gauss_adc1": {"gauss_adc1": [8]},
                    "gauss_adc2": {"gauss_adc2": [9]},
                    "samx": {"samx": [10]},
                }
            },
        ),
        # case: scan_types is false, msg contains all valid fields and entry is missing in config, should use hints
        (
            "config_device_no_entry",
            msg_1,
            {},
            {
                "scan_segment": {
                    "bpm4i": {"bpm4i": [5]},
                    "gauss_bpm": {"gauss_bpm": [6]},
                    "samx": {"samx": [10]},
                }
            },
        ),
        # case: scan_types is true, msg contains all valid fields, metadata contains scan "line_scan:"
        (
            "config_scan",
            msg_1,
            metadata_line,
            {
                "scan_segment": {
                    "bpm4i": {"bpm4i": [5]},
                    "gauss_adc1": {"gauss_adc1": [8]},
                    "gauss_adc2": {"gauss_adc2": [9]},
                    "gauss_bpm": {"gauss_bpm": [6]},
                    "samx": {"samx": [10]},
                }
            },
        ),
        (
            "config_scan",
            msg_1,
            metadata_grid,
            {
                "scan_segment": {
                    "bpm4i": {"bpm4i": [5]},
                    "gauss_adc1": {"gauss_adc1": [8]},
                    "gauss_adc2": {"gauss_adc2": [9]},
                    "gauss_bpm": {"gauss_bpm": [6]},
                    "samx": {"samx": [10]},
                }
            },
        ),
    ],
)
def test_on_scan_segment(monitor, config_name, msg, metadata, expected_data):
    config = load_test_config(config_name)
    monitor.on_config_update(config)

    # Get hints
    monitor.dev.__getitem__.side_effect = mock_getitem

    # Mock scan_storage.find_scan_by_ID
    mock_scan_data = MagicMock()
    mock_scan_data.data = {
        device_name: {
            entry: MagicMock(val=[msg["data"][device_name][entry]["value"]])
            for entry in msg["data"][device_name]
        }
        for device_name in msg["data"]
    }
    monitor.queue.scan_storage.find_scan_by_ID.return_value = mock_scan_data

    monitor.on_scan_segment(msg, metadata)
    assert monitor.database == expected_data
