from __future__ import annotations

from typing import TYPE_CHECKING

import pyqtgraph as pg
from pyqtgraph import TextItem
from pyqtgraph import functions as fn
from pyqtgraph import mkPen
from qtpy import QtCore
from qtpy.QtCore import QObject, Signal

from bec_widgets import SafeProperty
from bec_widgets.utils import BECConnector, ConnectionConfig
from bec_widgets.utils.colors import Colors

if TYPE_CHECKING:
    from bec_widgets.widgets.plots.image.image import Image


class LabelAdorner:
    """Manages a TextItem label on top of any ROI, keeping it aligned."""

    def __init__(
        self,
        roi: BaseROI,
        anchor: tuple[int, int] = (0, 1),
        padding: int = 2,
        bg_color: str | tuple[int, int, int, int] = (0, 0, 0, 100),
        text_color: str | tuple[int, int, int, int] = "white",
    ):
        """
        Initializes a label overlay for a given region of interest (ROI), allowing for customization
        of text placement, padding, background color, and text color. Automatically attaches the label
        to the ROI and updates its position and content based on ROI changes.

        Args:
            roi: The region of interest to which the label will be attached.
            anchor: Tuple specifying the label's anchor relative to the ROI. Default is (0, 1).
            padding: Integer specifying the padding around the label's text. Default is 2.
            bg_color: RGBA tuple for the label's background color. Default is (0, 0, 0, 100).
            text_color: String specifying the color of the label's text. Default is "white".
        """
        self.roi = roi
        self.label = TextItem(anchor=anchor)
        self.padding = padding
        self.bg_rgba = bg_color
        self.text_color = text_color
        roi.addItem(self.label) if hasattr(roi, "addItem") else self.label.setParentItem(roi)
        # initial draw
        self._update_html(roi.label)
        self._reposition()
        # reconnect on geometry/name changes
        roi.sigRegionChanged.connect(self._reposition)
        if hasattr(roi, "nameChanged"):
            roi.nameChanged.connect(self._update_html)

    def _update_html(self, text: str):
        """
        Updates the HTML content of the label with the given text.

        Creates an HTML div with the configured background color, text color, and padding,
        then sets this HTML as the content of the label.

        Args:
            text (str): The text to display in the label.
        """
        html = (
            f'<div style="background: rgba{self.bg_rgba}; '
            f"font-weight:bold; color:{self.text_color}; "
            f'padding:{self.padding}px;">{text}</div>'
        )
        self.label.setHtml(html)

    def _reposition(self):
        """
        Repositions the label to align with the ROI's current position.

        This method is called whenever the ROI's position or size changes.
        It places the label at the bottom-left corner of the ROI's bounding rectangle.
        """
        # put at top-left corner of ROI’s bounding rect
        size = self.roi.state["size"]
        height = size[1]
        self.label.setPos(0, height)


