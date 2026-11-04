from types import SimpleNamespace
from unittest import mock

import pytest
from qtpy.QtGui import QFontMetricsF

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.progress.scan_progressbar.scan_hook_tracker import (
    ScanRunState,
    describe_instructions,
    format_duration,
)
from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar import (
    ScanProgressBar,
    describe_state,
)
from bec_widgets.widgets.progress.scan_progressbar.scan_ui import (
    args_summary,
    request_inputs_summary,
    scan_bundle_names,
)
from bec_widgets.widgets.progress.stage_bar import BarMode


def status(scan_id="s1", state="open", **kwargs):
    content = {
        "scan_id": scan_id,
        "status": state,
        "scan_number": 12,
        "scan_name": "line_scan",
        "user_metadata": {"sample": "LiFePO4"},
        "request_inputs": {
            "arg_bundle": ["samx", -5, 5],
            "inputs": {},
            "kwargs": {"steps": 50, "exp_time": 0.1},
        },
    }
    content.update(kwargs)
    return content, {"RID": "rid-1", "scan_id": scan_id}


def hook(name, ts, scan_id="s1", hook_status="running", instructions=None, **kwargs):
    content = {
        "scan_id": scan_id,
        "hook": name,
        "status": hook_status,
        "instructions": instructions or [],
        "timestamp": ts,
        "waiting": False,
        "wait_started_at": None,
    }
    content.update(kwargs)
    return content, {"RID": "rid-1", "scan_id": scan_id}


def step(tracker, name, ts, scan_id="s1", **hook_kwargs):
    """A new top-level step as the server reports it, with the time it started."""
    tracker.on_scan_hook(*hook(name, ts, scan_id=scan_id, hook_started_at=ts, **hook_kwargs))


@pytest.fixture
def progress(qtbot, mocked_client):
    widget = create_widget(qtbot, ScanProgressBar, client=mocked_client)
    yield widget


def test_idle_widget(progress):
    assert progress.title_label.full_text() == "No scan yet"
    assert not progress.stop_button.isEnabled()
    assert progress.bar.mode == BarMode.IDLE


def test_busy_steps_then_measurement(progress):
    step(progress.tracker, "prepare_scan", 100.0)
    assert progress.bar.mode == BarMode.BUSY
    assert progress.bar.text.startswith("Preparing")
    assert progress.next_label.full_text().startswith("Next: Opening scan")

    progress.tracker.on_scan_status(*status())
    assert progress.title_label.full_text() == "#12 line_scan"
    assert "samx -5 5" in progress.header_row.toolTip()
    assert "samx -5 5" in progress.chips.toolTip()

    stage = [{"device": ["samx", "eiger"], "action": "stage", "parameter": {}}]
    step(progress.tracker, "stage", 101.0, instructions=stage)
    assert progress.state_chip.text() == "Staging"
    assert progress.instruction_label.full_text() == "Staging samx, eiger"

    step(progress.tracker, "scan_core", 104.0)
    progress.tracker.on_scan_progress(
        {"value": 10, "max_value": 50, "done": False}, {"scan_id": "s1"}
    )
    assert progress.bar.mode == BarMode.PROGRESS
    assert progress.bar.text.startswith("Point 10 of 50 · 20%")
    assert progress.bar.fraction == pytest.approx(0.2)

    timings = {t.hook: t for t in progress.state.step_times()}
    assert timings["prepare_scan"].total == pytest.approx(1.0)
    assert timings["stage"].total == pytest.approx(3.0)


def test_waiting_instruction_shows_wait_time(progress):
    move = [{"device": "samx", "action": "set", "parameter": {"value": -5.0}}]
    step(
        progress.tracker, "pre_scan", 200.0, instructions=move, waiting=True, wait_started_at=197.0
    )
    text = progress.instruction_label.full_text()
    assert text.startswith("Waiting for samx to reach -5")
    assert text.endswith("0:03")


def test_nested_hook_keeps_parent_step(progress):
    step(progress.tracker, "pre_scan", 10.0)
    progress.tracker.on_scan_hook(*hook("before_pre_scan", 10.5))
    state = progress.state
    assert state.top_hook == "pre_scan"
    assert progress.instruction_label.full_text().startswith("[before_pre_scan]")
    assert state.timings["before_pre_scan"].nested
    progress.tracker.on_scan_hook(*hook("before_pre_scan", 11.0, hook_status="completed"))
    progress.tracker.on_scan_hook(*hook("pre_scan", 11.0))
    assert state.timings["before_pre_scan"].total == pytest.approx(0.5)
    assert state.timings["pre_scan"].count == 1
    assert state.timings["pre_scan"].started_at == 10.0


def test_finished_scan(progress):
    step(progress.tracker, "stage", 10.0)
    progress.tracker.on_scan_status(*status(state="aborted"))
    assert progress.state_chip.text() == "Aborted"
    assert progress.bar.mode == BarMode.ERROR
    assert progress.bar.text.startswith("Aborted in Staging")
    assert not progress.stop_button.isEnabled()
    assert not progress.tracker._timer.isActive()


def test_stop_aborts_by_rid_then_offers_emergency_stop(progress, qtbot):
    progress.tracker.on_scan_status(*status())
    stop = progress.stop_button
    queue = stop.queue
    with mock.patch.object(queue, "request_scan_abortion") as abort:
        stop.click()
    abort.assert_called_once_with(request_id="rid-1")
    assert progress.confirm_frame.isHidden()  # no confirmation row by default
    # a stretched bar keeps the Stop width: the short label then says the same
    assert stop.button.text() in (stop.EMERGENCY_STOP_LABEL, stop.EMERGENCY_STOP_SHORT_LABEL)
    with mock.patch.object(queue, "request_scan_halt") as halt:
        stop.click()
    halt.assert_called_once_with(request_id="rid-1")
    stop._reset_timer.setInterval(50)
    stop._reset_timer.start()
    qtbot.waitUntil(lambda: stop.button.text() == "Stop", timeout=2000)


