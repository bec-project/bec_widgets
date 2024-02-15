from collections import defaultdict
from typing import Literal, Optional, Any

import pyqtgraph as pg
from pydantic import Field, BaseModel
from pyqtgraph import mkBrush

from qtpy.QtWidgets import QWidget
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtGui import QColor

from bec_lib.utils import user_access
from bec_lib import MessageEndpoints
from bec_widgets.utils import Colors
from bec_widgets.widgets.plots import BECPlotBase, WidgetConfig


class SignalData(BaseModel):
    """The data configuration of a signal in the 1D waveform widget for x and y axis."""

    # TODO add validator on name and entry
    name: str
    entry: str
    unit: Optional[str] = None  # todo implement later
    modifier: Optional[str] = None  # todo implement later


class Signal(BaseModel):
    """The configuration of a signal in the 1D waveform widget."""

    source: str  # TODO add validator on the source type
    x: SignalData
    y: SignalData


class CurveConfig(BaseModel):
    label: Optional[str] = Field(None, description="The label of the curve.")
    color: Optional[Any] = Field(None, description="The color of the curve.")
    symbol: Optional[str] = Field(None, description="The symbol of the curve.")
    symbol_size: Optional[int] = Field(5, description="The size of the symbol of the curve.")
    pen_width: Optional[int] = Field(2, description="The width of the pen of the curve.")
    pen_style: Optional[Literal["solid", "dash", "dot", "dashdot"]] = Field(
        "solid", description="The style of the pen of the curve."
    )  # TODO check if valid
    source: Optional[str] = Field(
        None, description="The source of the curve."
    )  # TODO here on or curve??
    signals: Optional[Signal] = Field(None, description="The signal of the curve.")


class Waveform1DConfig(WidgetConfig):
    color_palette: Literal["plasma", "viridis", "inferno", "magma"] = Field(
        "plasma", description="The color palette of the figure widget."
    )
    curves: list[CurveConfig] = Field(
        [], description="The list of curves to be added to the 1D waveform widget."
    )  # todo maybe dict??


class BECCurve(pg.PlotDataItem):  # TODO decide what will be accessible from the parent
    def __init__(
        self,
        config: Optional[CurveConfig] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if config is None:
            config = CurveConfig(widget_class=self.__class__.__name__)
        self.config = config

        self.apply_config()

    def apply_config(self):
        self.setPen(self.config.color)
        self.setSymbol(self.config.symbol)
        # self.setSymbolSize(self.config.symbol_size)
        # self.setSymbolBrush(self.config.color)
        # self.setPenWidth(self.config.pen_width)


class BECWaveform1D(BECPlotBase):
    scan_signal_update = pyqtSignal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        parent_figure=None,
        config: Optional[Waveform1DConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
    ):
        if config is None:
            config = Waveform1DConfig(widget_class=self.__class__.__name__)
        super().__init__(
            parent=parent, parent_figure=parent_figure, config=config, client=client, gui_id=gui_id
        )

        # self.curves = {}
        self.curve_data = defaultdict(dict)
        self.scanID = None

        # TODO add proxy later when update function is ready
        self.proxy_update_plot = pg.SignalProxy(
            self.scan_signal_update, rateLimit=25, slot=self.update_scan_segment_plot
        )

        # Get bec shortcuts dev, scans, queue, scan_storage, dap
        self.get_bec_shortcuts()

        # Connect dispatcher signals
        self.bec_dispatcher.connect_slot(self.on_scan_segment, MessageEndpoints.scan_segment())

        # TODO DEbug
        # self.add_curve("bpm4i")
        self.add_scan("samx", "samx", "bpm4i", "bpm4i")

        self.addLegend()

    def add_curve_by_config(self, curve_config: CurveConfig):
        # TODO something like this
        curve = BECCurve()
        self.curves[curve_config.label] = curve
        self.addItem(curve)

    def save_curve_config(self): ...

    @user_access
    def add_scan(
        self,
        x_name: str,
        x_entry: str,
        y_name: str,
        y_entry: str,
        color: Optional[str] = None,
        label: Optional[str] = None,
        symbol: Optional[str] = None,
        symbol_size: Optional[int] = None,
        symbol_color: Optional[str] = None,
        pen_width: Optional[int] = None,
        pen_style: Optional[Literal["solid", "dash", "dot", "dashdot"]] = None,
    ):
        # Check if curve already exists
        curve_source = "scan_segment"
        curve_id = (x_name, x_entry, y_name, y_entry)
        if curve_id in self.curve_data[curve_source]:
            raise ValueError(f"Curve with ID {curve_id} already exists in widget {self.gui_id}.")

        # Generate curve properties if not given
        if label is None:
            label = f"{y_name}-{y_entry}"
        if color is None:
            color = Colors.golden_angle_color(
                colormap=self.config.color_palette, num=len(self.curves) + 1
            )[-1]
            # color_brush = mkBrush(color)
        if symbol_color is None:
            symbol_color = color

        # Create curve by config
        curve_config = CurveConfig(
            label=label,
            color=color,
            symbol=symbol,
            symbol_size=symbol_size,
            symbol_color=symbol_color,
            pen_width=pen_width,
            pen_style=pen_style,
            source=curve_source,
            signals=Signal(
                source=curve_source,
                x=SignalData(name=x_name, entry=x_entry),
                y=SignalData(name=y_name, entry=y_entry),
            ),
        )
        curve = BECCurve(config=curve_config, name=label)
        self.curve_data[curve_source][curve_id] = curve
        self.addItem(curve)

    # def _create_bec_curve(self, curve_config: CurveConfig, source: str = "scan_segment"):
    #     curve = BECCurve(config=curve_config)
    #     #TODO add checkign if curve already exists
    #     self.curve_data[source][curve_config.label] = curve
    #     return curve

    def add_source(self, source: str):
        # TODO general function to add different sources
        # self.curve_data[source]
        pass

    def add_curve(self, curve_id: str, source: str = None):
        # curve = BECCurve()
        # curve = pg.PlotDataItem(name=curve_id)
        curve = BECCurve(name=curve_id)
        # self.curves[curve_id] = curve
        self.addItem(curve)

    def update_curve(self, source: str, curve_id: tuple, x, y): ...

    @pyqtSlot(dict, dict)
    def on_scan_segment(self, msg: dict, metadata: dict):
        """
        Handle new scan segments and saves data to a dictionary. Linked through bec_dispatcher.

        Args:
            msg (dict): Message received with scan data.
            metadata (dict): Metadata of the scan.
        """
        current_scanID = msg.get("scanID", None)
        if current_scanID is None:
            return

        if current_scanID != self.scanID:
            # self.clear() #TODO check if this is the right way to clear the plot
            self.scanID = current_scanID
            self.scan_data = self.queue.scan_storage.find_scan_by_ID(self.scanID)

        # self.scan_signal_update.emit()
        # self.update_from_storage(data=self.scan_data)
        self.update_scan_segment_plot()

    def update_scan_segment_plot(self):
        data = self.scan_data.data

        for curve_id, curve in self.curve_data["scan_segment"].items():
            x_name = curve_id[0]
            x_entry = curve_id[1]
            y_name = curve_id[2]
            y_entry = curve_id[3]

            data_x = data[x_name][x_entry].val
            data_y = data[y_name][y_entry].val

            curve.setData(data_x, data_y)
