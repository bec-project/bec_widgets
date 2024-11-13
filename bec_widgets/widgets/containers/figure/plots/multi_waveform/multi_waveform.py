from collections import deque
from typing import Literal, Optional

import pyqtgraph as pg
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from pydantic import Field, field_validator
from pyqtgraph.exporters import MatplotlibExporter
from qtpy.QtCore import Signal, Slot
from qtpy.QtWidgets import QWidget

from bec_widgets.utils import Colors
from bec_widgets.widgets.containers.figure.plots.plot_base import BECPlotBase, SubplotConfig

logger = bec_logger.logger


class BECMultiWaveformConfig(SubplotConfig):
    color_palette: Optional[str] = Field(
        "magma", description="The color palette of the figure widget.", validate_default=True
    )
    curve_limit: Optional[int] = Field(
        200, description="The maximum number of curves to display on the plot."
    )
    flush_buffer: Optional[bool] = Field(
        False, description="Flush the buffer of the plot widget when the curve limit is reached."
    )
    monitor: Optional[str] = Field(
        None, description="The monitor to set for the plot widget."
    )  # TODO validate monitor in bec -> maybe make it as SignalData class for validation purpose
    curve_width: Optional[int] = Field(1, description="The width of the curve on the plot.")
    opacity: Optional[int] = Field(50, description="The opacity of the curve on the plot.")
    highlight_last_curve: Optional[bool] = Field(
        True, description="Highlight the last curve on the plot."
    )

    model_config: dict = {"validate_assignment": True}
    _validate_color_map_z = field_validator("color_palette")(Colors.validate_color_map)


class BECMultiWaveform(BECPlotBase):
    monitor_signal_updated = Signal()
    highlighted_curve_index_changed = Signal(int)
    USER_ACCESS = [
        "_rpc_id",
        "_config_dict",
        "curves",
        "set_monitor",
        "set_opacity",
        "set_curve_limit",
        "set_curve_highlight",
        "set_colormap",
        "set",
        "set_title",
        "set_x_label",
        "set_y_label",
        "set_x_scale",
        "set_y_scale",
        "set_x_lim",
        "set_y_lim",
        "set_grid",
        "set_colormap",
        "enable_fps_monitor",
        "lock_aspect_ratio",
        "export",
        "get_all_data",
        "remove",
    ]

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        parent_figure=None,
        config: Optional[BECMultiWaveformConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
    ):
        if config is None:
            config = BECMultiWaveformConfig(widget_class=self.__class__.__name__)
        super().__init__(
            parent=parent, parent_figure=parent_figure, config=config, client=client, gui_id=gui_id
        )
        self.old_scan_id = None
        self.scan_id = None
        self.monitor = None
        self.connected = False
        self.current_highlight_index = 0
        self._curves = deque()
        self.visible_curves = []
        self.number_of_visible_curves = 0

        # Get bec shortcuts dev, scans, queue, scan_storage, dap
        self.get_bec_shortcuts()

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

    @property
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

    def set_monitor(self, monitor: str):
        """
        Set the monitor for the plot widget.
        Args:
            monitor (str): The monitor to set.
        """
        self.config.monitor = monitor
        self._connect_monitor()

    def _connect_monitor(self):
        """
        Connect the monitor to the plot widget.
        """
        try:
            previous_monitor = self.monitor
        except AttributeError:
            previous_monitor = None

        if previous_monitor and self.connected is True:
            self.bec_dispatcher.disconnect_slot(
                self.on_monitor_1d_update, MessageEndpoints.device_monitor_1d(previous_monitor)
            )
        if self.config.monitor and self.connected is False:
            self.bec_dispatcher.connect_slot(
                self.on_monitor_1d_update, MessageEndpoints.device_monitor_1d(self.config.monitor)
            )
            self.connected = True
            self.monitor = self.config.monitor

    @Slot(dict, dict)
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

        self.monitor_signal_updated.emit()

    @Slot(int)
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
        self.current_highlight_index = index
        num_colors = num_visible_curves
        colors = Colors.evenly_spaced_colors(
            colormap=self.config.color_palette, num=num_colors, format="HEX"
        )
        for i, curve in enumerate(self.plot_item.visible_curves):
            curve.setPen()
            if i == self.current_highlight_index:
                curve.setPen(pg.mkPen(color=colors[i], width=5))
                curve.setAlpha(alpha=1, auto=False)
                curve.setZValue(1)
            else:
                curve.setPen(pg.mkPen(color=colors[i], width=1))
                curve.setAlpha(alpha=self.config.opacity / 100, auto=False)
                curve.setZValue(0)

        self.highlighted_curve_index_changed.emit(self.current_highlight_index)

    @Slot(int)
    def set_opacity(self, opacity: int):
        """
        Set the opacity of the curve on the plot.

        Args:
            opacity(int): The opacity of the curve. 0-100.
        """
        self.config.opacity = max(0, min(100, opacity))
        self.set_curve_highlight(self.current_highlight_index)

    @Slot(int, bool)
    def set_curve_limit(self, max_trace: int, flush_buffer: bool = False):
        """
        Set the maximum number of traces to display on the plot.

        Args:
            max_trace (int): The maximum number of traces to display.
            flush_buffer (bool): Flush the buffer.
        """
        self.config.curve_limit = max_trace
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

    def scale_colors(self):
        """
        Scale the colors of the curves based on the current colormap.
        """
        if self.config.highlight_last_curve:
            self.set_curve_highlight(-1)  # Use -1 to highlight the last visible curve
        else:
            self.set_curve_highlight(self.current_highlight_index)

    def set_colormap(self, colormap: str):
        """
        Set the colormap for the curves.

        Args:
            colormap(str): Colormap for the curves.
        """
        self.config.color_palette = colormap
        self.set_curve_highlight(self.current_highlight_index)

    def hook_crosshair(self) -> None:
        super().hook_crosshair()
        if self.crosshair:
            self.highlighted_curve_index_changed.connect(self.crosshair.update_highlighted_curve)
            if self.curves:
                self.crosshair.update_highlighted_curve(self.current_highlight_index)

    def get_all_data(self, output: Literal["dict", "pandas"] = "dict") -> dict:
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
                logger.warning(
                    "Pandas is not installed. "
                    "Please install pandas using 'pip install pandas'."
                    "Output will be dictionary instead."
                )
                output = "dict"

        curve_keys = []
        curves_list = list(self.curves)
        for i, curve in enumerate(curves_list):
            x_data, y_data = curve.getData()
            if x_data is not None or y_data is not None:
                key = f"curve_{i}"
                curve_keys.append(key)
                if output == "dict":
                    data[key] = {"x": x_data.tolist(), "y": y_data.tolist()}
                elif output == "pandas" and pd is not None:
                    data[key] = pd.DataFrame({"x": x_data, "y": y_data})

        if output == "pandas" and pd is not None:
            combined_data = pd.concat([data[key] for key in curve_keys], axis=1, keys=curve_keys)
            return combined_data
        return data

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

    def export_to_matplotlib(self):
        """
        Export current waveform to matplotlib GUI. Available only if matplotlib is installed in the environment.
        """
        MatplotlibExporter(self.plot_item).export()


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.widgets.containers.figure import BECFigure

    app = QApplication(sys.argv)
    widget = BECFigure()
    widget.show()
    sys.exit(app.exec_())
