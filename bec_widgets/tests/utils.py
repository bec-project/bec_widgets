"""
Helpers for testing BEC widgets against a mocked BEC client. The fixtures built on top of them are
in :mod:`bec_widgets.tests.fixtures`.
"""

import json
import time
from unittest.mock import patch

import fakeredis
import h5py
from bec_lib import messages, service_config
from bec_lib.client import BECClient
from bec_lib.messages import _StoredDataInfo
from qtpy.QtCore import QEvent, QEventLoop

from bec_widgets.tests.fake_devices import DEVICES, DMMock
from bec_widgets.utils.bec_dispatcher import QtRedisConnector


def process_all_deferred_deletes(qapp):
    qapp.sendPostedEvents(None, QEvent.DeferredDelete)
    qapp.processEvents(QEventLoop.AllEvents)


_REDIS_CONN: QtRedisConnector | None = None


def global_mock_qt_redis_connector(*_, **__):
    global _REDIS_CONN
    if _REDIS_CONN is None:
        _REDIS_CONN = QtRedisConnector(bootstrap="localhost:1", redis_cls=fakeredis.FakeRedis)
    return _REDIS_CONN


def mock_client(*_, **__):
    """Create a BECClient on a shared fakeredis connector, populated with the fake DEVICES."""
    with (
        patch("bec_lib.client.DeviceManagerBase", DMMock),
        patch("bec_lib.client.DAPPlugins"),
        patch("bec_lib.client.Scans"),
        patch("bec_lib.client.ScanManager"),
        patch("bec_lib.bec_service.BECAccess"),
    ):
        client = BECClient(
            config=service_config.ServiceConfig(config={"redis": {"host": "localhost", "port": 1}}),
            connector_cls=global_mock_qt_redis_connector,
        )
        client.start()
    client.device_manager.add_devices(DEVICES)
    return client


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
        exit_status=metadata["status"],
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
