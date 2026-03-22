from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Literal

from bec_lib.endpoints import EndpointInfo, MessageEndpoints
from bec_lib.logger import bec_logger
from pydantic import Field
from qtpy import QtCore, QtGui
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_connector import BECConnector, ConnectionConfig
from bec_widgets.utils.colors import Colors
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot

logger = bec_logger.logger
if TYPE_CHECKING:
    from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_bar import (
        RingProgressContainerWidget,
    )


class ProgressbarConfig(ConnectionConfig):
    value: int | float = Field(0, description="Value for the progress bars.")
    direction: int = Field(
        -1, description="Direction of the progress bars. -1 for clockwise, 1 for counter-clockwise."
    )
    color: str | tuple = Field(
        (0, 159, 227, 255),
        description="Color for the progress bars. Can be tuple (R, G, B, A) or string HEX Code.",
    )
    background_color: str | tuple = Field(
        (200, 200, 200, 50),
        description="Background color for the progress bars. Can be tuple (R, G, B, A) or string HEX Code.",
    )
    link_colors: bool = Field(
        True,
        description="Whether to link the background color to the main color. If True, changing the main color will also change the background color.",
    )
    line_width: int = Field(20, description="Line widths for the progress bars.")
    start_position: int = Field(
        90,
        description="Start position for the progress bars in degrees. Default is 90 degrees - corespons to "
        "the top of the ring.",
    )
    min_value: int | float = Field(0, description="Minimum value for the progress bars.")
    max_value: int | float = Field(100, description="Maximum value for the progress bars.")
    precision: int = Field(3, description="Precision for the progress bars.")
    mode: Literal["manual", "scan", "device"] = Field(
        "manual", description="Update mode for the progress bars."
    )
    device: str | None = Field(
        None,
        description="Device name for the device readback mode, only used when mode is 'device'.",
    )
    signal: str | None = Field(
        None,
        description="Signal name for the device readback mode, only used when mode is 'device'.",
    )


