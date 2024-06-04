from __future__ import annotations

from typing import Literal, Optional

from bec_lib.endpoints import EndpointInfo
from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError
from qtpy import QtGui

from bec_widgets.utils import BECConnector, ConnectionConfig


class RingConnections(BaseModel):
    slot: Literal["on_scan_progress", "on_device_readback"] = None
    endpoint: EndpointInfo | str = None

    @field_validator("endpoint")
    def validate_endpoint(cls, v, values):
        slot = values.data["slot"]
        v = v.endpoint if isinstance(v, EndpointInfo) else v
        if slot == "on_scan_progress":
            if v != "scans/scan_progress":
                raise PydanticCustomError(
                    "unsupported endpoint",
                    "For slot 'on_scan_progress', endpoint must be MessageEndpoint.scan_progress or 'scans/scan_progress'.",
                    {"wrong_value": v},
                )
        elif slot == "on_device_readback":
            if not v.startswith("internal/devices/readback/"):
                raise PydanticCustomError(
                    "unsupported endpoint",
                    "For slot 'on_device_readback', endpoint must be MessageEndpoint.device_readback(device) or 'internal/devices/readback/{device}'.",
                    {"wrong_value": v},
                )
        return v


class RingConfig(ConnectionConfig):
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
    line_width: int | None = Field(5, description="Line widths for the progress bars.")
    start_position: int | None = Field(
        90,
        description="Start position for the progress bars in degrees. Default is 90 degrees - corespons to "
        "the top of the ring.",
    )
    min_value: int | None = Field(0, description="Minimum value for the progress bars.")
    max_value: int | None = Field(100, description="Maximum value for the progress bars.")
    precision: int | None = Field(3, description="Precision for the progress bars.")
    update_behaviour: Literal["manual", "auto"] | None = Field(
        "auto", description="Update behaviour for the progress bars."
    )
    connections: RingConnections | None = Field(
        default_factory=RingConnections, description="Connections for the progress bars."
    )


class Ring(BECConnector):
    USER_ACCESS = [
        "get_all_rpc",
        "rpc_id",
        "config_dict",
        "set_value",
        "set_color",
        "set_background",
        "set_line_width",
        "set_min_max_values",
        "set_start_angle",
        "set_connections",
        "reset_connection",
    ]

    def __init__(
        self,
        parent=None,
        parent_progress_widget=None,
        config: RingConfig | dict | None = None,
        client=None,
        gui_id: Optional[str] = None,
    ):
        if config is None:
            config = RingConfig(widget_class=self.__class__.__name__)
            self.config = config
        else:
            if isinstance(config, dict):
                config = RingConfig(**config)
            self.config = config
        super().__init__(client=client, config=config, gui_id=gui_id)

        self.parent_progress_widget = parent_progress_widget
        self.color = None
        self.background_color = None
        self.start_position = None
        self.config = config
        self.value = 0
        self.RID = None
        self._init_config_params()

    def _init_config_params(self):
        self.color = self.convert_color(self.config.color)
        self.background_color = self.convert_color(self.config.background_color)
        self.set_start_angle(self.config.start_position)
        if self.config.connections:
            self.set_connections(self.config.connections.slot, self.config.connections.endpoint)

    def set_value(self, value: int | float):
        self.value = round(
            max(self.config.min_value, min(self.config.max_value, value)), self.config.precision
        )

    def set_color(self, color: str | tuple):
        self.config.color = color
        self.color = self.convert_color(color)

    def set_background(self, color: str | tuple):
        self.config.background_color = color
        self.color = self.convert_color(color)

    def set_line_width(self, width: int):
        self.config.line_width = width

    def set_min_max_values(self, min_value: int, max_value: int):
        self.config.min_value = min_value
        self.config.max_value = max_value

    def set_start_angle(self, start_angle: int):
        self.config.start_position = start_angle
        self.start_position = start_angle * 16

    @staticmethod
    def convert_color(color):
        converted_color = None
        if isinstance(color, str):
            converted_color = QtGui.QColor(color)
        elif isinstance(color, tuple):
            converted_color = QtGui.QColor(*color)
        return converted_color

    def set_connections(self, slot: str, endpoint: str | EndpointInfo):
        if self.config.connections.endpoint == endpoint and self.config.connections.slot == slot:
            return
        else:
            self.bec_dispatcher.disconnect_slot(
                self.config.connections.slot, self.config.connections.endpoint
            )
            self.config.connections = RingConnections(slot=slot, endpoint=endpoint)
            self.bec_dispatcher.connect_slot(getattr(self, slot), endpoint)

    def reset_connection(self):
        self.bec_dispatcher.disconnect_slot(
            self.config.connections.slot, self.config.connections.endpoint
        )
        self.config.connections = RingConnections()

    def on_scan_progress(self, msg, meta):
        current_RID = meta.get("RID", None)
        if current_RID != self.RID:
            self.set_min_max_values(0, msg.get("max_value", 100))
        self.set_value(msg.get("value", 0))
        self.parent_progress_widget.update()

    def on_device_readback(self, msg, meta):
        if isinstance(self.config.connections.endpoint, EndpointInfo):
            endpoint = self.config.connections.endpoint.endpoint
        else:
            endpoint = self.config.connections.endpoint
        device = endpoint.split("/")[-1]
        value = msg.get("signals").get(device).get("value")
        self.set_value(value)
        self.parent_progress_widget.update()

    def cleanup(self):
        self.reset_connection()
        super().cleanup()
