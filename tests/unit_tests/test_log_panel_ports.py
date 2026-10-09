# pylint: disable=missing-function-docstring,missing-module-docstring,redefined-outer-name
# pylint: disable=protected-access,unused-argument,invalid-name
import time

import pytest
from bec_lib.messages import LogMessage
from qtpy.QtWidgets import QApplication

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.utility.logpanel import log_ux_common as common
from bec_widgets.widgets.utility.logpanel.log_panel_demo import demo_entries
from bec_widgets.widgets.utility.logpanel.log_panel_qml import LogPanelQml
from bec_widgets.widgets.utility.logpanel.log_panel_qwidget import LogPanelQWidget
from bec_widgets.widgets.utility.logpanel.log_ux_common import LogEntry, LogPanelBackend
from bec_widgets.widgets.utility.logpanel.logpanel import BecLogsQueue

TRACE = """Traceback (most recent call last):
  File "/opt/bec/device_server.py", line 412, in _set_device
    status = obj.set(value)
ophyd.utils.errors.LimitError: position=12.5 not within limits (-10, 10)"""

NOW = 1_760_000_000.0


@pytest.fixture
def backend(qtbot):
    obj = LogPanelBackend(use_queue=False)
    yield obj
    obj.cleanup()
    obj.deleteLater()


def add(backend, *specs):
    backend.ingest([LogEntry(backend.model.next_seq(), *spec) for spec in specs])


def visible(backend):
    model = backend.model
    return [model.entry(row) for row in range(model.rowCount())]


def test_entry_summarises_tracebacks():
    entry = LogEntry(1, "error", NOW, "DeviceServer", TRACE)
    assert entry.level == "ERROR"
    assert entry.badge == "ERROR"
    assert entry.group == "error"
    assert entry.is_traceback
    assert entry.line_count == 4
    assert entry.summary.startswith("ophyd.utils.errors.LimitError")
    kinds = [kind for _, kind in entry.body_lines()]
    assert kinds == ["head", "file", "text", "exception"]


def test_entry_defaults_for_missing_fields():
    entry = LogEntry(1, "console_log", 0, None, "hello")
    assert entry.service == common.UNKNOWN_SERVICE
    assert entry.group == "debug"
    assert entry.ts > 0


def test_repeats_are_folded(backend):
    add(
        backend,
        ("WARNING", NOW, "DeviceServer", "Waiting for samy"),
        ("WARNING", NOW + 1, "DeviceServer", "Waiting for samy"),
        ("WARNING", NOW + 2, "DeviceServer", "Waiting for samy"),
        ("WARNING", NOW + 3, "ScanServer", "Waiting for samy"),
        ("WARNING", NOW + 100, "ScanServer", "Waiting for samy"),
    )
    rows = visible(backend)
    assert [row.count for row in rows] == [3, 1, 1]
    assert rows[0].ts == NOW + 2
    assert rows[0].first_ts == NOW


def test_folding_in_a_later_batch_updates_the_row(backend):
    add(backend, ("INFO", NOW, "ScanServer", "same"))
    changed = []
    backend.model.dataChanged.connect(lambda *args: changed.append(args))
    add(backend, ("INFO", NOW + 1, "ScanServer", "same"))
    assert backend.model.rowCount() == 1
    assert visible(backend)[0].count == 2
    assert changed


def test_level_service_and_time_filters(backend):
    add(
        backend,
        ("ERROR", time.time() - 7200, "DeviceServer", "old error"),
        ("WARNING", time.time() - 10, "ScanServer", "warn"),
        ("INFO", time.time() - 5, "ScanServer", "info"),
        ("DEBUG", time.time(), "SciHub", "debug"),
    )
    backend.toggleGroup("debug")
    assert [e.summary for e in visible(backend)] == ["old error", "warn", "info"]
    backend.soloService("ScanServer")
    assert [e.summary for e in visible(backend)] == ["warn", "info"]
    assert backend.state["servicesLabel"] == "ScanServer"
    # chips count everything that passes the other filters
    counts = {g["key"]: g["count"] for g in backend.state["groups"]}
    assert counts == {"error": 0, "warning": 1, "info": 1, "debug": 0}
    backend.allServices()
    backend.setSince("1h")
    assert [e.summary for e in visible(backend)] == ["warn", "info"]
    assert backend.state["filtered"]
    backend.resetFilters()
    assert backend.model.rowCount() == 4
    assert not backend.state["filtered"]


