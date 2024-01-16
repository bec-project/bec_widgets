# TODO last backup

# todo super last refactor

from __future__ import annotations

import argparse
import itertools
import os
from collections.abc import Callable
from typing import Union

from bec_lib import BECClient, messages, ServiceConfig
from bec_lib.redis_connector import RedisConsumerThreaded
from qtpy.QtCore import QObject, Signal as pyqtSignal

# Adding a new pyqt signal requires a class factory, as they must be part of the class definition
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
    """Utility class to keep track of slots connected to a particular redis consumer"""

    def __init__(self, bec_config=None):
        super().__init__()
        self.client = BECClient()

        # TODO: this is a workaround for now to provide service config within qtdesigner, but is
        # it possible to provide config via a cli arg?
        if bec_config is None and os.path.isfile("bec_config.yaml"):
            bec_config = "bec_config.yaml"

        self.client.initialize(config=ServiceConfig(config_path=bec_config))
        self._connections = {}

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

        # Ensure topics_key is a tuple, whether single_callback_for_all_topics is True or False.
        topics_key = tuple(sorted(topics)) if single_callback_for_all_topics else tuple(topics)

        if topics_key not in self._connections:
            self._connections[topics_key] = self._create_connection(topics)
        connection = self._connections[topics_key]
        if slot not in connection.slots:
            connection.signal.connect(slot)
            connection.slots.add(slot)

    def _create_connection(self, topics: list) -> _Connection:
        """Creates a new connection for given topics."""

        def cb(msg):
            msg = messages.MessageReader.loads(msg.value)
            if not isinstance(msg, list):
                msg = [msg]
            for msg_i in msg:
                for connection_key, connection in self._connections.items():
                    if set(topics).intersection(
                        connection_key if isinstance(connection_key, tuple) else [connection_key]
                    ):
                        connection.signal.emit(msg_i.content, msg_i.metadata)

        consumer = self.client.connector.consumer(topics=topics, cb=cb)
        consumer.start()
        return _Connection(consumer)

    def _disconnect_slot_from_topic(self, slot: Callable, topic: str) -> None:
        """A helper method to disconnect a slot from a specific topic.

        Args:
            slot (Callable): A slot to be disconnected
            topic (str): A corresponding topic that can typically be acquired via
                bec_lib.MessageEndpoints
        """
        connection = self._connections.get(topic)
        if connection and slot in connection.slots:
            connection.signal.disconnect(slot)
            connection.slots.remove(slot)
            if not connection.slots:
                connection.consumer.shutdown()
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

        for key, connection in list(self._connections.items()):
            if slot in connection.slots:
                common_topics = set(topics).intersection(key)
                if common_topics:
                    remaining_topics = set(key) - set(topics)
                    # Disconnect slot from common topics
                    connection.signal.disconnect(slot)
                    connection.slots.remove(slot)
                    if not connection.slots:
                        print(f"{connection.consumer} is shutting down")
                        connection.consumer.shutdown()
                        del self._connections[key]
                    # Reconnect slot to remaining topics if any
                    if remaining_topics:
                        self.connect_slot(slot, list(remaining_topics), True)

    def disconnect_all(self):
        """Disconnect all slots from all topics."""
        for key, connection in list(self._connections.items()):
            for slot in list(connection.slots):
                self._disconnect_slot_from_topic(slot, key)

            if key in self._connections and not connection.slots:
                connection.consumer.shutdown()
                del self._connections[key]


parser = argparse.ArgumentParser()
parser.add_argument("--bec-config", default=None)
args, _ = parser.parse_known_args()

bec_dispatcher = _BECDispatcher(args.bec_config)
