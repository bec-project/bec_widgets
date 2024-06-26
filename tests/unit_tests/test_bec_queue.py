import pytest
from bec_lib import messages

from bec_widgets.widgets.bec_queue.bec_queue import BECQueue

from .client_mocks import mocked_client


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
                            "scan_motors": ["samx"],
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
    widget = BECQueue(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_bec_queue(bec_queue, bec_queue_msg_full):
    bec_queue.update_queue(bec_queue_msg_full.content, {})
    assert bec_queue.rowCount() == 1
    assert bec_queue.item(0, 0).text() == "1289"
    assert bec_queue.item(0, 1).text() == "line_scan"
    assert bec_queue.item(0, 2).text() == "COMPLETED"


def test_bec_queue_empty(bec_queue):
    bec_queue.update_queue({}, {})
    assert bec_queue.rowCount() == 1
    assert bec_queue.item(0, 0).text() == ""
    assert bec_queue.item(0, 1).text() == ""
    assert bec_queue.item(0, 2).text() == ""