def test_stop_menu_finishes_or_halts(progress):
    progress.tracker.on_scan_status(*status())
    stop = progress.stop_button
    with mock.patch.object(stop.queue, "request_set_completed") as finish:
        stop.finish_action.trigger()
    finish.assert_called_once_with(request_id="rid-1")
    assert stop.button.text() == "Stop"  # finishing is not an abort: no emergency step
    with mock.patch.object(stop.queue, "request_scan_halt") as halt:
        stop.halt_action.trigger()
    halt.assert_called_once_with(request_id="rid-1")


def test_confirm_before_stop_asks_first(progress):
    progress.confirm_before_stop = True
    progress.tracker.on_scan_status(*status())
    with mock.patch.object(progress.stop_button.queue, "request_scan_abortion") as abort:
        progress.stop_button.click()
        abort.assert_not_called()
        assert not progress.confirm_frame.isHidden()
        assert "#12 line_scan" in progress.confirm_label.full_text()
        progress.confirm_stop_button.click()
    abort.assert_called_once_with(request_id="rid-1")
    with mock.patch.object(progress.stop_button.queue, "request_set_completed") as finish:
        progress.stop_button.finish_action.trigger()
        assert progress.confirm_stop_button.text() == "Finish now"
        progress.confirm_cancel_button.click()
    finish.assert_not_called()


def test_step_times_popup_lists_hooks(progress):
    step(progress.tracker, "prepare_scan", 9.0)
    step(progress.tracker, "open_scan", 9.5)
    step(progress.tracker, "stage", 10.0)
    step(progress.tracker, "pre_scan", 12.5)
    progress.step_times.show_popup()
    hooks = [row[0] for row in progress.step_times.popup.rows]
    assert hooks == ["prepare_scan", "open_scan", "stage", "pre_scan"]
    assert progress.step_times.popup.rows[0][1] == "0.5 s"
    assert progress.step_times.popup.rows[2][1] == "2.5 s"
    progress.step_times.popup.hide()


def test_step_times_popup_updates_rows_in_place(progress, qtbot):
    step(progress.tracker, "stage", 10.0)
    popup = progress.step_times.popup
    progress.step_times.show_popup()
    qtbot.waitExposed(popup)
    first = popup._row(0)
    size = popup.size()
    for ts in (11.0, 12.0, 13.0):
        step(progress.tracker, "pre_scan", ts)
        progress.tracker.on_scan_hook(*hook("pre_scan", ts + 0.5, hook_status="completed"))
        step(progress.tracker, "stage", ts + 0.5)
        progress._render()
    assert popup._row(0) is first
    assert [row[0] for row in popup.rows] == ["stage", "pre_scan"]
    assert popup.width() >= size.width()
    popup.hide()


def test_old_scan_messages_are_ignored(progress):
    progress.tracker.on_scan_status(*status(scan_id="s2"))
    progress.tracker.on_scan_status(*status(scan_id="s1", state="closed"))
    assert progress.state.scan_id == "s2"


def test_without_hooks_progress_still_shows():
    state = ScanRunState(scan_id="x", scan_number=3, scan_name="grid_scan")
    assert describe_state(state)["bar_text"].startswith("Running")
    state.apply_progress({"value": 5, "max_value": 10})
    info = describe_state(state)
    assert info["bar_mode"] == BarMode.PROGRESS
    assert info["next"] == ""


@pytest.mark.parametrize(
    "instructions, waiting, expected",
    [
        (
            [{"device": "samx", "action": "set", "parameter": {"value": 1.5}}],
            False,
            "Moving samx to 1.5",
        ),
        (
            [{"device": "eiger", "action": "trigger", "parameter": {}}],
            True,
            "Waiting for eiger (trigger)",
        ),
        (
            [{"device": "dev", "action": "rpc", "parameter": {"func": "reset"}}],
            False,
            "Calling dev.reset()",
        ),
        (
            [{"device": None, "action": "baseline_reading", "parameter": {}}],
            False,
            "Reading baseline",
        ),
        ([{"device": "a", "action": "scan_report_instruction", "parameter": {}}], False, ""),
        (
            [{"device": ["a", "b", "c", "d", "e"], "action": "read", "parameter": {}}],
            False,
            "Reading a, b, c +2",
        ),
    ],
)
def test_describe_instructions(instructions, waiting, expected):
    assert describe_instructions(instructions, waiting) == expected


def test_format_duration():
    assert format_duration(5) == "0:05"
    assert format_duration(3725) == "1:02:05"
    assert format_duration(None) == ""


def test_points_inside_scan_core_do_not_flicker(progress):
    tracker = progress.tracker
    step(tracker, "scan_core", 50.0)
    tracker.on_scan_progress({"value": 3, "max_value": 50, "done": False}, {"scan_id": "s1"})
    started = progress.state.hook_started_local
    texts = set()
    shown = []
    for point in range(5):
        move = [{"device": "samx", "action": "set", "parameter": {"value": point}}]
        tracker.on_scan_hook(*hook("at_each_point", 51.0 + point, instructions=move))
        shown.append(progress.instruction_label.full_text())
        texts.add(
            (progress.bar.mode, progress.state_chip.text(), progress.instruction_label.full_text())
        )
        tracker.on_scan_hook(*hook("at_each_point", 51.5 + point, hook_status="completed"))
        tracker.on_scan_hook(*hook("scan_core", 51.5 + point))
        texts.add(
            (progress.bar.mode, progress.state_chip.text(), progress.instruction_label.full_text())
        )
    # the step and the bar stay put; the instruction line shows every broadcast at once
    assert {(mode, chip) for mode, chip, _ in texts} == {("progress", "Measuring")}
    assert shown == [f"Moving samx to {point}" for point in range(5)]
    assert progress.state.hook_started_local == started
    assert [t.hook for t in progress.state.step_times()] == ["scan_core"]
    assert progress.state.timings["scan_core"].count == 1


