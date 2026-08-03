# pylint: disable=no-member
# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

from collections import deque
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from bec_lib.logger import LogLevel
from bec_lib.messages import LogMessage
from qtpy.QtCore import QDateTime, Qt

from bec_widgets.utils.colors import apply_theme, get_accent_colors, get_theme_name
from bec_widgets.widgets.utility.logpanel.logpanel import LogPanel, TimestampUpdate

from .client_mocks import mocked_client

TEST_LOG_MESSAGES = [
    {"data": msg}
    for msg in [
        LogMessage(
            metadata={},
            log_type="debug",
            log_msg={
                "text": "datetime | debug | test log message",
                "record": {
                    "time": {"timestamp": 123456789.000, "repr": "2025-01-01 00:00:01"},
                    "message": "test debug message abcd",
                    "function": "_debug",
                },
                "service_name": "ScanServer",
            },
        ),
        LogMessage(
            metadata={},
            log_type="info",
            log_msg={
                "text": "datetime | info | test info log message",
                "record": {
                    "time": {"timestamp": 123456789.007, "repr": "2025-01-01 00:00:02"},
                    "message": "test info message efgh",
                    "function": "_info",
                },
                "service_name": "DeviceServer",
            },
        ),
        LogMessage(
            metadata={},
            log_type="success",
            log_msg={
                "text": "datetime | success | test log message",
                "record": {
                    "time": {"timestamp": 123456789.012, "repr": "2025-01-01 00:00:03"},
                    "message": "test success message ijkl",
                    "function": "_success",
                },
                "service_name": "ScanServer",
            },
        ),
    ]
]


@pytest.fixture
def log_panel(qtbot, mocked_client, monkeypatch):
    monkeypatch.setattr(mocked_client.connector, "xread", lambda *_, **__: TEST_LOG_MESSAGES)
    widget = LogPanel()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget._model.log_queue.cleanup()
    widget.close()
    widget.deleteLater()
    qtbot.wait(100)


def test_log_panel_init(qtbot, log_panel: LogPanel):
    assert log_panel


def test_log_panel_filters(qtbot, log_panel: LogPanel):
    assert log_panel._proxy.rowCount() == 3
    # Service filter
    log_panel._update_service_filter({"DeviceServer"})
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 1, timeout=200)
    log_panel._update_service_filter(set())  # empty include-list shows nothing
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 0, timeout=200)
    log_panel._update_service_filter(None)  # no service filter shows everything
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 3, timeout=200)
    # Text filter
    log_panel._proxy.update_filter_text("efgh")
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 1, timeout=200)
    log_panel._proxy.update_filter_text("")
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 3, timeout=200)
    # Time filter
    log_panel._proxy.update_timestamp(
        TimestampUpdate(value=QDateTime.fromMSecsSinceEpoch(123456789004), update_type="start")
    )
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 2, timeout=200)
    log_panel._proxy.update_timestamp(
        TimestampUpdate(value=QDateTime.fromMSecsSinceEpoch(123456789009), update_type="end")
    )
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 1, timeout=200)
    log_panel._proxy.update_timestamp(TimestampUpdate(value=None, update_type="start"))
    log_panel._proxy.update_timestamp(TimestampUpdate(value=None, update_type="end"))
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 3, timeout=200)
    # Level filter
    log_panel._proxy.update_level_filter(LogLevel.SUCCESS)
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 1, timeout=200)
    log_panel._proxy.update_level_filter(None)
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 3, timeout=200)


def test_log_panel_update(qtbot, log_panel: LogPanel):
    log_panel._model.log_queue._incoming.append(
        LogMessage(
            metadata={},
            log_type="error",
            log_msg={
                "text": "datetime | error | test log message",
                "record": {
                    "time": {"timestamp": 123456789.015, "repr": "2025-01-01 00:00:03"},
                    "message": "test error message xyz",
                    "function": "_error",
                },
                "service_name": "ScanServer",
            },
        )
    )
    # emit through the timer: _proc_update verifies its sender and skips plain calls
    log_panel._model.log_queue._update_timer.timeout.emit()
    qtbot.waitUntil(lambda: log_panel._model.rowCount() == 4, timeout=500)


