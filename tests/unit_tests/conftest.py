import json
import time

import h5py
import numpy as np
import pytest
from bec_lib import messages
from bec_lib.messages import _StoredDataInfo
from bec_qthemes import apply_theme
from pytestqt.exceptions import TimeoutError as QtBotTimeoutError
from qtpy.QtCore import QEvent, QEventLoop
from qtpy.QtWidgets import QApplication, QMessageBox

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils import bec_dispatcher as bec_dispatcher_module
from bec_widgets.utils import error_popups

# Patch to set default RAISE_ERROR_DEFAULT to True for tests
# This means that by default, error popups will raise exceptions during tests
# error_popups.RAISE_ERROR_DEFAULT = True


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    item.stash["failed"] = rep.failed


def process_all_deferred_deletes(qapp):
    qapp.sendPostedEvents(None, QEvent.DeferredDelete)
    qapp.processEvents(QEventLoop.AllEvents)


@pytest.fixture(autouse=True)
def qapplication(qtbot, request, testable_qtimer_class):  # pylint: disable=unused-argument
    qapp = QApplication.instance()
    process_all_deferred_deletes(qapp)
    apply_theme("light")
    qapp.processEvents()

    yield

    # if the test failed, we don't want to check for open widgets as
    # it simply pollutes the output
    # stop pyepics dispatcher for leaking tests
    from ophyd._pyepics_shim import _dispatcher

    _dispatcher.stop()
    if request.node.stash._storage.get("failed"):
        print("Test failed, skipping cleanup checks")
        return
    bec_dispatcher = bec_dispatcher_module.BECDispatcher()
    bec_dispatcher.stop_cli_server()

    testable_qtimer_class.check_all_stopped(qtbot)
    qapp.processEvents()
    if hasattr(qapp, "os_listener") and qapp.os_listener:
        qapp.removeEventFilter(qapp.os_listener)
    try:
        qtbot.waitUntil(lambda: qapp.topLevelWidgets() == [])
    except QtBotTimeoutError as exc:
        raise TimeoutError(f"Failed to close all widgets: {qapp.topLevelWidgets()}") from exc


@pytest.fixture(autouse=True)
def rpc_register():
    yield RPCRegister()
    RPCRegister.reset_singleton()


@pytest.fixture(autouse=True)
def bec_dispatcher(threads_check):  # pylint: disable=unused-argument
    bec_dispatcher = bec_dispatcher_module.BECDispatcher()
    yield bec_dispatcher
    bec_dispatcher.disconnect_all()
    # clean BEC client
    bec_dispatcher.client.shutdown()
    # stop the cli server
    bec_dispatcher.stop_cli_server()
    # reinitialize singleton for next test
    bec_dispatcher_module.BECDispatcher.reset_singleton()


@pytest.fixture(autouse=True)
def clean_singleton():
    error_popups._popup_utility_instance = None


@pytest.fixture(autouse=True)
def suppress_message_box(monkeypatch):
    """
    Auto-suppress any QMessageBox.exec_ calls by returning Ok immediately.
    """
    monkeypatch.setattr(QMessageBox, "exec_", lambda *args, **kwargs: QMessageBox.Ok)


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


@pytest.fixture
def grid_scan_history_msg(tmpdir):
    x_grid, y_grid = np.meshgrid(np.linspace(-5, 5, 10), np.linspace(-5, 5, 10))

    x_flat = x_grid.T.ravel()
    y_flat = y_grid.T.ravel()
    positions = np.vstack((x_flat, y_flat)).T
    num_points = len(positions)
    data = {
        "baseline": {"bpm1a": {"bpm1a": {"value": [1], "timestamp": [100]}}},
        "monitored": {
            "bpm4i": {
                "bpm4i": {
                    "value": np.random.rand(num_points),
                    "timestamp": np.random.rand(num_points),
                }
            },
            "samx": {"samx": {"value": x_flat, "timestamp": np.random.rand(num_points)}},
            "samy": {"samy": {"value": y_flat, "timestamp": np.random.rand(num_points)}},
        },
        "async": {
            "async_device": {
                "async_device": {
                    "value": np.random.rand(num_points * 10),
                    "timestamp": np.random.rand(num_points * 10),
                }
            }
        },
    }
    metadata = {
        "scan_id": "test_scan",
        "scan_name": "grid_scan",
        "scan_type": "step",
        "exit_status": "closed",
        "scan_number": 1,
        "dataset_number": 1,
        "request_inputs": {
            "arg_bundle": ["samx", -5, 5, 10, "samy", -5, 5, 10],
            "kwargs": {"relative": True},
        },
        "positions": positions.tolist(),
        "num_points": num_points,
    }

    file_path = str(tmpdir.join("scan_1.h5"))
    return create_history_file(file_path, data, metadata)


