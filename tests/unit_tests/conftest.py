import json
import time

import h5py
import numpy as np
import pytest
from bec_lib import messages
from bec_qthemes import apply_theme
from pytestqt.exceptions import TimeoutError as QtBotTimeoutError
from qtpy.QtWidgets import QApplication

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils import bec_dispatcher as bec_dispatcher_module
from bec_widgets.utils import error_popups


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    item.stash["failed"] = rep.failed


@pytest.fixture(autouse=True)
def qapplication(qtbot, request, testable_qtimer_class):  # pylint: disable=unused-argument
    qapp = QApplication.instance()
    if not hasattr(qapp, "theme"):
        apply_theme("light")
    qapp.processEvents()

    yield

    # if the test failed, we don't want to check for open widgets as
    # it simply pollutes the output
    if request.node.stash._storage.get("failed"):
        print("Test failed, skipping cleanup checks")
        return
    bec_dispatcher = bec_dispatcher_module.BECDispatcher()
    bec_dispatcher.stop_cli_server()

    testable_qtimer_class.check_all_stopped(qtbot)
    qapp = QApplication.instance()
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
                            if isinstance(sub_sub_value, list):
                                sub_sub_value = json.dumps(sub_sub_value)
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
