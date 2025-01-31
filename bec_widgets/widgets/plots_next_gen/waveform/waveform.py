from __future__ import annotations

import json
from typing import Literal, Optional

import numpy as np
import pyqtgraph as pg
from bec_lib import bec_logger, messages
from bec_lib.endpoints import MessageEndpoints
from pydantic import Field, field_validator
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QWidget

from bec_widgets.qt_utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils import ConnectionConfig
from bec_widgets.utils.bec_signal_proxy import BECSignalProxy
from bec_widgets.utils.colors import Colors, set_theme
from bec_widgets.widgets.dap.lmfit_dialog.lmfit_dialog import LMFitDialog
from bec_widgets.widgets.plots_next_gen.plot_base import PlotBase
from bec_widgets.widgets.plots_next_gen.waveform.curve import Curve, CurveConfig, DeviceSignal
from bec_widgets.widgets.plots_next_gen.waveform.utils.roi_manager import WaveformROIManager

logger = bec_logger.logger


# noinspection PyDataclass
class WaveformConfig(ConnectionConfig):
    color_palette: Optional[str] = Field(
        "magma", description="The color palette of the figure widget.", validate_default=True
    )

    model_config: dict = {"validate_assignment": True}
    _validate_color_palette = field_validator("color_palette")(Colors.validate_color_map)


