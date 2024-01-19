# pylint: disable=missing-function-docstring
from unittest.mock import Mock

import pytest
from bec_lib.messages import ScanMessage
from bec_lib.connector import MessageObject


msg = MessageObject(topic="", value=ScanMessage(point_id=0, scanID=0, data={}).dumps())


@pytest.fixture(name="consumer")
def _consumer(bec_dispatcher):
    bec_dispatcher.client.connector.consumer = Mock()
    consumer = bec_dispatcher.client.connector.consumer
    yield consumer


@pytest.mark.filterwarnings("ignore:Failed to connect to redis.")
def test_connect_one_slot(bec_dispatcher, consumer):
    slot1 = Mock()
    bec_dispatcher.connect_slot(slot=slot1, topics="topic0")
    consumer.assert_called_once()
    # trigger consumer callback as if a message was published
    consumer.call_args.kwargs["cb"](msg)
    slot1.assert_called_once()
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 2


def test_connect_identical(bec_dispatcher, consumer):
    slot1 = Mock()
    bec_dispatcher.connect_slot(slot=slot1, topics="topic0")
    bec_dispatcher.connect_slot(slot=slot1, topics="topic0")
    consumer.assert_called_once()

    consumer.call_args.kwargs["cb"](msg)
    slot1.assert_called_once()


def test_connect_many_slots_one_topic(bec_dispatcher, consumer):
    slot1, slot2 = Mock(), Mock()
    bec_dispatcher.connect_slot(slot=slot1, topics="topic0")
    consumer.assert_called_once()
    bec_dispatcher.connect_slot(slot=slot2, topics="topic0")
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
    bec_dispatcher.connect_slot(slot=slot1, topics="topic0")
    assert consumer.call_count == 1
    bec_dispatcher.connect_slot(slot=slot1, topics="topic1")
    assert consumer.call_count == 2
    # trigger consumer callback as if a message was published
    consumer.call_args_list[0].kwargs["cb"](msg)
    slot1.assert_called_once()
    consumer.call_args_list[1].kwargs["cb"](msg)
    assert slot1.call_count == 2


def test_disconnect_one_slot_one_topic(bec_dispatcher, consumer):
    slot1, slot2 = Mock(), Mock()
    bec_dispatcher.connect_slot(slot=slot1, topics="topic0")

    # disconnect using a different topic
    bec_dispatcher.disconnect_slot(slot=slot1, topics="topic1")
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 1

    # disconnect using a different slot
    bec_dispatcher.disconnect_slot(slot=slot2, topics="topic0")
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 2

    # disconnect using the right slot and topics
    bec_dispatcher.disconnect_slot(slot=slot1, topics="topic0")
    # reset count to 0 for slot
    slot1.reset_mock()
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 0


def test_disconnect_identical(bec_dispatcher, consumer):
    slot1 = Mock()
    # Try to connect slot twice
    bec_dispatcher.connect_slot(slot=slot1, topics="topic0")
    bec_dispatcher.connect_slot(slot=slot1, topics="topic0")

    # Test to call the slot once (slot should be not connected twice)
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 1

    # Disconnect the slot
    bec_dispatcher.disconnect_slot(slot=slot1, topics="topic0")

    # Test to call the slot once (slot should be not connected anymore), count remains 1
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 1


def test_disconnect_many_slots_one_topic(bec_dispatcher, consumer):
    slot1, slot2, slot3 = Mock(), Mock(), Mock()
    bec_dispatcher.connect_slot(slot=slot1, topics="topic0")
    bec_dispatcher.connect_slot(slot=slot2, topics="topic0")

    # disconnect using a different slot
    bec_dispatcher.disconnect_slot(slot3, topics="topic0")
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 1
    assert slot2.call_count == 1

    # disconnect using a different topics
    bec_dispatcher.disconnect_slot(slot1, topics="topic1")
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 2
    assert slot2.call_count == 2

    # disconnect using the right slot and topics
    bec_dispatcher.disconnect_slot(slot1, topics="topic0")
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 2
    assert slot2.call_count == 3


