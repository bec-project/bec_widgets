# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import threading
import time
from unittest import mock

import pytest
from bec_lib import service_config
from bec_lib.messages import GUIInstructionMessage, ScanMessage
from bec_lib.serialization import MsgpackSerialization

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
    assert len(bec_dispatcher.client.connector._topics_cb) == 3
    send_msg_event.set()
    qtbot.wait(10)
    assert cb1.call_count == 2
    assert cb2.call_count == 2

    bec_dispatcher.disconnect_all()

    assert len(bec_dispatcher.client.connector._topics_cb) == 0


@pytest.mark.parametrize("topics_msg_list", [(("topic1", dummy_msg), ("topic2", dummy_msg))])
def test_dispatcher_disconnect_one(bec_dispatcher_w_connector, qtbot, send_msg_event):
    bec_dispatcher = bec_dispatcher_w_connector
    cb1 = mock.Mock(spec=[])
    cb2 = mock.Mock(spec=[])

    bec_dispatcher.connect_slot(cb1, "topic1")
    bec_dispatcher.connect_slot(cb2, "topic2")
    assert len(bec_dispatcher.client.connector._topics_cb) == 2
    bec_dispatcher.disconnect_slot(cb1, "topic1")
    assert len(bec_dispatcher.client.connector._topics_cb) == 1

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
    assert len(bec_dispatcher.client.connector._topics_cb) == 1

    # The the given topic, two callbacks should be registered
    assert len(bec_dispatcher.client.connector._topics_cb["topic1"]) == 2

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
    assert len(bec_dispatcher.client.connector._topics_cb) == 1
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
    assert len(bec_dispatcher.client.connector._topics_cb) == 2
    bec_dispatcher.disconnect_slot(cb1, "topic1")
    assert len(bec_dispatcher.client.connector._topics_cb) == 1

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

    assert len(bec_dispatcher.client.connector._topics_cb) == 1
    assert len(_get_slots()) == 1
    bec_dispatcher.disconnect_slot(cb1.mock_slot, "topic1")
    assert len(bec_dispatcher.client.connector._topics_cb) == 0
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
        connector._buffered_connection._execute_callback(cb, {"data": rpc_msg}, {})

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
