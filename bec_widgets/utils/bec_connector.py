# pylint: disable = no-name-in-module,missing-module-docstring
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from bec_lib.logger import bec_logger
from bec_lib.utils.import_utils import lazy_import_from
from pydantic import BaseModel, Field, field_validator
from qtpy.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from qtpy.QtWidgets import QApplication

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils.container_utils import WidgetContainerUtils
from bec_widgets.utils.error_popups import ErrorPopupUtility
from bec_widgets.utils.error_popups import SafeSlot as pyqtSlot
from bec_widgets.utils.widget_io import WidgetHierarchy
from bec_widgets.utils.yaml_dialog import load_yaml, load_yaml_gui, save_yaml, save_yaml_gui

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.utils.bec_dispatcher import BECDispatcher
    from bec_widgets.widgets.containers.dock import BECDock

logger = bec_logger.logger
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
            v = f"{widget_class}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S_%f')}"
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
    """Connection mixin class to handle BEC client and device manager"""

    USER_ACCESS = ["_config_dict", "_get_all_rpc", "_rpc_id"]
    EXIT_HANDLERS = {}

    def __init__(
        self,
        client=None,
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        object_name: str | None = None,
        parent_dock: BECDock | None = None,  # TODO should go away
        parent_id: str | None = None,
        **kwargs,
    ):
        # Extract object_name from kwargs to not pass it to Qt class
        object_name = object_name or kwargs.pop("objectName", None)
        # Ensure the parent is always the first argument for QObject
        parent = kwargs.pop("parent", None)
        # This initializes the QObject or any qt related class
        super().__init__(parent=parent, **kwargs)
        # BEC related connections
        self.bec_dispatcher = BECDispatcher(client=client)
        self.client = self.bec_dispatcher.client if client is None else client
        self._parent_dock = parent_dock  # TODO also remove at some point

        if not self.client in BECConnector.EXIT_HANDLERS:
            # register function to clean connections at exit;
            # the function depends on BECClient, and BECDispatcher
            @pyqtSlot()
            def terminate(client=self.client, dispatcher=self.bec_dispatcher):
                logger.info("Disconnecting", repr(dispatcher))
                dispatcher.disconnect_all()
                logger.info("Shutting down BEC Client", repr(client))
                client.shutdown()

            BECConnector.EXIT_HANDLERS[self.client] = terminate
            QApplication.instance().aboutToQuit.connect(terminate)

        if config:
            self.config = config
            self.config.widget_class = self.__class__.__name__
        else:
            logger.debug(
                f"No initial config found for {self.__class__.__name__}.\n"
                f"Initializing with default config."
            )
            self.config = ConnectionConfig(widget_class=self.__class__.__name__)

        self.parent_id = parent_id
        # If the gui_id is passed, it should be respected. However, this should be revisted since
        # the gui_id has to be unique, and may no longer be.
        if gui_id:
            self.config.gui_id = gui_id
            self.gui_id: str = gui_id  # Keep namespace in sync
        else:
            self.gui_id: str = self.config.gui_id  # type: ignore

        # TODO Hierarchy can be refreshed upon creation -> also registry should be notified if objectName changes -> issue #472
        if object_name is not None:
            self.setObjectName(object_name)

        # 1) If no objectName is set, set the initial name
        if not self.objectName():
            self.setObjectName(self.__class__.__name__)
        self.object_name = self.objectName()

        # 2) Enforce unique objectName among siblings with the same BECConnector parent
        self.setParent(parent)
        if parent_id is None:
            connector_parent = WidgetHierarchy._get_becwidget_ancestor(self)
            if connector_parent is not None:
                self.parent_id = connector_parent.gui_id

        self._enforce_unique_sibling_name()
        self.rpc_register = RPCRegister()
        self.rpc_register.add_rpc(self)

        # Error popups
        self.error_utility = ErrorPopupUtility()

        self._thread_pool = QThreadPool.globalInstance()
        # Store references to running workers so they're not garbage collected prematurely.
        self._workers = []

    def _enforce_unique_sibling_name(self):
        """
        Enforce that this BECConnector has a unique objectName among its siblings.

        Sibling logic:
          - If there's a nearest BECConnector parent, only compare with children of that parent.
          - If parent is None (i.e., top-level object), compare with all other top-level BECConnectors.
        """
        parent_bec = WidgetHierarchy._get_becwidget_ancestor(self)

        if parent_bec:
            # We have a parent => only compare with siblings under that parent
            siblings = parent_bec.findChildren(BECConnector)
        else:
            # No parent => treat all top-level BECConnectors as siblings
            # 1) Gather all BECConnectors from QApplication
            all_widgets = QApplication.allWidgets()
            all_bec = [w for w in all_widgets if isinstance(w, BECConnector)]
            # 2) "Top-level" means closest BECConnector parent is None
            top_level_bec = [
                w for w in all_bec if WidgetHierarchy._get_becwidget_ancestor(w) is None
            ]
            # 3) We are among these top-level siblings
            siblings = top_level_bec

        # Collect used names among siblings
        used_names = {sib.objectName() for sib in siblings if sib is not self}

        base_name = self.objectName()
        if base_name not in used_names:
            # Name is already unique among siblings
            return

        # Need a suffix to avoid collision
        counter = 0
        while True:
            trial_name = f"{base_name}_{counter}"
            if trial_name not in used_names:
                self.setObjectName(trial_name)
                self.object_name = trial_name
                break
            counter += 1

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
        # Keep a reference to the worker so it is not garbage collected.
        self._workers.append(worker)
        # When the worker is done, remove it from our list.
        worker.signals.completed.connect(lambda: self._workers.remove(worker))
        self._thread_pool.start(worker)
        return worker

    def _get_all_rpc(self) -> dict:
        """Get all registered RPC objects."""
        all_connections = self.rpc_register.list_all_connections()
        return dict(all_connections)

    @property
    def _rpc_id(self) -> str:
        """Get the RPC ID of the widget."""
        return self.gui_id

    @_rpc_id.setter
    def _rpc_id(self, rpc_id: str) -> None:
        """Set the RPC ID of the widget."""
        self.gui_id = rpc_id

    @property
    def _config_dict(self) -> dict:
        """
        Get the configuration of the widget.

        Returns:
            dict: The configuration of the widget.
        """
        return self.config.model_dump()

    @_config_dict.setter
    def _config_dict(self, config: BaseModel) -> None:
        """
        Set the configuration of the widget.

        Args:
            config (BaseModel): The new configuration model.
        """
        self.config = config

    # FIXME some thoughts are required to decide how thhis should work with rpc registry
    def apply_config(self, config: dict, generate_new_id: bool = True) -> None:
        """
        Apply the configuration to the widget.

        Args:
            config (dict): Configuration settings.
            generate_new_id (bool): If True, generate a new GUI ID for the widget.
        """
        self.config = ConnectionConfig(**config)
        if generate_new_id is True:
            gui_id = str(uuid.uuid4())
            self.rpc_register.remove_rpc(self)
            self._set_gui_id(gui_id)
            self.rpc_register.add_rpc(self)
        else:
            self.gui_id = self.config.gui_id

    # FIXME some thoughts are required to decide how thhis should work with rpc registry
    def load_config(self, path: str | None = None, gui: bool = False):
        """
        Load the configuration of the widget from YAML.

        Args:
            path (str | None): Path to the configuration file for non-GUI dialog mode.
            gui (bool): If True, use the GUI dialog to load the configuration file.
        """
        if gui is True:
            config = load_yaml_gui(self)
        else:
            config = load_yaml(path)

        if config is not None:
            if config.get("widget_class") != self.__class__.__name__:
                raise ValueError(
                    f"Configuration file is not for {self.__class__.__name__}. Got configuration for {config.get('widget_class')}."
                )
            self.apply_config(config)

    def save_config(self, path: str | None = None, gui: bool = False):
        """
        Save the configuration of the widget to YAML.

        Args:
            path (str | None): Path to save the configuration file for non-GUI dialog mode.
            gui (bool): If True, use the GUI dialog to save the configuration file.
        """
        if gui is True:
            save_yaml_gui(self, self._config_dict)
        else:
            if path is None:
                path = os.getcwd()
            file_path = os.path.join(path, f"{self.__class__.__name__}_config.yaml")
            save_yaml(file_path, self._config_dict)

    # @pyqtSlot(str)
    def _set_gui_id(self, gui_id: str) -> None:
        """
        Set the GUI ID for the widget.

        Args:
            gui_id (str): GUI ID.
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
            client: BEC client.
        """
        self.client = client
        self.get_bec_shortcuts()

    @pyqtSlot(ConnectionConfig)  # TODO can be also dict
    def on_config_update(self, config: ConnectionConfig | dict) -> None:
        """
        Update the configuration for the widget.

        Args:
            config (ConnectionConfig | dict): Configuration settings.
        """
        gui_id = getattr(config, "gui_id", None)
        if isinstance(config, dict):
            config = ConnectionConfig(**config)
        self.config = config
        if gui_id and config.gui_id != gui_id:  # Recreating config should not overwrite the gui_id
            self.config.gui_id = gui_id

    def remove(self):
        """Cleanup the BECConnector"""
        # If the widget is attached to a dock, remove it from the dock.
        # TODO this should be handled by dock and dock are not by BECConnector
        if self._parent_dock is not None:
            self._parent_dock.delete(self.object_name)
        # If the widget is from Qt, trigger its close method.
        elif hasattr(self, "close"):
            self.close()
        # If the widget is neither from a Dock nor from Qt, remove it from the RPC registry.
        # i.e. Curve Item from Waveform
        else:
            self.rpc_register.remove_rpc(self)

    def get_config(self, dict_output: bool = True) -> dict | BaseModel:
        """
        Get the configuration of the widget.

        Args:
            dict_output (bool): If True, return the configuration as a dictionary.
                                If False, return the configuration as a pydantic model.

        Returns:
            dict | BaseModel: The configuration of the widget.
        """
        if dict_output:
            return self.config.model_dump()
        else:
            return self.config


# --- Example usage of BECConnector: running a simple task ---
if __name__ == "__main__":  # pragma: no cover
    import sys

    # Create a QApplication instance (required for QThreadPool)
    app = QApplication(sys.argv)

    connector = BECConnector()

    def print_numbers():
        """
        Task function that prints numbers 1 to 10 with a 0.5 second delay between each.
        """
        for i in range(1, 11):
            print(i)
            time.sleep(0.5)

    def task_complete():
        """
        Called when the task is complete.
        """
        print("Task complete")
        # Exit the application after the task completes.
        app.quit()

    # Submit the task using the connector's submit_task method.
    connector.submit_task(print_numbers, on_complete=task_complete)

    # Start the Qt event loop.
    sys.exit(app.exec_())