def test_long_wait_inside_scan_core_is_shown(progress):
    step(progress.tracker, "scan_core", 50.0)
    trigger = [{"device": "eiger", "action": "trigger", "parameter": {}}]
    progress.tracker.on_scan_hook(
        *hook("at_each_point", 60.0, instructions=trigger, waiting=True, wait_started_at=55.0)
    )
    assert progress.instruction_label.full_text() == "Waiting for eiger (trigger) · 0:05"


def test_scan_core_shows_points_before_the_first_progress(progress):
    progress.tracker.on_scan_status(*status(num_points=50))
    step(progress.tracker, "scan_core", 50.0)
    assert progress.bar.mode == BarMode.PROGRESS
    assert progress.bar.text.startswith("Point 0 of 50 · 0%")


def test_every_step_is_listed_in_order(progress):
    progress.tracker.on_scan_status(*status())
    for index, name in enumerate(("prepare_scan", "open_scan", "stage")):
        step(progress.tracker, name, 9.0 + index * 0.01)
    step(progress.tracker, "pre_scan", 10.0)
    progress.tracker.on_scan_hook(*hook("before_pre_scan", 10.2))
    step(progress.tracker, "scan_core", 11.0)
    step(progress.tracker, "post_scan", 15.0)
    for index, name in enumerate(("unstage", "close_scan")):
        step(progress.tracker, name, 15.5 + index * 0.01)
    progress.tracker.on_scan_status(*status(state="closed"))
    steps = progress.state.step_times()
    assert [t.hook for t in steps] == [
        "prepare_scan",
        "open_scan",
        "stage",
        "pre_scan",
        "before_pre_scan",
        "scan_core",
        "post_scan",
        "unstage",
        "close_scan",
    ]
    assert progress.state.timings["scan_core"].total == pytest.approx(4.0)
    assert progress.state.timings["stage"].total == pytest.approx(0.98)


def test_only_the_reported_steps_are_listed(progress):
    progress.tracker.on_scan_status(*status())
    step(progress.tracker, "scan_core", 11.0)
    step(progress.tracker, "post_scan", 15.0)
    assert [t.hook for t in progress.state.step_times()] == ["scan_core", "post_scan"]


def test_step_completion_and_error_come_from_the_hook(progress):
    progress.tracker.on_scan_status(*status())
    step(progress.tracker, "stage", 10.0)
    progress.tracker.on_scan_hook(*hook("stage", 12.0, hook_status="completed"))
    assert progress.state.timings["stage"].total == pytest.approx(2.0)
    step(progress.tracker, "pre_scan", 12.0)
    progress.tracker.on_scan_hook(*hook("pre_scan", 13.0, hook_status="error"))
    assert progress.state.hook_error == "pre_scan"
    assert progress.state.timings["pre_scan"].status == "error"
    progress.tracker.on_scan_status(*status(state="aborted"))
    info = describe_state(progress.state)
    assert info["bar_mode"] == BarMode.ERROR
    assert info["bar_text"].startswith("Aborted in Pre-scan")


def test_an_interrupted_step_is_not_shown_as_failed(progress):
    progress.tracker.on_scan_status(*status())
    step(progress.tracker, "scan_core", 10.0)
    progress.tracker.on_scan_hook(*hook("scan_core", 14.0, hook_status="interrupted"))
    timing = progress.state.timings["scan_core"]
    assert timing.status == "interrupted" and timing.started_at is None
    assert progress.state.hook_error is None
    progress.tracker.on_scan_status(*status(state="user_completed"))
    info = describe_state(progress.state)
    assert info["outcome"] == "Finished early"  # the outcome comes from the scan status
    assert info["bar_mode"] == BarMode.DONE


def test_an_interrupted_nested_hook_closes_without_an_error(progress):
    progress.tracker.on_scan_status(*status())
    step(progress.tracker, "stage", 10.0)
    progress.tracker.on_scan_hook(*hook("before_stage_modifier", 11.0))
    progress.tracker.on_scan_hook(*hook("before_stage_modifier", 12.0, hook_status="interrupted"))
    timing = progress.state.timings["before_stage_modifier"]
    assert timing.status == "interrupted" and timing.started_at is None
    assert progress.state.hook_error is None


def test_an_abort_closes_open_steps_as_interrupted_not_failed(progress):
    progress.tracker.on_scan_status(*status())
    step(progress.tracker, "stage", 10.0)
    progress.tracker.on_scan_hook(*hook("before_stage_modifier", 11.0))
    progress.tracker.on_scan_status(*status(state="aborted"))
    for name in ("stage", "before_stage_modifier"):
        assert progress.state.timings[name].status == "interrupted"
    assert progress.state.hook_error is None
    info = describe_state(progress.state)
    assert info["outcome"] == "Aborted"
    assert info["bar_text"].startswith("Aborted in Staging")


def queue(*scan_ids, entry_status="RUNNING"):
    """A scan queue status content with one request per scan id, in a running queue."""
    infos = [{"status": entry_status, "scan_id": [scan_id]} for scan_id in scan_ids]
    return {"queue": {"primary": {"info": infos, "status": "RUNNING"}}}, {}


def test_a_scan_that_left_the_queue_without_a_final_status_ends_as_aborted(progress, qtbot):
    tracker = progress.tracker
    tracker._lost_check.setInterval(20)
    tracker.on_scan_status(*status(num_points=20))
    step(tracker, "scan_core", 10.0)
    tracker.on_scan_progress({"value": 14, "max_value": 20}, {"scan_id": "s1"})
    tracker.on_queue_status(*queue("s1"))
    assert not tracker._lost_check.isActive()
    # the server was restarted while the scan ran: it never reports aborted
    tracker.on_queue_status(*queue())
    qtbot.waitUntil(lambda: progress.state.finished, timeout=2000)
    assert progress.state.status == "aborted" and progress.state.lost
    assert progress.state.timings["scan_core"].status == "interrupted"
    assert progress.bar.mode == BarMode.ERROR
    assert progress.bar.text == "Aborted in Measuring · scan server stopped"
    assert progress.next_label.full_text() == "The scan server stopped while the scan ran"
    assert not progress.stop_button.isEnabled()


