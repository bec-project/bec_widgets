from __future__ import annotations

from collections import defaultdict
from typing import Literal

import numpy as np
from bec_lib import bec_logger
from bec_lib.endpoints import MessageEndpoints
from pydantic import BaseModel, Field, field_validator
from qtpy.QtWidgets import QWidget

from bec_widgets.utils import ConnectionConfig
from bec_widgets.utils.colors import Colors
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.plots.image.image_base import ImageBase
from bec_widgets.widgets.plots.image.image_item import ImageItem

logger = bec_logger.logger


# noinspection PyDataclass
class ImageConfig(ConnectionConfig):
    color_map: str = Field(
        "plasma", description="The colormap  of the figure widget.", validate_default=True
    )
    color_bar: Literal["full", "simple"] | None = Field(
        None, description="The type of the color bar."
    )
    lock_aspect_ratio: bool = Field(
        False, description="Whether to lock the aspect ratio of the image."
    )

    model_config: dict = {"validate_assignment": True}
    _validate_color_map = field_validator("color_map")(Colors.validate_color_map)


class ImageLayerConfig(BaseModel):
    monitor: str | tuple | None = Field(None, description="The name of the monitor.")
    monitor_type: Literal["1d", "2d", "auto"] = Field("auto", description="The type of monitor.")
    source: Literal["device_monitor_1d", "device_monitor_2d", "auto"] = Field(
        "auto", description="The source of the image data."
    )


