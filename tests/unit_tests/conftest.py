import json
import time
from math import inf
from unittest import mock
from unittest.mock import MagicMock, PropertyMock, patch

import fakeredis
import h5py
import numpy as np
import pytest
from bec_lib import messages, service_config
from bec_lib.bec_service import messages
from bec_lib.client import BECClient
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import _StoredDataInfo
from bec_lib.scan_history import ScanHistory
from bec_qthemes import apply_theme
from ophyd._pyepics_shim import _dispatcher
from pytestqt.exceptions import TimeoutError as QtBotTimeoutError
from qtpy.QtCore import QEvent, QEventLoop
from qtpy.QtWidgets import QApplication, QMessageBox

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.tests.utils import DEVICES, DMMock, FakePositioner, Positioner
from bec_widgets.utils import bec_dispatcher as bec_dispatcher_module
from bec_widgets.utils import error_popups
from bec_widgets.utils.bec_dispatcher import QtRedisConnector

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
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)


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


_REDIS_CONN: QtRedisConnector | None = None


def global_mock_qt_redis_connector(*_, **__):
    global _REDIS_CONN
    if _REDIS_CONN is None:
        _REDIS_CONN = QtRedisConnector(bootstrap="localhost:1", redis_cls=fakeredis.FakeRedis)
    return _REDIS_CONN


def mock_client(*_, **__):
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
    return client


@pytest.fixture(autouse=True)
def bec_dispatcher(threads_check):  # pylint: disable=unused-argument
    with mock.patch.object(bec_dispatcher_module, "BECClient", mock_client):
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


@pytest.fixture(scope="function")
def mocked_client(bec_dispatcher):

    # Ensure isinstance check for Positioner passes
    original_isinstance = isinstance

    def isinstance_mock(obj, class_info):
        if class_info == Positioner and isinstance(obj, FakePositioner):
            return True
        return original_isinstance(obj, class_info)

    with patch("builtins.isinstance", new=isinstance_mock):
        yield bec_dispatcher.client
    bec_dispatcher.client.connector.shutdown()


@pytest.fixture(scope="function")
def mock_client_w_devices(mocked_client):
    mocked_client.device_manager.add_devices(DEVICES)


