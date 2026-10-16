from time import sleep
from typing import Callable
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
from bec_lib.messages import (
    ProcedureExecutionMessage,
    ProcedureRequestMessage,
    ProcedureWorkerStatus,
)
from bec_lib.procedures.helper import BackendProcedureHelper
from bec_lib.redis_connector import RedisConnector
from bec_server.procedures.manager import ProcedureManager
from bec_server.procedures.procedure_registry import register
from bec_server.procedures.worker_base import ProcedureWorker

import bec_widgets.tests.utils as test_utils
from bec_widgets.widgets.control.procedure_control.procedure_control import (
    ProcedureControl,
    QueueItem,
)


class MockWorker(ProcedureWorker):
    """In-process stand-in for the out-of-process worker: same queue/active-set protocol."""

    def _kill_process(self): ...

    def _setup_execution_environment(self): ...

    def _ending_or_ended(self) -> bool:
        return self._aborted.is_set()

    def logs(self) -> list[str]:
        return []

    def abort_execution(self, execution_id: str): ...

    def work(self):
        while (
            item := self._conn.blocking_list_pop_to_set_add(
                self.key, self._active_procs_endpoint, timeout_s=0.1
            )
        ) is not None:
            self.status = ProcedureWorkerStatus.RUNNING
            self._helper.status_update(item.execution_id, "Started")
            self._helper.notify_watchers(self._queue, queue_type="execution")
            sleep(0.1)
            self._helper.status_update(item.execution_id, "Finished")
            self._helper.remove_from_active.by_exec_id(item.execution_id)
            self.status = ProcedureWorkerStatus.IDLE
        self.status = ProcedureWorkerStatus.FINISHED


@pytest.fixture(autouse=True)
def fresh_fake_connector():
    """Main's fixtures share one fakeredis connector between tests and shut it down after each;
    its pub/sub listener does not come back, so give the next test a new one."""
    yield
    test_utils._REDIS_CONN = None


@pytest.fixture(scope="module", autouse=True)
def register_test_proc():
    register("test", lambda: None)


@pytest.fixture
def proc_ctrl_w_helper(qtbot, mocked_client: MagicMock):
    # the shared fakeredis connector outlives a single test
    for key in mocked_client.connector.keys("*procedure*"):
        mocked_client.connector._managed_connection.delete(key)
    proc_ctrl = ProcedureControl(client=mocked_client)
    qtbot.addWidget(proc_ctrl)
    # the manager gets its own connection to the same fake server: its shutdown() closes it
    fake_conn = lambda *_, **__: RedisConnector("localhost:1", redis_cls=fakeredis.FakeRedis)
    with (
        patch("bec_server.procedures.manager.RedisConnector", fake_conn),
        patch("bec_server.procedures.worker_base.RedisConnector", fake_conn),
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
    qtbot.waitUntil(lambda: proc_ctrl._active_queues.childCount() != 0, timeout=5000)


def test_abort(qtbot, proc_ctrl_w_helper: tuple[ProcedureControl, BackendProcedureHelper]):
    proc_ctrl, helper = proc_ctrl_w_helper
    assert proc_ctrl._active_queues.childCount() == 0
    helper.request.procedure("test")
    qtbot.waitUntil(lambda: proc_ctrl._active_queues.childCount() != 0, timeout=5000)

    assert proc_ctrl._unhandled_queues.childCount() == 0
    queue: QueueItem = proc_ctrl._active_queues.child(0)
    queue.child(0).actions_widget.layout().itemAt(0).widget().click()
    qtbot.waitUntil(lambda: proc_ctrl._active_queues.childCount() == 0, timeout=5000)
    qtbot.waitUntil(lambda: proc_ctrl._unhandled_queues.childCount() != 0, timeout=5000)


def test_delete(
    qtbot,
    proc_ctrl_w_helper: tuple[ProcedureControl, BackendProcedureHelper],
    exec_msg: Callable[[str], ProcedureExecutionMessage],
):
    proc_ctrl, helper = proc_ctrl_w_helper
    [helper.push.unhandled("test", exec_msg("abcd")) for _ in range(3)]
    qtbot.waitUntil(lambda: proc_ctrl._unhandled_queues.childCount() != 0, timeout=5000)
    queue: QueueItem = proc_ctrl._unhandled_queues.child(0)
    assert queue.childCount() == 3
    queue.actions_widget.layout().itemAt(0).widget().click()
    qtbot.waitUntil(lambda: helper.get.unhandled_queue("test") == [], timeout=5000)
    qtbot.waitUntil(lambda: proc_ctrl._unhandled_queues.childCount() == 0, timeout=5000)


def test_resubmit(
    qtbot,
    proc_ctrl_w_helper: tuple[ProcedureControl, BackendProcedureHelper],
    exec_msg: Callable[[str], ProcedureExecutionMessage],
):
    proc_ctrl, helper = proc_ctrl_w_helper
    [helper.push.unhandled("test", exec_msg(f"abcd{i}")) for i in range(3)]
    qtbot.waitUntil(lambda: proc_ctrl._unhandled_queues.childCount() != 0, timeout=5000)
    queue: QueueItem = proc_ctrl._unhandled_queues.child(0)
    assert queue.childCount() == 3
    assert proc_ctrl._active_queues.childCount() == 0
    queue.child(0).actions_widget.layout().itemAt(1).widget().click()
    qtbot.waitUntil(lambda: len(helper.get.unhandled_queue("test")) == 2, timeout=5000)
    qtbot.waitUntil(lambda: proc_ctrl._active_queues.childCount() != 0, timeout=5000)