class BaseROI(BECConnector):
    """Base class for all Region of Interest (ROI) implementations.

    This class serves as a mixin that provides common properties and methods for ROIs,
    including name, line color, and line width properties. It inherits from BECConnector
    to enable remote procedure call functionality.

    Attributes:
        RPC (bool): Flag indicating if remote procedure calls are enabled.
        PLUGIN (bool): Flag indicating if this class is a plugin.
        nameChanged (Signal): Signal emitted when the ROI name changes.
        penChanged (Signal): Signal emitted when the ROI pen (color/width) changes.
        USER_ACCESS (list): List of methods and properties accessible via RPC.
    """

    RPC = True
    PLUGIN = False

    nameChanged = Signal(str)
    penChanged = Signal()
    USER_ACCESS = [
        "label",
        "label.setter",
        "line_color",
        "line_color.setter",
        "line_width",
        "line_width.setter",
        "get_coordinates",
        "get_data_from_image",
        "set_position",
    ]

    def __init__(
        self,
        *,
        # BECConnector kwargs
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        parent_image: Image | None,
        # ROI-specific
        label: str | None = None,
        line_color: str | None = None,
        line_width: int = 5,
        # all remaining pg.*ROI kwargs (pos, size, pen, …)
        **pg_kwargs,
    ):
        """Base class for all modular ROIs.

        Args:
            label (str): Human-readable name shown in ROI Manager and labels.
            line_color (str | None, optional): Initial pen color. Defaults to None.
                Controller may override color later.
            line_width (int, optional): Initial pen width. Defaults to 15.
                Controller may override width later.
            config (ConnectionConfig | None, optional): Standard BECConnector argument. Defaults to None.
            gui_id (str | None, optional): Standard BECConnector argument. Defaults to None.
            parent_image (BECConnector | None, optional): Standard BECConnector argument. Defaults to None.
        """
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        self.config = config

        self.set_parent(parent_image)
        self.parent_plot_item = parent_image.plot_item
        object_name = label.replace("-", "_").replace(" ", "_") if label else None
        super().__init__(
            object_name=object_name,
            config=config,
            gui_id=gui_id,
            removable=True,
            invertible=True,
            **pg_kwargs,
        )

        self._label = label or "ROI"
        self._line_color = line_color or "#ffffff"
        self._line_width = line_width
        self._description = True
        self.setPen(mkPen(self._line_color, width=self._line_width))

    def set_parent(self, parent: Image):
        """
        Sets the parent image for this ROI.

        Args:
            parent (Image): The parent image object to associate with this ROI.
        """
        self.parent_image = parent

    def parent(self):
        """
        Gets the parent image associated with this ROI.

        Returns:
            Image: The parent image object, or None if no parent is set.
        """
        return self.parent_image

    @property
    def label(self) -> str:
        """
        Gets the display name of this ROI.

        Returns:
            str: The current name of the ROI.
        """
        return self._label

    @label.setter
    def label(self, new: str):
        """
        Sets the display name of this ROI.

        If the new name is different from the current name, this method updates
        the internal name, emits the nameChanged signal, and updates the object name.

        Args:
            new (str): The new name to set for the ROI.
        """
        if new != self._label:
            self._label = new
            self.nameChanged.emit(new)
            self.change_object_name(new)

    @property
    def line_color(self) -> str:
        """
        Gets the current line color of the ROI.

        Returns:
            str: The current line color as a string (e.g., hex color code).
        """
        return self._line_color

    @line_color.setter
    def line_color(self, value: str):
        """
        Sets the line color of the ROI.

        If the new color is different from the current color, this method updates
        the internal color value, updates the pen while preserving the line width,
        and emits the penChanged signal.

        Args:
            value (str): The new color to set for the ROI's outline (e.g., hex color code).
        """
        if value != self._line_color:
            self._line_color = value
            # update pen but preserve width
            self.setPen(mkPen(value, width=self._line_width))
            self.penChanged.emit()

    @property
    def line_width(self) -> int:
        """
        Gets the current line width of the ROI.

        Returns:
            int: The current line width in pixels.
        """
        return self._line_width

    @line_width.setter
    def line_width(self, value: int):
        """
        Sets the line width of the ROI.

        If the new width is different from the current width and is greater than 0,
        this method updates the internal width value, updates the pen while preserving
        the line color, and emits the penChanged signal.

        Args:
            value (int): The new width to set for the ROI's outline in pixels.
                Must be greater than 0.
        """
        if value != self._line_width and value > 0:
            self._line_width = value
            self.setPen(mkPen(self._line_color, width=value))
            self.penChanged.emit()

    @property
    def description(self) -> bool:
        """
        Gets whether ROI coordinates should be emitted with descriptive keys by default.

        Returns:
            bool: True if coordinates should include descriptive keys, False otherwise.
        """
        return self._description

    @description.setter
    def description(self, value: bool):
        """
        Sets whether ROI coordinates should be emitted with descriptive keys by default.

        This affects the default behavior of the get_coordinates method.

        Args:
            value (bool): True to emit coordinates with descriptive keys, False to emit
                as a simple tuple of values.
        """
        self._description = value

    def get_coordinates(self):
        """
        Gets the coordinates that define this ROI's position and shape.

        This is an abstract method that must be implemented by subclasses.
        Implementations should return either a dictionary with descriptive keys
        or a tuple of coordinates, depending on the value of self.description.

        Returns:
            dict or tuple: The coordinates defining the ROI's position and shape.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement get_coordinates()")

    def get_data_from_image(
        self, image_item: pg.ImageItem | None = None, returnMappedCoords: bool = False, **kwargs
    ):
        """Wrapper around `pyqtgraph.ROI.getArrayRegion`.

        Args:
            image_item (pg.ImageItem or None): The ImageItem to sample. If None, auto-detects
                the first `ImageItem` in the same GraphicsScene as this ROI.
            returnMappedCoords (bool): If True, also returns the coordinate array generated by
                *getArrayRegion*.
            **kwargs: Additional keyword arguments passed to *getArrayRegion* or *affineSlice*,
                such as `axes`, `order`, `shape`, etc.

        Returns:
            ndarray: Pixel data inside the ROI, or (data, coords) if *returnMappedCoords* is True.
        """
        if image_item is None:
            image_item = next(
                (
                    it
                    for it in self.scene().items()
                    if isinstance(it, pg.ImageItem) and it.image is not None
                ),
                None,
            )
        if image_item is None:
            raise RuntimeError("No ImageItem found in the current scene.")

        data = image_item.image  # the raw ndarray held by ImageItem
        return self.getArrayRegion(
            data, img=image_item, returnMappedCoords=returnMappedCoords, **kwargs
        )

    def add_scale_handle(self):
        return

    def set_position(self, x: float, y: float):
        """
        Sets the position of the ROI.

        Args:
            x (float): The x-coordinate of the new position.
            y (float): The y-coordinate of the new position.
        """
        self.setPos(x, y)

    def remove(self):
        # Delegate to controller first so that GUI managers stay in sync
        controller = getattr(self.parent_image, "roi_controller", None)
        if controller and self in controller.rois:
            controller.remove_roi(self)
            return  # controller will call back into this method once deregistered
        handles = self.handles
        for i in range(len(handles)):
            try:
                self.removeHandle(0)
            except IndexError:
                continue
        self.rpc_register.remove_rpc(self)
        self.parent_image.plot_item.removeItem(self)
        viewBox = self.parent_plot_item.vb
        viewBox.update()


class RectangularROI(BaseROI, pg.RectROI):
    """
    Defines a rectangular Region of Interest (ROI) with additional functionality.

    Provides tools for manipulating and extracting data from rectangular areas on
    images, includes support for GUI features and event-driven signaling.

    Attributes:
        edgesChanged (Signal): Signal emitted when the ROI edges change, providing
            the new ("top_left", "top_right", "bottom_left","bottom_right") coordinates.
        edgesReleased (Signal): Signal emitted when the ROI edges are released,
            providing the new ("top_left", "top_right", "bottom_left","bottom_right") coordinates.
    """

    edgesChanged = Signal(float, float, float, float)
    edgesReleased = Signal(float, float, float, float)

    def __init__(
        self,
        *,
        # pg.RectROI kwargs
        pos: tuple[float, float],
        size: tuple[float, float],
        pen=None,
        # BECConnector kwargs
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        parent_image: Image | None = None,
        # ROI specifics
        label: str | None = None,
        line_color: str | None = None,
        line_width: int = 5,
        resize_handles: bool = True,
        **extra_pg,
    ):
        """
        Initializes an instance with properties for defining a rectangular ROI with handles,
        configurations, and an auto-aligning label. Also connects a signal for region updates.

        Args:
            pos: Initial position of the ROI.
            size: Initial size of the ROI.
            pen: Defines the border appearance; can be color or style.
            config: Optional configuration details for the connection.
            gui_id: Optional identifier for the associated GUI element.
            parent_image: Optional parent object the ROI is related to.
            label: Optional label for identification within the context.
            line_color: Optional color of the ROI outline.
            line_width: Width of the ROI's outline in pixels.
            parent_plot_item: The plot item this ROI belongs to.
            **extra_pg: Additional keyword arguments specific to pg.RectROI.
        """
        super().__init__(
            config=config,
            gui_id=gui_id,
            parent_image=parent_image,
            label=label,
            line_color=line_color,
            line_width=line_width,
            pos=pos,
            size=size,
            pen=pen,
            **extra_pg,
        )

        self.sigRegionChanged.connect(self._on_region_changed)
        self.adorner = LabelAdorner(roi=self)
        self.hoverPen = fn.mkPen(color=(255, 0, 0), width=3, style=QtCore.Qt.DashLine)
        self.handleHoverPen = fn.mkPen("lime", width=4)

    def add_scale_handle(self):
        """
        Add scale handles at every corner and edge of the ROI.

        Corner handles are anchored to the centre for two-axis scaling.
        Edge handles are anchored to the midpoint of the opposite edge for single-axis scaling.
        """
        centre = [0.5, 0.5]

        # Corner handles – anchored to the centre for two-axis scaling
        self.addScaleHandle([0, 0], centre)  # top‑left
        self.addScaleHandle([1, 0], centre)  # top‑right
        self.addScaleHandle([0, 1], centre)  # bottom‑left
        self.addScaleHandle([1, 1], centre)  # bottom‑right

        # Edge handles – anchored to the midpoint of the opposite edge
        self.addScaleHandle([0.5, 0], [0.5, 1])  # top edge
        self.addScaleHandle([0.5, 1], [0.5, 0])  # bottom edge
        self.addScaleHandle([0, 0.5], [1, 0.5])  # left edge
        self.addScaleHandle([1, 0.5], [0, 0.5])  # right edge

        self.handlePen = fn.mkPen("#ffff00", width=5)  # bright yellow outline
        self.handleHoverPen = fn.mkPen("#00ffff", width=4)  # cyan, thicker when hovered
        self.handleBrush = (200, 200, 0, 120)  # semi-transparent fill
        self.handleHoverBrush = (0, 255, 255, 160)

    def _on_region_changed(self):
        """
        Handles ROI region change events.

        This method is called whenever the ROI's position or size changes.
        It calculates the new corner coordinates and emits the edgesChanged signal
        with the updated coordinates.
        """
        x0, y0 = self.pos().x(), self.pos().y()
        w, h = self.state["size"]
        self.edgesChanged.emit(x0, y0, x0 + w, y0 + h)
        viewBox = self.parent_plot_item.vb
        viewBox.update()

    def mouseDragEvent(self, ev):
        """
        Handles mouse drag events on the ROI.

        This method extends the parent class implementation to emit the edgesReleased
        signal when the mouse drag is finished, providing the final coordinates of the ROI.

        Args:
            ev: The mouse event object containing information about the drag operation.
        """
        super().mouseDragEvent(ev)
        if ev.isFinish():
            x0, y0 = self.pos().x(), self.pos().y()
            w, h = self.state["size"]
            self.edgesReleased.emit(x0, y0, x0 + w, y0 + h)

    def get_coordinates(self, typed: bool | None = None) -> dict | tuple:
        """
        Returns the coordinates of a rectangle's corners. Supports returning them
        as either a dictionary with descriptive keys or a tuple of coordinates.

        Args:
            typed (bool | None): If True, returns coordinates as a dictionary with
                descriptive keys. If False, returns them as a tuple. Defaults to
                the value of `self.description`.

        Returns:
            dict | tuple: The rectangle's corner coordinates, where the format
                depends on the `typed` parameter.
        """
        if typed is None:
            typed = self.description

        x0, y0 = self.pos().x(), self.pos().y()
        w, h = self.state["size"]
        x1, y1 = x0 + w, y0 + h
        if typed:
            return {
                "bottom_left": (x0, y0),
                "bottom_right": (x1, y0),
                "top_left": (x0, y1),
                "top_right": (x1, y1),
            }
        return ((x0, y0), (x1, y0), (x0, y1), (x1, y1))

    def _lookup_scene_image(self):
        """
        Searches for an image in the current scene.

        This helper method iterates through all items in the scene and returns
        the first pg.ImageItem that has a non-None image property.

        Returns:
            numpy.ndarray or None: The image from the first found ImageItem,
            or None if no suitable image is found.
        """
        for it in self.scene().items():
            if isinstance(it, pg.ImageItem) and it.image is not None:
                return it.image
        return None


class CircularROI(BaseROI, pg.CircleROI):
    """Circular Region of Interest with center/diameter tracking and auto-labeling.

    This class extends the BaseROI and pg.CircleROI classes to provide a circular ROI
    that emits signals when its center or diameter changes, and includes an auto-aligning
    label for visual identification.

    Attributes:
        centerChanged (Signal): Signal emitted when the ROI center or diameter changes,
            providing the new (center_x, center_y, diameter) values.
        centerReleased (Signal): Signal emitted when the ROI is released after dragging,
            providing the final (center_x, center_y, diameter) values.
    """

    centerChanged = Signal(float, float, float)
    centerReleased = Signal(float, float, float)

    def __init__(
        self,
        *,
        pos,
        size,
        pen=None,
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        parent_image: Image | None = None,
        label: str | None = None,
        line_color: str | None = None,
        line_width: int = 5,
        **extra_pg,
    ):
        """
        Initializes a circular ROI with the specified properties.

        Creates a circular ROI at the given position and with the given size,
        connects signals for tracking changes, and attaches an auto-aligning label.

        Args:
            pos: Initial position of the ROI as [x, y].
            size: Initial size of the ROI as [diameter, diameter].
            pen: Defines the border appearance; can be color or style.
            config (ConnectionConfig | None, optional): Configuration for BECConnector. Defaults to None.
            gui_id (str | None, optional): Identifier for the GUI element. Defaults to None.
            parent_image (BECConnector | None, optional): Parent image object. Defaults to None.
            label (str | None, optional): Display name for the ROI. Defaults to None.
            line_color (str | None, optional): Color of the ROI outline. Defaults to None.
            line_width (int, optional): Width of the ROI outline in pixels. Defaults to 3.
            parent_plot_item: The plot item this ROI belongs to.
            **extra_pg: Additional keyword arguments for pg.CircleROI.
        """
        super().__init__(
            config=config,
            gui_id=gui_id,
            parent_image=parent_image,
            label=label,
            line_color=line_color,
            line_width=line_width,
            pos=pos,
            size=size,
            pen=pen,
            **extra_pg,
        )
        self.sigRegionChanged.connect(self._on_region_changed)
        self._adorner = LabelAdorner(self)

    def _on_region_changed(self):
        """
        Handles ROI region change events.

        This method is called whenever the ROI's position or size changes.
        It calculates the center coordinates and diameter of the circle and
        emits the centerChanged signal with these values.
        """
        d = self.state["size"][0]
        cx = self.pos().x() + d / 2
        cy = self.pos().y() + d / 2
        self.centerChanged.emit(cx, cy, d)
        viewBox = self.parent_plot_item.getViewBox()
        viewBox.update()

    def mouseDragEvent(self, ev):
        """
        Handles mouse drag events on the ROI.

        This method extends the parent class implementation to emit the centerReleased
        signal when the mouse drag is finished, providing the final center coordinates
        and diameter of the circular ROI.

        Args:
            ev: The mouse event object containing information about the drag operation.
        """
        super().mouseDragEvent(ev)
        if ev.isFinish():
            d = self.state["size"][0]
            cx = self.pos().x() + d / 2
            cy = self.pos().y() + d / 2
            self.centerReleased.emit(cx, cy, d)

    def get_coordinates(self, typed: bool | None = None) -> dict | tuple:
        """
        Calculates and returns the coordinates and size of an object, either as a
        typed dictionary or as a tuple.

        Args:
            typed (bool | None): If True, returns coordinates as a dictionary. Defaults
                to None, which utilizes the object's description value.

        Returns:
            dict: A dictionary with keys 'center_x', 'center_y', 'diameter', and 'radius'
                if `typed` is True.
            tuple: A tuple containing (center_x, center_y, diameter, radius) if `typed` is False.
        """
        if typed is None:
            typed = self.description

        d = self.state["size"][0]
        cx = self.pos().x() + d / 2
        cy = self.pos().y() + d / 2

        if typed:
            return {"center_x": cx, "center_y": cy, "diameter": d, "radius": d / 2}
        return (cx, cy, d, d / 2)

    def _lookup_scene_image(self) -> pg.ImageItem | None:
        """
        Retrieves an image from the scene items if available.

        Iterates over all items in the scene and checks if any of them are of type
        `pg.ImageItem` and have a non-None image. If such an item is found, its image
        is returned.

        Returns:
            pg.ImageItem or None: The first found ImageItem with a non-None image,
            or None if no suitable image is found.
        """
        for it in self.scene().items():
            if isinstance(it, pg.ImageItem) and it.image is not None:
                return it.image
        return None


class ROIController(QObject):
    """Manages a collection of ROIs (Regions of Interest) with palette-assigned colors.

    Handles creating, adding, removing, and managing ROI instances. Supports color assignment
    from a colormap, and provides utility methods to access and manipulate ROIs.

    Attributes:
        roiAdded (Signal): Emits the new ROI instance when added.
        roiRemoved (Signal): Emits the removed ROI instance when deleted.
        cleared (Signal): Emits when all ROIs are removed.
        paletteChanged (Signal): Emits the new colormap name when updated.
        _colormap (str): Name of the colormap used for ROI colors.
        _rois (list[BaseROI]): Internal list storing currently managed ROIs.
        _colors (list[str]): Internal list of colors for the ROIs.
    """

    roiAdded = Signal(object)  # emits the new ROI instance
    roiRemoved = Signal(object)  # emits the removed ROI instance
    cleared = Signal()  # emits when all ROIs are removed
    paletteChanged = Signal(str)  # emits new colormap name

    def __init__(self, colormap="viridis"):
        """
        Initializes the ROI controller with the specified colormap.

        Sets up internal data structures for managing ROIs and their colors.

        Args:
            colormap (str, optional): The name of the colormap to use for ROI colors.
                Defaults to "viridis".
        """
        super().__init__()
        self._colormap = colormap
        self._rois: list[BaseROI] = []
        self._colors: list[str] = []
        self._rebuild_color_buffer()

    def _rebuild_color_buffer(self):
        """
        Regenerates the color buffer for ROIs.

        This internal method creates a new list of colors based on the current colormap
        and the number of ROIs. It ensures there's always one more color than the number
        of ROIs to allow for adding a new ROI without regenerating the colors.
        """
        n = len(self._rois) + 1
        self._colors = Colors.golden_angle_color(colormap=self._colormap, num=n, format="HEX")

    def add_roi(self, roi: BaseROI):
        """
        Registers an externally created ROI with this controller.

        Adds the ROI to the internal list, assigns it a color from the color buffer,
        ensures it has an appropriate line width, and emits the roiAdded signal.

        Args:
            roi (BaseROI): The ROI instance to register. Can be any subclass of BaseROI,
                such as RectangularROI or CircularROI.
        """
        self._rois.append(roi)
        self._rebuild_color_buffer()
        idx = len(self._rois) - 1
        if roi.label == "ROI" or roi.label.startswith("ROI "):
            roi.label = f"ROI {idx}"
        color = self._colors[idx]
        roi.line_color = color
        # ensure line width default is at least 3 if not previously set
        if getattr(roi, "line_width", 0) < 1:
            roi.line_width = 5
        self.roiAdded.emit(roi)

    def remove_roi(self, roi: BaseROI):
        """
        Removes an ROI from this controller.

        If the ROI is found in the internal list, it is removed, the color buffer
        is regenerated, and the roiRemoved signal is emitted.

        Args:
            roi (BaseROI): The ROI instance to remove.
        """
        if roi in self._rois:
            self.roiRemoved.emit(roi)
            self._rois.remove(roi)
            roi.remove()
            self._rebuild_color_buffer()
        else:
            roi.remove()

    def get_roi(self, index: int) -> BaseROI | None:
        """
        Returns the ROI at the specified index.

        Args:
            index (int): The index of the ROI to retrieve.

        Returns:
            BaseROI or None: The ROI at the specified index, or None if the index
                is out of range.
        """
        if 0 <= index < len(self._rois):
            return self._rois[index]
        return None

    def get_roi_by_name(self, name: str) -> BaseROI | None:
        """
        Returns the first ROI with the specified name.

        Args:
            name (str): The name to search for (case-sensitive).

        Returns:
            BaseROI or None: The first ROI with a matching name, or None if no
                matching ROI is found.
        """
        for r in self._rois:
            if r.label == name:
                return r
        return None

    def remove_roi_by_index(self, index: int):
        """
        Removes the ROI at the specified index.

        Args:
            index (int): The index of the ROI to remove.
        """
        roi = self.get_roi(index)
        if roi is not None:
            self.remove_roi(roi)

    def remove_roi_by_name(self, name: str):
        """
        Removes the first ROI with the specified name.

        Args:
            name (str): The name of the ROI to remove (case-sensitive).
        """
        roi = self.get_roi_by_name(name)
        if roi is not None:
            self.remove_roi(roi)

    def clear(self):
        """
        Removes all ROIs from this controller.

        Iterates through all ROIs and removes them one by one, then emits
        the cleared signal to notify listeners that all ROIs have been removed.
        """
        for roi in list(self._rois):
            self.remove_roi(roi)
        self.cleared.emit()

    def renormalize_colors(self):
        """
        Reassigns palette colors to all ROIs in order.

        Regenerates the color buffer based on the current colormap and number of ROIs,
        then assigns each ROI a color from the buffer in the order they were added.
        This is useful after changing the colormap or when ROIs need to be visually
        distinguished from each other.
        """
        self._rebuild_color_buffer()
        for idx, roi in enumerate(self._rois):
            roi.line_color = self._colors[idx]

    @SafeProperty(str)
    def colormap(self):
        """
        Gets the name of the colormap used for ROI colors.

        Returns:
            str: The name of the colormap.
        """
        return self._colormap

    @colormap.setter
    def colormap(self, cmap: str):
        """
        Sets the colormap used for ROI colors.

        Updates the internal colormap name and reassigns colors to all ROIs
        based on the new colormap.

        Args:
            cmap (str): The name of the colormap to use (e.g., "viridis", "plasma").
        """

        self.set_colormap(cmap)

    def set_colormap(self, cmap: str):
        Colors.validate_color_map(cmap)
        self._colormap = cmap
        self.paletteChanged.emit(cmap)
        self.renormalize_colors()

    @property
    def rois(self) -> list[BaseROI]:
        """
        Gets a copy of the list of ROIs managed by this controller.

        Returns a new list containing all the ROIs currently managed by this controller.
        The list is a copy, so modifying it won't affect the controller's internal list.

        Returns:
            list[BaseROI]: A list of all ROIs currently managed by this controller.
        """
        return list(self._rois)

    def cleanup(self):
        for roi in self._rois:
            self.remove_roi(roi)
