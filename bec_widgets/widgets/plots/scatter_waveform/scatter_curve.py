from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import numpy as np
import pyqtgraph as pg
from bec_lib import bec_logger
from pydantic import BaseModel, Field, ValidationError, field_validator
from qtpy import QtCore

from bec_widgets.utils import BECConnector, Colors, ConnectionConfig

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.plots.scatter_waveform.scatter_waveform import ScatterWaveform

logger = bec_logger.logger


# noinspection PyDataclass
class ScatterDeviceSignal(BaseModel):
    """The configuration of a signal in the scatter waveform widget."""

    name: str
    entry: str

    model_config: dict = {"validate_assignment": True}


# noinspection PyDataclass
class ScatterCurveConfig(ConnectionConfig):
    parent_id: str | None = Field(None, description="The parent plot of the curve.")
    label: str | None = Field(None, description="The label of the curve.")
    color: str | tuple = Field("#808080", description="The color of the curve.")
    symbol: str | None = Field("o", description="The symbol of the curve.")
    symbol_size: int | None = Field(7, description="The size of the symbol of the curve.")
    pen_width: int | None = Field(4, description="The width of the pen of the curve.")
    pen_style: Literal["solid", "dash", "dot", "dashdot"] = Field(
        "solid", description="The style of the pen of the curve."
    )
    color_map: str | None = Field(
        "plasma", description="The color palette of the figure widget.", validate_default=True
    )
    x_device: ScatterDeviceSignal | None = Field(
        None, description="The x device signal of the scatter waveform."
    )
    y_device: ScatterDeviceSignal | None = Field(
        None, description="The y device signal of the scatter waveform."
    )
    z_device: ScatterDeviceSignal | None = Field(
        None, description="The z device signal of the scatter waveform."
    )

    model_config: dict = {"validate_assignment": True}
    _validate_color_palette = field_validator("color_map")(Colors.validate_color_map)


class ScatterCurve(BECConnector, pg.PlotDataItem):
    """Scatter curve item for the scatter waveform widget."""

    USER_ACCESS = ["color_map"]

    def __init__(
        self,
        parent_item: ScatterWaveform,
        name: str | None = None,
        config: ScatterCurveConfig | None = None,
        gui_id: str | None = None,
        **kwargs,
    ):
        if config is None:
            config = ScatterCurveConfig(
                label=name,
                widget_class=self.__class__.__name__,
                parent_id=parent_item.config.gui_id,
            )
            self.config = config
        else:
            self.config = config
            name = config.label
        self.parent_item = parent_item
        self.parent_id = self.parent_item.gui_id
        super().__init__(name=name, config=config, gui_id=gui_id, **kwargs)

        self.data_z = None  # color scaling needs to be cashed for changing colormap
        self.apply_config()

    def parent(self):
        return self.parent_item

    def apply_config(self, config: dict | ScatterCurveConfig | None = None, **kwargs) -> None:
        """
        Apply the configuration to the curve.

        Args:
            config(dict|ScatterCurveConfig, optional): The configuration to apply.
        """

        if config is not None:
            if isinstance(config, dict):
                config = ScatterCurveConfig(**config)
            self.config = config

        pen_style_map = {
            "solid": QtCore.Qt.SolidLine,
            "dash": QtCore.Qt.DashLine,
            "dot": QtCore.Qt.DotLine,
            "dashdot": QtCore.Qt.DashDotLine,
        }
        pen_style = pen_style_map.get(self.config.pen_style, QtCore.Qt.SolidLine)

        pen = pg.mkPen(color=self.config.color, width=self.config.pen_width, style=pen_style)
        self.setPen(pen)

        if self.config.symbol:
            self.setSymbolSize(self.config.symbol_size)
            self.setSymbol(self.config.symbol)

    @property
    def color_map(self) -> str:
        """The color map of the scatter curve."""
        return self.config.color_map

    @color_map.setter
    def color_map(self, value: str):
        """
        Set the color map of the scatter curve.

        Args:
            value(str): The color map to set.
        """
        try:
            if value != self.config.color_map:
                self.config.color_map = value
                self.refresh_color_map(value)
        except ValidationError:
            return

    def set_data(
        self,
        x: list[float] | np.ndarray,
        y: list[float] | np.ndarray,
        z: list[float] | np.ndarray,
        color_map: str | None = None,
    ):
        """
        Set the data of the scatter curve.

        Args:
            x (list[float] | np.ndarray): The x data of the scatter curve.
            y (list[float] | np.ndarray): The y data of the scatter curve.
            z (list[float] | np.ndarray): The z data of the scatter curve.
            color_map (str | None): The color map of the scatter curve.
        """
        if color_map is None:
            color_map = self.config.color_map

        self.data_z = z
        color_z = self._make_z_gradient(z, color_map)
        try:
            self.setData(x=x, y=y, symbolBrush=color_z)
        except TypeError:
            logger.error("Error in setData, one of the data arrays is None")

    def _make_z_gradient(self, data_z: list | np.ndarray, colormap: str) -> list | None:
        """
        Make a gradient color for the z values.

        Args:
            data_z(list|np.ndarray): Z values.
            colormap(str): Colormap for the gradient color.

        Returns:
            list: List of colors for the z values.
        """
        # Normalize z_values for color mapping
        z_min, z_max = np.min(data_z), np.max(data_z)

        if z_max != z_min:  # Ensure that there is a range in the z values
            z_values_norm = (data_z - z_min) / (z_max - z_min)
            colormap = pg.colormap.get(colormap)  # using colormap from global settings
            colors = [colormap.map(z, mode="qcolor") for z in z_values_norm]
            return colors
        else:
            return None

    def refresh_color_map(self, color_map: str):
        """
        Refresh the color map of the scatter curve.

        Args:
            color_map(str): The color map to use.
        """
        x_data, y_data = self.getData()
        if x_data is None or y_data is None:
            return
        if self.data_z is not None:
            self.set_data(x_data, y_data, self.data_z, color_map)
