from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Literal, Optional

import numpy as np
import pyqtgraph as pg
from bec_lib import messages
from bec_lib.endpoints import MessageEndpoints
from bec_lib.scan_data import ScanData
from pydantic import Field, ValidationError
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtWidgets import QWidget

from bec_widgets.utils import Colors, EntryValidator
from bec_widgets.widgets.figure.plots.plot_base import BECPlotBase, SubplotConfig
from bec_widgets.widgets.figure.plots.waveform.waveform_curve import (
    BECCurve,
    CurveConfig,
    Signal,
    SignalData,
)


class Waveform1DConfig(SubplotConfig):
    color_palette: Literal["plasma", "viridis", "inferno", "magma"] = Field(
        "plasma", description="The color palette of the figure widget."
    )  # TODO can be extended to all colormaps from current pyqtgraph session
    curves: dict[str, CurveConfig] = Field(
        {}, description="The list of curves to be added to the 1D waveform widget."
    )


class BECWaveform(BECPlotBase):
    USER_ACCESS = [
        "rpc_id",
        "config_dict",
        "plot",
        "add_dap",
        "get_dap_params",
        "remove_curve",
        "scan_history",
        "curves",
        "get_curve",
        "get_curve_config",
        "apply_config",
        "get_all_data",
        "set",
        "set_title",
        "set_x_label",
        "set_y_label",
        "set_x_scale",
        "set_y_scale",
        "set_x_lim",
        "set_y_lim",
        "set_grid",
        "lock_aspect_ratio",
        "remove",
        "set_legend_label_size",
        "apply_config",
    ]
    scan_signal_update = pyqtSignal()
    dap_params_update = pyqtSignal(dict)

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

        self._curves_data = defaultdict(dict)
        self.old_scan_id = None
        self.scan_id = None

        # Scan segment update proxy
        self.proxy_update_plot = pg.SignalProxy(
            self.scan_signal_update, rateLimit=25, slot=self._update_scan_segment_plot
        )

        self.proxy_update_dap = pg.SignalProxy(
            self.scan_signal_update, rateLimit=25, slot=self.refresh_dap
        )
        # Get bec shortcuts dev, scans, queue, scan_storage, dap
        self.get_bec_shortcuts()

        # Connect dispatcher signals
        self.bec_dispatcher.connect_slot(self.on_scan_segment, MessageEndpoints.scan_segment())

        self.entry_validator = EntryValidator(self.dev)

        self.add_legend()
        self.apply_config(self.config)

    def apply_config(self, config: dict | SubplotConfig, replot_last_scan: bool = False):
        """
        Apply the configuration to the 1D waveform widget.

        Args:
            config(dict|SubplotConfig): Configuration settings.
            replot_last_scan(bool, optional): If True, replot the last scan. Defaults to False.
        """
        if isinstance(config, dict):
            try:
                config = Waveform1DConfig(**config)
            except ValidationError as e:
                print(f"Validation error when applying config to BECWaveform1D: {e}")
                return

        self.config = config
        self.plot_item.clear()  # TODO not sure if on the plot or layout level

        self.apply_axis_config()
        # Reset curves
        self._curves_data = defaultdict(dict)
        self._curves = self.plot_item.curves
        for curve_id, curve_config in self.config.curves.items():
            self.add_curve_by_config(curve_config)
        if replot_last_scan:
            self.scan_history(scan_index=-1)

    def change_gui_id(self, new_gui_id: str):
        """
        Change the GUI ID of the waveform widget and update the parent_id in all associated curves.

        Args:
            new_gui_id (str): The new GUI ID to be set for the waveform widget.
        """
        # Update the gui_id in the waveform widget itself
        self.gui_id = new_gui_id
        self.config.gui_id = new_gui_id

        for curve in self.curves:
            curve.config.parent_id = new_gui_id

    def add_curve_by_config(self, curve_config: CurveConfig | dict) -> BECCurve:
        """
        Add a curve to the plot widget by its configuration.

        Args:
            curve_config(CurveConfig|dict): Configuration of the curve to be added.

        Returns:
            BECCurve: The curve object.
        """
        if isinstance(curve_config, dict):
            curve_config = CurveConfig(**curve_config)
        curve = self._add_curve_object(
            name=curve_config.label, source=curve_config.source, config=curve_config
        )
        return curve

    def get_curve_config(self, curve_id: str, dict_output: bool = True) -> CurveConfig | dict:
        """
        Get the configuration of a curve by its ID.

        Args:
            curve_id(str): ID of the curve.

        Returns:
            CurveConfig|dict: Configuration of the curve.
        """
        for source, curves in self._curves_data.items():
            if curve_id in curves:
                if dict_output:
                    return curves[curve_id].config.model_dump()
                else:
                    return curves[curve_id].config

    @property
    def curves(self) -> list[BECCurve]:
        """
        Get the curves of the plot widget as a list
        Returns:
            list: List of curves.
        """
        return self._curves

    @curves.setter
    def curves(self, value: list[BECCurve]):
        self._curves = value

    def get_curve(self, identifier) -> BECCurve:
        """
        Get the curve by its index or ID.

        Args:
            identifier(int|str): Identifier of the curve. Can be either an integer (index) or a string (curve_id).

        Returns:
            BECCurve: The curve object.
        """
        if isinstance(identifier, int):
            return self.plot_item.curves[identifier]
        elif isinstance(identifier, str):
            for source_type, curves in self._curves_data.items():
                if identifier in curves:
                    return curves[identifier]
            raise ValueError(f"Curve with ID '{identifier}' not found.")
        else:
            raise ValueError("Identifier must be either an integer (index) or a string (curve_id).")

    def plot(
        self,
        x: list | np.ndarray | None = None,
        y: list | np.ndarray | None = None,
        x_name: str | None = None,
        y_name: str | None = None,
        z_name: str | None = None,
        x_entry: str | None = None,
        y_entry: str | None = None,
        z_entry: str | None = None,
        color: str | None = None,
        color_map_z: str | None = "plasma",
        label: str | None = None,
        validate: bool = True,
        dap: str | None = None,  # TODO add dap custom curve wrapper
    ) -> BECCurve:
        """
        Plot a curve to the plot widget.
        Args:
            x(list | np.ndarray): Custom x data to plot.
            y(list | np.ndarray): Custom y data to plot.
            x_name(str): The name of the device for the x-axis.
            y_name(str): The name of the device for the y-axis.
            z_name(str): The name of the device for the z-axis.
            x_entry(str): The name of the entry for the x-axis.
            y_entry(str): The name of the entry for the y-axis.
            z_entry(str): The name of the entry for the z-axis.
            color(str): The color of the curve.
            color_map_z(str): The color map to use for the z-axis.
            label(str): The label of the curve.
            validate(bool): If True, validate the device names and entries.
            dap(str): The dap model to use for the curve. If not specified, none will be added.

        Returns:
            BECCurve: The curve object.
        """

        if x is not None and y is not None:
            return self.add_curve_custom(x=x, y=y, label=label, color=color)
        else:
            if dap:
                self.add_dap(x_name=x_name, y_name=y_name, dap=dap)
            return self.add_curve_scan(
                x_name=x_name,
                y_name=y_name,
                z_name=z_name,
                x_entry=x_entry,
                y_entry=y_entry,
                z_entry=z_entry,
                color=color,
                color_map_z=color_map_z,
                label=label,
                validate_bec=validate,
            )

    def add_curve_custom(
        self,
        x: list | np.ndarray,
        y: list | np.ndarray,
        label: str = None,
        color: str = None,
        curve_source: str = "custom",
        **kwargs,
    ) -> BECCurve:
        """
        Add a custom data curve to the plot widget.

        Args:
            x(list|np.ndarray): X data of the curve.
            y(list|np.ndarray): Y data of the curve.
            label(str, optional): Label of the curve. Defaults to None.
            color(str, optional): Color of the curve. Defaults to None.
            curve_source(str, optional): Tag for source of the curve. Defaults to "custom".
            **kwargs: Additional keyword arguments for the curve configuration.

        Returns:
            BECCurve: The curve object.
        """
        curve_source = curve_source
        curve_id = label or f"Curve {len(self.plot_item.curves) + 1}"

        curve_exits = self._check_curve_id(curve_id, self._curves_data)
        if curve_exits:
            raise ValueError(
                f"Curve with ID '{curve_id}' already exists in widget '{self.gui_id}'."
            )

        color = (
            color
            or Colors.golden_angle_color(
                colormap=self.config.color_palette, num=len(self.plot_item.curves) + 1, format="HEX"
            )[-1]
        )

        # Create curve by config
        curve_config = CurveConfig(
            widget_class="BECCurve",
            parent_id=self.gui_id,
            label=curve_id,
            color=color,
            source=curve_source,
            **kwargs,
        )

        curve = self._add_curve_object(
            name=curve_id, source=curve_source, config=curve_config, data=(x, y)
        )
        return curve

    def add_curve_scan(
        self,
        x_name: str,
        y_name: str,
        z_name: Optional[str] = None,
        x_entry: Optional[str] = None,
        y_entry: Optional[str] = None,
        z_entry: Optional[str] = None,
        color: Optional[str] = None,
        color_map_z: Optional[str] = "plasma",
        label: Optional[str] = None,
        validate_bec: bool = True,
        source: str = "scan_segment",
        dap: Optional[str] = None,
        **kwargs,
    ) -> BECCurve:
        """
        Add a curve to the plot widget from the scan segment. #TODO adapt docs to DAP

        Args:
            x_name(str): Name of the x signal.
            x_entry(str): Entry of the x signal.
            y_name(str): Name of the y signal.
            y_entry(str): Entry of the y signal.
            z_name(str): Name of the z signal.
            z_entry(str): Entry of the z signal.
            color(str, optional): Color of the curve. Defaults to None.
            color_map_z(str): The color map to use for the z-axis.
            label(str, optional): Label of the curve. Defaults to None.
            **kwargs: Additional keyword arguments for the curve configuration.

        Returns:
            BECCurve: The curve object.
        """
        # Check if curve already exists
        curve_source = source

        # Get entry if not provided and validate
        x_entry, y_entry, z_entry = self._validate_signal_entries(
            x_name, y_name, z_name, x_entry, y_entry, z_entry, validate_bec
        )

        if z_name is not None and z_entry is not None:
            label = label or f"{z_name}-{z_entry}"
        else:
            label = label or f"{y_name}-{y_entry}"

        curve_exits = self._check_curve_id(label, self._curves_data)
        if curve_exits:
            raise ValueError(f"Curve with ID '{label}' already exists in widget '{self.gui_id}'.")

        color = (
            color
            or Colors.golden_angle_color(
                colormap=self.config.color_palette, num=len(self.plot_item.curves) + 1, format="HEX"
            )[-1]
        )

        # Create curve by config
        curve_config = CurveConfig(
            widget_class="BECCurve",
            parent_id=self.gui_id,
            label=label,
            color=color,
            color_map_z=color_map_z,
            source=curve_source,
            signals=Signal(
                source=curve_source,
                x=SignalData(name=x_name, entry=x_entry),
                y=SignalData(name=y_name, entry=y_entry),
                z=SignalData(name=z_name, entry=z_entry) if z_name else None,
                dap=dap,
            ),
            **kwargs,
        )
        curve = self._add_curve_object(name=label, source=curve_source, config=curve_config)
        return curve

    def add_dap(
        self,
        x_name: str,
        y_name: str,
        x_entry: Optional[str] = None,
        y_entry: Optional[str] = None,
        color: Optional[str] = None,
        dap: str = "GaussianModel",
        **kwargs,
    ) -> BECCurve:
        """
        Add LMFIT dap model curve to the plot widget.

        Args:
            x_name(str): Name of the x signal.
            x_entry(str): Entry of the x signal.
            y_name(str): Name of the y signal.
            y_entry(str): Entry of the y signal.
            color(str, optional): Color of the curve. Defaults to None.
            color_map_z(str): The color map to use for the z-axis.
            label(str, optional): Label of the curve. Defaults to None.
            dap(str): The dap model to use for the curve.
            **kwargs: Additional keyword arguments for the curve configuration.

        Returns:
            BECCurve: The curve object.
        """
        x_entry, y_entry, _ = self._validate_signal_entries(
            x_name, y_name, None, x_entry, y_entry, None
        )
        label = f"{y_name}-{y_entry}-{dap}"
        curve = self.add_curve_scan(
            x_name=x_name,
            y_name=y_name,
            x_entry=x_entry,
            y_entry=y_entry,
            color=color,
            label=label,
            source="DAP",
            dap=dap,
            pen_style="dash",
            symbol="star",
            **kwargs,
        )

        self.setup_dap(self.old_scan_id, self.scan_id)
        self.refresh_dap()
        return curve

    def get_dap_params(self) -> dict:
        """
        Get the DAP parameters of all DAP curves.

        Returns:
            dict: DAP parameters of all DAP curves.
        """
        params = {}
        for curve_id, curve in self._curves_data["DAP"].items():
            params[curve_id] = curve.dap_params
        return params

    def _add_curve_object(
        self,
        name: str,
        source: str,
        config: CurveConfig,
        data: tuple[list | np.ndarray, list | np.ndarray] = None,
    ) -> BECCurve:
        """
        Add a curve object to the plot widget.

        Args:
            name(str): ID of the curve.
            source(str): Source of the curve.
            config(CurveConfig): Configuration of the curve.
            data(tuple[list|np.ndarray,list|np.ndarray], optional): Data (x,y) to be plotted. Defaults to None.

        Returns:
            BECCurve: The curve object.
        """
        curve = BECCurve(config=config, name=name, parent_item=self)
        self._curves_data[source][name] = curve
        self.plot_item.addItem(curve)
        self.config.curves[name] = curve.config
        if data is not None:
            curve.setData(data[0], data[1])
        self.set_legend_label_size()
        return curve

    def _validate_signal_entries(
        self,
        x_name: str,
        y_name: str,
        z_name: str | None,
        x_entry: str | None,
        y_entry: str | None,
        z_entry: str | None,
        validate_bec: bool = True,
    ) -> tuple[str, str, str | None]:
        """
        Validate the signal name and entry.

        Args:
            x_name(str): Name of the x signal.
            y_name(str): Name of the y signal.
            z_name(str): Name of the z signal.
            x_entry(str|None): Entry of the x signal.
            y_entry(str|None): Entry of the y signal.
            z_entry(str|None): Entry of the z signal.
            validate_bec(bool, optional): If True, validate the signal with BEC. Defaults to True.

        Returns:
            tuple[str,str,str|None]: Validated x, y, z entries.
        """
        if validate_bec:
            x_entry = self.entry_validator.validate_signal(x_name, x_entry)
            y_entry = self.entry_validator.validate_signal(y_name, y_entry)
            if z_name:
                z_entry = self.entry_validator.validate_signal(z_name, z_entry)
        else:
            x_entry = x_name if x_entry is None else x_entry
            y_entry = y_name if y_entry is None else y_entry
            z_entry = z_name if z_entry is None else z_entry
        return x_entry, y_entry, z_entry

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
        for source, curves in self._curves_data.items():
            if curve_id in curves:
                curve = curves.pop(curve_id)
                self.plot_item.removeItem(curve)
                del self.config.curves[curve_id]
                if curve in self.plot_item.curves:
                    self.plot_item.curves.remove(curve)
                return
        raise KeyError(f"Curve with ID '{curve_id}' not found.")

    def _remove_curve_by_order(self, N):
        """
        Remove a curve by its order from the plot widget.

        Args:
            N(int): Order of the curve to be removed.
        """
        if N < len(self.plot_item.curves):
            curve = self.plot_item.curves[N]
            curve_id = curve.name()  # Assuming curve's name is used as its ID
            self.plot_item.removeItem(curve)
            del self.config.curves[curve_id]
            # Remove from self.curve_data
            for source, curves in self._curves_data.items():
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
        current_scan_id = msg.get("scan_id", None)
        if current_scan_id is None:
            return

        if current_scan_id != self.scan_id:
            self.old_scan_id = self.scan_id
            self.scan_id = current_scan_id
            self.scan_segment_data = self.queue.scan_storage.find_scan_by_ID(
                self.scan_id
            )  # TODO do scan access through BECFigure
            self.setup_dap(self.old_scan_id, self.scan_id)

        self.scan_signal_update.emit()

    def setup_dap(self, old_scan_id, new_scan_id):
        """
        Setup DAP for the new scan.

        Args:
            old_scan_id(str): old_scan_id, used to disconnect the previous dispatcher connection.
            new_scan_id(str): new_scan_id, used to connect the new dispatcher connection.

        """
        self.bec_dispatcher.disconnect_slot(
            self.update_dap, MessageEndpoints.dap_response(old_scan_id)
        )
        if len(self._curves_data["DAP"]) > 0:
            self.bec_dispatcher.connect_slot(
                self.update_dap, MessageEndpoints.dap_response(new_scan_id)
            )

    def refresh_dap(self):
        """
        Refresh the DAP curves with the latest data from the DAP model MessageEndpoints.dap_response().
        """
        for curve_id, curve in self._curves_data["DAP"].items():
            x_name = curve.config.signals.x.name
            y_name = curve.config.signals.y.name
            x_entry = curve.config.signals.x.entry
            y_entry = curve.config.signals.y.entry
            model_name = curve.config.signals.dap
            model = getattr(self.dap, model_name)

            msg = messages.DAPRequestMessage(
                dap_cls="LmfitService1D",
                dap_type="on_demand",
                config={
                    "args": [self.scan_id, x_name, x_entry, y_name, y_entry],
                    "kwargs": {},
                    "class_args": model._plugin_info["class_args"],
                    "class_kwargs": model._plugin_info["class_kwargs"],
                },
                metadata={"RID": self.scan_id},
            )
            self.client.connector.set_and_publish(MessageEndpoints.dap_request(), msg)

    @pyqtSlot(dict, dict)
    def update_dap(self, msg, metadata):
        self.msg = msg
        scan_id, x_name, x_entry, y_name, y_entry = msg["dap_request"].content["config"]["args"]
        model = msg["dap_request"].content["config"]["class_kwargs"]["model"]

        curve_id_request = f"{y_name}-{y_entry}-{model}"

        for curve_id, curve in self._curves_data["DAP"].items():
            if curve_id == curve_id_request:
                if msg["data"] is not None:
                    x = msg["data"][0]["x"]
                    y = msg["data"][0]["y"]
                    curve.setData(x, y)
                    curve.dap_params = msg["data"][1]["fit_parameters"]
                    self.dap_params_update.emit(curve.dap_params)
                break

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
        data_x = None
        data_y = None
        data_z = None
        for curve_id, curve in self._curves_data["scan_segment"].items():
            x_name = curve.config.signals.x.name
            x_entry = curve.config.signals.x.entry
            y_name = curve.config.signals.y.name
            y_entry = curve.config.signals.y.entry
            if curve.config.signals.z:
                z_name = curve.config.signals.z.name
                z_entry = curve.config.signals.z.entry

            try:
                data_x = data[x_name][x_entry].val
                data_y = data[y_name][y_entry].val
                if curve.config.signals.z:
                    data_z = data[z_name][z_entry].val
                    color_z = self._make_z_gradient(
                        data_z, curve.config.color_map_z
                    )  # TODO decide how to implement custom gradient
            except TypeError:
                continue

            if data_z is not None and color_z is not None:
                curve.setData(x=data_x, y=data_y, symbolBrush=color_z)
            else:
                curve.setData(data_x, data_y)

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

    def scan_history(self, scan_index: int = None, scan_id: str = None):
        """
        Update the scan curves with the data from the scan storage.
        Provide only one of scan_id or scan_index.

        Args:
            scan_id(str, optional): ScanID of the scan to be updated. Defaults to None.
            scan_index(int, optional): Index of the scan to be updated. Defaults to None.
        """
        if scan_index is not None and scan_id is not None:
            raise ValueError("Only one of scan_id or scan_index can be provided.")

        # Reset DAP connector
        self.bec_dispatcher.disconnect_slot(
            self.update_dap, MessageEndpoints.dap_response(self.scan_id)
        )
        if scan_index is not None:
            self.scan_id = self.queue.scan_storage.storage[scan_index].scan_id
        elif scan_id is not None:
            self.scan_id = scan_id

        self.setup_dap(self.old_scan_id, self.scan_id)
        data = self.queue.scan_storage.find_scan_by_ID(self.scan_id).data
        self._update_scan_curves(data)

    def get_all_data(self, output: Literal["dict", "pandas"] = "dict") -> dict | pd.DataFrame:
        """
        Extract all curve data into a dictionary or a pandas DataFrame.

        Args:
            output (Literal["dict", "pandas"]): Format of the output data.

        Returns:
            dict | pd.DataFrame: Data of all curves in the specified format.
        """
        data = {}
        try:
            import pandas as pd
        except ImportError:
            pd = None
            if output == "pandas":
                print(
                    "Pandas is not installed. "
                    "Please install pandas using 'pip install pandas'."
                    "Output will be dictionary instead."
                )
                output = "dict"

        for curve in self.plot_item.curves:
            x_data, y_data = curve.get_data()
            if x_data is not None or y_data is not None:
                if output == "dict":
                    data[curve.name()] = {"x": x_data.tolist(), "y": y_data.tolist()}
                elif output == "pandas" and pd is not None:
                    data[curve.name()] = pd.DataFrame({"x": x_data, "y": y_data})

        if output == "pandas" and pd is not None:
            combined_data = pd.concat(
                [data[curve.name()] for curve in self.plot_item.curves],
                axis=1,
                keys=[curve.name() for curve in self.plot_item.curves],
            )
            return combined_data
        return data

    def cleanup(self):
        """Cleanup the widget connection from BECDispatcher."""
        self.bec_dispatcher.disconnect_slot(self.on_scan_segment, MessageEndpoints.scan_segment())
        self.bec_dispatcher.disconnect_slot(
            self.update_dap, MessageEndpoints.dap_response(self.scan_id)
        )
        for curve in self.curves:
            curve.cleanup()
        super().cleanup()
