# pylint: skip-file
import json
import time
from unittest.mock import MagicMock

import h5py
from bec_lib import messages
from bec_lib.bec_service import messages
from bec_lib.config_helper import ConfigHelper
from bec_lib.device import Device as BECDevice
from bec_lib.device import Positioner as BECPositioner
from bec_lib.device import ReadoutPriority
from bec_lib.devicemanager import DeviceContainer
from bec_lib.messages import _StoredDataInfo
from bec_lib.scan_history import ScanHistory
from qtpy.QtCore import QEvent, QEventLoop


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
            "deviceTags": {"user device"},
            "enabled": enabled,
            "readOnly": False,
            "name": self.name,
        }
        self._info = {
            "signals": {
                self.name: {
                    "kind_str": "hinted",
                    "component_name": self.name,
                    "obj_name": self.name,
                    "signal_class": "Signal",
                }
            }
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
            "deviceTags": {"user motors"},
            "enabled": enabled,
            "readOnly": False,
            "name": self.name,
        }
        self._info = {
            "signals": {
                "readback": {
                    "kind_str": "hinted",
                    "component_name": "readback",
                    "obj_name": self.name,
                },  # hinted
                "setpoint": {
                    "kind_str": "normal",
                    "component_name": "setpoint",
                    "obj_name": f"{self.name}_setpoint",
                },  # normal
                "velocity": {
                    "kind_str": "config",
                    "component_name": "velocity",
                    "obj_name": f"{self.name}_velocity",
                },  # config
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

    def read(self, cached=False):
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

    def __init__(self, name="test", limits=None, read_value=1.0, enabled=True):
        super().__init__(name, limits=limits, read_value=read_value, enabled=enabled)


class Device(FakeDevice):
    """just placeholder for testing embedded isinstance check in DeviceCombobox"""

    def __init__(self, name, enabled=True):
        super().__init__(name, enabled)


class DMMock:
    def __init__(self, *args, **kwargs):
        self._service = args[0]
        self.config_helper = ConfigHelper(self._service.connector, self._service._service_name)
        self.devices = DeviceContainer()
        self.enabled_devices = [device for device in self.devices if device.enabled]

    def add_devices(self, devices: list):
        """
        Add devices to the DeviceContainer.

        Args:
            devices (list): List of device instances to add.
        """
        for device in devices:
            self.devices[device.name] = device

    def get_bec_signals(self, signal_class_name: str):
        """
        Emulate DeviceManager.get_bec_signals for unit-tests.

        For “AsyncSignal” we list every device whose readout_priority is
        ReadoutPriority.ASYNC and build a minimal tuple
        (device_name, signal_name, signal_info_dict) that matches the real
        API shape used by Waveform._check_async_signal_found.
        """
        signals: list[tuple[str, str, dict]] = []
        if signal_class_name != "AsyncSignal":
            return signals

        for device in self.devices.values():
            if getattr(device, "readout_priority", None) == ReadoutPriority.ASYNC:
                device_name = device.name
                signal_name = device.name  # primary signal in our mocks
                signal_info = {
                    "component_name": signal_name,
                    "obj_name": signal_name,
                    "kind_str": "hinted",
                    "signal_class": signal_class_name,
                    "metadata": {
                        "connected": True,
                        "precision": None,
                        "read_access": True,
                        "timestamp": 0.0,
                        "write_access": True,
                    },
                }
                signals.append((device_name, signal_name, signal_info))
        return signals

    def _get_redis_device_config(self) -> list[dict]:
        """Mock method to emulate DeviceManager._get_redis_device_config."""
        configs = []
        for device in self.devices.values():
            configs.append(device._config)
        return configs

    def initialize(*_): ...

    def shutdown(self): ...


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


class DummyData:
    def __init__(self, val, timestamps):
        self.val = val
        self.timestamps = timestamps

    def get(self, key, default=None):
        if key == "val":
            return self.val
        return default


def create_dummy_scan_item():
    """
    Helper to create a dummy scan item with both live_data and metadata/status_message info.
    """
    dummy_live_data = {
        "samx": {"samx": DummyData(val=[10, 20, 30], timestamps=[100, 200, 300])},
        "samy": {"samy": DummyData(val=[5, 10, 15], timestamps=[100, 200, 300])},
        "bpm4i": {"bpm4i": DummyData(val=[5, 6, 7], timestamps=[101, 201, 301])},
        "async_device": {"async_device": DummyData(val=[1, 2, 3], timestamps=[11, 21, 31])},
    }
    dummy_scan = MagicMock()
    dummy_scan.live_data = dummy_live_data
    dummy_scan.metadata = {
        "bec": {
            "scan_id": "dummy",
            "scan_report_devices": ["samx"],
            "readout_priority": {"monitored": ["bpm4i"], "async": ["async_device"]},
        }
    }
    dummy_scan.status_message.info = {
        "readout_priority": {"monitored": ["bpm4i"], "async": ["async_device"]},
        "scan_report_devices": ["samx"],
    }
    return dummy_scan


def inject_scan_history(widget, scan_history_factory, *history_args):
    """
    Helper to inject scan history messages into client history.
    """
    history_msgs = []
    for scan_id, scan_number in history_args:
        history_msgs.append(scan_history_factory(scan_id=scan_id, scan_number=scan_number))
    widget.client.history = ScanHistory(widget.client, False)
    for msg in history_msgs:
        widget.client.history._scan_data[msg.scan_id] = msg
        widget.client.history._scan_ids.append(msg.scan_id)
    widget.client.queue.scan_storage.current_scan = None
    return history_msgs


def create_history_file(file_path, data: dict, metadata: dict) -> messages.ScanHistoryMessage:
    """
    Helper to create a history file with the given data.
    The data should contain readout groups, e.g.
    {
        "baseline": {"samx": {"samx": {"value": [1, 2, 3], "timestamp": [100, 200, 300]}},
        "monitored": {"bpm4i": {"bpm4i": {"value": [5, 6, 7], "timestamp": [101, 201, 301]}}},
        "async": {"async_device": {"async_device": {"value": [1, 2, 3], "timestamp": [11, 21, 31]}}},
    }

    """

    with h5py.File(file_path, "w") as f:
        _metadata = f.create_group("entry/collection/metadata")
        _metadata.create_dataset("sample_name", data="test_sample")
        metadata_bec = f.create_group("entry/collection/metadata/bec")
        for key, value in metadata.items():
            if isinstance(value, dict):
                metadata_bec.create_group(key)
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, list):
                        sub_value = json.dumps(sub_value)
                        metadata_bec[key].create_dataset(sub_key, data=sub_value)
                    elif isinstance(sub_value, dict):
                        for sub_sub_key, sub_sub_value in sub_value.items():
                            sub_sub_group = metadata_bec[key].create_group(sub_key)
                            # Handle _StoredDataInfo objects
                            if isinstance(sub_sub_value, _StoredDataInfo):
                                # Store the numeric shape
                                sub_sub_group.create_dataset("shape", data=sub_sub_value.shape)
                                # Store the dtype as a UTF-8 string
                                dt = sub_sub_value.dtype or ""
                                sub_sub_group.create_dataset(
                                    "dtype", data=dt, dtype=h5py.string_dtype(encoding="utf-8")
                                )
                                continue
                            if isinstance(sub_sub_value, list):
                                json_val = json.dumps(sub_sub_value)
                                sub_sub_group.create_dataset(sub_sub_key, data=json_val)
                            elif isinstance(sub_sub_value, dict):
                                for k2, v2 in sub_sub_value.items():
                                    val = json.dumps(v2) if isinstance(v2, list) else v2
                                    sub_sub_group.create_dataset(k2, data=val)
                            else:
                                sub_sub_group.create_dataset(sub_sub_key, data=sub_sub_value)
                    else:
                        metadata_bec[key].create_dataset(sub_key, data=sub_value)
            else:
                metadata_bec.create_dataset(key, data=value)
        for group, devices in data.items():
            readout_group = f.create_group(f"entry/collection/readout_groups/{group}")

            for device, device_data in devices.items():
                dev_group = f.create_group(f"entry/collection/devices/{device}")
                for signal, signal_data in device_data.items():
                    signal_group = dev_group.create_group(signal)
                    for signal_key, signal_values in signal_data.items():
                        signal_group.create_dataset(signal_key, data=signal_values)

                readout_group[device] = h5py.SoftLink(f"/entry/collection/devices/{device}")
    msg = messages.ScanHistoryMessage(
        scan_id=metadata["scan_id"],
        scan_name=metadata["scan_name"],
        exit_status=metadata["exit_status"],
        file_path=file_path,
        scan_number=metadata["scan_number"],
        dataset_number=metadata["dataset_number"],
        start_time=time.time(),
        end_time=time.time(),
        num_points=metadata["num_points"],
        request_inputs=metadata["request_inputs"],
        stored_data_info=metadata.get("stored_data_info"),
        metadata={"scan_report_devices": metadata.get("scan_report_devices")},
    )
    return msg


def create_widget(qtbot, widget, *args, **kwargs):
    """
    Create a widget and add it to the qtbot for testing. This is a helper function that
    should be used in all tests that require a widget to be created.

    Args:
        qtbot (fixture): pytest-qt fixture
        widget (QWidget): widget class to be created
        *args: positional arguments for the widget
        **kwargs: keyword arguments for the widget

    Returns:
        QWidget: the created widget
    """
    widget = widget(*args, **kwargs)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


def process_all_deferred_deletes(qapp):
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)
