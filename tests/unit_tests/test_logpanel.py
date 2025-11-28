# pylint: disable=no-member
# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

from collections import deque
from unittest.mock import MagicMock, patch

import pytest
from bec_lib.logger import LogLevel
from bec_lib.messages import LogMessage
from qtpy.QtCore import QDateTime

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
def log_panel(qtbot, mocked_client):
    mocked_client.connector.xread = lambda *_, **__: TEST_LOG_MESSAGES
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
    log_panel._model.log_queue._proc_update()
    qtbot.waitUntil(lambda: log_panel._model.rowCount() == 4, timeout=500)
