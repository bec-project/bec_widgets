from unittest.mock import Mock

import pytest
from bec_lib.messages import ScanMessage
from bec_lib.connector import MessageObject

# TODO: find a better way to mock singletons
from bec_widgets.bec_dispatcher import _BECDispatcher

msg = MessageObject(topic="", value=ScanMessage(point_id=0, scanID=0, data={}).dumps())


@pytest.fixture(name="bec_dispatcher")
def _bec_dispatcher():
    bec_dispatcher = _BECDispatcher()
    yield bec_dispatcher


@pytest.fixture(name="consumer")
def _consumer(bec_dispatcher):
    bec_dispatcher.client.connector.consumer = Mock()
    consumer = bec_dispatcher.client.connector.consumer
    yield consumer


@pytest.mark.filterwarnings("ignore:Failed to connect to redis.")
def test_connect_one_slot(bec_dispatcher, consumer):
    slot1 = Mock()
    bec_dispatcher.connect_slot(slot=slot1, topic="topic0")
    consumer.assert_called_once()
    # trigger consumer callback as if a message was published
    consumer.call_args.kwargs["cb"](msg)
    slot1.assert_called_once()
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 2


def test_connect_identical(bec_dispatcher, consumer):
    slot1 = Mock()
    bec_dispatcher.connect_slot(slot=slot1, topic="topic0")
    bec_dispatcher.connect_slot(slot=slot1, topic="topic0")
    consumer.assert_called_once()

    consumer.call_args.kwargs["cb"](msg)
    slot1.assert_called_once()


def test_connect_many_slots_one_topic(bec_dispatcher, consumer):
    slot1, slot2 = Mock(), Mock()
    bec_dispatcher.connect_slot(slot=slot1, topic="topic0")
    consumer.assert_called_once()
    bec_dispatcher.connect_slot(slot=slot2, topic="topic0")
    consumer.assert_called_once()
    # trigger consumer callback as if a message was published
    consumer.call_args.kwargs["cb"](msg)
    slot1.assert_called_once()
    slot2.assert_called_once()
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 2
    assert slot2.call_count == 2


def test_connect_one_slot_many_topics(bec_dispatcher, consumer):
    slot1 = Mock()
    bec_dispatcher.connect_slot(slot=slot1, topic="topic0")
    assert consumer.call_count == 1
    bec_dispatcher.connect_slot(slot=slot1, topic="topic1")
    assert consumer.call_count == 2
    # trigger consumer callback as if a message was published
    consumer.call_args_list[0].kwargs["cb"](msg)
    slot1.assert_called_once()
    consumer.call_args_list[1].kwargs["cb"](msg)
    assert slot1.call_count == 2


def test_disconnect_one_slot_one_topic(bec_dispatcher, consumer):
    slot1, slot2 = Mock(), Mock()
    bec_dispatcher.connect_slot(slot=slot1, topic="topic0")

    # disconnect using a different slot
    bec_dispatcher.disconnect_slot(slot=slot1, topic="topic1")
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 1

    # disconnect using a different topic
    bec_dispatcher.disconnect_slot(slot=slot2, topic="topic0")
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 2

    # disconnect using the right slot and topic
    bec_dispatcher.disconnect_slot(slot=slot1, topic="topic0")
    with pytest.raises(KeyError):
        consumer.call_args.kwargs["cb"](msg)


def test_disconnect_identical(bec_dispatcher, consumer):
    slot1 = Mock()
    bec_dispatcher.connect_slot(slot=slot1, topic="topic0")
    bec_dispatcher.connect_slot(slot=slot1, topic="topic0")
    bec_dispatcher.disconnect_slot(slot=slot1, topic="topic0")
    with pytest.raises(KeyError):
        consumer.call_args.kwargs["cb"](msg)


def test_disconnect_many_slots_one_topic(bec_dispatcher, consumer):
    slot1, slot2, slot3 = Mock(), Mock(), Mock()
    bec_dispatcher.connect_slot(slot=slot1, topic="topic0")
    bec_dispatcher.connect_slot(slot=slot2, topic="topic0")

    # disconnect using a different slot
    bec_dispatcher.disconnect_slot(slot3, topic="topic0")
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 1
    assert slot2.call_count == 1

    # disconnect using a different topic
    bec_dispatcher.disconnect_slot(slot1, topic="topic1")
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 2
    assert slot2.call_count == 2

    # disconnect using the right slot and topic
    bec_dispatcher.disconnect_slot(slot1, topic="topic0")
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 2
    assert slot2.call_count == 3


def test_disconnect_one_slot_many_topics(bec_dispatcher, consumer):
    slot1, slot2 = Mock(), Mock()
    bec_dispatcher.connect_slot(slot=slot1, topic="topic0")
    bec_dispatcher.connect_slot(slot=slot1, topic="topic1")

    # disconnect using a different slot
    bec_dispatcher.disconnect_slot(slot=slot2, topic="topic0")
    consumer.call_args_list[0].kwargs["cb"](msg)
    assert slot1.call_count == 1
    consumer.call_args_list[1].kwargs["cb"](msg)
    assert slot1.call_count == 2

    # disconnect using a different topic
    bec_dispatcher.disconnect_slot(slot=slot1, topic="topic3")
    consumer.call_args_list[0].kwargs["cb"](msg)
    assert slot1.call_count == 3
    consumer.call_args_list[1].kwargs["cb"](msg)
    assert slot1.call_count == 4

    # disconnect using the right slot and topic
    bec_dispatcher.disconnect_slot(slot=slot1, topic="topic0")
    with pytest.raises(KeyError):
        consumer.call_args_list[0].kwargs["cb"](msg)
    consumer.call_args_list[1].kwargs["cb"](msg)
    assert slot1.call_count == 5

    bec_dispatcher.disconnect_slot(slot=slot1, topic="topic1")
    with pytest.raises(KeyError):
        consumer.call_args_list[0].kwargs["cb"](msg)
    with pytest.raises(KeyError):
        consumer.call_args_list[1].kwargs["cb"](msg)
    assert slot1.call_count == 5
