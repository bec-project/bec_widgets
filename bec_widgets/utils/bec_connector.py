# pylint: disable = no-name-in-module,missing-module-docstring
from __future__ import annotations

import time
from typing import Optional, Type

from pydantic import BaseModel, Field, field_validator
from qtpy.QtCore import Slot as pyqtSlot

from bec_widgets.utils.bec_dispatcher import BECDispatcher


class ConnectionConfig(BaseModel):
    """Configuration for BECConnector mixin class"""

    widget_class: str = Field(default="NonSpecifiedWidget", description="The class of the widget.")
    gui_id: Optional[str] = Field(
        default=None, validate_default=True, description="The GUI ID of the widget."
    )

    @field_validator("gui_id")
    def generate_gui_id(cls, v, values):
        """Generate a GUI ID if none is provided."""
        if v is None:
            widget_class = values.data["widget_class"]
            v = f"{widget_class}_{str(time.time())}"
            return v
        return v


class BECConnector:
    """Connection mixin class for all BEC widgets, to handle BEC client and device manager"""

    USER_ACCESS = ["config_dict"]

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

    def closeEvent(self, event):
        self.client.shutdown()
        super().closeEvent(event)
