# pylint: disable=missing-function-docstring, redefined-outer-name, protected-access
import json
from copy import deepcopy

import pytest
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import AvailableResourceMessage
from bec_lib.procedures.helper import ProcedureState
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QToolButton

from bec_widgets.applications.views.sequencer_view.concepts import CONCEPTS
from bec_widgets.applications.views.sequencer_view.sequencer_view import SequencerView
from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.control.sequencer import backend as backend_module
from bec_widgets.widgets.control.sequencer import editor_base, model, style
from bec_widgets.widgets.control.sequencer.backend import (
    BACKEND_AVAILABLE,
    SequencerBackend,
    friendly_message,
    run_failure,
    sequences_dir,
)
from bec_widgets.widgets.control.sequencer.checks import check
from bec_widgets.widgets.control.sequencer.document import SequenceDocument
from bec_widgets.widgets.control.sequencer.fields import device_picker, parse_number, parse_values
from bec_widgets.widgets.control.sequencer.table.table_editor import table_state

from .test_scan_control import available_scans_message

TIME_SCAN = {
    "class": "TimeScan",
    "base_class": "ScanBaseV4",
    "is_scan": True,
    "is_internal": False,
    "arg_input": {},
    "required_kwargs": [],
    "arg_bundle_size": {"bundle": 0, "min": None, "max": None},
    "doc": "Time scan",
    "signature": [
        {"name": "points", "kind": "POSITIONAL_OR_KEYWORD", "default": 1, "annotation": "int"},
        {"name": "interval", "kind": "POSITIONAL_OR_KEYWORD", "default": 1, "annotation": "float"},
    ],
    "gui_visibility": {},
}
HIDDEN = {**TIME_SCAN, "doc": "Move"}


@pytest.fixture
def client(mocked_client):
    resource = deepcopy(available_scans_message.resource)
    resource.update({"time_scan": TIME_SCAN, "umv": HIDDEN, "_internal_scan": TIME_SCAN})
    mocked_client.connector.set_and_publish(
        MessageEndpoints.available_scans(), AvailableResourceMessage(resource=resource)
    )
    yield mocked_client


@pytest.fixture
def backend(client):
    return SequencerBackend(client)


def two_positions() -> dict:
    """Twice: for samx at 1 and -1, move samx and run a time scan."""
    doc = model.empty_document("two_positions")
    loop = model.for_each_node(
        "position", [1, -1], [model.move_node("samx", model.ref("position"))]
    )
    model.children_of(loop).append(model.scan_node("time_scan", [], {"points": 2, "interval": 1}))
    doc["root"]["children"] = [model.repeat_node(2, [loop])]
    return model.normalize(doc)


def root_with(*children) -> dict:
    return {"id": "root", "type": "sequence", "children": list(children)}


# --- model ---------------------------------------------------------------------------------
def test_summary_and_timeline_unroll_loops():
    doc = two_positions()
    summary = model.summarize(doc["root"])
    assert summary.text() == "4 scans · 4 moves"
    items = model.timeline(doc["root"])
    assert [i.text for i in items if i.kind == "set"] == [
        "Move samx to 1",
        "Move samx to -1",
        "Move samx to 1",
        "Move samx to -1",
    ]
    assert items[0].context == "round 1/2 · position = 1"


def test_new_steps_are_blank_and_read_well():
    move, scan = model.new_step("set")[0], model.new_step("scan_call")[0]
    assert (move["device"], move["value"], scan["name"]) == ("", None, "")
    assert model.sentence(move) == "Move a motor to …"
    assert model.sentence(scan) == "Run a scan"
    start, loop = model.new_step("while")
    assert model.sentence(loop, root_with(start, loop)) == "While the motor is still moving"


def test_scan_details_leave_out_default_settings():
    entries = {"time_scan": TIME_SCAN}
    node = model.scan_node("time_scan", [], {"points": 5, "interval": 1})
    assert model.scan_details(node, entries) == "5 points"
    assert model.scan_details(node) == "5 points · 1 s interval"


