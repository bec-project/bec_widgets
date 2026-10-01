"""
Pytest fixtures for testing BEC widgets against a mocked BEC client, shared with plugin repos.

Import all of them into the ``conftest.py`` next to the widget tests::

    from bec_widgets.tests.fixtures import *  # noqa: F401,F403

The autouse fixtures reset the QApplication and the BEC singletons around every test, back the
dispatcher with a BECClient on fakeredis that knows the fake devices of
:mod:`bec_widgets.tests.fake_devices`, and fail a passing test that leaves a top-level widget open
or a timer running. ``mocked_client``, ``mocked_client_with_dap`` and the scan history fixtures are
available on request, :func:`bec_widgets.tests.utils.create_widget` creates widgets under test.

The fixtures are deliberately not registered as a pytest plugin, so that they only apply below the
conftest that imports them and leave the non-GUI tests of a repository alone. Importing this module
replaces ``qtpy.QtCore.QTimer`` with :class:`TestableQTimer`, which only affects widget modules
imported afterwards: import it in a conftest that is loaded before the widgets under test.

Requires ``bec_widgets[dev]`` (pytest-qt, fakeredis) and bec_lib's ``threads_check`` fixture.
"""

# pylint: disable=redefined-outer-name,unused-argument,wrong-import-position
import os

# Keep ophyd on its dummy control layer, so importing it does not create a real EPICS CA context
os.environ.setdefault("OPHYD_CONTROL_LAYER", "dummy")

import qtpy.QtCore

from bec_widgets.tests.testable_qtimer import TestableQTimer

# To support 'from qtpy.QtCore import QTimer' syntax, QTimer is replaced for the whole session
# see: https://docs.python.org/3/library/unittest.mock.html#where-to-patch
qtpy.QtCore.QTimer = TestableQTimer

# isort: split

from unittest import mock

import numpy as np
import pytest
from bec_lib.messages import _StoredDataInfo
from bec_qthemes import apply_theme
from bec_qthemes._theme import Theme
from ophyd._dummy_shim import _dispatcher
from pytestqt.exceptions import TimeoutError as QtBotTimeoutError
from qtpy.QtWidgets import QApplication, QMessageBox

from bec_widgets.tests.client_mocks import dap_plugin_message, mocked_client, mocked_client_with_dap
from bec_widgets.tests.utils import create_history_file, mock_client, process_all_deferred_deletes
from bec_widgets.utils import bec_dispatcher as bec_dispatcher_module
from bec_widgets.utils import error_popups
from bec_widgets.utils.rpc_register import RPCRegister

__all__ = [
    "pytest_runtest_makereport",
    "_capture_test_name_in_qtimer",
    "_register_worker_thread_dummies",
    "testable_qtimer_class",
    "qapplication",
    "rpc_register",
    "bec_dispatcher",
    "clean_singleton",
    "suppress_message_box",
    "mocked_client",
    "mocked_client_with_dap",
    "dap_plugin_message",
    "grid_scan_history_msg",
    "scan_history_factory",
]


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    item.stash["failed"] = rep.failed


@pytest.fixture(autouse=True)
def _capture_test_name_in_qtimer(request):
    TestableQTimer._current_test_name = request.node.name
    yield
    TestableQTimer._current_test_name = ""


@pytest.fixture
def testable_qtimer_class():
    return TestableQTimer


@pytest.fixture(autouse=True)
def qapplication(qtbot, request, testable_qtimer_class):
    qapp = QApplication.instance()
    process_all_deferred_deletes(qapp)

    if (
        not hasattr(qapp, "theme")
        or not isinstance(qapp.theme, Theme)
        or qapp.theme.theme != "light"
    ):
        apply_theme("light")
        qapp.processEvents()

    yield

    # if the test failed, we don't want to check for open widgets as
    # it simply pollutes the output
    # stop pyepics dispatcher for leaking tests

    _dispatcher.stop()
    from bec_widgets.widgets.editors.bec_console.bec_console import _bec_console_registry

    _bec_console_registry.clear()
    process_all_deferred_deletes(qapp)
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
def bec_dispatcher(threads_check):
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
        "status": "closed",
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
            "status": "closed",
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


@pytest.fixture(scope="session", autouse=True)
def _register_worker_thread_dummies():
    """Qt thread-pool threads register a permanent ``threading._DummyThread`` the first
    time Python inspects them (e.g. a loguru call inside a background Worker). Saturate
    the global pool once up front - with thread expiry disabled so the threads persist -
    so bec_lib's threads_check fixture never sees these registrations appear mid-test."""
    import threading

    from qtpy.QtCore import QRunnable, QThreadPool

    pool = QThreadPool.globalInstance()
    pool.setExpiryTimeout(-1)
    barrier = threading.Barrier(pool.maxThreadCount() + 1, timeout=10)

    class _Warmup(QRunnable):
        def run(self):
            threading.current_thread()
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                pass

    for _ in range(pool.maxThreadCount()):
        pool.start(_Warmup())
    try:
        barrier.wait()
    except threading.BrokenBarrierError:
        pass
