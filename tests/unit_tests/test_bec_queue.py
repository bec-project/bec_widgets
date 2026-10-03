from unittest.mock import MagicMock

import pytest
import shiboken6
from bec_lib import messages
from qtpy.QtCore import QEvent
from qtpy.QtWidgets import QAbstractButton, QApplication

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.widgets.control.buttons.button_abort.button_abort import AbortButton
from bec_widgets.widgets.services.bec_queue.bec_queue import BECQueue


@pytest.fixture
def bec_queue_msg_full():
    content = {
        "primary": {
            "info": [
                {
                    "active_request_block": None,
                    "is_scan": [True],
                    "queue_id": "600163fc-5e56-4901-af25-14e9ee76817c",
                    "request_blocks": [
                        {
                            "RID": "89a76021-28c0-4297-828e-74ae40b941e5",
                            "content": {
                                "parameter": {
                                    "args": {"samx": [-0.1, 0.1]},
                                    "kwargs": {
                                        "exp_time": 0.5,
                                        "relative": True,
                                        "steps": 20,
                                        "system_config": {
                                            "file_directory": None,
                                            "file_suffix": None,
                                        },
                                    },
                                },
                                "queue": "primary",
                                "scan_type": "line_scan",
                            },
                            "is_scan": True,
                            "metadata": {
                                "RID": "89a76021-28c0-4297-828e-74ae40b941e5",
                                "file_directory": None,
                                "file_suffix": None,
                                "user_metadata": {"sample_name": "testA"},
                            },
                            "msg": messages.ScanQueueMessage(
                                metadata={
                                    "file_suffix": None,
                                    "file_directory": None,
                                    "user_metadata": {"sample_name": "testA"},
                                    "RID": "89a76021-28c0-4297-828e-74ae40b941e5",
                                },
                                scan_type="line_scan",
                                parameter={
                                    "args": {"samx": [-0.1, 0.1]},
                                    "kwargs": {
                                        "steps": 20,
                                        "exp_time": 0.5,
                                        "relative": True,
                                        "system_config": {
                                            "file_suffix": None,
                                            "file_directory": None,
                                        },
                                    },
                                },
                                queue="primary",
                            ),
                            "readout_priority": {
                                "async": [],
                                "baseline": [],
                                "monitored": ["samx"],
                                "on_request": [],
                            },
                            "report_instructions": [{"scan_progress": 20}],
                            "scan_id": "2d704cc3-c172-404c-866d-608ce09fce40",
                            "scan_number": 1289,
                        }
                    ],
                    "scan_id": ["2d704cc3-c172-404c-866d-608ce09fce40"],
                    "scan_number": [1289],
                    "status": "COMPLETED",
                }
            ],
            "status": "RUNNING",
        }
    }
    msg = messages.ScanQueueStatusMessage(metadata={}, queue=content)
    return msg


@pytest.fixture
def bec_queue(qtbot, mocked_client):
    widget = BECQueue(client=mocked_client, refresh_upon_start=False)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_bec_queue(bec_queue, bec_queue_msg_full):
    bec_queue.update_queue(bec_queue_msg_full.content, {})
    assert bec_queue.table.rowCount() == 1
    assert bec_queue.table.item(0, 0).text() == "1289"
    assert bec_queue.table.item(0, 1).text() == "line_scan"
    assert bec_queue.table.item(0, 2).text() == "line_scan"
    assert bec_queue.table.item(0, 3).text() == "COMPLETED"


def test_bec_queue_empty(bec_queue):
    bec_queue.update_queue({}, {})
    assert bec_queue.table.rowCount() == 1
    assert bec_queue.table.item(0, 0).text() == ""
    assert bec_queue.table.item(0, 1).text() == ""
    assert bec_queue.table.item(0, 2).text() == ""
    assert bec_queue.table.item(0, 3).text() == ""


def test_queue_abort(bec_queue, bec_queue_msg_full):
    # test if abort buttons are not leaking, so making 3 times the same abort request and fixture should check the leak of the buttons automatically

    bec_queue.update_queue(bec_queue_msg_full.content, {})
    assert bec_queue.table.rowCount() == 1
    assert bec_queue.table.item(0, 0).text() == "1289"
    assert bec_queue.table.item(0, 1).text() == "line_scan"
    assert bec_queue.table.item(0, 2).text() == "line_scan"
    assert bec_queue.table.item(0, 3).text() == "COMPLETED"

    abort_button = bec_queue.table.cellWidget(0, 4)
    abort_button.button.click()

    bec_queue.update_queue(bec_queue_msg_full.content, {})

    assert bec_queue.table.rowCount() == 1
    assert bec_queue.table.item(0, 0).text() == "1289"
    assert bec_queue.table.item(0, 1).text() == "line_scan"
    assert bec_queue.table.item(0, 2).text() == "line_scan"
    assert bec_queue.table.item(0, 3).text() == "COMPLETED"

    abort_button = bec_queue.table.cellWidget(0, 4)
    abort_button.button.click()

    bec_queue.update_queue(bec_queue_msg_full.content, {})

    assert bec_queue.table.rowCount() == 1
    assert bec_queue.table.item(0, 0).text() == "1289"
    assert bec_queue.table.item(0, 1).text() == "line_scan"
    assert bec_queue.table.item(0, 2).text() == "line_scan"
    assert bec_queue.table.item(0, 3).text() == "COMPLETED"

    abort_button = bec_queue.table.cellWidget(0, 4)
    abort_button.button.click()


