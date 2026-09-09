# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import gc
import os
import subprocess
import sys
import threading
import time
import weakref
from pathlib import Path
from unittest import mock

import pytest
import shiboken6
from bec_lib import service_config
from bec_lib.messages import GUIInstructionMessage, ScanMessage
from bec_lib.serialization import MsgpackSerialization
from qtpy.QtCore import QEvent, QObject, QThread
from qtpy.QtWidgets import QApplication

from bec_widgets.utils.bec_dispatcher import BECDispatcher, QtRedisConnector, QtThreadSafeCallback


def test_init_handles_client_and_config_arg():
    # Client passed
    self_mock = mock.MagicMock(_initialized=False)
    with mock.patch.object(BECDispatcher, "start_cli_server"):
        BECDispatcher.__init__(self_mock, client=mock.MagicMock(name="test_client"))
        assert "test_client" in repr(self_mock.client)

    # No client, service config object
    self_mock.reset_mock()
    self_mock._initialized = False
    with (
        mock.patch.object(BECDispatcher, "start_cli_server"),
        mock.patch("bec_widgets.utils.bec_dispatcher.BECClient") as client_cls,
    ):
        config = service_config.ServiceConfig()
        BECDispatcher.__init__(self_mock, client=None, config=config)
        client_cls.assert_called_with(
            config=config, connector_cls=QtRedisConnector, name="BECWidgets"
        )

    # No client, service config string
    self_mock.reset_mock()
    self_mock._initialized = False
    with (
        mock.patch.object(BECDispatcher, "start_cli_server"),
        mock.patch("bec_widgets.utils.bec_dispatcher.BECClient"),
        mock.patch("bec_widgets.utils.bec_dispatcher.ServiceConfig") as svc_cfg,
        mock.patch("bec_widgets.utils.bec_dispatcher.isinstance", return_value=False),
    ):
        config = service_config.ServiceConfig()
        BECDispatcher.__init__(self_mock, client=None, config="test_str")
        svc_cfg.assert_called_with("test_str")


@pytest.fixture
def bec_dispatcher_w_connector(bec_dispatcher, topics_msg_list, send_msg_event):
    def pubsub_msg_generator():
        send_msg_event.wait()
        for topic, msg in topics_msg_list:
            yield {"channel": topic.encode(), "pattern": None, "data": msg}
        while True:
            time.sleep(0.2)
            yield StopIteration

    redis_class_mock = mock.MagicMock()
    pubsub = redis_class_mock().pubsub()
    messages = pubsub_msg_generator()
    pubsub.get_message.side_effect = lambda timeout: next(messages)
    connector = QtRedisConnector("localhost:1", redis_class_mock)
    bec_dispatcher.client.connector = connector
    yield bec_dispatcher
    connector.shutdown()


dummy_msg = MsgpackSerialization.dumps(ScanMessage(point_id=0, scan_id="0", data={}))


@pytest.fixture
def send_msg_event():
    return threading.Event()


@pytest.mark.parametrize(
    "topics_msg_list", [(("topic1", dummy_msg), ("topic2", dummy_msg), ("topic3", dummy_msg))]
)
def test_dispatcher_disconnect_all(bec_dispatcher_w_connector, qtbot, send_msg_event):
    bec_dispatcher = bec_dispatcher_w_connector
    cb1 = mock.Mock(spec=[])
    cb2 = mock.Mock(spec=[])

    bec_dispatcher.connect_slot(cb1, "topic1")
    bec_dispatcher.connect_slot(cb1, "topic2")
    bec_dispatcher.connect_slot(cb2, "topic2")
    bec_dispatcher.connect_slot(cb2, "topic3")
    assert len(bec_dispatcher.client.connector._managed_connection._topics_cb) == 3
    send_msg_event.set()
    qtbot.wait(10)
    assert cb1.call_count == 2
    assert cb2.call_count == 2

    bec_dispatcher.disconnect_all()

    assert len(bec_dispatcher.client.connector._managed_connection._topics_cb) == 0


@pytest.mark.parametrize("topics_msg_list", [(("topic1", dummy_msg), ("topic2", dummy_msg))])
def test_dispatcher_disconnect_one(bec_dispatcher_w_connector, qtbot, send_msg_event):
    bec_dispatcher = bec_dispatcher_w_connector
    cb1 = mock.Mock(spec=[])
    cb2 = mock.Mock(spec=[])

    bec_dispatcher.connect_slot(cb1, "topic1")
    bec_dispatcher.connect_slot(cb2, "topic2")
    assert len(bec_dispatcher.client.connector._managed_connection._topics_cb) == 2
    bec_dispatcher.disconnect_slot(cb1, "topic1")
    assert len(bec_dispatcher.client.connector._managed_connection._topics_cb) == 1

    send_msg_event.set()
    qtbot.wait(10)
    assert cb1.call_count == 0
    cb2.assert_called_once()