def make_log_msg(i: int, log_type: str = "info", service: str = "ScanServer") -> LogMessage:
    return LogMessage(
        metadata={},
        log_type=log_type,
        log_msg={
            "text": f"datetime | {log_type} | m{i}",
            "record": {
                "time": {"timestamp": 123456789.100 + i, "repr": "2025-01-01 00:00:04"},
                "message": f"m{i}",
                "function": "_test",
            },
            "service_name": service,
        },
    )


def _feed(log_panel: LogPanel, messages: list[LogMessage]):
    queue = log_panel._model.log_queue
    queue._incoming.extend(messages)
    # emit through the timer so _proc_update's verify_sender check passes (a plain
    # method call is skipped with "Sender is None")
    queue._update_timer.timeout.emit()


def _patched_const(monkeypatch, **overrides):
    import bec_widgets.widgets.utility.logpanel.logpanel as lp

    values = {
        "FUZZ_THRESHOLD": lp._CONST.FUZZ_THRESHOLD,
        "UPDATE_INTERVAL_MS": lp._CONST.UPDATE_INTERVAL_MS,
        "TRIM_CHUNK": lp._CONST.TRIM_CHUNK,
        "headers": lp._CONST.headers,
    }
    values.update(overrides)
    monkeypatch.setattr(lp, "_CONST", SimpleNamespace(**values))


def test_log_panel_appends_incrementally_and_filters_new_rows(qtbot, log_panel: LogPanel):
    log_panel._proxy.update_level_filter(LogLevel.WARNING)
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 0, timeout=200)
    with qtbot.waitSignal(log_panel._model.rowsInserted, timeout=500) as blocker:
        _feed(log_panel, [make_log_msg(0, "warning"), make_log_msg(1, "debug")])
    assert blocker.args[1:] == [3, 4]  # one contiguous append of both rows
    assert log_panel._model.rowCount() == 5
    # the proxy evaluated only the new rows: exactly the warning one is shown
    assert log_panel._proxy.rowCount() == 1
    assert log_panel._proxy.index(0, 3).data() == "m0"


def test_log_panel_trims_in_chunks(qtbot, log_panel: LogPanel, monkeypatch):
    _patched_const(monkeypatch, TRIM_CHUNK=3)
    monkeypatch.setattr(log_panel._model, "_max_length", 6)
    _feed(log_panel, [make_log_msg(i) for i in range(4)])
    # overflow 1 < TRIM_CHUNK: buffer transiently exceeds max_length
    assert log_panel._model.rowCount() == 7
    with qtbot.waitSignal(log_panel._model.rowsRemoved, timeout=500) as blocker:
        _feed(log_panel, [make_log_msg(i) for i in range(4, 8)])
    assert blocker.args[1:] == [0, 4]  # overflow of 5 trimmed from the top
    assert log_panel._model.rowCount() == 6
    assert log_panel._model.record(0).message == "m2"
    assert log_panel._model.record(5).message == "m7"


def test_log_panel_huge_batch_resets_to_tail(qtbot, log_panel: LogPanel, monkeypatch):
    monkeypatch.setattr(log_panel._model, "_max_length", 4)
    with qtbot.waitSignal(log_panel._model.modelReset, timeout=500):
        _feed(log_panel, [make_log_msg(i) for i in range(6)])
    assert log_panel._model.rowCount() == 4
    assert log_panel._model.record(0).message == "m2"
    assert log_panel._model.record(3).message == "m5"


def test_log_panel_trim_anchors_scroll_position(qtbot, log_panel: LogPanel, monkeypatch):
    _patched_const(monkeypatch, TRIM_CHUNK=5)
    monkeypatch.setattr(log_panel._model, "_max_length", 20)
    log_panel.resize(600, 300)
    log_panel.show()
    qtbot.waitExposed(log_panel)
    _feed(log_panel, [make_log_msg(i) for i in range(17)])
    assert log_panel._model.rowCount() == 20
    scrollbar = log_panel._table.verticalScrollBar()
    qtbot.waitUntil(lambda: scrollbar.maximum() >= 5, timeout=500)
    scrollbar.setValue(5)
    _feed(log_panel, [make_log_msg(i) for i in range(17, 22)])  # overflow 5 -> trim 5
    assert scrollbar.value() == 0  # shifted by the removed count, content stays anchored