def test_unused_variable_names():
    root = root_with(model.for_each_node("position", [1]))
    assert model.unused_variable(root) == "position2"
    assert model.unused_variable(root, "energy") == "energy"


def test_parse_numbers_and_values():
    assert parse_number("") is None
    assert parse_number("2") == 2 and isinstance(parse_number("2"), int)
    assert parse_number("2.0") == 2.0 and isinstance(parse_number("2.0"), float)
    assert parse_number("1e-3") == 0.001
    assert parse_number("abc") == "abc"
    assert parse_values("1, -1; 2.5\n3") == [1, -1, 2.5, 3]


# --- document ------------------------------------------------------------------------------
def test_document_delete_while_also_removes_its_move(qtbot):
    doc = SequenceDocument()
    doc.add(model.while_moving_nodes("samx", 5))
    doc.delete(model.children_of(doc.root)[1]["id"])
    assert model.children_of(doc.root) == []


def test_document_move_into_loop_and_undo(qtbot):
    doc = SequenceDocument()
    loop = model.repeat_node(3)
    scan = model.scan_node("time_scan")
    doc.add([loop, scan])
    doc.move(scan["id"], loop["id"], 0)
    assert [n["id"] for n in model.children_of(doc.node(loop["id"]))] == [scan["id"]]
    doc.undo()
    assert [n["id"] for n in model.children_of(doc.root)] == [loop["id"], scan["id"]]


def test_document_refuses_moving_a_loop_into_itself(qtbot):
    doc = SequenceDocument()
    outer = model.repeat_node(2, [model.repeat_node(2)])
    doc.add([outer])
    doc.move(outer["id"], model.children_of(outer)[0]["id"], 0)
    assert model.children_of(doc.root)[0]["id"] == outer["id"]


def test_new_move_inside_a_loop_goes_to_each_value(qtbot):
    doc = SequenceDocument()
    doc.add(doc.new_nodes("for_each"))
    loop = model.children_of(doc.root)[0]
    doc.select(loop["id"])
    doc.add_next_to_selection(doc.new_nodes("set"))
    assert model.children_of(loop)[0]["value"] == {"ref": "position"}
    assert doc.new_nodes("for_each")[0]["variable"] == "position2"


# --- checks --------------------------------------------------------------------------------
def test_checks_find_every_unfinished_step(backend):
    root = root_with(
        model.move_node("", None),
        model.move_node("samx", None),
        model.move_node("nope", 1),
        model.move_node("samx", "fast"),
        model.scan_node(""),
        model.scan_node("line_scan"),
        model.scan_node("line_scan", ["", 0, 1]),
        model.for_each_node("position", []),
        model.repeat_node(2),
        model.scan_node("time_scan", [], {"points": 1, "interval": 1}),
    )
    messages = [p.message for p in check(root, backend)]
    assert messages == [
        "Choose a motor",
        "Enter a position",
        "There is no device called “nope”",
        "samx needs a number",
        "Choose a scan",
        "Add at least one motor to the scan",
        "Choose a motor for the scan",
        "Enter at least one value",
        "This loop has no steps inside",
    ]


def test_checks_use_the_motor_limits_for_every_loop_value(backend):
    loop = model.for_each_node(
        "position", [1, 12], [model.move_node("samx", model.ref("position"))]
    )
    problems = check(root_with(loop), backend)
    assert [p.message for p in problems] == ["12 is outside the limits of samx (-10 to 10)"]
    assert problems[0].node_id == model.children_of(loop)[0]["id"]
    assert check(root_with(model.move_node("aptrx", 1e6)), backend) == []


def test_checks_pass_a_finished_sequence(backend):
    assert check(two_positions()["root"], backend) == []


# --- backend -------------------------------------------------------------------------------
def test_friendly_messages():
    assert (
        friendly_message("Undefined Reference: pos")
        == "“pos” is only known inside its “For each pos” loop"
    )
    assert friendly_message("Unknown device or signal: foo") == "There is no device called “foo”"
    assert (
        friendly_message("Non-settable device or signal: eiger") == "“eiger” cannot be moved or set"
    )
    assert (
        friendly_message("Device '' specified for scan argument at position 0 was not found")
        == "Choose a motor for the scan"
    )


