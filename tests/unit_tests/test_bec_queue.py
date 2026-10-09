import uuid
from unittest import mock

import pytest
from bec_lib import messages
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtQuickWidgets import QQuickWidget

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.services.bec_queue.bec_queue import BECQueue
from bec_widgets.widgets.services.bec_queue.queue_model import (
    ProgressState,
    QueueListModel,
    QueueRow,
    build_rows,
    describe_parameters,
)


def _block(scan_type="line_scan", scan_number=None, user_metadata=None, args=None, kwargs=None):
    rid = str(uuid.uuid4())
    return {
        "msg": messages.ScanQueueMessage(
            scan_type=scan_type,
            parameter={
                "args": args if args is not None else {"samx": [-0.1, 0.1]},
                "kwargs": kwargs if kwargs is not None else {"steps": 20, "exp_time": 0.5},
            },
            queue="primary",
            metadata={"RID": rid, "user_metadata": user_metadata or {}},
        ),
        "RID": rid,
        "readout_priority": {"monitored": ["samx"], "baseline": [], "async": [], "on_request": []},
        "is_scan": True,
        "scan_number": scan_number,
        "scan_id": str(uuid.uuid4()),
    }


def _entry(status, scan_number=None, reason=None, **kwargs):
    block = _block(scan_number=scan_number, **kwargs)
    return messages.QueueInfoEntry(
        queue_id=str(uuid.uuid4()),
        scan_id=[block["scan_id"]],
        is_scan=[True],
        request_blocks=[block],
        scan_number=[scan_number],
        status=status,
        reason=reason,
    )


def _status_msg(entries, status="RUNNING", locks=None):
    return messages.ScanQueueStatusMessage(
        metadata={}, queue={"primary": {"info": entries, "status": status, "locks": locks or []}}
    )


@pytest.fixture
def bec_queue_msg_full():
    entry = _entry("COMPLETED", scan_number=1289, user_metadata={"sample_name": "testA"})
    return _status_msg([entry])


@pytest.fixture
def busy_queue():
    """One running scan and three waiting ones."""
    entries = [_entry("RUNNING", scan_number=1291, user_metadata={"sample_name": "LaB6"})]
    entries += [_entry("PENDING") for _ in range(3)]
    return _status_msg(entries)


@pytest.fixture
def bec_queue(qtbot, mocked_client):
    widget = create_widget(qtbot, BECQueue, client=mocked_client, refresh_upon_start=False)
    qtbot.waitExposed(widget)
    yield widget


def _rows(widget: BECQueue) -> list[QueueRow]:
    return widget.controller.model.rows()


def test_bec_queue_qml_loads(bec_queue):
    assert bec_queue.view.status() == QQuickWidget.Status.Ready
    assert not bec_queue.view.errors()


def test_bec_queue(bec_queue, bec_queue_msg_full):
    bec_queue.update_queue(bec_queue_msg_full.content, {})
    rows = _rows(bec_queue)
    assert len(rows) == 1
    assert rows[0].scan_number == "1289"
    assert rows[0].title == "line_scan"
    assert rows[0].sample == "testA"
    assert rows[0].state_label == "Done"
    assert rows[0].subtitle == "samx −0.1 → 0.1 · 20 steps · 0.5 s"


def test_bec_queue_empty(bec_queue, bec_queue_msg_full):
    bec_queue.update_queue(bec_queue_msg_full.content, {})
    bec_queue.update_queue({}, {})
    assert _rows(bec_queue) == []
    assert bec_queue.controller.state == "idle"


def test_bec_queue_sections_and_busy(qtbot, bec_queue, busy_queue):
    with qtbot.waitSignal(bec_queue.queue_busy) as blocker:
        bec_queue.update_queue(busy_queue.content, {})
    assert blocker.args == [True]
    rows = _rows(bec_queue)
    assert [r.section for r in rows] == ["Now", "Waiting", "Waiting", "Waiting"]
    assert bec_queue.controller.state == "running"
    assert bec_queue.controller.runningCount == 1
    assert bec_queue.controller.waitingCount == 3
    waiting = rows[1:]
    assert [(r.can_move_up, r.can_move_down) for r in waiting] == [
        (False, True),
        (True, True),
        (True, False),
    ]


def test_bec_queue_paused_and_locked_state(bec_queue, busy_queue):
    info = busy_queue.queue["primary"].info
    bec_queue.update_queue(_status_msg(info, status="PAUSED").content, {})
    assert bec_queue.controller.state == "paused"
    lock = messages.ScanQueueLock(reason="Ring current low", identifier="beam")
    bec_queue.update_queue(_status_msg(info, status="LOCKED", locks=[lock]).content, {})
    assert bec_queue.controller.state == "locked"
    assert bec_queue.controller.lockReason == "Ring current low"


def test_remove_marks_only_the_target_row(bec_queue, busy_queue):
    """Regression: removing the third row used to hide the first (running) row."""
    bec_queue.update_queue(busy_queue.content, {})
    target = _rows(bec_queue)[3]
    bec_queue.controller.remove(target.request_id)

    bec_queue.client.queue.request_scan_abortion.assert_called_once_with(
        request_id=target.request_id
    )
    rows = _rows(bec_queue)
    assert len(rows) == 4, "rows only disappear once the server confirms"
    assert [r.removing for r in rows] == [False, False, False, True]

    # the server answers with the item gone
    bec_queue.update_queue(_status_msg(busy_queue.queue["primary"].info[:3]).content, {})
    rows = _rows(bec_queue)
    assert len(rows) == 3
    assert not any(r.removing for r in rows)


