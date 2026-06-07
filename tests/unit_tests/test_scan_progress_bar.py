from unittest import mock

import numpy as np
import pytest
from bec_lib.endpoints import MessageEndpoints

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.progress.bec_progressbar.bec_progressbar import (
    BECProgressBar,
    ProgressState,
)
from bec_widgets.widgets.progress.progress_backend import ProgressTask
from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar import ScanProgressBar

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


def test_progress_task_elapsed_time_uses_monotonic_clock(monkeypatch):
    times = iter([100.0, 102.5])
    monkeypatch.setattr(
        "bec_widgets.widgets.progress.progress_backend.time.monotonic", lambda: next(times)
    )
    task = ProgressTask(parent=None)
    task.timer.stop()

    task.update_elapsed_time()

    assert task._elapsed_time == 2.5
    assert task.time_elapsed == "00:00:02"


def test_scan_progressbar_initialization(scan_progressbar):
    assert isinstance(scan_progressbar, ScanProgressBar)
    assert isinstance(scan_progressbar.progressbar, BECProgressBar)


def test_scan_progressbar_passes_dynamic_stylesheet_setting(qtbot, mocked_client):
    widget = ScanProgressBar(client=mocked_client, enable_dynamic_stylesheet=False)
    qtbot.addWidget(widget)

    assert widget.progressbar.enable_dynamic_stylesheet is False


def test_scan_progressbar_starts_from_scan_progress_before_queue_update(scan_progressbar):
    scan_progressbar.progress_tracker.clear_task(emit_finished=False)

    scan_progressbar.progress_tracker.process_progress_message(
        {"value": 3, "max_value": 10, "done": False}, metadata={"RID": "live-rid"}
    )

    assert scan_progressbar.progress_tracker.task is not None
    assert scan_progressbar.progress_tracker._active_scan_id == "live-rid"
    assert scan_progressbar.progressbar._user_value == 3
    assert scan_progressbar.progressbar._user_maximum == 10


def test_update_labels_content(scan_progressbar):
    """update_labels() reflects ProgressTask time strings on the UI."""
    # fabricate a task with known timings
    task = ProgressTask(parent=scan_progressbar, value=30, max_value=100, done=False)
    task.timer.stop()
    task._elapsed_time = 50
    scan_progressbar.progress_tracker.task = task

    scan_progressbar.update_labels()

    assert scan_progressbar.ui.elapsed_time_label.text() == "00:00:50"
    assert scan_progressbar.ui.remaining_time_label.text() == "00:01:57"


def test_progress_update(qtbot, scan_progressbar):
    """
    Scan progress updates should update the embedded BECProgressBar
    and keep ProgressTask in sync.
    """
    task = ProgressTask(parent=scan_progressbar, value=0, max_value=100, done=False)
    task.timer.stop()
    scan_progressbar.progress_tracker.task = task

    msg = {"value": 20, "max_value": 100, "done": False}
    scan_progressbar.progress_tracker.process_progress_message(msg, metadata={"status": "open"})

    qtbot.wait(200)
    bar = scan_progressbar.progressbar
    assert bar._user_value == 20
    assert bar._user_maximum == 100
    # state reflects BEC status
    assert bar.state is ProgressState.NORMAL


def test_scan_status_open_resets_progress_before_first_progress_update(scan_progressbar):
    scan_progressbar.progressbar.set_maximum(50)
    scan_progressbar.progressbar.set_value(25)
    scan_progressbar.progressbar.state = ProgressState.INTERRUPTED
    scan_progressbar.ui.elapsed_time_label.setText("00:00:12")
    scan_progressbar.ui.remaining_time_label.setText("00:00:34")

    scan_progressbar.progress_tracker.process_scan_status_message(
        {"scan_id": "scan-1", "scan_number": 7, "status": "open"}, {"RID": "rid-1"}
    )

    assert scan_progressbar.progressbar._user_value == 0
    assert scan_progressbar.progressbar._user_maximum == 100
    assert scan_progressbar.progressbar.state is ProgressState.NORMAL
    assert scan_progressbar.ui.elapsed_time_label.text() == "00:00:00"
    assert scan_progressbar.ui.remaining_time_label.text() == "00:00:00"
    assert scan_progressbar.ui.source_label.text() == "Scan 7"


def test_scan_status_open_reset_ignores_same_scan(scan_progressbar):
    scan_progressbar.progress_tracker.process_scan_status_message(
        {"scan_id": "scan-1", "status": "open"}, {}
    )
    scan_progressbar.progressbar.set_value(20)

    scan_progressbar.progress_tracker.process_scan_status_message(
        {"scan_id": "scan-1", "status": "open"}, {}
    )

    assert scan_progressbar.progressbar._user_value == 20


