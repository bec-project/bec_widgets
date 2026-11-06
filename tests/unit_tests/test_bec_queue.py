import threading
from unittest import mock

import pytest
from bec_lib import messages
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import Qt, QThreadPool

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.progress.scan_progressbar.scan_ui import args_items, args_summary
from bec_widgets.widgets.progress.stage_bar import Tone
from bec_widgets.widgets.services.bec_queue.bec_queue import BECQueue
from bec_widgets.widgets.services.bec_queue.queue_model import QueueMove, ScanQueueModel
from bec_widgets.widgets.services.bec_queue.queue_ui import entry_detail_columns


def make_request(scan_type="line_scan", rid="rid", args=None, kwargs=None, user_metadata=None):
    return messages.ScanQueueMessage(
        scan_type=scan_type,
        parameter={
            "args": args if args is not None else {"samx": [-5, 5]},
            "kwargs": (
                kwargs
                if kwargs is not None
                else {"steps": 50, "exp_time": 0.1, "relative": True, "system_config": {}}
            ),
        },
        queue="primary",
        metadata={
            "RID": rid,
            "user_metadata": user_metadata or {},
            "client_info": {"acl_user": "user"},
        },
    )


def make_info(
    queue_id, status="PENDING", scan_number=None, scan_id=None, rid=None, **request_kwargs
):
    rid = rid or f"rid-{queue_id}"
    scan_id = scan_id or f"scan-{queue_id}"
    request = make_request(rid=rid, **request_kwargs)
    block = messages.RequestBlock(
        msg=request,
        RID=rid,
        readout_priority={"monitored": [], "baseline": [], "on_request": [], "async": []},
        is_scan=True,
        scan_number=scan_number,
        scan_id=scan_id,
    )
    return messages.QueueInfoEntry(
        queue_id=queue_id,
        scan_id=[scan_id],
        is_scan=[True],
        request_blocks=[block],
        scan_number=[scan_number],
        status=status,
    )


def queue_status(infos, status="RUNNING"):
    return messages.ScanQueueStatusMessage(
        queue={"primary": messages.ScanQueueStatus(info=infos, status=status)}, metadata={}
    )


def history_msg(queue_id, status="COMPLETED", **info_kwargs):
    info = make_info(queue_id, status=status, **info_kwargs)
    return messages.ScanQueueHistoryMessage(status=status, queue_id=queue_id, info=info)


@pytest.fixture
def queue_infos():
    return [
        make_info("q-run", status="RUNNING", scan_number=12, user_metadata={"sample": "LiFePO4"}),
        make_info(
            "q-a",
            scan_type="grid_scan",
            args={"samx": [-2, 2, 21], "samy": [-1, 1, 11]},
            user_metadata={"sample": "LiFePO4", "edge": "Fe K"},
        ),
        make_info("q-b", scan_type="time_scan", args={}, kwargs={"points": 100, "interval": 1.0}),
        make_info("q-c", user_metadata={"scan_name": "align_slit", "operator": "jw"}),
    ]


def push_state(client, infos, history=(), status="RUNNING"):
    client.connector.delete(MessageEndpoints.scan_queue_history())
    client.connector.set_and_publish(
        MessageEndpoints.scan_queue_status(), queue_status(infos, status)
    )
    for item in reversed(list(history)):
        client.connector.lpush(MessageEndpoints.scan_queue_history(), item)


def set_queue(widget, infos, status="PAUSED"):
    msg = queue_status(infos, status=status)
    widget.model.on_queue_status(msg.content, msg.metadata)


def wait_for_reads(qtbot, widget):
    """Wait until the queue's background Redis reads have landed."""
    qtbot.waitUntil(lambda: widget.model.loaded and not widget.model._reading)


def create_queue(qtbot, client):
    widget = create_widget(qtbot, BECQueue, client=client)
    wait_for_reads(qtbot, widget)
    return widget


@pytest.fixture
def queue_widget(qtbot, mocked_client, queue_infos):
    push_state(
        mocked_client,
        queue_infos,
        history=[history_msg("h-1", scan_number=11), history_msg("h-2", "STOPPED", scan_number=10)],
    )
    widget = create_queue(qtbot, mocked_client)
    yield widget


def test_model_splits_running_waiting_and_finished(queue_widget):
    model = queue_widget.model
    assert model.running is not None and model.running.queue_id == "q-run"
    assert [e.queue_id for e in model.waiting] == ["q-a", "q-b", "q-c"]
    assert [e.position for e in model.waiting] == [1, 2, 3]
    assert [e.queue_id for e in model.finished] == ["h-1", "h-2"]
    assert model.waiting[2].name == "align_slit"
    assert ("edge", "Fe K") in model.waiting[0].metadata
    # without the scan's signature the third value is not taken for a position
    assert "samx -2 2 21" in model.waiting[0].args
    assert model.finished[1].history_status[0] == "cancel"


def test_rows_follow_queue(queue_widget):
    rows = queue_widget.waiting_rows
    assert rows.order == ["q-a", "q-b", "q-c"]
    assert queue_widget.waiting_badge.text() == "3"


def test_move_sends_move_to_after_the_running_scan(queue_widget):
    queue = queue_widget.client.queue
    with mock.patch.object(queue, "request_queue_order_modification") as order:
        queue_widget.move_scan("q-b", QueueMove.UP)
        order.assert_called_once_with(
            scan_id="scan-q-b", action="move_to", position=1, queue="primary"
        )
        order.reset_mock()
        queue_widget.move_scan("q-b", QueueMove.UP)
        order.assert_not_called()
        queue_widget.move_scan("q-b", QueueMove.BOTTOM)
        order.assert_called_once_with(
            scan_id="scan-q-b", action="move_to", position=3, queue="primary"
        )
    assert queue_widget.waiting_rows.order == ["q-a", "q-c", "q-b"]


def test_move_shows_the_new_order_at_once_until_the_queue_confirms(queue_widget, queue_infos):
    with mock.patch.object(queue_widget.client.queue, "request_queue_order_modification"):
        queue_widget.move_scan("q-c", QueueMove.TOP)
    rows = queue_widget.waiting_rows
    assert rows.order == ["q-c", "q-a", "q-b"]
    assert rows.row("q-c").flashing
    assert [e.position for e in queue_widget.model.waiting] == [1, 2, 3]
    set_queue(queue_widget, queue_infos, status="RUNNING")  # the server has not moved it yet
    assert rows.order == ["q-c", "q-a", "q-b"]
    reordered = [queue_infos[0], queue_infos[3], queue_infos[1], queue_infos[2]]
    set_queue(queue_widget, reordered, status="RUNNING")
    assert queue_widget.model._wanted_order is None
    set_queue(queue_widget, queue_infos, status="RUNNING")  # someone else moved it back
    assert rows.order == ["q-a", "q-b", "q-c"]