def test_disconnect_one_slot_many_topics(bec_dispatcher, consumer):
    slot1, slot2 = Mock(), Mock()
    bec_dispatcher.connect_slot(slot=slot1, topics="topic0")
    bec_dispatcher.connect_slot(slot=slot1, topics="topic1")

    # disconnect using a different slot
    bec_dispatcher.disconnect_slot(slot=slot2, topics="topic0")
    consumer.call_args_list[0].kwargs["cb"](msg)
    assert slot1.call_count == 1
    consumer.call_args_list[1].kwargs["cb"](msg)
    assert slot1.call_count == 2

    # disconnect using a different topics
    bec_dispatcher.disconnect_slot(slot=slot1, topics="topic3")
    consumer.call_args_list[0].kwargs["cb"](msg)
    assert slot1.call_count == 3
    consumer.call_args_list[1].kwargs["cb"](msg)
    assert slot1.call_count == 4

    # disconnect using the right slot and topics
    bec_dispatcher.disconnect_slot(slot=slot1, topics="topic0")
    # Calling disconnected topic0 should not call slot1
    consumer.call_args_list[0].kwargs["cb"](msg)
    assert slot1.call_count == 4
    # Calling topic1 should still call slot1
    consumer.call_args_list[1].kwargs["cb"](msg)
    assert slot1.call_count == 5

    # disconnect remaining topic1 from slot1, calling any topic should not increase count
    bec_dispatcher.disconnect_slot(slot=slot1, topics="topic1")
    consumer.call_args_list[0].kwargs["cb"](msg)
    consumer.call_args_list[1].kwargs["cb"](msg)
    assert slot1.call_count == 5


def test_disconnect_all(bec_dispatcher, consumer):
    # Mock slots to connect
    slot1, slot2, slot3 = Mock(), Mock(), Mock()

    # Connect slots to different topics
    bec_dispatcher.connect_slot(slot=slot1, topics="topic0")
    bec_dispatcher.connect_slot(slot=slot2, topics="topic1")
    bec_dispatcher.connect_slot(slot=slot3, topics="topic2")

    # Call disconnect_all method
    bec_dispatcher.disconnect_all()

    # Simulate messages and verify that none of the slots are called
    consumer.call_args_list[0].kwargs["cb"](msg)
    consumer.call_args_list[1].kwargs["cb"](msg)
    consumer.call_args_list[2].kwargs["cb"](msg)

    # Ensure that the slots have not been called
    assert slot1.call_count == 0
    assert slot2.call_count == 0
    assert slot3.call_count == 0

    # Also, check that the consumer for each topic is shutdown
    assert "topic0" not in bec_dispatcher._connections
    assert "topic1" not in bec_dispatcher._connections
    assert "topic2" not in bec_dispatcher._connections


def test_connect_one_slot_multiple_topics_single_callback(bec_dispatcher, consumer):
    slot1 = Mock()

    # Connect the slot to multiple topics using a single callback
    topics = ["topic1", "topic2"]
    bec_dispatcher.connect_slot(slot=slot1, topics=topics, single_callback_for_all_topics=True)

    # Verify the initial state
    assert len(bec_dispatcher._connections) == 1  # One connection for all topics
    assert len(bec_dispatcher._connections[tuple(sorted(topics))].slots) == 1  # One slot connected

    # Simulate messages being published on each topic
    for topic in topics:
        msg_with_topic = MessageObject(
            topic=topic, value=ScanMessage(point_id=0, scanID=0, data={}).dumps()
        )
        consumer.call_args.kwargs["cb"](msg_with_topic)

    # Verify that the slot is called once for each topic
    assert slot1.call_count == len(topics)

    # Verify that a single consumer is created for all topics
    consumer.assert_called_once()


def test_disconnect_all_with_single_callback_for_multiple_topics(bec_dispatcher, consumer):
    slot1 = Mock()

    # Connect the slot to multiple topics using a single callback
    topics = ["topic1", "topic2"]
    bec_dispatcher.connect_slot(slot=slot1, topics=topics, single_callback_for_all_topics=True)

    # Verify the initial state
    assert len(bec_dispatcher._connections) == 1  # One connection for all topics
    assert len(bec_dispatcher._connections[tuple(sorted(topics))].slots) == 1  # One slot connected

    # Call disconnect_all method
    bec_dispatcher.disconnect_all()

    # Verify that the slot is disconnected
    assert len(bec_dispatcher._connections) == 0  # All connections are removed
    assert slot1.call_count == 0  # Slot has not been called

    # Simulate messages and verify that the slot is not called
    consumer.call_args.kwargs["cb"](msg)
    assert slot1.call_count == 0  # Slot has not been called
