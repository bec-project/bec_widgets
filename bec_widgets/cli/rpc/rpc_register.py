from __future__ import annotations

from functools import wraps
from threading import RLock
from typing import TYPE_CHECKING, Callable
from weakref import WeakValueDictionary

from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.utils.bec_connector import BECConnector
    from bec_widgets.utils.bec_widget import BECWidget
    from bec_widgets.widgets.containers.dock.dock import BECDock
    from bec_widgets.widgets.containers.dock.dock_area import BECDockArea

logger = bec_logger.logger


def broadcast_update(func):
    """
    Decorator to broadcast updates to the RPCRegister whenever a new RPC object is added or removed.
    If class attribute _skip_broadcast is set to True, the broadcast will be skipped
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        self.broadcast()
        return result

    return wrapper


class RPCRegister:
    """
    A singleton class that keeps track of all the RPC objects registered in the system for CLI usage.
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RPCRegister, cls).__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._rpc_register = WeakValueDictionary()
        self._broadcast_on_hold = RPCRegisterBroadcast(self)
        self._lock = RLock()
        self._skip_broadcast = False
        self._initialized = True
        self.callbacks = []

    @classmethod
    def delayed_broadcast(cls):
        """
        Delay the broadcast of the update to all the callbacks.
        """
        register = cls()
        return register._broadcast_on_hold

    @broadcast_update
    def add_rpc(self, rpc: BECConnector):
        """
        Add an RPC object to the register.

        Args:
            rpc(QObject): The RPC object to be added to the register.
        """
        if not hasattr(rpc, "gui_id"):
            raise ValueError("RPC object must have a 'gui_id' attribute.")
        self._rpc_register[rpc.gui_id] = rpc

    @broadcast_update
    def remove_rpc(self, rpc: BECConnector):
        """
        Remove an RPC object from the register.

        Args:
            rpc(str): The RPC object to be removed from the register.
        """
        if not hasattr(rpc, "gui_id"):
            raise ValueError(f"RPC object {rpc} must have a 'gui_id' attribute.")
        self._rpc_register.pop(rpc.gui_id, None)

    def get_rpc_by_id(self, gui_id: str) -> QObject | None:
        """
        Get an RPC object by its ID.

        Args:
            gui_id(str): The ID of the RPC object to be retrieved.

        Returns:
            QObject | None: The RPC object with the given ID or None
        """
        rpc_object = self._rpc_register.get(gui_id, None)
        return rpc_object

    def list_all_connections(self) -> dict:
        """
        List all the registered RPC objects.

        Returns:
            dict: A dictionary containing all the registered RPC objects.
        """
        with self._lock:
            connections = dict(self._rpc_register)
        return connections

    def get_names_of_rpc_by_class_type(
        self, cls: type[BECWidget] | type[BECConnector] | type[BECDock] | type[BECDockArea]
    ) -> list[str]:
        """Get all the names of the widgets.

        Args:
            cls(BECWidget | BECConnector): The class of the RPC object to be retrieved.
        """
        # This retrieves any rpc objects that are subclass of BECWidget,
        # i.e. curve and image items are excluded
        widgets = [rpc for rpc in self._rpc_register.values() if isinstance(rpc, cls)]
        return [widget.object_name for widget in widgets]

    def broadcast(self):
        """
        Broadcast the update to all the callbacks.
        """

        if self._skip_broadcast:
            return
        connections = self.list_all_connections()
        for callback in self.callbacks:
            callback(connections)

    def object_is_registered(self, obj: BECConnector) -> bool:
        """
        Check if an object is registered in the RPC register.

        Args:
            obj(QObject): The object to check.

        Returns:
            bool: True if the object is registered, False otherwise.
        """
        return obj.gui_id in self._rpc_register

    def add_callback(self, callback: Callable[[dict], None]):
        """
        Add a callback that will be called whenever the registry is updated.

        Args:
            callback(Callable[[dict], None]): The callback to be added. It should accept a dictionary of all the
            registered RPC objects as an argument.
        """
        self.callbacks.append(callback)

    @classmethod
    def reset_singleton(cls):
        """
        Reset the singleton instance.
        """
        cls._instance = None
        cls._initialized = False


class RPCRegisterBroadcast:
    """Context manager for RPCRegister broadcast."""

    def __init__(self, rpc_register: RPCRegister) -> None:
        self.rpc_register = rpc_register
        self._call_depth = 0

    def __enter__(self):
        """Enter the context manager"""
        self._call_depth += 1  # Needed for nested calls
        self.rpc_register._skip_broadcast = True
        return self.rpc_register

    def __exit__(self, *exc):
        """Exit the context manager"""

        self._call_depth -= 1  # Remove nested calls
        if self._call_depth == 0:  # The Last one to exit is responsible for broadcasting
            self.rpc_register._skip_broadcast = False
        self.rpc_register.broadcast()