def test_remove_aborts_by_request_id_and_collapses_the_row(queue_widget, qtbot):
    queue = queue_widget.client.queue
    with mock.patch.object(queue, "request_scan_abortion") as abort:
        queue_widget.remove_scan("q-b")
    abort.assert_called_once_with(request_id="rid-q-b")
    assert queue_widget.waiting_rows.rows["q-b"].leaving
    assert "q-b" not in [e.key for e in queue_widget.waiting_entries()]
    qtbot.waitUntil(lambda: "q-b" not in queue_widget.waiting_rows.rows, timeout=2000)


def test_rerun_resends_the_request_with_a_new_rid(queue_widget):
    with mock.patch.object(queue_widget.client.connector, "send") as send:
        queue_widget.rerun_scan("h-1")
    msg = send.call_args.args[1]
    assert msg.scan_type == "line_scan"
    assert msg.parameter["args"] == {"samx": [-5, 5]}
    assert msg.metadata["RID"] not in ("rid-h-1", None)
    assert "scan_id" not in msg.metadata
    assert queue_widget.is_requeued("h-1")
    assert (
        queue_widget.waiting_badge._anim.state() == queue_widget.waiting_badge._anim.State.Running
    )


def test_finished_status_is_an_icon_with_tooltip(queue_widget):
    rows = queue_widget.finished_rows
    stopped = rows.rows["h-2"]
    icon = stopped.status_icon if hasattr(stopped, "status_icon") else stopped.lead
    assert icon.icon_name == "cancel"
    assert icon.toolTip().startswith("Stopped")


def test_finished_durations_come_from_scan_status(qtbot, queue_widget):
    model = queue_widget.model
    model.on_scan_status({"scan_id": "scan-h-1", "status": "open", "timestamp": 100.0}, {})
    model.on_scan_status({"scan_id": "scan-h-1", "status": "closed", "timestamp": 165.0}, {})
    model.reload_history()
    wait_for_reads(qtbot, queue_widget)
    assert model.finished[0].duration == 65.0
    assert model.finished[0].exit_status == "closed"


def _sent_modifications(send):
    return [
        call.args[1]
        for call in send.call_args_list
        if call.args[0] == MessageEndpoints.scan_queue_modification_request()
    ]


def test_pause_and_resume(queue_widget, queue_infos):
    queue = queue_widget.client.queue
    with mock.patch.object(queue_widget.client.connector, "send") as send:
        queue_widget.pause_button.click()
    (pause,) = _sent_modifications(send)
    assert (pause.action, pause.request_id) == ("deferred_pause", "rid-q-run")
    msg = queue_status(queue_infos, status="PAUSED")
    queue_widget.model.on_queue_status(msg.content, msg.metadata)
    assert queue_widget.queue_chip.text() == "Paused"
    with mock.patch.object(queue, "request_scan_continuation") as resume:
        queue_widget.pause_button.click()
    resume.assert_called_once()


def test_pause_during_a_motor_move_holds_the_queue_instead_of_aborting(qtbot, mocked_client):
    """A umv has no scan id; bec_lib's request_scan_interruption would abort it."""
    request = messages.ScanQueueMessage(
        scan_type="umv", parameter={"args": {"samx": [10]}, "kwargs": {}}, queue="primary"
    )
    block = messages.RequestBlock(
        msg=request,
        RID="rid-umv",
        readout_priority={"monitored": [], "baseline": [], "on_request": [], "async": []},
        is_scan=False,
        scan_number=None,
        scan_id=None,
    )
    umv = messages.QueueInfoEntry(
        queue_id="q-umv",
        scan_id=[None],
        is_scan=[False],
        request_blocks=[block],
        scan_number=[None],
        status="RUNNING",
    )
    push_state(mocked_client, [umv, make_info("q-next")])
    widget = create_queue(qtbot, mocked_client)
    assert widget.pause_button.isEnabled()
    queue = mocked_client.queue
    with (
        mock.patch.object(mocked_client.connector, "send") as send,
        mock.patch.object(queue, "request_scan_interruption") as interruption,
        mock.patch.object(queue, "request_scan_abortion") as abortion,
    ):
        widget.pause_button.click()
    assert [(m.action, m.request_id) for m in _sent_modifications(send)] == [
        ("deferred_pause", "rid-umv")
    ]
    interruption.assert_not_called()
    abortion.assert_not_called()


def test_pause_disabled_without_running_scan(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos[1:])
    widget = create_queue(qtbot, mocked_client)
    assert widget.model.running is None
    assert not widget.pause_button.isEnabled()
    assert widget.queue_chip.text() == "Ready"


def test_detail_drawer_follows_selection(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=11)])
    widget = create_queue(qtbot, mocked_client)
    assert widget.drawer.hint.isVisibleTo(widget.drawer)
    widget.select("q-b")
    assert widget.drawer.waiting_actions.isVisibleTo(widget.drawer)
    assert "position 2 of 3" in widget.drawer.label.text()
    with mock.patch.object(widget.client.queue, "request_queue_order_modification") as order:
        widget.drawer.top_button.click()
    order.assert_called_once_with(scan_id="scan-q-b", action="move_to", position=1, queue="primary")
    assert "position 1 of 3" in widget.drawer.label.text()
    widget.select("h-1")
    assert widget.drawer.finished_actions.isVisibleTo(widget.drawer)
    with mock.patch.object(widget.client.connector, "send"):
        widget.drawer.rerun_button.click()
    assert widget.drawer.queued_label.isVisibleTo(widget.drawer)
    widget.select("h-1")
    assert widget.selected_key is None


def test_model_ignores_missing_queue(qtbot, mocked_client):
    model = ScanQueueModel(mocked_client, mock.MagicMock())
    model._apply_queue({"queue": {}})
    assert model.running is None and model.waiting == []