class Image(ImageBase):
    """
    Image widget for displaying 2D data.
    """

    PLUGIN = True
    RPC = True
    ICON_NAME = "image"
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
        "auto_range_x",
        "auto_range_x.setter",
        "auto_range_y",
        "auto_range_y.setter",
        "minimal_crosshair_precision",
        "minimal_crosshair_precision.setter",
        # ImageView Specific Settings
        "color_map",
        "color_map.setter",
        "v_range",
        "v_range.setter",
        "v_min",
        "v_min.setter",
        "v_max",
        "v_max.setter",
        "lock_aspect_ratio",
        "lock_aspect_ratio.setter",
        "autorange",
        "autorange.setter",
        "autorange_mode",
        "autorange_mode.setter",
        "monitor",
        "monitor.setter",
        "enable_colorbar",
        "enable_simple_colorbar",
        "enable_simple_colorbar.setter",
        "enable_full_colorbar",
        "enable_full_colorbar.setter",
        "fft",
        "fft.setter",
        "log",
        "log.setter",
        "num_rotation_90",
        "num_rotation_90.setter",
        "transpose",
        "transpose.setter",
        "image",
        "main_image",
        "add_roi",
        "remove_roi",
        "rois",
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        config: ImageConfig | None = None,
        client=None,
        gui_id: str | None = None,
        popups: bool = True,
        **kwargs,
    ):
        if config is None:
            config = ImageConfig(widget_class=self.__class__.__name__)
        self.gui_id = config.gui_id
        self._color_bar = None
        self.subscriptions: defaultdict[str, ImageLayerConfig] = defaultdict(
            lambda: ImageLayerConfig(monitor=None, monitor_type="auto", source="auto")
        )
        super().__init__(
            parent=parent, config=config, client=client, gui_id=gui_id, popups=popups, **kwargs
        )
        self.layer_removed.connect(self._on_layer_removed)
        self.scan_id = None

    ################################################################################
    # Data Acquisition

    @SafeProperty(str)
    def monitor(self) -> str:
        """
        The name of the monitor to use for the image.
        """
        return self.subscriptions["main"].monitor or ""

    @monitor.setter
    def monitor(self, value: str):
        """
        Set the monitor for the image.

        Args:
            value(str): The name of the monitor to set.
        """
        if self.subscriptions["main"].monitor == value:
            return
        try:
            self.entry_validator.validate_monitor(value)
        except ValueError:
            return
        self.image(monitor=value)

    @property
    def main_image(self) -> ImageItem:
        """Access the main image item."""
        return self.layer_manager["main"].image

    ################################################################################
    # High Level methods for API
    ################################################################################
    @SafeSlot(popup_error=True)
    def image(
        self,
        monitor: str | tuple | None = None,
        monitor_type: Literal["auto", "1d", "2d"] = "auto",
        color_map: str | None = None,
        color_bar: Literal["simple", "full"] | None = None,
        vrange: tuple[int, int] | None = None,
    ) -> ImageItem | None:
        """
        Set the image source and update the image.

        Args:
            monitor(str): The name of the monitor to use for the image.
            monitor_type(str): The type of monitor to use. Options are "1d", "2d", or "auto".
            color_map(str): The color map to use for the image.
            color_bar(str): The type of color bar to use. Options are "simple" or "full".
            vrange(tuple): The range of values to use for the color map.

        Returns:
            ImageItem: The image object.
        """

        if self.subscriptions["main"].monitor:
            self.disconnect_monitor(self.subscriptions["main"].monitor)
        if monitor is None or monitor == "":
            logger.warning(f"No monitor specified, cannot set image, old monitor is unsubscribed")
            return None
        if isinstance(monitor, tuple):
            self.entry_validator.validate_monitor(monitor[0])
        else:
            self.entry_validator.validate_monitor(monitor)

        self.set_image_update(monitor=monitor, type=monitor_type)
        if color_map is not None:
            self.main_image.color_map = color_map
        if color_bar is not None:
            self.enable_colorbar(True, color_bar)
        if vrange is not None:
            self.vrange = vrange

        self._sync_device_selection()

        return self.main_image

    def _sync_device_selection(self):
        """
        Synchronize the device selection with the current monitor.
        """
        config = self.subscriptions["main"]
        if config.monitor is not None:
            for combo in (
                self.selection_bundle.device_combo_box,
                self.selection_bundle.dim_combo_box,
            ):
                combo.blockSignals(True)
            if isinstance(config.monitor, tuple):
                self.selection_bundle.device_combo_box.setCurrentText(
                    f"{config.monitor[0]}_{config.monitor[1]}"
                )
            else:
                self.selection_bundle.device_combo_box.setCurrentText(config.monitor)
            self.selection_bundle.dim_combo_box.setCurrentText(config.monitor_type)
            for combo in (
                self.selection_bundle.device_combo_box,
                self.selection_bundle.dim_combo_box,
            ):
                combo.blockSignals(False)
        else:
            for combo in (
                self.selection_bundle.device_combo_box,
                self.selection_bundle.dim_combo_box,
            ):
                combo.blockSignals(True)
            self.selection_bundle.device_combo_box.setCurrentText("")
            self.selection_bundle.dim_combo_box.setCurrentText("auto")
            for combo in (
                self.selection_bundle.device_combo_box,
                self.selection_bundle.dim_combo_box,
            ):
                combo.blockSignals(False)

    ################################################################################
    # Post Processing
    ################################################################################

    @SafeProperty(bool)
    def fft(self) -> bool:
        """
        Whether FFT postprocessing is enabled.
        """
        return self.main_image.fft

    @fft.setter
    def fft(self, enable: bool):
        """
        Set FFT postprocessing.

        Args:
            enable(bool): Whether to enable FFT postprocessing.
        """
        self.main_image.fft = enable

    @SafeProperty(bool)
    def log(self) -> bool:
        """
        Whether logarithmic scaling is applied.
        """
        return self.main_image.log

    @log.setter
    def log(self, enable: bool):
        """
        Set logarithmic scaling.

        Args:
            enable(bool): Whether to enable logarithmic scaling.
        """
        self.main_image.log = enable

    @SafeProperty(int)
    def num_rotation_90(self) -> int:
        """
        The number of 90° rotations to apply counterclockwise.
        """
        return self.main_image.num_rotation_90

    @num_rotation_90.setter
    def num_rotation_90(self, value: int):
        """
        Set the number of 90° rotations to apply counterclockwise.

        Args:
            value(int): The number of 90° rotations to apply.
        """
        self.main_image.num_rotation_90 = value

    @SafeProperty(bool)
    def transpose(self) -> bool:
        """
        Whether the image is transposed.
        """
        return self.main_image.transpose

    @transpose.setter
    def transpose(self, enable: bool):
        """
        Set the image to be transposed.

        Args:
            enable(bool): Whether to enable transposing the image.
        """
        self.main_image.transpose = enable

    ################################################################################
    # Image Update Methods
    ################################################################################

    ########################################
    # Connections

    @SafeSlot()
    def set_image_update(self, monitor: str | tuple, type: Literal["1d", "2d", "auto"]):
        """
        Set the image update method for the given monitor.

        Args:
            monitor(str): The name of the monitor to use for the image.
            type(str): The type of monitor to use. Options are "1d", "2d", or "auto".
        """

        # TODO consider moving connecting and disconnecting logic to Image itself if multiple images
        if isinstance(monitor, tuple):
            device = self.dev[monitor[0]]
            signal = monitor[1]
            if len(monitor) == 3:
                signal_config = monitor[2]
            else:
                signal_config = device._info["signals"][signal]
            signal_class = signal_config.get("signal_class", None)
            if signal_class != "PreviewSignal":
                logger.warning(f"Signal '{monitor}' is not a PreviewSignal.")
                return

            ndim = signal_config.get("describe", None).get("signal_info", None).get("ndim", None)
            if ndim is None:
                logger.warning(
                    f"Signal '{monitor}' does not have a valid 'ndim' in its signal_info."
                )
                return

            if ndim == 1:
                self.bec_dispatcher.connect_slot(
                    self.on_image_update_1d, MessageEndpoints.device_preview(device.name, signal)
                )
                self.subscriptions["main"].source = "device_monitor_1d"
                self.subscriptions["main"].monitor_type = "1d"
            elif ndim == 2:
                self.bec_dispatcher.connect_slot(
                    self.on_image_update_2d, MessageEndpoints.device_preview(device.name, signal)
                )
                self.subscriptions["main"].source = "device_monitor_2d"
                self.subscriptions["main"].monitor_type = "2d"

        else:  # FIXME old monitor 1d/2d endpoint handling, present for backwards compatibility, will be removed in future versions
            if type == "1d":
                self.bec_dispatcher.connect_slot(
                    self.on_image_update_1d, MessageEndpoints.device_monitor_1d(monitor)
                )
                self.subscriptions["main"].source = "device_monitor_1d"
                self.subscriptions["main"].monitor_type = "1d"
            elif type == "2d":
                self.bec_dispatcher.connect_slot(
                    self.on_image_update_2d, MessageEndpoints.device_monitor_2d(monitor)
                )
                self.subscriptions["main"].source = "device_monitor_2d"
                self.subscriptions["main"].monitor_type = "2d"
            elif type == "auto":
                self.bec_dispatcher.connect_slot(
                    self.on_image_update_1d, MessageEndpoints.device_monitor_1d(monitor)
                )
                self.bec_dispatcher.connect_slot(
                    self.on_image_update_2d, MessageEndpoints.device_monitor_2d(monitor)
                )
                self.subscriptions["main"].source = "auto"
                logger.warning(
                    f"Updates for '{monitor}' will be fetch from both 1D and 2D monitor endpoints."
                )
                self.subscriptions["main"].monitor_type = "auto"

        logger.info(f"Connected to {monitor} with type {type}")
        self.subscriptions["main"].monitor = monitor

    def disconnect_monitor(self, monitor: str | tuple):
        """
        Disconnect the monitor from the image update signals, both 1D and 2D.

        Args:
            monitor(str|tuple): The name of the monitor to disconnect, or a tuple of (device, signal) for preview signals.
        """
        if isinstance(monitor, tuple):
            if self.subscriptions["main"].source == "device_monitor_1d":
                self.bec_dispatcher.disconnect_slot(
                    self.on_image_update_1d, MessageEndpoints.device_preview(monitor[0], monitor[1])
                )
            elif self.subscriptions["main"].source == "device_monitor_2d":
                self.bec_dispatcher.disconnect_slot(
                    self.on_image_update_2d, MessageEndpoints.device_preview(monitor[0], monitor[1])
                )
            else:
                logger.warning(
                    f"Cannot disconnect monitor {monitor} with source {self.subscriptions['main'].source}"
                )
                return
        else:  # FIXME old monitor 1d/2d endpoint handling, present for backwards compatibility, will be removed in future versions
            self.bec_dispatcher.disconnect_slot(
                self.on_image_update_1d, MessageEndpoints.device_monitor_1d(monitor)
            )
            self.bec_dispatcher.disconnect_slot(
                self.on_image_update_2d, MessageEndpoints.device_monitor_2d(monitor)
            )
        self.subscriptions["main"].monitor = None
        self._sync_device_selection()

    ########################################
    # 1D updates

    @SafeSlot(dict, dict)
    def on_image_update_1d(self, msg: dict, metadata: dict):
        """
        Update the image with 1D data.

        Args:
            msg(dict): The message containing the data.
            metadata(dict): The metadata associated with the message.
        """
        data = msg["data"]
        current_scan_id = metadata.get("scan_id", None)

        if current_scan_id is None:
            return
        if current_scan_id != self.scan_id:
            self.scan_id = current_scan_id
            self.main_image.clear()
            self.main_image.buffer = []
            self.main_image.max_len = 0
        image_buffer = self.adjust_image_buffer(self.main_image, data)
        if self._color_bar is not None:
            self._color_bar.blockSignals(True)
        self.main_image.set_data(image_buffer)
        if self._color_bar is not None:
            self._color_bar.blockSignals(False)
        self.image_updated.emit()

    def adjust_image_buffer(self, image: ImageItem, new_data: np.ndarray) -> np.ndarray:
        """
        Adjusts the image buffer to accommodate the new data, ensuring that all rows have the same length.

        Args:
            image: The image object (used to store a buffer list and max_len).
            new_data (np.ndarray): The new incoming 1D waveform data.

        Returns:
            np.ndarray: The updated image buffer with adjusted shapes.
        """
        new_len = new_data.shape[0]
        if not hasattr(image, "buffer"):
            image.buffer = []
            image.max_len = 0

        if new_len > image.max_len:
            image.max_len = new_len
            for i in range(len(image.buffer)):
                wf = image.buffer[i]
                pad_width = image.max_len - wf.shape[0]
                if pad_width > 0:
                    image.buffer[i] = np.pad(wf, (0, pad_width), mode="constant", constant_values=0)
            image.buffer.append(new_data)
        else:
            pad_width = image.max_len - new_len
            if pad_width > 0:
                new_data = np.pad(new_data, (0, pad_width), mode="constant", constant_values=0)
            image.buffer.append(new_data)

        image_buffer = np.array(image.buffer)
        return image_buffer

    ########################################
    # 2D updates

    def on_image_update_2d(self, msg: dict, metadata: dict):
        """
        Update the image with 2D data.

        Args:
            msg(dict): The message containing the data.
            metadata(dict): The metadata associated with the message.
        """
        data = msg["data"]
        if self._color_bar is not None:
            self._color_bar.blockSignals(True)
        self.main_image.set_data(data)
        if self._color_bar is not None:
            self._color_bar.blockSignals(False)
        self.image_updated.emit()

    ################################################################################
    # Clean up
    ################################################################################

    @SafeSlot(str)
    def _on_layer_removed(self, layer_name: str):
        """
        Handle the removal of a layer by disconnecting the monitor.

        Args:
            layer_name(str): The name of the layer that was removed.
        """
        if layer_name not in self.subscriptions:
            return
        config = self.subscriptions[layer_name]
        if config.monitor is not None:
            self.disconnect_monitor(config.monitor)
            config.monitor = None

    def cleanup(self):
        """
        Disconnect the image update signals and clean up the image.
        """
        self.layer_removed.disconnect(self._on_layer_removed)
        for layer_name in list(self.subscriptions.keys()):
            config = self.subscriptions[layer_name]
            if config.monitor is not None:
                self.disconnect_monitor(config.monitor)
            del self.subscriptions[layer_name]
        self.subscriptions.clear()

        # Toolbar cleanup
        self.toolbar.widgets["monitor"].widget.close()
        self.toolbar.widgets["monitor"].widget.deleteLater()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication, QHBoxLayout

    app = QApplication(sys.argv)
    win = QWidget()
    win.setWindowTitle("Image Demo")
    ml = QHBoxLayout(win)

    image_popup = Image(popups=True)
    image_side_panel = Image(popups=False)

    ml.addWidget(image_popup)
    ml.addWidget(image_side_panel)

    win.resize(1500, 800)
    win.show()
    sys.exit(app.exec_())
