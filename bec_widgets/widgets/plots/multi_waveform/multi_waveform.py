from __future__ import annotations

from collections import deque
from typing import Literal

import pyqtgraph as pg
from bec_lib.logger import bec_logger
from pydantic import Field, ValidationError, field_validator
from qtpy.QtCore import QTimer, Signal
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.colors import Colors
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.qt_data_subscription import QtDataSubscription
from bec_widgets.utils.side_panel import SidePanel
from bec_widgets.utils.toolbars.actions import WidgetAction
from bec_widgets.widgets.plots.image.toolbar_components.device_selection import (
    MONITOR_1D_ENTRY,
    DeviceSelection,
    DeviceSelectionConnection,
    device_selection_bundle,
)
from bec_widgets.widgets.plots.multi_waveform.settings.control_panel import (
    MultiWaveformControlPanel,
)
from bec_widgets.widgets.plots.plot_base import PlotBase
from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget

logger = bec_logger.logger


class MultiWaveformConfig(ConnectionConfig):
    color_palette: str | None = Field(
        "plasma", description="The color palette of the figure widget.", validate_default=True
    )
    curve_limit: int | None = Field(
        200, description="The maximum number of curves to display on the plot."
    )
    flush_buffer: bool | None = Field(
        False, description="Flush the buffer of the plot widget when the curve limit is reached."
    )
    monitor: str | None = Field(None, description="The device to monitor for the plot widget.")
    monitor_signal: str | None = Field(
        None,
        description=(
            "The signal/entry to monitor on the device. The reserved entry "
            f"'{MONITOR_1D_ENTRY}' selects the scan-less device_monitor_1d stream."
        ),
    )
    connection_status: Literal["connected", "disconnected", "error"] = Field(
        "disconnected", description="Current connection status."
    )
    connection_error: str | None = Field(None, description="Last connection error, if any.")
    curve_width: int | None = Field(1, description="The width of the curve on the plot.")
    opacity: int | None = Field(50, description="The opacity of the curve on the plot.")
    highlight_last_curve: bool | None = Field(
        True, description="Highlight the last curve on the plot."
    )

    model_config: dict = {"validate_assignment": True}
    _validate_color_map_z = field_validator("color_palette")(Colors.validate_color_map)


