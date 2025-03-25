from __future__ import annotations

from collections import deque

import pyqtgraph as pg
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from pydantic import Field, ValidationError, field_validator
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QWidget

from bec_widgets.qt_utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.qt_utils.side_panel import SidePanel
from bec_widgets.utils import Colors, ConnectionConfig
from bec_widgets.widgets.plots_next_gen.multi_waveform.settings.control_panel import (
    MultiWaveformControlPanel,
)
from bec_widgets.widgets.plots_next_gen.multi_waveform.toolbar_bundles.monitor_selection import (
    MultiWaveformSelectionToolbarBundle,
)
from bec_widgets.widgets.plots_next_gen.plot_base import PlotBase

logger = bec_logger.logger


class MultiWaveformConfig(ConnectionConfig):
    color_palette: str | None = Field(
        "magma", description="The color palette of the figure widget.", validate_default=True
    )
    curve_limit: int | None = Field(
        200, description="The maximum number of curves to display on the plot."
    )
    flush_buffer: bool | None = Field(
        False, description="Flush the buffer of the plot widget when the curve limit is reached."
    )
    monitor: str | None = Field(None, description="The monitor to set for the plot widget.")
    curve_width: int | None = Field(1, description="The width of the curve on the plot.")
    opacity: int | None = Field(50, description="The opacity of the curve on the plot.")
    highlight_last_curve: bool | None = Field(
        True, description="Highlight the last curve on the plot."
    )

    model_config: dict = {"validate_assignment": True}
    _validate_color_map_z = field_validator("color_palette")(Colors.validate_color_map)


class MultiWaveform(PlotBase):
    PLUGIN = True
    RPC = True
    ICON_NAME = "ssid_chart"
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
        "set_curve_limit",
        "plot",
        "set_curve_highlight",
        "clear_curves",
    ]

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

        # For PropertyManager identification
        self.setObjectName("MultiWaveform")

        # Scan Data
        self.old_scan_id = None
        self.scan_id = None
        self.connected = False
        self._current_highlight_index = 0
        self._curves = deque()
        self.visible_curves = []
        self.number_of_visible_curves = 0

        self._init_control_panel()

    ################################################################################
    # Widget Specific GUI interactions
    ################################################################################
    def _init_toolbar(self):
        self.monitor_selection_bundle = MultiWaveformSelectionToolbarBundle(
            bundle_id="motor_selection", target_widget=self
        )
        self.toolbar.add_bundle(self.monitor_selection_bundle, target_widget=self)
        super()._init_toolbar()
        self.toolbar.widgets["reset_legend"].action.setVisible(False)

    def _init_control_panel(self):
        self.control_panel = SidePanel(self, orientation="top", panel_max_width=90)
        self.layout_manager.add_widget_relative(
            self.control_panel, self.round_plot_widget, "bottom"
        )
        self.controls = MultiWaveformControlPanel(parent=self, target_widget=self)
        self.control_panel.add_menu(
            action_id="control",
            icon_name="tune",
            tooltip="Show Control panel",
            widget=self.controls,
            title=None,
        )
        self.control_panel.toolbar.widgets["control"].action.trigger()

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
        self._sync_monitor_selection_toolbar()

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

    @SafeProperty(str)
    def monitor(self) -> str:
        """
        The monitor of the figure widget.
        """
        return self.config.monitor

    @monitor.setter
    def monitor(self, value: str):
        """
        Set the monitor of the figure widget.

        Args:
            value(str): The monitor to set.
        """
        self.plot(value)

    ################################################################################
    # High Level methods for API
    ################################################################################

    @SafeSlot(popup_error=True)
    def plot(self, monitor: str, color_palette: str | None = "magma"):
        """
        Create a plot for the given monitor.
        Args:
            monitor (str): The monitor to set.
            color_palette (str|None): The color palette to use for the plot.
        """
        self.entry_validator.validate_monitor(monitor)
        self._disconnect_monitor()
        self.config.monitor = monitor
        self._connect_monitor()
        if color_palette is not None:
            self.color_palette = color_palette
        self._sync_monitor_selection_toolbar()

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
    @SafeSlot(dict, dict)
    def on_monitor_1d_update(self, msg: dict, metadata: dict):
        """
        Update the plot widget with the monitor data.

        Args:
            msg(dict): The message data.
            metadata(dict): The metadata of the message.
        """
        data = msg.get("data", None)
        current_scan_id = metadata.get("scan_id", None)

        if current_scan_id != self.scan_id:
            self.scan_id = current_scan_id
            self.clear_curves()
            self.curves.clear()
            if self.crosshair:
                self.crosshair.clear_markers()

        # Always create a new curve and add it
        curve = pg.PlotDataItem()
        curve.setData(data)
        self.plot_item.addItem(curve)
        self.curves.append(curve)

        # Max Trace and scale colors
        self.set_curve_limit(self.config.curve_limit, self.config.flush_buffer)

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

    def _disconnect_monitor(self):
        try:
            previous_monitor = self.config.monitor
        except AttributeError:
            previous_monitor = None

        if previous_monitor and self.connected is True:
            self.bec_dispatcher.disconnect_slot(
                self.on_monitor_1d_update, MessageEndpoints.device_monitor_1d(previous_monitor)
            )
            self.connected = False

    def _connect_monitor(self):
        """
        Connect the monitor to the plot widget.
        """

        if self.config.monitor and self.connected is False:
            self.bec_dispatcher.connect_slot(
                self.on_monitor_1d_update, MessageEndpoints.device_monitor_1d(self.config.monitor)
            )
            self.connected = True

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

    def _sync_monitor_selection_toolbar(self):
        """
        Sync the motor map selection toolbar with the current motor map.
        """
        if self.monitor_selection_bundle is not None:
            monitor = self.monitor_selection_bundle.monitor.currentText()
            color_palette = self.monitor_selection_bundle.colormap_widget.colormap

            if monitor != self.config.monitor:
                self.monitor_selection_bundle.monitor.blockSignals(True)
                self.monitor_selection_bundle.monitor.set_device(self.config.monitor)
                self.monitor_selection_bundle.monitor.check_validity(self.config.monitor)
                self.monitor_selection_bundle.monitor.blockSignals(False)

            if color_palette != self.config.color_palette:
                self.monitor_selection_bundle.colormap_widget.blockSignals(True)
                self.monitor_selection_bundle.colormap_widget.colormap = self.config.color_palette
                self.monitor_selection_bundle.colormap_widget.blockSignals(False)