def test_hide_service_and_toggle_back(backend):
    add(backend, ("INFO", NOW, "A", "a"), ("INFO", NOW + 1, "B", "b"))
    backend.hideService("A")
    assert [e.service for e in visible(backend)] == ["B"]
    backend.toggleService("A")
    assert backend.model.services is None
    assert backend.model.rowCount() == 2


def test_search_filter_and_regex(backend):
    add(
        backend,
        ("INFO", NOW, "DeviceServer", "samx moved to 1.0"),
        ("INFO", NOW + 1, "DeviceServer", "samy moved to 2.0"),
        ("ERROR", NOW + 2, "DeviceServer", TRACE),
    )
    backend.setSearch("SAMX")
    backend._apply_search()
    assert [e.summary for e in visible(backend)] == ["samx moved to 1.0"]
    # matches inside the collapsed lines count too
    backend.setSearch("obj.set")
    backend._apply_search()
    assert [e.is_traceback for e in visible(backend)] == [True]
    backend.setRegex(True)
    backend.setSearch(r"sam[xy] moved")
    backend._apply_search()
    assert backend.model.rowCount() == 2
    backend.setSearch("sam[")
    backend._apply_search()
    assert backend.state["regexError"]
    assert backend.model.rowCount() == 3  # an invalid pattern filters nothing


def test_highlight_mode_navigates_matches(backend, qtbot):
    add(
        backend,
        *[("INFO", NOW + i, "S", f"line {i} {'hit' if i % 3 == 0 else ''}") for i in range(10)],
    )
    backend.setSearchMode("highlight")
    backend.setSearch("hit")
    backend._apply_search()
    assert backend.model.rowCount() == 10
    assert backend.state["matchCount"] == 4
    assert backend.model.matcher.spans("a hit and hit") == [(2, 3), (10, 3)]
    with qtbot.waitSignal(backend.reveal_row) as blocker:
        backend.nextMatch()
    assert blocker.args == [0]
    assert not backend.follow
    backend.prevMatch()
    assert backend.state["matchPos"] == 4
    assert backend.model.current_row() == 9


def test_pause_buffers_and_resume_flushes(backend):
    add(backend, ("INFO", NOW, "S", "a"))
    backend.togglePause()
    add(backend, ("INFO", NOW + 1, "S", "b"), ("INFO", NOW + 2, "S", "c"))
    assert backend.model.rowCount() == 1
    assert backend.state["pending"] == 2
    backend.togglePause()
    assert backend.model.rowCount() == 3
    assert backend.state["pending"] == 0


def test_follow_counts_new_rows_below(backend, qtbot):
    add(backend, ("INFO", NOW, "S", "a"))
    with qtbot.waitSignal(backend.scroll_to_end):
        add(backend, ("INFO", NOW + 1, "S", "b"))
    backend.setFollow(False)
    add(backend, ("INFO", NOW + 2, "S", "c"), ("INFO", NOW + 3, "S", "d"))
    assert backend.state["newBelow"] == 2
    backend.jumpToLatest()
    assert backend.follow
    assert backend.state["newBelow"] == 0


def test_trim_keeps_counts_consistent(qtbot):
    backend = LogPanelBackend(use_queue=False, max_entries=100)
    backend.model.TRIM_CHUNK = 10
    add(
        backend,
        *[("INFO" if i % 2 else "WARNING", NOW + i, f"S{i % 3}", f"m{i}") for i in range(150)],
    )
    model = backend.model
    assert model.total == 100
    assert model.entries[0].summary == "m50"
    assert sum(model.group_counts.values()) == 100
    assert sum(model.service_counts.values()) == 100
    assert model.rowCount() == 100
    backend.cleanup()


