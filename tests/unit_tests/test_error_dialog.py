# pylint: disable=missing-function-docstring, redefined-outer-name, protected-access
import traceback

import pytest
from qtpy.QtWidgets import QApplication

from bec_widgets.utils.error_dialog import error_dialog_common as common
from bec_widgets.utils.error_dialog import error_dialog_registry as registry
from bec_widgets.utils.error_dialog.error_dialog_common import (
    ErrorDialogController,
    classify_path,
    parse_traceback,
    short_path,
)
from bec_widgets.utils.error_dialog.error_dialog_demo import ErrorDemo, check_limits
from bec_widgets.utils.error_popups import ErrorPopupUtility


def _format(func) -> str:
    try:
        func()
    except Exception as exc:  # pylint: disable=broad-except
        return "".join(traceback.format_exception(exc))
    raise AssertionError("no error raised")


def _limit_error():
    check_limits("samx", 12.5, (-10, 10))


def _chained():
    try:
        {}["bpm4i"]
    except KeyError as exc:
        raise RuntimeError("curve missing\nsecond line") from exc


def _json_error():
    import json  # pylint: disable=import-outside-toplevel

    json.loads("{bad")


@pytest.fixture(autouse=True)
def reset_dialogs(monkeypatch):
    monkeypatch.delenv("BEC_ERROR_DIALOG", raising=False)
    yield
    registry.reset_error_dialogs()
    QApplication.processEvents()


def test_parse_traceback_chain_and_carets():
    text = _format(_chained)
    exceptions = parse_traceback(text)
    assert [e.short_type for e in exceptions] == ["KeyError", "RuntimeError"]
    assert exceptions[0].relation == "Caused by"
    assert exceptions[1].message == "curve missing\nsecond line"
    frame = exceptions[0].frames[-1]
    assert frame.func == "_chained"
    assert "^" not in frame.code and frame.code


def test_parse_traceback_while_handling():
    text = "\n".join(
        [
            "Traceback (most recent call last):",
            '  File "/x/a.py", line 3, in f',
            "    g()",
            "KeyError: 'a'",
            "",
            "During handling of the above exception, another exception occurred:",
            "",
            "Traceback (most recent call last):",
            '  File "/x/a.py", line 5, in f',
            "    raise ValueError",
            "ValueError",
        ]
    )
    exceptions = parse_traceback(text)
    assert exceptions[0].relation == "While handling"
    assert exceptions[1].type == "ValueError" and exceptions[1].message == ""


def test_parse_plain_text():
    exceptions = parse_traceback("something went wrong")
    assert len(exceptions) == 1
    assert exceptions[0].type == "Error"
    assert exceptions[0].message == "something went wrong"


@pytest.mark.parametrize(
    "path, kind, short",
    [
        ("/usr/lib/python3.13/json/decoder.py", "library", "json/decoder.py"),
        ("/venv/lib/python3.13/site-packages/pydantic/main.py", "library", "pydantic/main.py"),
        ("/venv/lib/python3.13/site-packages/bec_lib/client.py", "bec", "bec_lib/client.py"),
        ("/home/u/bec_widgets/bec_widgets/utils/x.py", "bec", "bec_widgets/utils/x.py"),
        ("<frozen runpy>", "library", "<frozen runpy>"),
    ],
)
def test_classify_and_shorten(path, kind, short):
    assert classify_path(path) == kind
    assert short_path(path) == short


def test_short_path_uses_package_root():
    assert short_path(common.__file__) == "bec_widgets/utils/error_dialog/error_dialog_common.py"


def test_controller_folds_repeats_and_follows_newest(qtbot):
    controller = ErrorDialogController()
    first = controller.add_error("Method error", _format(_limit_error), "A.slot")
    again = controller.add_error("Method error", _format(_limit_error), "A.slot")
    assert first == again
    assert controller.current.count == 2
    other = controller.add_error("Method error", _format(_chained), "B.slot")
    assert controller.current.id == other
    state = controller.view_state()
    assert state["count"] == 2
    assert [row["type"] for row in state["errors"]] == ["RuntimeError", "LimitError"]


def test_controller_keeps_selection_when_reading_older(qtbot):
    controller = ErrorDialogController()
    old = controller.add_error("Method error", _format(_limit_error))
    controller.add_error("Method error", _format(_chained))
    controller.select(old)
    new = controller.add_error("Method error", _format(_json_error))
    assert controller.current.id == old
    unseen = [row for row in controller.view_state()["errors"] if not row["seen"]]
    assert [row["id"] for row in unseen] == [new]