def test_a_resumed_scan_runs_again_when_its_queue_entry_runs(progress):
    tracker = progress.tracker
    tracker.on_scan_status(*status(num_points=10))
    step(tracker, "scan_core", 10.0)
    tracker.on_scan_progress({"value": 4, "max_value": 10}, {"scan_id": "s1"})
    tracker.on_scan_status(*status(state="paused"))
    assert progress.state_chip.text() == "Paused" and progress.bar.mode == BarMode.PAUSED
    # a hard pause only pauses the queue entry; the queue itself still reports RUNNING
    tracker.on_queue_status(*queue("s1", entry_status="PAUSED"))
    assert progress.state_chip.text() == "Paused"
    # BEC resumes through the entry's status and sends no new scan status
    tracker.on_queue_status(*queue("s1"))
    tracker.on_scan_progress({"value": 6, "max_value": 10}, {"scan_id": "s1"})
    assert progress.state_chip.text() == "Measuring"
    assert progress.bar.mode == BarMode.PROGRESS
    assert progress.bar.text.startswith("Point 6 of 10")


def test_a_paused_scan_that_reports_its_next_step_runs_again(progress):
    tracker = progress.tracker
    tracker.on_scan_status(*status())
    step(tracker, "stage", 10.0)
    tracker.on_scan_status(*status(state="paused"))
    assert progress.state_chip.text() == "Paused"
    step(tracker, "pre_scan", 12.0)
    assert progress.state.status == "open"
    assert progress.state_chip.text() != "Paused"


def test_a_final_status_after_the_queue_update_wins(progress, qtbot):
    tracker = progress.tracker
    tracker._lost_check.setInterval(20)
    tracker.on_scan_status(*status())
    tracker.on_queue_status(*queue())  # the queue can drop the scan just before its status
    tracker.on_scan_status(*status(state="closed"))
    qtbot.wait(60)
    assert progress.state.status == "closed" and not progress.state.lost
    assert not tracker._lost_check.isActive()


def test_the_check_of_a_lost_scan_does_not_end_the_next_scan(progress, qtbot):
    tracker = progress.tracker
    tracker._lost_check.setInterval(20)
    tracker.on_scan_status(*status())
    tracker.on_queue_status(*queue())
    tracker.on_scan_status(*status(scan_id="s2"))  # opened before the check ran
    qtbot.wait(60)
    assert progress.state.scan_id == "s2" and not progress.state.finished


GRID_NAMES = ["start", "stop", "steps"]


@pytest.mark.parametrize(
    "values, names, expected",
    [
        ([-5, 5, 10], GRID_NAMES, "samx -5 → 5 steps 10"),  # the number of steps is no position
        ([-5, 5], ["start", "stop"], "samx -5 → 5"),
        ([1.5], ["target"], "samx 1.5"),
        ([[1, 2, 3]], ["positions"], "samx 1 → 2 → 3"),
        ([1, 2], ["center", "width"], "samx center 1 width 2"),
        ([-5, 5], None, "samx -5 → 5"),
        ([-5, 5, 10], None, "samx -5 5 10"),  # unknown meaning: not shown as a path
    ],
)
def test_argument_bundles_show_what_their_values_mean(values, names, expected):
    assert args_summary({"args": {"samx": values}, "kwargs": {}}, names) == expected


def test_request_inputs_are_split_in_bundles_with_their_names():
    inputs = {"arg_bundle": ["samx", -5, 5, 10, "samy", -1, 1, 20], "inputs": {}, "kwargs": {}}
    assert request_inputs_summary(inputs, GRID_NAMES) == (
        "samx -5 → 5 steps 10 · samy -1 → 1 steps 20"
    )
    assert request_inputs_summary(inputs) == "samx -5 5 10 samy -1 1 20"


def test_a_device_rpc_in_the_request_inputs_is_a_call():
    inputs = {
        "arg_bundle": [],
        "inputs": {"device": "samx", "func": "read"},
        "kwargs": {"func_args": ["a"], "func_kwargs": {"cached": False}, "rpc_id": "abc"},
    }
    assert request_inputs_summary(inputs) == "samx.read('a', cached=False)"


def test_scan_bundle_names_come_from_the_scan_info():
    arg_input = {"device": "device", "start": "float", "stop": "float", "steps": "int"}
    scans = SimpleNamespace(grid_scan=SimpleNamespace(scan_info={"arg_input": arg_input}))
    assert scan_bundle_names(scans, "grid_scan") == GRID_NAMES
    assert scan_bundle_names(scans, "unknown_scan") == []
    assert scan_bundle_names(None, "grid_scan") == []


def test_the_scan_arguments_follow_the_title(progress):
    assert progress.args_label.full_text() == ""
    progress.tracker.on_scan_status(*status())
    assert progress.title_label.full_text() == "#12 line_scan"
    assert progress.title_label.font().bold() and not progress.args_label.font().bold()
    assert progress.args_label.full_text().startswith("samx -5 5")
    assert progress.args_label.full_text() in progress.header_row.toolTip()


def test_the_title_keeps_its_width_and_the_arguments_take_the_rest(progress, qtbot):
    progress.resize(900, 200)
    progress.show()
    qtbot.waitExposed(progress)
    progress.tracker.on_scan_status(*status())
    qtbot.waitUntil(lambda: progress.title_label.text() == "#12 line_scan", timeout=2000)
    assert progress.args_label.width() > 100
    assert progress.args_label.x() <= progress.title_label.geometry().right() + 12


def test_a_failed_step_stays_an_error_after_the_abort(progress):
    progress.tracker.on_scan_status(*status())
    step(progress.tracker, "stage", 10.0)
    progress.tracker.on_scan_hook(*hook("before_stage_modifier", 11.0))
    progress.tracker.on_scan_hook(*hook("before_stage_modifier", 12.0, hook_status="error"))
    progress.tracker.on_scan_hook(*hook("stage", 12.5, hook_status="error"))
    progress.tracker.on_scan_status(*status(state="aborted"))
    assert progress.state.timings["before_stage_modifier"].status == "error"
    assert progress.state.timings["stage"].status == "error"
    assert progress.state.hook_error == "stage"