def test_expand_and_copy(backend, tmp_path):
    add(backend, ("ERROR", NOW, "DeviceServer", TRACE), ("INFO", NOW + 1, "S", "single"))
    backend.toggleExpanded(1)
    assert not backend.model.expanded  # single-line rows do not expand
    backend.toggleExpanded(0)
    model = backend.model
    index = model.index(0, 0)
    assert model.data(index, model.roleNames_ids()["expanded"]) is True
    lines = model.data(index, model.roleNames_ids()["bodyLines"])
    assert lines[-1]["kind"] == "exception"
    backend.copyRow(0)
    assert "[ERROR] DeviceServer: Traceback" in QApplication.clipboard().text()
    backend.copyMessage(1)
    assert QApplication.clipboard().text() == "single"
    path = tmp_path / "logs.log"
    backend.export_to(path)
    assert path.read_text().count("\n") >= 2


def test_time_modes():
    assert common.format_relative(100, now=101) == "now"
    assert common.format_relative(100, now=160) == "1 min ago"
    assert common.format_relative(100, now=100 + 7300) == "2 h ago"
    assert len(common.format_clock(time.time())) == len("12:00:00.000")


def test_queue_feeds_the_backend(qtbot, mocked_client, monkeypatch):
    msg = LogMessage(
        metadata={},
        log_type="warning",
        log_msg={
            "text": "x",
            "record": {"time": {"timestamp": NOW, "repr": ""}, "message": "from redis"},
            "service_name": "ScanServer",
        },
    )
    monkeypatch.setattr(mocked_client.connector, "xread", lambda *_, **__: [{"data": msg}])
    backend = LogPanelBackend(use_queue=True)
    assert [e.summary for e in visible(backend)] == ["from redis"]
    queue = BecLogsQueue.instance()
    queue._incoming.append(msg.model_copy(update={"log_type": "error"}))
    queue._proc_update()
    assert [e.level for e in visible(backend)] == ["WARNING", "ERROR"]
    backend.cleanup()
    assert BecLogsQueue._instance is None


@pytest.fixture(params=["qwidget", "qml"])
def panel(request, qtbot, mocked_client):
    cls = LogPanelQWidget if request.param == "qwidget" else LogPanelQml
    backend = LogPanelBackend(use_queue=False)
    backend.ingest(demo_entries(backend.model, 200))
    widget = create_widget(qtbot, cls, backend=backend)
    backend.setParent(widget)
    widget.resize(1000, 500)
    yield widget


def test_panel_renders_and_follows_state(panel, qtbot):
    backend = panel.backend
    assert backend.model.rowCount() > 0
    backend.toggleGroup("info")
    qtbot.wait(20)
    assert all(e.group != "info" for e in visible(backend))
    rows = [r for r in range(backend.model.rowCount()) if backend.model.entry(r).line_count > 1]
    backend.toggleExpanded(rows[0])
    qtbot.wait(20)
    assert panel.grab().width() == 1000
    if isinstance(panel, LogPanelQWidget):
        assert not panel.view.uniformRowHeights()
        assert panel._chips["info"].isChecked() is False
        backend.toggleExpanded(rows[0])
        assert panel.view.uniformRowHeights()
    else:
        assert panel.view.rootObject() is not None
        assert not panel.view.errors()


def test_panel_search_highlight_and_jump(panel, qtbot):
    backend = panel.backend
    backend.setSearchMode("highlight")
    backend.setSearch("samx")
    backend._apply_search()
    backend.nextMatch()
    qtbot.wait(20)
    assert backend.model.current_row() >= 0
    assert not backend.state["follow"]
    backend.jumpToLatest()
    qtbot.wait(20)
    assert backend.state["follow"]


def test_qwidget_toolbar_drives_backend(qtbot, mocked_client):
    backend = LogPanelBackend(use_queue=False)
    add(backend, ("ERROR", NOW, "A", "a"), ("INFO", NOW + 1, "B", "b"))
    panel = create_widget(qtbot, LogPanelQWidget, backend=backend)
    backend.setParent(panel)
    panel._chips["error"].click()
    assert backend.model.groups == {"warning", "info", "debug"}
    panel.mode_buttons["highlight"].click()
    assert backend.state["searchMode"] == "highlight"
    panel.regex_button.click()
    assert backend.state["regex"]
    panel.live_pill.clicked.emit()
    assert backend.paused
    assert panel.live_pill.text == "Paused"
    panel._fill_service_menu()
    assert len([a for a in panel.service_menu.actions() if a.isCheckable()]) == 2
