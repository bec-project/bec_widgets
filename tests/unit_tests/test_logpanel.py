# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

from collections import deque
from unittest.mock import MagicMock

import pytest
from bec_lib.messages import LogMessage
from qtpy.QtCore import QDateTime, Qt, Signal  # type: ignore

from bec_widgets.widgets.utility.logpanel._util import (
    log_time,
    replace_escapes,
    simple_color_format,
)
from bec_widgets.widgets.utility.logpanel.logpanel import DEFAULT_LOG_COLORS, LogPanel

from .client_mocks import mocked_client

TEST_TABLE_STRING = "2025-01-15 15:57:18 | bec_server.scan_server.scan_queue | [INFO] | \n \x1b[3m              primary queue / ScanQueueStatus.RUNNING              \x1b[0m\n┏━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┓\n┃\x1b[1m \x1b[0m\x1b[1m queue_id  \x1b[0m\x1b[1m \x1b[0m┃\x1b[1m \x1b[0m\x1b[1mscan_id\x1b[0m\x1b[1m \x1b[0m┃\x1b[1m \x1b[0m\x1b[1mis_scan\x1b[0m\x1b[1m \x1b[0m┃\x1b[1m \x1b[0m\x1b[1mtype\x1b[0m\x1b[1m \x1b[0m┃\x1b[1m \x1b[0m\x1b[1mscan_numb…\x1b[0m\x1b[1m \x1b[0m┃\x1b[1m \x1b[0m\x1b[1mIQ status\x1b[0m\x1b[1m \x1b[0m┃\n┡━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━┩\n│ bbe50c82-6… │  None   │  False  │  mv  │    None    │  PENDING  │\n└─────────────┴─────────┴─────────┴──────┴────────────┴───────────┘\n\n"

TEST_LOG_MESSAGES = [
    LogMessage(
        metadata={},
        log_type="debug",
        log_msg={
            "text": "datetime | debug | test log message",
            "record": {"time": {"timestamp": 123456789.000}},
            "service_name": "ScanServer",
        },
    ),
    LogMessage(
        metadata={},
        log_type="info",
        log_msg={
            "text": "datetime | info | test log message",
            "record": {"time": {"timestamp": 123456789.007}},
            "service_name": "ScanServer",
        },
    ),
    LogMessage(
        metadata={},
        log_type="success",
        log_msg={
            "text": "datetime | success | test log message",
            "record": {"time": {"timestamp": 123456789.012}},
            "service_name": "ScanServer",
        },
    ),
]

TEST_COMBINED_PLAINTEXT = "datetime | debug | test log message\ndatetime | info | test log message\ndatetime | success | test log message\n"


@pytest.fixture
def raw_queue():
    yield deque(TEST_LOG_MESSAGES, maxlen=100)


@pytest.fixture
def log_panel(qtbot, mocked_client: MagicMock):
    widget = LogPanel(client=mocked_client, service_status=MagicMock())
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.cleanup()


def test_log_panel_init(log_panel: LogPanel):
    assert log_panel.plain_text == ""


def test_table_string_processing():
    assert "\x1b" in TEST_TABLE_STRING
    sanitized = replace_escapes(TEST_TABLE_STRING)
    assert "\x1b" not in sanitized
    assert "  " not in sanitized
    assert "\n" not in sanitized


@pytest.mark.parametrize(
    ["msg", "color"], zip(TEST_LOG_MESSAGES, ["#0000CC", "#FFFFFF", "#00FF00"])
)
def test_color_format(msg: LogMessage, color: str):
    assert color in simple_color_format(msg, DEFAULT_LOG_COLORS)


def test_logpanel_output(qtbot, log_panel: LogPanel):
    log_panel._log_manager._data = deque(TEST_LOG_MESSAGES)
    log_panel._on_redraw()
    assert log_panel.plain_text == TEST_COMBINED_PLAINTEXT

    def display_queue_empty():
        print(log_panel._log_manager._display_queue)
        return len(log_panel._log_manager._display_queue) == 0

    next_text = "datetime | error | test log message"
    log_panel._log_manager._process_incoming_log_msg(
        {
            "data": LogMessage(
                metadata={},
                log_type="error",
                log_msg={"text": next_text, "record": {}, "service_name": "ScanServer"},
            )
        }
    )

    qtbot.waitUntil(display_queue_empty, timeout=5000)
    assert log_panel.plain_text == TEST_COMBINED_PLAINTEXT + next_text + "\n"


def test_level_filter(log_panel: LogPanel):
    log_panel._log_manager._data = deque(TEST_LOG_MESSAGES)
    log_panel._log_manager.update_level_filter("INFO")
    log_panel._on_redraw()
    assert (
        log_panel.plain_text
        == "datetime | info | test log message\ndatetime | success | test log message\n"
    )


def test_clear_button(log_panel: LogPanel):
    log_panel._log_manager._data = deque(TEST_LOG_MESSAGES)
    log_panel.toolbar.clear_button.click()
    assert log_panel._log_manager._data == deque([])


def test_timestamp_filter(log_panel: LogPanel):
    log_panel._log_manager._timestamp_start = QDateTime(1973, 11, 29, 21, 33, 9, 5, 1)
    pytest.approx(log_panel._log_manager._timestamp_start.toMSecsSinceEpoch() / 1000, 123456789.005)
    log_panel._log_manager._timestamp_end = QDateTime(1973, 11, 29, 21, 33, 9, 10, 1)
    pytest.approx(log_panel._log_manager._timestamp_end.toMSecsSinceEpoch() / 1000, 123456789.010)
    filter_ = log_panel._log_manager._create_timestamp_filter()
    assert not filter_(TEST_LOG_MESSAGES[0])
    assert filter_(TEST_LOG_MESSAGES[1])
    assert not filter_(TEST_LOG_MESSAGES[2])