def test_a_new_step_clears_the_wait_of_the_previous_step(progress):
    trigger = [{"device": "eiger", "action": "trigger", "parameter": {}}]
    step(
        progress.tracker,
        "scan_core",
        50.0,
        instructions=trigger,
        waiting=True,
        wait_started_at=45.0,
    )
    assert progress.instruction_label.full_text().startswith("Waiting for eiger")
    progress.tracker.on_scan_hook(*hook("post_scan", 51.0))
    assert progress.state.waiting is False
    assert progress.instruction_label.full_text() == ""


def test_a_step_of_another_scan_starts_that_scan(progress):
    progress.tracker.on_scan_status(*status())
    step(progress.tracker, "scan_core", 10.0)
    progress.tracker.on_scan_hook(*hook("stage", 20.0, scan_id="s2"))
    assert progress.state.scan_id == "s2" and progress.state.top_hook == "stage"


def opened_mid_scan(qtbot, mocked_client, stored):
    """A ScanProgressBar created while the connector holds the given stored messages."""
    from bec_lib.endpoints import MessageEndpoints

    def get(endpoint):
        msg = stored.get(endpoint.endpoint)
        return None if msg is None else mock.MagicMock(content=msg[0], metadata=msg[1])

    keys = {
        "status": MessageEndpoints.scan_status().endpoint,
        "hook": MessageEndpoints.scan_hook().endpoint,
        "progress": MessageEndpoints.scan_progress().endpoint,
        "queue": MessageEndpoints.scan_queue_status().endpoint,
    }
    stored = {keys[k]: v for k, v in stored.items()}
    with mock.patch.object(mocked_client.connector, "get", side_effect=get):
        widget = create_widget(qtbot, ScanProgressBar, client=mocked_client)
        qtbot.waitUntil(lambda: widget.tracker.loaded, timeout=2000)  # read in the thread pool
    return widget


def test_opened_mid_scan_shows_the_stored_hook_and_progress(qtbot, mocked_client):
    import time

    now = time.time()
    widget = opened_mid_scan(
        qtbot,
        mocked_client,
        {
            "status": status(num_points=20),
            "hook": hook(
                "scan_core",
                now - 1.0,
                hook_started_at=now - 21.0,
                instructions=[{"device": "eiger", "action": "trigger", "parameter": {}}],
                waiting=True,
                wait_started_at=now - 4.0,
            ),
            "progress": ({"value": 7, "max_value": 20, "done": False}, {"scan_id": "s1"}),
        },
    )
    assert widget.state_chip.text() == "Measuring"
    # the stored hook also has the current instruction and how long it has been waiting
    assert widget.instruction_label.full_text() == "Waiting for eiger (trigger) · 0:04"
    assert widget.bar.mode == BarMode.PROGRESS
    # 7 points in 21 s, so the 13 points left take about 39 s
    assert widget.state.remaining() == pytest.approx(39.0, abs=1.0)
    assert widget.bar.text == "Point 7 of 20 · 35% · 0:39 left"
    assert widget.state.hook_elapsed() == pytest.approx(21.0, abs=1.0)
    # the steps before it are not known and not listed
    assert [t.hook for t in widget.state.step_times()] == ["scan_core"]
    assert widget.state.timings["scan_core"].duration(now) == pytest.approx(21.0, abs=1.0)


def test_stored_hook_and_progress_of_another_scan_are_ignored(qtbot, mocked_client):
    import time

    now = time.time()
    widget = opened_mid_scan(
        qtbot,
        mocked_client,
        {
            "status": status(num_points=20),
            "hook": hook("close_scan", now - 50.0, scan_id="old"),
            "progress": ({"value": 20, "max_value": 20, "done": True}, {"scan_id": "old"}),
        },
    )
    assert widget.state.scan_id == "s1"
    assert widget.state.top_hook is None and widget.state.progress_value is None
    assert widget.state_chip.text() == "Running"


def test_opened_after_a_restart_ends_the_stale_stored_scan(qtbot, mocked_client):
    from bec_widgets.widgets.progress.scan_progressbar.scan_hook_tracker import ScanHookTracker

    # the stored status still says open, but the restarted server's queue no longer has the scan
    with mock.patch.object(ScanHookTracker, "LOST_SCAN_GRACE_MS", 20):
        widget = opened_mid_scan(
            qtbot, mocked_client, {"status": status(), "queue": queue("other")}
        )
    qtbot.waitUntil(lambda: widget.state.finished, timeout=2000)
    assert widget.state.lost
    assert widget.state_chip.text() == "Aborted"


def test_a_scan_that_finished_between_the_startup_reads_shows_done(qtbot, mocked_client):
    # read "open", then the scan finished before the queue was read: not a lost scan
    widget = opened_mid_scan(qtbot, mocked_client, {"status": status(), "queue": queue()})
    assert not widget.state.finished  # the grace period applies at startup too
    widget.tracker.on_scan_status(*status(state="closed"))
    assert widget.state_chip.text() == "Done" and not widget.state.lost
    assert "scan server stopped" not in widget.bar.text


def test_a_late_final_status_replaces_an_inferred_abort(progress, qtbot):
    tracker = progress.tracker
    tracker._lost_check.setInterval(20)
    tracker.on_scan_status(*status())
    step(tracker, "scan_core", 10.0)
    tracker.on_queue_status(*queue())
    qtbot.waitUntil(lambda: progress.state.lost, timeout=2000)
    tracker.on_scan_status(*status(state="closed"))  # the real end, after the grace period
    assert not progress.state.lost
    assert progress.state_chip.text() == "Done"
    assert progress.bar.text.startswith("Done ·") and "scan server stopped" not in progress.bar.text
    assert progress.next_label.full_text().startswith("Took")
    assert progress.state.timings["scan_core"].status == "completed"


