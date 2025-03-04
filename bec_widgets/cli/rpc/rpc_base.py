from __future__ import annotations

import threading
import uuid
from functools import wraps
from typing import TYPE_CHECKING, Any, cast

from bec_lib.client import BECClient
from bec_lib.endpoints import MessageEndpoints
from bec_lib.utils.import_utils import lazy_import, lazy_import_from

import bec_widgets.cli.client as client

if TYPE_CHECKING:
    from bec_lib import messages
    from bec_lib.connector import MessageObject
else:
    messages = lazy_import("bec_lib.messages")
    # from bec_lib.connector import MessageObject
    MessageObject = lazy_import_from("bec_lib.connector", ("MessageObject",))


def rpc_call(func):
    """
    A decorator for calling a function on the server.

    Args:
        func: The function to call.

    Returns:
        The result of the function call.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # we could rely on a strict type check here, but this is more flexible
        # moreover, it would anyway crash for objects...
        out = []
        for arg in args:
            if hasattr(arg, "name"):
                arg = arg.name
            out.append(arg)
        args = tuple(out)
        for key, val in kwargs.items():
            if hasattr(val, "name"):
                kwargs[key] = val.name
        if not self._root._gui_is_alive():
            raise RuntimeError("GUI is not alive")
        return self._run_rpc(func.__name__, *args, **kwargs)

    return wrapper


class RPCResponseTimeoutError(Exception):
    """Exception raised when an RPC response is not received within the expected time."""

    def __init__(self, request_id, timeout):
        super().__init__(
            f"RPC response not received within {timeout} seconds for request ID {request_id}"
        )


class RPCBase:
    def __init__(
        self,
        gui_id: str | None = None,
        config: dict | None = None,
        name: str | None = None,
        parent=None,
    ) -> None:
        self._client = BECClient()  # BECClient is a singleton; here, we simply get the instance
        self._config = config if config is not None else {}
        self._gui_id = gui_id if gui_id is not None else str(uuid.uuid4())[:5]
        self._name = name if name is not None else str(uuid.uuid4())[:5]
        self._parent = parent
        self._msg_wait_event = threading.Event()
        self._rpc_response = None
        super().__init__()
        # print(f"RPCBase: {self._gui_id}")

    def __repr__(self):
        type_ = type(self)
        qualname = type_.__qualname__
        return f"<{qualname} object at {hex(id(self))}>"

    @property
    def _root(self):
        """
        Get the root widget. This is the BECFigure widget that holds
        the anchor gui_id.
        """
        parent = self
        # pylint: disable=protected-access
        while parent._parent is not None:
            parent = parent._parent
        return parent

    def _run_rpc(self, method, *args, wait_for_rpc_response=True, timeout=3, **kwargs) -> Any:
        """
        Run the RPC call.

        Args:
            method: The method to call.
            args: The arguments to pass to the method.
            wait_for_rpc_response: Whether to wait for the RPC response.
            kwargs: The keyword arguments to pass to the method.

        Returns:
            The result of the RPC call.
        """
        request_id = str(uuid.uuid4())
        rpc_msg = messages.GUIInstructionMessage(
            action=method,
            parameter={"args": args, "kwargs": kwargs, "gui_id": self._gui_id},
            metadata={"request_id": request_id},
        )

        # pylint: disable=protected-access
        receiver = self._root._gui_id
        if wait_for_rpc_response:
            self._rpc_response = None
            self._msg_wait_event.clear()
            self._client.connector.register(
                MessageEndpoints.gui_instruction_response(request_id),
                cb=self._on_rpc_response,
                parent=self,
            )

        self._client.connector.set_and_publish(MessageEndpoints.gui_instructions(receiver), rpc_msg)

        if wait_for_rpc_response:
            try:
                finished = self._msg_wait_event.wait(timeout)
                if not finished:
                    raise RPCResponseTimeoutError(request_id, timeout)
            finally:
                self._msg_wait_event.clear()
                self._client.connector.unregister(
                    MessageEndpoints.gui_instruction_response(request_id), cb=self._on_rpc_response
                )
            # get class name
            if not self._rpc_response.accepted:
                raise ValueError(self._rpc_response.message["error"])
            msg_result = self._rpc_response.message.get("result")
            self._rpc_response = None
            return self._create_widget_from_msg_result(msg_result)

    @staticmethod
    def _on_rpc_response(msg: MessageObject, parent: RPCBase) -> None:
        msg = msg.value
        parent._msg_wait_event.set()
        parent._rpc_response = msg

    def _create_widget_from_msg_result(self, msg_result):
        if msg_result is None:
            return None
        if isinstance(msg_result, list):
            return [self._create_widget_from_msg_result(res) for res in msg_result]
        if isinstance(msg_result, dict):
            if "__rpc__" not in msg_result:
                return {
                    key: self._create_widget_from_msg_result(val) for key, val in msg_result.items()
                }
            cls = msg_result.pop("widget_class", None)
            msg_result.pop("__rpc__", None)

            if not cls:
                return msg_result

            cls = getattr(client, cls)
            # print(msg_result)
            ret = cls(parent=self, **msg_result)
            return ret
        return msg_result

    def _gui_is_alive(self):
        """
        Check if the GUI is alive.
        """
        heart = self._client.connector.get(MessageEndpoints.gui_heartbeat(self._root._gui_id))
        if heart is None:
            return False
        if heart.status == messages.BECStatus.RUNNING:
            return True
        return False
