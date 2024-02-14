from typing import Literal, Optional

import pyqtgraph as pg
from pydantic import Field, BaseModel

from qtpy.QtWidgets import QWidget
from qtpy.QtCore import Slot as pyqtSlot

from bec_lib import MessageEndpoints
from bec_widgets.widgets.plots import BECPlotBase, WidgetConfig


class SignalData(BaseModel):
    """The data configuration of a signal in the 1D waveform widget for x and y axis."""

    name: str
    entry: str
    unit: Optional[str]  # todo implement later
    modifier: Optional[str]  # todo implement later


class Signal(BaseModel):
    """The configuration of a signal in the 1D waveform widget."""

    source: str  # TODO add validator on the source type
    x: SignalData
    y: SignalData


class CurveConfig(BaseModel):
    label: Optional[str] = Field(None, description="The label of the curve.")
    color: Optional[str] = Field(None, description="The color of the curve.")
    symbol: Optional[str] = Field(None, description="The symbol of the curve.")
    symbol_size: Optional[int] = Field(None, description="The size of the symbol of the curve.")
    pen_width: Optional[int] = Field(None, description="The width of the pen of the curve.")
    pen_style: Optional[Literal["solid", "dash", "dot", "dashdot"]] = Field(
        None, description="The style of the pen of the curve."
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


class BECCurve(pg.PlotDataItem):
    def __init__(
        self,
        config: Optional[CurveConfig] = None,
    ):
        # if config is None: #TODO custom later
        #     config = CurveConfig(widget_class=self.__class__.__name__)
        self.config = config


class BECWaveform1D(BECPlotBase):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        config: Optional[Waveform1DConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
    ):
        if config is None:
            config = Waveform1DConfig(widget_class=self.__class__.__name__)
        super().__init__(parent=parent, config=config, client=client, gui_id=gui_id)

        self.curves = {}
        self.scanID = None

        self.proxy_update_plot = pg.SignalProxy(
            self.update_signal, rateLimit=25, slot=self.update_scan_segment_plot
        )

        # Get bec shortcuts dev, scans, queue, scan_storage, dap
        self.get_bec_shortcuts()

        # Connect dispatcher signals
        self.bec_dispatcher.connect_slot(self.on_scan_segment, MessageEndpoints.scan_segment())

    def add_curve_by_config(self, curve_config: CurveConfig):
        # TODO something like this
        curve = BECCurve()
        self.curves[curve_config.label] = curve
        self.addItem(curve)

    def add_curve(self, curve_id: str):
        curve = BECCurve()
        self.curves[curve_id] = curve
        self.addItem(curve)

    def update_curve(self, curve_id: str, x, y):
        self.curves[curve_id].setData(x, y)

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

        scan_data_current = self.scan_data.data
        data_x = scan_data_current["samx"]["samx"]
        data_y = scan_data_current["bpm4i"]["bpm4i"]

        self.update_curve("bpm4i", data_x, data_y)