@pytest.mark.parametrize("topics_msg_list", [(("topic1", dummy_msg),)])
def test_dispatcher_2_cb_same_topic(bec_dispatcher_w_connector, qtbot, send_msg_event):
    # test for BEC issue #276
    bec_dispatcher = bec_dispatcher_w_connector
    cb1 = mock.Mock(spec=[])
    cb2 = mock.Mock(spec=[])

    num_slots = len(bec_dispatcher._registered_slots)

    bec_dispatcher.connect_slot(cb1, "topic1")
    bec_dispatcher.connect_slot(cb2, "topic1")

    # The redis connector should only subscribe once to the topic
    assert len(bec_dispatcher.client.connector._managed_connection._topics_cb) == 1

    # The the given topic, two callbacks should be registered
    assert len(bec_dispatcher.client.connector._managed_connection._topics_cb["topic1"]) == 2

    # The dispatcher should have two slots
    assert len(bec_dispatcher._registered_slots) == num_slots + 2
    bec_dispatcher.disconnect_slot(cb1, "topic1")
    assert len(bec_dispatcher._registered_slots) == num_slots + 1

    send_msg_event.set()
    qtbot.wait(10)
    assert cb1.call_count == 0
    cb2.assert_called_once()


@pytest.mark.parametrize("topics_msg_list", [(("topic1", dummy_msg),)])
def test_dispatcher_2_cb_same_topic_same_slot(bec_dispatcher_w_connector, qtbot, send_msg_event):
    bec_dispatcher = bec_dispatcher_w_connector
    cb1 = mock.Mock(spec=[])

    bec_dispatcher.connect_slot(cb1, "topic1")
    bec_dispatcher.connect_slot(cb1, "topic1")
    assert len(bec_dispatcher.client.connector._managed_connection._topics_cb) == 1
    assert (
        len(list(filter(lambda slot: slot.cb == cb1, bec_dispatcher._registered_slots.values())))
        == 1
    )

    send_msg_event.set()
    qtbot.wait(10)
    assert cb1.call_count == 1
    bec_dispatcher.disconnect_slot(cb1, "topic1")
    assert (
        len(list(filter(lambda slot: slot.cb == cb1, bec_dispatcher._registered_slots.values())))
        == 0
    )


@pytest.mark.parametrize("topics_msg_list", [(("topic1", dummy_msg), ("topic2", dummy_msg))])
def test_dispatcher_2_topic_same_cb(bec_dispatcher_w_connector, qtbot, send_msg_event):
    bec_dispatcher = bec_dispatcher_w_connector
    cb1 = mock.Mock(spec=[])

    bec_dispatcher.connect_slot(cb1, "topic1")
    bec_dispatcher.connect_slot(cb1, "topic2")
    assert len(bec_dispatcher.client.connector._managed_connection._topics_cb) == 2
    bec_dispatcher.disconnect_slot(cb1, "topic1")
    assert len(bec_dispatcher.client.connector._managed_connection._topics_cb) == 1

    send_msg_event.set()
    qtbot.wait(10)
    cb1.assert_called_once()


@pytest.mark.parametrize("topics_msg_list", [(("topic1", dummy_msg), ("topic2", dummy_msg))])
def test_dispatcher_2_topic_same_cb_with_boundmethod(
    bec_dispatcher_w_connector, qtbot, send_msg_event
):
    bec_dispatcher = bec_dispatcher_w_connector

    class MockObject:
        def mock_slot(self, msg, metadata):
            pass

    cb1 = MockObject()

    bec_dispatcher.connect_slot(cb1.mock_slot, "topic1", {"metadata": "test"})
    bec_dispatcher.connect_slot(cb1.mock_slot, "topic1", {"metadata": "test"})

    def _get_slots():
        return list(
            filter(
                lambda slot: slot == QtThreadSafeCallback(cb1.mock_slot, {"metadata": "test"}),
                bec_dispatcher._registered_slots.values(),
            )
        )

    assert len(bec_dispatcher.client.connector._managed_connection._topics_cb) == 1
    assert len(_get_slots()) == 1
    bec_dispatcher.disconnect_slot(cb1.mock_slot, "topic1")
    assert len(bec_dispatcher.client.connector._managed_connection._topics_cb) == 0
    assert len(_get_slots()) == 0

    send_msg_event.set()
    qtbot.wait(10)


