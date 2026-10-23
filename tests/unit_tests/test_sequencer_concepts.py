# pylint: disable=missing-function-docstring, redefined-outer-name, protected-access
import pytest
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import AvailableResourceMessage

from bec_widgets.applications.views.sequencer_view.concepts import CONCEPTS
from bec_widgets.applications.views.sequencer_view.sequencer_view import SequencerView
from bec_widgets.tests.client_mocks import mocked_client  # noqa: F401
from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.backend import BACKEND_AVAILABLE, friendly_message
from bec_widgets.widgets.control.sequencer.document import SequenceDocument

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
        {
            "name": "points",
            "kind": "POSITIONAL_OR_KEYWORD",
            "default": "_empty",
            "annotation": "int",
        },
        {
            "name": "interval",
            "kind": "POSITIONAL_OR_KEYWORD",
            "default": "_empty",
            "annotation": "float",
        },
    ],
    "gui_visibility": {},
}


@pytest.fixture
def client(mocked_client):
    mocked_client.connector.set_and_publish(
        MessageEndpoints.available_scans(),
        AvailableResourceMessage(resource={"time_scan": TIME_SCAN}),
    )
    yield mocked_client


def test_summary_multiplies_through_loops():
    doc = model.example_document()
    summary = model.summarize(doc["root"])
    assert (summary.scans, summary.moves) == (4, 4)
    assert summary.text() == "4 scans · 4 moves"


def test_timeline_substitutes_loop_values():
    doc = model.example_document()
    items = model.timeline(doc["root"])
    assert [i.text for i in items if i.kind == "set"] == [
        "Move samx to 1",
        "Move samx to -1",
        "Move samx to 1",
        "Move samx to -1",
    ]
    assert items[0].context == "round 1/2 · position = 1"


def test_while_moving_sentence_names_the_motor():
    start, loop = model.while_moving_nodes("samx", 5, [model.scan_node("time_scan")])
    root = {"id": "root", "type": "sequence", "children": [start, loop]}
    assert model.sentence(start) == "Start moving samx to 5 (don't wait)"
    assert model.sentence(loop, root) == "While samx is still moving"
    assert model.summarize(root).open_ended


def test_document_delete_while_also_removes_its_move(qtbot):
    doc = SequenceDocument()
    start, loop = model.while_moving_nodes("samx", 5)
    doc.add([start, loop])
    doc.delete(loop["id"])
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
    inner = model.children_of(outer)[0]
    doc.move(outer["id"], inner["id"], 0)
    assert model.children_of(doc.root)[0]["id"] == outer["id"]


def test_friendly_messages():
    assert (
        friendly_message("Undefined Reference: pos")
        == "“pos” is only known inside its “For each pos” loop"
    )
    assert friendly_message("Unknown device or signal: foo") == "There is no device called “foo”"


@pytest.mark.parametrize("concept", list(CONCEPTS))
def test_concepts_build_a_valid_document(qtbot, client, concept):
    editor = create_widget(qtbot, CONCEPTS[concept], client=client)
    doc = editor.document.doc
    assert doc["schema_version"] == 1
    assert model.summarize(doc["root"]).scans > 0
    if BACKEND_AVAILABLE:
        from bec_lib.scan_sequencer import Schedule

        Schedule.model_validate(doc)


def test_table_compiles_one_scan_per_measured_row(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["table"], client=client)
    rows = editor.table.rowCount()
    assert model.summarize(editor.document.root).scans == rows
    editor.table.item(0, 0).setCheckState(editor.table.item(0, 0).checkState().Unchecked)
    assert model.summarize(editor.document.root).scans == rows - 1
    editor.repeat_spin.setValue(3)
    assert model.summarize(editor.document.root).scans == 3 * (rows - 1)


def test_guided_goals_compile(qtbot, client):
    editor = create_widget(qtbot, CONCEPTS["guided"], client=client)
    expected = {"positions": 4, "values": 8, "grid": 6, "repeat": 5}
    for goal, scans in expected.items():
        editor._on_goal(goal)
        assert model.summarize(editor.document.root).scans == scans, goal
    editor._on_goal("during")
    assert model.summarize(editor.document.root).open_ended


def test_view_switches_concepts_and_hands_guided_result_to_recipe(qtbot, client):
    view = create_widget(qtbot, SequencerView, client=client, concept="guided")
    guided = view.editors["guided"]
    guided._on_goal("repeat")
    guided.open_in_recipe.emit(guided.document.doc)
    assert view.stack.currentWidget() is view.editors["recipe"]
    assert model.summarize(view.editors["recipe"].document.root).scans == 5


class FakeStatus:
    def __init__(self):
        from bec_lib.procedures.helper import ProcedureState

        self.state = ProcedureState.SCHEDULED
        self.error = None
        self.done = False
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


def test_run_bar_runs_and_reports_the_procedure_state(qtbot, client):
    from bec_lib.procedures.helper import ProcedureState

    editor = create_widget(qtbot, CONCEPTS["guided"], client=client)
    editor._on_goal("repeat")
    bar = editor.run_bar
    status = FakeStatus()
    bar.backend.submit = lambda doc: status
    bar.backend.validate = lambda doc: []
    bar.run()
    assert bar.state.text() == "Queued"
    status.state = ProcedureState.RUNNING
    bar._poll()
    assert bar.state.text() == "Running"
    bar.stop()
    assert status.cancelled
    status.state = ProcedureState.SUCCESS
    bar._poll()
    assert bar.state.text() == "Finished"
    assert not bar._poll_timer.isActive()


def test_view_creates_editors_only_when_opened(qtbot, client):
    view = create_widget(qtbot, SequencerView, client=client)
    assert view.editors == {}
    view.on_enter()
    assert list(view.editors) == [next(iter(CONCEPTS))]


def test_theme_change_rebuilds_editors_and_keeps_their_work(qtbot, client):
    from bec_widgets.utils.colors import apply_theme

    view = create_widget(qtbot, SequencerView, client=client, concept="table")
    table = view.editors["table"]
    table.repeat_spin.setValue(2)
    table._add_row()
    rows = table.table.rowCount()
    view.show_concept("recipe").document.delete(
        model.children_of(view.editors["recipe"].document.root)[0]["id"]
    )
    view.show_concept("table")
    apply_theme("light")
    apply_theme("dark")
    qtbot.wait(50)
    new_table = view.editors["table"]
    assert new_table is not table
    assert view.stack.currentWidget() is new_table
    assert new_table.table.rowCount() == rows
    assert model.summarize(new_table.document.root).scans == 2 * rows
    assert model.children_of(view.editors["recipe"].document.root) == []