def test_refused_move_from_server_shows_its_reason(queue_widget):
    with mock.patch.object(queue_widget.client.queue, "request_queue_order_modification"):
        queue_widget.move_scan("q-c", QueueMove.UP)
    queue_widget.model.on_order_response(
        {"accepted": False, "message": "The running scan cannot be moved."}, {}
    )
    assert queue_widget._flash_next == {}
    assert queue_widget.waiting_hint.text() == "The running scan cannot be moved."
    assert queue_widget.waiting_rows.row("q-c").toolTip() == "The running scan cannot be moved."


def test_detail_rows_have_their_own_actions(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos)
    widget = create_queue(qtbot, mocked_client)
    first, last = widget.waiting_rows.rows["q-a"], widget.waiting_rows.rows["q-c"]
    assert not first.up_button.isEnabled() and first.down_button.isEnabled()
    assert last.up_button.isEnabled() and not last.down_button.isEnabled()
    with mock.patch.object(widget.client.queue, "request_queue_order_modification") as order:
        last.up_button.click()
    order.assert_called_once_with(scan_id="scan-q-c", action="move_to", position=2, queue="primary")
    with mock.patch.object(widget.client.queue, "request_scan_abortion") as abort:
        first.remove_button.click()
    abort.assert_called_once_with(request_id="rid-q-a")
    assert first.leaving


def test_rows_glide_to_their_new_place(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos)
    widget = create_queue(qtbot, mocked_client)
    widget.resize(460, 700)
    widget.show()
    qtbot.waitExposed(widget)
    rows = widget.waiting_rows
    top = rows.rows["q-a"].y()
    with mock.patch.object(widget.client.queue, "request_queue_order_modification"):
        widget.move_scan("q-c", QueueMove.TOP)
    assert "q-c" in rows.gliding
    qtbot.waitUntil(lambda: not rows.gliding, timeout=2000)
    ys = [rows.rows[k].y() for k in ("q-c", "q-a", "q-b")]
    assert ys == sorted(ys) and ys[0] == top


def test_detail_rows_show_metadata_then_arguments_and_keep_them_for_hover(
    qtbot, mocked_client, queue_infos
):
    push_state(mocked_client, queue_infos)
    widget = create_queue(qtbot, mocked_client)
    assert widget.show_details
    for entry in widget.model.waiting:
        row = widget.waiting_rows.rows[entry.key]
        named = entry.name != entry.scan_type  # a scan with its own name shows its type first
        prefix = [entry.scan_type] if named else []
        parts = prefix + [v for _, v in entry.metadata] + ([entry.args] if entry.args else [])
        assert row.meta_label.full_text() == " · ".join(parts)
        assert row.toolTip() == entry.args
        assert row.tail_label.isHidden()
    assert widget.finished_badge.text() == str(len(widget.model.finished))


def test_an_accepted_move_is_not_blamed_for_a_later_rejection(queue_widget):
    model = queue_widget.model
    failed = []
    model.action_failed.connect(lambda *args: failed.append(args))
    with mock.patch.object(queue_widget.client.queue, "request_queue_order_modification"):
        queue_widget.move_scan("q-b", QueueMove.UP)
    order = [e.key for e in model.waiting]
    model.on_order_response({"accepted": True, "message": "ok"}, {})
    # another client's move is refused later: the response is broadcast to everyone
    model.on_order_response({"accepted": False, "message": "not ours"}, {})
    assert failed == []
    assert [e.key for e in model.waiting] == order


def test_a_rejection_is_attributed_to_the_move_it_answers(queue_widget):
    model = queue_widget.model
    failed = []
    model.action_failed.connect(lambda *args: failed.append(args))
    with mock.patch.object(queue_widget.client.queue, "request_queue_order_modification"):
        queue_widget.move_scan("q-b", QueueMove.UP)
        queue_widget.move_scan("q-c", QueueMove.UP)
    model.on_order_response({"accepted": True, "message": "ok"}, {})
    model.on_order_response({"accepted": False, "message": "refused"}, {})
    assert [(args[1], args[2]) for args in failed] == [("q-c", "refused")]


def test_a_move_no_response_came_for_expires(queue_widget):
    model = queue_widget.model
    failed = []
    model.action_failed.connect(lambda *args: failed.append(args))
    with mock.patch.object(queue_widget.client.queue, "request_queue_order_modification"):
        queue_widget.move_scan("q-b", QueueMove.UP)
    model._pending_moves[0] = ("q-b", 0.0)  # its deadline has passed
    model.on_order_response({"accepted": False, "message": "not ours"}, {})
    assert failed == []
    assert not model._pending_moves


@pytest.mark.parametrize(
    "request_name, action",
    [
        ("request_queue_order_modification", lambda widget: widget.move_scan("q-b", QueueMove.UP)),
        ("request_scan_abortion", lambda widget: widget.remove_scan("q-b")),
    ],
)
def test_a_failed_send_does_not_escape_and_keeps_the_shown_order(
    queue_widget, request_name, action
):
    order = [e.key for e in queue_widget.model.waiting]
    with mock.patch.object(
        queue_widget.client.queue, request_name, side_effect=RuntimeError("redis is gone")
    ):
        action(queue_widget)
    assert [e.key for e in queue_widget.model.waiting] == order
    assert not queue_widget.model._pending_moves


def test_a_failed_rerun_does_not_escape(queue_widget):
    entry = queue_widget.model.finished[0]
    with mock.patch.object(
        queue_widget.client.connector, "send", side_effect=RuntimeError("redis is gone")
    ):
        queue_widget.rerun_scan(entry.key)


def test_rows_and_drawer_name_the_values_of_an_argument_bundle(qtbot, mocked_client, queue_infos):
    from types import SimpleNamespace

    arg_input = {"device": "device", "start": "float", "stop": "float", "steps": "int"}
    grid_scan = SimpleNamespace(scan_info={"arg_input": arg_input})
    push_state(mocked_client, queue_infos)
    with mock.patch.object(mocked_client, "scans", SimpleNamespace(grid_scan=grid_scan)):
        widget = create_queue(qtbot, mocked_client)
    entry = widget.model.waiting[0]
    assert entry.args.startswith("samx -2 → 2 steps 21 · samy -1 → 1 steps 11")
    assert ("samx", "-2 → 2 steps 21") in entry_detail_columns(entry)[0]


def test_a_device_rpc_is_shown_as_a_call():
    parameter = {
        "args": [],
        "kwargs": {
            "device": "samx",
            "func": "set",
            "func_args": (5.0,),
            "func_kwargs": {"wait": True},
            "rpc_id": "abc",
            "system_config": {},
        },
    }
    assert args_summary(parameter) == "samx.set(5, wait=True)"
    assert args_items(parameter) == [("call", "samx.set(5, wait=True)")]


