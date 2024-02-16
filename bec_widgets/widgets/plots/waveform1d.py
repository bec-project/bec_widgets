from collections import defaultdict
from typing import Literal, Optional, Any

import numpy as np
import pyqtgraph as pg
from pydantic import Field, BaseModel
from pyqtgraph import mkBrush

from qtpy.QtWidgets import QWidget
from qtpy import QtCore
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtGui import QColor

from bec_lib.scan_data import ScanData
from bec_lib.scan_items import ScanItem
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
    symbol: Optional[str] = Field("o", description="The symbol of the curve.")
    symbol_color: Optional[str] = Field(None, description="The color of the symbol of the curve.")
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
    curves: dict[str, CurveConfig] = Field(
        {}, description="The list of curves to be added to the 1D waveform widget."
    )


class BECCurve(pg.PlotDataItem):  # TODO decide what will be accessible from the parent
    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[CurveConfig] = None,
        **kwargs,
    ):
        super().__init__(name=name, **kwargs)
        if config is None:
            config = CurveConfig(label=name, widget_class=self.__class__.__name__)
        self.config = config

        self.apply_config()

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
            brush = mkBrush(color=symbol_color)
            self.setSymbolBrush(brush)
            self.setSymbolSize(self.config.symbol_size)
            self.setSymbol(self.config.symbol)

    def update_data(self, x, y):
        if self.config.source == "custom":
            self.setData(x, y)
        else:
            raise ValueError(f"Source {self.config.source} do not allow custom data setting.")


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

        self.curve_data = defaultdict(dict)
        self.scanID = None

        self.proxy_update_plot = pg.SignalProxy(
            self.scan_signal_update, rateLimit=25, slot=self._update_scan_segment_plot
        )

        # Get bec shortcuts dev, scans, queue, scan_storage, dap
        self.get_bec_shortcuts()

        # Connect dispatcher signals
        self.bec_dispatcher.connect_slot(self.on_scan_segment, MessageEndpoints.scan_segment())

        # TODO DEbug
        # Scan curves
        self.add_scan("samx", "samx", "bpm4i", "bpm4i", pen_style="dash")
        self.add_scan("samx", "samx", "bpm3a", "bpm3a", pen_style="solid")
        self.add_scan("samx", "samx", "bpm4d", "bpm4d", pen_style="dot")
        # Custom curves
        self.add_curve(
            x=[1, 2, 3, 4, 5],
            y=[1, 2, 3, 4, 5],
            label="curve-custom",
            color="blue",
            pen_style="dashdot",
        )
        self.add_curve(x=[1, 2, 3, 4, 5], y=[5, 4, 3, 2, 1], color="red", pen_style="dashdot")

        self.addLegend()

    def add_curve_by_config(self, curve_config: CurveConfig): ...

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
        **kwargs,
    ):
        # Check if curve already exists
        curve_source = "scan_segment"
        label = label or f"{y_name}-{y_entry}"

        curve_exits = self._check_curve_id(label, self.curve_data)
        if curve_exits:
            raise ValueError(f"Curve with ID '{label}' already exists in widget '{self.gui_id}'.")
            return

        color = (
            color
            or Colors.golden_angle_color(
                colormap=self.config.color_palette, num=len(self.curves) + 1
            )[-1]
        )

        # Create curve by config
        curve_config = CurveConfig(
            label=label,
            color=color,
            source=curve_source,
            signals=Signal(
                source=curve_source,
                x=SignalData(name=x_name, entry=x_entry),
                y=SignalData(name=y_name, entry=y_entry),
            ),
            **kwargs,
        )
        self._add_curve_object(name=label, source=curve_source, config=curve_config)

    @user_access
    def add_curve(
        self,
        x: list | np.ndarray,
        y: list | np.ndarray,
        label: str = None,
        color: str = None,
        **kwargs,
    ):
        curve_source = "custom"
        curve_id = label or f"Curve {len(self.curves) + 1}"

        curve_exits = self._check_curve_id(curve_id, self.curve_data)
        if curve_exits:
            raise ValueError(
                f"Curve with ID '{curve_id}' already exists in widget '{self.gui_id}'."
            )

        color = (
            color
            or Colors.golden_angle_color(
                colormap=self.config.color_palette, num=len(self.curves) + 1
            )[-1]
        )

        # Create curve by config
        curve_config = CurveConfig(
            label=curve_id,
            color=color,
            source=curve_source,
            **kwargs,
        )

        self._add_curve_object(name=curve_id, source=curve_source, config=curve_config, data=(x, y))

    def _add_curve_object(
        self,
        name: str,
        source: str,
        config: CurveConfig,
        data: tuple[list | np.ndarray, list | np.ndarray] = None,
    ):
        """
        Add a curve object to the plot widget.
        Args:
            name(str): ID of the curve.
            source(str): Source of the curve.
            config(CurveConfig): Configuration of the curve.
            data(tuple[list|np.ndarray,list|np.ndarray], optional): Data (x,y) to be plotted. Defaults to None.
        """
        curve = BECCurve(config=config, name=name)
        self.curve_data[source][name] = curve
        self.addItem(curve)
        self.config.curves[name] = curve.config
        if data is not None:
            curve.setData(data[0], data[1])

    def _check_curve_id(self, val: Any, dict_to_check: dict) -> bool:
        """
        Check if val is in the values of the dict_to_check or in the values of the nested dictionaries.
        Args:
            val(Any): Value to check.
            dict_to_check(dict): Dictionary to check.

        Returns:
            bool: True if val is in the values of the dict_to_check or in the values of the nested dictionaries, False otherwise.
        """
        if val in dict_to_check.keys():
            return True
        for key in dict_to_check:
            if isinstance(dict_to_check[key], dict):
                if self._check_curve_id(val, dict_to_check[key]):
                    return True
        return False

    def remove_curve(self, *identifiers):
        """
        Remove a curve from the plot widget.
        Args:
            *identifiers: Identifier of the curve to be removed. Can be either an integer (index) or a string (curve_id).
        """
        for identifier in identifiers:
            if isinstance(identifier, int):
                self._remove_curve_by_order(identifier)
            elif isinstance(identifier, str):
                self._remove_curve_by_id(identifier)
            else:
                raise ValueError(
                    "Each identifier must be either an integer (index) or a string (curve_id)."
                )

    def _remove_curve_by_id(self, curve_id):
        """
        Remove a curve by its ID from the plot widget.
        Args:
            curve_id(str): ID of the curve to be removed.
        """
        for source, curves in self.curve_data.items():
            if curve_id in curves:
                curve = curves.pop(curve_id)
                self.removeItem(curve)
                del self.config.curves[curve_id]
                if curve in self.curves:
                    self.curves.remove(curve)
                return
        raise KeyError(f"Curve with ID '{curve_id}' not found.")

    def _remove_curve_by_order(self, N):
        """
        Remove a curve by its order from the plot widget.
        Args:
            N(int): Order of the curve to be removed.
        """
        if N < len(self.curves):
            curve = self.curves[N]
            curve_id = curve.name()  # Assuming curve's name is used as its ID
            self.removeItem(curve)
            del self.config.curves[curve_id]
            # Remove from self.curve_data
            for source, curves in self.curve_data.items():
                if curve_id in curves:
                    del curves[curve_id]
                    break
        else:
            raise IndexError(f"Curve order {N} out of range.")

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
            self.scan_segment_data = self.queue.scan_storage.find_scan_by_ID(self.scanID)

        self.scan_signal_update.emit()

    def _update_scan_segment_plot(self):
        """Update the plot with the data from the scan segment."""
        data = self.scan_segment_data.data
        self._update_scan_curves(data)

    def _update_scan_curves(self, data: ScanData):
        """
        Update the scan curves with the data from the scan segment.
        Args:
            data(ScanData): Data from the scan segment.
        """
        for curve_id, curve in self.curve_data["scan_segment"].items():
            x_name = curve.config.signals.x.name
            x_entry = curve.config.signals.x.entry
            y_name = curve.config.signals.y.name
            y_entry = curve.config.signals.y.entry

            try:
                data_x = data[x_name][x_entry].val
                data_y = data[y_name][y_entry].val
            except TypeError:
                continue

            curve.setData(data_x, data_y)

    @user_access
    def update_scan_curve_history(self, scanID: str = None, scan_index: int = None):
        """
        Update the scan curves with the data from the scan storage.
        Provide only one of scanID or scan_index.
        Args:
            scanID(str, optional): ScanID of the scan to be updated. Defaults to None.
            scan_index(int, optional): Index of the scan to be updated. Defaults to None.
        """
        if scan_index is not None and scanID is not None:
            raise ValueError("Only one of scanID or scan_index can be provided.")

        if scan_index is not None:
            data = self.queue.scan_storage.storage[scan_index].data
        elif scanID is not None:
            data = self.queue.scan_storage.find_scan_by_ID(self.scanID).data

        self._update_scan_curves(data)
