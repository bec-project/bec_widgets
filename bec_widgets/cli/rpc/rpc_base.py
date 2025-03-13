from __future__ import annotations

import inspect
import threading
import uuid
from functools import wraps
from typing import TYPE_CHECKING, Any

from bec_lib.client import BECClient
from bec_lib.endpoints import MessageEndpoints
from bec_lib.utils.import_utils import lazy_import, lazy_import_from

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib import messages
    from bec_lib.connector import MessageObject

    import bec_widgets.cli.client as client
else:
    client = lazy_import("bec_widgets.cli.client")  # avoid circular import
    messages = lazy_import("bec_lib.messages")
    MessageObject = lazy_import_from("bec_lib.connector", ("MessageObject",))

# pylint: disable=protected-access


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
        caller_frame = inspect.currentframe().f_back
        while caller_frame:
            if "jedi" in caller_frame.f_globals:
                # Jedi module is present, likely tab completion
                # Do not run the RPC call
                return None  # func(*args, **kwargs)
            caller_frame = caller_frame.f_back

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


class DeletedWidgetError(Exception): ...


def check_for_deleted_widget(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self._gui_id not in self._registry:
            raise DeletedWidgetError(f"Widget with gui_id {self._gui_id} has been deleted")
        return func(self, *args, **kwargs)

    return wrapper


class RPCReference:
    def __init__(self, registry: dict, gui_id: str) -> None:
        self._registry = registry
        self._gui_id = gui_id

    @check_for_deleted_widget
    def __getattr__(self, name):
        if name in ["_registry", "_gui_id"]:
            return super().__getattribute__(name)
        return self._registry[self._gui_id].__getattribute__(name)

    @check_for_deleted_widget
    def __getitem__(self, key):
        return self._registry[self._gui_id].__getitem__(key)

    def __repr__(self):
        if self._gui_id not in self._registry:
            return f"<Deleted widget with gui_id {self._gui_id}>"
        return self._registry[self._gui_id].__repr__()

    def __str__(self):
        if self._gui_id not in self._registry:
            return f"<Deleted widget with gui_id {self._gui_id}>"
        return self._registry[self._gui_id].__str__()

    def __dir__(self):
        if self._gui_id not in self._registry:
            return []
        return self._registry[self._gui_id].__dir__()


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
        self._rpc_references: dict[str, str] = {}

    def __repr__(self):
        type_ = type(self)
        qualname = type_.__qualname__
        return f"<{qualname} with name: {self.widget_name}>"

    def remove(self):
        """
        Remove the widget.
        """
        self._run_rpc("remove")

    @property
    def widget_name(self):
        """
        Get the widget name.
        """
        return self._name

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
            # The namespace of the object will be updated dynamically on the client side
            # Therefor it is important to check if the object is already in the registry
            # If yes, we return the reference to the object, otherwise we create a new object
            # pylint: disable=protected-access
            if msg_result["gui_id"] in self._root._ipython_registry:
                return RPCReference(self._root._ipython_registry, msg_result["gui_id"])
            ret = cls(parent=self, **msg_result)
            self._root._ipython_registry[ret._gui_id] = ret
            obj = RPCReference(self._root._ipython_registry, ret._gui_id)
            return obj
            # return ret
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