def test_scan_status_non_open_does_not_reset_progress(scan_progressbar):
    scan_progressbar.progressbar.set_value(25)

    scan_progressbar.progress_tracker.process_scan_status_message(
        {"scan_id": "scan-1", "status": "closed"}, {}
    )

    assert scan_progressbar.progressbar._user_value == 25


@pytest.mark.parametrize(
    "status, value, max_val, expected_state",
    [
        ("open", 10, 100, ProgressState.NORMAL),
        ("paused", 25, 100, ProgressState.PAUSED),
        ("aborted", 30, 100, ProgressState.WARNING),
        ("halted", 40, 100, ProgressState.INTERRUPTED),
        ("closed", 100, 100, ProgressState.COMPLETED),
        ("user_completed", 40, 100, ProgressState.COMPLETED),
        ("UNKNOWN", 10, 100, ProgressState.NORMAL),
    ],
)
def test_state_mapping_during_updates(
    qtbot, scan_progressbar, status, value, max_val, expected_state
):
    """ScanProgressBar should translate BEC status → ProgressState consistently."""
    task = ProgressTask(parent=scan_progressbar, value=0, max_value=max_val, done=False)
    task.timer.stop()
    scan_progressbar.progress_tracker.task = task

    scan_progressbar.progress_tracker.process_progress_message(
        {"value": value, "max_value": max_val, "done": status == "closed"},
        metadata={"status": status},
    )

    assert scan_progressbar.progressbar.state is expected_state


def test_aborted_done_scan_keeps_partial_progress(scan_progressbar):
    scan_progressbar.progress_tracker.process_progress_message(
        {"value": 4, "max_value": 10, "done": True},
        metadata={"scan_id": "scan-1", "RID": "rid-1", "status": "aborted"},
    )

    assert scan_progressbar.progressbar._user_value == 4
    assert scan_progressbar.progressbar._user_maximum == 10
    assert scan_progressbar.progressbar.state is ProgressState.WARNING
    assert scan_progressbar.progress_tracker.task is None


def test_source_label_updates(scan_progressbar):
    """update_source_label() renders the current scan label."""
    scan_progressbar.progress_tracker.scan_number = 5
    scan_progressbar.update_source_label()
    assert scan_progressbar.ui.source_label.text() == "Scan 5"


def test_source_label_update_logs_only_on_text_change(scan_progressbar):
    scan_progressbar.progress_tracker.scan_number = 5

    with mock.patch(
        "bec_widgets.widgets.progress.scan_progressbar.scan_progressbar.logger.info"
    ) as mock_info:
        scan_progressbar.update_source_label()
        scan_progressbar.update_source_label()
        scan_progressbar.update_source_label()

    mock_info.assert_called_once_with("Set progress source to Scan 5")


def test_cleanup_disconnects_active_scan_subscription(scan_progressbar, monkeypatch):

    disconnect_calls = []

    monkeypatch.setattr(scan_progressbar.bec_dispatcher, "connect_slot", lambda *args: None)
    monkeypatch.setattr(
        scan_progressbar.bec_dispatcher,
        "disconnect_slot",
        lambda slot, endpoint: disconnect_calls.append(endpoint),
    )
    monkeypatch.setattr(scan_progressbar.progressbar, "close", lambda: None)
    monkeypatch.setattr(scan_progressbar.progressbar, "deleteLater", lambda: None)
    monkeypatch.setattr(BECWidget, "cleanup", lambda self: None)

    with (
        mock.patch.object(scan_progressbar, "close", wraps=scan_progressbar.close) as close_mock,
        mock.patch.object(
            scan_progressbar, "deleteLater", wraps=scan_progressbar.deleteLater
        ) as delete_later_mock,
    ):
        ScanProgressBar.cleanup(scan_progressbar)

    assert disconnect_calls == [MessageEndpoints.scan_progress(), MessageEndpoints.scan_status()]
    assert scan_progressbar.progress_tracker._connected is False
    close_mock.assert_not_called()
    delete_later_mock.assert_not_called()


def test_cleanup_stops_active_task(scan_progressbar, monkeypatch):
    monkeypatch.setattr(BECWidget, "cleanup", lambda self: None)
    scan_progressbar.progress_tracker.task = ProgressTask(parent=scan_progressbar)
    scan_progressbar.progress_tracker._active_scan_id = "scan-1"
    timer = scan_progressbar.progress_tracker.task.timer

    ScanProgressBar.cleanup(scan_progressbar)

    assert not timer.isActive()
    assert scan_progressbar.progress_tracker.task is None
    assert scan_progressbar.progress_tracker._active_scan_id is None