def test_qt_redis_connector_logs_rpc_before_qt_callback(monkeypatch):
    info_mock = mock.MagicMock()
    warning_mock = mock.MagicMock()
    monkeypatch.setattr("bec_widgets.utils.bec_dispatcher.logger.info", info_mock)
    monkeypatch.setattr("bec_widgets.utils.bec_dispatcher.logger.warning", warning_mock)

    def callback(_msg, _metadata):
        pass

    cb = QtThreadSafeCallback(callback)
    connector = QtRedisConnector("localhost:1", mock.MagicMock())
    rpc_msg = GUIInstructionMessage(
        action="set_value",
        parameter={"args": [1], "kwargs": {"source": "test"}, "gui_id": "ring"},
        metadata={
            "request_id": "dispatcher-request",
            "receiver": "gui",
            "object_name": "progressbar",
            "timeout": 0.1,
            "sent_at": 1.0,
            "deadline": 1.1,
        },
    )

    try:
        connector._managed_connection._execute_callback(cb, {"data": rpc_msg}, {})

        info_mock.assert_called_once()
        info_message = info_mock.call_args.args[0]
        assert "GUI RPC dispatcher received request before Qt callback emit" in info_message
        assert "request_id=dispatcher-request" in info_message
        assert "method=set_value" in info_message
        assert "receiver=gui" in info_message
        assert "target_gui_id=ring" in info_message
        assert "object_name=progressbar" in info_message
        assert "timeout=0.1" in info_message
        assert "stale_on_dispatch=True" in info_message

        warning_mock.assert_called_once()
        warning_message = warning_mock.call_args.args[0]
        assert "received request after client timeout deadline" in warning_message
        assert "request_id=dispatcher-request" in warning_message
    finally:
        connector.shutdown()


def test_stop_cli_server_is_idempotent(bec_dispatcher):
    """Both GUIServer.shutdown and BECConnector.terminate stop the CLI server at
    application exit; the second call must be a silent no-op, not an ERROR."""
    from unittest import mock

    from bec_widgets.utils import bec_dispatcher as bd_module

    with mock.patch.object(bd_module, "logger") as mock_logger:
        bec_dispatcher.stop_cli_server()
        bec_dispatcher.stop_cli_server()
    mock_logger.error.assert_not_called()


def _queue_callback(wrapper):
    """Queue a real cross-thread emission without allowing GUI delivery yet."""
    thread = threading.Thread(target=wrapper, args=({"value": 1}, {"source": "worker"}))
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()


def _deliver_after_receiver_collection(cyclic):
    """Run in a child process: the original queued bound method could segfault."""
    app = QApplication([])
    calls = []

    class Receiver:
        def __init__(self):
            self.state = "alive"
            if cyclic:
                self.cycle = self

        def receive(self, content, metadata):
            calls.append("entered")
            calls.append(self.state)

    receiver = Receiver()
    receiver_ref = weakref.ref(receiver)
    wrapper = QtThreadSafeCallback(receiver.receive)
    _queue_callback(wrapper)
    del receiver
    gc.collect()
    assert receiver_ref() is None
    assert wrapper.cb is None

    # A second queued callback proves that Qt has drained the queued deliveries.
    delivered = []
    sentinel = QtThreadSafeCallback(lambda *_: delivered.append(True))
    _queue_callback(sentinel)
    app.processEvents()
    assert delivered == [True]
    assert calls == []
    print("Collected receiver was not called", flush=True)


@pytest.mark.parametrize("cyclic", [False, True], ids=["refcount", "cyclic-gc"])
def test_qthreadsafe_callback_skips_collected_receiver_in_subprocess(cyclic):
    """Keep native crash regressions from terminating the pytest process."""
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "faulthandler",
            "-c",
            "from tests.unit_tests.test_bec_dispatcher import "
            f"_deliver_after_receiver_collection; _deliver_after_receiver_collection({cyclic!r})",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "OPHYD_CONTROL_LAYER": "dummy"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"Queued callback subprocess exited with {result.returncode}\n"
        f"{result.stdout[-6000:]}\n{result.stderr[-6000:]}"
    )
    assert "Collected receiver was not called" in result.stdout


def test_qthreadsafe_callback_delivers_live_receiver_on_gui_thread(qapp):
    calls = []

    class Receiver:
        def receive(self, content, metadata):
            calls.append((content, metadata, QThread.currentThread()))

    receiver = Receiver()
    wrapper = QtThreadSafeCallback(receiver.receive)
    _queue_callback(wrapper)
    assert calls == []

    qapp.processEvents()

    assert calls == [({"value": 1}, {"source": "worker"}, qapp.thread())]


