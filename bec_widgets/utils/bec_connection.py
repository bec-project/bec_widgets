"""Connection state of the BEC client to Redis, for apps that also run without a BEC server.

The BEC widgets start even when Redis does not answer. The dispatcher then keeps all subscriptions
and makes them once the client connects. ``BECConnection`` holds that state for the widgets that
show it (the BEC pill and the status box) and connects the client again on request.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

import redis
from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject, QThreadPool, Signal

from bec_widgets.utils.error_popups import SafeSlot

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.client import BECClient

    from bec_widgets.utils.bec_dispatcher import BECDispatcher

logger = bec_logger.logger

PROBE_TIMEOUT_S = 1.0


class ConnectionState(StrEnum):
    """How the BEC client is connected to Redis."""

    CONNECTED = "connected"
    """The client runs and Redis answers."""
    LOST = "lost"
    """The client runs but Redis stopped answering; the client reconnects by itself."""
    OFFLINE = "offline"
    """The app started without Redis; nothing live is available."""
    AVAILABLE = "available"
    """The app started without Redis and Redis answers now; a reconnect can connect the client."""
    CONNECTING = "connecting"
    """A reconnect is running."""


def redis_address(client: BECClient) -> str:
    """The "host:port" of the Redis server the client uses, or "" if unknown."""
    connector = getattr(client, "connector", None)
    try:
        return f"{connector.host}:{connector.port}"
    except Exception:  # pylint: disable=broad-except
        return ""


def redis_reachable(client: BECClient, timeout: float = PROBE_TIMEOUT_S) -> bool:
    """Whether the Redis server of the client answers, checked on a short-lived connection.

    The check does not use the client's own connections: those retry for minutes before they
    fail. It blocks for at most about ``timeout`` seconds, so call it off the GUI thread.

    Args:
        client (BECClient): The client whose Redis server to check.
        timeout (float): Connect and read timeout in seconds.

    Returns:
        bool: True if Redis answered, also with an authentication error.
    """
    # pylint: disable=protected-access
    try:
        pool = client.connector._managed_connection._redis_conn.connection_pool
        kwargs = dict(pool.connection_kwargs)
        connection_class = pool.connection_class
    except AttributeError:
        return False
    kwargs.pop("redis_connect_func", None)
    kwargs.pop("retry", None)
    kwargs.update(socket_connect_timeout=timeout, socket_timeout=timeout)
    connection = connection_class(**kwargs)
    try:
        connection.connect()
        connection.send_command("PING")
        connection.read_response()
    except (redis.exceptions.AuthenticationError, redis.exceptions.ResponseError):
        return True
    except Exception:  # pylint: disable=broad-except
        return False
    finally:
        connection.disconnect()
    return True


class BECConnection(QObject):
    """The connection state of the dispatcher's client, and the reconnect action.

    The state changes on the GUI thread only: the status poller reports whether Redis answers
    (``set_reachable``) and ``reconnect`` starts the client off the GUI thread.

    Signals:
        state_changed(): The state or the last reconnect error changed.
        reconnected(): The client connected after the app had started without Redis.
    """

    state_changed = Signal()
    reconnected = Signal()

    def __init__(self, dispatcher: BECDispatcher, connected: bool):
        super().__init__()
        self._dispatcher = dispatcher
        self._state = ConnectionState.CONNECTED if connected else ConnectionState.OFFLINE
        self._error = ""
        self._worker = None

    @property
    def state(self) -> ConnectionState:
        """The current connection state."""
        return self._state

    @property
    def connected(self) -> bool:
        """Whether the client runs, i.e. subscriptions and reads go to Redis."""
        return self._state in (ConnectionState.CONNECTED, ConnectionState.LOST)

    @property
    def address(self) -> str:
        """The "host:port" of the Redis server."""
        return redis_address(self._dispatcher.client)

    @property
    def error(self) -> str:
        """Why the last reconnect failed, or ""."""
        return self._error

    def _set_state(self, state: ConnectionState, error: str = "") -> None:
        if (state, error) == (self._state, self._error):
            return
        self._state, self._error = state, error
        self.state_changed.emit()

    def set_reachable(self, reachable: bool) -> None:
        """Update the state for the result of a Redis check.

        Args:
            reachable (bool): Whether Redis answered.
        """
        transitions = {
            (ConnectionState.CONNECTED, False): ConnectionState.LOST,
            (ConnectionState.LOST, True): ConnectionState.CONNECTED,
            (ConnectionState.OFFLINE, True): ConnectionState.AVAILABLE,
            (ConnectionState.AVAILABLE, False): ConnectionState.OFFLINE,
        }
        state = transitions.get((self._state, reachable))
        if state is not None:
            self._set_state(state, self._error if state == ConnectionState.OFFLINE else "")

    def reconnect(self) -> None:
        """Connect the client to Redis if the app started without it. Runs off the GUI thread."""
        if self.connected or self._state == ConnectionState.CONNECTING:
            return
        # pylint: disable=import-outside-toplevel
        from bec_widgets.utils.bec_connector import Worker

        self._set_state(ConnectionState.CONNECTING)
        self._worker = Worker(self._dispatcher.client.start)
        self._worker.signals.completed.connect(self._on_client_started)
        self._worker.signals.failed.connect(self._on_start_failed)
        QThreadPool.globalInstance().start(self._worker)

    @SafeSlot(str)
    def _on_start_failed(self, _error: str) -> None:
        self._on_client_started()

    @SafeSlot()
    def _on_client_started(self) -> None:
        self._worker = None
        if not self._dispatcher.client.started:
            address = self.address or "Redis"
            self._set_state(ConnectionState.OFFLINE, f"Still no answer from {address}")
            return
        logger.success("BEC client connected to Redis")
        self._set_state(ConnectionState.CONNECTED)
        self._dispatcher.on_client_connected()
        self.reconnected.emit()

    def cleanup(self) -> None:
        """Drop the result of a running reconnect."""
        if self._worker is not None:
            for signal in (self._worker.signals.completed, self._worker.signals.failed):
                try:
                    signal.disconnect()
                except (TypeError, RuntimeError):
                    pass
            self._worker = None
