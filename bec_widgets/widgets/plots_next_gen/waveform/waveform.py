from __future__ import annotations

import json

import pyqtgraph as pg
import numpy as np
from collections import defaultdict
from typing import Literal, Optional

from pydantic import Field, field_validator
from qtpy.QtCore import Slot

from bec_lib.device import ReadoutPriority
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QWidget

from bec_lib.endpoints import MessageEndpoints
from bec_widgets.qt_utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils import ConnectionConfig
from bec_widgets.utils.colors import set_theme, Colors
from bec_widgets.widgets.plots_next_gen.plot_base import PlotBase
from bec_widgets.widgets.plots_next_gen.waveform.curve import Curve, CurveConfig, DeviceSignal


# noinspection PyDataclass
class WaveformConfig(ConnectionConfig):
    color_palette: Optional[str] = Field(
        "magma", description="The color palette of the figure widget.", validate_default=True
    )
    # curves: dict[str, CurveConfig] = Field(
    #     {}, description="The list of curves to be added to the 1D waveform widget."
    # )

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
    scan_signal_update = Signal()  # TODO maybe rename to async_signal_update
    async_signal_update = Signal()
    # dap_params_update = Signal(dict, dict)
    # dap_summary_update = Signal(dict, dict)
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
        self._curves_by_class = defaultdict(dict)  # TODO needed can be 'device', 'custom','dap'
        self._sync_curves = []
        self._async_curves = []
        self._curves = self.plot_item.curves
        self._mode: Literal["sync", "async", "mixed"] = (
            "sync"  # TODO mode probably not needed as well, both wil be allowed
        )

        # Scan data
        self.old_scan_id = None
        self.scan_id = None
        self.scan_item = None
        self.current_sources = {"sync": [], "async": []}  # TODO maybe not needed
        self.x_mode = "auto"  # TODO maybe default could be 'best_effort'
        self._x_axis_mode = {
            "name": None,
            "entry": None,
            "readout_priority": None,
            "label_suffix": "",
        }  # TODO decide which one to use

        # TODO review relevant bec_dispatcher signals
        # Scan segment update proxy
        self.proxy_update_plot = pg.SignalProxy(
            self.scan_signal_update, rateLimit=25, slot=self.update_sync_curves
        )
        # self.proxy_update_dap = pg.SignalProxy(
        #     self.scan_signal_update, rateLimit=25, slot=self.refresh_dap
        # )
        # self.async_signal_update.connect(self.replot_async_curve)
        # self.autorange_signal.connect(self.auto_range)
        # self.bec_dispatcher.connect_slot(self.on_scan_segment, MessageEndpoints.scan_segment())

        # self.bec_dispatcher.connect_slot(
        #     self.on_scan_segment, MessageEndpoints.scan_segment()
        # )  # TODO probably not needed
        # Scan status update loop
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.bec_dispatcher.connect_slot(self.on_scan_progress, MessageEndpoints.scan_progress())

        # Curve update loop
        # self.proxy_scan_update = pg.SignalProxy(
        #     self.scan_signal_update, rateLimit=25, slot=self.update_sync_curves
        # )  # TODO implement
        # self.proxy_dap_update = pg.SignalProxy(
        #     self.dap_signal_update, rateLimit=25, slot=self.update_dap_curves
        # )  # TODO implement
        # self.bec_dispatcher.connect_slot(
        #     self.async_signal_update, self.update_async_curves
        # )  # TODO implement

        # TODO test curves

        # self.plot([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], label="test_curve")
        # self.plot([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], label="test_curve2")

    ################################################################################
    # Widget Specific Properties
    ################################################################################
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
        for c in self._curves:
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
        return self._curves

    @curves.setter
    def curves(self, value: list[Curve]):
        self._curves = value

    ################################################################################
    # High Level methods for API
    ################################################################################
    # TODO such as plot, add, remove curve, etc.
    def plot(
        self,
        arg1: list | np.ndarray | str | None = None,
        y: list | np.ndarray | None = None,
        x: list | np.ndarray | None = None,
        x_name: str | None = None,
        y_name: str | None = None,
        z_name: str | None = None,  # TODO not needed
        x_entry: str | None = None,
        y_entry: str | None = None,
        z_entry: str | None = None,  # TODO not needed
        color: str | None = None,
        color_map_z: (
            str | None
        ) = "magma",  # TODO probably not needed here there will be wrapper for this
        label: str | None = None,
        validate: bool = True,
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
            Curve: The curve object.
        """
        # 1. Custom curve logic
        if x is not None and y is not None:
            return self._add_curve_custom(x=x, y=y, label=label, color=color, **kwargs)

        if isinstance(arg1, str):
            y_name = arg1
        elif isinstance(arg1, list):
            if isinstance(y, list):
                return self._add_curve_custom(x=arg1, y=y, label=label, color=color, **kwargs)
            if y is None:
                x = np.arange(len(arg1))
                return self._add_curve_custom(x=x, y=arg1, label=label, color=color, **kwargs)
        elif isinstance(arg1, np.ndarray) and y is None:
            if arg1.ndim == 1:
                x = np.arange(arg1.size)
                return self._add_curve_custom(x=x, y=arg1, label=label, color=color, **kwargs)
            if arg1.ndim == 2:
                x = arg1[:, 0]
                y = arg1[:, 1]
                return self._add_curve_custom(x=x, y=y, label=label, color=color, **kwargs)
        if y_name is None:
            raise ValueError("y_name must be provided.")  # TODO provide logger

        # 2. BEC device curve logic
        self._add_device_curve(y_name, y_entry)  # TODO change y_name and y_entry

        # TODO implement x_mode change if putted by user

        # FIXME figure out dap logic adding
        # TODO implement the plot method

    ################################################################################
    # Curve Management Methods
    ################################################################################
    # TODO implement curve management methods

    def _add_device_curve(self, device_name: str, device_signal: str):
        """Add BEC Device curve, can be sync(monitored device) or async device."""
        # TODO implement signal fetch from BEC if not provided

        # Setup identifiers
        source = "device"
        curve_id = f"{device_name}-{device_signal}"

        # Check if curve already exists
        curve_exits = self._check_curve_id(curve_id)
        if curve_exits:
            raise ValueError(
                f"Curve with ID '{curve_id}' already exists in widget '{self.gui_id}'."
            )  # TODO change to logger

        # TODO do device check with BEC if it is loaded

        # Create curve by config
        color = self._generate_color_from_palette()  # TODO check the refresh logic of this
        curve_config = CurveConfig(
            widget_class="BECCurve",
            parent_id=self.gui_id,
            label=curve_id,
            color=color,
            source=source,
            signal=DeviceSignal(name=device_name, entry=device_signal),
        )
        self._add_curve_object(name=curve_id, source=source, config=curve_config)

    # TODO consolidate with adding curve object
    def _add_curve_custom(
        self,
        x: list | np.ndarray,
        y: list | np.ndarray,
        label: str = None,
        color: str = None,
        **kwargs,
    ) -> Curve:
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

        curve_id = label or f"Curve {len(self.plot_item.curves) + 1}"

        curve_exits = self._check_curve_id(curve_id)
        if curve_exits:
            raise ValueError(
                f"Curve with ID '{curve_id}' already exists in widget '{self.gui_id}'."
            )  # TODO change to logger

        color = (
            color
            or Colors.golden_angle_color(
                colormap="magma",  # FIXME Config do not have color_palette anymore
                num=max(10, len(self.plot_item.curves) + 1),
                format="HEX",
            )[len(self.plot_item.curves)]
        )

        # Create curve by config
        curve_config = CurveConfig(
            widget_class="BECCurve",
            parent_id=self.gui_id,
            label=curve_id,
            color=color,
            source="custom",
            **kwargs,
        )
        curve = self._add_curve_object(
            name=curve_id, source="custom", config=curve_config, data=(x, y)
        )
        return curve

    def _add_curve_object(
        self,
        name: str,
        source: str,  # todo probably also not needed
        config: CurveConfig,
        data: tuple[list | np.ndarray, list | np.ndarray] = None,
    ) -> Curve:
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
        # curve_exits = self._check_curve_id(config.label)
        # if curve_exits:
        #     raise ValueError(
        #         f"Curve with ID '{config.label}' already exists in widget '{self.gui_id}'."
        #     )  # TODO change to logger
        #
        # color = (
        #         color
        #         or Colors.golden_angle_color(
        #     colormap="magma",  # FIXME Config do not have color_palette anymore
        #     num=max(10, len(self.plot_item.curves) + 1),
        #     format="HEX",
        # )[len(self.plot_item.curves)]
        # )
        curve = Curve(config=config, name=name, parent_item=self)
        self._curves_by_class[source][name] = curve
        self.plot_item.addItem(curve)
        # self.config.curves[name] = curve.config #TODO will be changed
        if data is not None:
            curve.setData(data[0], data[1])
        # self.set_legend_label_size() #TODO will be changed
        return curve

    # TODO decide if needed
    def _add_curve(
        self,
        name: str,
        config: CurveConfig,
        data: tuple[list | np.ndarray, list | np.ndarray] = None,
    ):
        curve = Curve(name=name, config=config, parent_item=self)
        self.plot_item.addItem(curve)

        return curve

    def _generate_color_from_palette(self) -> str:
        # TODO think about refreshing all colors during this
        color = Colors.golden_angle_color(
            colormap=self.color_palette, num=max(10, len(self.plot_item.curves) + 1), format="HEX"
        )[len(self.plot_item.curves)]
        return color

    def _remove_curve_by_source(self, source: str):
        # TODO consider if this is needed
        pass

    def remove_curve(self, curve: int | str):
        """
        Remove a curve from the plot widget.

        Args:
            curve(int|str): The curve to remove. Can be the order of the curve or the name of the curve.
        """
        if isinstance(curve, int):
            self._remove_curve_by_order(curve)
        elif isinstance(curve, str):
            self._remove_curve_by_name(curve)

    def _remove_curve_by_name(self, name: str):
        """
        Remove a curve by its name from the plot widget.

        Args:
            name(str): Name of the curve to be removed.
        """
        for curve in self.plot_item.curves:
            if curve.name() == name:
                self.plot_item.removeItem(curve)
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
        else:
            raise IndexError(f"Curve order {N} out of range.")  # TODO can be logged

    def _check_curve_id(self, curve_id: str) -> bool:
        """
        Check if a curve ID exists in the plot widget.

        Args:
            curve_id(str): The ID of the curve to check.

        Returns:
            bool: True if the curve ID exists, False otherwise.
        """
        curve_ids = [curve.name() for curve in self._curves]
        if curve_id in curve_ids:
            return True
        return False

    ################################################################################
    # BEC Update Methods
    ################################################################################
    # TODO here will go bec related update slots
    @SafeSlot(dict, dict)
    def on_scan_segment(self, msg: dict, meta: dict):
        # TODO probably not needed
        print(f"Scan segment: {msg}")

    @SafeSlot(dict, dict)
    def on_scan_status(self, msg: dict, meta: dict):
        print(f"Scan status: {msg}")
        print(f"Scan status meta: {meta}")
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
            elif self._mode == "async":
                # TODO sync should be setup to new scan id
                self.async_signal_update.emit()
            else:
                self.scan_signal_update.emit()
                self.async_signal_update.emit()

    # TODO scan progress update loop triggering curve updates
    @SafeSlot(dict, dict)
    def on_scan_progress(self, msg: dict, meta: dict, *args, **kwargs):
        print(f"Scan progress: {msg}")
        print(f"Scan progress meta: {meta}")
        self.scan_signal_update.emit()

    def update_sync_curves(self):
        print("Updating sync curves")
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
            device_data = data[device_name][device_entry].val
            x_name = self.scan_item.status_message.info["scan_report_devices"][0]
            # TODO logic for x_entry
            x_entry = x_name
            x_data = data[x_name][x_entry].val
            curve.setData(x_data, device_data)

    def _categorise_device_curves(self, readout_priority: dict) -> str:
        # Reset sync/async curve lists
        self._async_curves = []
        self._sync_curves = []
        found_async = False
        found_sync = False
        mode = "sync"

        readout_priority_async = readout_priority.get("async", [])
        readout_priority_sync = readout_priority.get("monitored", [])

        # Iterate over all curves
        for curve_id, curve in self._curves_by_class["device"].items():
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

        # Determine mode of the scan
        if found_async and found_sync:
            mode = "mixed"
            print(
                f"Found both async and sync devices in the scan. X-axis integrity cannot be guaranteed."
            )  # TODO change to logger
            # TODO do some prompt to user to decide which mode to use
        elif found_async:
            mode = "async"
        elif found_sync:
            mode = "sync"
        else:
            mode = "sync"

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
    widget.plot(y_name="bpm4i", y_entry="bpm4i")
    widget.plot(y_name="bpm3a", y_entry="bpm3a")
    sys.exit(app.exec_())