class MultiWaveform(PlotBase):
    """
    MultiWaveform widget for displaying multiple waveforms emitted by a single signal.
    """

    PLUGIN = True
    RPC = True
    ICON_NAME = "ssid_chart"
    # Many simultaneous curves; the biggest beneficiary of the shader path.
    USE_OPENGL = True
    USER_ACCESS = [
        *PlotBase.USER_ACCESS,
        # MultiWaveform Specific RPC Access
        "highlighted_index",
        "highlighted_index.setter",
        "highlight_last_curve",
        "highlight_last_curve.setter",
        "color_palette",
        "color_palette.setter",
        "opacity",
        "opacity.setter",
        "flush_buffer",
        "flush_buffer.setter",
        "max_trace",
        "max_trace.setter",
        "monitor",
        "monitor.setter",
        "monitor_signal",
        "monitor_signal.setter",
        "set_curve_limit",
        "plot",
        "set_curve_highlight",
        "clear_curves",
    ]

    #: Async signal classes routed through the scan-scoped (live-follow) DataAPI path.
    SUPPORTED_SIGNALS = ["AsyncSignal", "AsyncMultiSignal", "DynamicSignal"]

    monitor_signal_updated = Signal()
    highlighted_curve_index_changed = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
        config: MultiWaveformConfig | None = None,
        client=None,
        gui_id: str | None = None,
        popups: bool = True,
        **kwargs,
    ):
        if config is None:
            config = MultiWaveformConfig(widget_class=self.__class__.__name__)
        super().__init__(
            parent=parent, config=config, client=client, gui_id=gui_id, popups=popups, **kwargs
        )

        # Scan Data
        self.old_scan_id = None
        self.scan_id = None
        self.connected = False
        self._current_highlight_index = 0
        self._curves = deque()
        self.visible_curves = []
        self.number_of_visible_curves = 0

        # Data delivery through the DataAPI: scan-less device streams
        # (monitor_1d, preview signals) or scan-scoped async signals.
        self._data_bridge: QtDataSubscription | None = None
        self._source_key: tuple[str, str] | None = None
        self._last_ordinal: int | None = None
        self._signal_config: dict | None = None
        self._device_selection_updating = False

        self._init_multiwaveform_toolbar()

    @property
    def _config(self) -> MultiWaveformConfig:
        """Connection-state view consumed by the shared DeviceSelectionConnection."""
        return self.config

    ################################################################################
    # Widget Specific GUI interactions
    ################################################################################
    def _init_multiwaveform_toolbar(self):
        bundle = device_selection_bundle(
            self.toolbar.components, client=self.client, ndim_filter=[1], include_monitor_1d=True
        )
        self.toolbar.components.add_safe(
            "color_map",
            WidgetAction(
                widget=BECColorMapWidget(cmap=self.config.color_palette), adjust_size=False
            ),
        )
        bundle.add_action("color_map")
        self.toolbar.add_bundle(bundle)
        self.toolbar.connect_bundle(
            "device_selection",
            DeviceSelectionConnection(self.toolbar.components, target_widget=self),
        )
        self.toolbar.toggle_action_visibility("reset_legend", visible=False)

        cmap = self.toolbar.components.get_action("color_map").widget
        cmap.colormap_changed_signal.connect(self.change_colormap)

        bundles = self.toolbar.shown_bundles
        bundles.insert(0, "device_selection")
        self.toolbar.show_bundles(bundles)

        self._init_control_panel()

        QTimer.singleShot(0, self._sync_device_selection)

    def _init_control_panel(self):
        control_panel = SidePanel(self, orientation="top", panel_max_width=90)
        self.layout_manager.add_widget_relative(control_panel, self.round_plot_widget, "bottom")
        self.controls = MultiWaveformControlPanel(parent=self, target_widget=self)
        control_panel.add_menu(
            action_id="control",
            icon_name="tune",
            tooltip="Show Control panel",
            widget=self.controls,
            title=None,
        )
        control_panel.toolbar.components.get_action("control").action.trigger()

    @SafeSlot()
    def on_device_selection_changed(self, _):
        """
        Called when device or signal selection changes in the toolbar.
        This reads from the toolbar and updates the widget properties.
        """
        if self._device_selection_updating:
            return

        self._device_selection_updating = True
        try:
            try:
                action = self.toolbar.components.get_action("device_selection")
            except Exception:
                return

            if action is None:
                return

            device_selection: DeviceSelection = action.widget
            device = device_selection.device_combo_box.currentText()
            signal_text = device_selection.signal_combo_box.currentText()

            if not device:
                self.device = ""
                return
            if not device_selection.device_combo_box.is_valid_input:
                return

            if not device_selection.signal_combo_box.is_valid_input:
                if self.config.monitor_signal:
                    self.signal = ""
                if device != (self.config.monitor or ""):
                    self.device = device
                return

            if device == self.config.monitor and signal_text == self.config.monitor_signal:
                return

            # Get the signal config stored in the combobox
            signal_config = device_selection.signal_combo_box.get_signal_config()

            if not signal_config and signal_text != MONITOR_1D_ENTRY:
                # Fallback: try to get config from device
                try:
                    device_obj = self.dev[device]
                    signal_config = device_obj._info["signals"].get(signal_text, {})
                except (KeyError, AttributeError):
                    logger.warning(f"Could not get signal config for {device}.{signal_text}")
                    signal_config = None

            # Store signal config and set properties which will trigger the connection
            pending_config = signal_config if isinstance(signal_config, dict) else None
            if device != (self.config.monitor or ""):
                self._signal_config = pending_config
                self.device = device
            # The device setter may replace the pending config while reconnecting
            # the previous signal; restore it for the signal connection.
            self._signal_config = pending_config
            self.signal = signal_text
        finally:
            self._device_selection_updating = False

    @SafeSlot(str)
    def change_colormap(self, colormap: str):
        self.color_palette = colormap

    ################################################################################
    # Widget Specific Properties
    ################################################################################

    @property
    def curves(self) -> deque:
        """
        Get the curves of the plot widget as a deque.
        Returns:
            deque: Deque of curves.
        """
        return self._curves

    @curves.setter
    def curves(self, value: deque):
        self._curves = value

    @SafeProperty(int, designable=False)
    def highlighted_index(self):
        return self._current_highlight_index

    @highlighted_index.setter
    def highlighted_index(self, value: int):
        self._current_highlight_index = value
        self.property_changed.emit("highlighted_index", value)
        self.set_curve_highlight(value)

    @SafeProperty(bool)
    def highlight_last_curve(self) -> bool:
        """
        Get the highlight_last_curve property.
        Returns:
            bool: The highlight_last_curve property.
        """
        return self.config.highlight_last_curve

    @highlight_last_curve.setter
    def highlight_last_curve(self, value: bool):
        self.config.highlight_last_curve = value
        self.property_changed.emit("highlight_last_curve", value)
        self.set_curve_highlight(-1)

    @SafeProperty(str)
    def color_palette(self) -> str:
        """
        The color palette of the figure widget.
        """
        return self.config.color_palette

    @color_palette.setter
    def color_palette(self, value: str):
        """
        Set the color palette of the figure widget.

        Args:
            value(str): The color palette to set.
        """
        try:
            self.config.color_palette = value
        except ValidationError:
            return
        self.set_curve_highlight(self._current_highlight_index)
        self._sync_colormap_toolbar()

    @SafeProperty(int)
    def opacity(self) -> int:
        """
        The opacity of the figure widget.
        """
        return self.config.opacity

    @opacity.setter
    def opacity(self, value: int):
        """
        Set the opacity of the figure widget.

        Args:
            value(int): The opacity to set.
        """
        self.config.opacity = max(0, min(100, value))
        self.property_changed.emit("opacity", value)
        self.set_curve_highlight(self._current_highlight_index)

    @SafeProperty(bool)
    def flush_buffer(self) -> bool:
        """
        The flush_buffer property.
        """
        return self.config.flush_buffer

    @flush_buffer.setter
    def flush_buffer(self, value: bool):
        self.config.flush_buffer = value
        self.property_changed.emit("flush_buffer", value)
        self.set_curve_limit(
            max_trace=self.config.curve_limit, flush_buffer=self.config.flush_buffer
        )

    @SafeProperty(int)
    def max_trace(self) -> int:
        """
        The maximum number of traces to display on the plot.
        """
        return self.config.curve_limit

    @max_trace.setter
    def max_trace(self, value: int):
        """
        Set the maximum number of traces to display on the plot.

        Args:
            value(int): The maximum number of traces to display.
        """
        self.config.curve_limit = value
        self.property_changed.emit("max_trace", value)
        self.set_curve_limit(
            max_trace=self.config.curve_limit, flush_buffer=self.config.flush_buffer
        )

    ################################################################################
    # Data Acquisition
    ################################################################################

    @SafeProperty(str, auto_emit=True, designable=False)
    def device(self) -> str:
        """
        The name of the device to monitor for waveform data.
        """
        return self.config.monitor or ""

    @device.setter
    def device(self, value: str):
        """
        Set the device name for the plot. This should be used together with signal.
        When both device and signal are set, the widget connects to that device signal.

        Args:
            value(str): The name of the device to monitor.
        """
        if not value:
            # Clear the monitor if empty device name
            if self.config.monitor:
                self._cleanup_data_api_subscription()
                self.config.monitor = None
                self.config.monitor_signal = None
                self._signal_config = None
                self._set_connection_status("disconnected")
            return

        old_device = self.config.monitor
        if old_device and self.config.monitor_signal and old_device != value:
            self._cleanup_data_api_subscription()
        self.config.monitor = value

        # If we have a signal, reconnect with the new device
        signal = self.config.monitor_signal
        if not signal:
            return
        if signal == MONITOR_1D_ENTRY:
            self._signal_config = None
            self._setup_data_api_subscription()
            return
        try:
            device_obj = self.dev[value]
            signal_config = device_obj._info.get("signals", {}).get(signal)
        except (KeyError, AttributeError):
            logger.warning(f"Device '{value}' not found")
            self._cleanup_data_api_subscription()
            self._set_connection_status("error", f"Device '{value}' not found")
            return
        if isinstance(signal_config, dict) and signal_config.get("signal_class"):
            self._signal_config = signal_config
            self._setup_data_api_subscription()
        else:
            logger.warning(f"Signal '{signal}' doesn't exist on device '{value}'")
            self._cleanup_data_api_subscription()
            self.config.monitor_signal = None
            self._signal_config = None
            self._set_connection_status("error", f"Signal '{signal}' doesn't exist")

    @SafeProperty(str, auto_emit=True, designable=False)
    def signal(self) -> str:
        """
        The signal/entry name to monitor on the device.
        """
        return self.config.monitor_signal or ""

    @signal.setter
    def signal(self, value: str):
        """
        Set the device signal for the plot. This should be used together with device.
        When set, it will connect to updates from that device signal.

        Args:
            value(str): The signal name to monitor. The reserved entry ``"monitor_1d"``
                selects the scan-less device_monitor_1d stream.
        """
        if not value:
            if self.config.monitor_signal:
                self._cleanup_data_api_subscription()
                self.config.monitor_signal = None
                self._signal_config = None
                self._set_connection_status("disconnected")
            return

        old_signal = self.config.monitor_signal
        if self.config.monitor and old_signal and old_signal != value:
            self._cleanup_data_api_subscription()
        self.config.monitor_signal = value

        if not self.config.monitor:
            logger.debug(f"signal setter: No device set yet for signal '{value}'")
            return

        if value == MONITOR_1D_ENTRY:
            self._signal_config = None
            self._setup_data_api_subscription()
            return

        try:
            device_obj = self.dev[self.config.monitor]
            signal_config = device_obj._info["signals"].get(value)
        except (KeyError, AttributeError):
            signal_config = None
        if not isinstance(signal_config, dict) or not signal_config.get("signal_class"):
            # Fall back to a combobox-provided config for this entry, if any
            signal_config = self._signal_config
            if not self._signal_config_matches(signal_config, value):
                logger.warning(
                    f"Could not find valid configuration for signal '{value}' "
                    f"on device '{self.config.monitor}'."
                )
                self._signal_config = None
                self._set_connection_status("error", f"Signal '{value}' not found")
                return
        self._signal_config = signal_config
        self._setup_data_api_subscription()

    @SafeProperty(str)
    def monitor(self) -> str:
        """
        The monitored device of the figure widget (alias of ``device``).
        """
        return self.config.monitor

    @monitor.setter
    def monitor(self, value: str):
        """
        Set the monitored device and connect to it, auto-selecting the signal.

        Args:
            value(str): The device to monitor.
        """
        self.plot(value)

    @SafeProperty(str)
    def monitor_signal(self) -> str:
        """
        The monitored signal/entry on the device (alias of ``signal``).
        """
        return self.config.monitor_signal

    @monitor_signal.setter
    def monitor_signal(self, value: str):
        """
        Set the monitored signal/entry on the device.

        Args:
            value(str): The signal to monitor.
        """
        self.signal = value

    ################################################################################
    # High Level methods for API
    ################################################################################

    @SafeSlot(popup_error=True)
    def plot(self, monitor: str, signal: str | None = None, color_palette: str | None = "plasma"):
        """
        Create a plot for the given monitor device and signal.

        Args:
            monitor (str): The device to monitor.
            signal (str|None): The signal/entry to monitor on the device. The reserved
                entry ``"monitor_1d"`` selects the scan-less device_monitor_1d stream.
                If None, the signal is auto-selected: the device's only 1D-capable
                preview/async signal if unambiguous, the monitor_1d stream otherwise.
            color_palette (str|None): The color palette to use for the plot.
        """
        if not monitor:
            self.device = ""
            return
        self.entry_validator.validate_monitor(monitor)
        if signal is None:
            signal = self._default_signal_for(monitor)
        if self.config.monitor_signal and self.config.monitor != monitor:
            # Clear the old entry first to avoid reconnect attempts on the new device
            self.signal = ""
        # Guard the device update so the toolbar sync does not pull the
        # auto-selected first combobox entry before the requested signal is set.
        self._device_selection_updating = True
        try:
            self.device = monitor
        finally:
            self._device_selection_updating = False
        self.signal = signal
        if color_palette is not None:
            self.color_palette = color_palette

    @SafeSlot(int, bool)
    def set_curve_limit(self, max_trace: int, flush_buffer: bool):
        """
        Set the maximum number of traces to display on the plot.

        Args:
            max_trace (int): The maximum number of traces to display.
            flush_buffer (bool): Flush the buffer.
        """
        if max_trace != self.config.curve_limit:
            self.config.curve_limit = max_trace
        if flush_buffer != self.config.flush_buffer:
            self.config.flush_buffer = flush_buffer

        if self.config.curve_limit is None:
            self.scale_colors()
            return

        if self.config.flush_buffer:
            # Remove excess curves from the plot and the deque
            while len(self.curves) > self.config.curve_limit:
                curve = self.curves.popleft()
                self.plot_item.removeItem(curve)
        else:
            # Hide or show curves based on the new max_trace
            num_curves_to_show = min(self.config.curve_limit, len(self.curves))
            for i, curve in enumerate(self.curves):
                if i < len(self.curves) - num_curves_to_show:
                    curve.hide()
                else:
                    curve.show()
        self.scale_colors()
        self.monitor_signal_updated.emit()

    ################################################################################
    # BEC Update Methods
    ################################################################################
    @SafeSlot(object)
    def _on_data_update(self, update) -> None:
        """
        Render one columnar DataAPI update of the monitored source.

        Each value of the source is one 1-D trace (newest last); ordinals are
        arrival counters (device streams) or per-scan async ordinals, so only
        traces newer than the last rendered ordinal are appended to the curve
        deque. ``"replace"`` async sources expose a single current state which
        replaces the trace set.

        Args:
            update (SubscriptionUpdate): Full-state snapshot of the monitored
                source.
        """
        if self._source_key is None:
            return
        source = update.get(*self._source_key)
        if source is None or source.values is None or len(source.values) == 0:
            return

        current_scan_id = self._effective_scan_id(update, source)
        if current_scan_id != self.scan_id:
            self.old_scan_id = self.scan_id
            self.scan_id = current_scan_id
            self.clear_curves()
            self.curves.clear()
            if update.scan_id:
                # Scan-scoped async ordinals restart with every scan; the
                # arrival counters of scan-less device streams do not.
                self._last_ordinal = None
            if self.crosshair:
                self.crosshair.clear_markers()

        if source.metadata.get("async_update_type") == "replace":
            # A replace source exposes one point: its current full state.
            self.clear_curves()
            self.curves.clear()
            curve = pg.PlotDataItem()
            curve.setData(source.values[-1])
            self.plot_item.addItem(curve)
            self.curves.append(curve)
            self._last_ordinal = None
            self.set_curve_limit(self.config.curve_limit, self.config.flush_buffer)
            return

        last_ordinal = self._last_ordinal
        new_traces = [
            (ordinal, data)
            for ordinal, data in zip(source.ordinals, source.values)
            if last_ordinal is None or ordinal > last_ordinal
        ]
        if not new_traces:
            return

        for _, data in new_traces:
            curve = pg.PlotDataItem()
            curve.setData(data)
            self.plot_item.addItem(curve)
            self.curves.append(curve)
        self._last_ordinal = new_traces[-1][0]

        # Max Trace and scale colors
        self.set_curve_limit(self.config.curve_limit, self.config.flush_buffer)

    @staticmethod
    def _effective_scan_id(update, source) -> str | None:
        """
        The scan id an update belongs to: the bound scan for scan-scoped
        subscriptions, the last-seen scan id from the stream metadata for
        scan-less device streams.

        Args:
            update (SubscriptionUpdate): The update snapshot.
            source (SourceData): The rendered source of the update.

        Returns:
            str | None: The scan id, or None if not known (yet).
        """
        if update.scan_id:
            return update.scan_id
        return source.metadata.get("scan_id")

    @SafeSlot(int)
    def set_curve_highlight(self, index: int):
        """
        Set the curve highlight based on visible curves.

        Args:
            index (int): The index of the curve to highlight among visible curves.
        """
        self.plot_item.visible_curves = [curve for curve in self.curves if curve.isVisible()]
        num_visible_curves = len(self.plot_item.visible_curves)
        self.number_of_visible_curves = num_visible_curves

        if num_visible_curves == 0:
            return  # No curves to highlight

        if index >= num_visible_curves:
            index = num_visible_curves - 1
        elif index < 0:
            index = num_visible_curves + index
        self._current_highlight_index = index
        num_colors = num_visible_curves
        colors = Colors.evenly_spaced_colors(
            colormap=self.config.color_palette, num=num_colors, format="HEX"
        )
        for i, curve in enumerate(self.plot_item.visible_curves):
            curve.setPen()
            if i == self._current_highlight_index:
                curve.setPen(pg.mkPen(color=colors[i], width=5))
                curve.setAlpha(alpha=1, auto=False)
                curve.setZValue(1)
            else:
                curve.setPen(pg.mkPen(color=colors[i], width=1))
                curve.setAlpha(alpha=self.config.opacity / 100, auto=False)
                curve.setZValue(0)

        self.highlighted_curve_index_changed.emit(self._current_highlight_index)

    ################################################################################
    # Signal classification and DataAPI routing
    ################################################################################

    def _default_signal_for(self, device: str) -> str:
        """
        Auto-select a signal for a device-only selection.

        Returns the device's only 1D-capable preview/async signal if it is
        unambiguous; the reserved monitor_1d stream entry otherwise (legacy
        monitor devices, or devices with several 1D-capable signals).

        Args:
            device (str): The device name.

        Returns:
            str: The signal/entry to monitor.
        """
        try:
            device_obj = self.dev[device]
            signals = device_obj._info.get("signals", {})
        except (KeyError, AttributeError):
            signals = {}
        supported = {"PreviewSignal", *self.SUPPORTED_SIGNALS}
        candidates = []
        for name, signal_config in signals.items():
            if not isinstance(signal_config, dict):
                continue
            if signal_config.get("signal_class") not in supported:
                continue
            describe = signal_config.get("describe") or {}
            signal_info = describe.get("signal_info") or {}
            if signal_info.get("ndim") == 1:
                candidates.append(name)
        if len(candidates) == 1:
            return candidates[0]
        if candidates:
            logger.warning(
                f"Device '{device}' has multiple 1D-capable signals ({candidates}); "
                f"defaulting to the '{MONITOR_1D_ENTRY}' stream. Select a signal "
                "explicitly to plot one of them."
            )
        return MONITOR_1D_ENTRY

    @staticmethod
    def _signal_config_matches(signal_config: dict | None, signal: str) -> bool:
        """Whether a stored signal config describes the given signal/entry."""
        if not isinstance(signal_config, dict) or not signal_config.get("signal_class"):
            return False
        return signal in (signal_config.get("component_name"), signal_config.get("obj_name"))

    def _resolve_route(self, device: str, signal: str) -> tuple[str | None, str, int | None] | None:
        """
        Classify the selected (device, signal) into a DataAPI route.

        Routing table:
            monitor_1d sentinel -> scan=None, entry "monitor_1d" (device stream)
            PreviewSignal (1D)  -> scan=None, entry = signal (device stream)
            Async*/DynamicSignal (1D) -> scan="live", entry = obj_name (live-follow)

        Args:
            device (str): The device name.
            signal (str): The selected signal/entry.

        Returns:
            tuple | None: ``(scan, entry, max_points)`` or None if the selection
                cannot be served (connection status is set accordingly).
        """
        if signal == MONITOR_1D_ENTRY:
            return (None, MONITOR_1D_ENTRY, self.config.curve_limit)

        signal_config = self._signal_config or {}
        signal_class = signal_config.get("signal_class")
        supported_classes = ["PreviewSignal"] + self.SUPPORTED_SIGNALS
        if signal_class not in supported_classes:
            logger.warning(
                f"Signal '{device}.{signal}' has unsupported signal class '{signal_class}'. "
                f"Supported classes: {supported_classes}"
            )
            self._set_connection_status("error", f"Unsupported signal class '{signal_class}'")
            return None

        describe = signal_config.get("describe") or {}
        signal_info = describe.get("signal_info") or {}
        ndim = signal_info.get("ndim", None)
        if ndim != 1:
            logger.warning(f"Unsupported ndim '{ndim}' for monitor '{device}.{signal}'.")
            self._set_connection_status("error", f"Unsupported ndim '{ndim}'")
            return None

        if signal_class == "PreviewSignal":
            # Scan-less device stream served by the DataAPI device plugin.
            return (None, signal, self.config.curve_limit)

        # Scan-scoped async stream; the DataAPI rebinds on new scans and hands
        # terminal scans over to history automatically (live-follow).
        entry = signal_config.get("obj_name") or f"{device}_{signal}"
        return ("live", entry, None)

    def _setup_data_api_subscription(self):
        """(Re)create the DataAPI subscription for the configured device and signal."""
        self._cleanup_data_api_subscription()
        device = self.config.monitor
        signal = self.config.monitor_signal
        if not device or not signal:
            self._set_connection_status("disconnected")
            return
        route = self._resolve_route(device, signal)
        if route is None:
            return
        scan, entry, max_points = route
        try:
            self._data_bridge = QtDataSubscription(
                self.client,
                sources=[(device, entry)],
                scan=scan,
                parent=self,
                min_emit_interval=self.update_interval_s,
                max_points=max_points,
            )
            self._data_bridge.updated.connect(self._on_data_update)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                f"Failed to configure multi waveform data subscription for "
                f"{device}.{signal}: {exc}"
            )
            self._cleanup_data_api_subscription()
            self._set_connection_status("error", str(exc))
            return
        self._source_key = (device, entry)
        self.connected = True
        self._set_connection_status("connected")
        logger.info(f"Connected to {device}.{signal} via {'live' if scan else 'device'} scope")

    def _cleanup_data_api_subscription(self):
        self._last_ordinal = None
        self._source_key = None
        self.connected = False
        if self._data_bridge is None:
            return
        try:
            self._data_bridge.close()
        finally:
            self._data_bridge = None

    def _set_connection_status(self, status: str, message: str | None = None) -> None:
        self.config.connection_status = status
        self.config.connection_error = message
        self.property_changed.emit("connection_status", status)
        self.property_changed.emit("connection_error", message or "")

    ################################################################################
    # Utility Methods
    ################################################################################
    def scale_colors(self):
        """
        Scale the colors of the curves based on the current colormap.
        """
        # TODO probably has to be changed to property
        if self.config.highlight_last_curve:
            self.set_curve_highlight(-1)  # Use -1 to highlight the last visible curve
        else:
            self.set_curve_highlight(self._current_highlight_index)

    def hook_crosshair(self) -> None:
        """
        Specific hookfor crosshair, since it is for multiple curves.
        """
        super().hook_crosshair()
        if self.crosshair:
            self.highlighted_curve_index_changed.connect(self.crosshair.update_highlighted_curve)
            if self.curves:
                self.crosshair.update_highlighted_curve(self._current_highlight_index)

    def clear_curves(self):
        """
        Remove all curves from the plot, excluding crosshair items.
        """
        items_to_remove = []
        for item in self.plot_item.items:
            if not getattr(item, "is_crosshair", False) and isinstance(item, pg.PlotDataItem):
                items_to_remove.append(item)
        for item in items_to_remove:
            self.plot_item.removeItem(item)

    def _sync_device_selection(self):
        """
        Synchronize the device and signal comboboxes with the current monitor state.
        This ensures the toolbar reflects the device and signal properties.
        """
        try:
            device_selection_action = self.toolbar.components.get_action("device_selection")
        except Exception:  # noqa: BLE001 - toolbar might not be ready during early init
            logger.warning(f"MultiWaveform ({self.object_name}) toolbar was not ready during init.")
            return

        if device_selection_action is None:
            return

        device_selection: DeviceSelection = device_selection_action.widget
        target_device = self.config.monitor or ""
        target_entry = self.config.monitor_signal or ""

        # Check if already synced
        if (
            device_selection.device_combo_box.currentText() == target_device
            and device_selection.signal_combo_box.currentText() == target_entry
        ):
            return

        device_selection.set_device_and_signal(target_device, target_entry)

    def _sync_signal_from_toolbar(self) -> None:
        """
        Pull the signal selection from the toolbar if it differs from the current signal.
        This keeps CLI-driven device updates in sync with the signal combobox state.
        """
        if self._device_selection_updating:
            return

        if not self.config.monitor:
            return

        try:
            device_selection_action = self.toolbar.components.get_action("device_selection")
        except Exception:  # noqa: BLE001 - toolbar might not be ready during early init
            return

        if device_selection_action is None:
            return

        device_selection: DeviceSelection = device_selection_action.widget
        if device_selection.device_combo_box.currentText() != self.config.monitor:
            return

        signal_text = device_selection.signal_combo_box.currentText()
        if not signal_text or signal_text == self.config.monitor_signal:
            return

        signal_config = device_selection.signal_combo_box.get_signal_config()
        if signal_config:
            self._signal_config = signal_config
        elif signal_text != MONITOR_1D_ENTRY:
            return

        self._device_selection_updating = True
        try:
            self.signal = signal_text
        finally:
            self._device_selection_updating = False

    def _sync_colormap_toolbar(self):
        """
        Sync the colormap toolbar widget with the current color palette.
        """
        try:
            cmap_widget: BECColorMapWidget = self.toolbar.components.get_action("color_map").widget
        except Exception:  # noqa: BLE001 - toolbar might not be ready during early init
            return
        if cmap_widget.colormap != self.config.color_palette:
            cmap_widget.blockSignals(True)
            cmap_widget.colormap = self.config.color_palette
            cmap_widget.blockSignals(False)

    def cleanup(self):
        self._cleanup_data_api_subscription()
        self.clear_curves()
        try:
            self.toolbar.disconnect_bundle("device_selection")
        except Exception:  # noqa: BLE001
            pass
        super().cleanup()
