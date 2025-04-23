from __future__ import annotations

from typing import Literal, Optional

import pyqtgraph as pg
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError
from qtpy import QtCore, QtGui
from qtpy.QtCore import QSize, Slot
from qtpy.QtWidgets import QSizePolicy, QWidget

from bec_widgets.utils import Colors, ConnectionConfig, EntryValidator
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.progress.ring_progress_bar.ring import Ring, RingConfig

logger = bec_logger.logger


class RingProgressBarConfig(ConnectionConfig):
    color_map: Optional[str] = Field(
        "magma", description="Color scheme for the progress bars.", validate_default=True
    )
    min_number_of_bars: int | None = Field(
        1, description="Minimum number of progress bars to display."
    )
    max_number_of_bars: int | None = Field(
        10, description="Maximum number of progress bars to display."
    )
    num_bars: int | None = Field(1, description="Number of progress bars to display.")
    gap: int | None = Field(20, description="Gap between progress bars.")
    auto_updates: bool | None = Field(
        True, description="Enable or disable updates based on scan queue status."
    )
    rings: list[RingConfig] | None = Field([], description="List of ring configurations.")

    @field_validator("num_bars")
    @classmethod
    def validate_num_bars(cls, v, values):
        min_number_of_bars = values.data.get("min_number_of_bars", None)
        max_number_of_bars = values.data.get("max_number_of_bars", None)
        if min_number_of_bars is not None and max_number_of_bars is not None:
            logger.info(
                f"Number of bars adjusted to be between defined min:{min_number_of_bars} and max:{max_number_of_bars} number of bars."
            )
            v = max(min_number_of_bars, min(v, max_number_of_bars))
            return v

    @field_validator("rings")
    @classmethod
    def validate_rings(cls, v, values):
        if v is not None and v is not []:
            num_bars = values.data.get("num_bars", None)
            if len(v) != num_bars:
                raise PydanticCustomError(
                    "different number of configs",
                    f"Length of rings configuration ({len(v)}) does not match the number of bars ({num_bars}).",
                    {"wrong_value": len(v)},
                )
            indices = [ring.index for ring in v]
            if sorted(indices) != list(range(len(indices))):
                raise PydanticCustomError(
                    "wrong indices",
                    f"Indices of ring configurations must be unique and in order from 0 to num_bars {num_bars}.",
                    {"wrong_value": indices},
                )
        return v

    _validate_colormap = field_validator("color_map")(Colors.validate_color_map)


