# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring

import pytest
from unittest.mock import MagicMock


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
    device_names = [
        "samx",
        "samy",
        "gauss_bpm",
        "gauss_adc1",
        "gauss_adc2",
        "gauss_adc3",
        "bpm4i",
        "bpm3a",
        "bpm3i",
    ]
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