@pytest.fixture
def scan_history_factory(tmpdir):
    """
    Factory to create scan history messages with custom parameters.
    Usage:
        msg1 = scan_history_factory(scan_id="id1", scan_number=1, num_points=10)
        msg2 = scan_history_factory(scan_id="id2", scan_number=2, scan_name="grid_scan", num_points=16)
    """

    def _factory(
        scan_id: str = "test_scan",
        scan_number: int = 1,
        dataset_number: int = 1,
        scan_name: str = "line_scan",
        scan_type: str = "step",
        num_points: int = 10,
        x_range: tuple = (-5, 5),
        y_range: tuple = (-5, 5),
    ):
        # Generate positions based on scan type
        if scan_name == "grid_scan":
            grid_size = int(np.sqrt(num_points))
            x_grid, y_grid = np.meshgrid(
                np.linspace(x_range[0], x_range[1], grid_size),
                np.linspace(y_range[0], y_range[1], grid_size),
            )
            x_flat = x_grid.T.ravel()
            y_flat = y_grid.T.ravel()
        else:
            x_flat = np.linspace(x_range[0], x_range[1], num_points)
            y_flat = np.linspace(y_range[0], y_range[1], num_points)
        positions = np.vstack((x_flat, y_flat)).T
        num_pts = len(positions)
        # Create dummy data
        data = {
            "baseline": {"bpm1a": {"bpm1a": {"value": [1], "timestamp": [100]}}},
            "monitored": {
                "bpm4i": {
                    "bpm4i": {
                        "value": np.random.rand(num_points),
                        "timestamp": np.random.rand(num_points),
                    }
                },
                "bpm3a": {
                    "bpm3a": {
                        "value": np.random.rand(num_points),
                        "timestamp": np.random.rand(num_points),
                    }
                },
                "samx": {"samx": {"value": x_flat, "timestamp": np.arange(num_pts)}},
                "samy": {"samy": {"value": y_flat, "timestamp": np.arange(num_pts)}},
            },
            "async": {
                "async_device": {
                    "async_device": {
                        "value": np.random.rand(num_pts * 10),
                        "timestamp": np.random.rand(num_pts * 10),
                    }
                }
            },
        }
        metadata = {
            "scan_id": scan_id,
            "scan_name": scan_name,
            "scan_type": scan_type,
            "exit_status": "closed",
            "scan_number": scan_number,
            "dataset_number": dataset_number,
            "request_inputs": {
                "arg_bundle": [
                    "samx",
                    x_range[0],
                    x_range[1],
                    num_pts,
                    "samy",
                    y_range[0],
                    y_range[1],
                    num_pts,
                ],
                "kwargs": {"relative": True},
            },
            "positions": positions.tolist(),
            "num_points": num_pts,
            "stored_data_info": {
                "samx": {"samx": _StoredDataInfo(shape=(num_points,), dtype="float64")},
                "samy": {"samy": _StoredDataInfo(shape=(num_points,), dtype="float64")},
                "bpm4i": {"bpm4i": _StoredDataInfo(shape=(10,), dtype="float64")},
                "async_device": {
                    "async_device": _StoredDataInfo(shape=(num_points * 10,), dtype="float64")
                },
            },
            "scan_report_devices": [b"samx"],
        }
        file_path = str(tmpdir.join(f"{scan_id}.h5"))
        return create_history_file(file_path, data, metadata)

    return _factory