def test_run_failure_names_the_step_and_the_reason():
    error = (
        "Traceback (most recent call last):\n  File ...\n"
        "bec_lib.scan_sequencer.core.runtime.ExecutionError: Node root/move_1: An alarm.\n"
        "\tAn error occurred during 'set' on device 'samx'.\n\n"
        "LimitError: position=1000 not within limits (-50, 50)\n"
    )
    failure = run_failure(error)
    assert failure.node_id == "move_1"
    assert failure.message == "LimitError: position=1000 not within limits (-50, 50)"
    assert run_failure("").message == "The sequence failed"


def test_scan_entries_hide_moves_and_internal_scans(backend, client):
    assert list(backend.scan_entries()) == ["grid_scan", "line_scan", "time_scan"]
    client.connector.set_and_publish(
        MessageEndpoints.available_scans(), AvailableResourceMessage(resource={})
    )
    assert "time_scan" in backend.scan_entries()  # cached until reload
    backend.reload()
    assert backend.scan_entries() == {}


def test_backend_device_information(backend):
    assert backend.is_motor("samx") and not backend.is_motor("eiger")
    assert backend.limits("samx") == (-10.0, 10.0)
    assert backend.limits("aptrx") is None
    assert backend.device("missing") is None
    assert backend.position("samx") == 2.0


def test_sequences_dir_is_next_to_the_widget_settings(client):
    assert sequences_dir(client).name == "sequences"
    assert sequences_dir(object()) is None


# --- concepts ------------------------------------------------------------------------------
@pytest.mark.parametrize("concept", [c for c in CONCEPTS if c != "guided"])
def test_concepts_start_empty(qtbot, client, concept):
    editor = create_widget(qtbot, CONCEPTS[concept], client=client)
    assert model.children_of(editor.document.root) == []
    assert editor.run_bar.state.text() == "Empty"
    assert not editor.run_bar.run_button.isEnabled()


def test_guided_starts_with_an_unfilled_sentence(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["guided"], client=client)
    assert editor.run_bar.state.text().endswith("to finish")
    assert not editor.run_bar.run_button.isEnabled()
    nodes = [n for n, _d, _p in model.walk(editor.document.root)]
    assert all(n.get("device", "") == "" for n in nodes if n["type"] == "set")
    assert all(n.get("name") == "" for n in nodes if n["type"] == "scan_call")


@pytest.mark.parametrize("concept", ["recipe", "blocks", "flow"])
def test_tree_concepts_mark_unfinished_steps_and_get_ready(qtbot, client, concept):
    editor = create_widget(qtbot, CONCEPTS[concept], client=client)
    editor.document.add(editor.document.new_nodes("set"))
    editor.run_bar.check()
    move = model.children_of(editor.document.root)[0]
    assert editor.problem_for(move["id"]) == "Choose a motor"
    assert editor.run_bar.state.text() == "1 step to finish"
    editor.document.update(move["id"], device="samx", value=1)
    editor.run_bar.check()
    assert editor.problems == []
    assert editor.run_bar.state.text() in ("Ready to run", "Editing only")


def test_recipe_inspector_edits_the_selected_move(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["recipe"], client=client)
    editor.add_step("set")
    move = model.children_of(editor.document.root)[0]
    inspector = editor.inspector
    assert inspector.pages.currentWidget() is inspector.move_page
    inspector.device.setCurrentText("samx")
    inspector.move_value.number.setText("2.5")
    inspector._commit()
    assert (move["device"], move["value"]) == ("samx", 2.5)
    assert "Now at 2" in inspector.move_info.text() and "-10 to 10" in inspector.move_info.text()


def test_theme_colors_are_copies(qtbot):
    color = style.theme("FG", "#333333")
    color.setAlpha(10)
    assert style.theme("FG", "#333333").alpha() == 255


