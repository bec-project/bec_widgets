from __future__ import annotations

from typing import Literal

import numpy as np
import pyqtgraph as pg
from bec_lib import bec_logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from qtpy.QtCore import QPointF, Signal, SignalInstance
from qtpy.QtWidgets import QDialog, QVBoxLayout

from bec_widgets.utils.container_utils import WidgetContainerUtils
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.side_panel import SidePanel
from bec_widgets.utils.toolbars.actions import MaterialIconAction, SwitchableToolBarAction
from bec_widgets.widgets.plots.image.image_item import ImageItem
from bec_widgets.widgets.plots.image.image_roi_plot import ImageROIPlot
from bec_widgets.widgets.plots.image.setting_widgets.image_roi_tree import ROIPropertyTree
from bec_widgets.widgets.plots.image.toolbar_components.image_base_actions import (
    ImageColorbarConnection,
    ImageProcessingConnection,
    ImageRoiConnection,
    image_autorange,
    image_colorbar,
    image_processing,
    image_roi_bundle,
)
from bec_widgets.widgets.plots.plot_base import PlotBase
from bec_widgets.widgets.plots.roi.image_roi import (
    BaseROI,
    CircularROI,
    EllipticalROI,
    RectangularROI,
    ROIController,
)

logger = bec_logger.logger


class ImageLayerSync(BaseModel):
    """
    Model for the image layer synchronization.
    """

    autorange: bool = Field(
        True, description="Whether to synchronize the autorange of the image layer."
    )
    autorange_mode: bool = Field(
        True, description="Whether to synchronize the autorange mode of the image layer."
    )
    color_map: bool = Field(
        True, description="Whether to synchronize the color map of the image layer."
    )
    v_range: bool = Field(
        True, description="Whether to synchronize the v_range of the image layer."
    )
    fft: bool = Field(True, description="Whether to synchronize the FFT of the image layer.")
    log: bool = Field(True, description="Whether to synchronize the log of the image layer.")
    rotation: bool = Field(
        True, description="Whether to synchronize the rotation of the image layer."
    )
    transpose: bool = Field(
        True, description="Whether to synchronize the transpose of the image layer."
    )


