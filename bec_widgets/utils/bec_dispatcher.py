from __future__ import annotations

import argparse
import itertools
import os
from collections.abc import Callable
from typing import Union

from bec_lib import BECClient, messages, ServiceConfig
from bec_lib.redis_connector import RedisConsumerThreaded
from qtpy.QtCore import QObject, Signal as pyqtSignal

# Adding a new pyqt signal requres a class factory, as they must be part of the class definition
# and cannot be dynamically added as class attributes after the class has been defined.
_signal_class_factory = (
    type(f"Signal{i}", (QObject,), dict(signal=pyqtSignal(dict, dict))) for i in itertools.count()
)


class _Connection:
    """Utility class to keep track of slots connected to a particular redis consumer"""

    def __init__(self, consumer) -> None:
        self.consumer: RedisConsumerThreaded = consumer
        self.slots = set()
        # keep a reference to a new signal class, so it is not gc'ed
        self._signal_container = next(_signal_class_factory)()
        self.signal: pyqtSignal = self._signal_container.signal


class _BECDispatcher(QObject):
    def __init__(self, bec_config=None):
        super().__init__()
        self.client = BECClient()

        # TODO: this is a workaround for now to provide service config within qtdesigner, but is
        # it possible to provide config via a cli arg?
        if bec_config is None and os.path.isfile("bec_config.yaml"):
            bec_config = "bec_config.yaml"

        self.client.initialize(config=ServiceConfig(config_path=bec_config))
        self._connections = {}

    def _connect_slot_to_topic(self, slot: Callable, topic: str) -> None:
        """A helper method to connect a slot to a specific topic

        Args:
            slot (Callable): A slot method/function that accepts two inputs: content and metadata of
                the corresponding pub/sub message
            topic (str): A topic that can typically be acquired via bec_lib.MessageEndpoints
        """
        # create new connection for topic if it doesn't exist
        if topic not in self._connections:

            def cb(msg):
                msg = messages.MessageReader.loads(msg.value)
                # TODO: this can could be replaced with a simple
                # self._connections[topic].signal.emit(msg.content, msg.metadata)
                # once all dispatcher.connect_slot calls are made with a single topic only
                if not isinstance(msg, list):
                    msg = [msg]
                for msg_i in msg:
                    self._connections[topic].signal.emit(msg_i.content, msg_i.metadata)

            consumer = self.client.connector.consumer(topics=topic, cb=cb)
            consumer.start()

            self._connections[topic] = _Connection(consumer)

        # connect slot if it's not connected
        if slot not in self._connections[topic].slots:
            self._connections[topic].signal.connect(slot)
            self._connections[topic].slots.add(slot)

    def _connect_slot_to_multiple_topics(self, slot: Callable, topics: list) -> None:
        """
        A helper method to connect a slot to multiple topics using a single callback.
        Args:
            slot (Callable): A slot method/function that accepts two inputs: content and metadata of
                the corresponding pub/sub message
            topics (list): A list of topics that can typically be acquired via bec_lib.MessageEndpoints.
        """

        # Creating a unique key for this combination of topics
        topics_key = tuple(sorted(topics))

        if topics_key not in self._connections:

            def cb(msg):
                msg = messages.MessageReader.loads(msg.value)
                self._connections[topics_key].signal.emit(msg.content, msg.metadata)

            consumer = self.client.connector.consumer(topics=topics, cb=cb)
            consumer.start()

            self._connections[topics_key] = _Connection(consumer)

        if slot not in self._connections[topics_key].slots:
            self._connections[topics_key].signal.connect(slot)
            self._connections[topics_key].slots.add(slot)

    def connect_slot(
        self, slot: Callable, topics: Union[str, list], single_callback_for_all_topics=False
    ) -> None:
        """Connect widget's pyqt slot, so that it is called on new pub/sub topic message.

        Args:
            slot (Callable): A slot method/function that accepts two inputs: content and metadata of
                the corresponding pub/sub message
            topics (str | list): A topic or list of topics that can typically be acquired via bec_lib.MessageEndpoints
            single_callback_for_all_topics (bool): If True, use the same callback for all topics, otherwise use
                separate callbacks.
        """
        if isinstance(topics, str):
            topics = [topics]

        if single_callback_for_all_topics:
            self._connect_slot_to_multiple_topics(slot, topics)
        else:
            for topic in topics:
                self._connect_slot_to_topic(slot, topic)

    def _disconnect_slot_from_topic(self, slot: Callable, topic: str) -> None:
        """A helper method to disconnect a slot from a specific topic.

        Args:
            slot (Callable): A slot to be disconnected
            topic (str): A corresponding topic that can typically be acquired via
                bec_lib.MessageEndpoints
        """
        if topic not in self._connections:
            return

        if slot not in self._connections[topic].slots:
            return

        self._connections[topic].signal.disconnect(slot)
        self._connections[topic].slots.remove(slot)

        if not self._connections[topic].slots:
            # shutdown consumer if there are no more connected slots
            self._connections[topic].consumer.shutdown()
            del self._connections[topic]

    def disconnect_slot(self, slot: Callable, topics: Union[str, list]) -> None:
        """Disconnect widget's pyqt slot from pub/sub updates on a topic.

        Args:
            slot (Callable): A slot to be disconnected
            topics (str | list): A corresponding topic or list of topics that can typically be acquired via
                bec_lib.MessageEndpoints
        """
        if isinstance(topics, str):
            topics = [topics]

        for topic in topics:
            self._disconnect_slot_from_topic(slot, topic)

    def disconnect_all(self):
        """Disconnect all slots from all topics."""
        for key, connection in list(self._connections.items()):
            for slot in list(connection.slots):
                self._disconnect_slot_from_topic(slot, key)  # Updated to pass key

            # Check if the topic still exists before trying to shutdown and delete
            if key in self._connections and not connection.slots:
                connection.consumer.shutdown()
                del self._connections[key]


parser = argparse.ArgumentParser()
parser.add_argument("--bec-config", default=None)
args, _ = parser.parse_known_args()

bec_dispatcher = _BECDispatcher(args.bec_config)
