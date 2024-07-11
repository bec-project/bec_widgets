from __future__ import annotations

import datetime
import time
from collections import defaultdict
from typing import Any, Literal, Optional

import numpy as np
import pyqtgraph as pg
from bec_lib import messages
from bec_lib.device import ReadoutPriority
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
    )
    curves: dict[str, CurveConfig] = Field(
        {}, description="The list of curves to be added to the 1D waveform widget."
    )


class BECWaveform(BECPlotBase):
    READOUT_PRIORITY_HANDLER = {
        ReadoutPriority.ON_REQUEST: "on_request",
        ReadoutPriority.BASELINE: "baseline",
        ReadoutPriority.MONITORED: "monitored",
        ReadoutPriority.ASYNC: "async",
        ReadoutPriority.CONTINUOUS: "continuous",
    }
    USER_ACCESS = [
        "_rpc_id",
        "_config_dict",
        "plot",
        "add_dap",
        "change_x_axis",
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
    async_signal_update = pyqtSignal()
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
        self._x_axis_mode = {
            "name": None,
            "entry": None,
            "readout_priority": None,
            "label_suffix": "",
        }

        # Scan segment update proxy
        self.proxy_update_plot = pg.SignalProxy(
            self.scan_signal_update, rateLimit=25, slot=self._update_scan_curves
        )
        self.proxy_update_dap = pg.SignalProxy(
            self.scan_signal_update, rateLimit=25, slot=self.refresh_dap
        )
        self.async_signal_update.connect(self.replot_async_curve)

        # Get bec shortcuts dev, scans, queue, scan_storage, dap
        self.get_bec_shortcuts()

        # Connect dispatcher signals
        self.bec_dispatcher.connect_slot(self.on_scan_segment, MessageEndpoints.scan_segment())
        # TODO disabled -> scan_status is SET_AND_PUBLISH -> do not work in combination with autoupdate from CLI
        # self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())

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
    # Waveform Properties
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

    ###################################
    # Adding and Removing Curves
    ###################################

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
            dap(str): The dap model to use for the curve, only available for sync devices. If not specified, none will be added.

        Returns:
            BECCurve: The curve object.
        """

        if x is not None and y is not None:
            return self.add_curve_custom(x=x, y=y, label=label, color=color, **kwargs)
        else:
            if dap:
                self.add_dap(x_name=x_name, y_name=y_name, dap=dap)
            curve = self.add_curve_bec(
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
            self.async_signal_update.emit()
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

        readout_priority_x = None
        if x_name not in ["best_effort", "timestamp", "index"]:
            readout_priority_x = self._get_device_readout_priority(x_name)

        self.x_axis_mode = {
            "name": x_name,
            "entry": x_entry,
            readout_priority_x: readout_priority_x,
        }

        if len(self.curves) > 0:
            # validate all curves
            for curve in self.curves:
                self._validate_x_axis_behaviour(curve.config.signals.y.name, x_name, x_entry, False)
            self._switch_x_axis_item(
                f"{x_name}-{x_entry}"
                if x_name not in ["best_effort", "timestamp", "index"]
                else x_name
            )
            for curve_id, curve_config in zip(curve_ids, curve_configs):
                if curve_config.signals.x:
                    curve_config.signals.x.name = x_name
                    curve_config.signals.x.entry = x_entry
                self.remove_curve(curve_id)
                self.add_curve_by_config(curve_config)

            self.async_signal_update.emit()
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

    def add_curve_bec(
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
        dap: str | None = None,
        source: str | None = None,
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
            dap(str, optional): The dap model to use for the curve. Defaults to None.
            **kwargs: Additional keyword arguments for the curve configuration.

        Returns:
            BECCurve: The curve object.
        """
        # 1. Check - y_name must be provided
        if y_name is None:
            raise ValueError("y_name must be provided.")

        # 2. Check - get source of the device
        if source is None:
            source = self._validate_device_source_compatibity(y_name)

        # 3. Check - check if there is already a x axis signal
        if x_name is None:
            x_name = self.x_axis_mode["name"]

        # 4. Check - Get entry if not provided and validate
        x_entry, y_entry, z_entry = self._validate_signal_entries(
            x_name, y_name, z_name, x_entry, y_entry, z_entry, validate_bec
        )

        if z_name is not None and z_entry is not None:
            label = label or f"{z_name}-{z_entry}"
        else:
            label = label or f"{y_name}-{y_entry}"

        # 5. Check - Check if curve already exists
        curve_exits = self._check_curve_id(label, self._curves_data)
        if curve_exits:
            raise ValueError(f"Curve with ID '{label}' already exists in widget '{self.gui_id}'.")

        # Validate or define x axis behaviour and compatibility with y_name readoutPriority
        self._validate_x_axis_behaviour(y_name, x_name, x_entry)

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

        if self.x_axis_mode["readout_priority"] == "async":
            raise ValueError(
                f"Async signals cannot be fitted at the moment. Please switch to 'monitored' or 'baseline' signals."
            )

        if validate_bec is True:
            x_entry, y_entry, _ = self._validate_signal_entries(
                x_name, y_name, None, x_entry, y_entry, None
            )
        label = f"{y_name}-{y_entry}-{dap}"
        curve = self.add_curve_bec(
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

    @pyqtSlot()
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

    def _validate_device_source_compatibity(self, name: str):
        readout_priority_y = self._get_device_readout_priority(name)
        if readout_priority_y == "monitored" or readout_priority_y == "baseline":
            source = "scan_segment"
        elif readout_priority_y == "async":
            source = "async"
        else:
            raise ValueError(
                f"Readout priority '{readout_priority_y}' of device '{name}' is not supported for y signal."
            )
        return source

    def _validate_x_axis_behaviour(
        self, y_name: str, x_name: str | None = None, x_entry: str | None = None, auto_switch=True
    ) -> None:
        """
        Validate the x axis behaviour and consistency for the plot item.

        Args:
            source(str): Source of updating device. Can be either "scan_segment" or "async".
            x_name(str): Name of the x signal.
                - "best_effort": Use the best effort signal.
                - "timestamp": Use the timestamp signal.
                - "index": Use the index signal.
                - Custom signal name of device from BEC.
            x_entry(str): Entry of the x signal.
        """

        readout_priority_y = self._get_device_readout_priority(y_name)

        # Check if the x axis behaviour is already set
        if self._x_axis_mode["name"] is not None:
            # Case 1: The same x axis signal is used, check if source is compatible with the device
            if x_name != self._x_axis_mode["name"] and x_entry != self._x_axis_mode["entry"]:
                # A different x axis signal is used, raise an exception
                raise ValueError(
                    f"All curves must have the same x axis.\n"
                    f" Current valid x axis: '{self._x_axis_mode['name']}'\n"
                    f" Attempted to add curve with x axis: '{x_name}'\n"
                    f"If you want to change the x-axis of the curve, please remove previous curves or change the x axis of the plot widget with '.change_x_axis({x_name})'."
                )

        # If x_axis_mode["name"] is None, determine the mode based on x_name
        # With async the best effort is always "index"
        # Setting mode to either "best_effort", "timestamp", "index", or a custom one
        if x_name is None and readout_priority_y == "async":
            x_name = "index"
            x_entry = "index"
        if x_name in ["best_effort", "timestamp", "index"]:
            self._x_axis_mode["name"] = x_name
            self._x_axis_mode["entry"] = x_entry
        else:
            self._x_axis_mode["name"] = x_name
            self._x_axis_mode["entry"] = x_entry
            if readout_priority_y == "async":
                raise ValueError(
                    f"Async devices '{y_name}' cannot be used with custom x signal '{x_name}-{x_entry}'."
                )

        if auto_switch is True:
            # Switch the x axis mode accordingly
            self._switch_x_axis_item(
                f"{x_name}-{x_entry}"
                if x_name not in ["best_effort", "timestamp", "index"]
                else x_name
            )

    def _get_device_readout_priority(self, name: str):
        """
        Get the type of device from the entry_validator.

        Args:
            name(str): Name of the device.
            entry(str): Entry of the device.

        Returns:
            str: Type of the device.
        """
        return self.READOUT_PRIORITY_HANDLER[self.dev[name].readout_priority]

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
        self._x_axis_mode["label_suffix"] = f" [{mode}]"

        if mode == "timestamp":
            self.plot_item.setAxisItems({"bottom": date_axis})
            self.plot_item.setLabel("bottom", f"{current_label}{self._x_axis_mode['label_suffix']}")
        elif mode == "index":
            self.plot_item.setAxisItems({"bottom": default_axis})
            self.plot_item.setLabel("bottom", f"{current_label}{self._x_axis_mode['label_suffix']}")
        else:
            self.plot_item.setAxisItems({"bottom": default_axis})
            self.plot_item.setLabel("bottom", f"{current_label}{self._x_axis_mode['label_suffix']}")

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
            if x_name is None:
                x_name = "best_effort"
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
                for curve_id, curve in self._curves_data["async"].items():
                    self.setup_async(curve.config.signals.y.name)

    @pyqtSlot(dict, dict)
    def on_scan_segment(self, msg: dict, metadata: dict):
        """
        Handle new scan segments and saves data to a dictionary. Linked through bec_dispatcher.
        Used only for triggering scan segment update from the BECClient scan storage.

        Args:
            msg (dict): Message received with scan data.
            metadata (dict): Metadata of the scan.
        """
        self.on_scan_status(msg)

        self.scan_signal_update.emit()

    def set_x_label(self, label: str, size: int = None):
        """
        Set the label of the x-axis.

        Args:
            label(str): Label of the x-axis.
            size(int): Font size of the label.
        """
        super().set_x_label(label, size)
        current_label = "" if self.config.axis.x_label is None else self.config.axis.x_label
        self.plot_item.setLabel("bottom", f"{current_label}{self._x_axis_mode['label_suffix']}")

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

    @pyqtSlot(str)
    def setup_async(self, device: str):
        self.bec_dispatcher.disconnect_slot(
            self.on_async_readback, MessageEndpoints.device_async_readback(self.old_scan_id, device)
        )
        try:
            self._curves_data["async"][f"{device}-{device}"].clear_data()
        except KeyError:
            pass
        if len(self._curves_data["async"]) > 0:
            self.bec_dispatcher.connect_slot(
                self.on_async_readback,
                MessageEndpoints.device_async_readback(self.scan_id, device),
                from_start=True,
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
    def on_async_readback(self, msg, metadata):
        """
        Get async data readback.

        Args:
            msg(dict): Message with the async data.
            metadata(dict): Metadata of the message.
        """
        print(msg)
        instruction = metadata.get("async_update")
        for curve_id, curve in self._curves_data["async"].items():
            y_name = curve.config.signals.y.name
            y_entry = curve.config.signals.y.entry
            x_name = self._x_axis_mode["name"]
            for device, async_data in msg["signals"].items():
                if device == y_entry:
                    data_plot = async_data["value"]
                    if instruction == "extend":
                        x_data, y_data = curve.get_data()
                        if y_data is not None:
                            new_data = np.hstack((y_data, data_plot))
                        else:
                            new_data = data_plot
                        if x_name == "timestamp":
                            if x_data is not None:
                                x_data = np.hstack(
                                    (x_data, self.convert_timestamps(async_data["timestamp"]))
                                )
                            else:
                                x_data = self.convert_timestamps(async_data["timestamp"])
                            curve.setData(x_data, new_data)
                        else:
                            curve.setData(new_data)
                    elif instruction == "replace":
                        if x_name == "timestamp":
                            x_data = self.convert_timestamps(async_data["timestamp"])
                            curve.setData(x_data, data_plot)
                        else:
                            curve.setData(data_plot)

    @pyqtSlot()
    def replot_async_curve(self):
        try:
            data = self.scan_item.async_data
        except AttributeError:
            return
        for curve_id, curve in self._curves_data["async"].items():
            y_name = curve.config.signals.y.name
            y_entry = curve.config.signals.y.entry

            if curve.config.signals.x:
                x_name = curve.config.signals.x.name

            if x_name == "timestamp":
                data_x = self.convert_timestamps(data[y_name][y_entry]["timestamp"])
            else:
                data_x = None
            data_y = data[y_name][y_entry]["value"]

            if data_x is None:
                curve.setData(data_y)
            else:
                curve.setData(data_x, data_y)

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
            if len(self._curves_data["async"]) > 0:
                x_data = None
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
        for curve_id, curve in self._curves_data["async"].items():
            self.bec_dispatcher.disconnect_slot(
                self.on_async_readback,
                MessageEndpoints.device_async_readback(self.scan_id, curve_id),
            )
        for curve in self.curves:
            curve.cleanup()
        super().cleanup()