class ImageLayer(BaseModel):
    """
    Model for the image layer.
    """

    name: str = Field(description="The name of the image layer.")
    image: ImageItem = Field(description="The image item to be displayed.")
    sync: ImageLayerSync = Field(
        default_factory=ImageLayerSync,
        description="The synchronization settings for the image layer.",
    )
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ImageLayerManager:
    """
    Manager for the image layers.
    """

    Z_RANGE_USER = (-100, 100)

    def __init__(
        self,
        parent: ImageBase,
        plot_item: pg.PlotItem,
        on_add: SignalInstance | None = None,
        on_remove: SignalInstance | None = None,
    ):
        self.parent = parent
        self.plot_item = plot_item
        self.on_add = on_add
        self.on_remove = on_remove
        self.layers: dict[str, ImageLayer] = {}

    def add(
        self,
        name: str | None = None,
        z_position: int | Literal["top", "bottom"] | None = None,
        sync: ImageLayerSync | None = None,
        **kwargs,
    ) -> ImageLayer:
        """
        Add an image layer to the widget.

        Args:
            name (str | None): The name of the image layer. If None, a default name is generated.
            image (ImageItem): The image layer to add.
            z_position (int | None): The z position of the image layer. If None, the layer is added to the top.
            sync (ImageLayerSync | None): The synchronization settings for the image layer.
            **kwargs: ImageLayerSync settings. Only used if sync is None.
        """
        if name is None:
            name = WidgetContainerUtils.generate_unique_name(
                "image_layer", list(self.layers.keys())
            )
        if name in self.layers:
            raise ValueError(f"Layer with name '{name}' already exists.")
        if sync is None:
            sync = ImageLayerSync(**kwargs)
        if z_position is None or z_position == "top":
            z_position = self._get_top_z_position()
        elif z_position == "bottom":
            z_position = self._get_bottom_z_position()
        image = ImageItem(parent_image=self.parent, object_name=name)
        image.setZValue(z_position)
        image.removed.connect(self._remove_destroyed_layer)

        # FIXME: For now, we hard-code the default color map here. In the future, this should be configurable.
        image.color_map = "plasma"

        self.layers[name] = ImageLayer(name=name, image=image, sync=sync)
        self.plot_item.addItem(image)

        if self.on_add is not None:
            self.on_add.emit(name)

        return self.layers[name]

    @SafeSlot(str)
    def _remove_destroyed_layer(self, layer: str):
        """
        Remove a layer that has been destroyed.

        Args:
            layer (str): The name of the layer to remove.
        """
        self.remove(layer)
        if self.on_remove is not None:
            self.on_remove.emit(layer)

    def remove(self, layer: ImageLayer | str):
        """
        Remove an image layer from the widget.

        Args:
            layer (ImageLayer | str): The image layer to remove. Can be the layer object or the name of the layer.
        """
        if isinstance(layer, str):
            name = layer
        else:
            name = layer.name

        removed_layer = self.layers.pop(name, None)

        if not removed_layer:
            return
        self.plot_item.removeItem(removed_layer.image)
        removed_layer.image.remove(emit=False)
        removed_layer.image.deleteLater()
        removed_layer.image = None

    def clear(self):
        """
        Clear all image layers from the manager.
        """
        for layer in list(self.layers.keys()):
            # Remove each layer from the plot item and delete it
            self.remove(layer)
        self.layers.clear()

    def _get_top_z_position(self) -> int:
        """
        Get the top z position of the image layers, capping it to the maximum z value.

        Returns:
            int: The top z position of the image layers.
        """
        if not self.layers:
            return 0
        z = max(layer.image.zValue() for layer in self.layers.values()) + 1
        return min(z, self.Z_RANGE_USER[1])

    def _get_bottom_z_position(self) -> int:
        """
        Get the bottom z position of the image layers, capping it to the minimum z value.

        Returns:
            int: The bottom z position of the image layers.
        """
        if not self.layers:
            return 0
        z = min(layer.image.zValue() for layer in self.layers.values()) - 1
        return max(z, self.Z_RANGE_USER[0])

    def __iter__(self):
        """
        Iterate over the image layers.

        Returns:
            Iterator[ImageLayer]: An iterator over the image layers.
        """
        return iter(self.layers.values())

    def __getitem__(self, name: str) -> ImageLayer:
        """
        Get an image layer by name.

        Args:
            name (str): The name of the image layer.

        Returns:
            ImageLayer: The image layer with the given name.
        """
        if not isinstance(name, str):
            raise TypeError("name must be a string")
        if name == "main" and name not in self.layers:
            # If 'main' is requested, create a default layer if it doesn't exist
            return self.add(name=name, z_position="top")
        return self.layers[name]

    def __len__(self) -> int:
        """
        Get the number of image layers.

        Returns:
            int: The number of image layers.
        """
        return len(self.layers)


