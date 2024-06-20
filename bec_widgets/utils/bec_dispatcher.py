from __future__ import annotations

import argparse
import collections
from collections.abc import Callable
from typing import TYPE_CHECKING, Union

import redis
from bec_lib.client import BECClient
from bec_lib.redis_connector import MessageObject, RedisConnector
from bec_lib.service_config import ServiceConfig
from qtpy.QtCore import PYQT5, PYQT6, PYSIDE2, PYSIDE6, QCoreApplication, QObject
from qtpy.QtCore import Signal as pyqtSignal

if TYPE_CHECKING:
    from bec_lib.endpoints import EndpointInfo


class QtThreadSafeCallback(QObject):
    cb_signal = pyqtSignal(dict, dict)

    def __init__(self, cb):
        super().__init__()

        self.cb = cb
        self.cb_signal.connect(self.cb)

    def __hash__(self):
        # make 2 differents QtThreadSafeCallback to look
        # identical when used as dictionary keys, if the
        # callback is the same
        return id(self.cb)

    def __call__(self, msg_content, metadata):
        self.cb_signal.emit(msg_content, metadata)


class QtRedisConnector(RedisConnector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _execute_callback(self, cb, msg, kwargs):
        if not isinstance(cb, QtThreadSafeCallback):
            return super()._execute_callback(cb, msg, kwargs)
        # if msg.msg_type == "bundle_message":
        #    # big warning: how to handle bundle messages?
        #    # message with messages inside ; which slot to call?
        #    # bundle_msg = msg
        #    # for msg in bundle_msg:
        #    #    ...
        #    # for now, only consider the 1st message
        #    msg = msg[0]
        #    raise RuntimeError(f"
        if isinstance(msg, MessageObject):
            if isinstance(msg.value, list):
                msg = msg.value[0]
            else:
                msg = msg.value

            # we can notice kwargs are lost when passed to Qt slot
            metadata = msg.metadata
            cb(msg.content, metadata)
        else:
            # from stream
            msg = msg["data"]
            cb(msg.content, msg.metadata)


class BECDispatcher:
    """Utility class to keep track of slots connected to a particular redis connector"""

    _instance = None
    _initialized = False
    qapp = None

    def __new__(cls, client=None, config: str = None, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BECDispatcher, cls).__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self, client=None, config: str = None):
        if self._initialized:
            return

        if not QCoreApplication.instance():
            BECDispatcher.qapp = QCoreApplication([])

        self._slots = collections.defaultdict(set)
        self.client = client

        if self.client is None:
            if config is not None:
                host, port = config.split(":")
                redis_config = {"host": host, "port": port}
                self.client = BECClient(
                    config=ServiceConfig(redis=redis_config), connector_cls=QtRedisConnector
                )  # , forced=True)
            else:
                self.client = BECClient(connector_cls=QtRedisConnector)  # , forced=True)
        else:
            if self.client.started:
                # have to reinitialize client to use proper connector
                self.client.shutdown()
            self.client._BECClient__init_params["connector_cls"] = QtRedisConnector

        try:
            self.client.start()
        except redis.exceptions.ConnectionError:
            print("Could not connect to Redis, skipping start of BECClient.")

        self._initialized = True

    @classmethod
    def reset_singleton(cls):
        cls._instance = None
        cls._initialized = False

        if not cls.qapp:
            return

        # shutdown QCoreApp if it exists
        if PYQT5 or PYQT6:
            cls.qapp.exit()
        elif PYSIDE2 or PYSIDE6:
            cls.qapp.shutdown()
        cls.qapp = None

    def connect_slot(
        self, slot: Callable, topics: Union[EndpointInfo, str, list[Union[EndpointInfo, str]]]
    ) -> None:
        """Connect widget's pyqt slot, so that it is called on new pub/sub topic message.

        Args:
            slot (Callable): A slot method/function that accepts two inputs: content and metadata of
                the corresponding pub/sub message
            topics (EndpointInfo | str | list): A topic or list of topics that can typically be acquired via bec_lib.MessageEndpoints
        """
        slot = QtThreadSafeCallback(slot)
        self.client.connector.register(topics, cb=slot)
        topics_str, _ = self.client.connector._convert_endpointinfo(topics)
        self._slots[slot].update(set(topics_str))

    def disconnect_slot(self, slot: Callable, topics: Union[str, list]):
        # find the right slot to disconnect from ;
        # slot callbacks are wrapped in QtThreadSafeCallback objects,
        # but the slot we receive here is the original callable
        for connected_slot in self._slots:
            if connected_slot.cb == slot:
                break
        else:
            return
        self.client.connector.unregister(topics, cb=connected_slot)
        topics_str, _ = self.client.connector._convert_endpointinfo(topics)
        self._slots[slot].difference_update(set(topics_str))
        if not self._slots[slot]:
            del self._slots[slot]

    def disconnect_topics(self, topics: Union[str, list]):
        self.client.connector.unregister(topics)
        topics_str, _ = self.client.connector._convert_endpointinfo(topics)
        for slot in list(self._slots.keys()):
            slot_topics = self._slots[slot]
            slot_topics.difference_update(set(topics_str))
            if not slot_topics:
                del self._slots[slot]

    def disconnect_all(self, *args, **kwargs):
        self.disconnect_topics(self.client.connector._topics_cb)
