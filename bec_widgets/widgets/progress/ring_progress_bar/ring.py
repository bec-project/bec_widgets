from __future__ import annotations

from typing import Literal, Optional

from bec_lib.endpoints import EndpointInfo, MessageEndpoints
from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError
from qtpy import QtGui

from bec_widgets.utils import BECConnector, ConnectionConfig


class ProgressbarConnections(BaseModel):
    slot: Literal["on_scan_progress", "on_device_readback"] = None
    endpoint: EndpointInfo | str = None
    model_config: dict = {"validate_assignment": True}

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v, values):
        slot = values.data["slot"]
        v = v.endpoint if isinstance(v, EndpointInfo) else v
        if slot == "on_scan_progress":
            if v != MessageEndpoints.scan_progress().endpoint:
                raise PydanticCustomError(
                    "unsupported endpoint",
                    "For slot 'on_scan_progress', endpoint must be MessageEndpoint.scan_progress or 'scans/scan_progress'.",
                    {"wrong_value": v},
                )
        elif slot == "on_device_readback":
            if not v.startswith(MessageEndpoints.device_readback("").endpoint):
                raise PydanticCustomError(
                    "unsupported endpoint",
                    "For slot 'on_device_readback', endpoint must be MessageEndpoint.device_readback(device) or 'internal/devices/readback/{device}'.",
                    {"wrong_value": v},
                )
        return v


class ProgressbarConfig(ConnectionConfig):
    value: int | float | None = Field(0, description="Value for the progress bars.")
    direction: int | None = Field(
        -1, description="Direction of the progress bars. -1 for clockwise, 1 for counter-clockwise."
    )
    color: str | tuple | None = Field(
        (0, 159, 227, 255),
        description="Color for the progress bars. Can be tuple (R, G, B, A) or string HEX Code.",
    )
    background_color: str | tuple | None = Field(
        (200, 200, 200, 50),
        description="Background color for the progress bars. Can be tuple (R, G, B, A) or string HEX Code.",
    )
    index: int | None = Field(0, description="Index of the progress bar. 0 is outer ring.")
    line_width: int | None = Field(10, description="Line widths for the progress bars.")
    start_position: int | None = Field(
        90,
        description="Start position for the progress bars in degrees. Default is 90 degrees - corespons to "
        "the top of the ring.",
    )
    min_value: int | float | None = Field(0, description="Minimum value for the progress bars.")
    max_value: int | float | None = Field(100, description="Maximum value for the progress bars.")
    precision: int | None = Field(3, description="Precision for the progress bars.")
    update_behaviour: Literal["manual", "auto"] | None = Field(
        "auto", description="Update behaviour for the progress bars."
    )
    connections: ProgressbarConnections | None = Field(
        default_factory=ProgressbarConnections, description="Connections for the progress bars."
    )


class RingConfig(ProgressbarConfig):
    index: int | None = Field(0, description="Index of the progress bar. 0 is outer ring.")
    start_position: int | None = Field(
        90,
        description="Start position for the progress bars in degrees. Default is 90 degrees - corespons to "
        "the top of the ring.",
    )


