from __future__ import annotations

import json
from typing import Literal

import numpy as np
import pyqtgraph as pg
from bec_lib import bec_logger, messages
from bec_lib.endpoints import MessageEndpoints
from pydantic import BaseModel, Field, field_validator
from qtpy.QtCore import QTimer, Signal
from qtpy.QtGui import QTransform
from scipy.interpolate import (
    CloughTocher2DInterpolator,
    LinearNDInterpolator,
    NearestNDInterpolator,
)
from scipy.spatial import cKDTree
from toolz import partition

from bec_widgets.utils import Colors
from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.settings_dialog import SettingsDialog
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.widgets.plots.heatmap.settings.heatmap_setting import HeatmapSettings
from bec_widgets.widgets.plots.image.image_base import ImageBase
from bec_widgets.widgets.plots.image.image_item import ImageItem

logger = bec_logger.logger


class HeatmapDeviceSignal(BaseModel):
    """The configuration of a signal in the scatter waveform widget."""

    name: str
    entry: str

    model_config: dict = {"validate_assignment": True}


class HeatmapConfig(ConnectionConfig):
    parent_id: str | None = Field(None, description="The parent plot of the curve.")
    color_map: str | None = Field(
        "plasma", description="The color palette of the heatmap widget.", validate_default=True
    )
    color_bar: Literal["full", "simple"] | None = Field(
        None, description="The type of the color bar."
    )
    interpolation: Literal["linear", "nearest", "clough"] = Field(
        "linear", description="The interpolation method for the heatmap."
    )
    oversampling_factor: float = Field(
        1.0,
        description="Factor to oversample the grid resolution (1.0 = no oversampling, 2.0 = 2x resolution).",
    )
    show_config_label: bool = Field(
        True, description="Whether to show the configuration label in the heatmap."
    )
    enforce_interpolation: bool = Field(
        False, description="Whether to use the interpolation mode even for grid scans."
    )
    lock_aspect_ratio: bool = Field(
        False, description="Whether to lock the aspect ratio of the image."
    )
    x_device: HeatmapDeviceSignal | None = Field(
        None, description="The x device signal of the heatmap."
    )
    y_device: HeatmapDeviceSignal | None = Field(
        None, description="The y device signal of the heatmap."
    )
    z_device: HeatmapDeviceSignal | None = Field(
        None, description="The z device signal of the heatmap."
    )

    model_config: dict = {"validate_assignment": True}
    _validate_color_palette = field_validator("color_map")(Colors.validate_color_map)


