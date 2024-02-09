# pylint: disable = no-name-in-module,missing-module-docstring

import time

from qtpy.QtCore import Slot as pyqtSlot

from bec_widgets.utils.bec_dispatcher import BECDispatcher


class BECConnector:
    """Connection mixin class for all BEC widgets, to handle BEC client and device manager"""

    def __init__(
        self,
        client=None,
        gui_id=None,
        config: dict = None,
    ):
        self.bec_dispatcher = BECDispatcher()
        self.client = self.bec_dispatcher.client if client is None else client
        self.dev = self.client.device_manager.devices

        self.gui_id = gui_id

        if self.gui_id is None:
            self.gui_id = self.__class__.__name__ + str(time.time())

        # Current configuration
        self.config = config

        # Init UI
        if self.config is None:
            print(f"No initial config found for {self.__class__.__name__}")
        else:
            self.on_config_update(self.config)

    # TODO decide if worth to do on the level of base class
    def set_gui_id(self, gui_id: str) -> None:
        """
        Set the GUI ID for the widget.
        Args:
            gui_id(str): GUI ID
        """
        self.gui_id = gui_id
        # TODO decide if to change here or put it also in dataclass like something like gui_id: str = None
        self.config["gui_id"] = gui_id

    def _init_config(self):
        """Initialise the configuration"""
        raise NotImplementedError

    def get_config(self):
        """Return the current configuration settings."""
        return self.config

    def update_client(self, client) -> None:
        """Update the client and device manager from BEC and create object for BEC shortcuts.
        Args:
            client: BEC client
        """
        self.client = client
        self.dev = self.client.device_manager.devices
        self.scans = self.client.scans
        self.queue = self.client.queue
        self.scan_storage = self.queue.scan_storage
        self.dap = self.client.dap

    # TODO will be pydantic model instead of python dict
    @pyqtSlot(dict)
    def on_config_update(self, config: dict) -> None:  # TODO rpc this?
        """
        Update the configuration for the widget.
        Args:
            config(dict): Configuration settings.
        """
        self.config = config
        self._init_config()

    @pyqtSlot(dict)
    def on_instruction(self, msg_content: dict) -> None:  # TODO decide this or rpc?
        """
        Handle instructions sent to the GUI.
        Args:
            msg_content (dict): Message content with the instruction and parameters.
        """
        raise NotImplementedError
