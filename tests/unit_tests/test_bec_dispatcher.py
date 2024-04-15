# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import time
from unittest import mock

import pytest
import redis
from bec_lib.connector import MessageObject
from bec_lib.messages import ScanMessage
from bec_lib.redis_connector import RedisConnector
from bec_lib.serialization import MsgpackSerialization

from bec_widgets.utils.bec_dispatcher import QtRedisConnector


@pytest.fixture
def bec_dispatcher_w_connector(bec_dispatcher, topics_msg_list):
    def pubsub_msg_generator():
        for topic, msg in topics_msg_list:
            yield {"channel": topic.encode(), "pattern": None, "data": msg}
        while True:
            time.sleep(0.2)
            yield StopIteration

    with mock.patch("redis.Redis"):
        pubsub = redis.Redis().pubsub()
        messages = pubsub_msg_generator()
        pubsub.get_message.side_effect = lambda timeout: next(messages)
        connector = QtRedisConnector("localhost:1")
        bec_dispatcher.client.connector = connector
        yield bec_dispatcher


dummy_msg = MsgpackSerialization.dumps(ScanMessage(point_id=0, scan_id="0", data={}))


@pytest.mark.parametrize(
    "topics_msg_list",
    [
        (
            ("topic1", dummy_msg),
            ("topic2", dummy_msg),
            ("topic3", dummy_msg),
        )
    ],
)
def test_dispatcher_disconnect_all(bec_dispatcher_w_connector, qtbot):
    bec_dispatcher = bec_dispatcher_w_connector
    cb1 = mock.Mock(spec=[])
    cb2 = mock.Mock(spec=[])

    bec_dispatcher.connect_slot(cb1, "topic1")
    bec_dispatcher.connect_slot(cb1, "topic2")
    bec_dispatcher.connect_slot(cb2, "topic2")
    bec_dispatcher.connect_slot(cb2, "topic3")
    assert len(bec_dispatcher.client.connector._topics_cb) == 3

    bec_dispatcher.disconnect_all()

    assert len(bec_dispatcher.client.connector._topics_cb) == 0
