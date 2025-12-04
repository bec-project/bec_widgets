from time import sleep
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest
from bec_lib.messages import ProcedureExecutionMessage, ProcedureRequestMessage
from bec_lib.procedures.helper import BackendProcedureHelper
from bec_server.procedures.manager import ProcedureManager
from bec_server.procedures.procedure_registry import register
from bec_server.procedures.worker_base import ProcedureWorker

from bec_widgets.widgets.control.procedure_control.procedure_control import (
    ProcedureControl,
    QueueItem,
)

from .client_mocks import mocked_client


class MockWorker(ProcedureWorker):
    def _kill_process(self): ...

    def _run_task(self, item):
        sleep(0.1)

    def _setup_execution_environment(self): ...

    def abort(self): ...

    def abort_execution(self, execution_id: str): ...


@pytest.fixture(scope="module", autouse=True)
def register_test_proc():
    register("test", lambda: None)


@pytest.fixture
def proc_ctrl_w_helper(qtbot, mocked_client: MagicMock):
    proc_ctrl = ProcedureControl(client=mocked_client)
    qtbot.addWidget(proc_ctrl)
    with patch(
        "bec_server.procedures.manager.RedisConnector", lambda _: proc_ctrl.client.connector
    ):
        manager = ProcedureManager(MagicMock(), MockWorker)
    yield proc_ctrl, BackendProcedureHelper(proc_ctrl.client.connector)
    manager.shutdown()


@pytest.fixture
def req_msg():
    return ProcedureRequestMessage(identifier="test")


@pytest.fixture
def exec_msg():
    return lambda id: ProcedureExecutionMessage(identifier="test", queue="test", execution_id=id)


def test_add_proc(qtbot, proc_ctrl_w_helper: tuple[ProcedureControl, BackendProcedureHelper]):
    proc_ctrl, helper = proc_ctrl_w_helper
    assert proc_ctrl._active_queues.childCount() == 0
    helper.request.procedure("test")
    qtbot.waitUntil(lambda: proc_ctrl._active_queues.childCount() != 0, timeout=500)


def test_abort(qtbot, proc_ctrl_w_helper: tuple[ProcedureControl, BackendProcedureHelper]):
    proc_ctrl, helper = proc_ctrl_w_helper
    assert proc_ctrl._active_queues.childCount() == 0
    helper.request.procedure("test")
    qtbot.waitUntil(lambda: proc_ctrl._active_queues.childCount() != 0, timeout=500)

    assert proc_ctrl._unhandled_queues.childCount() == 0
    queue: QueueItem = proc_ctrl._active_queues.child(0)
    queue.child(0).actions_widget.layout().itemAt(0).widget().click()
    qtbot.waitUntil(lambda: proc_ctrl._active_queues.childCount() == 0, timeout=500)
    qtbot.waitUntil(lambda: proc_ctrl._unhandled_queues.childCount() != 0, timeout=500)


def test_delete(
    qtbot,
    proc_ctrl_w_helper: tuple[ProcedureControl, BackendProcedureHelper],
    exec_msg: Callable[[str], ProcedureExecutionMessage],
):
    proc_ctrl, helper = proc_ctrl_w_helper
    [helper.push.unhandled("test", exec_msg("abcd")) for _ in range(3)]
    qtbot.waitUntil(lambda: proc_ctrl._unhandled_queues.childCount() != 0, timeout=500)
    queue: QueueItem = proc_ctrl._unhandled_queues.child(0)
    assert queue.childCount() == 3
    queue.actions_widget.layout().itemAt(0).widget().click()
    qtbot.waitUntil(lambda: helper.get.unhandled_queue("test") == [], timeout=500)
    qtbot.waitUntil(lambda: proc_ctrl._unhandled_queues.childCount() == 0, timeout=500)


def test_resubmit(
    qtbot,
    proc_ctrl_w_helper: tuple[ProcedureControl, BackendProcedureHelper],
    exec_msg: Callable[[str], ProcedureExecutionMessage],
):
    proc_ctrl, helper = proc_ctrl_w_helper
    [helper.push.unhandled("test", exec_msg(f"abcd{i}")) for i in range(3)]
    qtbot.waitUntil(lambda: proc_ctrl._unhandled_queues.childCount() != 0, timeout=500)
    queue: QueueItem = proc_ctrl._unhandled_queues.child(0)
    assert queue.childCount() == 3
    assert proc_ctrl._active_queues.childCount() == 0
    queue.child(0).actions_widget.layout().itemAt(1).widget().click()
    qtbot.waitUntil(lambda: len(helper.get.unhandled_queue("test")) == 2, timeout=500)
    qtbot.waitUntil(lambda: proc_ctrl._active_queues.childCount() != 0, timeout=500)
