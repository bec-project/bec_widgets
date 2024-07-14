from __future__ import annotations

import datetime
import time
from collections import defaultdict
from typing import Any, Literal, Optional

import numpy as np
import pyqtgraph as pg
from bec_lib import messages
from bec_lib.endpoints import MessageEndpoints
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
        "_rpc_id",
        "_config_dict",
        "plot",
        "add_dap",
        "get_dap_params",
        "remove_curve",
        "scan_history",
        "curves",
        "get_curve",
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
        self.scan_item = None
        self._x_axis_mode = {"name": None, "entry": None}

        # Scan segment update proxy
        self.proxy_update_plot = pg.SignalProxy(
            self.scan_signal_update, rateLimit=25, slot=self._update_scan_curves
        )

        self.proxy_update_dap = pg.SignalProxy(
            self.scan_signal_update, rateLimit=25, slot=self.refresh_dap
        )
        # Get bec shortcuts dev, scans, queue, scan_storage, dap
        self.get_bec_shortcuts()

        # Connect dispatcher signals
        self.bec_dispatcher.connect_slot(self.on_scan_segment, MessageEndpoints.scan_segment())
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())

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

    ###################################
    # Adding and Removing Curves
    ###################################

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

    @property
    def x_axis_mode(self) -> dict:
        """
        Get the x axis mode of the plot widget.

        Returns:
            dict: The x axis mode.
        """
        return self._x_axis_mode

    @x_axis_mode.setter
    def x_axis_mode(self, value: dict):
        self._x_axis_mode = value

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
        **kwargs,
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
            return self.add_curve_custom(x=x, y=y, label=label, color=color, **kwargs)
        else:
            if dap:
                self.add_dap(x_name=x_name, y_name=y_name, dap=dap)
            curve = self.add_curve_scan(
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
                **kwargs,
            )
            self.scan_signal_update.emit()
            return curve

    def change_x_axis(self, x_name: str, x_entry: str | None = None):
        """
        Change the x axis of the plot widget.

        Args:
            x_name(str): Name of the x signal.
            x_entry(str): Entry of the x signal.
        """
        curve_configs = self.config.curves
        curve_ids = list(curve_configs.keys())
        curve_configs = list(curve_configs.values())

        x_entry, _, _ = self._validate_signal_entries(
            x_name, None, None, x_entry, None, None, validate_bec=True
        )

        self.x_axis_mode = {"name": x_name, "entry": x_entry}

        for curve_id, curve_config in zip(curve_ids, curve_configs):
            if curve_config.signals.x:
                curve_config.signals.x.name = x_name
                curve_config.signals.x.entry = x_entry
            self.remove_curve(curve_id)
            self.add_curve_by_config(curve_config)

        self.scan_signal_update.emit()

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
        x_name: str | None = None,
        y_name: str | None = None,
        z_name: str | None = None,
        x_entry: str | None = None,
        y_entry: str | None = None,
        z_entry: str | None = None,
        color: str | None = None,
        color_map_z: str | None = "plasma",
        label: str | None = None,
        validate_bec: bool = True,
        source: str = "scan_segment",
        dap: str | None = None,
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
            validate_bec(bool, optional): If True, validate the signal with BEC. Defaults to True.
            source(str, optional): Source of the curve. Defaults to "scan_segment".
            dap(str, optional): The dap model to use for the curve. Defaults to None.
            **kwargs: Additional keyword arguments for the curve configuration.

        Returns:
            BECCurve: The curve object.
        """
        if y_name is None:
            raise ValueError("y_name must be provided.")

        if x_name is None:
            x_name = self.x_axis_mode["name"]

        # Get entry if not provided and validate
        x_entry, y_entry, z_entry = self._validate_signal_entries(
            x_name, y_name, z_name, x_entry, y_entry, z_entry, validate_bec
        )

        if z_name is not None and z_entry is not None:
            label = label or f"{z_name}-{z_entry}"
        else:
            label = label or f"{y_name}-{y_entry}"

        # Check if curve already exists
        curve_exits = self._check_curve_id(label, self._curves_data)
        if curve_exits:
            raise ValueError(f"Curve with ID '{label}' already exists in widget '{self.gui_id}'.")

        # Validate or define x axis behaviour
        self._validate_x_axis_behaviour(x_name, x_entry)

        # Create color if not specified
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
            source=source,
            signals=Signal(
                source=source,
                x=SignalData(name=x_name, entry=x_entry) if x_name else None,
                y=SignalData(name=y_name, entry=y_entry),
                z=SignalData(name=z_name, entry=z_entry) if z_name else None,
                dap=dap,
            ),
            **kwargs,
        )

        curve = self._add_curve_object(name=label, source=source, config=curve_config)
        return curve

    def add_dap(
        self,
        x_name: str | None = None,
        y_name: str | None = None,
        x_entry: Optional[str] = None,
        y_entry: Optional[str] = None,
        color: Optional[str] = None,
        dap: str = "GaussianModel",
        validate_bec: bool = True,
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
            validate_bec(bool, optional): If True, validate the signal with BEC. Defaults to True.
            **kwargs: Additional keyword arguments for the curve configuration.

        Returns:
            BECCurve: The curve object.
        """
        if x_name is None:
            x_name = self.x_axis_mode["name"]
            x_entry = self.x_axis_mode["entry"]
            if x_name == "timestamp" or x_name == "index":
                raise ValueError(
                    f"Cannot use x axis '{x_name}' for DAP curve. Please provide a custom x axis signal or switch to 'best_effort' signal mode."
                )
        if validate_bec is True:  # TODO adapt dap for x axis global behaviour
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

    def _validate_x_axis_behaviour(
        self, x_name: str | None = None, x_entry: str | None = None
    ) -> None:
        """
        Validate the x axis behaviour and consistency for the plot item.

        Args:
            x_name(str): Name of the x signal.
                - "best_effort": Use the best effort signal.
                - "timestamp": Use the timestamp signal.
                - "index": Use the index signal.
                - Custom signal name of device from BEC.
            x_entry(str): Entry of the x signal.
        """
        # Check if the x axis behaviour is already set
        if self._x_axis_mode["name"] is not None:
            # Case 1: The same x axis signal is used, do nothing
            if x_name == self._x_axis_mode["name"] and x_entry == self._x_axis_mode["entry"]:
                return

            # Case 2: A different x axis signal is used, raise an exception
            raise ValueError(
                f"All curves must have the same x axis.\n"
                f" Current valid x axis: '{self._x_axis_mode['name']}'\n"
                f" Attempted to add curve with x axis: '{x_name}'\n"
                f"If you want to change the x-axis of the curve, please remove previous curves."
            )
        # If x_axis_mode["name"] is None, determine the mode based on x_name
        # Setting mode to either "best_effort", "timestamp", "index", or a custom one
        if x_name in ["best_effort", "timestamp", "index"]:
            self._x_axis_mode["name"] = x_name
            self._x_axis_mode["entry"] = x_entry
        else:
            self._x_axis_mode["name"] = x_name
            self._x_axis_mode["entry"] = x_entry

        # Switch the x axis mode accordingly
        self._switch_x_axis_item(
            f"{x_name}-{x_entry}" if x_name not in ["best_effort", "timestamp", "index"] else x_name
        )

    def _switch_x_axis_item(self, mode: str):
        """
        Switch the x-axis mode between timestamp, index, the best effort and custom signal.

        Args:
            mode(str): Mode of the x-axis.
                - "timestamp": Use the timestamp signal.
                - "index": Use the index signal.
                - "best_effort": Use the best effort signal.
                - Custom signal name of device from BEC.
        """
        current_label = "" if self.config.axis.x_label is None else self.config.axis.x_label
        date_axis = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation="bottom")
        default_axis = pg.AxisItem(orientation="bottom")

        if mode == "timestamp":
            self.plot_item.setAxisItems({"bottom": date_axis})
            self.plot_item.setLabel("bottom", f"{current_label} [timestamp]")
        elif mode == "index":
            self.plot_item.setAxisItems({"bottom": default_axis})
            self.plot_item.setLabel("bottom", f"{current_label} [index]")
        else:
            self.plot_item.setAxisItems({"bottom": default_axis})
            self.plot_item.setLabel("bottom", f"{current_label} [{mode}]")

    def _validate_signal_entries(
        self,
        x_name: str | None,
        y_name: str | None,
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
            if x_name:
                if x_name == "index" or x_name == "timestamp" or x_name == "best_effort":
                    x_entry = x_name
                else:
                    x_entry = self.entry_validator.validate_signal(x_name, x_entry)
            if y_name:
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

    @pyqtSlot(dict)
    def on_scan_status(self, msg):
        """
        Handle the scan status message.

        Args:
            msg(dict): Message received with scan status.
        """

        current_scan_id = msg.get("scan_id", None)
        if current_scan_id is None:
            return

        if current_scan_id != self.scan_id:
            self.old_scan_id = self.scan_id
            self.scan_id = current_scan_id
            self.scan_item = self.queue.scan_storage.find_scan_by_ID(self.scan_id)
            if self._curves_data["DAP"]:
                self.setup_dap(self.old_scan_id, self.scan_id)
            if self._curves_data["async"]:
                print("setting async")
                # for curve in self._curves_data["async"]:
                #     self.setup_async(curve.config.signals.y.name)

    @pyqtSlot(dict, dict)
    def on_scan_segment(self, msg: dict, metadata: dict):
        """
        Handle new scan segments and saves data to a dictionary. Linked through bec_dispatcher.
        Used only for triggering scan segment update from the BECClient scan storage.

        Args:
            msg (dict): Message received with scan data.
            metadata (dict): Metadata of the scan.
        """

        self.scan_signal_update.emit()

    def setup_dap(self, old_scan_id: str | None, new_scan_id: str | None):
        """
        Setup DAP for the new scan.

        Args:
            old_scan_id(str): old_scan_id, used to disconnect the previous dispatcher connection.
            new_scan_id(str): new_scan_id, used to connect the new dispatcher connection.

        """
        self.bec_dispatcher.disconnect_slot(
            self.update_dap, MessageEndpoints.dap_response(f"{old_scan_id}-{self.gui_id}")
        )
        if len(self._curves_data["DAP"]) > 0:
            self.bec_dispatcher.connect_slot(
                self.update_dap, MessageEndpoints.dap_response(f"{new_scan_id}-{self.gui_id}")
            )

    def setup_async(self, device: str):
        self.bec_dispatcher.disconnect_slot(
            self.update_dap, MessageEndpoints.device_async_readback(self.old_scan_id, device)
        )
        if len(self._curves_data["async"]) > 0:
            self.bec_dispatcher.connect_slot(
                self.update_dap, MessageEndpoints.device_async_readback(self.scan_id, device)
            )

    @pyqtSlot()
    def refresh_dap(self):
        """
        Refresh the DAP curves with the latest data from the DAP model MessageEndpoints.dap_response().
        """
        for curve_id, curve in self._curves_data["DAP"].items():
            if curve.config.signals.x is not None:
                x_name = curve.config.signals.x.name
                x_entry = curve.config.signals.x.entry
                if (
                    x_name == "timestamp" or x_name == "index"
                ):  # timestamp and index not supported by DAP
                    return
                try:  # to prevent DAP update if the x axis is not the same as the current scan
                    current_x_names = self.scan_item.status_message.info["scan_report_devices"]
                    if x_name not in current_x_names:
                        return
                except AttributeError:
                    return
            else:
                try:
                    x_name = self.scan_item.status_message.info["scan_report_devices"][0]
                    x_entry = self.entry_validator.validate_signal(x_name, None)
                except AttributeError:
                    return
            y_name = curve.config.signals.y.name
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
                metadata={"RID": f"{self.scan_id}-{self.gui_id}"},
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

    @pyqtSlot(dict, dict)
    def update_async(self, msg, metadata):
        print("async")
        print(f"msg: {msg}")
        print(f"metadata: {metadata}")

    @pyqtSlot()
    def _update_scan_curves(self):
        """
        Update the scan curves with the data from the scan segment.
        """
        try:
            data = self.scan_item.data
        except AttributeError:
            return

        data_x = None
        data_y = None
        data_z = None

        for curve_id, curve in self._curves_data["scan_segment"].items():

            y_name = curve.config.signals.y.name
            y_entry = curve.config.signals.y.entry
            if curve.config.signals.z:
                z_name = curve.config.signals.z.name
                z_entry = curve.config.signals.z.entry

            data_x = self._get_x_data(curve, y_name, y_entry)
            if data_x == []:  # case if the data is empty because motor is not scanned
                return

            try:
                data_y = data[y_name][y_entry].val
                if curve.config.signals.z:
                    data_z = data[z_name][z_entry].val
                    color_z = self._make_z_gradient(data_z, curve.config.color_map_z)
            except TypeError:
                continue

            if data_z is not None and color_z is not None:
                try:
                    curve.setData(x=data_x, y=data_y, symbolBrush=color_z)
                except:
                    return
            if data_x is None:
                curve.setData(data_y)
            else:
                curve.setData(data_x, data_y)

    def _get_x_data(self, curve: BECCurve, y_name: str, y_entry: str) -> list | np.ndarray | None:
        """
        Get the x data for the curve with the decision logic based on the curve configuration:
            - If x is called 'timestamp', use the timestamp data from the scan item.
            - If x is called 'index', use the rolling index.
            - If x is a custom signal, use the data from the scan item.
            - If x is not specified, use the first device from the scan report.

        Args:
            curve(BECCurve): The curve object.

        Returns:
            list|np.ndarray|None: X data for the curve.
        """
        if curve.config.signals.x is not None:
            if curve.config.signals.x.name == "timestamp":
                timestamps = self.scan_item.data[y_name][y_entry].timestamps
                x_data = self.convert_timestamps(timestamps)
            elif curve.config.signals.x.name == "index":
                x_data = None
            else:
                x_name = curve.config.signals.x.name
                x_entry = curve.config.signals.x.entry
                try:
                    x_data = self.scan_item.data[x_name][x_entry].val
                except TypeError:
                    x_data = []
        else:
            x_name = self.scan_item.status_message.info["scan_report_devices"][0]
            x_entry = self.entry_validator.validate_signal(x_name, None)
            x_data = self.scan_item.data[x_name][x_entry].val
            self.set_x_label(f"[auto: {x_name}-{x_entry}]")

        return x_data

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
            try:
                self.scan_id = self.queue.scan_storage.storage[scan_index].scan_id
            except IndexError:
                print(f"Scan index {scan_index} out of range.")
                return
        elif scan_id is not None:
            self.scan_id = scan_id

        self.setup_dap(self.old_scan_id, self.scan_id)
        self.scan_item = self.queue.scan_storage.find_scan_by_ID(self.scan_id)
        self.scan_signal_update.emit()

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

    @staticmethod
    def convert_timestamps(timestamps: list) -> list:
        """
        Convert timestamps to human-readable dates.

        Args:
            timestamps(list): List of timestamps.

        Returns:
            list: List of human-readable dates.
        """
        human_readable_dates = [
            datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S.%f")
            for ts in timestamps
        ]
        data2float = [
            time.mktime(datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S.%f").timetuple())
            for date in human_readable_dates
        ]
        return data2float

    def cleanup(self):
        """Cleanup the widget connection from BECDispatcher."""
        self.bec_dispatcher.disconnect_slot(self.on_scan_segment, MessageEndpoints.scan_segment())
        self.bec_dispatcher.disconnect_slot(
            self.update_dap, MessageEndpoints.dap_response(self.scan_id)
        )
        for curve in self.curves:
            curve.cleanup()
        super().cleanup()