def test_creating_the_bar_does_not_wait_for_redis(qtbot, mocked_client):
    import threading

    from bec_lib.endpoints import MessageEndpoints

    started, release, threads = threading.Event(), threading.Event(), []
    old_status = mock.MagicMock(content=status(scan_id="old")[0], metadata={})

    def get(endpoint, *args, **kwargs):
        threads.append(threading.get_ident())
        if endpoint == MessageEndpoints.scan_status():
            started.set()
            release.wait(5)
            return old_status
        return None

    with mock.patch.object(mocked_client.connector, "get", side_effect=get):
        widget = create_widget(qtbot, ScanProgressBar, client=mocked_client)
        assert started.wait(5)  # the widget is built while the stored status is still read
        assert not widget.tracker.loaded
        widget.tracker.on_scan_status(*status(scan_id="live"))  # a live update comes first
        release.set()
        qtbot.waitUntil(lambda: widget.tracker.loaded, timeout=2000)
    assert threading.main_thread().ident not in threads
    assert widget.state.scan_id == "live"  # the older stored status does not replace it


def test_opened_mid_scan_keeps_a_scan_that_is_still_queued(qtbot, mocked_client):
    widget = opened_mid_scan(qtbot, mocked_client, {"status": status(), "queue": queue("s1")})
    assert not widget.state.finished
    assert widget.state_chip.text() == "Running"


def stored_read(widget, **stored):
    """Deliver the result of the background startup read to a widget's tracker."""
    msgs = {key: mock.MagicMock(content=v[0], metadata=v[1]) for key, v in stored.items()}
    widget.tracker._on_initial_state(msgs)


def test_a_live_hook_does_not_stop_the_stored_status_and_progress(progress):
    step(progress.tracker, "scan_core", 100.0)  # the live hook comes before the startup read
    assert progress.state.scan_number is None
    stored_read(
        progress,
        status=status(num_points=20, user_metadata={"scan_name": "My Scan"}),
        hook=hook("stage", 90.0),
        progress=({"value": 7, "max_value": 20}, {"scan_id": "s1"}),
    )
    assert progress.state.scan_number == 12
    assert progress.state.display_name == "My Scan"
    assert progress.title_label.full_text() == "#12 My Scan"
    assert progress.state.progress_value == 7
    assert progress.state.top_hook == "scan_core"  # the stored hook is older than the live one


def test_a_live_status_keeps_its_values_over_the_stored_one(progress):
    progress.tracker.on_scan_status(*status(scan_number=13))
    progress.tracker.on_scan_progress({"value": 9, "max_value": 20}, {"scan_id": "s1"})
    stored_read(
        progress,
        status=status(scan_number=12),
        progress=({"value": 7, "max_value": 20}, {"scan_id": "s1"}),
    )
    assert progress.state.scan_number == 13
    assert progress.state.progress_value == 9


def test_live_progress_wins_over_the_stored_one_after_a_live_hook(progress):
    step(progress.tracker, "scan_core", 100.0)
    progress.tracker.on_scan_progress({"value": 9, "max_value": 20}, {"scan_id": "s1"})
    stored_read(
        progress,
        status=status(num_points=20),
        progress=({"value": 7, "max_value": 20}, {"scan_id": "s1"}),
    )
    assert progress.state.scan_number == 12
    assert progress.state.progress_value == 9


def test_the_stored_status_of_another_scan_is_ignored(progress):
    step(progress.tracker, "scan_core", 100.0, scan_id="s2")
    stored_read(progress, status=status(scan_id="old"))
    assert progress.state.scan_id == "s2"
    assert progress.state.scan_number is None


def test_time_left_is_the_same_for_a_widget_that_saw_the_whole_scan(progress):
    import time

    now = time.time()
    progress.tracker.on_scan_status(*status(num_points=20))
    progress.tracker.on_scan_hook(*hook("scan_core", now, hook_started_at=now - 21.0))
    progress.tracker.on_scan_progress({"value": 7, "max_value": 20}, {"scan_id": "s1"})
    assert progress.state.remaining() == pytest.approx(39.0, abs=1.0)


def test_progress_of_a_scan_without_a_status_is_ignored(progress):
    progress.tracker.on_scan_progress({"value": 3, "max_value": 10}, {"scan_id": "unseen"})
    assert progress.state is None
    progress.tracker.on_scan_status(*status())
    progress.tracker.on_scan_progress({"value": 3, "max_value": 10}, {"scan_id": "unseen"})
    assert progress.state.scan_id == "s1" and progress.state.progress_value is None


def test_bar_fills_spare_height_and_scales_its_label(progress, qtbot):
    progress.tracker.on_scan_status(*status(num_points=50))
    step(progress.tracker, "scan_core", 50.0)
    progress.resize(900, 180)
    progress.show()
    qtbot.waitExposed(progress)
    small_bar = progress.bar.height()
    small_font = progress.bar.label_font(small_bar, progress.bar.width()).pointSizeF()
    progress.resize(900, 420)
    qtbot.waitUntil(lambda: progress.bar.height() > small_bar + 100, timeout=1000)
    big_font = progress.bar.label_font(progress.bar.height(), progress.bar.width()).pointSizeF()
    assert big_font > small_font

    progress.fill_height = False
    qtbot.waitUntil(lambda: progress.bar.height() == progress.bar_height, timeout=1000)


def test_metadata_is_under_the_title_and_parameters_stay_a_tooltip(progress):
    progress.tracker.on_scan_status(*status())
    layout = progress.layout()
    assert layout.indexOf(progress.chips) == layout.indexOf(progress.header_row) + 1
    assert not progress.chips.isHidden()
    assert "steps 50" in progress.header_row.toolTip()
    progress.tracker.on_scan_status(*status(scan_id="s2", user_metadata={}))
    assert progress.chips.isHidden()


def test_long_instruction_is_elided_with_the_full_text_as_tooltip(progress, qtbot):
    step(progress.tracker, "pre_scan", 10.0)
    long_text = "Moving " + ", ".join(f"motor_{i}" for i in range(30))
    label = progress.instruction_label
    progress.resize(260, 220)
    progress.show()
    qtbot.waitExposed(progress)
    label.setText(long_text)
    assert label.text().endswith("…")
    assert label.toolTip() == long_text
    with mock.patch.object(label, "setToolTip") as set_tooltip:
        label.setText(long_text)
    set_tooltip.assert_not_called()
    progress._render()
    with mock.patch.object(label, "setToolTip") as set_tooltip:
        progress._render()  # nothing changed: no re-elide, no tooltip churn
    set_tooltip.assert_not_called()
    label.setText("Short")
    assert label.text() == "Short"
    assert label.toolTip() == ""


