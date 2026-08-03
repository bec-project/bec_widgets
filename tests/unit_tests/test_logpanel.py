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
    log_panel._update_service_filter(set())
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