class ImageBase(PlotBase):
    """
    Base class for the Image widget.
    """

    sync_colorbar_with_autorange = Signal()
    image_updated = Signal()
    layer_added = Signal(str)
    layer_removed = Signal(str)

    def __init__(self, *args, **kwargs):
        """
        Initialize the ImageBase widget.
        """
        self.x_roi = None
        self.y_roi = None
        self._color_bar = None
        super().__init__(*args, **kwargs)

        self.roi_controller = ROIController(colormap="viridis")

        # Headless controller keeps the canonical list.
        self.roi_manager_dialog = None
        self.layer_manager: ImageLayerManager = ImageLayerManager(
            self, plot_item=self.plot_item, on_add=self.layer_added, on_remove=self.layer_removed
        )
        self.layer_manager.add("main")
        self._init_image_base_toolbar()

        self.autorange = True
        self.autorange_mode = "mean"

        # Initialize ROI plots and side panels
        self._add_roi_plots()

        # Refresh theme for ROI plots
        self._update_theme()

        self.toolbar.show_bundles(
            [
                "image_crosshair",
                "mouse_interaction",
                "image_autorange",
                "image_colorbar",
                "image_processing",
            ]
        )

    ################################################################################
    # Widget Specific GUI interactions
    ################################################################################

    def apply_theme(self, theme: str):
        super().apply_theme(theme)
        if self.x_roi is not None and self.y_roi is not None:
            self.x_roi.apply_theme(theme)
            self.y_roi.apply_theme(theme)

    def add_layer(self, name: str | None = None, **kwargs) -> ImageLayer:
        """
        Add a new image layer to the widget.

        Args:
            name (str | None): The name of the image layer. If None, a default name is generated.
            **kwargs: Additional arguments for the image layer.

        Returns:
            ImageLayer: The added image layer.
        """
        layer = self.layer_manager.add(name=name, **kwargs)
        self.image_updated.emit()
        return layer

    def remove_layer(self, layer: ImageLayer | str):
        """
        Remove an image layer from the widget.

        Args:
            layer (ImageLayer | str): The image layer to remove. Can be the layer object or the name of the layer.
        """
        self.layer_manager.remove(layer)
        self.image_updated.emit()

    def layers(self) -> list[ImageLayer]:
        """
        Get the list of image layers.

        Returns:
            list[ImageLayer]: The list of image layers.
        """
        return list(self.layer_manager.layers.values())

    def _init_image_base_toolbar(self):

        try:

            # ROI Actions
            self.toolbar.add_bundle(image_roi_bundle(self.toolbar.components))
            self.toolbar.connect_bundle(
                "image_base", ImageRoiConnection(self.toolbar.components, target_widget=self)
            )

            # Lock Aspect Ratio Action
            lock_aspect_ratio_action = MaterialIconAction(
                icon_name="aspect_ratio", tooltip="Lock Aspect Ratio", checkable=True, parent=self
            )
            self.toolbar.components.add_safe("lock_aspect_ratio", lock_aspect_ratio_action)
            self.toolbar.get_bundle("mouse_interaction").add_action("lock_aspect_ratio")
            lock_aspect_ratio_action.action.toggled.connect(
                lambda checked: self.setProperty("lock_aspect_ratio", checked)
            )
            lock_aspect_ratio_action.action.setChecked(True)

            # Autorange Action
            self.toolbar.add_bundle(image_autorange(self.toolbar.components))
            action = self.toolbar.components.get_action("image_autorange")
            action.actions["mean"].action.toggled.connect(
                lambda checked: self.toggle_autorange(checked, mode="mean")
            )
            action.actions["max"].action.toggled.connect(
                lambda checked: self.toggle_autorange(checked, mode="max")
            )

            # Colorbar Actions
            self.toolbar.add_bundle(image_colorbar(self.toolbar.components))

            self.toolbar.connect_bundle(
                "image_colorbar",
                ImageColorbarConnection(self.toolbar.components, target_widget=self),
            )

            # Image Processing Actions
            self.toolbar.add_bundle(image_processing(self.toolbar.components))
            self.toolbar.connect_bundle(
                "image_processing",
                ImageProcessingConnection(self.toolbar.components, target_widget=self),
            )

            # ROI Manager Action
            self.toolbar.components.add_safe(
                "roi_mgr",
                MaterialIconAction(
                    icon_name="view_list", tooltip="ROI Manager", checkable=True, parent=self
                ),
            )
            self.toolbar.get_bundle("axis_popup").add_action("roi_mgr")
            self.toolbar.components.get_action("roi_mgr").action.triggered.connect(
                self.show_roi_manager_popup
            )
        except Exception as e:
            logger.error(f"Error initializing toolbar: {e}")

    ########################################
    # ROI Gui Manager
    def add_side_menus(self):
        super().add_side_menus()

        roi_mgr = ROIPropertyTree(parent=self, image_widget=self)
        self.side_panel.add_menu(
            action_id="roi_mgr",
            icon_name="view_list",
            tooltip="ROI Manager",
            widget=roi_mgr,
            title="ROI Manager",
        )

    def show_roi_manager_popup(self):
        roi_action = self.toolbar.components.get_action("roi_mgr").action
        if self.roi_manager_dialog is None or not self.roi_manager_dialog.isVisible():
            self.roi_mgr = ROIPropertyTree(parent=self, image_widget=self)
            self.roi_manager_dialog = QDialog(modal=False)
            self.roi_manager_dialog.layout = QVBoxLayout(self.roi_manager_dialog)
            self.roi_manager_dialog.layout.addWidget(self.roi_mgr)
            self.roi_manager_dialog.finished.connect(self._roi_mgr_closed)
            self.roi_manager_dialog.show()
            roi_action.setChecked(True)
        else:
            self.roi_manager_dialog.raise_()
            self.roi_manager_dialog.activateWindow()
            roi_action.setChecked(True)

    def _roi_mgr_closed(self):
        self.roi_mgr.close()
        self.roi_mgr.deleteLater()
        self.roi_manager_dialog.close()
        self.roi_manager_dialog.deleteLater()
        self.roi_manager_dialog = None
        self.toolbar.components.get_action("roi_mgr").action.setChecked(False)

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
        autorange_state = self.layer_manager["main"].image.autorange
        if enabled:
            if self._color_bar:
                if self.config.color_bar == "full":
                    self.cleanup_histogram_lut_item(self._color_bar)
                self.plot_widget.removeItem(self._color_bar)
                self._color_bar = None

            def disable_autorange():
                print("Disabling autorange")
                self.setProperty("autorange", False)

            if style == "simple":
                self._color_bar = pg.ColorBarItem(colorMap=self.config.color_map)
                self._color_bar.setImageItem(self.layer_manager["main"].image)
                self._color_bar.sigLevelsChangeFinished.connect(disable_autorange)

            elif style == "full":
                self._color_bar = pg.HistogramLUTItem()
                self._color_bar.setImageItem(self.layer_manager["main"].image)
                self._color_bar.gradient.loadPreset(self.config.color_map)
                self._color_bar.sigLevelsChanged.connect(disable_autorange)

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
    # Static rois with roi manager

    def add_roi(
        self,
        kind: Literal["rect", "circle", "ellipse"] = "rect",
        name: str | None = None,
        line_width: int | None = 5,
        pos: tuple[float, float] | None = (10, 10),
        size: tuple[float, float] | None = (50, 50),
        movable: bool = True,
        **pg_kwargs,
    ) -> RectangularROI | CircularROI:
        """
        Add a ROI to the image.

        Args:
            kind(str): The type of ROI to add. Options are "rect" or "circle".
            name(str): The name of the ROI.
            line_width(int): The line width of the ROI.
            pos(tuple): The position of the ROI.
            size(tuple): The size of the ROI.
            movable(bool): Whether the ROI is movable.
            **pg_kwargs: Additional arguments for the ROI.

        Returns:
            RectangularROI | CircularROI: The created ROI object.
        """
        if name is None:
            name = f"ROI_{len(self.roi_controller.rois) + 1}"
        if kind == "rect":
            roi = RectangularROI(
                pos=pos,
                size=size,
                parent_image=self,
                line_width=line_width,
                label=name,
                movable=movable,
                **pg_kwargs,
            )
        elif kind == "circle":
            roi = CircularROI(
                pos=pos,
                size=size,
                parent_image=self,
                line_width=line_width,
                label=name,
                movable=movable,
                **pg_kwargs,
            )
        elif kind == "ellipse":
            roi = EllipticalROI(
                pos=pos,
                size=size,
                parent_image=self,
                line_width=line_width,
                label=name,
                movable=movable,
                **pg_kwargs,
            )
        else:
            raise ValueError("kind must be 'rect' or 'circle'")

        # Add to plot and controller (controller assigns color)
        self.plot_item.addItem(roi)
        self.roi_controller.add_roi(roi)
        return roi

    def remove_roi(self, roi: int | str):
        """Remove an ROI by index or label via the ROIController."""
        if isinstance(roi, int):
            self.roi_controller.remove_roi_by_index(roi)
        elif isinstance(roi, str):
            self.roi_controller.remove_roi_by_name(roi)
        else:
            raise ValueError("roi must be an int index or str name")

    def _add_roi_plots(self):
        """
        Initialize the ROI plots and side panels.
        """
        # Create ROI plot widgets
        self.x_roi = ImageROIPlot(parent=self)
        self.x_roi.plot_item.setXLink(self.plot_item)
        self.y_roi = ImageROIPlot(parent=self)
        self.y_roi.plot_item.setYLink(self.plot_item)
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

    def toggle_roi_panels(self, checked: bool):
        """
        Show or hide the ROI panels based on the test action toggle state.

        Args:
            checked (bool): Whether the test action is checked.
        """
        if checked:
            # Show the ROI panels
            self.hook_crosshair()
            self.side_panel_x.show_panel(self.x_panel_index)
            self.side_panel_y.show_panel(self.y_panel_index)
            self.crosshair.coordinatesChanged2D.connect(self.update_image_slices)
            self.image_updated.connect(self.update_image_slices)
        else:
            self.unhook_crosshair()
            # Hide the ROI panels
            self.side_panel_x.hide_panel()
            self.side_panel_y.hide_panel()
            self.image_updated.disconnect(self.update_image_slices)

    @SafeSlot()
    def update_image_slices(self, coordinates: tuple[int, int, int] = None):
        """
        Update the image slices based on the crosshair position.

        Args:
            coordinates(tuple): The coordinates of the crosshair.
        """
        if coordinates is None:
            # Try to get coordinates from crosshair position (like in crosshair mouse_moved)
            if (
                hasattr(self, "crosshair")
                and hasattr(self.crosshair, "v_line")
                and hasattr(self.crosshair, "h_line")
            ):
                x = int(round(self.crosshair.v_line.value()))
                y = int(round(self.crosshair.h_line.value()))
            else:
                return
        else:
            x = coordinates[1]
            y = coordinates[2]
        image_item = self.layer_manager["main"].image
        image = image_item.image
        if image is None:
            return
        max_row, max_col = image.shape[0] - 1, image.shape[1] - 1
        row, col = x, y
        if not (0 <= row <= max_row and 0 <= col <= max_col):
            return
        # Horizontal slice
        h_slice = image[:, col]
        x_pixel_indices = np.arange(h_slice.shape[0])
        if image_item.image_transform is None:
            h_world_x = np.arange(h_slice.shape[0])
        else:
            h_world_x = [
                image_item.image_transform.map(xi + 0.5, col + 0.5)[0] for xi in x_pixel_indices
            ]
        self.x_roi.plot_item.clear()
        self.x_roi.plot_item.plot(h_world_x, h_slice, pen=pg.mkPen(self.x_roi.curve_color, width=3))

        # Vertical slice
        v_slice = image[row, :]
        y_pixel_indices = np.arange(v_slice.shape[0])
        if image_item.image_transform is None:
            v_world_y = np.arange(v_slice.shape[0])
        else:
            v_world_y = [
                image_item.image_transform.map(row + 0.5, yi + 0.5)[1] for yi in y_pixel_indices
            ]
        self.y_roi.plot_item.clear()
        self.y_roi.plot_item.plot(v_slice, v_world_y, pen=pg.mkPen(self.y_roi.curve_color, width=3))

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
            for layer in self.layer_manager:
                if not layer.sync.color_map:
                    continue
                layer.image.color_map = value

            if self._color_bar:
                if self.config.color_bar == "simple":
                    self._color_bar.setColorMap(value)
                elif self.config.color_bar == "full":
                    self._color_bar.gradient.loadPreset(value)
        except ValidationError:
            return

    @SafeProperty("QPointF")
    def v_range(self) -> QPointF:
        """
        Set the v_range of the main image.
        """
        vmin, vmax = self.layer_manager["main"].image.v_range
        return QPointF(vmin, vmax)

    @v_range.setter
    def v_range(self, value: tuple | list | QPointF):
        """
        Set the v_range of the main image.

        Args:
            value(tuple | list | QPointF): The range of values to set.
        """
        self._set_vrange(value, disable_autorange=True)

    def _set_vrange(self, value: tuple | list | QPointF, disable_autorange: bool = True):
        if isinstance(value, (tuple, list)):
            value = self._tuple_to_qpointf(value)

        vmin, vmax = value.x(), value.y()

        for layer in self.layer_manager:
            if not layer.sync.v_range:
                continue
            layer.image.set_v_range((vmin, vmax), disable_autorange=disable_autorange)

        # propagate to colorbar if exists
        if self._color_bar:
            if self.config.color_bar == "simple":
                self._color_bar.setLevels(low=vmin, high=vmax)
            elif self.config.color_bar == "full":
                self._color_bar.setLevels(min=vmin, max=vmax)
                self._color_bar.setHistogramRange(vmin - 0.1 * vmin, vmax + 0.1 * vmax)

        # self.toolbar.components.get_action("image_autorange").set_state_all(False)

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
    # Autorange + Colorbar sync

    @SafeProperty(bool)
    def autorange(self) -> bool:
        """
        Whether autorange is enabled.
        """

        # FIXME: this should be made more general
        return self.layer_manager["main"].image.autorange

    @autorange.setter
    def autorange(self, enabled: bool):
        """
        Set autorange.

        Args:
            enabled(bool): Whether to enable autorange.
        """
        self._set_autorange(enabled)

    def _set_autorange(self, enabled: bool, sync: bool = True):
        """
        Set the autorange for all layers.

        Args:
            enabled(bool): Whether to enable autorange.
            sync(bool): Whether to synchronize the autorange state across all layers.
        """
        print(f"Setting autorange to {enabled}")
        for layer in self.layer_manager:
            if not layer.sync.autorange:
                continue
            layer.image.autorange = enabled
            if enabled and layer.image.raw_data is not None:
                layer.image.apply_autorange()
                # if sync:
                self._sync_colorbar_levels()
        self._sync_autorange_switch()
        print(f"Autorange set to {enabled}")

    @SafeProperty(str)
    def autorange_mode(self) -> str:
        """
        Autorange mode.

        Options:
            - "max": Use the maximum value of the image for autoranging.
            - "mean": Use the mean value of the image for autoranging.

        """
        return self.layer_manager["main"].image.autorange_mode

    @autorange_mode.setter
    def autorange_mode(self, mode: str):
        """
        Set the autorange mode.

        Args:
            mode(str): The autorange mode. Options are "max" or "mean".
        """
        print(f"Setting autorange mode to {mode}")
        # for qt Designer
        if mode not in ["max", "mean"]:
            return
        for layer in self.layer_manager:
            if not layer.sync.autorange_mode:
                continue
            layer.image.autorange_mode = mode

        self._sync_autorange_switch()

    @SafeSlot(bool, str, bool)
    def toggle_autorange(self, enabled: bool, mode: str):
        """
        Toggle autorange.

        Args:
            enabled(bool): Whether to enable autorange.
            mode(str): The autorange mode. Options are "max" or "mean".
        """
        if not self.layer_manager:
            return
        print(f"Toggling autorange to {enabled} with mode {mode}")
        for layer in self.layer_manager:
            if layer.sync.autorange:
                layer.image.autorange = enabled
            if layer.sync.autorange_mode:
                layer.image.autorange_mode = mode

            if not enabled:
                continue
            # We only need to apply autorange if we enabled it
            layer.image.apply_autorange()

        self._sync_colorbar_levels()

    def _sync_autorange_switch(self):
        """
        Synchronize the autorange switch with the current autorange state and mode if changed from outside.
        """
        action: SwitchableToolBarAction = self.toolbar.components.get_action("image_autorange")  # type: ignore
        with action.signal_blocker():
            action.set_default_action(f"{self.layer_manager['main'].image.autorange_mode}")
            action.set_state_all(self.layer_manager["main"].image.autorange)

    def _sync_colorbar_levels(self):
        """Immediately propagate current levels to the active colorbar."""

        if not self._color_bar:
            return

        total_vrange = (0, 0)
        for layer in self.layer_manager:
            if not layer.sync.v_range:
                continue
            img = layer.image
            total_vrange = (min(total_vrange[0], img.v_min), max(total_vrange[1], img.v_max))

        self._color_bar.blockSignals(True)
        self._set_vrange(total_vrange, disable_autorange=False)  # type: ignore
        self._color_bar.blockSignals(False)

    def _sync_colorbar_actions(self):
        """
        Synchronize the colorbar actions with the current colorbar state.
        """
        colorbar_switch: SwitchableToolBarAction = self.toolbar.components.get_action(
            "image_colorbar_switch"
        )
        with colorbar_switch.signal_blocker():
            if self._color_bar is not None:
                colorbar_switch.set_default_action(f"{self.config.color_bar}_colorbar")
                colorbar_switch.set_state_all(True)
            else:
                colorbar_switch.set_state_all(False)

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
        Cleanup the widget.
        """

        # Remove all ROIs
        rois = self.rois
        for roi in rois:
            roi.remove()

        # Colorbar Cleanup
        if self._color_bar:
            if self.config.color_bar == "full":
                self.cleanup_histogram_lut_item(self._color_bar)
            if self.config.color_bar == "simple":
                self.plot_widget.removeItem(self._color_bar)
                self._color_bar.deleteLater()
            self._color_bar = None

        # Popup cleanup
        if self.roi_manager_dialog is not None:
            self.roi_manager_dialog.reject()
            self.roi_manager_dialog = None

        # ROI plots cleanup
        if self.x_roi is not None:
            self.x_roi.cleanup_pyqtgraph()
        if self.y_roi is not None:
            self.y_roi.cleanup_pyqtgraph()

        self.layer_manager.clear()
        self.layer_manager = None

        super().cleanup()