def test_show_details_off_hides_the_arguments_in_the_rows_only(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=11)])
    widget = create_queue(qtbot, mocked_client)
    waiting, finished = widget.model.waiting[0], widget.model.finished[0]
    rows = (widget.waiting_rows.rows[waiting.key], widget.finished_rows.rows[finished.key])
    assert waiting.args and finished.args
    assert all(row.meta_label.full_text().endswith(row.toolTip()) for row in rows)

    widget.show_details = False
    assert waiting.args not in rows[0].meta_label.full_text()
    assert rows[0].meta_label.full_text() == " · ".join(v for _, v in waiting.metadata)
    assert finished.args not in rows[1].meta_label.full_text()
    assert [row.toolTip() for row in rows] == [waiting.args, finished.args]

    widget.show_details = True
    assert rows[0].meta_label.full_text().endswith(waiting.args)


def test_a_scan_without_metadata_shows_just_its_arguments(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos)
    widget = create_queue(qtbot, mocked_client)
    entry = next(e for e in widget.model.waiting if e.key == "q-b")
    assert not entry.metadata and entry.args
    assert widget.waiting_rows.rows[entry.key].meta_label.full_text() == entry.args


def test_long_arguments_are_elided_in_the_row(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos)
    widget = create_queue(qtbot, mocked_client)
    entry = widget.model.waiting[0]
    row = widget.waiting_rows.rows[entry.key]
    row.meta_label.resize(60, row.meta_label.height())
    assert row.meta_label.full_text().endswith(entry.args)
    assert row.meta_label.text() != row.meta_label.full_text()  # the shown text is elided
    assert row.toolTip() == entry.args


def test_drawer_shows_arguments_and_metadata_side_by_side(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos)
    widget = create_queue(qtbot, mocked_client)
    widget.resize(520, 700)
    widget.show()
    qtbot.waitExposed(widget)
    drawer = widget.drawer
    entry = next(e for e in widget.model.waiting if e.metadata)
    widget.select(entry.key)
    qtbot.waitUntil(lambda: drawer.width() >= drawer.STACK_BELOW, timeout=1000)
    assert drawer.meta_grid._items == entry.metadata
    assert drawer.args_grid._items and all(
        k not in dict(entry.metadata) for k, _ in drawer.args_grid._items
    )
    assert not drawer.meta_box.isHidden() and not drawer.stacked
    assert drawer.args_box.y() == drawer.meta_box.y()  # top-aligned, side by side

    widget.resize(300, 700)
    qtbot.waitUntil(lambda: drawer.stacked, timeout=1000)
    qtbot.waitUntil(lambda: drawer.meta_box.y() > drawer.args_box.y(), timeout=1000)
    assert drawer.meta_box.x() == drawer.args_box.x()


def test_drawer_without_metadata_has_one_column(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos)
    widget = create_queue(qtbot, mocked_client)
    entry = next(e for e in widget.model.waiting if not e.metadata)
    widget.select(entry.key)
    assert widget.drawer.meta_box.isHidden()
    assert widget.drawer.args_grid._items


def test_icon_buttons_render_at_the_device_pixel_ratio(qtbot):
    from qtpy.QtCore import QSize
    from qtpy.QtGui import QIcon
    from qtpy.QtWidgets import QWidget

    from bec_widgets.widgets.services.bec_queue.queue_ui import IconButton

    host = QWidget()
    qtbot.addWidget(host)
    with mock.patch.object(IconButton, "devicePixelRatioF", return_value=2.0):
        button = IconButton("delete", "Remove", parent=host)
        icon = button.icon()
        assert QSize(36, 36) in icon.availableSizes(QIcon.Mode.Normal)
        normal = icon.pixmap(QSize(18, 18), 2.0, QIcon.Mode.Normal).toImage()
        disabled = icon.pixmap(QSize(18, 18), 2.0, QIcon.Mode.Disabled).toImage()
    assert normal.size() == QSize(36, 36)
    assert normal != disabled


SCREENSHOT_KWARGS = {
    "steps": 10,
    "relative": False,
    "exp_time": 1,
    "frames_per_trigger": 1,
    "settling_time": 0,
    "settling_time_after_trigger": 0,
    "readout_time": 0,
    "burst_at_each_point": 1,
    "system_config": {},
}


def _drawer_for(qtbot, mocked_client, width, kwargs=None, metadata=None):
    infos = [
        make_info("q-run", status="RUNNING", scan_number=1),
        make_info(
            "q-x",
            args={"samx": [0, 1]},
            kwargs=kwargs or SCREENSHOT_KWARGS,
            user_metadata=metadata or {"comment": "stuff", "sample_name": "sample"},
        ),
    ]
    push_state(mocked_client, infos)
    widget = create_queue(qtbot, mocked_client)
    widget.resize(width, 760)
    widget.show()
    qtbot.waitExposed(widget)
    widget.select("q-x")
    qtbot.wait(50)
    return widget.drawer


def _elided(grid):
    return [v.full_text() for v in grid._values if v.text() != v.full_text()]


def test_drawer_columns_sized_by_content(qtbot, mocked_client):
    drawer = _drawer_for(qtbot, mocked_client, 444)  # 420 px of drawer content
    assert not drawer.stacked
    qtbot.waitUntil(lambda: not _elided(drawer.args_grid), timeout=1000)
    assert not _elided(drawer.meta_grid)
    args, meta = drawer.args_box.geometry(), drawer.meta_box.geometry()
    assert args.right() < meta.left()  # side by side, no overlap
    # metadata follows the arguments at their natural width plus the gap, packed to the left
    assert args.width() == drawer.args_grid.natural_width()
    meta_text_left = meta.left() + drawer.meta_box.layout().contentsMargins().left()
    assert meta_text_left - args.left() == args.width() + drawer.COLUMN_GAP


def test_drawer_splitter_can_be_dragged_and_keeps_its_place(qtbot, mocked_client):
    drawer = _drawer_for(qtbot, mocked_client, 600)
    before = drawer.args_box.width()
    drawer.splitter.moveSplitter(before + 40, 1)
    qtbot.waitUntil(lambda: drawer.args_box.width() == before + 40, timeout=1000)
    drawer.resize(drawer.width() + 20, drawer.height())
    qtbot.wait(50)
    assert drawer.args_box.width() == before + 40  # the dragged place is kept


