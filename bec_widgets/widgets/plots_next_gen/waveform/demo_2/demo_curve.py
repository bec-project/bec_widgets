from typing import Optional, Literal

import pyqtgraph as pg
from qtpy.QtCore import Qt
from pydantic import BaseModel, Field


class CurveConfig(BaseModel):
    label: str = Field(..., description="Label/ID of this curve")
    color: str = Field("blue", description="Curve color")
    symbol: Optional[str] = Field(None, description="Symbol e.g. 'o', 'x'")
    pen_width: int = Field(2, description="Pen width in px")
    pen_style: Literal["solid", "dash", "dot", "dashdot"] = "solid"

    # You can add device/signal if desired:
    # signals: Optional[Signal] = None
    # etc.

    class Config:
        model_config = {"validate_assignment": True}


pen_style_map = {
    "solid": Qt.SolidLine,
    "dash": Qt.DashLine,
    "dot": Qt.DotLine,
    "dashdot": Qt.DashDotLine,
}


class BECCurve(pg.PlotDataItem):
    """
    A custom PlotDataItem that holds a reference to a Pydantic-based CurveConfig.
    """

    def __init__(self, config: CurveConfig, parent=None):
        super().__init__(name=config.label)  # set the PlotDataItem name
        self.config = config
        self._parent = parent  # optional reference to the WaveformPlot
        # now apply config to actual PlotDataItem
        self.apply_config()

    def apply_config(self):
        style = pen_style_map.get(self.config.pen_style, Qt.SolidLine)
        pen = pg.mkPen(color=self.config.color, width=self.config.pen_width, style=style)
        self.setPen(pen)

        if self.config.symbol is not None:
            self.setSymbol(self.config.symbol)
        else:
            self.setSymbol(None)

    def set_data_custom(self, x, y):
        # If you only want to allow custom data if config.source == "custom", etc.
        self.setData(x, y)