def test_device_picker_is_not_red_while_empty(qtbot, client):
    picker = device_picker(None, client)
    qtbot.addWidget(picker)
    picker.check_validity("")
    assert picker.styleSheet() == ""
    picker.setCurrentText("nodevice")
    picker.check_validity("nodevice")
    assert "red" in picker.styleSheet()


def test_recipe_inspector_picks_a_scan_with_its_defaults(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["recipe"], client=client)
    editor.add_step("scan_call")
    scan = model.children_of(editor.document.root)[0]
    editor.inspector._on_scan_chosen("line_scan")
    assert scan["name"] == "line_scan"
    assert editor.inspector.scan_picker.scan() == "line_scan"
    assert scan["positional"] == ["", 0.0, 0.0]
    assert "metadata" not in scan["arguments"]
    editor.run_bar.check()
    assert editor.problem_for(scan["id"]) == "Choose a motor for the scan"


def test_inspector_keeps_metadata_of_a_scan(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["recipe"], client=client)
    scan = model.scan_node("time_scan", [], {"points": 2, "interval": 1, "metadata": {"a": 1}})
    editor.document.add([scan])
    editor.inspector._commit()
    assert scan["arguments"]["metadata"] == {"a": 1}


def test_recipe_tree_shows_the_problem_next_to_the_step(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["recipe"], client=client)
    editor.add_step("set")
    editor.run_bar.check()
    item = editor.tree.topLevelItem(0)
    assert item.text(1) == "Choose a motor"


def test_blocks_show_problems_without_rebuilding(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["blocks"], client=client)
    editor.append("set")
    editor.run_bar.check()
    move = model.children_of(editor.document.root)[0]
    block = editor._blocks[move["id"]]
    assert block.problem == "Choose a motor"
    editor.inline_update(move["id"], device="samx", value=1)
    editor.run_bar.check()
    assert editor._blocks[move["id"]] is block
    assert block.problem == ""


def test_table_rows_become_moves_and_scans(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["table"], client=client)
    editor.add_motor("samx")
    editor.add_motor("samy")
    editor.paste("A\t1\t2\nB\t3\t\nC\t4\t5")
    editor.scan.update(name="time_scan", positional=[], arguments={"points": 1, "interval": 1})
    editor._compile()
    summary = model.summarize(editor.document.root)
    assert (summary.scans, summary.moves) == (3, 5)
    scans = [n for n, _d, _p in model.walk(editor.document.root) if n["type"] == "scan_call"]
    assert scans[0]["arguments"]["metadata"] == {"sample_name": "A"}
    editor.table.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
    editor.repeat_spin.setValue(2)
    assert model.summarize(editor.document.root).scans == 4


def test_table_motor_chips_follow_the_columns(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["table"], client=client)
    editor.add_motor("samx")
    editor.add_motor("samy")
    editor._remove_motor("samx")
    chips = [
        editor.motor_chips.itemAt(i).widget().text() for i in range(editor.motor_chips.count())
    ]
    assert chips == ["samy  ✕"]
    # removed chips must disappear at once, not when Qt gets round to deleting them
    shown = [b for b in editor.findChildren(QToolButton) if "✕" in b.text() and not b.isHidden()]
    assert len(shown) == 1


def test_table_paste_with_a_header_adds_the_motor_columns(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["table"], client=client)
    editor.paste("name\tsamx\tsamy\nfoil\t1\t2\nempty\t3\t4\n")
    assert editor.motors == ["samx", "samy"]
    assert [r[1] for r in editor._rows()] == ["foil", "empty"]


def test_table_marks_the_cell_outside_the_limits(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["table"], client=client)
    editor.add_motor("samx")
    editor.paste("A\t50")
    editor.run_bar.check()
    item = editor.table.item(0, 2)
    assert "outside the limits" in item.toolTip()