def test_drawer_columns_share_half_when_both_overflow(qtbot, mocked_client):
    long_kwargs = {f"long_parameter_name_{i}": "x" * 120 for i in range(3)}
    long_meta = {f"long_metadata_key_{i}": "y" * 120 for i in range(3)}
    drawer = _drawer_for(qtbot, mocked_client, 1200, kwargs=long_kwargs, metadata=long_meta)
    stacked, args_w, meta_w = drawer.column_widths(700)
    assert not stacked and abs(args_w - meta_w) <= 1


def test_drawer_columns_stack_when_narrow(qtbot, mocked_client):
    drawer = _drawer_for(qtbot, mocked_client, 320)
    qtbot.waitUntil(lambda: drawer.stacked, timeout=1000)


def test_finished_rows_have_an_inline_rerun_button(qtbot, mocked_client, queue_infos):
    push_state(
        mocked_client,
        queue_infos,
        history=[history_msg("h-1", scan_number=10), history_msg("h-2", status="STOPPED")],
    )
    widget = create_queue(qtbot, mocked_client)
    rows = widget.finished_rows.rows
    assert all(not row.rerun_button.isHidden() for row in rows.values())
    row = rows["h-1"]
    assert row.rerun_button.isEnabled()
    with mock.patch.object(widget.client.connector, "send") as send:
        row.rerun_button.click()
    send.assert_called_once()
    assert widget.selected_key is None  # the click did not select the row
    assert row.tail_label.text() == "Queued ✓"
    assert row.rerun_button.isHidden()


def test_inline_rerun_is_disabled_without_the_request(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=10)])
    widget = create_queue(qtbot, mocked_client)
    entry = widget.model.finished[0]
    entry.request = None
    row = widget.finished_rows.rows[entry.key]
    row.set_entry(entry, selected=False)
    assert not row.rerun_button.isEnabled()
    assert "Cannot run again" in row.rerun_button.toolTip()


def test_drawer_close_button_toggle_and_escape(qtbot, mocked_client, queue_infos):
    from qtpy.QtCore import Qt

    push_state(mocked_client, queue_infos)
    widget = create_queue(qtbot, mocked_client)
    drawer = widget.drawer
    assert drawer.close_button.isHidden()
    widget.select("q-b")
    assert not drawer.close_button.isHidden()
    assert widget.waiting_rows.rows["q-b"].selected
    drawer.close_button.click()
    assert widget.selected_key is None
    assert drawer.details.isHidden() and drawer.close_button.isHidden()
    assert not widget.waiting_rows.rows["q-b"].selected

    widget.select("q-b")
    widget.select("q-b")  # clicking the selected row again closes it
    assert widget.selected_key is None

    widget.select("q-b")
    qtbot.keyClick(widget, Qt.Key.Key_Escape)
    assert widget.selected_key is None


def test_drawer_keys_are_not_cut_when_there_is_room(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=11)])
    widget = create_queue(qtbot, mocked_client)
    widget.resize(460, 680)
    widget.show()
    qtbot.waitExposed(widget)
    widget.select("h-1")
    qtbot.wait(50)
    keys = widget.drawer.args_grid._keys
    assert keys and all(k.text() == k.full_text() for k in keys)


def test_finished_times_show_start_and_duration():
    from datetime import date, datetime

    from bec_widgets.widgets.services.bec_queue.queue_model import QueueEntry
    from bec_widgets.widgets.services.bec_queue.queue_ui import finished_times

    start = datetime(2026, 10, 30, 14, 2, 31).timestamp()
    entry = QueueEntry(queue_id="q", status="COMPLETED", scan_type="line_scan", name="line_scan")
    entry.started_at, entry.finished_at = start, start + 11
    assert finished_times(entry, today=date(2026, 10, 30)) == "14:02:31 (0:11)"
    assert finished_times(entry, today=date(2026, 10, 31)) == "Oct 30 14:02 (0:11)"
    entry.started_at = None
    assert finished_times(entry, today=date(2026, 10, 30)) == ""
    entry.started_at, entry.finished_at = None, None
    assert finished_times(entry) == ""


def test_history_times_come_from_the_scan_history(qtbot, mocked_client, queue_infos):
    from bec_lib import messages as bec_messages

    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=11)])
    hist = mock.MagicMock(spec=bec_messages.ScanHistoryMessage)
    hist.scan_id, hist.start_time, hist.end_time = "scan-h-1", 1000.0, 1011.0
    with mock.patch.object(mocked_client.connector, "get_last", return_value=[hist]):
        widget = create_queue(qtbot, mocked_client)
    entry = widget.model.finished[0]
    assert (entry.started_at, entry.finished_at) == (1000.0, 1011.0)
    assert widget.finished_rows.rows[entry.key].tail_label.text().endswith("(0:11)")


def test_scan_history_is_read_only_for_scans_not_seen_yet(qtbot, mocked_client, queue_infos):
    from bec_lib import messages as bec_messages

    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=11)])
    hist = mock.MagicMock(spec=bec_messages.ScanHistoryMessage)
    hist.scan_id, hist.start_time, hist.end_time = "scan-h-1", 1000.0, 1011.0
    with mock.patch.object(mocked_client.connector, "get_last", return_value=[hist]) as get_last:
        widget = create_queue(qtbot, mocked_client)
        model = widget.model
        model.HISTORY_RETRIES = 2
        model._history_retry.setInterval(60_000)  # the retries are triggered by hand here
        assert get_last.call_count == 1

        model.reload_history()
        wait_for_reads(qtbot, widget)
        assert get_last.call_count == 1  # h-1 was found, it is not looked up again
        assert model.finished[0].started_at == 1000.0

        mocked_client.connector.lpush(
            MessageEndpoints.scan_queue_history(), history_msg("h-2", scan_number=12)
        )
        model.reload_history()
        wait_for_reads(qtbot, widget)
        assert get_last.call_count == 2
        assert model._history_retry.isActive()  # h-2 is not in the scan history yet
        model.reload_history()
        wait_for_reads(qtbot, widget)
        assert get_last.call_count == 3
        # after HISTORY_RETRIES misses (e.g. a scan that never started) it is not looked up again
        model.reload_history()
        wait_for_reads(qtbot, widget)
        assert get_last.call_count == 3


