from __future__ import annotations

from functools import wraps
from threading import Lock
from typing import TYPE_CHECKING, Callable
from weakref import WeakValueDictionary

from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject

if TYPE_CHECKING:
    from bec_widgets.utils.bec_connector import BECConnector
    from bec_widgets.utils.bec_widget import BECWidget
    from bec_widgets.widgets.containers.dock.dock import BECDock
    from bec_widgets.widgets.containers.dock.dock_area import BECDockArea

logger = bec_logger.logger


class RPCRegister:
    """
    A singleton class that keeps track of all the RPC objects registered in the system for CLI usage.
    """

    _instance = None
    _initialized = False
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RPCRegister, cls).__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._rpc_register = WeakValueDictionary()
        self._initialized = True

    def add_rpc(self, rpc: QObject):
        """
        Add an RPC object to the register.

        Args:
            rpc(QObject): The RPC object to be added to the register.
        """
        if not hasattr(rpc, "gui_id"):
            raise ValueError("RPC object must have a 'gui_id' attribute.")
        self._rpc_register[rpc.gui_id] = rpc

    def remove_rpc(self, rpc: str):
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
        self, cls: BECWidget | BECConnector | BECDock | BECDockArea
    ) -> list[str]:
        """Get all the names of the widgets.

        Args:
            cls(BECWidget | BECConnector): The class of the RPC object to be retrieved.
        """
        # This retrieves any rpc objects that are subclass of BECWidget,
        # i.e. curve and image items are excluded
        widgets = [rpc for rpc in self._rpc_register.values() if isinstance(rpc, cls)]
        return [widget._name for widget in widgets]

    @classmethod
    def reset_singleton(cls):
        """
        Reset the singleton instance.
        """
        cls._instance = None
        cls._initialized = False
