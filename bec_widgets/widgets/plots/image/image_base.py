from __future__ import annotations

from typing import Literal

import numpy as np
import pyqtgraph as pg
from bec_lib import bec_logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from qtpy.QtCore import QPointF, Signal, SignalInstance
from qtpy.QtWidgets import QDialog, QVBoxLayout

from bec_widgets.utils.colors import Colors
from bec_widgets.utils.container_utils import WidgetContainerUtils
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.side_panel import SidePanel
from bec_widgets.utils.toolbars.actions import MaterialIconAction, SwitchableToolBarAction
from bec_widgets.widgets.plots.image.bec_histogram_lut_item import (
    BECColorBarItem,
    BECHistogramLUTItem,
)
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

        color_map = getattr(getattr(self.parent, "config", None), "color_map", None)
        if color_map:
            image.color_map = color_map

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

    MAX_TICKS_COLORBAR = 10

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
        # The pinned array coordinates are tracked at widget level so the pinned
        # profiles can refresh regardless of the crosshair lifecycle.
        self.crosshair_coordinates_pinned.connect(self._on_pin_coordinates)
        self.crosshair_pin_cleared.connect(self._on_pin_cleared)
        # Live and pinned crosshair coordinates share one refresh mechanism; the
        # live label otherwise only refreshes on mouse moves, which would leave a
        # stale intensity under a streaming image.
        self.image_updated.connect(self._on_image_updated_refresh)

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

    @SafeSlot(tuple)
    def _on_pin_coordinates(self, coordinates: tuple) -> None:
        """Track the pinned array coordinates.

        Args:
            coordinates (tuple): ``(name, row, col)`` as emitted by the crosshair.
        """
        self._pinned_slice_coords = (coordinates[1], coordinates[2])

    @SafeSlot()
    def _on_pin_cleared(self) -> None:
        """Forget the pinned coordinates once the pin is removed."""
        self._pinned_slice_coords = None

    @SafeSlot()
    def _on_image_updated_refresh(self) -> None:
        """Refresh crosshair labels and pinned profiles after the image changed.

        The live and the pinned coordinate use the same mechanism: each label and
        each profile is rebuilt from its coordinate against the current image.
        """
        if self.crosshair is not None:
            self.crosshair.update_on_image_change()
        else:
            self._update_detached_pin_label()
        self.update_image_slices(pinned=True)

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
        vrange: tuple[float, float] | None = None,
    ):
        """
        Enable the colorbar and switch types of colorbars.

        Args:
            enabled(bool): Whether to enable the colorbar.
            style(Literal["full", "simple"]): The type of colorbar to enable.
            vrange(tuple): The range of values to use for the colorbar.
        """
        if enabled and style not in ("full", "simple"):
            raise ValueError(f"Invalid colorbar style '{style}'; use 'full' or 'simple'.")

        main_image = self.layer_manager["main"].image
        autorange_state = main_image.autorange
        saved_vrange = main_image.v_range
        if enabled:
            self._remove_color_bar()

            def disable_autorange():
                logger.info("Disabling autorange")
                self.setProperty("autorange", False)

            if style == "simple":
                cmap = Colors.get_colormap(self.config.color_map)
                self._color_bar = BECColorBarItem(colorMap=cmap)
                self._color_bar.setImageItem(main_image)
                self._color_bar.sigLevelsChangeFinished.connect(disable_autorange)
                self.config.color_bar = "simple"

            elif style == "full":
                self._color_bar = BECHistogramLUTItem()
                self._color_bar.setImageItem(main_image)
                self.config.color_bar = "full"
                self._apply_colormap_to_colorbar(self.config.color_map)
                region = self._color_bar.region

                def disable_autorange_on_drag():
                    # sigLevelsChanged also fires on every rendered frame:
                    # HistogramLUTItem.imageChanged snaps the region to the
                    # current image levels on each setImage. Only a mouse drag
                    # of the region (or one of its edge lines) is user intent.
                    if region.moving or any(line.moving for line in region.lines):
                        disable_autorange()

                self._color_bar.sigLevelsChanged.connect(disable_autorange_on_drag)

            # Custom colorbar context menu (replaces pyqtgraph's default menus).
            self._color_bar.sigColorMapChangeRequested.connect(self._set_colormap_from_menu)
            self._color_bar.sigColorLevelsChangeRequested.connect(self._set_vrange_from_menu)
            self._color_bar.sigAutoLevelsRequested.connect(self._autorange_from_menu)

            self.plot_widget.addItem(self._color_bar, row=0, col=1)
        else:
            self._remove_color_bar()
            self.config.color_bar = None

        self.autorange = autorange_state
        if enabled and not autorange_state:
            # Attaching a colorbar re-levels the image (HistogramLUTItem's
            # setImageItem auto-levels); restore the previous manual levels so
            # switching between colorbar styles keeps the levels in sync.
            self._set_vrange(saved_vrange, disable_autorange=False)
        self._sync_colorbar_actions()

        if vrange:  # should be at the end to disable the autorange if defined
            self.v_range = vrange

    def _remove_color_bar(self) -> None:
        """
        Remove the current colorbar from the plot and fully tear it down, including
        the parentless menus/dialogs it owns.
        """
        if self._color_bar is None:
            return
        if isinstance(self._color_bar, (BECHistogramLUTItem, BECColorBarItem)):
            self._color_bar.cleanup()
        self.plot_widget.removeItem(self._color_bar)
        self._color_bar.deleteLater()
        self._color_bar = None

    def _apply_colormap_to_colorbar(self, color_map: str) -> None:
        if not self._color_bar:
            return

        cmap = Colors.get_colormap(color_map)

        if self.config.color_bar == "simple":
            self._color_bar.setColorMap(cmap)
            return

        if self.config.color_bar != "full":
            return

        gradient = getattr(self._color_bar, "gradient", None)
        if gradient is None:
            return

        positions = np.linspace(0.0, 1.0, self.MAX_TICKS_COLORBAR)
        colors = cmap.map(positions, mode="byte")

        colors = np.asarray(colors)
        if colors.ndim != 2:
            return
        if colors.shape[1] == 3:  # add alpha
            alpha = np.full((colors.shape[0], 1), 255, dtype=colors.dtype)
            colors = np.concatenate([colors, alpha], axis=1)

        ticks = [(float(p), tuple(int(x) for x in c)) for p, c in zip(positions, colors)]
        state = {"mode": "rgb", "ticks": ticks}
        gradient.restoreState(state)

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

        # Persistent live profile curves (updated in place so a pinned reference
        # curve is not wiped on every crosshair move) and the pinned curves that
        # follow the image data at a fixed pixel.
        self.x_roi_curve = None
        self.y_roi_curve = None
        self.x_roi_pinned = None
        self.y_roi_pinned = None
        # Pinned pixel (array indices) for the pinned profile refreshes.
        self._pinned_slice_coords: tuple[int, int] | None = None
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
            # Clicking pins the X/Y profiles at a fixed pixel for comparison.
            self.crosshair.coordinatesPinned2D.connect(self.pin_image_slices)
            self.crosshair.pinCleared.connect(self.clear_pinned_slices)
            self.image_updated.connect(self.update_image_slices)
            self.update_image_slices()
            # If a pin survived a previous toggle, rebuild its profiles now that
            # the consumer slots are connected again.
            if self.crosshair.pinned_pos is not None:
                self.crosshair.reemit_pin()
        else:
            self.unhook_crosshair()
            # Hide the ROI panels (the crosshair is destroyed, so its pin signals
            # disconnect automatically; just drop the pinned reference curves).
            self.clear_pinned_slices()
            self.side_panel_x.hide_panel()
            self.side_panel_y.hide_panel()
            self.image_updated.disconnect(self.update_image_slices)

    @SafeSlot()
    def update_image_slices(
        self, coordinates: tuple[int, int, int] | None = None, *, pinned: bool = False
    ):
        """
        Update the X/Y profile curves at a pixel position.

        The live crosshair and the pinned marker share this logic; ``pinned``
        selects which pair of curves is updated and how it is styled. The live
        pixel comes from ``coordinates`` (or the crosshair lines), the pinned
        pixel is the stored pin position.

        Args:
            coordinates(tuple): ``(name, row, col)`` pixel coordinates for the
                live curves; ignored for the pinned curves.
            pinned(bool): Update the pinned reference curves instead of the live ones.
        """
        image_item = self.layer_manager["main"].image
        image = image_item.image
        if image is not None and image.ndim != 2:
            self.clear_image_slices()
            return

        if pinned:
            if self._pinned_slice_coords is None:
                return
            row, col = self._pinned_slice_coords
        elif coordinates is not None:
            row, col = coordinates[1], coordinates[2]
        elif (
            hasattr(self, "crosshair")
            and hasattr(self.crosshair, "v_line")
            and hasattr(self.crosshair, "h_line")
        ):
            # Fall back to the crosshair line positions (like crosshair mouse_moved).
            row = int(round(self.crosshair.v_line.value()))
            col = int(round(self.crosshair.h_line.value()))
        else:
            return

        slices = self._compute_image_slices(image_item, row, col)
        if slices is None:
            return
        h_world_x, h_slice, v_world_y, v_slice = slices

        # Curves are persistent and updated in place (rather than clear()+plot())
        # so the other pair survives every refresh.
        if pinned:
            if self.x_roi_pinned is None:
                # Solid pen on purpose: Qt's dash stroker on a many-segment profile
                # curve is 10-20x more expensive to paint and dominates the whole
                # panel repaint.
                pen = pg.mkPen("#f2c037", width=2)
                self.x_roi_pinned = self.x_roi.plot_item.plot(h_world_x, h_slice, pen=pen)
                self.y_roi_pinned = self.y_roi.plot_item.plot(v_slice, v_world_y, pen=pen)
                # Keep the pinned styling when the ROI plots re-pen on theme change.
                self.x_roi_pinned.is_pinned_reference = True
                self.y_roi_pinned.is_pinned_reference = True
            else:
                self.x_roi_pinned.setData(h_world_x, h_slice)
                self.y_roi_pinned.setData(v_slice, v_world_y)
            return

        if self.x_roi_curve is None:
            self.x_roi_curve = self.x_roi.plot_item.plot(
                h_world_x, h_slice, pen=pg.mkPen(self.x_roi.curve_color, width=3)
            )
            self.y_roi_curve = self.y_roi.plot_item.plot(
                v_slice, v_world_y, pen=pg.mkPen(self.y_roi.curve_color, width=3)
            )
        else:
            self.x_roi_curve.setData(h_world_x, h_slice)
            self.y_roi_curve.setData(v_slice, v_world_y)

    def _compute_image_slices(self, image_item, row: int, col: int):
        """Compute the horizontal/vertical profile slices through the image at (row, col).

        Args:
            image_item: The image item to slice.
            row (int): Pixel index along the image's first axis.
            col (int): Pixel index along the image's second axis.

        Returns:
            tuple | None: ``(h_world_x, h_slice, v_world_y, v_slice)`` in world coordinates,
            or ``None`` if the image is not scalar 2-D or the pixel is out of bounds.
        """
        image = image_item.image
        if image is None or image.ndim != 2:
            return None
        max_row, max_col = image.shape[0] - 1, image.shape[1] - 1
        if not (0 <= row <= max_row and 0 <= col <= max_col):
            return None
        # Horizontal slice (varies along the first axis at the fixed column)
        h_slice = image[:, col]
        x_pixel_indices = np.arange(h_slice.shape[0])
        if image_item.image_transform is None:
            h_world_x = np.arange(h_slice.shape[0])
        else:
            h_world_x = [
                image_item.image_transform.map(xi + 0.5, col + 0.5)[0] for xi in x_pixel_indices
            ]
        # Vertical slice (varies along the second axis at the fixed row)
        v_slice = image[row, :]
        y_pixel_indices = np.arange(v_slice.shape[0])
        if image_item.image_transform is None:
            v_world_y = np.arange(v_slice.shape[0])
        else:
            v_world_y = [
                image_item.image_transform.map(row + 0.5, yi + 0.5)[1] for yi in y_pixel_indices
            ]
        return h_world_x, h_slice, v_world_y, v_slice

    @SafeSlot()
    def clear_image_slices(self):
        """Remove live and pinned profile curves for an unsupported image."""
        if self.x_roi_curve is not None:
            self.x_roi.plot_item.removeItem(self.x_roi_curve)
            self.x_roi_curve = None
        if self.y_roi_curve is not None:
            self.y_roi.plot_item.removeItem(self.y_roi_curve)
            self.y_roi_curve = None
        self.clear_pinned_slices()

    @SafeSlot(tuple)
    def pin_image_slices(self, _coordinates: tuple):
        """Create or update the pinned profile curves at the pinned pixel.

        Args:
            _coordinates (tuple): ``(name, row, col)`` from ``coordinatesPinned2D``;
                the pixel itself is tracked by ``_on_pin_coordinates``.
        """
        self.update_image_slices(pinned=True)

    @SafeSlot()
    def clear_pinned_slices(self):
        """Remove the pinned profile curves, if present.

        The pinned coordinates are kept: the pin itself may still exist (e.g. the
        ROI panels were toggled off) and its label keeps following the image.
        """
        if self.x_roi_pinned is not None:
            self.x_roi.plot_item.removeItem(self.x_roi_pinned)
            self.x_roi_pinned = None
        if self.y_roi_pinned is not None:
            self.y_roi.plot_item.removeItem(self.y_roi_pinned)
            self.y_roi_pinned = None

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
                self._apply_colormap_to_colorbar(self.config.color_map)
        except ValidationError as exc:
            logger.warning(
                f"Colormap '{value}' is not available; keeping '{self.config.color_map}'. {exc}"
            )
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

        # Non-finite levels would crash pyqtgraph's colorbar
        if not (np.isfinite(vmin) and np.isfinite(vmax)):
            logger.warning(f"Ignoring non-finite v_range ({vmin}, {vmax}).")
            return

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

    @SafeSlot(str)
    def _set_colormap_from_menu(self, color_map: str):
        """Apply a colormap chosen from the colorbar context menu."""
        self.color_map = color_map

    @SafeSlot(object)
    def _set_vrange_from_menu(self, vrange: tuple[float, float]):
        """Apply explicit color levels requested from the colorbar context menu."""
        self._set_vrange(vrange, disable_autorange=True)

    @SafeSlot()
    def _autorange_from_menu(self):
        """Enable autorange (current mode) from the colorbar context menu."""
        self.autorange = True

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
        if not self.layer_manager:
            return False
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
        if not self.layer_manager:
            return
        for layer in self.layer_manager:
            if not layer.sync.autorange:
                continue
            layer.image.autorange = enabled
            if enabled and layer.image.raw_data is not None:
                layer.image.apply_autorange()
                # if sync:
                self._sync_colorbar_levels()
        self._sync_autorange_switch()
        logger.info(f"Autorange set to {enabled}")

    @SafeProperty(str)
    def autorange_mode(self) -> str:
        """
        Autorange mode.

        Options:
            - "max": Use the maximum value of the image for autoranging.
            - "mean": Use the mean value of the image for autoranging.

        """
        if not self.layer_manager:
            return "mean"
        return self.layer_manager["main"].image.autorange_mode

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
        if not self.layer_manager:
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
        if not self.layer_manager:
            return
        action: SwitchableToolBarAction = self.toolbar.components.get_action("image_autorange")  # type: ignore
        with action.signal_blocker():
            action.set_default_action(f"{self.layer_manager['main'].image.autorange_mode}")
            action.set_state_all(self.layer_manager["main"].image.autorange)

    def _sync_colorbar_levels(self):
        """Immediately propagate current levels to the active colorbar."""

        if not self._color_bar or not self.layer_manager:
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

    def cleanup(self):
        """
        Cleanup the widget.
        """
        self.toolbar.cleanup()

        # Remove all ROIs
        rois = self.rois
        for roi in rois:
            roi.remove()

        # Colorbar Cleanup
        self._remove_color_bar()

        # Popup cleanup
        if self.roi_manager_dialog is not None:
            self.roi_manager_dialog.reject()
            self.roi_manager_dialog = None

        # ROI plots cleanup
        if self.x_roi is not None:
            self.x_roi.cleanup_pyqtgraph()
        if self.y_roi is not None:
            self.y_roi.cleanup_pyqtgraph()

        if self.layer_manager is not None:
            self.layer_manager.clear()
            self.layer_manager = None

        super().cleanup()