class Ring(BECConnector, QWidget):
    USER_ACCESS = [
        "set_value",
        "set_color",
        "set_background",
        "set_colors_linked",
        "set_line_width",
        "set_min_max_values",
        "set_start_angle",
        "set_update",
        "set_precision",
    ]
    RPC = True

    def __init__(self, parent: RingProgressContainerWidget | None = None, client=None, **kwargs):
        self.progress_container = parent
        self.config: ProgressbarConfig = ProgressbarConfig(widget_class=self.__class__.__name__)  # type: ignore
        super().__init__(parent=parent, client=client, config=self.config, **kwargs)
        self._color: QColor = self.convert_color(self.config.color)
        self._background_color: QColor = self.convert_color(self.config.background_color)
        self.registered_slot: tuple[Callable, str | EndpointInfo] | None = None
        self.RID = None
        self._gap = 5
        self.set_start_angle(self.config.start_position)

    def set_value(self, value: int | float):
        """
        Set the value for the ring widget

        Args:
            value(int | float): Value for the ring widget
        """
        self.value = value

    def set_color(self, color: str | tuple):
        """
        Set the color for the ring widget

        Args:
            color(str | tuple): Color for the ring widget. Can be HEX code or tuple (R, G, B, A).
        """
        self._color = self.convert_color(color)
        self.config.color = self._color.name()

        # Automatically set background color
        if self.config.link_colors:
            self._auto_set_background_color()

        self.update()

    def set_background(self, color: str | tuple | QColor):
        """
        Set the background color for the ring widget. The background color is only used when colors are not linked.

        Args:
            color(str | tuple): Background color for the ring widget. Can be HEX code or tuple (R, G, B, A).
        """
        # Only allow manual background color changes when colors are not linked
        if self.config.link_colors:
            return

        self._background_color = self.convert_color(color)
        self.config.background_color = self._background_color.name()
        self.update()

    def _auto_set_background_color(self):
        """
        Automatically set the background color based on the main color and the current theme.
        """
        palette = self.palette()
        bg = palette.color(QtGui.QPalette.ColorRole.Window)
        bg_color = Colors.subtle_background_color(self._color, bg)
        self.config.background_color = bg_color.name()
        self._background_color = bg_color
        self.update()

    def set_colors_linked(self, linked: bool):
        """
        Set whether the colors are linked for the ring widget.
        If colors are linked, changing the main color will also change the background color.

        Args:
            linked(bool): Whether to link the colors for the ring widget
        """
        self.config.link_colors = linked
        if linked:
            self._auto_set_background_color()
        self.update()

    def set_line_width(self, width: int):
        """
        Set the line width for the ring widget

        Args:
            width(int): Line width for the ring widget
        """
        self.config.line_width = width
        self.update()

    def set_min_max_values(self, min_value: int | float, max_value: int | float):
        """
        Set the min and max values for the ring widget.

        Args:
            min_value(int | float): Minimum value for the ring widget
            max_value(int | float): Maximum value for the ring widget
        """
        self.config.min_value = min_value
        self.config.max_value = max_value
        self.update()

    def set_start_angle(self, start_angle: int):
        """
        Set the start angle for the ring widget.

        Args:
            start_angle(int): Start angle for the ring widget in degrees
        """
        self.config.start_position = start_angle
        self.update()

    def set_update(
        self, mode: Literal["manual", "scan", "device"], device: str = "", signal: str = ""
    ):
        """
        Set the update mode for the ring widget.
        Modes:
        - "manual": Manual update mode, the value is set by the user.
        - "scan": Update mode for the scan progress. The value is updated by the current scan progress.
        - "device": Update mode for the device readback. The value is updated by the device readback. Take into account that user has to set the device name and limits.

        Args:
            mode(str): Update mode for the ring widget. Can be "manual", "scan" or "device"
            device(str): Device name for the device readback mode, only used when mode is "device"
            signal(str): Signal name for the device readback mode, only used when mode is "device"
        """

        match mode:
            case "manual":
                if self.config.mode == "manual":
                    return
                if self.registered_slot is not None:
                    self.bec_dispatcher.disconnect_slot(*self.registered_slot)
                self.config.mode = "manual"
                self.registered_slot = None
            case "scan":
                if self.config.mode == "scan":
                    return
                if self.registered_slot is not None:
                    self.bec_dispatcher.disconnect_slot(*self.registered_slot)
                self.config.mode = "scan"
                self.bec_dispatcher.connect_slot(
                    self.on_scan_progress, MessageEndpoints.scan_progress()
                )
                self.registered_slot = (self.on_scan_progress, MessageEndpoints.scan_progress())
            case "device":
                if self.registered_slot is not None:
                    self.bec_dispatcher.disconnect_slot(*self.registered_slot)
                self.config.mode = "device"
                if device == "":
                    self.registered_slot = None
                    return
                self.config.device = device
                # self.config.signal = self._get_signal_from_device(device, signal)
                signal = self._update_device_connection(device, signal)
                self.config.signal = signal

            case _:
                raise ValueError(f"Unsupported mode: {mode}")

    def set_precision(self, precision: int):
        """
        Set the precision for the ring widget.

        Args:
            precision(int): Precision for the ring widget
        """
        self.config.precision = precision
        self.update()

    def set_direction(self, direction: int):
        """
        Set the direction for the ring widget.

        Args:
            direction(int): Direction for the ring widget. -1 for clockwise, 1 for counter-clockwise.
        """
        self.config.direction = direction
        self.update()

    def _get_signals_for_device(self, device: str) -> dict[str, list[str]]:
        """
        Get the signals for the device.

        Args:
            device(str): Device name for the device

        Returns:
            dict[str, list[str]]: Dictionary with the signals for the device
        """
        dm = self.bec_dispatcher.client.device_manager
        if not dm:
            raise ValueError("Device manager is not available in the BEC client.")
        dev_obj = dm.devices.get(device)
        if dev_obj is None:
            raise ValueError(f"Device '{device}' not found in device manager.")

        progress_signals = [
            obj["component_name"]
            for obj in dev_obj._info["signals"].values()
            if obj["signal_class"] == "ProgressSignal"
        ]
        hinted_signals = [
            obj["obj_name"]
            for obj in dev_obj._info["signals"].values()
            if obj["kind_str"] == "hinted"
            and obj["signal_class"]
            not in ["ProgressSignal", "AsyncSignal", "AsyncMultiSignal", "DynamicSignal"]
        ]

        normal_signals = [
            obj["component_name"]
            for obj in dev_obj._info["signals"].values()
            if obj["kind_str"] == "normal"
        ]
        return {
            "progress_signals": progress_signals,
            "hinted_signals": hinted_signals,
            "normal_signals": normal_signals,
        }

    def _update_device_connection(self, device: str, signal: str | None) -> str:
        """
        Update the device connection for the ring widget.

        In general, we support two modes here:
        - If signal is provided, we use that directly.
        - If signal is not provided, we try to get the signal from the device manager.
          We first check for progress signals, then for hinted signals, and finally for normal signals.

        Depending on what type of signal we get (progress or hinted/normal), we subscribe to different endpoints.

        Args:
            device(str): Device name for the device mode
            signal(str): Signal name for the device mode

        Returns:
            str: The selected signal name for the device mode
        """
        logger.info(f"Updating device connection for device '{device}' and signal '{signal}'")
        dm = self.bec_dispatcher.client.device_manager
        if not dm:
            raise ValueError("Device manager is not available in the BEC client.")
        dev_obj = dm.devices.get(device)
        if dev_obj is None:
            return ""

        signals = self._get_signals_for_device(device)
        progress_signals = signals["progress_signals"]
        hinted_signals = signals["hinted_signals"]
        normal_signals = signals["normal_signals"]

        if not signal:
            # If signal is not provided, we try to get it from the device manager
            if len(progress_signals) > 0:
                signal = progress_signals[0]
                logger.info(
                    f"Using progress signal '{signal}' for device '{device}' in ring progress bar."
                )
            elif len(hinted_signals) > 0:
                signal = hinted_signals[0]
                logger.info(
                    f"Using hinted signal '{signal}' for device '{device}' in ring progress bar."
                )
            elif len(normal_signals) > 0:
                signal = normal_signals[0]
                logger.info(
                    f"Using normal signal '{signal}' for device '{device}' in ring progress bar."
                )
            else:
                logger.warning(f"No signals found for device '{device}' in ring progress bar.")
                return ""

        if signal in progress_signals:
            endpoint = MessageEndpoints.device_progress(device)
            self.bec_dispatcher.connect_slot(self.on_device_progress, endpoint)
            self.registered_slot = (self.on_device_progress, endpoint)
            return signal
        if signal in hinted_signals or signal in normal_signals:
            endpoint = MessageEndpoints.device_readback(device)
            self.bec_dispatcher.connect_slot(self.on_device_readback, endpoint)
            self.registered_slot = (self.on_device_readback, endpoint)
            return signal

    @SafeSlot(dict, dict)
    def on_scan_progress(self, msg, meta):
        """
        Update the ring widget with the scan progress.

        Args:
            msg(dict): Message with the scan progress
            meta(dict): Metadata for the message
        """
        current_RID = meta.get("RID", None)
        if current_RID != self.RID:
            self.set_min_max_values(0, msg.get("max_value", 100))
        self.set_value(msg.get("value", 0))
        self.update()

    @SafeSlot(dict, dict)
    def on_device_readback(self, msg, meta):
        """
        Update the ring widget with the device readback.

        Args:
            msg(dict): Message with the device readback
            meta(dict): Metadata for the message
        """
        device = self.config.device
        if device is None:
            return
        signal = self.config.signal or device
        value = msg.get("signals", {}).get(signal, {}).get("value", None)
        if value is None:
            return
        self.set_value(value)
        self.update()

    @SafeSlot(dict, dict)
    def on_device_progress(self, msg, meta):
        """
        Update the ring widget with the device progress.

        Args:
            msg(dict): Message with the device progress
            meta(dict): Metadata for the message
        """
        device = self.config.device
        if device is None:
            return
        max_val = msg.get("max_value", 100)
        self.set_min_max_values(0, max_val)
        value = msg.get("value", 0)
        if msg.get("done"):
            value = max_val
        self.set_value(value)
        self.update()

    def paintEvent(self, event):
        if not self.progress_container:
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        size = min(self.width(), self.height())

        # Center the ring
        x_offset = (self.width() - size) // 2
        y_offset = (self.height() - size) // 2

        max_ring_size = self.progress_container.get_max_ring_size()

        rect = QtCore.QRect(x_offset, y_offset, size, size)
        rect.adjust(max_ring_size, max_ring_size, -max_ring_size, -max_ring_size)

        # Background arc
        painter.setPen(
            QtGui.QPen(self._background_color, self.config.line_width, QtCore.Qt.PenStyle.SolidLine)
        )

        gap: int = self.gap  # type: ignore

        # Important: Qt uses a 16th of a degree for angles. start_position is therefore multiplied by 16.
        start_position: float = self.config.start_position * 16  # type: ignore

        adjusted_rect = QtCore.QRect(
            rect.left() + gap, rect.top() + gap, rect.width() - 2 * gap, rect.height() - 2 * gap
        )
        painter.drawArc(adjusted_rect, start_position, 360 * 16)

        # Foreground arc
        pen = QtGui.QPen(self.color, self.config.line_width, QtCore.Qt.PenStyle.SolidLine)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        proportion = (self.config.value - self.config.min_value) / (
            (self.config.max_value - self.config.min_value) + 1e-3
        )
        angle = int(proportion * 360 * 16 * self.config.direction)
        painter.drawArc(adjusted_rect, start_position, angle)
        painter.end()

    def convert_color(self, color: str | tuple | QColor) -> QColor:
        """
        Convert the color to QColor

        Args:
            color(str | tuple | QColor): Color for the ring widget. Can be HEX code or tuple (R, G, B, A) or QColor.
        """

        if isinstance(color, QColor):
            return color
        if isinstance(color, str):
            return QtGui.QColor(color)
        if isinstance(color, (tuple, list)):
            return QtGui.QColor(*color)
        raise ValueError(f"Unsupported color format: {color}")

    def cleanup(self):
        """
        Cleanup the ring widget.
        Disconnect any registered slots.
        """
        if self.registered_slot is not None:
            self.bec_dispatcher.disconnect_slot(*self.registered_slot)
            self.registered_slot = None

    ###############################################
    ####### QProperties ###########################
    ###############################################

    @SafeProperty(int)
    def gap(self) -> int:
        return self._gap

    @gap.setter
    def gap(self, value: int):
        self._gap = value
        self.update()

    @SafeProperty(bool)
    def link_colors(self) -> bool:
        return self.config.link_colors

    @link_colors.setter
    def link_colors(self, value: bool):
        logger.info(f"Setting link_colors to {value}")
        self.set_colors_linked(value)

    @SafeProperty(QColor)
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, value: QColor):
        self.set_color(value)

    @SafeProperty(QColor)
    def background_color(self) -> QColor:
        return self._background_color

    @background_color.setter
    def background_color(self, value: QColor):
        self.set_background(value)

    @SafeProperty(float)
    def value(self) -> float:
        return self.config.value

    @value.setter
    def value(self, value: float):
        self.config.value = round(
            float(max(self.config.min_value, min(self.config.max_value, value))),
            self.config.precision,
        )
        self.update()

    @SafeProperty(float)
    def min_value(self) -> float:
        return self.config.min_value

    @min_value.setter
    def min_value(self, value: float):
        self.config.min_value = value
        self.update()

    @SafeProperty(float)
    def max_value(self) -> float:
        return self.config.max_value

    @max_value.setter
    def max_value(self, value: float):
        self.config.max_value = value
        self.update()

    @SafeProperty(str)
    def mode(self) -> str:
        return self.config.mode

    @mode.setter
    def mode(self, value: str):
        self.set_update(value)

    @SafeProperty(str)
    def device(self) -> str:
        return self.config.device or ""

    @device.setter
    def device(self, value: str):
        self.config.device = value

    @SafeProperty(str)
    def signal(self) -> str:
        return self.config.signal or ""

    @signal.setter
    def signal(self, value: str):
        self.config.signal = value

    @SafeProperty(int)
    def line_width(self) -> int:
        return self.config.line_width

    @line_width.setter
    def line_width(self, value: int):
        self.config.line_width = value
        self.update()

    @SafeProperty(int)
    def start_position(self) -> int:
        return self.config.start_position

    @start_position.setter
    def start_position(self, value: int):
        self.config.start_position = value
        self.update()

    @SafeProperty(int)
    def precision(self) -> int:
        return self.config.precision

    @precision.setter
    def precision(self, value: int):
        self.config.precision = value
        self.update()

    @SafeProperty(int)
    def direction(self) -> int:
        return self.config.direction

    @direction.setter
    def direction(self, value: int):
        self.config.direction = value
        self.update()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    ring = Ring()
    ring.export_settings()
    ring.show()
    sys.exit(app.exec())
