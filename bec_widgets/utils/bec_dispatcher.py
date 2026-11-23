from __future__ import annotations

import collections
import random
import string
import time
import weakref
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, DefaultDict, Hashable

import redis
from bec_lib.client import BECClient
from bec_lib.data_api import ScanTarget, SourceKey
from bec_lib.logger import bec_logger
from bec_lib.redis_connector import MessageObject, RedisConnector
from bec_lib.redis_connector.managed_redis_connection import ManagedRedisConnection
from bec_lib.service_config import ServiceConfig
from qtpy.QtCore import Signal as pyqtSignal

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.qt_data_subscription import QtDataSubscription
from bec_widgets.utils.qt_owned_callback import QtOwnedCallback
from bec_widgets.utils.rpc_logging import elapsed_seconds, format_elapsed
from bec_widgets.utils.serialization import register_serializer_extension

logger = bec_logger.logger

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.endpoints import EndpointInfo

    from bec_widgets.utils.bec_widget import BECWidget
    from bec_widgets.utils.rpc_server import RPCServer


def _log_rpc_dispatcher_receive(msg_content: Any, metadata: Any) -> None:
    if not isinstance(msg_content, dict) or not isinstance(metadata, dict):
        return
    request_id = metadata.get("request_id")
    method = msg_content.get("action")
    parameter = msg_content.get("parameter")
    if request_id is None or method is None or not isinstance(parameter, dict):
        return

    dispatch_received_at = time.time()
    sent_at = metadata.get("sent_at")
    deadline = metadata.get("deadline")
    timeout = metadata.get("timeout")
    dispatch_latency = elapsed_seconds(sent_at, dispatch_received_at)
    stale_on_dispatch = deadline is not None and dispatch_received_at > deadline
    target_gui_id = parameter.get("gui_id") or metadata.get("target_gui_id")

    logger.info(
        "GUI RPC dispatcher received request before Qt callback emit "
        f"request_id={request_id} method={method} receiver={metadata.get('receiver')} "
        f"target_gui_id={target_gui_id} object_name={metadata.get('object_name')} "
        f"timeout={timeout} dispatch_latency_s={format_elapsed(dispatch_latency)} "
        f"stale_on_dispatch={stale_on_dispatch}"
    )
    if stale_on_dispatch:
        logger.warning(
            "GUI RPC dispatcher received request after client timeout deadline "
            f"request_id={request_id} method={method} receiver={metadata.get('receiver')} "
            f"target_gui_id={target_gui_id} object_name={metadata.get('object_name')} "
            f"timeout={timeout} dispatch_latency_s={format_elapsed(dispatch_latency)}"
        )


class QtThreadSafeCallback(QtOwnedCallback):
    """
    QtThreadSafeCallback is a wrapper around a callback function to make it thread-safe for Qt.

    The callback and its owner are held as :class:`QtOwnedCallback` describes: weakly, and
    resolved only when a delivery occurs. Queued messages are delivered to the wrapper's
    own Qt slot.
    """

    cb_signal = pyqtSignal(dict, dict)

    def __init__(self, cb: Callable, cb_info: dict | None = None, owner: object | None = None):
        """
        Initialize the QtThreadSafeCallback.

        Args:
            cb (Callable): The callback function to be wrapped.
            cb_info (dict, optional): Subscription context delivered as ``metadata["cb_info"]``.
                Defaults to None.
            owner (object, optional): Lifetime anchor for non-method callables. Ignored for
                bound methods (their ``__self__`` is the owner). Defaults to None.
        """
        super().__init__(cb, owner)
        self.cb_info = cb_info
        self.cb_signal.connect(self._deliver)
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

    @SafeSlot(dict, dict)
    def _deliver(self, msg_content: dict, metadata: dict) -> None:
        """Resolve and retain a live callback for the duration of this delivery."""
        callback = self.live_callback()
        if callback is not None:
            if self.cb_info is not None:
                metadata = {**metadata, "cb_info": dict(self.cb_info)}
            callback(msg_content, metadata)

    def __call__(self, msg_content, metadata):
        if not self._active:
            return
        self.cb_signal.emit(msg_content, metadata)