class RingProgressBar(BECWidget, QWidget):
    """
    Show the progress of devices, scans or custom values in the form of ring progress bars.
    """

    PLUGIN = True
    ICON_NAME = "track_changes"
    USER_ACCESS = [
        "_get_all_rpc",
        "_rpc_id",
        "_config_dict",
        "rings",
        "update_config",
        "add_ring",
        "remove_ring",
        "set_precision",
        "set_min_max_values",
        "set_number_of_bars",
        "set_value",
        "set_colors_from_map",
        "set_colors_directly",
        "set_line_widths",
        "set_gap",
        "set_diameter",
        "reset_diameter",
        "enable_auto_updates",
    ]

    def __init__(
        self,
        parent=None,
        config: RingProgressBarConfig | dict | None = None,
        client=None,
        gui_id: str | None = None,
        num_bars: int | None = None,
        **kwargs,
    ):
        if config is None:
            config = RingProgressBarConfig(widget_class=self.__class__.__name__)
            self.config = config
        else:
            if isinstance(config, dict):
                config = RingProgressBarConfig(**config, widget_class=self.__class__.__name__)
            self.config = config
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)

        self.get_bec_shortcuts()
        self.entry_validator = EntryValidator(self.dev)

        self.RID = None

        # For updating bar behaviour
        self._auto_updates = True
        self._rings = []

        if num_bars is not None:
            self.config.num_bars = max(
                self.config.min_number_of_bars, min(num_bars, self.config.max_number_of_bars)
            )
        self.initialize_bars()

        self.enable_auto_updates(self.config.auto_updates)

    @property
    def rings(self) -> list[Ring]:
        """Returns a list of all rings in the progress bar."""
        return self._rings

    @rings.setter
    def rings(self, value: list[Ring]):
        self._rings = value

    def update_config(self, config: RingProgressBarConfig | dict):
        """
        Update the configuration of the widget.

        Args:
            config(SpiralProgressBarConfig|dict): Configuration to update.
        """
        if isinstance(config, dict):
            config = RingProgressBarConfig(**config, widget_class=self.__class__.__name__)
        self.config = config
        self.clear_all()

    def initialize_bars(self):
        """
        Initialize the progress bars.
        """
        start_positions = [90 * 16] * self.config.num_bars
        directions = [-1] * self.config.num_bars

        self.config.rings = [
            RingConfig(
                widget_class="Ring",
                index=i,
                start_positions=start_positions[i],
                directions=directions[i],
            )
            for i in range(self.config.num_bars)
        ]
        self._rings = [Ring(parent=self, config=config) for config in self.config.rings]

        if self.config.color_map:
            self.set_colors_from_map(self.config.color_map)

        min_size = self._calculate_minimum_size()
        self.setMinimumSize(min_size)
        # Set outer ring to listen to scan progress
        self.rings[0].set_update(mode="scan")
        self.update()

    def add_ring(self, **kwargs) -> Ring:
        """
        Add a new progress bar.

        Args:
            **kwargs: Keyword arguments for the new progress bar.

        Returns:
            Ring: Ring object.
        """
        if self.config.num_bars < self.config.max_number_of_bars:
            ring_index = self.config.num_bars
            ring_config = RingConfig(
                widget_class="Ring",
                index=ring_index,
                start_positions=90 * 16,
                directions=-1,
                **kwargs,
            )
            ring = Ring(parent=self, config=ring_config)
            self.config.num_bars += 1
            self._rings.append(ring)
            self.config.rings.append(ring.config)
            if self.config.color_map:
                self.set_colors_from_map(self.config.color_map)
            base_line_width = self._rings[ring.config.index].config.line_width
            self.set_line_widths(base_line_width, ring.config.index)
            self.update()
            return ring

    def remove_ring(self, index: int):
        """
        Remove a progress bar by index.

        Args:
            index(int): Index of the progress bar to remove.
        """
        ring = self._find_ring_by_index(index)
        self._cleanup_ring(ring)
        self.update()

    def _cleanup_ring(self, ring: Ring) -> None:
        ring.reset_connection()
        self._rings.remove(ring)
        self.config.rings.remove(ring.config)
        self.config.num_bars -= 1
        self._reindex_rings()
        if self.config.color_map:
            self.set_colors_from_map(self.config.color_map)
        # Remove ring from rpc, afterwards call close event.
        ring.rpc_register.remove_rpc(ring)
        ring.deleteLater()
        # del ring

    def _reindex_rings(self):
        """
        Reindex the progress bars.
        """
        for i, ring in enumerate(self._rings):
            ring.config.index = i

    def set_precision(self, precision: int, bar_index: int = None):
        """
        Set the precision for the progress bars. If bar_index is not provide, the precision will be set for all progress bars.

        Args:
            precision(int): Precision for the progress bars.
            bar_index(int): Index of the progress bar to set the precision for. If provided, only a single precision can be set.
        """
        if bar_index is not None:
            bar_index = self._bar_index_check(bar_index)
            ring = self._find_ring_by_index(bar_index)
            ring.config.precision = precision
        else:
            for ring in self._rings:
                ring.config.precision = precision
        self.update()

    def set_min_max_values(
        self,
        min_values: int | float | list[int | float],
        max_values: int | float | list[int | float],
    ):
        """
        Set the minimum and maximum values for the progress bars.

        Args:
            min_values(int|float | list[float]): Minimum value(s) for the progress bars. If multiple progress bars are displayed, provide a list of minimum values for each progress bar.
            max_values(int|float | list[float]): Maximum value(s) for the progress bars. If multiple progress bars are displayed, provide a list of maximum values for each progress bar.
        """
        if isinstance(min_values, int) or isinstance(min_values, float):
            min_values = [min_values]
        if isinstance(max_values, int) or isinstance(max_values, float):
            max_values = [max_values]
        min_values = self._adjust_list_to_bars(min_values)
        max_values = self._adjust_list_to_bars(max_values)
        for ring, min_value, max_value in zip(self._rings, min_values, max_values):
            ring.set_min_max_values(min_value, max_value)
        self.update()

    def set_number_of_bars(self, num_bars: int):
        """
        Set the number of progress bars to display.

        Args:
            num_bars(int): Number of progress bars to display.
        """
        num_bars = max(
            self.config.min_number_of_bars, min(num_bars, self.config.max_number_of_bars)
        )
        current_num_bars = self.config.num_bars

        if num_bars > current_num_bars:
            for i in range(current_num_bars, num_bars):
                new_ring_config = RingConfig(
                    widget_class="Ring", index=i, start_positions=90 * 16, directions=-1
                )
                self.config.rings.append(new_ring_config)
                new_ring = Ring(parent=self, config=new_ring_config)
                self._rings.append(new_ring)

        elif num_bars < current_num_bars:
            for i in range(current_num_bars - 1, num_bars - 1, -1):
                self.remove_ring(i)

        self.config.num_bars = num_bars

        if self.config.color_map:
            self.set_colors_from_map(self.config.color_map)

        base_line_width = self._rings[0].config.line_width
        self.set_line_widths(base_line_width)

        self.update()

    def set_value(self, values: int | list, ring_index: int = None):
        """
        Set the values for the progress bars.

        Args:
            values(int | tuple): Value(s) for the progress bars. If multiple progress bars are displayed, provide a tuple of values for each progress bar.
            ring_index(int): Index of the progress bar to set the value for. If provided, only a single value can be set.

        Examples:
            >>> SpiralProgressBar.set_value(50)
            >>> SpiralProgressBar.set_value([30, 40, 50]) # (outer, middle, inner)
            >>> SpiralProgressBar.set_value(60, bar_index=1) # Set the value for the middle progress bar.
        """
        if ring_index is not None:
            ring = self._find_ring_by_index(ring_index)
            if isinstance(values, list):
                values = values[0]
                logger.warning(
                    f"Warning: Only a single value can be set for a single progress bar. Using the first value in the list {values}"
                )
            ring.set_value(values)
        else:
            if isinstance(values, int):
                values = [values]
                values = self._adjust_list_to_bars(values)
            for ring, value in zip(self._rings, values):
                ring.set_value(value)
        self.update()

    def set_colors_from_map(self, colormap, color_format: Literal["RGB", "HEX"] = "RGB"):
        """
        Set the colors for the progress bars from a colormap.

        Args:
            colormap(str): Name of the colormap.
            color_format(Literal["RGB","HEX"]): Format of the returned colors ('RGB', 'HEX').
        """
        if colormap not in pg.colormap.listMaps():
            raise ValueError(
                f"Colormap '{colormap}' not found in the current installation of pyqtgraph"
            )
        colors = Colors.golden_angle_color(colormap, self.config.num_bars, color_format)
        self.set_colors_directly(colors)
        self.config.color_map = colormap
        self.update()

    def set_colors_directly(self, colors: list[str | tuple] | str | tuple, bar_index: int = None):
        """
        Set the colors for the progress bars directly.

        Args:
            colors(list[str | tuple] | str | tuple): Color(s) for the progress bars. If multiple progress bars are displayed, provide a list of colors for each progress bar.
            bar_index(int): Index of the progress bar to set the color for. If provided, only a single color can be set.
        """
        if bar_index is not None and isinstance(colors, (str, tuple)):
            bar_index = self._bar_index_check(bar_index)
            ring = self._find_ring_by_index(bar_index)
            ring.set_color(colors)
        else:
            if isinstance(colors, (str, tuple)):
                colors = [colors]
            colors = self._adjust_list_to_bars(colors)
            for ring, color in zip(self._rings, colors):
                ring.set_color(color)
        self.update()

    def set_line_widths(self, widths: int | list[int], bar_index: int = None):
        """
        Set the line widths for the progress bars.

        Args:
            widths(int | list[int]): Line width(s) for the progress bars. If multiple progress bars are displayed, provide a list of line widths for each progress bar.
            bar_index(int): Index of the progress bar to set the line width for. If provided, only a single line width can be set.
        """
        if bar_index is not None:
            bar_index = self._bar_index_check(bar_index)
            ring = self._find_ring_by_index(bar_index)
            if isinstance(widths, list):
                widths = widths[0]
                logger.warning(
                    f"Warning: Only a single line width can be set for a single progress bar. Using the first value in the list {widths}"
                )
            ring.set_line_width(widths)
        else:
            if isinstance(widths, int):
                widths = [widths]
            widths = self._adjust_list_to_bars(widths)
            self.config.gap = max(widths) * 2
            for ring, width in zip(self._rings, widths):
                ring.set_line_width(width)
        min_size = self._calculate_minimum_size()
        self.setMinimumSize(min_size)
        self.update()

    def set_gap(self, gap: int):
        """
        Set the gap between the progress bars.

        Args:
            gap(int): Gap between the progress bars.
        """
        self.config.gap = gap
        self.update()

    def set_diameter(self, diameter: int):
        """
        Set the diameter of the widget.

        Args:
            diameter(int): Diameter of the widget.
        """
        size = QSize(diameter, diameter)
        self.resize(size)
        self.setFixedSize(size)

    def _find_ring_by_index(self, index: int) -> Ring:
        """
        Find the ring by index.

        Args:
            index(int): Index of the ring.

        Returns:
            Ring: Ring object.
        """
        found_ring = None
        for ring in self._rings:
            if ring.config.index == index:
                found_ring = ring
                break
        if found_ring is None:
            raise ValueError(f"Ring with index {index} not found.")
        return found_ring

    def enable_auto_updates(self, enable: bool = True):
        """
        Enable or disable updates based on scan status. Overrides manual updates.
        The behaviour of the whole progress bar widget will be driven by the scan queue status.

        Args:
            enable(bool): True or False.

        Returns:
            bool: True if scan segment updates are enabled.
        """

        self._auto_updates = enable
        if enable is True:
            self.bec_dispatcher.connect_slot(
                self.on_scan_queue_status, MessageEndpoints.scan_queue_status()
            )
        else:
            self.bec_dispatcher.disconnect_slot(
                self.on_scan_queue_status, MessageEndpoints.scan_queue_status()
            )
        return self._auto_updates

    @Slot(dict, dict)
    def on_scan_queue_status(self, msg, meta):
        """
        Slot to handle scan queue status messages. Decides what update to perform based on the scan queue status.

        Args:
            msg(dict): Message from the BEC.
            meta(dict): Metadata from the BEC.
        """
        primary_queue = msg.get("queue").get("primary")
        info = primary_queue.get("info", None)

        if info:
            active_request_block = info[0].get("active_request_block", None)
            if active_request_block:
                report_instructions = active_request_block.get("report_instructions", None)
                if report_instructions:
                    instruction_type = list(report_instructions[0].keys())[0]
                    if instruction_type == "scan_progress":
                        self._hook_scan_progress(ring_index=0)
                    elif instruction_type == "readback":
                        devices = report_instructions[0].get("readback").get("devices")
                        start = report_instructions[0].get("readback").get("start")
                        end = report_instructions[0].get("readback").get("end")
                        if self.config.num_bars != len(devices):
                            self.set_number_of_bars(len(devices))
                        for index, device in enumerate(devices):
                            self._hook_readback(index, device, start[index], end[index])
                    else:
                        logger.error(f"{instruction_type} not supported yet.")

                    # elif instruction_type == "device_progress":
                    #     print("hook device_progress")

    def _hook_scan_progress(self, ring_index: int = None):
        """
        Hook the scan progress to the progress bars.

        Args:
            ring_index(int): Index of the progress bar to hook the scan progress to.
        """
        if ring_index is not None:
            ring = self._find_ring_by_index(ring_index)
        else:
            ring = self._rings[0]

        if ring.config.connections.slot == "on_scan_progress":
            return
        else:
            ring.set_connections("on_scan_progress", MessageEndpoints.scan_progress())

    def _hook_readback(self, bar_index: int, device: str, min: float | int, max: float | int):
        """
        Hook the readback values to the progress bars.

        Args:
            bar_index(int): Index of the progress bar to hook the readback values to.
            device(str): Device to readback values from.
            min(float|int): Minimum value for the progress bar.
            max(float|int): Maximum value for the progress bar.
        """
        ring = self._find_ring_by_index(bar_index)
        ring.set_min_max_values(min, max)
        endpoint = MessageEndpoints.device_readback(device)
        ring.set_connections("on_device_readback", endpoint)

    def _adjust_list_to_bars(self, items: list) -> list:
        """
        Utility method to adjust the list of parameters to match the number of progress bars.

        Args:
            items(list): List of parameters for the progress bars.

        Returns:
            list: List of parameters for the progress bars.
        """
        if items is None:
            raise ValueError(
                "Items cannot be None. Please provide a list for parameters for the progress bars."
            )
        if not isinstance(items, list):
            items = [items]
        if len(items) < self.config.num_bars:
            last_item = items[-1]
            items.extend([last_item] * (self.config.num_bars - len(items)))
        elif len(items) > self.config.num_bars:
            items = items[: self.config.num_bars]
        return items

    def _bar_index_check(self, bar_index: int):
        """
        Utility method to check if the bar index is within the range of the number of progress bars.

        Args:
            bar_index(int): Index of the progress bar to set the value for.
        """
        if not (0 <= bar_index < self.config.num_bars):
            raise ValueError(
                f"bar_index {bar_index} out of range of number of bars {self.config.num_bars}."
            )
        return bar_index

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        size = min(self.width(), self.height())
        rect = QtCore.QRect(0, 0, size, size)
        rect.adjust(
            max(ring.config.line_width for ring in self._rings),
            max(ring.config.line_width for ring in self._rings),
            -max(ring.config.line_width for ring in self._rings),
            -max(ring.config.line_width for ring in self._rings),
        )

        for i, ring in enumerate(self._rings):
            # Background arc
            painter.setPen(
                QtGui.QPen(ring.background_color, ring.config.line_width, QtCore.Qt.SolidLine)
            )
            offset = self.config.gap * i
            adjusted_rect = QtCore.QRect(
                rect.left() + offset,
                rect.top() + offset,
                rect.width() - 2 * offset,
                rect.height() - 2 * offset,
            )
            painter.drawArc(adjusted_rect, ring.config.start_position, 360 * 16)

            # Foreground arc
            pen = QtGui.QPen(ring.color, ring.config.line_width, QtCore.Qt.SolidLine)
            pen.setCapStyle(QtCore.Qt.RoundCap)
            painter.setPen(pen)
            proportion = (ring.config.value - ring.config.min_value) / (
                (ring.config.max_value - ring.config.min_value) + 1e-3
            )
            angle = int(proportion * 360 * 16 * ring.config.direction)
            painter.drawArc(adjusted_rect, ring.start_position, angle)

    def reset_diameter(self):
        """
        Reset the fixed size of the widget.
        """
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setMinimumSize(self._calculate_minimum_size())
        self.setMaximumSize(16777215, 16777215)

    def _calculate_minimum_size(self):
        """
        Calculate the minimum size of the widget.
        """
        if not self.config.rings:
            logger.warning("no rings to get size from setting size to 10x10")
            return QSize(10, 10)
        ring_widths = [self.config.rings[i].line_width for i in range(self.config.num_bars)]
        total_width = sum(ring_widths) + self.config.gap * (self.config.num_bars - 1)
        diameter = total_width * 2
        if diameter < 50:
            diameter = 50
        return QSize(diameter, diameter)

    def sizeHint(self):
        min_size = self._calculate_minimum_size()
        return min_size

    def clear_all(self):
        for ring in self._rings:
            ring.reset_connection()
        self._rings.clear()
        self.update()
        self.initialize_bars()

    def cleanup(self):
        self.bec_dispatcher.disconnect_slot(
            self.on_scan_queue_status, MessageEndpoints.scan_queue_status()
        )
        for ring in self._rings:
            self._cleanup_ring(ring)
        self._rings.clear()
        super().cleanup()