def test_controller_dismiss_step_clear(qtbot):
    controller = ErrorDialogController()
    ids = [
        controller.add_error("Method error", _format(f))
        for f in (_limit_error, _chained, _json_error)
    ]
    assert controller.current.id == ids[2]
    controller.step(1)
    assert controller.current.id == ids[1]
    controller.dismiss()
    assert controller.current.id == ids[0]
    assert len(controller.errors) == 2
    controller.clear()
    assert controller.current is None
    assert controller.view_state()["current"] is None


def test_rows_fold_library_frames(qtbot):
    controller = ErrorDialogController()
    controller.add_error("Method error", _format(_json_error))
    rows = controller.view_state()["current"]["rows"]
    assert rows[0]["kind"] == "section" and rows[0]["label"] == "Raised"
    groups = [row for row in rows if row["kind"] == "group"]
    assert groups and "json" in groups[0]["label"]
    assert not any(row["kind"] == "frame" and not row["bec"] for row in rows)
    controller.toggle_group(groups[0]["key"])
    rows = controller.view_state()["current"]["rows"]
    assert any(row["kind"] == "frame" and not row["bec"] for row in rows)
    controller.set_show_library(True)
    rows = controller.view_state()["current"]["rows"]
    assert not any(row["kind"] == "group" for row in rows)


def test_focus_frame_and_context(qtbot):
    controller = ErrorDialogController()
    controller.add_error("Method error", _format(_limit_error))
    location = controller.view_state()["current"]["location"]
    assert location["func"] == "check_limits"
    assert any(row["current"] and "raise LimitError" in row["text"] for row in location["context"])
    frame = next(r for r in controller.view_state()["current"]["rows"] if r["kind"] == "frame")
    controller.toggle_frame(frame["key"])
    expanded = next(
        r for r in controller.view_state()["current"]["rows"] if r["key"] == frame["key"]
    )
    assert expanded["expanded"] and expanded["context"]


def test_report_and_issue_url(qtbot):
    controller = ErrorDialogController()
    controller.add_error("Method error", _format(_limit_error), "Demo.slot")
    report = controller.copy_report()
    assert "LimitError: Target 12.5" in report.splitlines()[0]
    assert "Raised in: Demo.slot" in report and "bec_widgets" in report
    url = controller.current.issue_url()
    assert url.startswith(common.ISSUE_URL)
    assert len(url) < 12000


@pytest.mark.parametrize("ui", ["qwidget", "qml"])
def test_safeslot_routes_to_new_dialog(qtbot, monkeypatch, ui):
    monkeypatch.setenv("BEC_ERROR_DIALOG", ui)
    demo = ErrorDemo()
    qtbot.addWidget(demo)
    utility = ErrorPopupUtility()
    with qtbot.assertNotEmitted(utility.error_occurred):
        with qtbot.waitSignal(utility.error_reported, timeout=1000):
            demo.on_setpoint_change()
    qtbot.waitUntil(lambda: ui in registry._DIALOGS)
    dialog = registry._DIALOGS[ui]
    assert dialog.isVisible()
    assert dialog.controller.current.source == "ErrorDemo.on_setpoint_change"
    demo.burst()
    qtbot.waitUntil(lambda: len(dialog.controller.errors) == 2)
    assert dialog.controller.current.count == 7
    assert dialog.width() >= dialog.MIN_SIZE[0] and dialog.height() >= dialog.MIN_SIZE[1]
    dialog.close()
    assert dialog.controller.errors == []


def test_qwidget_dialog_renders_rows(qtbot):
    from bec_widgets.utils.error_dialog.error_dialog_qwidget import (  # pylint: disable=import-outside-toplevel
        ErrorDialogWidget,
    )

    dialog = ErrorDialogWidget()
    qtbot.addWidget(dialog)
    dialog.show_error("Method error", _format(_chained), "X.y")
    assert dialog.type_label.text() == "RuntimeError"
    assert dialog.message_label.text() == "curve missing"
    assert dialog.message_more.isVisible()
    assert not dialog.sidebar.isVisible()
    dialog.show_error("Method error", _format(_limit_error), "X.z")
    assert dialog.sidebar.isVisible() and dialog.pager_label.text() == "1 of 2"
    dialog.controller.set_mode("raw")
    assert dialog.stack.currentIndex() == 1
    assert "LimitError" in dialog.raw_text.toPlainText()
    dialog.cleanup()
    dialog.close()


def test_legacy_popup_unchanged_without_env(qtbot):
    utility = ErrorPopupUtility()
    shown = []
    utility.error_occurred.disconnect(utility.show_error_message)
    utility.error_occurred.connect(lambda *args: shown.append(args))
    try:
        demo = ErrorDemo()
        qtbot.addWidget(demo)
        with qtbot.assertNotEmitted(utility.error_reported):
            demo.on_setpoint_change()
        assert shown and shown[0][0] == "Method error"
    finally:
        utility.error_occurred.disconnect()
        utility.error_occurred.connect(utility.show_error_message)
