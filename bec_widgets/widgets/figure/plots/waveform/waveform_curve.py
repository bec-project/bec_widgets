from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Optional

import numpy as np
import pyqtgraph as pg
from bec_lib.logger import bec_logger
from pydantic import BaseModel, Field, field_validator
from qtpy import QtCore

from bec_widgets.utils import BECConnector, Colors, ConnectionConfig

if TYPE_CHECKING:
    from bec_widgets.widgets.figure.plots.waveform import BECWaveform1D

logger = bec_logger.logger


class SignalData(BaseModel):
    """The data configuration of a signal in the 1D waveform widget for x and y axis."""

    name: str
    entry: str
    unit: Optional[str] = None  # todo implement later
    modifier: Optional[str] = None  # todo implement later
    limits: Optional[list[float]] = None  # todo implement later
    model_config: dict = {"validate_assignment": True}


class Signal(BaseModel):
    """The configuration of a signal in the 1D waveform widget."""

    source: str
    x: Optional[SignalData] = None
    y: SignalData
    z: Optional[SignalData] = None
    dap: Optional[str] = None
    model_config: dict = {"validate_assignment": True}


class CurveConfig(ConnectionConfig):
    parent_id: Optional[str] = Field(None, description="The parent plot of the curve.")
    label: Optional[str] = Field(None, description="The label of the curve.")
    color: Optional[str | tuple] = Field(None, description="The color of the curve.")
    symbol: Optional[str | None] = Field("o", description="The symbol of the curve.")
    symbol_color: Optional[str | tuple] = Field(
        None, description="The color of the symbol of the curve."
    )
    symbol_size: Optional[int] = Field(7, description="The size of the symbol of the curve.")
    pen_width: Optional[int] = Field(4, description="The width of the pen of the curve.")
    pen_style: Optional[Literal["solid", "dash", "dot", "dashdot"]] = Field(
        "solid", description="The style of the pen of the curve."
    )
    source: Optional[str] = Field(None, description="The source of the curve.")
    signals: Optional[Signal] = Field(None, description="The signal of the curve.")
    color_map_z: Optional[str] = Field(
        "magma", description="The colormap of the curves z gradient.", validate_default=True
    )

    model_config: dict = {"validate_assignment": True}

    _validate_color_map_z = field_validator("color_map_z")(Colors.validate_color_map)
    _validate_color = field_validator("color")(Colors.validate_color)
    _validate_symbol_color = field_validator("symbol_color")(Colors.validate_color)


class BECCurve(BECConnector, pg.PlotDataItem):
    USER_ACCESS = [
        "remove",
        "dap_params",
        "_rpc_id",
        "_config_dict",
        "set",
        "set_data",
        "set_color",
        "set_color_map_z",
        "set_symbol",
        "set_symbol_color",
        "set_symbol_size",
        "set_pen_width",
        "set_pen_style",
        "get_data",
        "dap_params",
    ]

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[CurveConfig] = None,
        gui_id: Optional[str] = None,
        parent_item: Optional[BECWaveform1D] = None,
        **kwargs,
    ):
        if config is None:
            config = CurveConfig(label=name, widget_class=self.__class__.__name__)
            self.config = config
        else:
            self.config = config
            # config.widget_class = self.__class__.__name__
        super().__init__(config=config, gui_id=gui_id)
        pg.PlotDataItem.__init__(self, name=name)

        self.parent_item = parent_item
        self.apply_config()
        self.dap_params = None
        self.dap_summary = None
        if kwargs:
            self.set(**kwargs)

    def apply_config(self):
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
            symbol_color = self.config.symbol_color or self.config.color
            brush = pg.mkBrush(color=symbol_color)

            self.setSymbolBrush(brush)
            self.setSymbolSize(self.config.symbol_size)
            self.setSymbol(self.config.symbol)

    @property
    def dap_params(self):
        return self._dap_params

    @dap_params.setter
    def dap_params(self, value):
        self._dap_params = value

    @property
    def dap_summary(self):
        return self._dap_report

    @dap_summary.setter
    def dap_summary(self, value):
        self._dap_report = value

    def set_data(self, x, y):
        if self.config.source == "custom":
            self.setData(x, y)
        else:
            raise ValueError(f"Source {self.config.source} do not allow custom data setting.")

    def set(self, **kwargs):
        """
        Set the properties of the curve.

        Args:
            **kwargs: Keyword arguments for the properties to be set.

        Possible properties:
            - color: str
            - symbol: str
            - symbol_color: str
            - symbol_size: int
            - pen_width: int
            - pen_style: Literal["solid", "dash", "dot", "dashdot"]
        """

        # Mapping of keywords to setter methods
        method_map = {
            "color": self.set_color,
            "color_map_z": self.set_color_map_z,
            "symbol": self.set_symbol,
            "symbol_color": self.set_symbol_color,
            "symbol_size": self.set_symbol_size,
            "pen_width": self.set_pen_width,
            "pen_style": self.set_pen_style,
        }
        for key, value in kwargs.items():
            if key in method_map:
                method_map[key](value)
            else:
                logger.warning(f"Warning: '{key}' is not a recognized property.")

    def set_color(self, color: str, symbol_color: Optional[str] = None):
        """
        Change the color of the curve.

        Args:
            color(str): Color of the curve.
            symbol_color(str, optional): Color of the symbol. Defaults to None.
        """
        self.config.color = color
        self.config.symbol_color = symbol_color or color
        self.apply_config()

    def set_symbol(self, symbol: str):
        """
        Change the symbol of the curve.

        Args:
            symbol(str): Symbol of the curve.
        """
        self.config.symbol = symbol
        self.setSymbol(symbol)
        self.updateItems()

    def set_symbol_color(self, symbol_color: str):
        """
        Change the symbol color of the curve.

        Args:
            symbol_color(str): Color of the symbol.
        """
        self.config.symbol_color = symbol_color
        self.apply_config()

    def set_symbol_size(self, symbol_size: int):
        """
        Change the symbol size of the curve.

        Args:
            symbol_size(int): Size of the symbol.
        """
        self.config.symbol_size = symbol_size
        self.apply_config()

    def set_pen_width(self, pen_width: int):
        """
        Change the pen width of the curve.

        Args:
            pen_width(int): Width of the pen.
        """
        self.config.pen_width = pen_width
        self.apply_config()

    def set_pen_style(self, pen_style: Literal["solid", "dash", "dot", "dashdot"]):
        """
        Change the pen style of the curve.

        Args:
            pen_style(Literal["solid", "dash", "dot", "dashdot"]): Style of the pen.
        """
        self.config.pen_style = pen_style
        self.apply_config()

    def set_color_map_z(self, colormap: str):
        """
        Set the colormap for the scatter plot z gradient.

        Args:
            colormap(str): Colormap for the scatter plot.
        """
        self.config.color_map_z = colormap
        self.apply_config()
        self.parent_item.scan_history(-1)

    def get_data(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Get the data of the curve.
        Returns:
            tuple[np.ndarray,np.ndarray]: X and Y data of the curve.
        """
        try:
            x_data, y_data = self.getData()
        except TypeError:
            x_data, y_data = np.array([]), np.array([])
        return x_data, y_data

    def clear_data(self):
        self.setData([], [])

    def remove(self):
        """Remove the curve from the plot."""
        # self.parent_item.removeItem(self)
        self.parent_item.remove_curve(self.name())
        self.rpc_register.remove_rpc(self)
