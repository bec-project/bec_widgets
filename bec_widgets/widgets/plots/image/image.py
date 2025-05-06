from __future__ import annotations

from typing import Literal

import numpy as np
import pyqtgraph as pg
from bec_lib import bec_logger
from bec_lib.endpoints import MessageEndpoints
from pydantic import Field, ValidationError, field_validator
from qtpy.QtCore import QPointF, Signal
from qtpy.QtWidgets import QWidget

from bec_widgets.utils import ConnectionConfig
from bec_widgets.utils.colors import Colors
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.plots.roi.image_roi import (
    BaseROI,
    RectangularROI,
    CircularROI,
    ROIController,
    ROIManagerTree,
)
from bec_widgets.utils.side_panel import SidePanel
from bec_widgets.utils.toolbar import MaterialIconAction, SwitchableToolBarAction
from bec_widgets.widgets.plots.image.image_item import ImageItem
from bec_widgets.widgets.plots.image.image_roi_plot import ImageROIPlot
from bec_widgets.widgets.plots.image.toolbar_bundles.image_selection import (
    MonitorSelectionToolbarBundle,
)
from bec_widgets.widgets.plots.image.toolbar_bundles.processing import ImageProcessingToolbarBundle
from bec_widgets.widgets.plots.plot_base import PlotBase

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