@pytest.mark.parametrize(
    "disconnect", ["disconnect_owner", "disconnect_slot", "disconnect_topics", "disconnect_all"]
)
def test_dispatcher_disconnect_cancels_queued_delivery(bec_dispatcher, qapp, disconnect):
    owner = QObject()
    callback = mock.Mock(spec=[])
    bec_dispatcher.connect_slot(callback, "lifetime-test", owner=owner)
    wrapper = next(slot for slot in bec_dispatcher._registered_slots if slot.cb is callback)
    _queue_callback(wrapper)
    callback.assert_not_called()

    if disconnect == "disconnect_owner":
        bec_dispatcher.disconnect_owner(owner)
    elif disconnect == "disconnect_slot":
        bec_dispatcher.disconnect_slot(callback, "lifetime-test")
    elif disconnect == "disconnect_topics":
        bec_dispatcher.disconnect_topics("lifetime-test")
    else:
        bec_dispatcher.disconnect_all()

    # The connector may still hold an in-flight reference to the released wrapper.
    _queue_callback(wrapper)
    qapp.processEvents()
    callback.assert_not_called()
    assert wrapper not in bec_dispatcher._registered_slots


@pytest.mark.parametrize("disconnect", ["disconnect_slot", "disconnect_topics"])
def test_dispatcher_partial_disconnect_preserves_delivery(bec_dispatcher, qapp, disconnect):
    owner = QObject()
    callback = mock.Mock(spec=[])
    bec_dispatcher.connect_slot(callback, ["removed-topic", "retained-topic"], owner=owner)
    wrapper = next(slot for slot in bec_dispatcher._registered_slots if slot.cb is callback)
    _queue_callback(wrapper)

    if disconnect == "disconnect_slot":
        bec_dispatcher.disconnect_slot(callback, "removed-topic")
    else:
        bec_dispatcher.disconnect_topics("removed-topic")

    qapp.processEvents()
    callback.assert_called_once_with({"value": 1}, {"source": "worker"})
    assert wrapper.topics == {"retained-topic"}
    _queue_callback(wrapper)
    qapp.processEvents()
    assert callback.call_count == 2


def test_dispatcher_reconnect_does_not_reactivate_old_delivery(bec_dispatcher, qapp):
    owner = QObject()
    callback = mock.Mock(spec=[])
    bec_dispatcher.connect_slot(callback, "lifetime-test", owner=owner)
    old_wrapper = next(slot for slot in bec_dispatcher._registered_slots if slot.cb is callback)
    _queue_callback(old_wrapper)
    bec_dispatcher.disconnect_owner(owner)

    bec_dispatcher.connect_slot(callback, "lifetime-test", owner=owner)
    new_wrapper = next(slot for slot in bec_dispatcher._registered_slots if slot.cb is callback)
    assert new_wrapper is not old_wrapper
    _queue_callback(old_wrapper)
    _queue_callback(new_wrapper)
    qapp.processEvents()

    callback.assert_called_once_with({"value": 1}, {"source": "worker"})


def test_dispatcher_disconnect_releases_lambda_capture(bec_dispatcher):
    owner = QObject()
    owner_ref = weakref.ref(owner)
    bec_dispatcher.connect_slot(
        lambda _content, _metadata, target=owner: target.objectName(), "lifetime-test", owner=owner
    )
    wrapper = next(
        slot
        for slot in bec_dispatcher._registered_slots
        if slot.cb_owner is not None and slot.cb_owner() is owner
    )
    callback_ref = weakref.ref(wrapper.cb)
    del owner
    gc.collect()
    assert owner_ref() is not None

    bec_dispatcher.disconnect_owner(owner_ref())
    gc.collect()

    # An in-flight wrapper must not keep the lambda or its captured owner alive.
    assert callback_ref() is None
    assert owner_ref() is None


@pytest.mark.parametrize("teardown", ["native-delete", "cleanup", "garbage-collect"])
def test_qthreadsafe_callback_checks_lambda_owner_at_delivery(qapp, teardown):
    calls = []
    owner = QObject()
    owner_ref = weakref.ref(owner)
    wrapper = QtThreadSafeCallback(lambda *_: calls.append(True), owner=owner)
    _queue_callback(wrapper)

    if teardown == "native-delete":
        owner.deleteLater()
        qapp.sendPostedEvents(owner, QEvent.Type.DeferredDelete)
        assert not shiboken6.isValid(owner)
    elif teardown == "cleanup":
        owner._destroyed = True
    else:
        del owner
        gc.collect()
        assert owner_ref() is None

    qapp.processEvents()
    assert calls == []
