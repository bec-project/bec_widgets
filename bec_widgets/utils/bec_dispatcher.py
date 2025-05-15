from __future__ import annotations

import collections
import random
import string
from collections.abc import Callable
from typing import TYPE_CHECKING, DefaultDict, Hashable, Union

import louie
import redis
from bec_lib.client import BECClient
from bec_lib.logger import bec_logger
from bec_lib.redis_connector import MessageObject, RedisConnector
from bec_lib.service_config import ServiceConfig
from qtpy.QtCore import QObject
from qtpy.QtCore import Signal as pyqtSignal

from bec_widgets.utils.serialization import register_serializer_extension

logger = bec_logger.logger

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.endpoints import EndpointInfo

    from bec_widgets.utils.rpc_server import RPCServer


class QtThreadSafeCallback(QObject):
    """QtThreadSafeCallback is a wrapper around a callback function to make it thread-safe for Qt."""

    cb_signal = pyqtSignal(dict, dict)

    def __init__(self, cb: Callable, cb_info: dict | None = None):
        """
        Initialize the QtThreadSafeCallback.

        Args:
            cb (Callable): The callback function to be wrapped.
            cb_info (dict, optional): Additional information about the callback. Defaults to None.
        """
        super().__init__()
        self.cb_info = cb_info

        self.cb = cb
        self.cb_ref = louie.saferef.safe_ref(cb)
        self.cb_signal.connect(self.cb)
        self.topics = set()

    def __hash__(self):
        # make 2 differents QtThreadSafeCallback to look
        # identical when used as dictionary keys, if the
        # callback is the same
        return f"{id(self.cb_ref)}{self.cb_info}".__hash__()

    def __eq__(self, other):
        if not isinstance(other, QtThreadSafeCallback):
            return False
        return self.cb_ref == other.cb_ref and self.cb_info == other.cb_info

    def __call__(self, msg_content, metadata):
        if self.cb_ref() is None:
            # callback has been deleted
            return
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
    client: BECClient
    cli_server: RPCServer | None = None

    def __new__(
        cls,
        client=None,
        config: str | ServiceConfig | None = None,
        gui_id: str | None = None,
        *args,
        **kwargs,
    ):
        if cls._instance is None:
            cls._instance = super(BECDispatcher, cls).__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self, client=None, config: str | ServiceConfig | None = None, gui_id: str = None):
        if self._initialized:
            return

        self._registered_slots: DefaultDict[Hashable, QtThreadSafeCallback] = (
            collections.defaultdict()
        )
        self.client = client

        if self.client is None:
            if config is not None:
                if not isinstance(config, ServiceConfig):
                    # config is supposed to be a path
                    config = ServiceConfig(config)
            self.client = BECClient(
                config=config, connector_cls=QtRedisConnector, name="BECWidgets"
            )
        else:
            if self.client.started:
                # have to reinitialize client to use proper connector
                logger.info("Shutting down BECClient to switch to QtRedisConnector")
                self.client.shutdown()
            self.client._BECClient__init_params["connector_cls"] = QtRedisConnector

        try:
            self.client.start()
        except redis.exceptions.ConnectionError:
            logger.warning("Could not connect to Redis, skipping start of BECClient.")

        register_serializer_extension()

        logger.success("Initialized BECDispatcher")

        self.start_cli_server(gui_id=gui_id)
        self._initialized = True

    @classmethod
    def reset_singleton(cls):
        """
        Reset the singleton instance of the BECDispatcher.
        """
        cls._instance = None
        cls._initialized = False

    def connect_slot(
        self,
        slot: Callable,
        topics: EndpointInfo | str | list[EndpointInfo] | list[str],
        cb_info: dict | None = None,
        **kwargs,
    ) -> None:
        """Connect widget's qt slot, so that it is called on new pub/sub topic message.

        Args:
            slot (Callable): A slot method/function that accepts two inputs: content and metadata of
                the corresponding pub/sub message
            topics EndpointInfo | str | list[EndpointInfo] | list[str]: A topic or list of topics that can typically be acquired via bec_lib.MessageEndpoints
            cb_info (dict | None): A dictionary containing information about the callback. Defaults to None.
        """
        qt_slot = QtThreadSafeCallback(cb=slot, cb_info=cb_info)
        if qt_slot not in self._registered_slots:
            self._registered_slots[qt_slot] = qt_slot
        qt_slot = self._registered_slots[qt_slot]
        self.client.connector.register(topics, cb=qt_slot, **kwargs)
        topics_str, _ = self.client.connector._convert_endpointinfo(topics)
        qt_slot.topics.update(set(topics_str))

    def disconnect_slot(
        self, slot: Callable, topics: EndpointInfo | str | list[EndpointInfo] | list[str]
    ):
        """
        Disconnect a slot from a topic.

        Args:
            slot(Callable): The slot to disconnect
            topics EndpointInfo | str | list[EndpointInfo] | list[str]: A topic or list of topics to unsub from.
        """
        # find the right slot to disconnect from ;
        # slot callbacks are wrapped in QtThreadSafeCallback objects,
        # but the slot we receive here is the original callable
        for connected_slot in self._registered_slots.values():
            if connected_slot.cb == slot:
                break
        else:
            return
        self.client.connector.unregister(topics, cb=connected_slot)
        topics_str, _ = self.client.connector._convert_endpointinfo(topics)
        self._registered_slots[connected_slot].topics.difference_update(set(topics_str))
        if not self._registered_slots[connected_slot].topics:
            del self._registered_slots[connected_slot]

    def disconnect_topics(self, topics: Union[str, list]):
        """
        Disconnect all slots from a topic.

        Args:
            topics(Union[str, list]): The topic(s) to disconnect from
        """
        self.client.connector.unregister(topics)
        topics_str, _ = self.client.connector._convert_endpointinfo(topics)

        remove_slots = []
        for connected_slot in self._registered_slots.values():
            connected_slot.topics.difference_update(set(topics_str))

            if not connected_slot.topics:
                remove_slots.append(connected_slot)

        for connected_slot in remove_slots:
            self._registered_slots.pop(connected_slot, None)

    def disconnect_all(self, *args, **kwargs):
        """
        Disconnect all slots from all topics.

        Args:
            *args: Arbitrary positional arguments
            **kwargs: Arbitrary keyword arguments
        """
        # pylint: disable=protected-access
        self.disconnect_topics(self.client.connector._topics_cb)

    def start_cli_server(self, gui_id: str | None = None):
        """
        Start the CLI server.

        Args:
            gui_id(str, optional): The GUI ID. Defaults to None. If None, a unique identifier will be generated.
        """
        # pylint: disable=import-outside-toplevel
        from bec_widgets.utils.rpc_server import RPCServer

        if gui_id is None:
            gui_id = self.generate_unique_identifier()

        if not self.client.started:
            logger.error("Cannot start CLI server without a running client")
            return
        self.cli_server = RPCServer(gui_id, dispatcher=self, client=self.client)
        logger.success(f"Started CLI server with gui_id: {gui_id}")

    def stop_cli_server(self):
        """
        Stop the CLI server.
        """
        if self.cli_server is None:
            logger.error("Cannot stop CLI server without starting it first")
            return
        self.cli_server.shutdown()
        self.cli_server = None
        logger.success("Stopped CLI server")

    @staticmethod
    def generate_unique_identifier(length: int = 4) -> str:
        """
        Generate a unique identifier for the application.

        Args:
            length: The length of the identifier. Defaults to 4.

        Returns:
            str: The unique identifier.
        """
        allowed_chars = string.ascii_lowercase + string.digits
        return "".join(random.choices(allowed_chars, k=length))
