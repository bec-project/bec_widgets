from threading import Lock
from weakref import WeakValueDictionary


class RPCRegister:
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

    def add_rpc(self, rpc):
        if not hasattr(rpc, "gui_id"):
            raise ValueError("RPC object must have a 'gui_id' attribute.")
        self._rpc_register[rpc.gui_id] = rpc

    def remove_rpc(self, rpc):
        if not hasattr(rpc, "gui_id"):
            raise ValueError(f"RPC object {rpc} must have a 'gui_id' attribute.")
        self._rpc_register.pop(rpc.gui_id, None)

    def get_rpc_by_id(self, gui_id):
        rpc_object = self._rpc_register.get(gui_id, None)
        print(f"get rpc by id: {rpc_object}")
        return rpc_object

    def list_all_connections(self):
        with self._lock:
            connections = dict(self._rpc_register)
        return connections

    @classmethod
    def reset_singleton(cls):
        cls._instance = None
        cls._initialized = False
