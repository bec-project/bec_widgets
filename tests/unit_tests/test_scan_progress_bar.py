import numpy as np
import pytest

from bec_widgets.widgets.progress.bec_progressbar.bec_progressbar import (
    BECProgressBar,
    ProgressState,
)
from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar import (
    ProgressSource,
    ProgressTask,
    ScanProgressBar,
)

from .client_mocks import mocked_client


@pytest.fixture
def scan_progressbar(qtbot, mocked_client):
    widget = ScanProgressBar(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_progress_task_basic():
    """percentage, remaining, and formatted time helpers behave as expected."""
    task = ProgressTask(parent=None, value=50, max_value=100, done=False)
    task.timer.stop()  # we don’t want the timer ticking in tests
    task._elapsed_time = 10  # simulate 10 s elapsed

    # 50 / 100  ⇒ 50 %
    assert task.percentage == 50

    # speed  =  value / elapsed  = 5 steps / s
    assert np.isclose(task.speed, 5)

    # remaining steps = 50 ; time_remaining ≈ 10 s
    assert task.remaining == 50
    assert task.time_remaining == "00:00:10"

    # time_elapsed formatting
    assert task.time_elapsed == "00:00:10"


def test_scan_progressbar_initialization(scan_progressbar):
    assert isinstance(scan_progressbar, ScanProgressBar)
    assert isinstance(scan_progressbar.progressbar, BECProgressBar)


def test_update_labels_content(scan_progressbar):
    """update_labels() reflects ProgressTask time strings on the UI."""
    # fabricate a task with known timings
    task = ProgressTask(parent=scan_progressbar, value=30, max_value=100, done=False)
    task.timer.stop()
    task._elapsed_time = 50
    scan_progressbar.task = task

    scan_progressbar.update_labels()

    assert scan_progressbar.ui.elapsed_time_label.text() == "00:00:50"
    assert scan_progressbar.ui.remaining_time_label.text() == "00:01:57"


def test_on_progress_update(qtbot, scan_progressbar):
    """
    on_progress_update() should forward new values to the embedded
    BECProgressBar and keep ProgressTask in sync.
    """
    task = ProgressTask(parent=scan_progressbar, value=0, max_value=100, done=False)
    task.timer.stop()
    scan_progressbar.task = task

    msg = {"value": 20, "max_value": 100, "done": False}
    scan_progressbar.on_progress_update(msg, metadata={"status": "open"})

    qtbot.wait(200)
    bar = scan_progressbar.progressbar
    assert bar._user_value == 20
    assert bar._user_maximum == 100
    # state reflects BEC status
    assert bar.state is ProgressState.NORMAL


@pytest.mark.parametrize(
    "status, value, max_val, expected_state",
    [
        ("open", 10, 100, ProgressState.NORMAL),
        ("paused", 25, 100, ProgressState.PAUSED),
        ("aborted", 30, 100, ProgressState.INTERRUPTED),
        ("halted", 40, 100, ProgressState.PAUSED),
        ("closed", 100, 100, ProgressState.COMPLETED),
    ],
)
def test_state_mapping_during_updates(
    qtbot, scan_progressbar, status, value, max_val, expected_state
):
    """ScanProgressBar should translate BEC status → ProgressState consistently."""
    task = ProgressTask(parent=scan_progressbar, value=0, max_value=max_val, done=False)
    task.timer.stop()
    scan_progressbar.task = task

    scan_progressbar.on_progress_update(
        {"value": value, "max_value": max_val, "done": status == "closed"},
        metadata={"status": status},
    )

    assert scan_progressbar.progressbar.state is expected_state


def test_source_label_updates(scan_progressbar):
    """update_source_label() renders correct text for both progress sources."""
    # device progress
    scan_progressbar.update_source_label(ProgressSource.DEVICE_PROGRESS, device="motor")
    assert scan_progressbar.ui.source_label.text() == "Device motor"

    # scan progress (needs a scan_number for deterministic text)
    scan_progressbar.scan_number = 5
    scan_progressbar.update_source_label(ProgressSource.SCAN_PROGRESS)
    assert scan_progressbar.ui.source_label.text() == "Scan 5"


def test_set_progress_source_connections(scan_progressbar, monkeypatch):
    """ """
    from bec_lib.endpoints import MessageEndpoints

    connect_calls = []
    disconnect_calls = []

    def fake_connect(slot, endpoint):
        connect_calls.append(endpoint)

    def fake_disconnect(slot, endpoint):
        disconnect_calls.append(endpoint)

    # Patch dispatcher methods
    monkeypatch.setattr(scan_progressbar.bec_dispatcher, "connect_slot", fake_connect)
    monkeypatch.setattr(scan_progressbar.bec_dispatcher, "disconnect_slot", fake_disconnect)

    # switch to SCAN_PROGRESS
    scan_progressbar.scan_number = 7
    scan_progressbar.set_progress_source(ProgressSource.SCAN_PROGRESS)

    assert scan_progressbar._progress_source == ProgressSource.SCAN_PROGRESS
    assert scan_progressbar.ui.source_label.text() == "Scan 7"
    assert connect_calls[-1] == MessageEndpoints.scan_progress()
    assert disconnect_calls == []

    # switch to DEVICE_PROGRESS
    device = "motor"
    scan_progressbar.set_progress_source(ProgressSource.DEVICE_PROGRESS, device=device)

    assert scan_progressbar._progress_source == ProgressSource.DEVICE_PROGRESS
    assert scan_progressbar.ui.source_label.text() == f"Device {device}"
    assert connect_calls[-1] == MessageEndpoints.device_progress(device=device)
    assert disconnect_calls == [MessageEndpoints.scan_progress()]

    # calling again with the SAME source should not add new connect calls
    prev_connect_count = len(connect_calls)
    scan_progressbar.set_progress_source(ProgressSource.DEVICE_PROGRESS, device=device)
    assert len(connect_calls) == prev_connect_count, "No extra connect made for same source"