def test_abort_current(bec_queue, busy_queue):
    bec_queue.update_queue(busy_queue.content, {})
    running = _rows(bec_queue)[0]
    bec_queue.controller.abortCurrent()
    bec_queue.client.queue.request_scan_abortion.assert_called_once_with(
        request_id=running.request_id
    )


def test_move_requests(bec_queue, busy_queue):
    bec_queue.update_queue(busy_queue.content, {})
    row = _rows(bec_queue)[2]
    bec_queue.controller.moveUp(row.scan_id)
    bec_queue.controller.moveDown(row.scan_id)
    calls = bec_queue.client.queue.request_queue_order_modification.call_args_list
    assert calls == [
        mock.call(scan_id=row.scan_id, action="move_up"),
        mock.call(scan_id=row.scan_id, action="move_down"),
    ]


def test_pause_and_resume(bec_queue):
    with mock.patch.object(bec_queue.client.connector, "send") as send:
        bec_queue.controller.pause()
    endpoint, msg = send.call_args.args
    assert endpoint == MessageEndpoints.scan_queue_modification_request()
    assert msg.action == "deferred_pause"
    bec_queue.controller.resume()
    bec_queue.client.queue.request_scan_continuation.assert_called_once()


def test_halt_and_clear(bec_queue):
    bec_queue.controller.halt()
    bec_queue.client.queue.request_scan_halt.assert_called_once()
    bec_queue.controller.clear()
    bec_queue.client.queue.request_queue_reset.assert_called_once()


def test_progress_is_shown_on_running_row(bec_queue, busy_queue):
    bec_queue.update_queue(busy_queue.content, {})
    scan_id = busy_queue.queue["primary"].info[0].scan_id[0]
    bec_queue.on_scan_progress({"value": 10, "max_value": 40, "done": False}, {"scan_id": scan_id})
    running = _rows(bec_queue)[0]
    assert running.progress == pytest.approx(0.25)
    assert running.progress_text.startswith("10 / 40")
    bec_queue.on_scan_progress({"value": 40, "max_value": 40, "done": True}, {"scan_id": scan_id})
    assert _rows(bec_queue)[0].progress == -1


def test_history_is_shown_as_recent(qtbot, bec_queue, busy_queue):
    finished = _entry("STOPPED", scan_number=1290, reason="user")
    bec_queue.client.connector.lpush(
        MessageEndpoints.scan_queue_history(),
        messages.ScanQueueHistoryMessage(
            status="STOPPED", queue_id=finished.queue_id, info=finished
        ),
    )
    bec_queue.update_queue(busy_queue.content, {})
    # an item leaving the queue triggers a history read
    bec_queue.update_queue(_status_msg(busy_queue.queue["primary"].info[1:]).content, {})
    qtbot.waitUntil(lambda: any(r.section == "Recent" for r in _rows(bec_queue)), timeout=2000)
    recent = [r for r in _rows(bec_queue) if r.section == "Recent"]
    assert recent[0].scan_number == "1290"
    assert recent[0].state_label == "Aborted · by user"
    assert bec_queue.controller.lastFinished == "scan 1290 · aborted · by user"

    bec_queue.controller.showRecent = False
    assert not any(r.section == "Recent" for r in _rows(bec_queue))


def test_hide_toolbar(bec_queue):
    bec_queue.hide_toolbar = True
    assert bec_queue.controller.toolbarVisible is False
    bec_queue.hide_toolbar = False
    assert bec_queue.controller.toolbarVisible is True


def test_describe_parameters_grid():
    msg = messages.ScanQueueMessage(
        scan_type="grid_scan",
        parameter={
            "args": {"samx": [-5, 5, 41], "samy": [-2, 2, 11]},
            "kwargs": {"exp_time": 0.1, "relative": True},
        },
        queue="primary",
        metadata={},
    )
    assert describe_parameters(msg) == "samx −5 → 5 (41) · samy −2 → 2 (11) · 0.1 s · relative"


def test_build_rows_skips_history_still_in_queue():
    entry = _entry("RUNNING", scan_number=5)
    queue = messages.ScanQueueStatus(info=[entry], status="RUNNING")
    history = [
        messages.ScanQueueHistoryMessage(status="RUNNING", queue_id=entry.queue_id, info=entry)
    ]
    rows = build_rows(queue, history, ProgressState())
    assert [r.section for r in rows] == ["Now"]


def test_list_model_moves_rows_instead_of_resetting(qtbot):
    model = QueueListModel()
    rows = [QueueRow(key=k, section="Waiting", queue_id=k) for k in "abc"]
    model.set_rows(rows)
    with qtbot.assertNotEmitted(model.modelReset), qtbot.waitSignal(model.rowsMoved):
        model.set_rows([rows[1], rows[0], rows[2]])
    assert [r.key for r in model.rows()] == ["b", "a", "c"]
    with qtbot.waitSignal(model.rowsRemoved):
        model.set_rows([rows[0]])
    assert [r.key for r in model.rows()] == ["a"]