def test_a_scan_history_entry_published_late_is_still_found(qtbot, mocked_client, queue_infos):
    from bec_lib import messages as bec_messages

    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=11)])
    hist = mock.MagicMock(spec=bec_messages.ScanHistoryMessage)
    hist.scan_id, hist.start_time, hist.end_time = "scan-h-1", 1000.0, 1011.0
    published: list = []  # the file writer publishes the entry after the queue moved the scan
    with mock.patch.object(
        mocked_client.connector, "get_last", side_effect=lambda *a, **k: published
    ):
        widget = create_queue(qtbot, mocked_client)
        widget.model._history_retry.setInterval(20)
        assert widget.model.finished[0].started_at is None
        published.append(hist)
        qtbot.waitUntil(lambda: widget.model.finished[0].started_at == 1000.0, timeout=2000)
    assert widget.model.finished[0].finished_at == 1011.0
    assert not widget.model._history_retry.isActive()


def _blocking_lrange(client):
    """Patch value for connector.lrange that waits until released."""
    started, release = threading.Event(), threading.Event()
    original = client.connector.lrange

    def lrange(*args, **kwargs):
        started.set()
        release.wait(5)
        return original(*args, **kwargs)

    return lrange, started, release


def test_queue_reads_run_off_the_gui_thread(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=11)])
    threads = []
    connector = mocked_client.connector

    def record(original):
        def wrapper(endpoint, *args, **kwargs):
            if "queue" in endpoint.endpoint or endpoint == MessageEndpoints.scan_history():
                threads.append(threading.get_ident())
            return original(endpoint, *args, **kwargs)

        return wrapper

    with (
        mock.patch.object(connector, "get", side_effect=record(connector.get)),
        mock.patch.object(connector, "lrange", side_effect=record(connector.lrange)),
        mock.patch.object(connector, "get_last", side_effect=record(lambda *a, **k: [])),
    ):
        widget = create_queue(qtbot, mocked_client)
        set_queue(widget, queue_infos[1:], status="RUNNING")  # the running scan leaves
        wait_for_reads(qtbot, widget)
    assert len(threads) >= 4  # queue status, history, scan history, history again
    assert threading.main_thread().ident not in threads
    assert [e.queue_id for e in widget.model.finished] == ["h-1"]


def test_a_stale_read_is_ignored(qtbot, queue_widget):
    model = queue_widget.model
    finished = list(model.finished)
    stale = {"queue": queue_status([]).content, "history": [], "times": {}}
    model._on_read_done(model._read_generation - 1, stale)
    assert model.finished == finished
    assert model.running is not None and model.running.queue_id == "q-run"


def test_a_read_older_than_a_live_queue_update_keeps_the_live_queue(
    qtbot, mocked_client, queue_infos
):
    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=11)])
    lrange, started, release = _blocking_lrange(mocked_client)
    with mock.patch.object(mocked_client.connector, "lrange", side_effect=lrange):
        widget = create_widget(qtbot, BECQueue, client=mocked_client)
        assert started.wait(5)
        set_queue(widget, queue_infos[2:], status="RUNNING")  # newer than the read in flight
        release.set()
        wait_for_reads(qtbot, widget)
    assert [e.queue_id for e in widget.model.waiting] == ["q-b", "q-c"]
    assert [e.queue_id for e in widget.model.finished] == ["h-1"]


def test_loading_shows_no_empty_state(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=11)])
    lrange, started, release = _blocking_lrange(mocked_client)
    with mock.patch.object(mocked_client.connector, "lrange", side_effect=lrange):
        widget = create_widget(qtbot, BECQueue, client=mocked_client)
        assert started.wait(5)
        assert not widget.waiting_empty.isVisibleTo(widget)
        assert widget.queue_chip.text() == "Loading"
        release.set()
        wait_for_reads(qtbot, widget)
    assert widget.queue_chip.text() == "Running"
    assert not widget.waiting_empty.isVisibleTo(widget)


def test_closing_while_a_read_is_in_flight_is_safe(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=11)])
    lrange, started, release = _blocking_lrange(mocked_client)
    with mock.patch.object(mocked_client.connector, "lrange", side_effect=lrange):
        widget = create_widget(qtbot, BECQueue, client=mocked_client)
        assert started.wait(5)
        widget.close()  # cleanup while the read is still running
        release.set()
        qtbot.waitUntil(lambda: QThreadPool.globalInstance().activeThreadCount() == 0, timeout=5000)
    qtbot.wait(50)  # the queued result is delivered and dropped
    assert widget.model.finished == [] and not widget.model.loaded


def test_reloads_during_a_read_are_folded_into_one(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=11)])
    widget = create_queue(qtbot, mocked_client)
    lrange, started, release = _blocking_lrange(mocked_client)
    with mock.patch.object(mocked_client.connector, "lrange", side_effect=lrange) as patched:
        widget.model.reload_history()
        assert started.wait(5)
        mocked_client.connector.lpush(
            MessageEndpoints.scan_queue_history(), history_msg("h-2", scan_number=12)
        )
        for _ in range(5):
            widget.model.reload_history()
        release.set()
        wait_for_reads(qtbot, widget)
    assert patched.call_count == 2
    assert [e.queue_id for e in widget.model.finished] == ["h-2", "h-1"]


def test_no_toasts_anywhere(queue_widget):
    from qtpy.QtWidgets import QFrame

    from bec_widgets.widgets.services.bec_queue import queue_ui

    assert not hasattr(queue_ui, "Toast")
    assert not hasattr(queue_widget, "toast")
    assert not [w for w in queue_widget.findChildren(QFrame) if w.objectName() == "queue_toast"]


def test_refusal_note_clears_after_a_while(queue_widget, qtbot, monkeypatch):
    queue_widget._failure_timer.setInterval(100)
    with mock.patch.object(queue_widget.client.queue, "request_queue_order_modification"):
        queue_widget.move_scan("q-c", QueueMove.UP)
    queue_widget.model.on_order_response({"accepted": False, "message": "Refused."}, {})
    assert queue_widget.waiting_hint.text() == "Refused."
    qtbot.waitUntil(lambda: queue_widget.waiting_hint.text() != "Refused.", timeout=2000)


