from unittest.mock import MagicMock

from bec_lib.device import Device as BECDevice
from bec_lib.device import Positioner as BECPositioner
from bec_lib.device import ReadoutPriority
from bec_lib.devicemanager import DeviceContainer


class FakeDevice(BECDevice):
    """Fake minimal positioner class for testing."""

    def __init__(self, name, enabled=True, readout_priority=ReadoutPriority.MONITORED):
        super().__init__(name=name)
        self._enabled = enabled
        self.signals = {self.name: {"value": 1.0}}
        self.description = {self.name: {"source": self.name, "dtype": "number", "shape": []}}
        self._readout_priority = readout_priority
        self._config = {
            "readoutPriority": "baseline",
            "deviceClass": "ophyd.Device",
            "deviceConfig": {},
            "deviceTags": ["user device"],
            "enabled": enabled,
            "readOnly": False,
            "name": self.name,
        }

    @property
    def readout_priority(self):
        return self._readout_priority

    @readout_priority.setter
    def readout_priority(self, value):
        self._readout_priority = value

    @property
    def limits(self) -> tuple[float, float]:
        return self._limits

    @limits.setter
    def limits(self, value: tuple[float, float]):
        self._limits = value

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


class FakePositioner(BECPositioner):

    def __init__(
        self,
        name,
        enabled=True,
        limits=None,
        read_value=1.0,
        readout_priority=ReadoutPriority.MONITORED,
    ):
        super().__init__(name=name)
        # self.limits = limits if limits is not None else [0.0, 0.0]
        self.read_value = read_value
        self.setpoint_value = read_value
        self.motor_is_moving_value = 0
        self._enabled = enabled
        self._limits = limits
        self._readout_priority = readout_priority
        self.signals = {self.name: {"value": 1.0}}
        self.description = {self.name: {"source": self.name, "dtype": "number", "shape": []}}
        self._config = {
            "readoutPriority": "baseline",
            "deviceClass": "ophyd_devices.SimPositioner",
            "deviceConfig": {"delay": 1, "tolerance": 0.01, "update_frequency": 400},
            "deviceTags": ["user motors"],
            "enabled": enabled,
            "readOnly": False,
            "name": self.name,
        }
        self._info = {
            "signals": {
                "readback": {"kind_str": "5"},  # hinted
                "setpoint": {"kind_str": "1"},  # normal
                "velocity": {"kind_str": "2"},  # config
            }
        }
        self.signals = {
            self.name: {"value": self.read_value},
            f"{self.name}_setpoint": {"value": self.setpoint_value},
            f"{self.name}_motor_is_moving": {"value": self.motor_is_moving_value},
        }

    @property
    def readout_priority(self):
        return self._readout_priority

    @readout_priority.setter
    def readout_priority(self, value):
        self._readout_priority = value

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @property
    def limits(self) -> tuple[float, float]:
        return self._limits

    @limits.setter
    def limits(self, value: tuple[float, float]):
        self._limits = value

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
        self.read_value = fake_value

    def describe(self) -> dict:
        """
        Get the description of the device
        Returns:
            dict: Description of the device
        """
        return self.description

    @property
    def precision(self):
        return 3

    def set_read_value(self, value):
        self.read_value = value

    def read(self):
        return self.signals

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
        self.enabled_devices = [device for device in self.devices if device.enabled]

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
    FakeDevice("eiger", readout_priority=ReadoutPriority.ASYNC),
    FakeDevice("waveform1d"),
    FakeDevice("async_device", readout_priority=ReadoutPriority.ASYNC),
    Positioner("test", limits=[-10, 10], read_value=2.0),
    Device("test_device"),
]


def check_remote_data_size(widget, plot_name, num_elements):
    """
    Check if the remote data has the correct number of elements.
    Used in the qtbot.waitUntil function.
    """
    return len(widget.get_all_data()[plot_name]["x"]) == num_elements