class Ring(BECConnector):
    USER_ACCESS = [
        "_get_all_rpc",
        "_rpc_id",
        "_config_dict",
        "set_value",
        "set_color",
        "set_background",
        "set_line_width",
        "set_min_max_values",
        "set_start_angle",
        "set_update",
        "reset_connection",
    ]

    def __init__(
        self,
        parent=None,
        parent_progress_widget=None,
        config: RingConfig | dict | None = None,
        client=None,
        gui_id: Optional[str] = None,
        **kwargs,
    ):
        if config is None:
            config = RingConfig(widget_class=self.__class__.__name__)
            self.config = config
        else:
            if isinstance(config, dict):
                config = RingConfig(**config)
            self.config = config
        super().__init__(client=client, config=config, gui_id=gui_id, **kwargs)

        self.parent_progress_widget = parent_progress_widget
        self.color = None
        self.background_color = None
        self.start_position = None
        self.config = config
        self.RID = None
        self._init_config_params()

    def _init_config_params(self):
        self.color = self.convert_color(self.config.color)
        self.background_color = self.convert_color(self.config.background_color)
        self.set_start_angle(self.config.start_position)
        if self.config.connections:
            self.set_connections(self.config.connections.slot, self.config.connections.endpoint)

    def set_value(self, value: int | float):
        """
        Set the value for the ring widget

        Args:
            value(int | float): Value for the ring widget
        """
        self.config.value = round(
            float(max(self.config.min_value, min(self.config.max_value, value))),
            self.config.precision,
        )
        self.parent_progress_widget.update()

    def set_color(self, color: str | tuple):
        """
        Set the color for the ring widget

        Args:
            color(str | tuple): Color for the ring widget. Can be HEX code or tuple (R, G, B, A).
        """
        self.config.color = color
        self.color = self.convert_color(color)
        self.parent_progress_widget.update()

    def set_background(self, color: str | tuple):
        """
        Set the background color for the ring widget

        Args:
            color(str | tuple): Background color for the ring widget. Can be HEX code or tuple (R, G, B, A).
        """
        self.config.background_color = color
        self.color = self.convert_color(color)
        self.parent_progress_widget.update()

    def set_line_width(self, width: int):
        """
        Set the line width for the ring widget

        Args:
            width(int): Line width for the ring widget
        """
        self.config.line_width = width
        self.parent_progress_widget.update()

    def set_min_max_values(self, min_value: int | float, max_value: int | float):
        """
        Set the min and max values for the ring widget.

        Args:
            min_value(int | float): Minimum value for the ring widget
            max_value(int | float): Maximum value for the ring widget
        """
        self.config.min_value = min_value
        self.config.max_value = max_value
        self.parent_progress_widget.update()

    def set_start_angle(self, start_angle: int):
        """
        Set the start angle for the ring widget

        Args:
            start_angle(int): Start angle for the ring widget in degrees
        """
        self.config.start_position = start_angle
        self.start_position = start_angle * 16
        self.parent_progress_widget.update()

    @staticmethod
    def convert_color(color):
        """
        Convert the color to QColor

        Args:
            color(str | tuple): Color for the ring widget. Can be HEX code or tuple (R, G, B, A).
        """
        converted_color = None
        if isinstance(color, str):
            converted_color = QtGui.QColor(color)
        elif isinstance(color, tuple):
            converted_color = QtGui.QColor(*color)
        return converted_color

    def set_update(self, mode: Literal["manual", "scan", "device"], device: str = None):
        """
        Set the update mode for the ring widget.
        Modes:
        - "manual": Manual update mode, the value is set by the user.
        - "scan": Update mode for the scan progress. The value is updated by the current scan progress.
        - "device": Update mode for the device readback. The value is updated by the device readback. Take into account that user has to set the device name and limits.

        Args:
            mode(str): Update mode for the ring widget. Can be "manual", "scan" or "device"
            device(str): Device name for the device readback mode, only used when mode is "device"
        """
        if mode == "manual":
            self.bec_dispatcher.disconnect_slot(
                getattr(self, self.config.connections.slot), self.config.connections.endpoint
            )
            self.config.connections.slot = None
            self.config.connections.endpoint = None
        elif mode == "scan":
            self.set_connections("on_scan_progress", "scans/scan_progress")
        elif mode == "device":
            self.set_connections("on_device_readback", f"internal/devices/readback/{device}")

        self.parent_progress_widget.enable_auto_updates(False)

    def set_connections(self, slot: str, endpoint: str | EndpointInfo):
        """
        Set the connections for the ring widget

        Args:
            slot(str): Slot for the ring widget update. Can be "on_scan_progress" or "on_device_readback".
            endpoint(str | EndpointInfo): Endpoint for the ring widget update. Endpoint has to match the slot type.
        """
        if self.config.connections.endpoint == endpoint and self.config.connections.slot == slot:
            return
        else:
            self.bec_dispatcher.disconnect_slot(
                self.config.connections.slot, self.config.connections.endpoint
            )
            self.config.connections = ProgressbarConnections(slot=slot, endpoint=endpoint)
            self.bec_dispatcher.connect_slot(getattr(self, slot), endpoint)

    def reset_connection(self):
        """
        Reset the connections for the ring widget. Disconnect the current slot and endpoint.
        """
        self.bec_dispatcher.disconnect_slot(
            self.config.connections.slot, self.config.connections.endpoint
        )
        self.config.connections = ProgressbarConnections()

    def on_scan_progress(self, msg, meta):
        """
        Update the ring widget with the scan progress.

        Args:
            msg(dict): Message with the scan progress
            meta(dict): Metadata for the message
        """
        current_RID = meta.get("RID", None)
        if current_RID != self.RID:
            self.set_min_max_values(0, msg.get("max_value", 100))
        self.set_value(msg.get("value", 0))
        self.parent_progress_widget.update()

    def on_device_readback(self, msg, meta):
        """
        Update the ring widget with the device readback.

        Args:
            msg(dict): Message with the device readback
            meta(dict): Metadata for the message
        """
        if isinstance(self.config.connections.endpoint, EndpointInfo):
            endpoint = self.config.connections.endpoint.endpoint
        else:
            endpoint = self.config.connections.endpoint
        device = endpoint.split("/")[-1]
        value = msg.get("signals").get(device).get("value")
        self.set_value(value)
        self.parent_progress_widget.update()