def test_bar_label_tooltip_only_when_cut(progress, qtbot):
    progress.resize(200, 160)
    progress.show()
    qtbot.waitExposed(progress)
    long_text = "Point 1 of 50 · 2% · 1:23:45 left and a very long tail that cannot fit"
    progress.bar.set_state("progress", 0.1, long_text)
    assert progress.bar.toolTip() == long_text
    progress.bar.set_state("progress", 0.1, "1%")
    assert progress.bar.toolTip() == ""


def test_stretched_stop_button_follows_the_bar_and_label_grows_gently(progress, qtbot):
    progress.tracker.on_scan_status(*status(num_points=50))
    step(progress.tracker, "scan_core", 50.0)
    progress.tracker.on_scan_progress(
        {"value": 20, "max_value": 50, "done": False}, {"scan_id": "s1"}
    )
    progress.resize(900, 150)
    progress.show()
    qtbot.waitExposed(progress)
    bar, stop = progress.bar, progress.stop_button
    min_bar = bar.bar_height
    small_stop_font = progress._stop_base_size  # px
    base_text = bar.label_font(min_bar, bar.width()).pointSizeF()

    progress.resize(900, 520)
    qtbot.waitUntil(lambda: bar.height() > 300, timeout=1000)
    qtbot.waitUntil(lambda: abs(stop.height() - bar.height()) <= 2, timeout=1000)
    assert bar.scale > 1.0
    assert stop.button.fontInfo().pixelSize() > small_stop_font
    font = bar.label_font(bar.height(), bar.width())
    assert font.pointSizeF() > base_text
    text_h = QFontMetricsF(font).height()
    base_h = QFontMetricsF(bar.label_font(min_bar, bar.width())).height()
    assert text_h - base_h <= 0.25 * (bar.height() - min_bar) + 1
    # a normal progress label still fits the bar width, so it is not elided
    width = QFontMetricsF(font).horizontalAdvance(bar.text)
    assert width <= bar.width() - bar.TEXT_PADDING
    assert bar.toolTip() == ""

    progress.fill_height = False
    qtbot.waitUntil(lambda: bar.height() == min_bar, timeout=1000)
    assert bar.scale == 1.0 and not bar.stretched
    assert stop.button.fontInfo().pixelSize() == small_stop_font
    assert stop.button.height() == stop.arrow.height() == min_bar


def test_stop_button_can_be_hidden(progress, qtbot):
    progress.tracker.on_scan_status(*status())
    progress.resize(420, 160)
    progress.show()
    qtbot.waitExposed(progress)
    bar_width = progress.bar.width()
    progress.show_stop_button = False
    qtbot.waitUntil(lambda: progress.bar.width() > bar_width, timeout=1000)
    assert progress.stop_button.isHidden()
    progress.ask_stop()
    progress._render()
    assert progress.confirm_frame.isHidden()
    assert progress.stop_button.isHidden()

    progress.show_stop_button = True
    assert not progress.stop_button.isHidden()
    assert progress.stop_button.isEnabled()
    progress.ask_stop()
    assert not progress.confirm_frame.isHidden()
    progress.show_stop_button = False
    assert progress.confirm_frame.isHidden() and progress.stop_button.isHidden()


def test_stop_button_hidden_from_the_constructor(qtbot, mocked_client):
    widget = create_widget(qtbot, ScanProgressBar, client=mocked_client, show_stop_button=False)
    assert widget.stop_button.isHidden()


def test_style_sheets_have_no_unknown_properties(qtbot, mocked_client):
    from qtpy.QtCore import qInstallMessageHandler

    messages = []
    previous = qInstallMessageHandler(lambda _mode, _context, text: messages.append(text))
    try:
        progress = create_widget(qtbot, ScanProgressBar, client=mocked_client)
        progress.tracker.on_scan_status(*status())
        progress.resize(420, 300)
        progress.show()
        qtbot.waitExposed(progress)
        progress.grab()
    finally:
        qInstallMessageHandler(previous)
    assert "text-decoration-style" not in progress.step_times.styleSheet()
    assert not [m for m in messages if "Unknown property" in m]


def test_tall_bar_label_and_stop_do_not_change_size_on_ticks(progress, qtbot):
    from qtpy.QtCore import QEvent, QObject

    class ResizeCounter(QObject):
        count = 0

        def eventFilter(self, _obj, event):  # pylint: disable=invalid-name
            if event.type() == QEvent.Type.Resize:
                self.count += 1
            return False

    progress.tracker.on_scan_status(*status(num_points=120))
    step(progress.tracker, "scan_core", 1.0)
    progress.resize(560, 480)
    progress.show()
    qtbot.waitExposed(progress)
    qtbot.wait(50)
    counter = ResizeCounter()
    progress.stop_button.installEventFilter(counter)
    sizes, bar_geometries = [], set()
    for tick in range(60):
        progress.tracker.on_scan_progress(
            {"value": tick * 2, "max_value": 120, "done": False}, {"scan_id": "s1"}
        )
        qtbot.wait(2)
        rect = progress.bar._bar_rect()
        sizes.append(
            progress.bar.label_font(rect.height(), progress.bar._label_width(rect)).pointSizeF()
        )
        bar_geometries.add(progress.bar.geometry().getRect())
    font_changes = sum(1 for a, b in zip(sizes, sizes[1:]) if a != b)
    assert font_changes <= 2  # only when the reserved label length grows
    assert len(bar_geometries) <= font_changes + 1
    assert counter.count <= font_changes + 1
    # the label uses most of a tall bar's width but keeps some air at both ends
    rect = progress.bar._bar_rect()
    font = progress.bar.label_font(rect.height(), progress.bar._label_width(rect))
    width = QFontMetricsF(font).horizontalAdvance(progress.bar.text)
    assert 0.55 * rect.width() <= width <= progress.bar.TEXT_WIDTH_SHARE * rect.width()