def _queue_entry(scan_number: int, rid: str, status: str = "PENDING") -> dict:
    """Build a single primary-queue entry with one request block."""
    msg = messages.ScanQueueMessage(
        metadata={"RID": rid}, scan_type="line_scan", parameter={"args": {}, "kwargs": {}}
    )
    return {
        "queue_id": f"queue-{scan_number}",
        "scan_id": [f"scan-{scan_number}"],
        "is_scan": [True],
        "request_blocks": [
            {
                "msg": msg,
                "RID": rid,
                "readout_priority": {"monitored": [], "baseline": [], "on_request": []},
                "is_scan": True,
                "scan_number": scan_number,
                "scan_id": f"scan-{scan_number}",
            }
        ],
        "scan_number": [scan_number],
        "status": status,
    }


@pytest.fixture
def bec_queue_msg_three_rows():
    """Queue status with three pending scans, one row each."""
    content = {
        "primary": {
            "info": [
                _queue_entry(1001, "rid-1001", status="RUNNING"),
                _queue_entry(1002, "rid-1002"),
                _queue_entry(1003, "rid-1003"),
            ],
            "status": "RUNNING",
        }
    }
    return messages.ScanQueueStatusMessage(metadata={}, queue=content)


def _row_scan_numbers(bec_queue: BECQueue) -> list[str]:
    return [bec_queue.table.item(row, 0).text() for row in range(bec_queue.table.rowCount())]


@pytest.mark.parametrize("clicked_row", [0, 1, 2])
def test_queue_abort_removes_clicked_row(bec_queue, bec_queue_msg_three_rows, clicked_row):
    """Clicking the abort button of a row aborts that request and removes exactly that row."""
    bec_queue.update_queue(bec_queue_msg_three_rows.content, {})
    assert _row_scan_numbers(bec_queue) == ["1001", "1002", "1003"]

    queue_mock = MagicMock()
    for row in range(bec_queue.table.rowCount()):
        bec_queue.table.cellWidget(row, 4).queue = queue_mock

    clicked = bec_queue.table.cellWidget(clicked_row, 4)
    assert isinstance(clicked, AbortButton)
    expected_rid = f"rid-{1001 + clicked_row}"
    assert clicked.request_id == expected_rid

    clicked.button.click()

    queue_mock.request_scan_abortion.assert_called_once_with(request_id=expected_rid)
    remaining = [n for n in ["1001", "1002", "1003"] if n != str(1001 + clicked_row)]
    assert _row_scan_numbers(bec_queue) == remaining

    # Every remaining row keeps an intact abort button for its own request.
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    for row, scan_number in enumerate(remaining):
        cell = bec_queue.table.cellWidget(row, 4)
        assert isinstance(cell, AbortButton)
        assert cell.request_id == f"rid-{scan_number}"
        assert shiboken6.isValid(cell.button)
    # The aborted row's cell widget is deleted together with its row.
    assert not shiboken6.isValid(clicked)


def test_queue_delete_selected_row_without_abort_sender_is_noop(
    bec_queue, bec_queue_msg_three_rows
):
    """A call that does not originate from an abort button must not remove any row."""
    bec_queue.update_queue(bec_queue_msg_three_rows.content, {})
    bec_queue.delete_selected_row()
    assert _row_scan_numbers(bec_queue) == ["1001", "1002", "1003"]


def _primary_queue_content(entries: list[dict]) -> dict:
    """Content of a queue status message whose primary queue holds the given entries."""
    return messages.ScanQueueStatusMessage(
        metadata={}, queue={"primary": {"info": entries, "status": "RUNNING"}}
    ).content


def _click_every_button_in_row(bec_queue: BECQueue, row: int) -> None:
    """Click every button that any cell widget of the given row offers."""
    for column in range(bec_queue.table.columnCount()):
        cell = bec_queue.table.cellWidget(row, column)
        if cell is None:
            continue
        for button in cell.findChildren(QAbstractButton):
            button.click()


@pytest.mark.parametrize(
    "empty_content",
    [{}, {"queue": {}}, "primary_without_items"],
    ids=["no_queue", "no_primary_queue", "empty_primary_queue"],
)
def test_queue_placeholder_row_never_requests_abort(bec_queue, mocked_client, empty_content):
    """
    The empty-queue placeholder row targets no request, so it must not offer an abort.

    An empty request id is not harmless by design: AbortButton treats None as "abort the current
    request", and a scan may already run while the placeholder is still displayed. Clicking what
    the placeholder offers must therefore send no abort request at all and keep the placeholder.
    """
    if empty_content == "primary_without_items":
        empty_content = _primary_queue_content([])
    # Start from a populated table so the placeholder replaces a real row.
    bec_queue.update_queue(_primary_queue_content([_queue_entry(1001, "rid-1001")]), {})
    previous_button = bec_queue.table.cellWidget(0, 4)
    assert isinstance(previous_button, AbortButton)

    bec_queue.update_queue(empty_content, {})
    assert _row_scan_numbers(bec_queue) == [""]
    # The placeholder must not inherit the abort button of the row it replaces.
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not shiboken6.isValid(previous_button)

    _click_every_button_in_row(bec_queue, 0)

    mocked_client.queue.request_scan_abortion.assert_not_called()
    assert _row_scan_numbers(bec_queue) == [""]
    assert bec_queue.table.cellWidget(0, 4) is None


def test_queue_row_without_request_id_has_no_abort_button(bec_queue, mocked_client):
    """A queue item that carries no request id cannot be aborted by id, so it gets no button."""
    bec_queue.update_queue(_primary_queue_content([_queue_entry(1002, "")]), {})
    assert _row_scan_numbers(bec_queue) == ["1002"]
    assert bec_queue.table.cellWidget(0, 4) is None

    _click_every_button_in_row(bec_queue, 0)
    mocked_client.queue.request_scan_abortion.assert_not_called()
    assert _row_scan_numbers(bec_queue) == ["1002"]
