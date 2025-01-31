from __future__ import annotations

import json
from typing import Literal, Optional

import numpy as np
import pyqtgraph as pg

from bec_lib import bec_logger
from bec_lib import messages
from bec_lib.device import ReadoutPriority
from bec_lib.endpoints import MessageEndpoints
from pydantic import Field, field_validator
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QWidget

from bec_widgets.qt_utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils import ConnectionConfig
from bec_widgets.utils.bec_signal_proxy import BECSignalProxy
from bec_widgets.utils.colors import Colors, set_theme
from bec_widgets.widgets.plots_next_gen.plot_base import PlotBase
from bec_widgets.widgets.plots_next_gen.waveform.curve import Curve, CurveConfig, DeviceSignal

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

    READOUT_PRIORITY_HANDLER = {
        ReadoutPriority.ON_REQUEST: "on_request",
        ReadoutPriority.BASELINE: "baseline",
        ReadoutPriority.MONITORED: "monitored",
        ReadoutPriority.ASYNC: "async",
        ReadoutPriority.CONTINUOUS: "continuous",
    }

    # TODO implement signals
    scan_signal_update = Signal()  # TODO maybe rename to sync_signal_update
    async_signal_update = Signal()
    request_dap_update = Signal()
    unblock_dap_proxy = Signal()
    dap_signal_update = Signal()
    dap_params_update = Signal(dict, dict)
    dap_summary_update = Signal(dict, dict)
    # autorange_signal = Signal()
    new_scan = Signal()
    new_scan_id = Signal(str)

    # roi_changed = Signal(tuple)
    # roi_active = Signal(bool)
    # request_dap_refresh = Signal()
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
        self._x_axis_mode = {
            "name": "auto",
            "entry": None,
            "readout_priority": None,
            "label_suffix": "",
        }  # TODO decide which one to use

        # Scan status update loop
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.bec_dispatcher.connect_slot(self.on_scan_progress, MessageEndpoints.scan_progress())

        # Curve update loop
        # TODO review relevant bec_dispatcher signals
        self.proxy_update_plot = pg.SignalProxy(
            self.scan_signal_update, rateLimit=25, slot=self.update_sync_curves
        )
        self.proxy_dap_request = BECSignalProxy(
            self.request_dap_update, rateLimit=25, slot=self.request_dap
        )
        self.unblock_dap_proxy.connect(self.proxy_dap_request.unblock_proxy)

        # TODO implement bec proxy to request dap update
        # self.async_signal_update.connect(self.replot_async_curve)
        # self.autorange_signal.connect(self.auto_range)
        # self.proxy_dap_update = pg.SignalProxy(
        #     self.dap_signal_update, rateLimit=25, slot=self.update_dap_curves
        # )  # TODO implement
        # self.bec_dispatcher.connect_slot(
        #     self.async_signal_update, self.update_async_curves
        # )  # TODO implement

    ################################################################################
    # Widget Specific Properties
    ################################################################################

    @SafeProperty(str)
    def x_mode(self) -> str:
        return self._x_axis_mode["name"]

    @x_mode.setter
    def x_mode(self, value: str):
        self._x_axis_mode["name"] = value
        self._switch_x_axis_item(mode=value)
        # self._update_x_label_suffix() #TODO update straight away or wait for the next scan??
        self.async_signal_update.emit()
        self.scan_signal_update.emit()
        self.request_dap_update.emit()
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
    @SafeProperty(str)
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
        # TODO implement setter
        pass

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
        validate: bool = True,  # TODO global vs local validation rules
        dap: str | None = None,  # TODO add dap custom curve wrapper
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
            validate(bool): If True, validate the device names and entries.
            dap(str): The dap model to use for the curve, only available for sync devices. If not specified, none will be added.

        Returns:
            Curve: The curve object.
        """
        # 1. Custom curve logic
        if x is not None and y is not None:
            return self._add_curve(
                source="custom", label=label, color=color, x_data=x, y_data=y, **kwargs
            )

        # Another custom case if user put 'arg1' as data
        if isinstance(arg1, list) or isinstance(arg1, np.ndarray):
            # if user also gave 'y' => custom
            if isinstance(y, list) or isinstance(y, np.ndarray):
                return self._add_curve(
                    source="custom",
                    label=label,
                    color=color,
                    x_data=np.asarray(arg1),
                    y_data=np.asarray(y),
                    **kwargs,
                )
            # if user did not pass 'y', we guess we want to do x=..., y=...
            if y is None:
                x_ary = np.arange(len(arg1))
                return self._add_curve(
                    source="custom",
                    label=label,
                    color=color,
                    x_data=x_ary,
                    y_data=np.asarray(arg1),
                    **kwargs,
                )

            # if it's a 2D array
            if isinstance(arg1, np.ndarray) and arg1.ndim == 2 and y is None:
                x_ary = arg1[:, 0]
                y_ary = arg1[:, 1]
                return self._add_curve(
                    source="custom", label=label, color=color, x_data=x_ary, y_data=y_ary, **kwargs
                )

        # 2) If user gave 'arg1' as str => interpret as y_name
        if isinstance(arg1, str):
            y_name = arg1

        # 3) If y_name => device
        if y_name is None:
            logger.error("y_name must be provided if not using custom data")
            raise ValueError("y_name must be provided if not using custom data")

        # TODO decide if to use logger or raise
        y_entry = self.entry_validator.validate_signal(name=y_name, entry=y_entry)

        # device curve
        curve = self._add_curve(
            source="device",
            label=label,
            color=color,
            device_name=y_name,
            device_entry=y_entry,
            **kwargs,
        )

        # 4) If user gave x_name => store in x_axis_mode
        # TODO double check the logic
        if x_name is not None:
            self._x_axis_mode["name"] = x_name
            if x_name not in ["timestamp", "index", "auto"]:
                self._x_axis_mode["entry"] = self.entry_validator.validate_signal(
                    name=x_name, entry=x_entry
                )

        if dap is not None:
            # self.add_dap_curve(device_label=label, dap_name=dap, color=color, **kwargs) #TODO adapt to use this function
            self._add_curve(
                source="dap", device_name=y_name, device_entry=y_entry, dap=dap, **kwargs
            )

        return curve

    ################################################################################
    # Curve Management Methods
    # TODO has to be tested
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

        # 4) Create the DAP curve config using `_add_curve(...)`
        new_curve = self._add_curve(
            source="dap",
            label=dap_label,
            color=color,
            device_name=dev_name,
            device_entry=dev_entry,
            dap=dap_name,
            parent_label=device_label,  # link back to the device curve
            symbol="*",
            **kwargs,
        )

        # 5) Immediately request a DAP update (this can trigger the pipeline)
        self.request_dap_update.emit()

        return new_curve

    def _add_curve(
        self,
        source: Literal["custom", "device", "dap"],
        label: str | None = None,
        color: str | None = None,
        device_name: str | None = None,
        device_entry: str | None = None,
        x_data: np.ndarray | None = None,
        y_data: np.ndarray | None = None,
        dap: str | None = None,
        **kwargs,
    ) -> Curve:
        # TODO check the label logic
        # TODO parent_label has to be done better with consideration of custom labels
        parent_label = None
        if not label:
            # Generate fallback
            if source == "custom":
                label = f"Curve {len(self.plot_item.curves) + 1}"
            if source == "device":
                label = f"{device_name}-{device_entry}"
            if source == "dap":
                label = f"{device_name}-{device_entry}-{dap}"
                parent_label = f"{device_name}-{device_entry}"

        if self._check_curve_id(label):
            raise ValueError(f"Curve with ID '{label}' already exists in widget '{self.gui_id}'.")

        # If color not provided, pick from the palette
        if not color:
            color = self._generate_color_from_palette()

        # Build the config
        config = CurveConfig(
            widget_class="Curve",
            parent_id=self.gui_id,
            label=label,
            color=color,
            source=source,
            parent_label=parent_label,
            **kwargs,
        )

        # If device-based, add device signal
        if source == "device":
            self.entry_validator.validate_signal(device_name, device_entry)  # TODO notify user
            # if not device_name or not device_entry:
            #     raise ValueError("device_name and device_entry are required for 'device' source.")
            config.signal = DeviceSignal(name=device_name, entry=device_entry)

        # If custom, we might want x_data, y_data
        final_data = None
        if source == "custom":
            if x_data is None or y_data is None:
                raise ValueError("x_data,y_data must be provided for 'custom' source.")
            final_data = (x_data, y_data)

        if source == "dap":  # TODO change logic
            config.signal = DeviceSignal(name=device_name, entry=device_entry, dap=dap)

        # Finally, create the curve item
        curve = self._add_curve_object(name=label, source=source, config=config, data=final_data)
        return curve

    def _add_curve_object(
        self,
        name: str,
        source: str,
        config: CurveConfig,
        data: tuple[list | np.ndarray, list | np.ndarray] = None,
    ) -> Curve:
        curve = Curve(config=config, name=name, parent_item=self)
        # self._curves_by_class[source][name] = curve
        self.plot_item.addItem(curve)

        if data is not None:
            curve.setData(data[0], data[1])
        if source == "device":
            self.async_signal_update.emit()
            self.scan_signal_update.emit()

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
            raise IndexError(f"Curve order {N} out of range.")  # TODO can be logged

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

    # TODO extend and implement
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
    # TODO here will go bec related update slots

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
        readout_priority = msg.get("readout_priority", None)
        if current_scan_id is None or readout_priority is None:
            return

        if current_scan_id != self.scan_id:
            self.reset()
            self.new_scan.emit()
            self.new_scan_id.emit(current_scan_id)
            self.auto_range_x = True
            self.auto_range_y = True
            self.old_scan_id = self.scan_id
            self.scan_id = current_scan_id
            self.scan_item = self.queue.scan_storage.find_scan_by_ID(self.scan_id)

            self._mode = self._categorise_device_curves(readout_priority)

            # First trigger to sync and async data
            if self._mode == "sync":
                self.scan_signal_update.emit()
                print("Sync mode")  # TODO change to logger
            elif self._mode == "async":
                for curve in self._async_curves:
                    self._setup_async_curve(curve)
                self.async_signal_update.emit()
                print("Async mode")  # TODO change to logger
            else:
                self.scan_signal_update.emit()
                for curve in self._async_curves:
                    self._setup_async_curve(curve)
                self.async_signal_update.emit()
                print("Mixed mode")  # TODO change to logger
        self.setup_dap_for_scan()

    @SafeSlot(dict, dict)
    def on_scan_progress(self, msg: dict, meta: dict):
        """
        Slot for handling scan progress messages. Used for triggering the update of the sync curves.

        Args:
            msg(dict): The message content.
            meta(dict): The message metadata.
        """
        self.scan_signal_update.emit()

    # @SafeSlot() #TODO from some reason TypeError: Waveform.update_sync_curves() takes 1 positional argument but 2 were given
    def update_sync_curves(self):
        try:
            data = (
                self.scan_item.live_data
                if hasattr(self.scan_item, "live_data")  # backward compatibility
                else self.scan_item.data
            )
        except AttributeError:
            return

        for curve in self._sync_curves:
            device_name = curve.config.signal.name
            device_entry = curve.config.signal.entry
            device_data = data.get(device_name, {}).get(device_entry, {}).get("val", None)
            x_data = self._get_x_data(device_name, device_entry)
            if len(data) == 0:  # case if the data is empty because motor is not scanned
                return
            if device_data is not None and x_data is not None:
                curve.setData(x_data, device_data)
            if device_data is not None and x_data is None:
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
        print(f"Setup async curve {name}")  # TODO change to logger

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

            # TODO implement DAP logic
            msg = messages.DAPRequestMessage(
                dap_cls="LmfitService1D",
                dap_type="on_demand",
                config={
                    "args": [],
                    "kwargs": {"data_x": x_data, "data_y": y_data},  # TODO add xmin,xmax as before
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
        msg_config = msg.get("dap_request", None).content.get("config", {})

        curve_id = msg_config.get("curve_label", None)
        curve = self._find_curve_by_label(curve_id)

        try:
            x = msg.get("data", None)[0].get("x", None)
            y = msg.get("data", None)[0].get("y", None)
        except:
            self.unblock_dap_proxy.emit()
            return
        curve.setData(x, y)
        curve.dap_params = msg["data"][1]["fit_parameters"]
        curve.dap_summary = msg["data"][1]["fit_summary"]
        metadata.update({"curve_id": curve_id})
        self.dap_params_update.emit(curve.dap_params, metadata)
        self.dap_summary_update.emit(curve.dap_summary, metadata)
        self.unblock_dap_proxy.emit()

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
        live_data = (
            self.scan_item.live_data
            if hasattr(self.scan_item, "live_data")
            else self.scan_item.data
        )

        # 1 User wants custom signal
        # TODO extend validation
        if self._x_axis_mode["name"] not in ["timestamp", "index", "auto"]:
            x_name = self._x_axis_mode["name"]
            x_entry = self._x_axis_mode.get("entry", None)
            if x_entry is None:
                x_entry = self.entry_validator.validate_signal(x_name, None)
            # if the motor was not scanned, an empty list is returned and curves are not updated
            x_data = live_data.get(x_name, {}).get(x_entry, {}).get("val", [])
            new_suffix = f" [custom: {x_name}-{x_entry}]"

        # 2 User wants timestamp
        if self._x_axis_mode["name"] == "timestamp":
            print("Timestamp mode")  # TODO change to logger
            print(f"Device name: {device_name}, entry: {device_entry}")  # TODO change to logger
            timestamps = live_data[device_name][device_entry].timestamps
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
                x_name = self.scan_item.status_message.info["scan_report_devices"][0]
                x_entry = self.entry_validator.validate_signal(x_name, None)
                x_data = live_data.get(x_name, {}).get(x_entry, {}).get("val", None)
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
        print(f'Switching x-axis mode to "{mode}"')  # TODO change to logger
        date_axis = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation="bottom")
        default_axis = pg.AxisItem(orientation="bottom")
        if mode == "timestamp":
            self.plot_item.setAxisItems({"bottom": date_axis})
        else:
            self.plot_item.setAxisItems({"bottom": default_axis})

    def _categorise_device_curves(self, readout_priority: dict) -> str:
        """
        Categorise the device curves into sync and async based on the readout priority.

        Args:
            readout_priority(dict): The readout priority of the scan.
        """
        # Reset sync/async curve lists
        self._async_curves = []
        self._sync_curves = []
        self._dap_curves = []
        found_async = False
        found_sync = False
        mode = "sync"

        readout_priority_async = readout_priority.get("async", [])
        readout_priority_sync = readout_priority.get("monitored", [])

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
                print(
                    f"Device {dev_name} not found in readout priority list."
                )  # TODO change to logger

        # Determine the mode of the scan
        if found_async and found_sync:
            mode = "mixed"
            logger.warning(
                f"Found both async and sync devices in the scan. X-axis integrity cannot be guaranteed."
            )
            # TODO do some prompt to user to decide which mode to use
        elif found_async:
            mode = "async"
        elif found_sync:
            mode = "sync"

        logger.info(f"Curve acquisition mode: {mode}")

        return mode

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
    widget.plot("monitor_async")
    widget.plot("bullshit")
    # widget.plot(y_name="bpm4i", y_entry="bpm4i")
    # widget.plot(y_name="bpm3a", y_entry="bpm3a")
    sys.exit(app.exec_())
