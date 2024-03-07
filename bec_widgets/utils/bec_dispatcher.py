from __future__ import annotations

import argparse
import itertools
import os
from collections.abc import Callable
from typing import Union

import redis
from bec_lib import BECClient, ServiceConfig
from qtpy.QtCore import QObject
from qtpy.QtCore import Signal as pyqtSignal

from bec_lib.endpoints import EndpointInfo

# Adding a new pyqt signal requires a class factory, as they must be part of the class definition
# and cannot be dynamically added as class attributes after the class has been defined.
_signal_class_factory = (
    type(f"Signal{i}", (QObject,), dict(signal=pyqtSignal(dict, dict))) for i in itertools.count()
)


class _Connection:
    """Utility class to keep track of slots connected to a particular redis connector"""

    def __init__(self, callback) -> None:
        self.callback = callback

        self.slots = set()
        # keep a reference to a new signal class, so it is not gc'ed
        self._signal_container = next(_signal_class_factory)()
        self.signal: pyqtSignal = self._signal_container.signal


class _BECDispatcher(QObject):
    """Utility class to keep track of slots connected to a particular redis connector"""

    def __init__(self, bec_config=None):
        super().__init__()
        self.client = BECClient()

        # TODO: this is a workaround for now to provide service config within qtdesigner, but is
        # it possible to provide config via a cli arg?
        if bec_config is None and os.path.isfile("bec_config.yaml"):
            bec_config = "bec_config.yaml"

        try:
            self.client.initialize(config=ServiceConfig(config_path=bec_config))
        except redis.exceptions.ConnectionError as e:
            print(f"Failed to initialize BECClient: {e}")
        self._connections = {}

    def connect_slot(
        self,
        slot: Callable,
        topics: Union[EndpointInfo, str, list[Union[EndpointInfo, str]]],
        single_callback_for_all_topics=False,
    ) -> None:
        """Connect widget's pyqt slot, so that it is called on new pub/sub topic message.

        Args:
            slot (Callable): A slot method/function that accepts two inputs: content and metadata of
                the corresponding pub/sub message
            topics (EndpointInfo | str | list): A topic or list of topics that can typically be acquired via bec_lib.MessageEndpoints
            single_callback_for_all_topics (bool): If True, use the same callback for all topics, otherwise use
                separate callbacks.
        """
        # Normalise the topics input
        if isinstance(topics, (str, EndpointInfo)):
            topics = [topics]

        endpoint_to_consumer_type = {
            (topic.endpoint if isinstance(topic, EndpointInfo) else topic): (
                topic.message_op.name if isinstance(topic, EndpointInfo) else "SEND"
            )
            for topic in topics
        }

        # Group topics by consumer type
        consumer_type_to_endpoints = {}
        for endpoint, consumer_type in endpoint_to_consumer_type.items():
            if consumer_type not in consumer_type_to_endpoints:
                consumer_type_to_endpoints[consumer_type] = []
            consumer_type_to_endpoints[consumer_type].append(endpoint)

        for consumer_type, endpoints in consumer_type_to_endpoints.items():
            topics_key = (
                tuple(sorted(endpoints)) if single_callback_for_all_topics else tuple(endpoints)
            )

            if topics_key not in self._connections:
                self._connections[topics_key] = self._create_connection(endpoints, consumer_type)
            connection = self._connections[topics_key]

            if slot not in connection.slots:
                connection.signal.connect(slot)
                connection.slots.add(slot)

    def _create_connection(self, topics: list, consumer_type: str) -> _Connection:
        """Creates a new connection for given topics."""

        def cb(msg):
            if isinstance(msg, dict):
                msg = msg["data"]
            else:
                msg = msg.value
            for connection_key, connection in self._connections.items():
                if set(topics).intersection(connection_key):
                    if isinstance(msg, list):
                        msg = msg[0]
                    connection.signal.emit(msg.content, msg.metadata)

        try:
            if consumer_type == "STREAM":
                self.client.connector.register_stream(topics=topics, cb=cb, newest_only=True)
            else:
                self.client.connector.register(topics=topics, cb=cb)
        except redis.exceptions.ConnectionError:
            print("Could not connect to Redis, skipping registration of topics.")

        return _Connection(cb)

    def _do_disconnect_slot(self, topic, slot):
        print(f"Disconnecting {slot} from {topic}")
        connection = self._connections[topic]
        try:
            connection.signal.disconnect(slot)
        except TypeError:
            print(f"Could not disconnect slot:'{slot}' from topic:'{topic}'")
            print("Continue to remove slot:'{slot}' from 'connection.slots'.")
        connection.slots.remove(slot)
        if not connection.slots:
            del self._connections[topic]

    def _disconnect_slot_from_topic(self, slot: Callable, topic: str) -> None:
        """A helper method to disconnect a slot from a specific topic.

        Args:
            slot (Callable): A slot to be disconnected
            topic (str): A corresponding topic that can typically be acquired via
                bec_lib.MessageEndpoints
        """
        connection = self._connections.get(topic)
        if connection and slot in connection.slots:
            self._do_disconnect_slot(topic, slot)

    def disconnect_slot(self, slot: Callable, topics: Union[str, list]) -> None:
        """Disconnect widget's pyqt slot from pub/sub updates on a topic.

        Args:
            slot (Callable): A slot to be disconnected
            topics (str | list): A corresponding topic or list of topics that can typically be acquired via
                bec_lib.MessageEndpoints
        """
        # Normalise the topics input
        if isinstance(topics, (str, EndpointInfo)):
            topics = [topics]

        endpoints = [
            topic.endpoint if isinstance(topic, EndpointInfo) else topic for topic in topics
        ]

        for key, connection in list(self._connections.items()):
            if slot in connection.slots:
                common_topics = set(endpoints).intersection(key)
                if common_topics:
                    remaining_topics = set(key) - set(endpoints)
                    # Disconnect slot from common topics
                    self._do_disconnect_slot(key, slot)
                    # Reconnect slot to remaining topics if any
                    if remaining_topics:
                        self.connect_slot(slot, list(remaining_topics), True)

    def disconnect_all(self):
        """Disconnect all slots from all topics."""
        for key, connection in list(self._connections.items()):
            for slot in list(connection.slots):
                self._disconnect_slot_from_topic(slot, key)


# variable holding the Singleton instance of BECDispatcher
_bec_dispatcher = None


def BECDispatcher():
    global _bec_dispatcher
    if _bec_dispatcher is None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--bec-config", default=None)
        args, _ = parser.parse_known_args()

        _bec_dispatcher = _BECDispatcher(args.bec_config)
    return _bec_dispatcher