def test_pause_button_states(queue_widget, queue_infos):
    button = queue_widget.pause_button
    assert button.text() == "Pause queue" and button.isEnabled()
    assert queue_widget.pause_icon_name == "pause"
    with mock.patch.object(queue_widget.client.connector, "send") as send:
        button.click()
    assert [m.action for m in _sent_modifications(send)] == ["deferred_pause"]
    assert button.text() == "Pausing…" and not button.isEnabled()

    paused = queue_status(queue_infos, status="PAUSED")
    queue_widget.model.on_queue_status(paused.content, paused.metadata)
    assert button.text() == "Resume queue" and button.isEnabled()
    assert queue_widget.pause_icon_name == "play_arrow"
    assert queue_widget.queue_chip.text() == "Paused"
    with mock.patch.object(button, "setStyleSheet") as restyle:
        queue_widget._render_header()
        queue_widget._render_header()
    restyle.assert_not_called()  # no style churn while the state is unchanged
    with mock.patch.object(queue_widget.client.queue, "request_scan_continuation") as resume:
        button.click()
    resume.assert_called_once()


def test_pause_button_idle_and_pending_timeout(qtbot, mocked_client, queue_infos):
    push_state(mocked_client, queue_infos[1:])
    widget = create_queue(qtbot, mocked_client)
    assert widget.pause_button.text() == "Pause queue"
    assert not widget.pause_button.isEnabled()
    widget._pause_requested_at = 0.0  # a pause that never landed falls back
    widget._render_header()
    assert widget.pause_button.text() == "Pause queue"


def test_queue_style_sheets_have_no_unknown_properties(qtbot, mocked_client, queue_infos):
    from qtpy.QtCore import qInstallMessageHandler

    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=11)])
    logged = []
    previous = qInstallMessageHandler(lambda _mode, _context, text: logged.append(text))
    try:
        widget = create_queue(qtbot, mocked_client)
        widget.select("q-a")
        widget.resize(420, 600)
        widget.show()
        qtbot.waitExposed(widget)
        widget.grab()
    finally:
        qInstallMessageHandler(previous)
    assert not [m for m in logged if "Unknown property" in m]


def test_rpc_remove_closes_the_widget_and_keeps_the_queue(queue_widget, qtbot):
    """remove() is the BECConnector removal; removing a scan is remove_scan()."""
    queue_widget.model.remove = mock.MagicMock()
    with qtbot.waitSignal(queue_widget.widget_removed, timeout=1000):
        queue_widget.remove()
    queue_widget.model.remove.assert_not_called()


def test_theme_switch_restyles_the_header_and_status_icons_without_a_queue_update(
    queue_widget, qtbot
):
    from bec_widgets.utils.colors import apply_theme
    from bec_widgets.utils.theme_utils import css, theme_colors

    apply_theme("light")
    try:
        status_icon = queue_widget.finished_rows.rows["h-1"].lead
        light_warn = css(theme_colors()["warn"], 0.8)
        light_icon = status_icon.pixmap().toImage().pixelColor(status_icon.pixmap().rect().center())
        assert light_warn in queue_widget.pause_button.styleSheet()

        with mock.patch.object(queue_widget.model, "changed") as changed:
            apply_theme("dark")
            changed.emit.assert_not_called()
        dark_warn = css(theme_colors()["warn"], 0.8)
        assert dark_warn != light_warn
        assert dark_warn in queue_widget.pause_button.styleSheet()
        assert light_warn not in queue_widget.pause_button.styleSheet()
        dark_icon = status_icon.pixmap().toImage().pixelColor(status_icon.pixmap().rect().center())
        assert dark_icon != light_icon
    finally:
        apply_theme("light")


def test_escape_closes_the_drawer_after_a_profile_restored_the_focus_policy(
    qtbot, mocked_client, queue_infos
):
    """A dock area profile restores the queue's own Qt properties, focusPolicy included."""
    from qtpy.QtCore import QSize

    push_state(mocked_client, queue_infos)
    widget = create_queue(qtbot, mocked_client)
    widget.setProperty("minimumSize", QSize(0, 0))
    widget.setProperty("focusPolicy", Qt.FocusPolicy.NoFocus)
    assert widget.minimumSizeHint().width() >= 300
    # a click on a row or on the drawer gives focus to these, and Esc propagates to the queue
    assert widget.content.focusPolicy() == Qt.FocusPolicy.ClickFocus
    assert widget.drawer.focusPolicy() == Qt.FocusPolicy.ClickFocus

    widget.select("q-b")
    qtbot.keyClick(widget.waiting_rows.rows["q-b"], Qt.Key.Key_Escape)
    assert widget.selected_key is None
    widget.select("q-b")
    qtbot.keyClick(widget.drawer.name_label, Qt.Key.Key_Escape)
    assert widget.selected_key is None


@pytest.mark.parametrize("end_status", ["STOPPED", "COMPLETED"])
def test_finished_scan_reaches_the_history_without_waiting_for_the_next_one(
    qtbot, mocked_client, end_status
):
    """The server publishes the end status, then pushes the history entry, then drops the item."""
    push_state(mocked_client, [make_info("q-1", status="RUNNING", scan_number=1)])
    widget = create_queue(qtbot, mocked_client)
    assert widget.model.finished == []

    # 1. the item ends, but it is still in the queue and not in the history yet
    set_queue(widget, [make_info("q-1", status=end_status, scan_number=1)], status="RUNNING")
    # 2. the worker pushes the history entry
    mocked_client.connector.lpush(
        MessageEndpoints.scan_queue_history(), history_msg("q-1", end_status, scan_number=1)
    )
    # 3. the item is removed from the queue
    set_queue(widget, [], status="RUNNING")
    wait_for_reads(qtbot, widget)

    assert [entry.queue_id for entry in widget.model.finished] == ["q-1"]
    assert "q-1" in widget.finished_rows.rows


def test_a_scan_finished_early_has_its_own_icon(qtbot, mocked_client, queue_infos):
    from bec_lib import messages as bec_messages

    push_state(
        mocked_client,
        queue_infos,
        history=[history_msg("h-1", scan_number=11), history_msg("h-2", scan_number=10)],
    )
    early = mock.MagicMock(spec=bec_messages.ScanHistoryMessage)
    early.scan_id, early.start_time, early.end_time = "scan-h-1", 1000.0, 1011.0
    early.exit_status = "user_completed"
    done = mock.MagicMock(spec=bec_messages.ScanHistoryMessage)
    done.scan_id, done.start_time, done.end_time = "scan-h-2", 900.0, 950.0
    done.exit_status = "closed"
    with mock.patch.object(mocked_client.connector, "get_last", return_value=[early, done]):
        widget = create_queue(qtbot, mocked_client)
    finished_early = widget.finished_rows.rows["h-1"].lead
    completed = widget.finished_rows.rows["h-2"].lead
    assert (finished_early.icon_name, finished_early.tone) == ("flag_circle", Tone.ACCENT)
    assert finished_early.toolTip().startswith("Finished early")
    assert (completed.icon_name, completed.tone) == ("check_circle", Tone.OK)
    assert completed.toolTip().startswith("Completed")


