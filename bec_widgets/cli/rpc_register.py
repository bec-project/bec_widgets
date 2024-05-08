from threading import Lock
from weakref import WeakValueDictionary

from qtpy.QtCore import QObject


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

    def get_rpc_by_id(self, gui_id: str) -> QObject:
        """
        Get an RPC object by its ID.

        Args:
            gui_id(str): The ID of the RPC object to be retrieved.

        Returns:
            QObject: The RPC object with the given ID.
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

    @classmethod
    def reset_singleton(cls):
        """
        Reset the singleton instance.
        """
        cls._instance = None
        cls._initialized = False