def test_docked_stop_keeps_a_small_share_and_the_bar_label_fits(progress, qtbot):
    progress.tracker.on_scan_status(*status(num_points=50))
    step(progress.tracker, "scan_core", 1.0)
    progress.resize(690, 260)
    progress.show()
    qtbot.waitExposed(progress)
    progress.tracker.on_scan_status(*status(state="aborted"))
    qtbot.wait(50)
    row = progress._bar_row.geometry().width()
    stop = progress.stop_button
    assert stop.width() <= progress.STOP_ROW_MAX * row + 1
    rect = progress.bar._bar_rect()
    font = progress.bar.label_font(rect.height(), progress.bar._label_width(rect))
    assert progress.bar.text.startswith("Aborted in Measuring")
    width = QFontMetricsF(font).horizontalAdvance(progress.bar.text)
    assert width <= rect.width() - progress.bar.TEXT_PADDING  # not elided

    progress.tracker.on_scan_status(*status(scan_id="s2", state="open", num_points=50))
    step(progress.tracker, "scan_core", 2.0, scan_id="s2")
    qtbot.wait(50)
    before = progress.bar.geometry()
    stop._activate_emergency_stop()
    qtbot.wait(50)
    assert progress.bar.geometry() == before  # Emergency Stop does not move the bar
    stop._deactivate_emergency_stop()
    qtbot.wait(50)
    assert progress.bar.geometry() == before


@pytest.mark.parametrize("size", [(420, 190), (620, 190), (690, 260), (900, 300)])
def test_stop_never_clips_its_label(progress, qtbot, size):
    progress.tracker.on_scan_status(*status(num_points=1000))
    step(progress.tracker, "scan_core", 1.0)
    progress.resize(*size)
    progress.show()
    qtbot.waitExposed(progress)
    qtbot.wait(50)
    stop = progress.stop_button
    button = stop.button
    for emergency in (False, True):
        if emergency:
            stop._activate_emergency_stop()
            qtbot.wait(20)
        assert button.width() >= button.sizeHint().width(), button.text()
        assert stop.width() >= button.sizeHint().width() + stop.arrow.width() - 1
        # measured with the polished font, the label keeps some room before the divider
        with_icon = not button.icon().isNull()
        assert button.width() >= stop.label_width(button.text(), with_icon) + 2, button.text()
    stop._reset_timer.stop()
    stop._deactivate_emergency_stop()


def test_unstretched_stop_has_the_bar_height_on_both_segments(qtbot, mocked_client):
    widget = create_widget(qtbot, ScanProgressBar, client=mocked_client, fill_height=False)
    widget.tracker.on_scan_status(*status(num_points=50))
    step(widget.tracker, "scan_core", 1.0)
    widget.resize(520, 200)
    widget.show()
    qtbot.waitExposed(widget)
    bar, stop = widget.bar, widget.stop_button

    def aligned(height):
        parts = (stop.button, stop.arrow)
        return all(part.height() == height and part.y() == stop.button.y() for part in parts)

    qtbot.waitUntil(lambda: aligned(bar.height()), timeout=1000)
    assert bar.height() == bar.get_bar_height()

    widget.bar_height = 34
    qtbot.waitUntil(lambda: bar.height() == 34 and aligned(34), timeout=1000)

    # stretched the parts follow the tall bar; back to normal they take the bar height again
    widget.resize(520, 400)
    widget.fill_height = True
    qtbot.waitUntil(lambda: bar.stretched and aligned(bar.height()), timeout=1000)
    assert stop.button.height() > 34
    widget.fill_height = False
    qtbot.waitUntil(lambda: not bar.stretched and aligned(34), timeout=1000)


def test_the_scan_is_shown_by_its_own_name(progress):
    progress.tracker.on_scan_status(*status(user_metadata={"scan_name": "My Scan"}))
    assert progress.title_label.full_text() == "#12 My Scan"
    assert progress.header_row.toolTip().startswith("line_scan: samx -5 5")
    progress.tracker.on_scan_status(*status(scan_id="s2", user_metadata={}))
    assert progress.title_label.full_text() == "#12 line_scan"
    assert not progress.header_row.toolTip().startswith("line_scan:")


def test_show_details_toggles_the_metadata_chips(progress, qtbot):
    progress.show()
    qtbot.waitExposed(progress)
    progress.tracker.on_scan_status(*status())
    assert progress.chips.isVisible()
    progress.setProperty("show_details", False)  # as Designer and the property editor set it
    assert not progress.chips.isVisible()
    progress.show_details = True
    assert progress.chips.isVisible()
    progress.tracker.on_scan_status(*status(scan_id="s2", user_metadata={}))
    assert not progress.chips.isVisible()  # nothing to show without user metadata


def test_busy_stripes_run_at_10_hz_only_while_shown(progress, qtbot):
    progress.show()
    qtbot.waitExposed(progress)
    timer = progress.bar._stripe_timer
    step(progress.tracker, "prepare_scan", 100.0)
    assert progress.bar.mode == BarMode.BUSY
    assert timer.isActive() and timer.interval() == 100

    progress.hide()
    assert not timer.isActive()
    step(progress.tracker, "stage", 101.0)  # an update while hidden does not restart it
    assert not timer.isActive()
    progress.show()
    qtbot.waitExposed(progress)
    assert timer.isActive()

    progress.showMinimized()
    qtbot.waitUntil(lambda: not timer.isActive())
    step(progress.tracker, "pre_scan", 102.0)
    assert not timer.isActive()
    progress.showNormal()
    qtbot.waitUntil(timer.isActive)

    step(progress.tracker, "scan_core", 103.0)
    progress.tracker.on_scan_progress({"value": 1, "max_value": 10}, {"scan_id": "s1"})
    assert progress.bar.mode == BarMode.PROGRESS and not timer.isActive()
