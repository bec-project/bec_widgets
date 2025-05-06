# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import threading
import time
from unittest import mock

import pytest
from bec_lib.messages import ScanMessage
from bec_lib.serialization import MsgpackSerialization

from bec_widgets.utils.bec_dispatcher import QtRedisConnector, QtThreadSafeCallback


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