class Image(PlotBase):
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
        # ImageView Specific Settings
        "color_map",
        "color_map.setter",
        "vrange",
        "vrange.setter",
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
    ]
    sync_colorbar_with_autorange = Signal()

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
        self._main_image = ImageItem()
        super().__init__(
            parent=parent, config=config, client=client, gui_id=gui_id, popups=popups, **kwargs
        )
        self._main_image = ImageItem(parent_image=self)

        self.plot_item.addItem(self._main_image)
        self.scan_id = None

        # Default Color map to plasma
        self.color_map = "plasma"

        # Initialize ROI plots and side panels
        self._add_roi_plots()

        # ---------------- ROI Manager integration ----------------
        # Headless controller keeps the canonical list.
        self.roi_controller = ROIController(colormap=self.color_map)
        # TODO make as property for RPC
        # self.rois = self.roi_controller.rois

        # TODO mock data to setup the image
        self._main_image.set_data(np.random.rand(100, 100))

    ################################################################################
    # Widget Specific GUI interactions
    ################################################################################
    def _init_toolbar(self):

        # add to the first position
        self.selection_bundle = MonitorSelectionToolbarBundle(
            bundle_id="selection", target_widget=self
        )
        self.toolbar.add_bundle(self.selection_bundle, self)

        super()._init_toolbar()

        # Image specific changes to PlotBase toolbar
        self.toolbar.widgets["reset_legend"].action.setVisible(False)

        # Lock aspect ratio button
        self.lock_aspect_ratio_action = MaterialIconAction(
            icon_name="aspect_ratio", tooltip="Lock Aspect Ratio", checkable=True, parent=self
        )
        self.toolbar.add_action_to_bundle(
            bundle_id="mouse_interaction",
            action_id="lock_aspect_ratio",
            action=self.lock_aspect_ratio_action,
            target_widget=self,
        )
        self.lock_aspect_ratio_action.action.toggled.connect(
            lambda checked: self.setProperty("lock_aspect_ratio", checked)
        )
        self.lock_aspect_ratio_action.action.setChecked(True)

        self._init_autorange_action()
        self._init_colorbar_action()

        # Processing Bundle
        self.processing_bundle = ImageProcessingToolbarBundle(
            bundle_id="processing", target_widget=self
        )
        self.toolbar.add_bundle(self.processing_bundle, target_widget=self)

    def _init_autorange_action(self):

        self.autorange_mean_action = MaterialIconAction(
            icon_name="hdr_auto", tooltip="Enable Auto Range (Mean)", checkable=True, parent=self
        )
        self.autorange_max_action = MaterialIconAction(
            icon_name="hdr_auto",
            tooltip="Enable Auto Range (Max)",
            checkable=True,
            filled=True,
            parent=self,
        )

        self.autorange_switch = SwitchableToolBarAction(
            actions={
                "auto_range_mean": self.autorange_mean_action,
                "auto_range_max": self.autorange_max_action,
            },
            initial_action="auto_range_mean",
            tooltip="Enable Auto Range",
            checkable=True,
            parent=self,
        )

        self.toolbar.add_action_to_bundle(
            bundle_id="roi",
            action_id="autorange_image",
            action=self.autorange_switch,
            target_widget=self,
        )

        self.autorange_mean_action.action.toggled.connect(
            lambda checked: self.toggle_autorange(checked, mode="mean")
        )
        self.autorange_max_action.action.toggled.connect(
            lambda checked: self.toggle_autorange(checked, mode="max")
        )

        self.autorange = True
        self.autorange_mode = "mean"

    ################################################################################
    # Colorbar

    def _init_colorbar_action(self):
        self.full_colorbar_action = MaterialIconAction(
            icon_name="edgesensor_low", tooltip="Enable Full Colorbar", checkable=True, parent=self
        )
        self.simple_colorbar_action = MaterialIconAction(
            icon_name="smartphone", tooltip="Enable Simple Colorbar", checkable=True, parent=self
        )

        self.colorbar_switch = SwitchableToolBarAction(
            actions={
                "full_colorbar": self.full_colorbar_action,
                "simple_colorbar": self.simple_colorbar_action,
            },
            initial_action="full_colorbar",
            tooltip="Enable Full Colorbar",
            checkable=True,
            parent=self,
        )

        self.toolbar.add_action_to_bundle(
            bundle_id="roi",
            action_id="switch_colorbar",
            action=self.colorbar_switch,
            target_widget=self,
        )

        self.simple_colorbar_action.action.toggled.connect(
            lambda checked: self.enable_colorbar(checked, style="simple")
        )
        self.full_colorbar_action.action.toggled.connect(
            lambda checked: self.enable_colorbar(checked, style="full")
        )

    def enable_colorbar(
        self,
        enabled: bool,
        style: Literal["full", "simple"] = "full",
        vrange: tuple[int, int] | None = None,
    ):
        """
        Enable the colorbar and switch types of colorbars.

        Args:
            enabled(bool): Whether to enable the colorbar.
            style(Literal["full", "simple"]): The type of colorbar to enable.
            vrange(tuple): The range of values to use for the colorbar.
        """
        autorange_state = self._main_image.autorange
        if enabled:
            if self._color_bar:
                if self.config.color_bar == "full":
                    self.cleanup_histogram_lut_item(self._color_bar)
                self.plot_widget.removeItem(self._color_bar)
                self._color_bar = None

            if style == "simple":
                self._color_bar = pg.ColorBarItem(colorMap=self.config.color_map)
                self._color_bar.setImageItem(self._main_image)
                self._color_bar.sigLevelsChangeFinished.connect(
                    lambda: self.setProperty("autorange", False)
                )

            elif style == "full":
                self._color_bar = pg.HistogramLUTItem()
                self._color_bar.setImageItem(self._main_image)
                self._color_bar.gradient.loadPreset(self.config.color_map)
                self._color_bar.sigLevelsChanged.connect(
                    lambda: self.setProperty("autorange", False)
                )

            self.plot_widget.addItem(self._color_bar, row=0, col=1)
            self.config.color_bar = style
        else:
            if self._color_bar:
                self.plot_widget.removeItem(self._color_bar)
                self._color_bar = None
            self.config.color_bar = None

        self.autorange = autorange_state
        self._sync_colorbar_actions()

        if vrange:  # should be at the end to disable the autorange if defined
            self.v_range = vrange

    ################################################################################
    # Roi plots with cuts

    def _add_roi_plots(self):
        """
        Initialize the ROI plots and side panels.
        """
        # Create ROI plot widgets
        self.x_roi = ImageROIPlot(parent=self)
        self.y_roi = ImageROIPlot(parent=self)
        self.x_roi.apply_theme("dark")
        self.y_roi.apply_theme("dark")

        # Set titles for the plots
        self.x_roi.plot_item.setTitle("X ROI")
        self.y_roi.plot_item.setTitle("Y ROI")

        # Create side panels
        self.side_panel_x = SidePanel(
            parent=self, orientation="bottom", panel_max_width=200, show_toolbar=False
        )
        self.side_panel_y = SidePanel(
            parent=self, orientation="left", panel_max_width=200, show_toolbar=False
        )

        # Add ROI plots to side panels
        self.x_panel_index = self.side_panel_x.add_menu(widget=self.x_roi)
        self.y_panel_index = self.side_panel_y.add_menu(widget=self.y_roi)

        # # Add side panels to the layout
        self.layout_manager.add_widget_relative(
            self.side_panel_x, self.round_plot_widget, position="bottom", shift_direction="down"
        )
        self.layout_manager.add_widget_relative(
            self.side_panel_y, self.round_plot_widget, position="left", shift_direction="right"
        )

    def hook_crosshair(self) -> None:
        super().hook_crosshair()
        self.toggle_roi_panels(True)

    def unhook_crosshair(self) -> None:
        super().unhook_crosshair()
        self.toggle_roi_panels(False)

    def toggle_roi_panels(self, checked):
        """
        Show or hide the ROI panels based on the test action toggle state.

        Args:
            checked (bool): Whether the test action is checked.
        """
        if checked:
            # Show the ROI panels
            self.side_panel_x.show_panel(self.x_panel_index)
            self.side_panel_y.show_panel(self.y_panel_index)
            self.crosshair.coordinatesChanged2D.connect(self.update_image_slices)
        else:
            # Hide the ROI panels
            self.side_panel_x.hide_panel()
            self.side_panel_y.hide_panel()

    def update_image_slices(self, coordinates: tuple[int, int]):

        x = coordinates[1]
        y = coordinates[2]
        image = self._main_image.image
        max_row, max_col = image.shape[0] - 1, image.shape[1] - 1
        row, col = x, y
        if not (0 <= row <= max_row and 0 <= col <= max_col):
            return
        # Horizontal slice (row)
        h_slice = image[row, :]
        x_axis = np.arange(h_slice.shape[0])
        self.x_roi.plot_item.clear()
        self.x_roi.plot_item.plot(x_axis, h_slice)
        # Vertical slice (column)
        v_slice = image[:, col]
        y_axis = np.arange(v_slice.shape[0])
        self.y_roi.plot_item.clear()
        self.y_roi.plot_item.plot(v_slice, y_axis)

    ################################################################################
    # Static rois with roi manager

    def add_roi(
        self, kind: Literal["rect", "circle"] = "rect", name: str | None = None, **pg_kwargs
    ) -> BaseROI:
        """Create an ROI (rect or circle), add to scene & controller, and return it."""
        if name is None:
            name = f"ROI_{len(self.roi_controller.rois) + 1}"
        if kind == "rect":
            roi = RectangularROI(
                pos=[10, 10],
                size=[50, 50],
                parent_image=self,
                line_width=3,
                label=name,
                **pg_kwargs,
            )
        elif kind == "circle":
            roi = CircularROI(
                pos=[10, 10],
                size=[50, 50],
                parent_image=self,
                line_width=3,
                label=name,
                **pg_kwargs,
            )
        else:
            raise ValueError("kind must be 'rect' or 'circle'")

        # Add to plot and controller (controller assigns color)
        self.plot_item.addItem(roi)
        self.roi_controller.add_roi(roi)
        return roi

    def remove_roi(self, roi_index: int | None = None, roi_name: str | None = None):
        """Remove ROI by index or name from both scene and controller."""
        if roi_index is not None:
            roi = self.roi_controller.get_roi(roi_index)
        elif roi_name is not None:
            roi = self.roi_controller.get_roi_by_name(roi_name)
        else:
            raise ValueError("Either roi_index or roi_name must be provided")

        if roi is not None:
            self.plot_item.removeItem(roi)
            self.roi_controller.remove_roi(roi)

    ################################################################################
    # Widget Specific Properties
    ################################################################################
    ################################################################################
    # Rois

    @property
    def rois(self) -> list[BaseROI]:
        """
        Get the list of ROIs.
        """
        return self.roi_controller.rois

    ################################################################################
    # Colorbar toggle

    @SafeProperty(bool)
    def enable_simple_colorbar(self) -> bool:
        """
        Enable the simple colorbar.
        """
        enabled = False
        if self.config.color_bar == "simple":
            enabled = True
        return enabled

    @enable_simple_colorbar.setter
    def enable_simple_colorbar(self, value: bool):
        """
        Enable the simple colorbar.

        Args:
            value(bool): Whether to enable the simple colorbar.
        """
        self.enable_colorbar(enabled=value, style="simple")

    @SafeProperty(bool)
    def enable_full_colorbar(self) -> bool:
        """
        Enable the full colorbar.
        """
        enabled = False
        if self.config.color_bar == "full":
            enabled = True
        return enabled

    @enable_full_colorbar.setter
    def enable_full_colorbar(self, value: bool):
        """
        Enable the full colorbar.

        Args:
            value(bool): Whether to enable the full colorbar.
        """
        self.enable_colorbar(enabled=value, style="full")

    ################################################################################
    # Appearance

    @SafeProperty(str)
    def color_map(self) -> str:
        """
        Set the color map of the image.
        """
        return self.config.color_map

    @color_map.setter
    def color_map(self, value: str):
        """
        Set the color map of the image.

        Args:
            value(str): The color map to set.
        """
        try:
            self.config.color_map = value
            self._main_image.color_map = value

            if self._color_bar:
                if self.config.color_bar == "simple":
                    self._color_bar.setColorMap(value)
                elif self.config.color_bar == "full":
                    self._color_bar.gradient.loadPreset(value)
        except ValidationError:
            return

    # v_range is for designer, vrange is for RPC
    @SafeProperty("QPointF")
    def v_range(self) -> QPointF:
        """
        Set the v_range of the main image.
        """
        vmin, vmax = self._main_image.v_range
        return QPointF(vmin, vmax)

    @v_range.setter
    def v_range(self, value: tuple | list | QPointF):
        """
        Set the v_range of the main image.

        Args:
            value(tuple | list | QPointF): The range of values to set.
        """
        if isinstance(value, (tuple, list)):
            value = self._tuple_to_qpointf(value)

        vmin, vmax = value.x(), value.y()

        self._main_image.v_range = (vmin, vmax)

        # propagate to colorbar if exists
        if self._color_bar:
            if self.config.color_bar == "simple":
                self._color_bar.setLevels(low=vmin, high=vmax)
            elif self.config.color_bar == "full":
                self._color_bar.setLevels(min=vmin, max=vmax)
                self._color_bar.setHistogramRange(vmin - 0.1 * vmin, vmax + 0.1 * vmax)

        self.autorange_switch.set_state_all(False)

    @property
    def vrange(self) -> tuple:
        """
        Get the vrange of the image.
        """
        return (self.v_range.x(), self.v_range.y())

    @vrange.setter
    def vrange(self, value):
        """
        Set the vrange of the image.

        Args:
            value(tuple):
        """
        self.v_range = value

    @property
    def v_min(self) -> float:
        """
        Get the minimum value of the v_range.
        """
        return self.v_range.x()

    @v_min.setter
    def v_min(self, value: float):
        """
        Set the minimum value of the v_range.

        Args:
            value(float): The minimum value to set.
        """
        self.v_range = (value, self.v_range.y())

    @property
    def v_max(self) -> float:
        """
        Get the maximum value of the v_range.
        """
        return self.v_range.y()

    @v_max.setter
    def v_max(self, value: float):
        """
        Set the maximum value of the v_range.

        Args:
            value(float): The maximum value to set.
        """
        self.v_range = (self.v_range.x(), value)

    @SafeProperty(bool)
    def lock_aspect_ratio(self) -> bool:
        """
        Whether the aspect ratio is locked.
        """
        return self.config.lock_aspect_ratio

    @lock_aspect_ratio.setter
    def lock_aspect_ratio(self, value: bool):
        """
        Set the aspect ratio lock.

        Args:
            value(bool): Whether to lock the aspect ratio.
        """
        self.config.lock_aspect_ratio = bool(value)
        self.plot_item.setAspectLocked(value)

    ################################################################################
    # Data Acquisition

    @SafeProperty(str)
    def monitor(self) -> str:
        """
        The name of the monitor to use for the image.
        """
        return self._main_image.config.monitor

    @monitor.setter
    def monitor(self, value: str):
        """
        Set the monitor for the image.

        Args:
            value(str): The name of the monitor to set.
        """
        if self._main_image.config.monitor == value:
            return
        try:
            self.entry_validator.validate_monitor(value)
        except ValueError:
            return
        self.image(monitor=value)

    @property
    def main_image(self) -> ImageItem:
        """Access the main image item."""
        return self._main_image

    ################################################################################
    # Autorange + Colorbar sync

    @SafeProperty(bool)
    def autorange(self) -> bool:
        """
        Whether autorange is enabled.
        """
        return self._main_image.autorange

    @autorange.setter
    def autorange(self, enabled: bool):
        """
        Set autorange.

        Args:
            enabled(bool): Whether to enable autorange.
        """
        self._main_image.autorange = enabled
        if enabled and self._main_image.raw_data is not None:
            self._main_image.apply_autorange()
            self._sync_colorbar_levels()
        self._sync_autorange_switch()

    @SafeProperty(str)
    def autorange_mode(self) -> str:
        """
        Autorange mode.

        Options:
            - "max": Use the maximum value of the image for autoranging.
            - "mean": Use the mean value of the image for autoranging.

        """
        return self._main_image.autorange_mode

    @autorange_mode.setter
    def autorange_mode(self, mode: str):
        """
        Set the autorange mode.

        Args:
            mode(str): The autorange mode. Options are "max" or "mean".
        """
        # for qt Designer
        if mode not in ["max", "mean"]:
            return
        self._main_image.autorange_mode = mode

        self._sync_autorange_switch()

    @SafeSlot(bool, str, bool)
    def toggle_autorange(self, enabled: bool, mode: str):
        """
        Toggle autorange.

        Args:
            enabled(bool): Whether to enable autorange.
            mode(str): The autorange mode. Options are "max" or "mean".
        """
        if self._main_image is not None:
            self._main_image.autorange = enabled
            self._main_image.autorange_mode = mode
            if enabled:
                self._main_image.apply_autorange()
            self._sync_colorbar_levels()

    def _sync_autorange_switch(self):
        """
        Synchronize the autorange switch with the current autorange state and mode if changed from outside.
        """
        self.autorange_switch.block_all_signals(True)
        self.autorange_switch.set_default_action(f"auto_range_{self._main_image.autorange_mode}")
        self.autorange_switch.set_state_all(self._main_image.autorange)
        self.autorange_switch.block_all_signals(False)

    def _sync_colorbar_levels(self):
        """Immediately propagate current levels to the active colorbar."""
        vrange = self._main_image.v_range
        if self._color_bar:
            self._color_bar.blockSignals(True)
            self.v_range = vrange
            self._color_bar.blockSignals(False)

    def _sync_colorbar_actions(self):
        """
        Synchronize the colorbar actions with the current colorbar state.
        """
        self.colorbar_switch.block_all_signals(True)
        if self._color_bar is not None:
            self.colorbar_switch.set_default_action(f"{self.config.color_bar}_colorbar")
            self.colorbar_switch.set_state_all(True)
        else:
            self.colorbar_switch.set_state_all(False)
        self.colorbar_switch.block_all_signals(False)

    ################################################################################
    # Post Processing
    ################################################################################

    @SafeProperty(bool)
    def fft(self) -> bool:
        """
        Whether FFT postprocessing is enabled.
        """
        return self._main_image.fft

    @fft.setter
    def fft(self, enable: bool):
        """
        Set FFT postprocessing.

        Args:
            enable(bool): Whether to enable FFT postprocessing.
        """
        self._main_image.fft = enable

    @SafeProperty(bool)
    def log(self) -> bool:
        """
        Whether logarithmic scaling is applied.
        """
        return self._main_image.log

    @log.setter
    def log(self, enable: bool):
        """
        Set logarithmic scaling.

        Args:
            enable(bool): Whether to enable logarithmic scaling.
        """
        self._main_image.log = enable

    @SafeProperty(int)
    def num_rotation_90(self) -> int:
        """
        The number of 90° rotations to apply counterclockwise.
        """
        return self._main_image.num_rotation_90

    @num_rotation_90.setter
    def num_rotation_90(self, value: int):
        """
        Set the number of 90° rotations to apply counterclockwise.

        Args:
            value(int): The number of 90° rotations to apply.
        """
        self._main_image.num_rotation_90 = value

    @SafeProperty(bool)
    def transpose(self) -> bool:
        """
        Whether the image is transposed.
        """
        return self._main_image.transpose

    @transpose.setter
    def transpose(self, enable: bool):
        """
        Set the image to be transposed.

        Args:
            enable(bool): Whether to enable transposing the image.
        """
        self._main_image.transpose = enable

    ################################################################################
    # High Level methods for API
    ################################################################################
    @SafeSlot(popup_error=True)
    def image(
        self,
        monitor: str | None = None,
        monitor_type: Literal["auto", "1d", "2d"] = "auto",
        color_map: str | None = None,
        color_bar: Literal["simple", "full"] | None = None,
        vrange: tuple[int, int] | None = None,
    ) -> ImageItem:
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

        if self._main_image.config.monitor is not None:
            self.disconnect_monitor(self._main_image.config.monitor)
        self.entry_validator.validate_monitor(monitor)
        self._main_image.config.monitor = monitor

        if monitor_type == "1d":
            self._main_image.config.source = "device_monitor_1d"
            self._main_image.config.monitor_type = "1d"
        elif monitor_type == "2d":
            self._main_image.config.source = "device_monitor_2d"
            self._main_image.config.monitor_type = "2d"
        elif monitor_type == "auto":
            self._main_image.config.source = "auto"
            logger.warning(
                f"Updates for '{monitor}' will be fetch from both 1D and 2D monitor endpoints."
            )
            self._main_image.config.monitor_type = "auto"

        self.set_image_update(monitor=monitor, type=monitor_type)
        if color_map is not None:
            self._main_image.color_map = color_map
        if color_bar is not None:
            self.enable_colorbar(True, color_bar)
        if vrange is not None:
            self.vrange = vrange

        self._sync_device_selection()

        return self._main_image

    def _sync_device_selection(self):
        """
        Synchronize the device selection with the current monitor.
        """
        if self._main_image.config.monitor is not None:
            for combo in (
                self.selection_bundle.device_combo_box,
                self.selection_bundle.dim_combo_box,
            ):
                combo.blockSignals(True)
            self.selection_bundle.device_combo_box.set_device(self._main_image.config.monitor)
            self.selection_bundle.dim_combo_box.setCurrentText(self._main_image.config.monitor_type)
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
    # Image Update Methods
    ################################################################################

    ########################################
    # Connections

    def set_image_update(self, monitor: str, type: Literal["1d", "2d", "auto"]):
        """
        Set the image update method for the given monitor.

        Args:
            monitor(str): The name of the monitor to use for the image.
            type(str): The type of monitor to use. Options are "1d", "2d", or "auto".
        """

        # TODO consider moving connecting and disconnecting logic to Image itself if multiple images
        if type == "1d":
            self.bec_dispatcher.connect_slot(
                self.on_image_update_1d, MessageEndpoints.device_monitor_1d(monitor)
            )
        elif type == "2d":
            self.bec_dispatcher.connect_slot(
                self.on_image_update_2d, MessageEndpoints.device_monitor_2d(monitor)
            )
        elif type == "auto":
            self.bec_dispatcher.connect_slot(
                self.on_image_update_1d, MessageEndpoints.device_monitor_1d(monitor)
            )
            self.bec_dispatcher.connect_slot(
                self.on_image_update_2d, MessageEndpoints.device_monitor_2d(monitor)
            )
        print(f"Connected to {monitor} with type {type}")
        self._main_image.config.monitor = monitor

    def disconnect_monitor(self, monitor: str):
        """
        Disconnect the monitor from the image update signals, both 1D and 2D.

        Args:
            monitor(str): The name of the monitor to disconnect.
        """
        self.bec_dispatcher.disconnect_slot(
            self.on_image_update_1d, MessageEndpoints.device_monitor_1d(monitor)
        )
        self.bec_dispatcher.disconnect_slot(
            self.on_image_update_2d, MessageEndpoints.device_monitor_2d(monitor)
        )
        self._main_image.config.monitor = None
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
            self._main_image.clear()
            self._main_image.buffer = []
            self._main_image.max_len = 0
        image_buffer = self.adjust_image_buffer(self._main_image, data)
        if self._color_bar is not None:
            self._color_bar.blockSignals(True)
        self._main_image.set_data(image_buffer)
        if self._color_bar is not None:
            self._color_bar.blockSignals(False)

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
        self._main_image.set_data(data)
        if self._color_bar is not None:
            self._color_bar.blockSignals(False)

    ################################################################################
    # Clean up
    ################################################################################

    @staticmethod
    def cleanup_histogram_lut_item(histogram_lut_item: pg.HistogramLUTItem):
        """
        Clean up HistogramLUTItem safely, including open ViewBox menus and child widgets.

        Args:
            histogram_lut_item(pg.HistogramLUTItem): The HistogramLUTItem to clean up.
        """
        histogram_lut_item.vb.menu.close()
        histogram_lut_item.vb.menu.deleteLater()

        histogram_lut_item.gradient.menu.close()
        histogram_lut_item.gradient.menu.deleteLater()
        histogram_lut_item.gradient.colorDialog.close()
        histogram_lut_item.gradient.colorDialog.deleteLater()

    def cleanup(self):
        """
        Disconnect the image update signals and clean up the image.
        """
        # Main Image cleanup
        if self._main_image.config.monitor is not None:
            self.disconnect_monitor(self._main_image.config.monitor)
            self._main_image.config.monitor = None
        self.plot_item.removeItem(self._main_image)
        self._main_image = None

        # Colorbar Cleanup
        if self._color_bar:
            if self.config.color_bar == "full":
                self.cleanup_histogram_lut_item(self._color_bar)
            if self.config.color_bar == "simple":
                self.plot_widget.removeItem(self._color_bar)
                self._color_bar.deleteLater()
            self._color_bar = None

        # Toolbar cleanup
        self.toolbar.widgets["monitor"].widget.close()
        self.toolbar.widgets["monitor"].widget.deleteLater()

        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = Image(popups=False)
    widget.show()
    widget.resize(1000, 800)
    sys.exit(app.exec_())