class Heatmap(ImageBase):
    """
    Heatmap widget for visualizing 2d grid data with color mapping for the z-axis.
    """

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
        "enable_colorbar",
        "enable_simple_colorbar",
        "enable_simple_colorbar.setter",
        "enable_full_colorbar",
        "enable_full_colorbar.setter",
        "interpolation_method",
        "interpolation_method.setter",
        "oversampling_factor",
        "oversampling_factor.setter",
        "enforce_interpolation",
        "enforce_interpolation.setter",
        "fft",
        "fft.setter",
        "log",
        "log.setter",
        "main_image",
        "add_roi",
        "remove_roi",
        "rois",
        "plot",
    ]

    PLUGIN = True
    RPC = True
    ICON_NAME = "dataset"

    new_scan = Signal()
    new_scan_id = Signal(str)
    sync_signal_update = Signal()
    heatmap_property_changed = Signal()

    def __init__(self, parent=None, config: HeatmapConfig | None = None, **kwargs):
        if config is None:
            config = HeatmapConfig(
                widget_class=self.__class__.__name__,
                parent_id=None,
                color_map="plasma",
                color_bar=None,
                interpolation="linear",
                oversampling_factor=1.0,
                lock_aspect_ratio=False,
                x_device=None,
                y_device=None,
                z_device=None,
            )
        super().__init__(parent=parent, config=config, theme_update=True, **kwargs)
        self._image_config = config
        self.scan_id = None
        self.old_scan_id = None
        self.scan_item = None
        self.status_message = None
        self._grid_index = None
        self.heatmap_dialog = None
        bg_color = pg.mkColor((240, 240, 240, 150))
        self.config_label = pg.LegendItem(
            labelTextColor=(0, 0, 0), offset=(-30, 1), brush=pg.mkBrush(bg_color), horSpacing=0
        )
        self.config_label.setParentItem(self.plot_item.vb)
        self.config_label.setVisible(False)
        self.reload = False
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.bec_dispatcher.connect_slot(self.on_scan_progress, MessageEndpoints.scan_progress())
        self.heatmap_property_changed.connect(lambda: self.sync_signal_update.emit())

        self.proxy_update_sync = pg.SignalProxy(
            self.sync_signal_update, rateLimit=5, slot=self.update_plot
        )
        self._init_toolbar_heatmap()
        self.toolbar.show_bundles(
            [
                "heatmap_settings",
                "plot_export",
                "image_crosshair",
                "mouse_interaction",
                "image_autorange",
                "image_colorbar",
                "image_processing",
                "axis_popup",
                "interpolation_info",
            ]
        )

    @property
    def main_image(self) -> ImageItem:
        """Access the main image item."""
        return self.layer_manager["main"].image

    ################################################################################
    # Widget Specific GUI interactions
    ################################################################################

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        """
        Apply the current theme to the heatmap widget.
        """
        super().apply_theme(theme)
        if theme == "dark":
            brush = pg.mkBrush(pg.mkColor(50, 50, 50, 150))
            color = pg.mkColor(255, 255, 255)
        else:
            brush = pg.mkBrush(pg.mkColor(240, 240, 240, 150))
            color = pg.mkColor(0, 0, 0)
        if hasattr(self, "config_label"):
            self.config_label.setBrush(brush)
            self.config_label.setLabelTextColor(color)
            self.redraw_config_label()

    @SafeSlot(popup_error=True)
    def plot(
        self,
        x_name: str,
        y_name: str,
        z_name: str,
        x_entry: None | str = None,
        y_entry: None | str = None,
        z_entry: None | str = None,
        color_map: str | None = "plasma",
        validate_bec: bool = True,
        interpolation: Literal["linear", "nearest"] | None = None,
        enforce_interpolation: bool | None = None,
        oversampling_factor: float | None = None,
        lock_aspect_ratio: bool | None = None,
        show_config_label: bool | None = None,
        reload: bool = False,
    ):
        """
        Plot the heatmap with the given x, y, and z data.

        Args:
            x_name (str): The name of the x-axis signal.
            y_name (str): The name of the y-axis signal.
            z_name (str): The name of the z-axis signal.
            x_entry (str | None): The entry for the x-axis signal.
            y_entry (str | None): The entry for the y-axis signal.
            z_entry (str | None): The entry for the z-axis signal.
            color_map (str | None): The color map to use for the heatmap.
            validate_bec (bool): Whether to validate the entries against BEC signals.
            interpolation (Literal["linear", "nearest"] | None): The interpolation method to use.
            enforce_interpolation (bool | None): Whether to enforce interpolation even for grid scans.
            oversampling_factor (float | None): Factor to oversample the grid resolution.
            lock_aspect_ratio (bool | None): Whether to lock the aspect ratio of the image.
            show_config_label (bool | None): Whether to show the configuration label in the heatmap.
            reload (bool): Whether to reload the heatmap with new data.
        """
        if validate_bec:
            x_entry = self.entry_validator.validate_signal(x_name, x_entry)
            y_entry = self.entry_validator.validate_signal(y_name, y_entry)
            z_entry = self.entry_validator.validate_signal(z_name, z_entry)

        if x_entry is None or y_entry is None or z_entry is None:
            raise ValueError("x, y, and z entries must be provided.")
        if x_name is None or y_name is None or z_name is None:
            raise ValueError("x, y, and z names must be provided.")

        if interpolation is None:
            interpolation = self._image_config.interpolation

        if oversampling_factor is None:
            oversampling_factor = self._image_config.oversampling_factor

        if enforce_interpolation is None:
            enforce_interpolation = self._image_config.enforce_interpolation

        if lock_aspect_ratio is None:
            lock_aspect_ratio = self._image_config.lock_aspect_ratio

        if show_config_label is None:
            show_config_label = self._image_config.show_config_label

        self._image_config = HeatmapConfig(
            parent_id=self.gui_id,
            x_device=HeatmapDeviceSignal(name=x_name, entry=x_entry),
            y_device=HeatmapDeviceSignal(name=y_name, entry=y_entry),
            z_device=HeatmapDeviceSignal(name=z_name, entry=z_entry),
            color_map=color_map,
            color_bar=None,
            interpolation=interpolation,
            oversampling_factor=oversampling_factor,
            enforce_interpolation=enforce_interpolation,
            lock_aspect_ratio=lock_aspect_ratio,
            show_config_label=show_config_label,
        )
        self.color_map = color_map
        self.reload = reload
        self.update_labels()

        self._fetch_running_scan()
        self.sync_signal_update.emit()

    def _fetch_running_scan(self):
        scan = self.client.queue.scan_storage.current_scan
        if scan is not None:
            self.scan_item = scan
            self.scan_id = scan.scan_id
        elif self.client.history and len(self.client.history) > 0:
            self.scan_item = self.client.history[-1]
            self.scan_id = self.client.history._scan_ids[-1]
            self.old_scan_id = None

    def update_labels(self):
        """
        Update the labels of the x, y, and z axes.
        """
        if self._image_config is None:
            return
        x_name = self._image_config.x_device.name
        y_name = self._image_config.y_device.name
        z_name = self._image_config.z_device.name

        if x_name is not None:
            self.x_label = x_name  # type: ignore
            x_dev = self.dev.get(x_name)
            if x_dev and hasattr(x_dev, "egu"):
                self.x_label_units = x_dev.egu()
        if y_name is not None:
            self.y_label = y_name  # type: ignore
            y_dev = self.dev.get(y_name)
            if y_dev and hasattr(y_dev, "egu"):
                self.y_label_units = y_dev.egu()
        if z_name is not None:
            self.title = z_name

    def _init_toolbar_heatmap(self):
        """
        Initialize the toolbar for the heatmap widget, adding actions for heatmap settings.
        """
        self.toolbar.add_action(
            "heatmap_settings",
            MaterialIconAction(
                icon_name="scatter_plot",
                tooltip="Show Heatmap Settings",
                checkable=True,
                parent=self,
            ),
        )

        self.toolbar.components.get_action("heatmap_settings").action.triggered.connect(
            self.show_heatmap_settings
        )

        # disable all processing actions except for the fft and log
        bundle = self.toolbar.get_bundle("image_processing")
        for name, action in bundle.bundle_actions.items():
            if name not in ["image_processing_fft", "image_processing_log"]:
                action().action.setVisible(False)

        self.toolbar.add_action(
            "interpolation_info",
            MaterialIconAction(
                icon_name="info", tooltip="Show Interpolation Info", checkable=True, parent=self
            ),
        )
        self.toolbar.components.get_action("interpolation_info").action.triggered.connect(
            self.toggle_interpolation_info
        )
        self.toolbar.components.get_action("interpolation_info").action.setChecked(
            self._image_config.show_config_label
        )

    def show_heatmap_settings(self):
        """
        Show the heatmap settings dialog.
        """
        heatmap_settings_action = self.toolbar.components.get_action("heatmap_settings").action
        if self.heatmap_dialog is None or not self.heatmap_dialog.isVisible():
            heatmap_settings = HeatmapSettings(parent=self, target_widget=self, popup=True)
            self.heatmap_dialog = SettingsDialog(
                self, settings_widget=heatmap_settings, window_title="Heatmap Settings", modal=False
            )
            self.heatmap_dialog.resize(700, 350)
            # When the dialog is closed, update the toolbar icon and clear the reference
            self.heatmap_dialog.finished.connect(self._heatmap_dialog_closed)
            self.heatmap_dialog.show()
            heatmap_settings_action.setChecked(True)
        else:
            # If already open, bring it to the front
            self.heatmap_dialog.raise_()
            self.heatmap_dialog.activateWindow()
            heatmap_settings_action.setChecked(True)  # keep it toggled

    def toggle_interpolation_info(self):
        """
        Toggle the visibility of the interpolation info label.
        """
        self._image_config.show_config_label = not self._image_config.show_config_label
        self.toolbar.components.get_action("interpolation_info").action.setChecked(
            self._image_config.show_config_label
        )
        self.redraw_config_label()

    def _heatmap_dialog_closed(self):
        """
        Slot for when the heatmap settings dialog is closed.
        """
        self.heatmap_dialog = None
        self.toolbar.components.get_action("heatmap_settings").action.setChecked(False)

    @SafeSlot(dict, dict)
    def on_scan_status(self, msg: dict, meta: dict):
        """
        Initial scan status message handler, which is triggered at the begging and end of scan.

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
            self.old_scan_id = self.scan_id
            self.scan_id = current_scan_id
            self.scan_item = self.queue.scan_storage.find_scan_by_ID(self.scan_id)  # type: ignore

            # First trigger to update the scan curves
            self.sync_signal_update.emit()

    @SafeSlot(dict, dict)
    def on_scan_progress(self, msg: dict, meta: dict):
        self.sync_signal_update.emit()
        status = msg.get("done")
        if status:
            QTimer.singleShot(100, self.update_plot)
            QTimer.singleShot(300, self.update_plot)

    @SafeSlot(verify_sender=True)
    def update_plot(self, _=None) -> None:
        """
        Update the plot with the current data.
        """
        if self.scan_item is None:
            logger.info("No scan executed so far; skipping update.")
            return
        data, access_key = self._fetch_scan_data_and_access()
        if data == "none":
            logger.info("No scan executed so far; skipping update.")
            return

        if self._image_config is None:
            return
        try:
            x_name = self._image_config.x_device.name
            x_entry = self._image_config.x_device.entry
            y_name = self._image_config.y_device.name
            y_entry = self._image_config.y_device.entry
            z_name = self._image_config.z_device.name
            z_entry = self._image_config.z_device.entry
        except AttributeError:
            return

        if access_key == "val":
            x_data = data.get(x_name, {}).get(x_entry, {}).get(access_key, None)
            y_data = data.get(y_name, {}).get(y_entry, {}).get(access_key, None)
            z_data = data.get(z_name, {}).get(z_entry, {}).get(access_key, None)
        else:
            x_data = data.get(x_name, {}).get(x_entry, {}).read().get("value", None)
            y_data = data.get(y_name, {}).get(y_entry, {}).read().get("value", None)
            z_data = data.get(z_name, {}).get(z_entry, {}).read().get("value", None)

            if not isinstance(x_data, list):
                x_data = x_data.tolist() if isinstance(x_data, np.ndarray) else None
            if not isinstance(y_data, list):
                y_data = y_data.tolist() if isinstance(y_data, np.ndarray) else None
            if not isinstance(z_data, list):
                z_data = z_data.tolist() if isinstance(z_data, np.ndarray) else None

        if x_data is None or y_data is None or z_data is None:
            logger.warning("x, y, or z data is None; skipping update.")
            return
        if len(x_data) != len(y_data) or len(x_data) != len(z_data):
            logger.warning(
                "x, y, and z data lengths do not match; skipping update. "
                f"Lengths: x={len(x_data)}, y={len(y_data)}, z={len(z_data)}"
            )
            return

        if hasattr(self.scan_item, "status_message"):
            scan_msg = self.scan_item.status_message
        elif hasattr(self.scan_item, "metadata"):
            metadata = self.scan_item.metadata["bec"]
            status = metadata["exit_status"]
            scan_id = metadata["scan_id"]
            scan_name = metadata["scan_name"]
            scan_type = metadata["scan_type"]
            scan_number = metadata["scan_number"]
            request_inputs = metadata["request_inputs"]
            if "arg_bundle" in request_inputs and isinstance(request_inputs["arg_bundle"], str):
                # Convert the arg_bundle from a JSON string to a dictionary
                request_inputs["arg_bundle"] = json.loads(request_inputs["arg_bundle"])
            positions = metadata.get("positions", [])
            positions = positions.tolist() if isinstance(positions, np.ndarray) else positions

            scan_msg = messages.ScanStatusMessage(
                status=status,
                scan_id=scan_id,
                scan_name=scan_name,
                scan_number=scan_number,
                scan_type=scan_type,
                request_inputs=request_inputs,
                info={"positions": positions},
            )
        else:
            scan_msg = None

        if scan_msg is None:
            logger.warning("Scan message is None; skipping update.")
            return
        self.status_message = scan_msg

        if self._image_config.show_config_label:
            self.redraw_config_label()

        img, transform = self.get_image_data(x_data=x_data, y_data=y_data, z_data=z_data)
        if img is None:
            logger.warning("Image data is None; skipping update.")
            return

        if self._color_bar is not None:
            self._color_bar.blockSignals(True)
        self.main_image.set_data(img, transform=transform)
        if self._color_bar is not None:
            self._color_bar.blockSignals(False)
        self.image_updated.emit()
        if self.crosshair is not None:
            self.crosshair.update_markers_on_image_change()

    def redraw_config_label(self):
        scan_msg = self.status_message
        if scan_msg is None:
            return
        if not self._image_config.show_config_label:
            self.config_label.setVisible(False)
            return

        self.config_label.setOffset((-30, 1))
        self.config_label.setVisible(True)
        self.config_label.clear()
        self.config_label.addItem(self.plot_item, f"Scan: {scan_msg.scan_number}")
        self.config_label.addItem(self.plot_item, f"Scan Name: {scan_msg.scan_name}")
        if scan_msg.scan_name != "grid_scan" or self._image_config.enforce_interpolation:
            self.config_label.addItem(
                self.plot_item, f"Interpolation: {self._image_config.interpolation}"
            )
            self.config_label.addItem(
                self.plot_item, f"Oversampling: {self._image_config.oversampling_factor}x"
            )

    def get_image_data(
        self,
        x_data: list[float] | None = None,
        y_data: list[float] | None = None,
        z_data: list[float] | None = None,
    ) -> tuple[np.ndarray | None, QTransform | None]:
        """
        Get the image data for the heatmap. Depending on the scan type, it will
        either pre-allocate the grid (grid_scan) or interpolate the data (step scan).

        Args:
            x_data (np.ndarray): The x data.
            y_data (np.ndarray): The y data.
            z_data (np.ndarray): The z data.
            msg (messages.ScanStatusMessage): The scan status message.

        Returns:
            tuple[np.ndarray, QTransform]: The image data and the QTransform.
        """
        msg = self.status_message
        if x_data is None or y_data is None or z_data is None or msg is None:
            logger.warning("x, y, or z data is None; skipping update.")
            return None, None

        if msg.scan_name == "grid_scan" and not self._image_config.enforce_interpolation:
            # We only support the grid scan mode if both scanning motors
            # are configured in the heatmap config.
            device_x = self._image_config.x_device.entry
            device_y = self._image_config.y_device.entry
            if (
                device_x in msg.request_inputs["arg_bundle"]
                and device_y in msg.request_inputs["arg_bundle"]
            ):
                return self.get_grid_scan_image(z_data, msg)
        if len(z_data) < 4:
            # LinearNDInterpolator requires at least 4 points to interpolate
            return None, None
        return self.get_step_scan_image(x_data, y_data, z_data, msg)

    def get_grid_scan_image(
        self, z_data: list[float], msg: messages.ScanStatusMessage
    ) -> tuple[np.ndarray, QTransform]:
        """
        Get the image data for a grid scan.
        Args:
            z_data (np.ndarray): The z data.
            msg (messages.ScanStatusMessage): The scan status message.

        Returns:
            tuple[np.ndarray, QTransform]: The image data and the QTransform.
        """

        args = self.arg_bundle_to_dict(4, msg.request_inputs["arg_bundle"])

        shape = (
            args[self._image_config.x_device.entry][-1],
            args[self._image_config.y_device.entry][-1],
        )

        data = self.main_image.raw_data

        if data is None or data.shape != shape:
            data = np.empty(shape)
            data.fill(np.nan)

        def _get_grid_data(axis, snaked=True):
            x_grid, y_grid = np.meshgrid(axis[0], axis[1])
            if snaked:
                y_grid.T[::2] = np.fliplr(y_grid.T[::2])
            x_flat = x_grid.T.ravel()
            y_flat = y_grid.T.ravel()
            positions = np.vstack((x_flat, y_flat)).T
            return positions

        snaked = msg.request_inputs["kwargs"].get("snaked", True)

        # If the scan's fast axis is x, we need to swap the x and y axes
        swap = bool(msg.request_inputs["arg_bundle"][4] == self._image_config.x_device.entry)

        # calculate the QTransform to put (0,0) at the axis origin
        scan_pos = np.asarray(msg.info["positions"])
        x_min = min(scan_pos[:, 0])
        x_max = max(scan_pos[:, 0])
        y_min = min(scan_pos[:, 1])
        y_max = max(scan_pos[:, 1])

        x_range = x_max - x_min
        y_range = y_max - y_min

        pixel_size_x = x_range / (shape[0] - 1)
        pixel_size_y = y_range / (shape[1] - 1)

        transform = QTransform()
        if swap:
            transform.scale(pixel_size_y, pixel_size_x)
            transform.translate(y_min / pixel_size_y - 0.5, x_min / pixel_size_x - 0.5)
        else:
            transform.scale(pixel_size_x, pixel_size_y)
            transform.translate(x_min / pixel_size_x - 0.5, y_min / pixel_size_y - 0.5)

        target_positions = _get_grid_data(
            (np.arange(shape[int(swap)]), np.arange(shape[int(not swap)])), snaked=snaked
        )

        # Fill the data array with the z values
        if self._grid_index is None or self.reload:
            self._grid_index = 0
            self.reload = False

        for i in range(self._grid_index, len(z_data)):
            data[target_positions[i, int(swap)], target_positions[i, int(not swap)]] = z_data[i]
        self._grid_index = len(z_data)
        return data, transform

    def get_step_scan_image(
        self,
        x_data: list[float],
        y_data: list[float],
        z_data: list[float],
        msg: messages.ScanStatusMessage,
    ) -> tuple[np.ndarray, QTransform]:
        """
        Get the image data for an arbitrary step scan.

        Args:
            x_data (list[float]): The x data.
            y_data (list[float]): The y data.
            z_data (list[float]): The z data.
            msg (messages.ScanStatusMessage): The scan status message.

        Returns:
            tuple[np.ndarray, QTransform]: The image data and the QTransform.
        """
        xy_data = np.column_stack((x_data, y_data))
        grid_x, grid_y, transform = self.get_image_grid(xy_data)

        # Interpolate the z data onto the grid
        if self._image_config.interpolation == "linear":
            interp = LinearNDInterpolator(xy_data, z_data)
        elif self._image_config.interpolation == "nearest":
            interp = NearestNDInterpolator(xy_data, z_data)
        elif self._image_config.interpolation == "clough":
            interp = CloughTocher2DInterpolator(xy_data, z_data)
        else:
            raise ValueError(
                "Interpolation method must be either 'linear', 'nearest', or 'clough'."
            )
        grid_z = interp(grid_x, grid_y)

        return grid_z, transform

    def get_image_grid(self, positions) -> tuple[np.ndarray, np.ndarray, QTransform]:
        """
        LRU-cached calculation of the grid for the image. The lru cache is indexed by the scan_id
        to avoid recalculating the grid for the same scan.

        Args:
            _scan_id (str): The scan ID. Needed for caching but not used in the function.

        Returns:
            tuple[np.ndarray, np.ndarray, QTransform]: The grid x and y coordinates and the QTransform.
        """
        base_width, base_height = self.estimate_image_resolution(positions)

        # Apply oversampling factor
        factor = self._image_config.oversampling_factor

        # Apply oversampling
        width = int(base_width * factor)
        height = int(base_height * factor)

        # Create grid
        grid_x, grid_y = np.mgrid[
            min(positions[:, 0]) : max(positions[:, 0]) : width * 1j,
            min(positions[:, 1]) : max(positions[:, 1]) : height * 1j,
        ]

        # Calculate transform
        x_min, x_max = min(positions[:, 0]), max(positions[:, 0])
        y_min, y_max = min(positions[:, 1]), max(positions[:, 1])
        x_range = x_max - x_min
        y_range = y_max - y_min
        x_scale = x_range / width
        y_scale = y_range / height

        transform = QTransform()
        transform.scale(x_scale, y_scale)
        transform.translate(x_min / x_scale - 0.5, y_min / y_scale - 0.5)

        return grid_x, grid_y, transform

    @staticmethod
    def estimate_image_resolution(coords: np.ndarray) -> tuple[int, int]:
        """
        Estimate the number of pixels needed for the image based on the coordinates.

        Args:
            coords (np.ndarray): The coordinates of the points.

        Returns:
            tuple[int, int]: The estimated width and height of the image."""
        if coords.ndim != 2 or coords.shape[1] != 2:
            raise ValueError("Input must be an (m x 2) array of (x, y) coordinates.")

        x_min, x_max = coords[:, 0].min(), coords[:, 0].max()
        y_min, y_max = coords[:, 1].min(), coords[:, 1].max()

        tree = cKDTree(coords)
        distances, _ = tree.query(coords, k=2)
        distances = distances[:, 1]  # Get the second nearest neighbor distance
        avg_distance = np.mean(distances)

        width_extent = x_max - x_min
        height_extent = y_max - y_min

        # Calculate the number of pixels needed based on the average distance
        width_pixels = int(np.ceil(width_extent / avg_distance))
        height_pixels = int(np.ceil(height_extent / avg_distance))

        return max(1, width_pixels), max(1, height_pixels)

    def arg_bundle_to_dict(self, bundle_size: int, args: list) -> dict:
        """
        Convert the argument bundle to a dictionary.

        Args:
            args (list): The argument bundle.

        Returns:
            dict: The dictionary representation of the argument bundle.
        """
        params = {}
        for cmds in partition(bundle_size, args):
            params[cmds[0]] = list(cmds[1:])
        return params

    def _fetch_scan_data_and_access(self):
        """
        Decide whether the widget is in live or historical mode
        and return the appropriate data dict and access key.

        Returns:
            data_dict (dict): The data structure for the current scan.
            access_key (str): Either 'val' (live) or 'value' (history).
        """
        if self.scan_item is None:
            # Optionally fetch the latest from history if nothing is set
            # self.update_with_scan_history(-1)
            if self.scan_item is None:
                logger.info("No scan executed so far; skipping update.")
                return "none", "none"

        if hasattr(self.scan_item, "live_data"):
            # Live scan
            return self.scan_item.live_data, "val"

        # Historical
        scan_devices = self.scan_item.devices
        return scan_devices, "value"

    def reset(self):
        self._grid_index = None
        self.main_image.clear()
        if self.crosshair is not None:
            self.crosshair.reset()
        super().reset()

    @SafeProperty(str)
    def interpolation_method(self) -> str:
        """
        The interpolation method used for the heatmap.
        """
        return self._image_config.interpolation

    @interpolation_method.setter
    def interpolation_method(self, value: str):
        """
        Set the interpolation method for the heatmap.
        Args:
            value(str): The interpolation method, either 'linear' or 'nearest'.
        """
        if value not in ["linear", "nearest"]:
            raise ValueError("Interpolation method must be either 'linear' or 'nearest'.")
        self._image_config.interpolation = value
        self.heatmap_property_changed.emit()

    @SafeProperty(float)
    def oversampling_factor(self) -> float:
        """
        The oversampling factor for grid resolution.
        """
        return self._image_config.oversampling_factor

    @oversampling_factor.setter
    def oversampling_factor(self, value: float):
        """
        Set the oversampling factor for grid resolution.
        Args:
            value(float): The oversampling factor (1.0 = no oversampling, 2.0 = 2x resolution).
        """
        if value <= 0:
            raise ValueError("Oversampling factor must be greater than 0.")
        self._image_config.oversampling_factor = value
        self.heatmap_property_changed.emit()

    @SafeProperty(bool)
    def enforce_interpolation(self) -> bool:
        """
        Whether to enforce interpolation even for grid scans.
        """
        return self._image_config.enforce_interpolation

    @enforce_interpolation.setter
    def enforce_interpolation(self, value: bool):
        """
        Set whether to enforce interpolation even for grid scans.

        Args:
            value(bool): Whether to enforce interpolation.
        """
        self._image_config.enforce_interpolation = value
        self.heatmap_property_changed.emit()

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


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    heatmap = Heatmap()
    heatmap.plot(x_name="samx", y_name="samy", z_name="bpm4i", oversampling_factor=5.0)
    heatmap.show()
    sys.exit(app.exec_())