class QtManagedRedisConnection(ManagedRedisConnection):
    def _execute_callback(self, cb, msg, kwargs):
        if not isinstance(cb, QtThreadSafeCallback):
            return super()._execute_callback(cb, msg, kwargs)

        if isinstance(msg, MessageObject):
            if isinstance(msg.value, list):
                msg = msg.value[0]
            else:
                msg = msg.value

            # we can notice kwargs are lost when passed to Qt slot
            metadata = msg.metadata
            _log_rpc_dispatcher_receive(msg.content, metadata)
            cb(msg.content, metadata)
        else:
            # from stream
            msg = msg["data"]
            _log_rpc_dispatcher_receive(msg.content, msg.metadata)
            cb(msg.content, msg.metadata)


class QtRedisConnector(RedisConnector):
    connector_cls = QtManagedRedisConnection


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
        # The DataAPI subscriptions of the widgets. Held here, not by the widgets, for
        # the reason the slot wrappers are: data threads emit on them.
        self._data_subscriptions: list[QtDataSubscription] = []

        if client is None:
            if config is not None and not isinstance(config, ServiceConfig):
                # config is supposed to be a path
                config = ServiceConfig(config)
            self.client = BECClient(
                config=config, connector_cls=QtRedisConnector, name="BECWidgets"
            )
        else:
            self.client = client
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
        owner: object | None = None,
        **kwargs,
    ) -> None:
        """Connect widget's qt slot, so that it is called on new pub/sub topic message.

        Args:
            slot (Callable): A slot method/function that accepts two inputs: content and metadata of
                the corresponding pub/sub message
            topics EndpointInfo | str | list[EndpointInfo] | list[str]: A topic or list of topics that can typically be acquired via bec_lib.MessageEndpoints
            cb_info (dict | None): Subscription context delivered as ``metadata["cb_info"]``.
                Defaults to None. Callbacks must use this context rather than ``QObject.sender()``.
            owner (object | None): Lifetime anchor for non-method callables (lambdas, partials,
                module functions): the subscription is released when the owner is cleaned up or
                destroyed. Bound methods already carry their owner and ignore this. Defaults to None.
        """
        if not hasattr(slot, "__self__") and owner is None:
            logger.warning(
                f"connect_slot({slot!r}) on {topics}: the callable has no owner, so it cannot be "
                "released automatically and stays subscribed until disconnect_slot is called. "
                "Pass owner=<widget> to bind its lifetime to a widget."
            )
        # Self-healing: reap subscriptions whose owners died without any close event
        # before adding new ones, so stale registrations never accumulate.
        self.cleanup_dead_slots()
        qt_slot = QtThreadSafeCallback(cb=slot, cb_info=cb_info, owner=owner)
        if not self.client.connector.any_stream_is_registered(topics, qt_slot):
            if qt_slot not in self._registered_slots:
                self._registered_slots[qt_slot] = qt_slot
            qt_slot = self._registered_slots[qt_slot]
            self.client.connector.register(topics, cb=qt_slot, **kwargs)
            topics_str, _ = self.client.connector.extract_raw_endpoints_from_info(topics)
            qt_slot.topics.update(set(topics_str))
        else:
            logger.warning(f"Attempted to create duplicate stream subscription for {topics=}")

    def disconnect_slot(
        self,
        slot: Callable,
        topics: EndpointInfo | str | list[EndpointInfo] | list[str] | None = None,
        cb_info: dict | None = None,
    ):
        """
        Disconnect a slot from topics.

        Among the wrappers matching the callback (and ``cb_info``, when given), every
        wrapper subscribed to any of the requested topics is released from exactly those
        topics — a topic list spanning several registrations of the same slot releases
        all of them. Without ``topics``, the slot is disconnected from everything it is
        subscribed to. If none of the wrappers is subscribed to the requested topics,
        nothing is released and a warning names the actual subscriptions — a blind
        unregister on the wrong wrapper would silently no-op.

        Args:
            slot(Callable): The slot to disconnect
            topics(EndpointInfo | str | list[EndpointInfo] | list[str] | None): A topic or
                list of topics to unsub from. None disconnects the slot from all its topics.
            cb_info(dict | None): When the same slot was registered multiple times with
                different cb_info payloads (e.g. per-signal async subscriptions), pass the
                payload to narrow the candidate registrations before the topic match.
        """
        # slot callbacks are wrapped in QtThreadSafeCallback objects,
        # but the slot we receive here is the original callable
        candidates = []
        for connected_slot in self._registered_slots.values():
            if connected_slot.cb != slot:
                continue
            if cb_info is not None and connected_slot.cb_info != cb_info:
                continue
            candidates.append(connected_slot)
        if topics is None:
            for connected_slot in candidates:
                self._release_slot(connected_slot)
            return
        topics_str, _ = self.client.connector.extract_raw_endpoints_from_info(topics)
        requested = set(topics_str)
        matched = False
        for connected_slot in candidates:
            overlap = connected_slot.topics & requested
            if not overlap:
                continue
            matched = True
            if not connected_slot.topics - overlap:
                # Fully emptied: release through _release_slot, which also invalidates the
                # wrapper so deliveries that are already queued are cancelled.
                self._release_slot(connected_slot)
                continue
            # unregister only what this wrapper actually holds; the same requested list
            # may span several wrappers of the same callback
            self.client.connector.unregister(list(overlap), cb=connected_slot)
            connected_slot.topics.difference_update(overlap)
        if not matched and candidates:
            logger.warning(
                f"disconnect_slot({slot!r}): no registration matches topics "
                f"{sorted(requested)}; the slot is subscribed to "
                f"{sorted(set().union(*(s.topics for s in candidates)))}. Nothing released."
            )

    def disconnect_topics(self, topics: str | list):
        """
        Disconnect all slots from a topic.

        Args:
            topics(Union[str, list]): The topic(s) to disconnect from
        """
        topics_str, _ = self.client.connector.extract_raw_endpoints_from_info(topics)

        remove_slots = []
        for connected_slot in list(self._registered_slots.values()):
            if not connected_slot.topics.difference(topics_str):
                connected_slot.invalidate()
                remove_slots.append(connected_slot)

        self.client.connector.unregister(topics)
        for connected_slot in self._registered_slots.values():
            connected_slot.topics.difference_update(topics_str)
        for connected_slot in remove_slots:
            self._registered_slots.pop(connected_slot, None)

    def disconnect_all(self, *args, **kwargs):
        """
        Disconnect all slots from all topics.

        Args:
            *args: Arbitrary positional arguments
            **kwargs: Arbitrary keyword arguments
        """
        topics = set()
        for connected_slot in self._registered_slots.values():
            topics.update(connected_slot.topics)
        if topics:
            self.disconnect_topics(list(topics))
        for subscription in list(self._data_subscriptions):
            self.disconnect_data_subscription(subscription)

    def connect_data_subscription(
        self,
        slot: Callable,
        sources: list[SourceKey] | None = None,
        scan: str | None = ScanTarget.LIVE,
        owner: object | None = None,
        progress_slot: Callable | None = None,
        **kwargs,
    ) -> QtDataSubscription:
        """
        Connect a widget's slot to data of the DataAPI, so that it is called on the Qt
        thread with every ``SubscriptionUpdate``.

        The counterpart of :meth:`connect_slot` for scan and device data: the dispatcher
        holds the subscription, never the widget, and releases it when the owner is cleaned
        up (:meth:`disconnect_owner`) or found dead (:meth:`cleanup_dead_slots`).

        Args:
            slot (Callable): A slot that accepts one ``SubscriptionUpdate``.
            sources (list[SourceKey] | None): The (device, entry) pairs to subscribe to.
            scan (str | None): ``ScanTarget.LIVE`` to follow the running scan, a scan id, or
                None for scan-less device streams.
            owner (object | None): Lifetime anchor for a slot that is not a bound method, as
                for :meth:`connect_slot`. Defaults to None.
            progress_slot (Callable | None): A slot that accepts the fraction (0..1) of a
                stored scan that is loaded. Defaults to None.
            **kwargs: Further options of ``QtDataSubscription`` (``min_emit_interval``,
                ``max_points``, ``size_limit_bytes``, ``devices``, ``correlation``, ...).

        Returns:
            QtDataSubscription: The subscription: its state (``groups``, ``routes``,
                ``scan_id``, ...) and what can be changed while it runs (``set_sources``,
                ``request_view``, ``confirm_size``). Pass it to
                :meth:`disconnect_data_subscription` to end it.
        """
        if not hasattr(slot, "__self__") and owner is None:
            logger.warning(
                f"connect_data_subscription({slot!r}): the callable has no owner, so it cannot "
                "be released automatically and stays subscribed until "
                "disconnect_data_subscription is called. Pass owner=<widget> to bind its "
                "lifetime to a widget."
            )
        self.cleanup_dead_slots()
        subscription = QtDataSubscription(
            self.client,
            slot,
            sources=sources,
            scan=scan,
            owner=owner,
            progress_slot=progress_slot,
            **kwargs,
        )
        self._data_subscriptions.append(subscription)
        return subscription

    def disconnect_data_subscription(self, subscription: QtDataSubscription | None) -> None:
        """
        End a subscription made with :meth:`connect_data_subscription`. Idempotent.

        Args:
            subscription (QtDataSubscription | None): The subscription; None is ignored.
        """
        if subscription is None:
            return
        subscription.close()
        if subscription in self._data_subscriptions:
            self._data_subscriptions.remove(subscription)

    def data_subscriptions(self, owner: object) -> list[QtDataSubscription]:
        """
        The data subscriptions of one owner.

        Args:
            owner (object): The widget whose slots they deliver to.

        Returns:
            list[QtDataSubscription]: Its open subscriptions.
        """
        return [s for s in self._data_subscriptions if s.owner is owner]

    def disconnect_owner(self, owner: BECWidget) -> int:
        """
        Disconnect all slots owned by a particular widget.

        Called by ``BECWidget.cleanup``, so widgets never need to disconnect their own
        slots at teardown. Idempotent: calling it again (or for an owner without
        subscriptions) is a no-op.

        Args:
            owner(BECWidget): The owner widget whose slots should be disconnected

        Returns:
            int: The number of released slot wrappers.
        """
        slots_to_disconnect = [
            connected_slot
            for connected_slot in list(self._registered_slots.values())
            if connected_slot.cb_owner is not None and connected_slot.cb_owner() is owner
        ]
        for qt_slot in slots_to_disconnect:
            self._release_slot(qt_slot)
        if slots_to_disconnect:
            logger.info(
                f"Released {len(slots_to_disconnect)} dispatcher slot(s) owned by "
                f"{type(owner).__name__}"
            )
        for subscription in self.data_subscriptions(owner):
            self.disconnect_data_subscription(subscription)
        return len(slots_to_disconnect)

    def _release_slot(self, qt_slot: QtThreadSafeCallback) -> None:
        """Unregister all topics of a slot wrapper and drop it from the registry."""
        qt_slot.invalidate()
        topics = list(qt_slot.topics)
        if topics:
            self.client.connector.unregister(topics, cb=qt_slot)
        qt_slot.topics.clear()
        self._registered_slots.pop(qt_slot, None)

    def cleanup_dead_slots(self) -> int:
        """
        Release subscriptions whose callback or owner no longer exists.

        Covers every death path that never delivers a close event: widgets destroyed
        together with a parent, C++ objects deleted while a Python reference lingers,
        and owners that were simply garbage collected. Runs automatically whenever a
        BECWidget is destroyed and on every connect_slot, so stale subscriptions never
        accumulate.

        Returns:
            int: The number of released slot wrappers.
        """
        dead_slots = [slot for slot in list(self._registered_slots.values()) if slot.is_dead()]
        for qt_slot in dead_slots:
            self._release_slot(qt_slot)
        if dead_slots:
            logger.info(f"Released {len(dead_slots)} dispatcher slot(s) with dead owners")
        for subscription in [s for s in self._data_subscriptions if s.is_dead()]:
            self.disconnect_data_subscription(subscription)
        return len(dead_slots)

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
        Stop the CLI server. Idempotent: application teardown has several owners
        (``GUIServer.shutdown`` and the generic ``BECConnector.terminate`` exit
        handler both run on ``aboutToQuit``), so a second stop is an expected
        no-op, not an error.
        """
        if self.cli_server is None:
            logger.debug("CLI server already stopped or never started")
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
