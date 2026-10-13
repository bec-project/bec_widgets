"""Scheduler composition and authoritative procedure integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Event, get_ident
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.control.scan_scheduler import ScanScheduler
from bec_widgets.widgets.control.scan_scheduler.document import SequenceDraft
from bec_widgets.widgets.control.scan_scheduler.inspector import ValueInput


@pytest.fixture
def scheduler(qtbot, mocked_client):
    info = json.loads(Path(__file__).with_name("scan_info.json").read_text())
    mocked_client.scans._available_scans = {
        name: SimpleNamespace(scan_info=entry) for name, entry in info.items()
    }
    mocked_client.proc = MagicMock()
    return create_widget(qtbot, ScanScheduler, client=mocked_client)


@pytest.fixture
def sequence():
    return {
        "schema_version": 1,
        "type": "sequence",
        "id": "alternating_positions",
        "revision": 1,
        "root": {
            "id": "repeat",
            "type": "repeat",
            "count": 2,
            "body": {
                "id": "positions",
                "type": "for_each",
                "variable": "position",
                "values": [1, -1],
                "body": {
                    "id": "steps",
                    "type": "sequence",
                    "children": [
                        {
                            "id": "move",
                            "type": "set",
                            "device": "samx",
                            "value": {"ref": "position"},
                            "wait": True,
                        },
                        {
                            "id": "scan",
                            "type": "scan_call",
                            "name": "time_scan",
                            "positional": [1, 0.1],
                            "arguments": {},
                        },
                    ],
                },
            },
        },
    }


def test_tree_and_scope(scheduler, sequence):
    scheduler.load_json(json.dumps(sequence))
    assert scheduler.exports.tabText(0) == "Description"
    scheduler._rebuild_tree(("body", "body", "children", 0))
    assert scheduler.inspector.fields["value"].mode.currentData() == "position"
    assert "position" in scheduler.inspector.scope.text()
    assert "and wait" in scheduler.tree.currentItem().text(1)
    assert json.loads(scheduler.document_json())["root"] == scheduler.draft.document["root"]


def test_validate_exports_in_worker(scheduler, sequence, qtbot):
    scheduler.load_json(json.dumps(sequence))
    scheduler.validate_sequence()
    qtbot.waitUntil(lambda: not scheduler._busy)
    assert "Sequence valid" in scheduler.message.text()
    assert "wait" in scheduler.description.toPlainText()
    assert "time_scan" in scheduler.python.toPlainText()
    assert scheduler.client.proc.request_new.call_count == 0


def test_invalid_scan_never_submitted(scheduler, sequence, qtbot):
    sequence["root"]["body"]["body"]["children"][1]["positional"] = []
    scheduler.load_json(json.dumps(sequence))
    scheduler.execute_sequence()
    qtbot.waitUntil(lambda: not scheduler._busy)
    assert scheduler.client.proc.request_new.call_count == 0
    assert "points" in scheduler.message.text()


def test_execute_uses_procedure_without_retaining_records(scheduler, sequence, qtbot):
    scheduler.load_json(json.dumps(sequence))
    scheduler.execute_sequence()
    qtbot.waitUntil(lambda: not scheduler._busy)
    request = scheduler.client.proc.request_new.call_args
    assert request.args[0] == "run_sequence"
    document, _definitions = request.args[1][0]
    assert json.loads(document)["revision"] == 1
    assert scheduler.draft.document["revision"] == 1
    assert not hasattr(scheduler, "records")
    assert not hasattr(scheduler, "queue_table")
    assert not hasattr(scheduler, "history_table")


def test_submission_does_not_block_event_loop(scheduler, sequence, qtbot):
    started, release = Event(), Event()
    threads = []

    def request(*args, **kwargs):
        threads.append(get_ident())
        started.set()
        assert release.wait(5)
        return SimpleNamespace(done=True, state=SimpleNamespace(value="SUCCESS"), error=None)

    scheduler.client.proc.request_new.side_effect = request
    scheduler.load_json(json.dumps(sequence))
    scheduler.execute_sequence()
    try:
        qtbot.waitUntil(started.is_set)
        assert scheduler._busy
        assert threads == [threads[0]] and threads[0] != get_ident()
    finally:
        release.set()
    qtbot.waitUntil(lambda: not scheduler._busy)


def test_json_errors_preserve_draft(scheduler, sequence):
    scheduler.load_json(json.dumps(sequence))
    original = scheduler.document_json()
    scheduler.json.setPlainText('{"type":"scan"}')
    scheduler._apply_json()
    assert scheduler.document_json() == original


def test_edit_add_wrap_move_remove(scheduler):
    scheduler.palette.setCurrentText("set")
    scheduler._add()
    scheduler.inspector.fields["device"].setCurrentText("samx.velocity")
    scheduler.inspector.fields["value"].value_edit.setText("2")
    scheduler._apply()
    scheduler.palette.setCurrentText("repeat")
    scheduler._wrap()
    assert scheduler.draft.node(scheduler._path)["count"] == 1
    assert scheduler.inspector.fields["count"].minimum() == 1
    scheduler._remove()
    assert scheduler.draft.document["root"]["children"] == []


def test_document_nested_scope_and_reordering(sequence):
    draft = SequenceDraft(sequence)
    path = ("body", "body", "children", 0)
    assert draft.variables(path) == ["position"]
    assert draft.variables(("body",)) == []
    assert draft.move(path, 1)[-1] == 1
    draft.remove(("body", "body"))
    assert draft.node(("body", "body"))["children"] == []


def test_value_reference_and_safe_literal(qtbot):
    widget = ValueInput({"ref": "pol"}, ["pol"])
    qtbot.addWidget(widget)
    assert widget.value() == {"ref": "pol"}
    widget.mode.setCurrentIndex(0)
    widget.value_edit.setText(json.dumps("'\n__import__('os')"))
    assert widget.value() == "'\n__import__('os')"


def test_close_stops_pending_edits(scheduler):
    scheduler.render_timer.start()
    scheduler.close()
    assert not scheduler.render_timer.isActive()


def test_named_scan_arguments_preserve_semantics(scheduler, sequence, qtbot):
    sequence["root"]["body"]["values"] = [0.1, 0.2]
    scheduler.load_json(json.dumps(sequence))
    path = ("body", "body", "children", 1)
    scheduler._rebuild_tree(path)
    inputs = scheduler.inspector.scan_arguments
    assert inputs.values() == ("time_scan", [1, 0.1], {})
    # Bind exposure time to the visible variable without rewriting positional arguments.
    editor = inputs.inputs[("arguments", "exp_time")]
    editor.setText("$position")
    editor.editingFinished.emit()
    scheduler._apply()
    scan = scheduler.draft.node(path)
    assert scan["positional"] == [1, 0.1]
    assert scan["arguments"]["exp_time"] == {"ref": "position"}
    scheduler.validate_sequence()
    qtbot.waitUntil(lambda: not scheduler._busy)
    assert "time_scan" in scheduler.description.toPlainText(), scheduler.message.text()


def test_execution_passes_transitive_definitions(scheduler, qtbot):
    definitions = [
        {
            "id": "inner",
            "version": 1,
            "parameters": {"type": "object", "additionalProperties": False},
            "body": {
                "id": "scan",
                "type": "scan_call",
                "name": "time_scan",
                "positional": [1, 0.1],
            },
        },
        {
            "id": "outer",
            "version": 1,
            "body": {
                "id": "call",
                "type": "component_call",
                "definition": {"id": "inner", "version": 1},
            },
        },
        {"id": "unused", "version": 1, "body": {"id": "empty", "type": "sequence", "children": []}},
    ]
    document = {
        "id": "reusable",
        "revision": 1,
        "root": {
            "id": "call",
            "type": "component_call",
            "definition": {"id": "outer", "version": 1},
        },
    }
    scheduler.client.proc.request_new.return_value = SimpleNamespace(
        done=False, state=SimpleNamespace(value="RUNNING"), error=None
    )
    scheduler.load_json(json.dumps(document), json.dumps(definitions))
    scheduler.execute_sequence()
    qtbot.waitUntil(lambda: not scheduler._busy)
    request = scheduler.client.proc.request_new.call_args
    assert request is not None, scheduler.message.text()
    definitions = request.args[1][0][1]
    assert [entry["id"] for entry in definitions] == ["inner", "outer"]


def test_invalid_reference_rejected_before_submission(scheduler, sequence, qtbot):
    sequence["root"]["body"]["body"]["children"][0]["value"] = {"ref": "missing"}
    scheduler.load_json(json.dumps(sequence))
    scheduler.execute_sequence()
    qtbot.waitUntil(lambda: not scheduler._busy)
    assert "missing" in scheduler.message.text()
    scheduler.client.proc.request_new.assert_not_called()


def test_repeat_zero_and_unknown_types_rejected(scheduler, sequence):
    sequence["root"]["count"] = 0
    with pytest.raises(ValueError):
        scheduler.load_json(json.dumps(sequence))
    sequence["root"]["count"] = 1
    sequence["type"] = "scan"
    with pytest.raises(ValueError):
        scheduler.load_json(json.dumps(sequence))


def test_description_capture(scheduler, qtbot):
    import os

    from bec_widgets.examples.scan_scheduler import example_sequence

    scheduler.load_json(example_sequence().model_dump_json())
    scheduler.resize(1400, 1000)
    scheduler._rebuild_tree(("body", "body", "children", 0))
    scheduler.show()
    scheduler.validate_sequence()
    qtbot.waitUntil(lambda: not scheduler._busy)
    assert scheduler.description.toPlainText()
    if filename := os.environ.get("BEC_SCHEDULER_SCREENSHOT"):
        qtbot.wait(100)
        assert scheduler.grab().save(filename)
    if filename := os.environ.get("BEC_SCHEDULER_PYTHON_SCREENSHOT"):
        scheduler.exports.setCurrentIndex(1)
        qtbot.wait(100)
        assert scheduler.grab().save(filename)


def test_nested_scan_inspector_capture(scheduler, qtbot):
    import os

    def scan(identity, exposure):
        return {
            "id": identity,
            "type": "scan_call",
            "name": "line_scan",
            "positional": ["samx", -1.0, 1.0],
            "arguments": {
                "steps": 30,
                "relative": False,
                "exp_time": exposure,
                "metadata": {"sample_name": "sample1"},
            },
        }

    document = {
        "id": "Position & exposure",
        "revision": 1,
        "root": {
            "id": "root",
            "type": "sequence",
            "children": [
                {
                    "id": "Position cycle",
                    "type": "repeat",
                    "count": 3,
                    "body": {
                        "id": "Position sweep",
                        "type": "for_each",
                        "variable": "position",
                        "values": [-1, 1],
                        "body": {
                            "id": "position_steps",
                            "type": "sequence",
                            "children": [
                                {
                                    "id": "Set position",
                                    "type": "set",
                                    "device": "samx",
                                    "value": {"ref": "position"},
                                    "wait": True,
                                },
                                {
                                    "id": "Repeat acquisition",
                                    "type": "repeat",
                                    "count": 2,
                                    "body": scan("Position line", 0.1),
                                },
                            ],
                        },
                    },
                },
                {
                    "id": "Exposure series",
                    "type": "for_each",
                    "variable": "exposure",
                    "values": [0.1, 0.2],
                    "body": {
                        "id": "Repeat exposure acquisition",
                        "type": "repeat",
                        "count": 2,
                        "body": scan("Exposure line", {"ref": "exposure"}),
                    },
                },
            ],
        },
    }
    scheduler.load_json(json.dumps(document))
    scheduler.resize(1250, 1050)
    scheduler._rebuild_tree(("children", 1, "body", "body"))
    scheduler.show()
    scheduler.validate_sequence()
    qtbot.waitUntil(lambda: not scheduler._busy)
    assert scheduler.description.toPlainText(), scheduler.message.text()
    assert "$exposure" in scheduler.inspector.scope.text()
    if filename := os.environ.get("BEC_SCHEDULER_REVISED_SCREENSHOT"):
        qtbot.wait(100)
        assert scheduler.grab().save(filename)


def test_scan_control_is_embedded_without_fetching_metadata(scheduler, sequence, monkeypatch):
    from bec_widgets.widgets.control.scan_control import ScanControl

    def unexpected_fetch(*args, **kwargs):
        raise AssertionError("Scan metadata is already subscribed")

    monkeypatch.setattr(scheduler.client.connector, "get", unexpected_fetch)
    scheduler.load_json(json.dumps(sequence))
    scheduler._rebuild_tree(("body", "body", "children", 1))
    editor = scheduler.inspector.scan_arguments
    assert isinstance(editor.control, ScanControl)
    assert editor.control.hide_scan_control_buttons
    assert not editor.control.scan_control_group.isEnabled()
    assert editor.values() == ("time_scan", [1, 0.1], {})


def test_native_restore_refreshes_bindings(scheduler, sequence, qtbot):
    scheduler.load_json(json.dumps(sequence))
    scheduler._rebuild_tree(("body", "body", "children", 1))
    editor = scheduler.inspector.scan_arguments
    binding = editor.inputs[("arguments", "exp_time")]
    binding.setText("$position")
    binding.editingFinished.emit()
    control = editor.control
    control._last_scan_parameters_received.emit(
        control._last_scan_fetch_generation, "time_scan", ([], {"points": 5, "interval": 0.2})
    )
    qtbot.waitUntil(lambda: not editor.refresh_timer.isActive())
    assert editor.values() == ("time_scan", [], {"points": 5, "interval": 0.2})
    assert binding.text() == "0.00 s"


def test_missing_scan_arguments_stay_missing(scheduler, sequence):
    scan = sequence["root"]["body"]["body"]["children"][1]
    scan["positional"] = []
    scheduler.load_json(json.dumps(sequence))
    scheduler._rebuild_tree(("body", "body", "children", 1))
    assert scheduler.inspector.scan_arguments.values() == ("time_scan", [], {})


def test_new_scan_uses_native_selector(scheduler, sequence):
    scan = sequence["root"]["body"]["body"]["children"][1]
    scheduler.load_json(json.dumps(sequence))
    scan = scheduler.draft.document["root"]["body"]["body"]["children"][1]
    scan["name"] = ""
    scan["positional"] = []
    scheduler._rebuild_tree(("body", "body", "children", 1))
    editor = scheduler.inspector.scan_arguments
    assert editor is not None
    editor.control.current_scan = "time_scan"
    editor._confirmed(0)
    assert editor.values()[0] == "time_scan"


def test_native_scan_device_bundles_preserve_positional_inputs(scheduler, sequence, qtbot):
    node = sequence["root"]["body"]["body"]["children"][1]
    node.update(
        name="line_scan",
        positional=["samx", -1, 1, "samy", -2, 2],
        arguments={"steps": 3, "relative": False},
    )
    scheduler.load_json(json.dumps(sequence))
    scheduler._rebuild_tree(("body", "body", "children", 1))
    editor = scheduler.inspector.scan_arguments
    assert editor.control.arg_box.count_arg_rows() == 2
    assert editor.values() == ("line_scan", node["positional"], node["arguments"])
    editor.control.arg_box.button_remove_bundle.click()
    qtbot.waitUntil(lambda: not editor.refresh_timer.isActive())
    name, positional, keywords = editor.values()
    assert name == "line_scan"
    assert positional == ["samx", -1, 1]
    assert keywords["steps"] == 3


def test_direct_variable_input_respects_scope_and_literal_bounds(scheduler, sequence):
    from qtpy.QtGui import QValidator

    sequence["root"]["body"]["body"]["children"][1].update(
        name="line_scan", positional=["samx", -1, 1], arguments={"steps": 3, "relative": False}
    )
    scheduler.load_json(json.dumps(sequence))
    scheduler._rebuild_tree(("body", "body", "children", 1))
    field = scheduler.inspector.scan_arguments.inputs[("arguments", "steps")]
    validator = field.validator()
    assert validator.validate("$position", 9)[0] == QValidator.State.Acceptable
    field.setText("$position")
    assert field.value() == {"ref": "position"}
    field.setText("$missing")
    with pytest.raises(ValueError, match="not available"):
        field.value()
    field.setText("0")
    with pytest.raises(ValueError, match="Invalid steps"):
        field.value()
    field.setText("5")
    assert field.value() == 5


def test_description_updates_without_preview_action(scheduler, sequence, qtbot):
    from qtpy.QtWidgets import QPushButton

    scheduler.load_json(json.dumps(sequence))
    qtbot.waitUntil(lambda: bool(scheduler.description.toPlainText()))
    assert scheduler.exports.count() == 3
    buttons = [button.text() for button in scheduler.findChildren(QPushButton)]
    assert "Execute" in buttons
    assert "Preview execution" not in buttons
    assert "Submit sequence" not in buttons
    scheduler.client.proc.request_new.assert_not_called()
