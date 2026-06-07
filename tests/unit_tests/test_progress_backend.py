from unittest import mock

from bec_lib.endpoints import MessageEndpoints

from bec_widgets.widgets.progress.progress_backend import BECProgressTracker


def _dispatcher():
    dispatcher = mock.MagicMock()
    return dispatcher


def test_tracker_subscribes_to_scan_progress_immediately():
    dispatcher = _dispatcher()
    tracker = BECProgressTracker(dispatcher)

    tracker.start()

    assert dispatcher.connect_slot.call_args_list == [
        mock.call(tracker.process_progress_message, MessageEndpoints.scan_progress()),
        mock.call(tracker.process_scan_status_message, MessageEndpoints.scan_status()),
    ]
    tracker.cleanup()


def test_tracker_starts_scan_from_scan_progress_metadata():
    dispatcher = _dispatcher()
    tracker = BECProgressTracker(dispatcher)
    snapshots = []
    tracker.progress_updated.connect(snapshots.append)

    tracker.start()
    tracker.process_progress_message(
        {"value": 3, "max_value": 10},
        {"scan_id": "scan-2", "RID": "rid-2", "scan_number": 2, "status": "open"},
    )

    assert tracker.task is not None
    assert tracker._active_scan_id == "scan-2"
    assert tracker._active_rid == "rid-2"
    assert tracker.scan_number == 2
    assert snapshots[-1].scan_number == 2

    tracker.cleanup()


def test_tracker_switches_sources_idempotently():
    dispatcher = _dispatcher()
    tracker = BECProgressTracker(dispatcher)

    tracker.start()
    tracker.start()
    assert dispatcher.connect_slot.call_count == 2
    assert dispatcher.disconnect_slot.call_count == 0

    tracker.cleanup()


def test_tracker_resets_progress_on_new_open_scan_status():
    dispatcher = _dispatcher()
    tracker = BECProgressTracker(dispatcher)
    snapshots = []
    tracker.progress_updated.connect(snapshots.append)
    tracker.start()

    snapshot = tracker.process_scan_status_message(
        {"scan_id": "scan-1", "scan_number": 7, "status": "open"}, {}
    )

    assert snapshot is not None
    assert snapshot.value == 0
    assert snapshot.max_value == 100
    assert snapshot.status == "open"
    assert snapshot.scan_id == "scan-1"
    assert snapshot.scan_number == 7
    assert snapshot.is_new_scan is True
    assert tracker.task is None
    assert tracker.scan_number == 7
    assert snapshots[-1] == snapshot

    tracker.cleanup()


def test_tracker_ignores_duplicate_open_scan_status():
    dispatcher = _dispatcher()
    tracker = BECProgressTracker(dispatcher)
    snapshots = []
    tracker.progress_updated.connect(snapshots.append)
    tracker.start()

    tracker.process_scan_status_message({"scan_id": "scan-1", "status": "open"}, {})
    tracker.process_scan_status_message({"scan_id": "scan-1", "status": "open"}, {})

    assert len(snapshots) == 1

    tracker.cleanup()


def test_tracker_ignores_open_scan_status_after_progress_for_same_scan():
    dispatcher = _dispatcher()
    tracker = BECProgressTracker(dispatcher)
    snapshots = []
    tracker.progress_updated.connect(snapshots.append)
    tracker.start()

    tracker.process_progress_message(
        {"value": 3, "max_value": 10}, {"scan_id": "scan-1", "RID": "rid-1", "status": "open"}
    )
    snapshot = tracker.process_scan_status_message(
        {"scan_id": "scan-1", "scan_number": 7, "status": "open"}, {}
    )

    assert snapshot is None
    assert len(snapshots) == 1
    assert snapshots[-1].value == 3
    assert tracker.task is not None
    assert tracker.task.value == 3

    tracker.cleanup()


def test_tracker_ignores_open_scan_status_after_done_progress_for_same_scan():
    dispatcher = _dispatcher()
    tracker = BECProgressTracker(dispatcher)
    snapshots = []
    tracker.progress_updated.connect(snapshots.append)
    tracker.start()

    tracker.process_progress_message(
        {"value": 10, "max_value": 10, "done": True},
        {"scan_id": "scan-1", "RID": "rid-1", "status": "closed"},
    )
    snapshot = tracker.process_scan_status_message(
        {"scan_id": "scan-1", "scan_number": 7, "status": "open"}, {}
    )

    assert snapshot is None
    assert len(snapshots) == 1
    assert snapshots[-1].value == 10
    assert tracker.task is None

    tracker.cleanup()


def test_tracker_marks_new_scan_only_when_rid_changes():
    dispatcher = _dispatcher()
    tracker = BECProgressTracker(dispatcher)
    snapshots = []
    tracker.progress_updated.connect(snapshots.append)
    tracker.start()

    tracker.process_progress_message({"value": 10, "max_value": 100}, {"RID": "rid-1"})
    tracker.process_progress_message({"value": 20, "max_value": 200}, {"RID": "rid-1"})
    tracker.process_progress_message({"value": 5, "max_value": 50}, {"RID": "rid-2"})

    assert [snapshot.is_new_scan for snapshot in snapshots] == [True, False, True]
    assert tracker._active_rid == "rid-2"

    tracker.cleanup()


def test_tracker_keeps_partial_value_for_done_scan_progress():
    dispatcher = _dispatcher()
    tracker = BECProgressTracker(dispatcher)
    snapshots = []
    tracker.progress_updated.connect(snapshots.append)
    tracker.start()

    tracker.process_progress_message(
        {"value": 4, "max_value": 10, "done": True},
        {"scan_id": "scan-1", "RID": "rid-1", "status": "aborted"},
    )

    assert snapshots[-1].value == 4
    assert snapshots[-1].max_value == 10
    assert snapshots[-1].done is True
    assert tracker.task is None

    tracker.cleanup()