def test_log_panel_follows_tail_when_pinned_to_bottom(qtbot, log_panel: LogPanel, monkeypatch):
    _patched_const(monkeypatch, TRIM_CHUNK=5)
    monkeypatch.setattr(log_panel._model, "_max_length", 20)
    log_panel.resize(600, 300)
    log_panel.show()
    qtbot.waitExposed(log_panel)
    _feed(log_panel, [make_log_msg(i) for i in range(17)])
    scrollbar = log_panel._table.verticalScrollBar()
    qtbot.waitUntil(lambda: scrollbar.maximum() >= 5, timeout=500)
    log_panel._table.scrollToBottom()
    for start in range(17, 37, 5):  # several trim cycles at steady state
        _feed(log_panel, [make_log_msg(i) for i in range(start, start + 5)])
        assert scrollbar.value() == scrollbar.maximum()  # still tailing the newest logs
    last_visible = log_panel._proxy.index(log_panel._proxy.rowCount() - 1, 3).data()
    assert last_visible == "m36"


def test_log_panel_survives_malformed_messages(qtbot, log_panel: LogPanel):
    # shapes that pass LogMessage validation (log_msg is `dict | str`, no inner schema)
    # but used to break record flattening, filtering, or painting
    poison = [
        LogMessage(metadata={}, log_type="info", log_msg={"record": "oops"}),
        LogMessage(metadata={}, log_type="info", log_msg={"record": {"message": 5, "time": 1.0}}),
        LogMessage(metadata={}, log_type="console_log", log_msg="plain string payload"),
        LogMessage(
            metadata={},
            log_type="info",
            log_msg={
                "service_name": ["not", "a", "string"],
                "record": {"message": {"nested": 1}, "time": {"timestamp": "abc", "repr": 7}},
            },
        ),
    ]
    # activate every filter type so filterAcceptsRow runs all comparisons on the new rows
    log_panel._proxy.update_timestamp(
        TimestampUpdate(value=QDateTime.fromMSecsSinceEpoch(0), update_type="start")
    )
    log_panel._proxy.update_service_filter({"ScanServer"})
    log_panel._proxy.update_filter_text("payload")
    _feed(log_panel, poison)
    assert log_panel._model.rowCount() == 7  # the whole batch landed, nothing raised
    # a panel constructed after the poison entered the shared history must still build
    second_panel = LogPanel()
    qtbot.addWidget(second_panel)
    assert second_panel._model.rowCount() == 7
    second_panel.close()


def test_log_panel_close_detaches_from_queue(qtbot, log_panel: LogPanel):
    queue = log_panel._model.log_queue
    log_panel.close()
    _feed(log_panel, [make_log_msg(0)])
    assert log_panel._model.rowCount() == 3  # closed panel no longer receives updates
    assert len(queue) == 4  # the shared history still ingests


def test_direct_queue_construction_registers_singleton(qtbot, mocked_client, monkeypatch):
    from bec_widgets.widgets.utility.logpanel.logpanel import BecLogsQueue

    monkeypatch.setattr(mocked_client.connector, "xread", lambda *_, **__: TEST_LOG_MESSAGES)
    queue = BecLogsQueue(None, client=mocked_client)
    try:
        assert BecLogsQueue._instance is queue
        assert BecLogsQueue.instance() is queue
        with pytest.raises(RuntimeError):
            BecLogsQueue(None, client=mocked_client)
    finally:
        queue.cleanup()


def test_log_panel_copy_selection(qtbot, log_panel: LogPanel):
    from qtpy.QtWidgets import QApplication

    log_panel._table.selectAll()
    log_panel._copy_selection()
    copied = QApplication.clipboard().text().splitlines()
    assert len(copied) == 3
    assert "test debug message abcd" in copied[0]
    assert "[DEBUG]" in copied[0] and "ScanServer" in copied[0]


def test_log_panel_detail_pane(qtbot, log_panel: LogPanel):
    assert log_panel._detail.isHidden()
    log_panel._table.setCurrentIndex(log_panel._proxy.index(1, 0))
    log_panel._show_details()
    assert not log_panel._detail.isHidden()
    assert log_panel._detail_text.toPlainText() == "test info message efgh"
    assert "INFO" in log_panel._detail_header.text()
    # selection changes update the open pane (sync is deferred by one event-loop turn)
    log_panel._table.setCurrentIndex(log_panel._proxy.index(2, 0))
    qtbot.waitUntil(
        lambda: log_panel._detail_text.toPlainText() == "test success message ijkl", timeout=500
    )
    log_panel._hide_details()
    assert log_panel._detail.isHidden()