##################################################
# Client Fixture with DAP
##################################################
@pytest.fixture(scope="function")
def dap_plugin_message():
    msg = messages.AvailableResourceMessage(
        **{
            "resource": {
                "GaussianModel": {
                    "class": "LmfitService1D",
                    "user_friendly_name": "GaussianModel",
                    "class_doc": "A model based on a Gaussian or normal distribution lineshape.\n\n    The model has three Parameters: `amplitude`, `center`, and `sigma`.\n    In addition, parameters `fwhm` and `height` are included as\n    constraints to report full width at half maximum and maximum peak\n    height, respectively.\n\n    .. math::\n\n        f(x; A, \\mu, \\sigma) = \\frac{A}{\\sigma\\sqrt{2\\pi}} e^{[{-{(x-\\mu)^2}/{{2\\sigma}^2}}]}\n\n    where the parameter `amplitude` corresponds to :math:`A`, `center` to\n    :math:`\\mu`, and `sigma` to :math:`\\sigma`. The full width at half\n    maximum is :math:`2\\sigma\\sqrt{2\\ln{2}}`, approximately\n    :math:`2.3548\\sigma`.\n\n    For more information, see: https://en.wikipedia.org/wiki/Normal_distribution\n\n    ",
                    "run_doc": "A model based on a Gaussian or normal distribution lineshape.\n\n    The model has three Parameters: `amplitude`, `center`, and `sigma`.\n    In addition, parameters `fwhm` and `height` are included as\n    constraints to report full width at half maximum and maximum peak\n    height, respectively.\n\n    .. math::\n\n        f(x; A, \\mu, \\sigma) = \\frac{A}{\\sigma\\sqrt{2\\pi}} e^{[{-{(x-\\mu)^2}/{{2\\sigma}^2}}]}\n\n    where the parameter `amplitude` corresponds to :math:`A`, `center` to\n    :math:`\\mu`, and `sigma` to :math:`\\sigma`. The full width at half\n    maximum is :math:`2\\sigma\\sqrt{2\\ln{2}}`, approximately\n    :math:`2.3548\\sigma`.\n\n    For more information, see: https://en.wikipedia.org/wiki/Normal_distribution\n\n    \n        Args:\n            scan_item (ScanItem): Scan item or scan ID\n            device_x (DeviceBase | str): Device name for x\n            signal_x (DeviceBase | str): Signal name for x\n            device_y (DeviceBase | str): Device name for y\n            signal_y (DeviceBase | str): Signal name for y\n            parameters (dict): Fit parameters\n        ",
                    "run_name": "fit",
                    "signature": [
                        {
                            "name": "args",
                            "kind": "VAR_POSITIONAL",
                            "default": "_empty",
                            "annotation": "_empty",
                        },
                        {
                            "name": "scan_item",
                            "kind": "KEYWORD_ONLY",
                            "default": None,
                            "annotation": "ScanItem | str",
                        },
                        {
                            "name": "device_x",
                            "kind": "KEYWORD_ONLY",
                            "default": None,
                            "annotation": "DeviceBase | str",
                        },
                        {
                            "name": "signal_x",
                            "kind": "KEYWORD_ONLY",
                            "default": None,
                            "annotation": "DeviceBase | str",
                        },
                        {
                            "name": "device_y",
                            "kind": "KEYWORD_ONLY",
                            "default": None,
                            "annotation": "DeviceBase | str",
                        },
                        {
                            "name": "signal_y",
                            "kind": "KEYWORD_ONLY",
                            "default": None,
                            "annotation": "DeviceBase | str",
                        },
                        {
                            "name": "parameters",
                            "kind": "KEYWORD_ONLY",
                            "default": None,
                            "annotation": "dict",
                        },
                        {
                            "name": "kwargs",
                            "kind": "VAR_KEYWORD",
                            "default": "_empty",
                            "annotation": "_empty",
                        },
                    ],
                    "auto_fit_supported": True,
                    "params": {
                        "amplitude": {
                            "name": "amplitude",
                            "value": 1.0,
                            "vary": True,
                            "min": -inf,
                            "max": inf,
                            "expr": None,
                            "brute_step": None,
                            "user_data": None,
                        },
                        "center": {
                            "name": "center",
                            "value": 0.0,
                            "vary": True,
                            "min": -inf,
                            "max": inf,
                            "expr": None,
                            "brute_step": None,
                            "user_data": None,
                        },
                        "sigma": {
                            "name": "sigma",
                            "value": 1.0,
                            "vary": True,
                            "min": 0,
                            "max": inf,
                            "expr": None,
                            "brute_step": None,
                            "user_data": None,
                        },
                        "fwhm": {
                            "name": "fwhm",
                            "value": 2.35482,
                            "vary": False,
                            "min": -inf,
                            "max": inf,
                            "expr": "2.3548200*sigma",
                            "brute_step": None,
                            "user_data": None,
                        },
                        "height": {
                            "name": "height",
                            "value": 0.3989423,
                            "vary": False,
                            "min": -inf,
                            "max": inf,
                            "expr": "0.3989423*amplitude/max(1e-15, sigma)",
                            "brute_step": None,
                            "user_data": None,
                        },
                    },
                    "class_args": [],
                    "class_kwargs": {"model": "GaussianModel"},
                }
            }
        }
    )
    yield msg


@pytest.fixture(scope="function")
def mocked_client_with_dap(mocked_client, dap_plugin_message):
    mocked_client.device_manager.add_devices(DEVICES)
    dap_services = {
        "BECClient": messages.StatusMessage(name="BECClient", status=1, info={}),
        "DAPServer/LmfitService1D": messages.StatusMessage(
            name="LmfitService1D", status=1, info={}
        ),
    }
    type(mocked_client).service_status = PropertyMock(return_value=dap_services)
    mocked_client.connector.set(
        topic=MessageEndpoints.dap_available_plugins("dap"), msg=dap_plugin_message
    )

    # Patch the client's DAP attribute so that the available models include "GaussianModel"
    patched_models = {"GaussianModel": {}, "LorentzModel": {}, "SineModel": {}}
    mocked_client.dap._available_dap_plugins = patched_models

    yield mocked_client


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