def test_every_view_shows_the_scan_by_its_own_name(qtbot, mocked_client, tmp_path):
    from qtpy.QtCore import QSettings

    from bec_widgets.widgets.containers.main_window.addons.scan_status_item import ScanStatusItem
    from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar import ScanProgressBar

    infos = [
        make_info(
            "q-run", status="RUNNING", scan_number=12, user_metadata={"scan_name": "My Scan"}
        ),
        make_info("q-a", user_metadata={"scan_name": "Next Scan"}),
    ]
    push_state(mocked_client, infos)
    queue = create_queue(qtbot, mocked_client)
    bar = create_widget(qtbot, ScanProgressBar, client=mocked_client)
    pill = create_widget(
        qtbot,
        ScanStatusItem,
        client=mocked_client,
        settings=lambda: QSettings(str(tmp_path / "pill.ini"), QSettings.Format.IniFormat),
    )
    pill.set_width_mode("wide")
    status = {
        "scan_id": "scan-q-run",
        "status": "open",
        "scan_number": 12,
        "scan_name": "line_scan",
        "user_metadata": {"scan_name": "My Scan", "sample": "LaB6"},
        "request_inputs": {"arg_bundle": ["samx", -5, 5], "inputs": {}, "kwargs": {}},
    }
    for tracker in (bar.tracker, queue.progress.tracker, pill.tracker):
        tracker.on_scan_status(status, {"RID": "rid-q-run", "scan_id": "scan-q-run"})

    for progress in (bar, queue.progress):
        assert progress.title_label.full_text() == "#12 My Scan"
        # the scan type is still one hover away
        assert progress.header_row.toolTip().startswith("line_scan: samx -5 5")
    assert pill.pill.text.startswith("#12 My Scan")
    row = queue.waiting_rows.rows["q-a"]
    assert row.name_label.text() == "Next Scan"
    assert row.meta_label.full_text().startswith("line_scan")


def _answer_reset(choice):
    """Stand in for the modal dialog: click its button with this text, or press Esc."""
    from qtpy.QtWidgets import QMessageBox

    shown = []

    def exec_(box):
        shown.append((box.windowTitle(), box.text(), box.informativeText(), box.defaultButton()))
        if choice == "escape":
            box.escapeButton().click()
            return 0
        next(b for b in box.buttons() if b.text().replace("&", "") == choice).click()
        return 0

    return mock.patch.object(QMessageBox, "exec", exec_), shown


def test_reset_queue_asks_first_and_resets_on_confirm(queue_widget):
    queue_widget.model.client.queue.request_queue_reset = mock.MagicMock()
    patch, shown = _answer_reset("Reset queue")
    with patch:
        queue_widget.reset_action.trigger()
    queue_widget.model.client.queue.request_queue_reset.assert_called_once_with()
    _title, text, details, default = shown[0]  # macOS message boxes have no window title
    assert text == "Reset the scan queue?"
    assert "stops the running scan #12 line_scan" in details
    assert "removes the 3 waiting scans" in details
    assert details.endswith("This cannot be undone.")
    assert default.text().replace("&", "") == "Cancel"


@pytest.mark.parametrize("choice", ["Cancel", "escape"])
def test_reset_queue_cancel_does_nothing(queue_widget, choice):
    queue_widget.model.client.queue.request_queue_reset = mock.MagicMock()
    patch, _shown = _answer_reset(choice)
    with patch:
        queue_widget.reset_action.trigger()
    queue_widget.model.client.queue.request_queue_reset.assert_not_called()


def test_reset_queue_is_offered_only_when_there_is_something_to_reset(qtbot, mocked_client):
    push_state(mocked_client, [])
    widget = create_queue(qtbot, mocked_client)
    assert not widget.reset_action.isEnabled()
    set_queue(widget, [make_info("q-a")], status="PAUSED")
    assert widget.reset_action.isEnabled()
    assert widget.more_button.menu().actions() == [widget.reset_action]
    assert widget.more_button.focusPolicy() == Qt.FocusPolicy.TabFocus


def test_queue_actions_are_reported_with_their_enum_kind(queue_widget):
    from bec_widgets.widgets.services.bec_queue.queue_model import QueueAction

    model = queue_widget.model
    sent, failed = [], []
    model.action_sent.connect(lambda kind, key, _text: sent.append((kind, key)))
    model.action_failed.connect(lambda kind, key, _text: failed.append((kind, key)))
    with mock.patch.object(queue_widget.client.connector, "send"):
        model.pause()
        model.resume()
    with mock.patch.object(model.client.queue, "request_scan_abortion"):
        model.remove("q-a")
    with mock.patch.object(model.client.queue, "request_queue_order_modification"):
        model.move("q-b", QueueMove.UP)
    model.on_order_response({"accepted": False, "message": "The running scan cannot be moved."}, {})
    assert sent == [
        (QueueAction.PAUSE, ""),
        (QueueAction.RESUME, ""),
        (QueueAction.REMOVE, "q-a"),
        (QueueAction.MOVE, "q-b"),
    ]
    assert failed == [(QueueAction.MOVE, "q-b")]
    # the slots get the enum itself, not a plain str
    assert all(type(kind) is QueueAction for kind, _ in sent + failed)


def test_deleting_while_a_read_is_in_flight_is_safe(qtbot, mocked_client, queue_infos):
    from qtpy.QtWidgets import QApplication

    push_state(mocked_client, queue_infos, history=[history_msg("h-1", scan_number=11)])
    lrange, started, release = _blocking_lrange(mocked_client)
    with mock.patch.object(mocked_client.connector, "lrange", side_effect=lrange):
        widget = BECQueue(client=mocked_client)
        assert started.wait(5)
        model_destroyed = []
        widget.model.destroyed.connect(lambda: model_destroyed.append(True))
        widget.cleanup()
        widget.deleteLater()  # widget and model are gone before the read returns
        qtbot.waitUntil(lambda: bool(model_destroyed), timeout=2000)
        release.set()
        qtbot.waitUntil(lambda: QThreadPool.globalInstance().activeThreadCount() == 0, timeout=5000)
        QApplication.processEvents()  # the late result has no receiver left; nothing raises