def test_log_panel_clear_view_keeps_history(qtbot, log_panel: LogPanel):
    queue = log_panel._model.log_queue
    log_panel._clear_view()
    assert log_panel._model.rowCount() == 0
    assert len(queue) == 3  # shared history untouched
    _feed(log_panel, [make_log_msg(0)])
    assert log_panel._model.rowCount() == 1  # new logs keep arriving after a clear


def test_log_panel_toolbar_service_selection(qtbot, log_panel: LogPanel):
    toolbar = log_panel._toolbar
    toolbar._known_services = {"ScanServer", "DeviceServer"}
    toolbar.set_service_selection({"DeviceServer"})
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 1, timeout=200)
    assert toolbar.service_button.text() == "DeviceServer"
    toolbar.hide_service("DeviceServer")
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 0, timeout=200)
    assert toolbar.service_button.text() == "No services"
    # re-checking every known service through the menu collapses to the unfiltered state
    toolbar.set_service_selection({"ScanServer"})
    toolbar._on_service_toggled("DeviceServer", True)
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 3, timeout=200)
    assert toolbar.service_button.text() == "All services"
    assert toolbar._checked_services is None


def test_log_panel_toolbar_level_default_and_preset(qtbot, log_panel: LogPanel):
    box = log_panel._toolbar.filter_level_dropdown
    assert box.currentIndex() == 0
    assert box.currentText() == "All levels"
    assert box.itemData(0) is None
    assert "CONSOLE_LOG" not in [box.itemText(i) for i in range(box.count())]
    log_panel._toolbar.set_level(LogLevel.SUCCESS)
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 1, timeout=200)
    log_panel._toolbar.set_level(None)
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 3, timeout=200)


def test_log_panel_search_debounce_and_match_count(qtbot, log_panel: LogPanel):
    toolbar = log_panel._toolbar
    toolbar.search_textbox.setText("efgh")
    assert log_panel._proxy.rowCount() == 3  # not yet applied - debounced
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 1, timeout=1000)
    assert toolbar.match_label.text() == "1 / 3"
    toolbar.search_textbox.clear()  # clearing applies instantly
    assert log_panel._proxy.rowCount() == 3
    assert toolbar.match_label.text() == "3"


def test_log_panel_jump_button_counts_new_rows(qtbot, log_panel: LogPanel, monkeypatch):
    monkeypatch.setattr(log_panel._model, "_max_length", 50)
    log_panel.resize(600, 300)
    log_panel.show()
    qtbot.waitExposed(log_panel)
    _feed(log_panel, [make_log_msg(i) for i in range(30)])
    table = log_panel._table
    qtbot.waitUntil(lambda: table.verticalScrollBar().maximum() > 0, timeout=500)
    table.verticalScrollBar().setValue(0)  # scroll up to read history
    _feed(log_panel, [make_log_msg(i) for i in range(30, 35)])
    assert table._jump_button.isVisible()
    assert table._jump_button.text() == "5 new"
    table._jump_button.click()
    qtbot.waitUntil(lambda: not table._jump_button.isVisible(), timeout=500)
    scrollbar = table.verticalScrollBar()
    assert scrollbar.value() == scrollbar.maximum()


def test_log_panel_constructor_service_filter_stays_applied(qtbot, mocked_client, monkeypatch):
    monkeypatch.setattr(mocked_client.connector, "xread", lambda *_, **__: TEST_LOG_MESSAGES)
    widget = LogPanel(service_filter={"DeviceServer"})
    qtbot.addWidget(widget)
    try:
        assert widget._proxy.rowCount() == 1  # only the DeviceServer row
        assert widget._toolbar.service_button.text() == "DeviceServer"
    finally:
        widget._model.log_queue.cleanup()