def test_table_reads_its_own_sequence_back(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["table"], client=client)
    editor.add_motor("samx")
    editor.paste("A\t1\nB\t2")
    editor.scan.update(name="time_scan", positional=[], arguments={"points": 1, "interval": 1})
    editor.repeat_spin.setValue(3)
    state = table_state(json.loads(json.dumps(editor.document.doc)))
    assert state["motors"] == ["samx"]
    assert state["rows"] == [["A", [1], True], ["B", [2], True]]
    assert state["repeats"] == 3
    assert table_state(two_positions()) is None


def test_guided_goals_compile(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["guided"], client=client)
    scan = model.scan_node("time_scan", [], {"points": 1, "interval": 1})
    memory = dict(
        motor="samx",
        positions=[1, 2],
        repeat=2,
        setting="samz",
        setting_values=[0.5, 1, 1.5],
        slow="samy",
        slow_values=[0, 1],
        fast="samx",
        fast_values=[0, 1, 2],
        count=5,
        target=3,
    )
    expected = {"positions": 4, "values": 6, "grid": 6, "repeat": 5}
    for goal, scans in expected.items():
        editor.restore_state({"goal": goal, "scan": scan, "memory": memory})
        assert model.summarize(editor.document.root).scans == scans, goal
        editor.run_bar.check()
        assert editor.problems == [], goal
    editor.restore_state({"goal": "during", "scan": scan, "memory": memory})
    assert model.summarize(editor.document.root).open_ended
    editor.run_bar.check()
    assert editor.problems == []


def test_guided_points_at_the_missing_field_and_keeps_typed_values(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["guided"], client=client)
    editor.run_bar.check()
    assert editor.problem.text() == "Enter at least one value"
    editor.fields["positions"].setText("1, 2")
    editor._compile()
    editor._on_goal("during")
    editor._on_goal("positions")
    assert editor.fields["positions"].values() == [1, 2]


def test_flow_inserts_steps_at_a_plus(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["flow"], client=client)
    editor.document.add(editor.document.new_nodes("repeat"))
    loop = model.children_of(editor.document.root)[0]
    editor.document.add(editor.document.new_nodes("scan_call"), loop["id"], 0)
    assert model.children_of(loop)[0]["type"] == "scan_call"
    assert editor.timeline.count() == 2


# --- view ----------------------------------------------------------------------------------
def test_view_creates_editors_only_when_opened(qtbot, client):
    view = create_widget(qtbot, SequencerView, client=client)
    assert view.editors == {}
    view.on_enter()
    assert list(view.editors) == [next(iter(CONCEPTS))]


def test_view_hands_guided_and_foreign_files_to_recipe(qtbot, client):
    view = create_widget(qtbot, SequencerView, client=client, concept="guided")
    guided = view.editors["guided"]
    guided.restore_state(
        {"goal": "repeat", "scan": model.scan_node("time_scan"), "memory": {"count": 5}}
    )
    guided.open_in_recipe.emit(guided.document.doc)
    assert view.stack.currentWidget() is view.editors["recipe"]
    assert model.summarize(view.editors["recipe"].document.root).scans == 5
    table = view.show_concept("table")
    table.open_document(two_positions())
    assert view.stack.currentWidget() is view.editors["recipe"]
    assert model.summarize(view.editors["recipe"].document.root).scans == 4


def test_theme_change_rebuilds_editors_and_keeps_their_work(qtbot, client):
    from bec_widgets.utils.colors import apply_theme

    view = create_widget(qtbot, SequencerView, client=client, concept="table")
    table = view.editors["table"]
    table.add_motor("samx")
    table.paste("A\t1\nB\t2")
    table.repeat_spin.setValue(2)
    view.show_concept("recipe").document.set_document(two_positions())
    view.show_concept("table")
    apply_theme("light")
    apply_theme("dark")
    qtbot.wait(50)
    new_table = view.editors["table"]
    assert new_table is not table
    assert view.stack.currentWidget() is new_table
    assert new_table.motors == ["samx"] and new_table.table.rowCount() == 2
    assert model.summarize(new_table.document.root).scans == 4
    assert model.summarize(view.editors["recipe"].document.root).scans == 4


