# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
from bec_lib.client import BECClient
from bec_lib.device import Positioner, ReadoutPriority
from bec_lib.devicemanager import DeviceContainer
from bec_lib.redis_connector import RedisConnector


class FakeDevice:
    """Fake minimal positioner class for testing."""

    def __init__(self, name, enabled=True, readout_priority=ReadoutPriority.MONITORED):
        self.name = name
        self.enabled = enabled
        self.signals = {self.name: {"value": 1.0}}
        self.description = {self.name: {"source": self.name, "dtype": "number", "shape": []}}
        self.readout_priority = readout_priority
        self._config = {
            "readoutPriority": "baseline",
            "deviceClass": "ophyd_devices.SimPositioner",
            "deviceConfig": {
                "delay": 1,
                "limits": [-50, 50],
                "tolerance": 0.01,
                "update_frequency": 400,
            },
            "deviceTags": ["user motors"],
            "enabled": enabled,
            "readOnly": False,
            "name": self.name,
        }

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


class FakePositioner(FakeDevice):
    def __init__(
        self,
        name,
        enabled=True,
        limits=None,
        read_value=1.0,
        readout_priority=ReadoutPriority.MONITORED,
    ):
        super().__init__(name, enabled, readout_priority)
        self.limits = limits if limits is not None else [0, 0]
        self.read_value = read_value
        self.name = name

    @property
    def precision(self):
        return 3

    def set_read_value(self, value):
        self.read_value = value

    def read(self):
        return {
            self.name: {"value": self.read_value},
            f"{self.name}_setpoint": {"value": self.read_value},
            f"{self.name}_motor_is_moving": {"value": 0},
        }

    def set_limits(self, limits):
        self.limits = limits

    def move(self, value, relative=False):
        """Simulates moving the device to a new position."""
        if relative:
            self.read_value += value
        else:
            self.read_value = value
        # Respect the limits
        self.read_value = max(min(self.read_value, self.limits[1]), self.limits[0])

    @property
    def readback(self):
        return MagicMock(get=MagicMock(return_value=self.read_value))


class Positioner(FakePositioner):
    """just placeholder for testing embedded isinstance check in DeviceCombobox"""

    def __init__(self, name="test", limits=None, read_value=1.0):
        super().__init__(name, limits, read_value)


class Device(FakeDevice):
    """just placeholder for testing embedded isinstance check in DeviceCombobox"""

    def __init__(self, name, enabled=True):
        super().__init__(name, enabled)


class DMMock:
    def __init__(self):
        self.devices = DeviceContainer()

    def add_devives(self, devices: list):
        for device in devices:
            self.devices[device.name] = device


DEVICES = [
    FakePositioner("samx", limits=[-10, 10], read_value=2.0),
    FakePositioner("samy", limits=[-5, 5], read_value=3.0),
    FakePositioner("samz", limits=[-8, 8], read_value=4.0),
    FakePositioner("aptrx", limits=None, read_value=4.0),
    FakePositioner("aptry", limits=None, read_value=5.0),
    FakeDevice("gauss_bpm"),
    FakeDevice("gauss_adc1"),
    FakeDevice("gauss_adc2"),
    FakeDevice("gauss_adc3"),
    FakeDevice("bpm4i"),
    FakeDevice("bpm3a"),
    FakeDevice("bpm3i"),
    FakeDevice("eiger"),
    FakeDevice("async_device", readout_priority=ReadoutPriority.ASYNC),
    Positioner("test", limits=[-10, 10], read_value=2.0),
    Device("test_device"),
]


def fake_redis_server(host, port):
    redis = fakeredis.FakeRedis()
    return redis


@pytest.fixture(scope="function")
def mocked_client(bec_dispatcher):
    connector = RedisConnector("localhost:1", redis_cls=fake_redis_server)
    # Create a MagicMock object
    client = MagicMock()  # TODO change to real BECClient

    # Shutdown the original client
    bec_dispatcher.client.shutdown()
    # Mock the connector attribute
    bec_dispatcher.client = client

    # Mock the device_manager.devices attribute
    client.connector = connector
    client.device_manager = DMMock()
    client.device_manager.add_devives(DEVICES)

    def mock_mv(*args, relative=False):
        # Extracting motor and value pairs
        for i in range(0, len(args), 2):
            motor = args[i]
            value = args[i + 1]
            motor.move(value, relative=relative)
        return MagicMock(wait=MagicMock())

    client.scans = MagicMock(mv=mock_mv)

    # Ensure isinstance check for Positioner passes
    original_isinstance = isinstance

    def isinstance_mock(obj, class_info):
        if class_info == Positioner and isinstance(obj, FakePositioner):
            return True
        return original_isinstance(obj, class_info)

    with patch("builtins.isinstance", new=isinstance_mock):
        yield client
    connector.shutdown()  # TODO change to real BECClient
