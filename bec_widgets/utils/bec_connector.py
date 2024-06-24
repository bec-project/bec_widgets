# pylint: disable = no-name-in-module,missing-module-docstring
from __future__ import annotations

import time
from typing import Optional

from bec_lib.utils.import_utils import lazy_import_from
from pydantic import BaseModel, Field, field_validator
from qtpy.QtCore import QObject, QRunnable, QThreadPool, Signal
from qtpy.QtCore import Slot as pyqtSlot

from bec_widgets.cli.rpc_register import RPCRegister

BECDispatcher = lazy_import_from("bec_widgets.utils.bec_dispatcher", ("BECDispatcher",))


class ConnectionConfig(BaseModel):
    """Configuration for BECConnector mixin class"""

    widget_class: str = Field(default="NonSpecifiedWidget", description="The class of the widget.")
    gui_id: Optional[str] = Field(
        default=None, validate_default=True, description="The GUI ID of the widget."
    )
    model_config: dict = {"validate_assignment": True}

    @field_validator("gui_id")
    @classmethod
    def generate_gui_id(cls, v, values):
        """Generate a GUI ID if none is provided."""
        if v is None:
            widget_class = values.data["widget_class"]
            v = f"{widget_class}_{str(time.time())}"
            return v
        return v


class WorkerSignals(QObject):
    progress = Signal(dict)
    completed = Signal()


class Worker(QRunnable):
    """
    Worker class to run a function in a separate thread.
    """

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.signals = WorkerSignals()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """
        Run the specified function in the thread.
        """
        self.func(*self.args, **self.kwargs)
        self.signals.completed.emit()


class BECConnector:
    """Connection mixin class for all BEC widgets, to handle BEC client and device manager"""

    USER_ACCESS = ["config_dict", "get_all_rpc"]

    def __init__(self, client=None, config: ConnectionConfig = None, gui_id: str = None):
        # BEC related connections
        self.bec_dispatcher = BECDispatcher(client=client)
        self.client = self.bec_dispatcher.client if client is None else client

        if config:
            self.config = config
            self.config.widget_class = self.__class__.__name__
        else:
            print(
                f"No initial config found for {self.__class__.__name__}.\n"
                f"Initializing with default config."
            )
            self.config = ConnectionConfig(widget_class=self.__class__.__name__)

        if gui_id:
            self.config.gui_id = gui_id
            self.gui_id = gui_id
        else:
            self.gui_id = self.config.gui_id

        # register widget to rpc register
        self.rpc_register = RPCRegister()
        self.rpc_register.add_rpc(self)

        self._thread_pool = QThreadPool.globalInstance()

    def submit_task(self, fn, *args, on_complete: pyqtSlot = None, **kwargs) -> Worker:
        """
        Submit a task to run in a separate thread. The task will run the specified
        function with the provided arguments and emit the completed signal when done.

        Use this method if you want to wait for a task to complete without blocking the
        main thread.

        Args:
            fn: Function to run in a separate thread.
            *args: Arguments for the function.
            on_complete: Slot to run when the task is complete.
            **kwargs: Keyword arguments for the function.

        Returns:
            worker: The worker object that will run the task.

        Examples:
            >>> def my_function(a, b):
            >>>     print(a + b)
            >>> self.submit_task(my_function, 1, 2)

            >>> def my_function(a, b):
            >>>     print(a + b)
            >>> def on_complete():
            >>>     print("Task complete")
            >>> self.submit_task(my_function, 1, 2, on_complete=on_complete)

        """
        worker = Worker(fn, *args, **kwargs)
        if on_complete:
            worker.signals.completed.connect(on_complete)
        self._thread_pool.start(worker)
        return worker

    def get_all_rpc(self) -> dict:
        """Get all registered RPC objects."""
        all_connections = self.rpc_register.list_all_connections()
        return dict(all_connections)

    @property
    def rpc_id(self) -> str:
        """Get the RPC ID of the widget."""
        return self.gui_id

    @rpc_id.setter
    def rpc_id(self, rpc_id: str) -> None:
        """Set the RPC ID of the widget."""
        self.gui_id = rpc_id

    @property
    def config_dict(self) -> dict:
        """
        Get the configuration of the widget.

        Returns:
            dict: The configuration of the widget.
        """
        return self.config.model_dump()

    @config_dict.setter
    def config_dict(self, config: BaseModel) -> None:
        """
        Get the configuration of the widget.

        Returns:
            dict: The configuration of the widget.
        """
        self.config = config

    @pyqtSlot(str)
    def set_gui_id(self, gui_id: str) -> None:
        """
        Set the GUI ID for the widget.

        Args:
            gui_id(str): GUI ID
        """
        self.config.gui_id = gui_id
        self.gui_id = gui_id

    def get_obj_by_id(self, obj_id: str):
        if obj_id == self.gui_id:
            return self

    def get_bec_shortcuts(self):
        """Get BEC shortcuts for the widget."""
        self.dev = self.client.device_manager.devices
        self.scans = self.client.scans
        self.queue = self.client.queue
        self.scan_storage = self.queue.scan_storage
        self.dap = self.client.dap

    def update_client(self, client) -> None:
        """Update the client and device manager from BEC and create object for BEC shortcuts.

        Args:
            client: BEC client
        """
        self.client = client
        self.get_bec_shortcuts()

    @pyqtSlot(ConnectionConfig)  # TODO can be also dict
    def on_config_update(self, config: ConnectionConfig | dict) -> None:
        """
        Update the configuration for the widget.

        Args:
            config(ConnectionConfig): Configuration settings.
        """
        if isinstance(config, dict):
            config = ConnectionConfig(**config)
            # TODO add error handler

        self.config = config

    def get_config(self, dict_output: bool = True) -> dict | BaseModel:
        """
        Get the configuration of the widget.

        Args:
            dict_output(bool): If True, return the configuration as a dictionary. If False, return the configuration as a pydantic model.

        Returns:
            dict: The configuration of the plot widget.
        """
        if dict_output:
            return self.config.model_dump()
        else:
            return self.config

    def cleanup(self):
        """Cleanup the widget."""
        self.rpc_register.remove_rpc(self)
        all_connections = self.rpc_register.list_all_connections()
        if len(all_connections) == 0:
            print("No more connections. Shutting down GUI BEC client.")
            self.bec_dispatcher.disconnect_all()
            self.client.shutdown()

    # def closeEvent(self, event):
    #     self.cleanup()
    #     super().closeEvent(event)