def test_drafts_keep_the_work_after_closing(qtbot, client, tmp_path, monkeypatch):
    monkeypatch.setattr(editor_base, "sequences_dir", lambda _client: tmp_path)
    first = create_widget(qtbot, CONCEPTS["recipe"], client=client, draft_name="recipe")
    first.document.set_document(two_positions())
    first.save_draft()
    assert (tmp_path / "drafts" / "recipe.json").exists()
    second = create_widget(qtbot, CONCEPTS["recipe"], client=client, draft_name="recipe")
    assert model.summarize(second.document.root).scans == 4


# --- run bar -------------------------------------------------------------------------------
class FakeStatus:
    def __init__(self):
        self.state = ProcedureState.SCHEDULED
        self.error = None
        self.done = False
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


@pytest.fixture
def ready_editor(qtbot, client, monkeypatch):
    monkeypatch.setattr(backend_module, "BACKEND_AVAILABLE", True)
    editor = create_widget(qtbot, CONCEPTS["recipe"], client=client)
    editor.document.set_document(two_positions())
    status = FakeStatus()
    editor.backend.submit = lambda doc: status
    editor.backend.validate = lambda doc: []
    editor.run_bar.check()
    assert editor.run_bar.run_button.isEnabled()
    return editor, status


def test_run_bar_follows_the_scans_until_finished(ready_editor):
    editor, status = ready_editor
    bar = editor.run_bar
    bar.run()
    assert bar.state.text() == "Queued"
    status.state = ProcedureState.RUNNING
    bar._on_scan_status({"status": "open", "info": {"scan_name": "time_scan"}}, {})
    bar._poll()
    assert bar.state.text() == "Running"
    assert bar.message.text().startswith("Scan 1 of 4")
    bar._on_scan_status({"status": "closed", "info": {"scan_name": "time_scan"}}, {})
    bar._on_scan_status({"status": "open", "info": {"scan_name": "umv"}}, {})
    bar._on_scan_status({"status": "open", "info": {"scan_name": "time_scan"}}, {})
    bar._poll()
    assert bar.message.text().startswith("Scan 2 of 4")
    status.state = ProcedureState.SUCCESS
    bar._poll()
    assert bar.state.text() == "Finished"
    assert not bar._poll_timer.isActive()
    assert bar.run_button.isVisible() or not bar.isVisible()


def test_run_bar_stop(ready_editor):
    editor, status = ready_editor
    bar = editor.run_bar
    bar.run()
    status.state = ProcedureState.RUNNING
    bar.stop()
    assert status.cancelled
    assert bar.state.text() == "Stopping"
    status.state, status.error = ProcedureState.FAILED, "Aborted by user."
    bar._poll()
    assert bar.state.text() == "Stopped"


def test_run_bar_marks_the_step_that_failed(ready_editor):
    editor, status = ready_editor
    bar = editor.run_bar
    move = next(n for n, _d, _p in model.walk(editor.document.root) if n["type"] == "set")
    bar.run()
    status.state = ProcedureState.FAILED
    status.error = f"ExecutionError: Node root/{move['id']}: An alarm.\nLimitError: too far"
    bar._poll()
    assert bar.state.text() == "Failed"
    assert bar.message.text() == "Move: LimitError: too far"
    assert editor.problem_for(move["id"]) == "Failed here: LimitError: too far"
    assert not bar.details_button.isHidden()


def test_run_bar_without_the_backend_only_edits(qtbot, client, monkeypatch):
    monkeypatch.setattr(backend_module, "BACKEND_AVAILABLE", False)
    editor = create_widget(qtbot, CONCEPTS["recipe"], client=client)
    editor.document.set_document(two_positions())
    editor.run_bar.check()
    assert editor.run_bar.state.text() == "Editing only"
    assert not editor.run_bar.run_button.isEnabled()


@pytest.mark.skipif(not BACKEND_AVAILABLE, reason="needs the scan sequencer backend")
def test_backend_accepts_what_the_concepts_build(qtbot, client):
    from bec_lib.scan_sequencer import Schedule

    for doc in (two_positions(),):
        Schedule.model_validate(doc)