def test_log_panel_context_service_filters_on_fresh_panel(qtbot, log_panel: LogPanel):
    # neither action may depend on the service menu having been opened before
    log_panel._filter_service_only("DeviceServer")
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 1, timeout=200)
    log_panel._toolbar.set_service_selection(None)
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 3, timeout=200)
    log_panel._filter_service_hide("ScanServer")
    qtbot.waitUntil(lambda: log_panel._proxy.rowCount() == 1, timeout=200)
    assert log_panel._proxy.index(0, 2).data() == "DeviceServer"


def test_log_panel_filter_change_does_not_show_jump_pill(qtbot, log_panel: LogPanel, monkeypatch):
    monkeypatch.setattr(log_panel._model, "_max_length", 100)
    log_panel.resize(600, 300)
    log_panel.show()
    qtbot.waitExposed(log_panel)
    _feed(log_panel, [make_log_msg(i) for i in range(40)])
    table = log_panel._table
    qtbot.waitUntil(lambda: table.verticalScrollBar().maximum() > 0, timeout=500)
    table.verticalScrollBar().setValue(0)
    log_panel._proxy.update_filter_text("m1")  # tighten, then relax: no new logs arrived
    log_panel._proxy.update_filter_text("")
    assert not table._jump_button.isVisible()
    assert table._new_below == 0


def test_log_panel_filter_tighten_does_not_leak_scroll_latch(qtbot, log_panel, monkeypatch):
    monkeypatch.setattr(log_panel._model, "_max_length", 100)
    log_panel.resize(600, 300)
    log_panel.show()
    qtbot.waitExposed(log_panel)
    _feed(log_panel, [make_log_msg(i) for i in range(40)])
    table = log_panel._table
    qtbot.waitUntil(lambda: table.verticalScrollBar().maximum() > 0, timeout=500)
    table.scrollToBottom()
    log_panel._proxy.update_filter_text("m")  # removal-only cycle while pinned to bottom
    table.verticalScrollBar().setValue(0)  # then scroll up to read
    _feed(log_panel, [make_log_msg(99)])  # a new matching log must not yank the view
    assert table.verticalScrollBar().value() == 0


def test_log_panel_detail_pane_freezes_when_record_trimmed(qtbot, log_panel, monkeypatch):
    _patched_const(monkeypatch, TRIM_CHUNK=3)
    monkeypatch.setattr(log_panel._model, "_max_length", 8)
    log_panel._table.setCurrentIndex(log_panel._proxy.index(0, 0))
    log_panel._show_details()
    assert log_panel._detail_text.toPlainText() == "test debug message abcd"
    _feed(log_panel, [make_log_msg(i) for i in range(4)])  # append-only, 7 rows
    _feed(log_panel, [make_log_msg(i) for i in range(4, 8)])  # trims the shown record away
    qtbot.wait(100)  # let the deferred selection sync run
    assert log_panel._detail_text.toPlainText() == "test debug message abcd"
    assert "(no longer in buffer)" in log_panel._detail_header.text()
    # an explicit click follows the selection again, out of the freeze
    log_panel._table.setCurrentIndex(log_panel._proxy.index(0, 0))
    log_panel._on_row_clicked()
    assert log_panel._detail_frozen is False
    assert "(no longer in buffer)" not in log_panel._detail_header.text()


def test_log_panel_set_level_with_unlisted_level_keeps_filter(qtbot, log_panel: LogPanel):
    log_panel._proxy.update_level_filter(LogLevel.CONSOLE_LOG)
    log_panel._toolbar.set_level(LogLevel.CONSOLE_LOG)  # not in the dropdown
    assert log_panel._proxy._level_num == LogLevel.CONSOLE_LOG.value  # filter not wiped
    assert log_panel._toolbar.filter_level_dropdown.currentIndex() == 0


def test_log_panel_colors_follow_theme(qtbot, log_panel: LogPanel):
    info_index = log_panel._model.index(1, 0)
    success_index = log_panel._model.index(2, 0)

    # INFO rows have no explicit color so the view falls back to the palette text color
    assert log_panel._model.data(info_index, Qt.ItemDataRole.ForegroundRole) is None

    original_theme = get_theme_name()
    other_theme = "dark" if original_theme == "light" else "light"
    try:
        for theme in (other_theme, original_theme):
            apply_theme(theme)
            success_color = log_panel._model.data(success_index, Qt.ItemDataRole.ForegroundRole)
            assert success_color == get_accent_colors().success
    finally:
        apply_theme(original_theme)