class Waveform(PlotBase):
    PLUGIN = True
    ICON_NAME = "show_chart"
    USER_ACCESS = [
        # General PlotBase Settings
        "enable_toolbar",
        "enable_toolbar.setter",
        "enable_side_panel",
        "enable_side_panel.setter",
        "enable_fps_monitor",
        "enable_fps_monitor.setter",
        "set",
        "title",
        "title.setter",
        "x_label",
        "x_label.setter",
        "y_label",
        "y_label.setter",
        "x_limits",
        "x_limits.setter",
        "y_limits",
        "y_limits.setter",
        "x_grid",
        "x_grid.setter",
        "y_grid",
        "y_grid.setter",
        "inner_axes",
        "inner_axes.setter",
        "outer_axes",
        "outer_axes.setter",
        "lock_aspect_ratio",
        "lock_aspect_ratio.setter",
        "auto_range_x",
        "auto_range_x.setter",
        "auto_range_y",
        "auto_range_y.setter",
        "x_log",
        "x_log.setter",
        "y_log",
        "y_log.setter",
        "legend_label_size",
        "legend_label_size.setter",
        # Waveform Specific RPC Access
        "x_mode",
        "x_mode.setter",
        "color_palette",
        "color_palette.setter",
        "plot",
        "add_dap_curve",
        "remove_curve",
        "scan_history",
    ]

    sync_signal_update = Signal()
    async_signal_update = Signal()
    request_dap_update = Signal()
    unblock_dap_proxy = Signal()
    dap_params_update = Signal(dict, dict)
    dap_summary_update = Signal(dict, dict)
    new_scan = Signal()
    new_scan_id = Signal(str)

    roi_changed = Signal(tuple)
    roi_active = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        config: WaveformConfig | None = None,
        client=None,
        gui_id: str | None = None,
    ):
        if config is None:
            config = WaveformConfig(widget_class=self.__class__.__name__)
        super().__init__(parent=parent, config=config, client=client, gui_id=gui_id)

        # For PropertyManager identification
        self.setObjectName("Waveform")

        # Curve data
        self._sync_curves = []
        self._async_curves = []
        self._dap_curves = []
        self._mode: Literal["sync", "async", "mixed"] = (
            "sync"  # TODO mode probably not needed as well, both wil be allowed
        )

        # Scan data
        self.old_scan_id = None
        self.scan_id = None
        self.scan_item = None
        self.readout_priority = None
        self._x_axis_mode = {
            "name": "auto",
            "entry": None,
            "readout_priority": None,
            "label_suffix": "",
        }  # TODO decide which one to use

        # Specific GUI elements
        self._init_roi_manager()
        self._add_dap_summary_side_menu()

        # Scan status update loop
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.bec_dispatcher.connect_slot(self.on_scan_progress, MessageEndpoints.scan_progress())

        # Curve update loop
        self.proxy_update_sync = pg.SignalProxy(
            self.sync_signal_update, rateLimit=25, slot=self.update_sync_curves
        )
        self.proxy_update_async = pg.SignalProxy(
            self.async_signal_update, rateLimit=25, slot=self.update_async_curves
        )
        self.proxy_dap_request = BECSignalProxy(
            self.request_dap_update, rateLimit=25, slot=self.request_dap, timeout=10.0
        )
        self.unblock_dap_proxy.connect(self.proxy_dap_request.unblock_proxy)

        self.scan_history(-1)

    ################################################################################
    # Widget Specific GUI interactions
    ################################################################################

    ################################################################################
    # Roi manager

    def _init_roi_manager(self):
        """
        Initialize the ROI manager for the Waveform widget.
        """
        self._roi_manager = WaveformROIManager(self.plot_item, parent=self)

        # Connect manager signals -> forward them via Waveform's own signals
        self._roi_manager.roi_changed.connect(self.roi_changed)
        self._roi_manager.roi_active.connect(self.roi_active)

        # Example: connect ROI changed to re-request DAP
        self.roi_changed.connect(self._on_roi_changed_for_dap)
        self._roi_manager.roi_active.connect(self.request_dap_update)
        self.toolbar.widgets["roi_linear"].action.toggled.connect(self._roi_manager.toggle_roi)

    @property
    def roi_region(self) -> tuple[float, float] | None:
        """
        Allows external code to get/set the ROI region easily via Waveform.
        """
        return self._roi_manager.roi_region

    @roi_region.setter
    def roi_region(self, value: tuple[float, float] | None):
        self._roi_manager.roi_region = value

    def select_roi(self, region: tuple[float, float]):
        """
        Public method if you want the old `select_roi` style.
        """
        self._roi_manager.select_roi(region)

    # If you want the old toggle_roi style:
    def toggle_roi(self, enabled: bool):
        self._roi_manager.toggle_roi(enabled)

    def _on_roi_changed_for_dap(self, region: tuple[float, float]):
        """
        Whenever the ROI changes, you might want to re-request DAP with the new x_min, x_max.
        """
        logger.info(f"ROI region changed to {region}, requesting new DAP fit.")
        # Example: you could store these in a local property, or directly call request_dap_update
        self.request_dap_update.emit()

    ################################################################################
    # Dap Summary

    def _add_dap_summary_side_menu(self):
        self.dap_summary = LMFitDialog(parent=self)
        self.side_panel.add_menu(
            action_id="fit_params",
            icon_name="monitoring",
            tooltip="Open Fit Parameters",
            widget=self.dap_summary,
            title="Fit Parameters",
        )
        self.dap_summary_update.connect(self.dap_summary.update_summary_tree)

    def _get_dap_from_target_widget(self) -> None:
        """Get the DAP data from the target widget and update the DAP dialog manually on creation."""
        dap_summary = self.get_dap_summary()
        for curve_id, data in dap_summary.items():
            md = {"curve_id": curve_id}
            self.dap_summary.update_summary_tree(data=data, metadata=md)

    def _update_dap_curves(self): ...

    @SafeSlot()
    def get_dap_params(self) -> dict:
        """
        Get the DAP parameters of all DAP curves.

        Returns:
            dict: DAP parameters of all DAP curves.
        """
        params = {}
        for curve in self._dap_curves:
            params[curve.name()] = curve.dap_params
        return params

    @SafeSlot()
    def get_dap_summary(self) -> dict:
        """
        Get the DAP summary of all DAP curves.

        Returns:
            dict: DAP summary of all DAP curves.
        """
        summary = {}
        for curve in self._dap_curves:
            summary[curve.name()] = curve.dap_summary
        return summary

    ################################################################################
    # Widget Specific Properties
    ################################################################################

    @SafeProperty(str)
    def x_mode(self) -> str:
        return self._x_axis_mode["name"]

    @x_mode.setter
    def x_mode(self, value: str):
        # FIXME wrong update of the label
        self._x_axis_mode["name"] = value
        self._switch_x_axis_item(mode=value)
        # self._update_x_label_suffix()  # TODO update straight away or wait for the next scan??
        self.async_signal_update.emit()
        self.sync_signal_update.emit()
        self.plot_item.enableAutoRange(x=True)

    @SafeProperty(str)
    def color_palette(self) -> str:
        return self.config.color_palette

    # TODO update colors of all curves
    @color_palette.setter
    def color_palette(self, value: str):
        try:
            self.config.color_palette = value
            colors = Colors.golden_angle_color(
                colormap=self.config.color_palette,
                num=max(10, len(self.plot_item.curves) + 1),
                format="HEX",
            )
            for i, curve in enumerate(self.plot_item.curves):
                curve.set_color(colors[i])
        except Exception:
            return

    # TODO for loading and setting json rpc_register has to be double checked
    @SafeProperty(str, designable=False)
    def curve_json(self) -> str:
        """
        A JSON string property that serializes all curves' pydantic configs.
        """
        raw_list = []
        for c in self.plot_item.curves:
            if c.config.source == "custom":  # Do not serialize custom curves
                continue
            cfg_dict = c.config.dict()
            raw_list.append(cfg_dict)
        return json.dumps(raw_list, indent=2)

    @curve_json.setter
    def curve_json(self, json_data: str):
        """
        Load curves from a JSON string and add them to the plot, omitting custom source curves.
        """
        try:
            curve_configs = json.loads(json_data)
            for cfg_dict in curve_configs:
                if cfg_dict.get("source") == "custom":
                    logger.warning(f"Custom source curve '{cfg_dict['label']}' not loaded.")
                    continue
                config = CurveConfig(**cfg_dict)
                self._add_curve(config=config)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")

    @property
    def curves(self) -> list[Curve]:
        """
        Get the curves of the plot widget as a list.

        Returns:
            list: List of curves.
        """
        return self.plot_item.curves

    @curves.setter
    def curves(self, value: list[Curve]):
        self.plot_item.curves = value

    ################################################################################
    # High Level methods for API
    ################################################################################
    # TODO such as plot, add, remove curve, etc.
    @SafeSlot(popup_error=True)
    def plot(
        self,
        arg1: list | np.ndarray | str | None = None,
        y: list | np.ndarray | None = None,
        x: list | np.ndarray | None = None,
        x_name: str | None = None,
        y_name: str | None = None,
        x_entry: str | None = None,
        y_entry: str | None = None,
        color: str | None = None,
        label: str | None = None,
        dap: str | None = None,
        **kwargs,
    ) -> Curve:
        # TODO review the docstring
        """
        Plot a curve to the plot widget.

        Args:
            arg1(list | np.ndarray | str | None): First argument which can be x data, y data, or y_name.
            y(list | np.ndarray): Custom y data to plot.
            x(list | np.ndarray): Custom y data to plot.
            x_name(str): Name of the x signal.
                - "auto": Use the best effort signal.
                - "timestamp": Use the timestamp signal.
                - "index": Use the index signal.
                - Custom signal name of device from BEC.
            y_name(str): The name of the device for the y-axis.
            x_entry(str): The name of the entry for the x-axis.
            y_entry(str): The name of the entry for the y-axis.
            color(str): The color of the curve.
            label(str): The label of the curve.
            dap(str): The dap model to use for the curve, only available for sync devices. If not specified, none will be added.

        Returns:
            Curve: The curve object.
        """
        # 0) preallocate
        source = "custom"
        x_data = None
        y_data = None

        # 1. Custom curve logic
        if x is not None and y is not None:
            source = "custom"
            x_data = np.asarray(x)
            y_data = np.asarray(y)

        if isinstance(arg1, str):
            y_name = arg1
        elif isinstance(arg1, list):
            if isinstance(y, list):
                source = "custom"
                x_data = np.asarray(arg1)
                y_data = np.asarray(y)
            if y is None:
                source = "custom"
                arr = np.asarray(arg1)
                x_data = np.arange(len(arr))
                y_data = arr
        elif isinstance(arg1, np.ndarray) and y is None:
            if arg1.ndim == 1:
                source = "custom"
                x_data = np.arange(len(arg1))
                y_data = arg1
            if arg1.ndim == 2 and arg1.shape[1] == 2:
                source = "custom"
                x_data = arg1[:, 0]
                y_data = arg1[:, 1]

        # If y_name is set => device data
        if y_name is not None and x_data is None and y_data is None:
            source = "device"
            # Validate or obtain entry
            y_entry = self.entry_validator.validate_signal(name=y_name, entry=y_entry)

        # If user gave x_name => store in x_axis_mode, but do not set data here
        # TODO check logic if legit
        if x_name is not None:
            self._x_axis_mode["name"] = x_name
            if x_name not in ["timestamp", "index", "auto"]:
                self._x_axis_mode["entry"] = self.entry_validator.validate_signal(x_name, x_entry)

        # Decide label if not provided
        if label is None:
            if source == "custom":
                label = f"Curve {len(self.plot_item.curves) + 1}"
            else:
                label = f"{y_name}-{y_entry}"

        # If color not provided, generate from palette
        if color is None:
            color = self._generate_color_from_palette()

        # Build the config
        config = CurveConfig(
            widget_class="Curve",
            parent_id=self.gui_id,
            label=label,
            color=color,
            source=source,
            **kwargs,
        )

        # If it's device-based, attach DeviceSignal
        if source == "device":
            config.signal = DeviceSignal(name=y_name, entry=y_entry)

        # CREATE THE CURVE
        curve = self._add_curve(config=config, x_data=x_data, y_data=y_data)

        if dap is not None and source == "device":
            self.add_dap_curve(device_label=curve.name(), dap_name=dap, **kwargs)

        return curve

    ################################################################################
    # Curve Management Methods
    def add_dap_curve(
        self, device_label: str, dap_name: str, color: str | None = None, **kwargs
    ) -> Curve:
        """
        Create a new DAP curve referencing the existing device curve `device_label`,
        with the data processing model `dap_name`.

        Args:
            device_label(str): The label of the device curve to add DAP to.
            dap_name(str): The name of the DAP model to use.
            color(str): The color of the curve.
            **kwargs

        Returns:
            Curve: The new DAP curve.
        """

        # 1) Find the existing device curve by label
        device_curve = self._find_curve_by_label(device_label)
        if not device_curve:
            raise ValueError(f"No existing curve found with label '{device_label}'.")
        if device_curve.config.source != "device":
            raise ValueError(
                f"Curve '{device_label}' is not a device curve. Only device curves can have DAP."
            )

        dev_name = device_curve.config.signal.name
        dev_entry = device_curve.config.signal.entry

        # 2) Build a label for the new DAP curve
        dap_label = f"{dev_name}-{dev_entry}-{dap_name}"

        # 3) Possibly raise if the DAP curve already exists
        if self._check_curve_id(dap_label):
            raise ValueError(f"DAP curve '{dap_label}' already exists.")

        if color is None:
            color = self._generate_color_from_palette()

        # Build config for DAP
        config = CurveConfig(
            widget_class="Curve",
            parent_id=self.gui_id,
            label=dap_label,
            color=color,
            source="dap",
            parent_label=device_label,
            symbol="star",
            **kwargs,
        )

        # Attach device signal with DAP
        config.signal = DeviceSignal(name=dev_name, entry=dev_entry, dap=dap_name)

        # 4) Create the DAP curve config using `_add_curve(...)`
        dap_curve = self._add_curve(config=config)

        return dap_curve

    def _add_curve(
        self,
        config: CurveConfig,
        x_data: np.ndarray | None = None,
        y_data: np.ndarray | None = None,
    ) -> Curve:
        """
        Private method to finalize creation of a new Curve in this Waveform widget
        based on an already-built `CurveConfig`.

        Args:
            config (CurveConfig): A fully populated pydantic model describing how to create and style the curve.
            x_data (np.ndarray | None): If this is a custom curve (config.source == "custom"), optional x data array.
            y_data (np.ndarray | None): If this is a custom curve (config.source == "custom"), optional y data array.

        Returns:
            Curve: The newly created curve object.

        Raises:
            ValueError: If a duplicate curve label/config is found, or if
                        custom data is missing for `source='custom'`.
        """
        label = config.label
        if not label:
            # Fallback label
            label = f"Curve {len(self.plot_item.curves) + 1}"
            config.label = label

        # Check for duplicates
        if self._check_curve_id(label):
            raise ValueError(f"Curve with ID '{label}' already exists in widget '{self.gui_id}'.")

        # If user did not provide color in config, pick from palette
        if not config.color:
            config.color = self._generate_color_from_palette()

        # For custom data, ensure x_data, y_data
        if config.source == "custom":
            if x_data is None or y_data is None:
                raise ValueError("For 'custom' curves, x_data and y_data must be provided.")

        # Actually create the Curve item
        curve = self._add_curve_object(name=label, config=config)

        # If custom => set initial data
        if config.source == "custom" and x_data is not None and y_data is not None:
            curve.setData(x_data, y_data)

        # If device => schedule BEC updates
        if config.source == "device":
            if self.scan_item is None:
                self.scan_history(-1)
            self.async_signal_update.emit()
            self.sync_signal_update.emit()
        if config.source == "dap":
            self.setup_dap_for_scan()
            self.request_dap()  # Request DAP update directly without blocking proxy

        return curve

    def _add_curve_object(self, name: str, config: CurveConfig) -> Curve:
        """
        Low-level creation of the PlotDataItem (Curve) from a `CurveConfig`.

        Args:
            name (str): The name/label of the curve.
            config (CurveConfig): Configuration model describing the curve.

        Returns:
            Curve: The newly created curve object, added to the plot.
        """
        curve = Curve(config=config, name=name, parent_item=self)
        self.plot_item.addItem(curve)
        self._categorise_device_curves()
        return curve

    def _generate_color_from_palette(self) -> str:
        """
        Generate a color for the next new curve, based on the current number of curves.
        """
        current_count = len(self.plot_item.curves)
        color_list = Colors.golden_angle_color(
            colormap=self.color_palette, num=max(10, current_count + 1), format="HEX"
        )
        return color_list[current_count]

    def _refresh_colors(self):
        """
        Re-assign colors to all existing curves so they match the new count-based distribution.
        """
        all_curves = self.plot_item.curves
        # Generate enough colors for the new total
        color_list = Colors.golden_angle_color(
            colormap=self.color_palette, num=max(10, len(all_curves)), format="HEX"
        )
        for i, curve in enumerate(all_curves):
            curve.set_color(color_list[i])

    def clear_all(self):
        """
        Clear all curves from the plot widget.
        """
        curve_list = [curve for curve in self.plot_item.curves]
        for curve in curve_list:
            self.remove_curve(curve.name())

    def remove_curve(self, curve: int | str):
        """
        Remove a curve from the plot widget.

        Args:
            curve(int|str): The curve to remove. Can be the order of the curve or the name of the curve.
        """
        # TODO check if it removes curve from rpc register !!!!
        if isinstance(curve, int):
            self._remove_curve_by_order(curve)
        elif isinstance(curve, str):
            self._remove_curve_by_name(curve)

        self._refresh_colors()

    def _remove_curve_by_name(self, name: str):
        """
        Remove a curve by its name from the plot widget.

        Args:
            name(str): Name of the curve to be removed.
        """
        for curve in self.plot_item.curves:
            if curve.name() == name:
                self.plot_item.removeItem(curve)
                self._curve_clean_up(curve)
                return

    def _remove_curve_by_order(self, N: int):
        """
        Remove a curve by its order from the plot widget.

        Args:
            N(int): Order of the curve to be removed.
        """
        if N < len(self.plot_item.curves):
            curve = self.plot_item.curves[N]
            self.plot_item.removeItem(curve)
            self._curve_clean_up(curve)

        else:
            logger.error(f"Curve order {N} out of range.")
            raise IndexError(f"Curve order {N} out of range.")

    def _curve_clean_up(self, curve: Curve):
        """
        Clean up the curve by disconnecting the async update signal (even for sync curves).

        Args:
            curve(Curve): The curve to clean up.
        """
        self.bec_dispatcher.disconnect_slot(
            self.on_async_readback,
            MessageEndpoints.device_async_readback(self.scan_id, curve.name()),
        )

        # Remove itself from the DAP summary
        if curve.config.source == "dap":
            self.dap_summary.remove_dap_data(curve.name())

        # find a corresponding dap curve and remove it
        for c in self.curves:
            if c.config.parent_label == curve.name():
                self.plot_item.removeItem(c)
                self._curve_clean_up(c)

    def _check_curve_id(self, curve_id: str) -> bool:
        """
        Check if a curve ID exists in the plot widget.

        Args:
            curve_id(str): The ID of the curve to check.

        Returns:
            bool: True if the curve ID exists, False otherwise.
        """
        curve_ids = [curve.name() for curve in self.plot_item.curves]
        if curve_id in curve_ids:
            return True
        return False

    def _find_curve_by_label(self, label: str) -> Curve | None:
        """
        Find a curve by its label.

        Args:
            label(str): The label of the curve to find.

        Returns:
            Curve|None: The curve object if found, None otherwise.
        """
        for c in self.curves:
            if c.name() == label:
                return c
        return None

    ################################################################################
    # BEC Update Methods
    ################################################################################
    @SafeSlot(dict, dict)
    def on_scan_status(self, msg: dict, meta: dict):
        """
        Initial scan status message handler, which is triggered at the begging and end of scan.
        Used for triggering the update of the sync and async curves.

        Args:
            msg(dict): The message content.
            meta(dict): The message metadata.
        """
        current_scan_id = msg.get("scan_id", None)
        if current_scan_id is None:
            return

        if current_scan_id != self.scan_id:
            self.reset()
            self.new_scan.emit()
            self.new_scan_id.emit(current_scan_id)
            self.auto_range_x = True
            self.auto_range_y = True
            self.old_scan_id = self.scan_id
            self.scan_id = current_scan_id
            self.scan_item = self.queue.scan_storage.find_scan_by_ID(self.scan_id)  # live scan

            self._mode = self._categorise_device_curves()

            # First trigger to sync and async data
            if self._mode == "sync":
                self.sync_signal_update.emit()
                logger.info("Scan status: Sync mode")
            elif self._mode == "async":
                for curve in self._async_curves:
                    self._setup_async_curve(curve)
                self.async_signal_update.emit()
                logger.info("Scan status: Async mode")
            else:
                self.sync_signal_update.emit()
                for curve in self._async_curves:
                    self._setup_async_curve(curve)
                self.async_signal_update.emit()
                logger.info("Scan status: Mixed mode")
                logger.warning("Mixed mode - integrity of x axis cannot be guaranteed.")
        self.setup_dap_for_scan()

    @SafeSlot(dict, dict)
    def on_scan_progress(self, msg: dict, meta: dict):
        """
        Slot for handling scan progress messages. Used for triggering the update of the sync curves.

        Args:
            msg(dict): The message content.
            meta(dict): The message metadata.
        """
        self.sync_signal_update.emit()

    def _fetch_scan_data_and_access(self):
        """
        Decide whether we're in a live scan or history
        and return the appropriate data dict and access key.

        Returns:
            data_dict (dict): The data structure for the current scan.
            access_key (str): Either 'val' (live) or 'value' (history).
        """
        if self.scan_item is None:
            # Optionally fetch the latest from history if nothing is set
            self.scan_history(-1)

        if hasattr(self.scan_item, "live_data"):
            # Live scan
            return self.scan_item.live_data, "val"
        else:
            # Historical
            scan_devices = self.scan_item.devices
            return (scan_devices, "value")

    # @SafeSlot() #TODO from some reason TypeError: Waveform.update_sync_curves() takes 1 positional argument but 2 were given
    def update_sync_curves(self):
        """
        Update the sync curves with the latest data from the scan.
        """
        data, access_key = self._fetch_scan_data_and_access()
        for curve in self._sync_curves:
            device_name = curve.config.signal.name
            device_entry = curve.config.signal.entry
            if access_key == "val":
                device_data = data.get(device_name, {}).get(device_entry, {}).get(access_key, None)
            else:
                device_data = (
                    data.get(device_name, {}).get(device_entry, {}).read().get("value", None)
                )
            x_data = self._get_x_data(device_name, device_entry)
            # TODO check logic for x data
            if len(data) == 0:  # case if the data is empty because motor is not scanned
                return
            if device_data is not None and x_data is not None:
                curve.setData(x_data, device_data)
            if device_data is not None and x_data is None:
                curve.setData(device_data)
        self.request_dap_update.emit()

    def update_async_curves(self):
        """
        Manually load data for asynchronous device curves (in history scenario)
        or re-check in live data if needed. For live scanning, typically real-time
        updates come from on_async_readback(). But if user is browsing history,
        we must fetch the final recorded data from the scan storage.

        This parallels update_sync_curves(), but for self._async_curves.
        """
        data, access_key = self._fetch_scan_data_and_access()

        for curve in self._async_curves:
            device_name = curve.config.signal.name
            device_entry = curve.config.signal.entry
            if access_key == "val":
                device_data = data.get(device_name, {}).get(device_entry, {}).get(access_key, None)
            else:
                device_data = (
                    data.get(device_name, {}).get(device_entry, {}).read().get("value", None)
                )

            x_data = self._get_x_data(device_name, device_entry)

            # If there's actual data, set it
            if device_data is not None:
                if x_data is not None:
                    curve.setData(x_data, device_data)
                else:
                    curve.setData(device_data)
        self.request_dap_update.emit()

    def _setup_async_curve(self, curve: Curve):
        name = curve.config.signal.name
        self.bec_dispatcher.disconnect_slot(
            self.on_async_readback, MessageEndpoints.device_async_readback(self.old_scan_id, name)
        )
        try:
            curve.clear_data()
        except KeyError:
            pass
        self.bec_dispatcher.connect_slot(
            self.on_async_readback,
            MessageEndpoints.device_async_readback(self.scan_id, name),
            from_start=True,
        )
        logger.info(f"Setup async curve {name}")

    @SafeSlot(dict, dict)
    def on_async_readback(self, msg, metadata):
        """
        Get async data readback.

        Args:
            msg(dict): Message with the async data.
            metadata(dict): Metadata of the message.
        """
        instruction = metadata.get("async_update")
        for curve in self._async_curves:
            y_name = curve.config.signal.name
            y_entry = curve.config.signal.entry
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
                                x_data = np.hstack((x_data, async_data["timestamp"]))
                            else:
                                x_data = async_data["timestamp"]
                                # FIXME x axis wrong if timestamp switched during scan
                            curve.setData(x_data, new_data)
                        else:
                            curve.setData(new_data)
                    elif instruction == "replace":
                        if x_name == "timestamp":
                            x_data = async_data["timestamp"]
                            curve.setData(x_data, data_plot)
                        else:
                            curve.setData(data_plot)
        self.request_dap_update.emit()

    def setup_dap_for_scan(self):
        """Setup DAP updates for the new scan."""
        self.bec_dispatcher.disconnect_slot(
            self.update_dap_curves,
            MessageEndpoints.dap_response(f"{self.old_scan_id}-{self.gui_id}"),
        )
        if len(self._dap_curves) > 0:
            self.bec_dispatcher.connect_slot(
                self.update_dap_curves,
                MessageEndpoints.dap_response(f"{self.scan_id}-{self.gui_id}"),
            )

    # @SafeSlot() #FIXME type error
    def request_dap(self):
        """Request new fit for data"""

        for dap_curve in self._dap_curves:
            parent_label = getattr(dap_curve.config, "parent_label", None)
            if not parent_label:
                continue
            # find the device curve
            parent_curve = self._find_curve_by_label(parent_label)
            if parent_curve is None:
                logger.warning(f"No device curve found for DAP curve '{dap_curve.name()}'!")
                continue

            x_data, y_data = parent_curve.get_data()
            model_name = dap_curve.config.signal.dap
            model = getattr(self.dap, model_name)
            try:
                x_min, x_max = self.roi_region
                x_data, y_data = self._crop_data(x_data, y_data, x_min, x_max)
            except TypeError:
                x_min = None
                x_max = None

            msg = messages.DAPRequestMessage(
                dap_cls="LmfitService1D",
                dap_type="on_demand",
                config={
                    "args": [],
                    "kwargs": {"data_x": x_data, "data_y": y_data},
                    "class_args": model._plugin_info["class_args"],
                    "class_kwargs": model._plugin_info["class_kwargs"],
                    "curve_label": dap_curve.name(),
                },
                metadata={"RID": f"{self.scan_id}-{self.gui_id}"},
            )
            self.client.connector.set_and_publish(MessageEndpoints.dap_request(), msg)

    @SafeSlot(dict, dict)
    def update_dap_curves(self, msg, metadata):
        """Callback for DAP response message."""
        self.unblock_dap_proxy.emit()
        msg_config = msg.get("dap_request", None).content.get("config", {})

        curve_id = msg_config.get("curve_label", None)
        curve = self._find_curve_by_label(curve_id)

        try:
            x = msg.get("data", None)[0].get("x", None)
            y = msg.get("data", None)[0].get("y", None)
        except:
            return
        curve.setData(x, y)
        curve.dap_params = msg["data"][1]["fit_parameters"]
        curve.dap_summary = msg["data"][1]["fit_summary"]
        metadata.update({"curve_id": curve_id})
        self.dap_params_update.emit(curve.dap_params, metadata)
        self.dap_summary_update.emit(curve.dap_summary, metadata)

    def _get_x_data(self, device_name: str, device_entry: str):
        """
        Get the x data for the curves with the decision logic based on the widget x mode configuration:
            - If x is called 'timestamp', use the timestamp data from the scan item.
            - If x is called 'index', use the rolling index.
            - If x is a custom signal, use the data from the scan item.
            - If x is not specified, use the first device from the scan report.

        Additionally, checks and updates the x label suffix.

        Args:
            device_name(str): The name of the device.
            device_entry(str): The entry of the device

        Returns:
            list|np.ndarray|None: X data for the curve.
        """
        x_data = None
        new_suffix = None
        data, access_key = self._fetch_scan_data_and_access()

        # 1 User wants custom signal
        # TODO extend validation
        if self._x_axis_mode["name"] not in ["timestamp", "index", "auto"]:
            x_name = self._x_axis_mode["name"]
            x_entry = self._x_axis_mode.get("entry", None)
            if x_entry is None:
                x_entry = self.entry_validator.validate_signal(x_name, None)
            # if the motor was not scanned, an empty list is returned and curves are not updated
            if access_key == "val":
                x_data = data.get(x_name, {}).get(x_entry, {}).get(access_key, None)
            else:
                x_data = data.get(x_name, {}).get(x_entry, {}).read().get("value", None)
            new_suffix = f" [custom: {x_name}-{x_entry}]"

        # 2 User wants timestamp
        if self._x_axis_mode["name"] == "timestamp":
            print("Timestamp mode")  # TODO change to logger
            print(f"Device name: {device_name}, entry: {device_entry}")  # TODO change to logger
            timestamps = data[device_name][device_entry].timestamps
            x_data = timestamps
            new_suffix = " [timestamp]"

        # 3 User wants index
        if self._x_axis_mode["name"] == "index":
            x_data = None
            new_suffix = " [index]"

        # 4 Best effort automatic mode
        if self._x_axis_mode["name"] is None or self._x_axis_mode["name"] == "auto":
            # 4.1 If there are async curves, use index
            if len(self._async_curves) > 0:
                x_data = None
                new_suffix = " [auto: index]"
                self._update_x_label_suffix(new_suffix)
            # 4.2 If there are sync curves, use the first device from the scan report
            else:
                try:
                    x_name = self._ensure_str_list(
                        self.scan_item.metadata["bec"]["scan_report_devices"]
                    )[0]
                except:
                    x_name = self.scan_item.status_message.info["scan_report_devices"][0]
                x_entry = self.entry_validator.validate_signal(x_name, None)
                if access_key == "val":
                    x_data = data.get(x_name, {}).get(x_entry, {}).get(access_key, None)
                else:
                    x_data = data.get(x_name, {}).get(x_entry, {}).read().get("value", None)
                new_suffix = f" [auto: {x_name}-{x_entry}]"
        self._update_x_label_suffix(new_suffix)
        return x_data

    # TODO reuse somehow in the x_mode setter
    def _update_x_label_suffix(self, new_suffix: str):
        """
        Update x_label so it ends with `new_suffix`, removing any old suffix.

        Args:
            new_suffix(str): The new suffix to add to the x_label.
        """

        if new_suffix == self._x_axis_mode["label_suffix"]:
            return

        old_label = self.x_label
        if self._x_axis_mode["label_suffix"] and old_label.endswith(
            self._x_axis_mode["label_suffix"]
        ):
            old_label = old_label[: -len(self._x_axis_mode["label_suffix"])]

        updated_label = old_label
        if new_suffix:
            updated_label += new_suffix

        self.x_label = updated_label
        self._x_axis_mode["label_suffix"] = new_suffix

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
        logger.info(f'Switching x-axis mode to "{mode}"')
        date_axis = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation="bottom")
        default_axis = pg.AxisItem(orientation="bottom")
        if mode == "timestamp":
            self.plot_item.setAxisItems({"bottom": date_axis})
        else:
            self.plot_item.setAxisItems({"bottom": default_axis})

    def _categorise_device_curves(self) -> str:
        """
        Categorise the device curves into sync and async based on the readout priority.
        """
        if self.scan_item is None:
            self.scan_history(-1)

        try:
            readout_priority = self.scan_item.metadata["bec"]["readout_priority"]
        except:
            readout_priority = self.scan_item.status_message.info["readout_priority"]

        # Reset sync/async curve lists
        self._async_curves.clear()
        self._sync_curves.clear()
        self._dap_curves.clear()
        found_async = False
        found_sync = False
        mode = "sync"

        readout_priority_async = self._ensure_str_list(readout_priority.get("async", []))
        readout_priority_sync = self._ensure_str_list(readout_priority.get("monitored", []))

        # Iterate over all curves
        for curve in self.curves:
            # categorise dap curves firsts
            if curve.config.source == "dap":
                self._dap_curves.append(curve)
                continue
            dev_name = curve.config.signal.name
            if dev_name in readout_priority_async:
                self._async_curves.append(curve)
                found_async = True
            elif dev_name in readout_priority_sync:
                self._sync_curves.append(curve)
                found_sync = True
            else:
                logger.warning("Device {dev_name} not found in readout priority list.")

        # Determine the mode of the scan
        if found_async and found_sync:
            mode = "mixed"
            logger.warning(
                f"Found both async and sync devices in the scan. X-axis integrity cannot be guaranteed."
            )
        elif found_async:
            mode = "async"
        elif found_sync:
            mode = "sync"

        logger.info(f"Scan {self.scan_id} => mode={self._mode}")
        return mode

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

        if scan_index is None and scan_id is None:
            logger.warning(f"Neither scan_id or scan_number was provided, fetching the latest scan")
            scan_index = -1

        if scan_index is not None:
            self.scan_item = self.client.history[scan_index]
            metadata = self.scan_item.metadata
            self.scan_id = metadata["bec"]["scan_id"]
        else:
            self.scan_id = scan_id
            self.scan_item = self.client.history.get_by_scan_id(scan_id)

        self._categorise_device_curves()

        self.setup_dap_for_scan()
        self.sync_signal_update.emit()
        self.async_signal_update.emit()

    ################################################################################
    # Utility Methods
    ################################################################################
    def _ensure_str_list(self, entries: list | tuple | np.ndarray):
        """
        Convert a variety of possible inputs (string, bytes, list/tuple/ndarray of either)
        into a list of Python strings.

        Args:
            entries:

        Returns:
            list[str]: A list of Python strings.
        """

        if isinstance(entries, (list, tuple, np.ndarray)):
            return [self._to_str(e) for e in entries]
        else:
            return [self._to_str(entries)]

    @staticmethod
    def _to_str(x):
        """
        Convert a single object x (which may be a Python string, bytes, or something else)
        into a plain Python string.
        """
        if isinstance(x, bytes):
            return x.decode("utf-8", errors="replace")
        return str(x)

    @staticmethod
    def _crop_data(x_data, y_data, x_min=None, x_max=None):
        """
        Utility function to crop x_data and y_data based on x_min and x_max.

        Args:
            x_data (np.ndarray): The array of x-values.
            y_data (np.ndarray): The array of y-values corresponding to x_data.
            x_min (float, optional): The lower bound for cropping. Defaults to None.
            x_max (float, optional): The upper bound for cropping. Defaults to None.

        Returns:
            tuple: (cropped_x_data, cropped_y_data)
        """
        # If either bound is None, skip cropping
        if x_min is None or x_max is None:
            return x_data, y_data

        # Create a boolean mask to select only those points within [x_min, x_max]
        mask = (x_data >= x_min) & (x_data <= x_max)

        return x_data[mask], y_data[mask]

    ################################################################################
    # Export Methods
    ################################################################################


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    set_theme("dark")
    widget = Waveform()
    widget.show()
    widget.plot(y_name="bpm4i", y_entry="bpm4i", dap="GaussianModel")
    widget.plot(y_name="bpm3a", y_entry="bpm3a")
    sys.exit(app.exec_())
