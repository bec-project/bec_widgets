from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QPushButton
from pyqtgraph import TextItem, mkPen
from qtpy.QtCore import QObject, Qt, Signal
from qtpy.QtWidgets import QColorDialog, QToolButton, QTreeWidget, QTreeWidgetItem, QWidget

from bec_widgets.utils import BECConnector, ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import Colors
from bec_widgets.utils.toolbar import MaterialIconAction, ModularToolBar
from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget


# TODO temp will be taken from the curve_tree.py
class ColorButton(QPushButton):
    """A QPushButton subclass that displays a color.

    The background is set to the given color and the button text is the hex code.
    The text color is chosen automatically (black if the background is light, white if dark)
    to guarantee good readability.
    """

    def __init__(self, color="#000000", parent=None):
        """Initialize the color button.

        Args:
            color (str): The initial color in hex format (e.g., '#000000').
            parent: Optional QWidget parent.
        """
        super().__init__(parent)
        self.set_color(color)

    def set_color(self, color):
        """Set the button's color and update its appearance.

        Args:
            color (str or QColor): The new color to assign.
        """
        if isinstance(color, QColor):
            self._color = color.name()
        else:
            self._color = color
        self._update_appearance()

    def color(self):
        """Return the current color in hex."""
        return self._color

    def _update_appearance(self):
        """Update the button style based on the background color's brightness."""
        c = QColor(self._color)
        brightness = c.lightnessF()
        text_color = "#000000" if brightness > 0.5 else "#FFFFFF"
        self.setStyleSheet(f"background-color: {self._color}; color: {text_color};")
        self.setText(self._color)


class LabelAdorner:
    """Manages a TextItem label on top of any ROI, keeping it aligned."""

    def __init__(self, roi, anchor=(0, 1), padding=2, bg_color=(0, 0, 0, 100), text_color="white"):
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
        self._update_html(roi.name)
        self._reposition()
        # reconnect on geometry/name changes
        roi.sigRegionChanged.connect(self._reposition)
        if hasattr(roi, "nameChanged"):
            roi.nameChanged.connect(self._update_html)

    def _update_html(self, text):
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

    def _reposition(self, *args):
        """
        Repositions the label to align with the ROI's current position.

        This method is called whenever the ROI's position or size changes.
        It places the label at the bottom-left corner of the ROI's bounding rectangle.

        Args:
            *args: Variable length argument list, not used but required for signal connection.
        """
        # put at top-left corner of ROI’s bounding rect
        size = self.roi.state["size"]
        # size = [width, height]
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
        "name",
        "name.setter",
        "line_color",
        "line_color.setter",
        "line_width",
        "line_width.setter",
        "get_coordinates",
        "get_data_from_image",
    ]

    def __init__(
        self,
        *,
        # BECConnector kwargs
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        parent_image: BECConnector | None = None,
        # ROI-specific
        name: str | None = None,
        line_color: str | None = None,
        line_width: int = 3,
        # all remaining pg.*ROI kwargs (pos, size, pen, …)
        **pg_kwargs,
    ):
        """Base class for all modular ROIs.

        Args:
            name (str): Human-readable name shown in ROI Manager and labels.
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

        if parent_image is not None:
            self.set_parent(parent_image)
        else:
            self.parent_image = None
        object_name = name.replace("-", "_").replace(" ", "_") if name else None
        super().__init__(object_name=object_name, config=config, gui_id=gui_id, **pg_kwargs)

        self._name = name or "ROI"
        self._line_color = line_color or "#ffffff"
        self._line_width = line_width
        self._description = True
        self.setPen(mkPen(self._line_color, width=self._line_width))

    def set_parent(self, parent: BECConnector):
        """
        Sets the parent image for this ROI.

        Args:
            parent (BECConnector): The parent image object to associate with this ROI.
        """
        self.parent_image = parent

    def parent(self):
        """
        Gets the parent image associated with this ROI.

        Returns:
            BECConnector: The parent image object, or None if no parent is set.
        """
        return self.parent_image

    @property
    def name(self) -> str:
        """
        Gets the display name of this ROI.

        Returns:
            str: The current name of the ROI.
        """
        return self._name

    # TODO implement name change dynamically from CLI
    @name.setter
    def name(self, new: str):
        """
        Sets the display name of this ROI.

        If the new name is different from the current name, this method updates
        the internal name, emits the nameChanged signal, and updates the object name.

        Args:
            new (str): The new name to set for the ROI.
        """
        if new != self._name:
            self._name = new
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

    def get_data_from_image(self, image: "np.ndarray | None" = None):
        """
        Extracts pixel data from within the ROI boundaries.

        This is an abstract method that must be implemented by subclasses.

        Args:
            image (np.ndarray, optional): The source image from which to extract data.
                If None, the method should try to locate an image in the scene.

        Returns:
            np.ndarray: Array of pixel values contained within the ROI.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError


class RectangularROI(BaseROI, pg.RectROI):
    """
    Defines a rectangular Region of Interest (ROI) with additional functionality.

    Provides tools for manipulating and extracting data from rectangular areas on
    images, includes support for GUI features and event-driven signaling.

    Attributes:
        edgesChanged (Signal): Signal emitted when the ROI edges change, providing
            the new (x0, y0, x1, y1) coordinates.
        edgesReleased (Signal): Signal emitted when the ROI edges are released,
            providing the new (x0, y0, x1, y1) coordinates.
    """

    edgesChanged = Signal(float, float, float, float)
    edgesReleased = Signal(float, float, float, float)

    def __init__(
        self,
        *,
        # pg.RectROI kwargs
        pos,
        size,
        pen=None,
        # BECConnector kwargs
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        parent_image: BECConnector | None = None,
        # ROI specifics
        label: str | None = None,
        line_color: str | None = None,
        line_width: int = 3,
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
            **extra_pg: Additional keyword arguments specific to pg.RectROI.
        """
        super().__init__(
            config=config,
            gui_id=gui_id,
            parent_image=parent_image,
            name=label,
            line_color=line_color,
            line_width=line_width,
            pos=pos,
            size=size,
            pen=pen,
            **extra_pg,
        )

        self.addScaleHandle([0.5, 1], [0.5, 0.5])
        self.addScaleHandle([1, 0.5], [0.5, 0.5])
        self.addScaleHandle([1, 1], [0.5, 0.5])
        self.sigRegionChanged.connect(self._on_region_changed)
        self.handlePen = mkPen("white", width=20)
        self.handleHoverPen = mkPen("white", width=30)  # TODO not sure if this works
        # attach the auto-aligning label
        self._adorner = LabelAdorner(self)

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
                "top_left": (x0, y0),
                "top_right": (x1, y0),
                "bottom_left": (x0, y1),
                "bottom_right": (x1, y1),
            }
        return (x0, y0, x1, y1)

    def get_data_from_image(self, image=None) -> "np.ndarray":
        """
        Extracts a Region of Interest (ROI) from the provided image or a default scene image.

        Args:
            image: Optional; An image from which to extract the ROI. If not provided,
                a default scene image will be used.

        Returns:
            The extracted ROI as a cropped image.

        Raises:
            RuntimeError: If no image is provided and a default scene image is not available.
        """

        if image is None:
            image = self._lookup_scene_image()
        if image is None:
            raise RuntimeError("No image available to extract ROI data.")
        x0, y0, x1, y1 = map(int, self.get_coordinates())
        y0 = max(0, y0)
        y1 = min(image.shape[0], y1)
        x0 = max(0, x0)
        x1 = min(image.shape[1], x1)
        return image[y0:y1, x0:x1]

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
        parent_image: BECConnector | None = None,
        label: str | None = None,
        line_color: str | None = None,
        line_width: int = 3,
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
            **extra_pg: Additional keyword arguments for pg.CircleROI.
        """
        super().__init__(
            config=config,
            gui_id=gui_id,
            parent_image=parent_image,
            name=label,
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

    def get_data_from_image(self, image=None):
        """
        Extracts ROI (region of interest) data from the provided or default image.

        The method computes a circular mask based on coordinates and radius, then
        extracts pixel data within this circular ROI from the given image.

        Args:
            image (numpy.ndarray, optional): Input image from which ROI data will
                be extracted. If None, the method will attempt to obtain an image
                using `self._lookup_scene_image()`.

        Returns:
            numpy.ndarray: Array containing pixel data within the defined circular ROI.

        Raises:
            RuntimeError: If no image is provided and no image can be retrieved from
                `self._lookup_scene_image()`.
        """
        import numpy as np

        if image is None:
            image = self._lookup_scene_image()
        if image is None:
            raise RuntimeError("No image available to extract ROI data.")
        cx, cy, d = self.get_coordinates()
        r = d / 2
        x0, x1 = int(max(0, cx - r)), int(min(image.shape[1], cx + r))
        y0, y1 = int(max(0, cy - r)), int(min(image.shape[0], cy + r))
        yy, xx = np.ogrid[y0:y1, x0:x1]
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r**2
        return image[y0:y1, x0:x1][mask]

    def _lookup_scene_image(self):
        """
        Retrieves an image from the scene items if available.

        Iterates over all items in the scene and checks if any of them are of type
        `pg.ImageItem` and have a non-None image. If such an item is found, its image
        is returned.

        Returns:
            numpy.ndarray or None: The image from the scene item if found, otherwise
            None.
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
        colormap (str): Name of the colormap used for ROI colors.
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
        self.colormap = colormap
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
        self._colors = Colors.golden_angle_color(colormap=self.colormap, num=n, format="HEX")

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
        if roi.name == "ROI" or roi.name.startswith("ROI "):
            roi.name = f"ROI {idx}"
        color = self._colors[idx]
        roi.line_color = color
        # ensure line width default is at least 3 if not previously set
        if getattr(roi, "line_width", 0) < 1:
            roi.line_width = 3
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
            self._rois.remove(roi)
            self._rebuild_color_buffer()
            self.roiRemoved.emit(roi)

    # Convenience helpers -------------------------------------------------
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
            if r.name == name:
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

    # TODO can be property with validation
    def set_colormap(self, cmap: str):
        """
        Sets the colormap used for ROI colors.

        Updates the internal colormap name, emits the paletteChanged signal,
        and reassigns colors to all ROIs based on the new colormap.

        Args:
            cmap (str): The name of the colormap to use (e.g., "viridis", "plasma").
        """
        self.colormap = cmap
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


class ROIManagerTree(BECWidget, QWidget):
    """
    Tree-based GUI widget for managing Region of Interest (ROI) instances.

    This widget provides a user interface for creating, viewing, and manipulating
    ROIs on an image plot. It includes a toolbar with buttons for adding rectangular
    and circular ROIs, expanding/collapsing the tree view, and changing the colormap.
    The tree view displays all ROIs with options to rename them, print their data,
    change their colors, and remove them.

    Attributes:
        PLUGIN (bool): Flag indicating if this class is a plugin for BECDesigner.
        RPC (bool): Flag indicating if remote procedure calls are enabled.
    """

    PLUGIN = False
    RPC = False

    def __init__(
        self,
        plot,
        controller: ROIController | None = None,
        parent=None,
        config: ConnectionConfig = None,
        **kwargs,
    ):
        """
        Initializes the ROI Manager Tree widget.

        Sets up the widget with a plot reference, ROI controller, and UI components
        including a toolbar and tree view for managing ROIs.

        Args:
            plot: The plot widget where ROIs will be displayed.
            controller (ROIController | None, optional): The controller for managing ROIs.
                If None, a new ROIController is created. Defaults to None.
            parent: The parent widget. Defaults to None.
            config (ConnectionConfig, optional): Configuration for BECWidget.
                If None, a default configuration is created. Defaults to None.
            **kwargs: Additional keyword arguments passed to the parent class.
        """
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        super().__init__(parent=parent, config=config, **kwargs)
        self.plot = plot
        if controller is None:
            controller = ROIController()
        self.controller = controller

        self.layout = QVBoxLayout(self)
        self.roi_items: dict[BaseROI, QTreeWidgetItem] = {}

        self._init_toolbar()
        self._init_tree()

        # subscribe to the headless controller:
        self.controller.roiAdded.connect(self._on_roi_added)
        self.controller.roiRemoved.connect(self._on_roi_removed)
        self.controller.cleared.connect(self.clear)
        self.controller.paletteChanged.connect(lambda cmap: self.controller.renormalize_colors())

        # initial population
        for roi in self.controller.rois:
            self._add_roi_item(roi)

    @property
    def all_rois(self):
        """
        Gets all ROIs managed by this widget's controller.

        This is a convenience property that delegates to the controller's rois property.

        Returns:
            list[BaseROI]: A list of all ROIs currently managed by the controller.
        """
        return self.controller.rois

    def _init_toolbar(self):
        """
        Initializes the toolbar with buttons and widgets for ROI management.

        Creates a toolbar with buttons for adding rectangular and circular ROIs,
        expanding and collapsing the tree view, renormalizing colors, and a
        colormap selector widget. Connects signals from these controls to the
        appropriate handler methods.
        """
        self.toolbar = ModularToolBar(parent=self, target_widget=self, orientation="horizontal")
        add_rect = MaterialIconAction(
            icon_name="add_box", tooltip="Add Rect ROI", checkable=False, parent=self
        )
        add_circle = MaterialIconAction(
            icon_name="panorama_fish_eye", tooltip="Add Circle ROI", checkable=False, parent=self
        )
        expand = MaterialIconAction(
            icon_name="unfold_more", tooltip="Expand All", checkable=False, parent=self
        )
        collapse = MaterialIconAction(
            icon_name="unfold_less", tooltip="Collapse All", checkable=False, parent=self
        )
        renorm = MaterialIconAction(
            icon_name="palette", tooltip="Renormalize Colors", checkable=False, parent=self
        )
        self.toolbar.add_action("add_rect", add_rect, self)
        self.toolbar.add_action("add_circle", add_circle, self)
        self.toolbar.add_action("expand", expand, self)
        self.toolbar.add_action("collapse", collapse, self)
        self.toolbar.add_action("renorm", renorm, self)
        self.toolbar.addWidget(QWidget())  # spacer
        cmap = BECColorMapWidget(cmap=self.controller.colormap)
        self.toolbar.addWidget(cmap)
        add_rect.action.triggered.connect(lambda: self.add_new_roi("rect"))
        add_circle.action.triggered.connect(lambda: self.add_new_roi("circle"))
        expand.action.triggered.connect(lambda: self.tree.expandAll())
        collapse.action.triggered.connect(lambda: self.tree.collapseAll())
        renorm.action.triggered.connect(lambda: self.controller.renormalize_colors())
        cmap.colormap_changed_signal.connect(self._on_colormap_changed)

        self.layout.addWidget(self.toolbar)
        self.toolbar = self.toolbar

    def _init_tree(self):
        """
        Initializes the tree widget for displaying and managing ROIs.

        Creates a QTreeWidget with columns for the ROI name, print button,
        color button, and remove button. Sets up edit triggers to allow
        renaming ROIs by double-clicking or pressing edit keys, and connects
        the itemChanged signal to handle ROI name changes.
        """
        tw = QTreeWidget()
        tw.setColumnCount(4)
        tw.setHeaderLabels(["Name", "Print", "Color", "Remove"])
        tw.setEditTriggers(QTreeWidget.DoubleClicked | QTreeWidget.EditKeyPressed)
        tw.itemChanged.connect(self._on_item_changed)
        self.layout.addWidget(tw)
        self.tree = tw

    def add_new_roi(self, kind: str = "rect"):
        """
        Creates and adds a new ROI of the specified kind.

        Creates either a rectangular or circular ROI with default position and size,
        assigns it a name based on the current number of ROIs, and adds it to the
        controller.

        Args:
            kind (str, optional): The type of ROI to create, either "rect" for rectangular
                or any other value for circular. Defaults to "rect".
        """
        idx = len(self.all_rois) + 1
        name = f"ROI {idx}"
        if kind == "rect":
            roi = RectangularROI(pos=[10, 10], size=[50, 50], line_width=3, label=name)
        else:
            roi = CircularROI(pos=[10, 10], size=[50, 50], line_width=3, label=name)
        self.controller.add_roi(roi)

    def _on_roi_added(self, roi):
        """
        Handles the event when a new ROI is added to the controller.

        This method is called when the controller's roiAdded signal is emitted.
        It adds the ROI to the plot if it's not already there, and adds a
        corresponding item to the tree view.

        Args:
            roi (BaseROI): The ROI that was added to the controller.
        """
        # Only add to plot if not already present
        if not hasattr(roi, "scene") or roi.scene() is None:
            self.plot.addItem(roi)
        self._add_roi_item(roi)

    def _on_roi_removed(self, roi):
        """
        Handles the event when an ROI is removed from the controller.

        This method is called when the controller's roiRemoved signal is emitted.
        It removes the corresponding item from the tree view.

        Args:
            roi (BaseROI): The ROI that was removed from the controller.
        """
        item = self.roi_items.pop(roi, None)
        if item is not None:
            idx = self.tree.indexOfTopLevelItem(item)
            if idx != -1:
                self.tree.takeTopLevelItem(idx)

    def _add_roi_item(self, roi: BaseROI):
        """
        Adds an ROI to the tree widget and sets up its UI controls.

        Creates a tree item for the ROI with buttons for printing data, changing color,
        and removing the ROI. Also connects signals from the ROI to print coordinate
        information when it's moved or released.

        Args:
            roi (BaseROI): The ROI to add to the tree widget.
        """
        item = QTreeWidgetItem(self.tree, [roi.name])
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        pb = QToolButton(self)
        pb.setText("📐")
        cb = QToolButton(self)
        cb.setText("🎨")
        rb = QToolButton(self)
        rb.setText("✖")
        self.tree.setItemWidget(item, 1, pb)
        self.tree.setItemWidget(item, 2, cb)
        self.tree.setItemWidget(item, 3, rb)
        self.roi_items[roi] = item

        # Hook printing on move/release
        if isinstance(roi, RectangularROI):
            roi.edgesChanged.connect(
                lambda x0, y0, x1, y1, name=roi.name: print(f"{name} moved: {x0},{y0} → {x1},{y1}")
            )
            roi.edgesReleased.connect(
                lambda x0, y0, x1, y1, name=roi.name: print(
                    f"{name} released: {x0},{y0} → {x1},{y1}"
                )
            )
        else:
            roi.centerChanged.connect(
                lambda cx, cy, d, name=roi.name: print(
                    f"{name} moved: center=({cx:.1f},{cy:.1f}), d={d:.1f}"
                )
            )
            roi.centerReleased.connect(
                lambda cx, cy, d, name=roi.name: print(
                    f"{name} released: center=({cx:.1f},{cy:.1f}), d={d:.1f}"
                )
            )

        # Buttons
        pb.clicked.connect(lambda *_: self._print_roi(roi))
        cb.clicked.connect(lambda *_: self._change_color(roi))
        rb.clicked.connect(lambda *_: self._remove_roi(roi))

        # adjust column widths
        for c in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(c)

    def _on_item_changed(self, item, col):
        if col != 0:
            return
        new_name = item.text(0)
        for roi, it in self.roi_items.items():
            if it is item:
                roi.name = new_name
                break

    def _print_roi(self, roi):
        coords = roi.get_coordinates()
        try:
            data = roi.get_data_from_image()  # auto-detect image
            info = f"mean={data.mean():.3g}, N={data.size}"
            data = f"data = {data}"
        except Exception as err:
            info = f"no data ({err})"
        print(coords, info, data)

    def _change_color(self, roi):
        c = QColorDialog.getColor(parent=self)
        if not c.isValid():
            return
        idx = self.controller.rois.index(roi)
        self.controller._colors[idx] = c.name()
        roi.line_color = c.name()

    def _remove_roi(self, roi):
        self.plot.removeItem(roi)
        item = self.roi_items.pop(roi)
        self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        # Remove from controller (which will update .all_rois)
        self.controller.remove_roi(roi)

    # Removed renormalize_colors; use controller.renormalize_colors instead.

    def _on_colormap_changed(self, cmap):
        self.controller.set_colormap(cmap)

    def clear(self):
        for roi in list(self.all_rois):
            self.plot.removeItem(roi)
            item = self.roi_items.pop(roi, None)
            if item is not None:
                idx = self.tree.indexOfTopLevelItem(item)
                if idx != -1:
                    self.tree.takeTopLevelItem(idx)


# -----------------------------------------------------------------------------
# New alternative manager: ROIPropertyTree
# -----------------------------------------------------------------------------
from qtpy.QtWidgets import QSpinBox, QLabel


class ROIPropertyTree(BECWidget, QWidget):
    """
    Two-column tree:  [ROI]  [Properties]

    • Top-level = ROI name (editable) + color button.
    • Children  =   type, line-width (spin box), coordinates (auto-updating).
    """

    PLUGIN = False
    RPC = False

    COL_ROI, COL_PROPS = 0, 1

    def __init__(self, plot: pg.PlotItem, controller: ROIController | None = None, parent=None):
        if controller is None:
            controller = ROIController()
        super().__init__(
            parent=parent, config=ConnectionConfig(widget_class=self.__class__.__name__)
        )
        self.plot = plot
        self.controller = controller
        self.roi_items: dict[BaseROI, QTreeWidgetItem] = {}

        self.layout = QVBoxLayout(self)
        self._init_toolbar()
        self._init_tree()

        # connect controller
        c = self.controller
        c.roiAdded.connect(self._on_roi_added)
        c.roiRemoved.connect(self._on_roi_removed)
        c.cleared.connect(self.tree.clear)

        # initial load
        for r in c.rois:
            self._on_roi_added(r)

    # --------------------------------------------------------------------- UI
    def _init_toolbar(self):
        tb = ModularToolBar(self, self, orientation="horizontal")
        for icon, tip, slot in (
            ("add_box", "Add Rect ROI", lambda: self._add_rect()),
            ("panorama_fish_eye", "Add Circle ROI", lambda: self._add_circle()),
            ("unfold_more", "Expand All", self.treeExpandAll),
            ("unfold_less", "Collapse All", self.treeCollapseAll),
            ("palette", "Renormalize Colors", self.controller.renormalize_colors),
        ):
            act = MaterialIconAction(icon, tip, False, self)
            tb.add_action(tip, act, self)
            act.action.triggered.connect(slot)
        # colormap widget
        cmap = BECColorMapWidget(cmap=self.controller.colormap)
        tb.addWidget(QWidget())  # spacer
        tb.addWidget(cmap)
        cmap.colormap_changed_signal.connect(self.controller.set_colormap)
        self.layout.addWidget(tb)

    def _init_tree(self):
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["ROI", "Properties"])
        self.tree.setAlternatingRowColors(True)
        self.tree.itemChanged.connect(self._on_item_edited)
        self.layout.addWidget(self.tree)

    # ----------------------------------------------------------------- helpers
    def _add_rect(self):
        r = RectangularROI(pos=[10, 10], size=[50, 50])
        self.plot.addItem(r)
        self.controller.add_roi(r)

    def _add_circle(self):
        r = CircularROI(pos=[10, 10], size=[50, 50])
        self.plot.addItem(r)
        self.controller.add_roi(r)

    # --------------------------------------------------------- controller slots
    def _on_roi_added(self, roi: BaseROI):
        # parent row
        parent = QTreeWidgetItem(self.tree, [roi.name])
        parent.setFlags(parent.flags() | Qt.ItemIsEditable)
        # color button
        color_btn = ColorButton(roi.line_color)
        self.tree.setItemWidget(parent, self.COL_PROPS, color_btn)
        color_btn.clicked.connect(lambda: self._pick_color(roi, color_btn))

        # child rows
        type_item = QTreeWidgetItem(parent, ["Type", roi.__class__.__name__])
        width_item = QTreeWidgetItem(parent, ["Line width"])
        width_spin = QSpinBox()
        width_spin.setRange(1, 20)
        width_spin.setValue(roi.line_width)
        self.tree.setItemWidget(width_item, self.COL_PROPS, width_spin)
        width_spin.valueChanged.connect(lambda v, r=roi: setattr(r, "line_width", v))

        # --- Step 2: Insert separate coordinate rows (one per value)
        coord_rows = {}
        coords = roi.get_coordinates(typed=True)  # e.g. {'left':x0, 'top':y0,...}

        for key, value in coords.items():
            # Human-readable label: “center x” from “center_x”, etc.
            label = key.replace("_", " ").title()
            if isinstance(value, (tuple, list)):
                val_text = "(" + ", ".join(f"{v:.2f}" for v in value) + ")"
            elif isinstance(value, (int, float)):
                val_text = f"{value:.2f}"
            else:
                val_text = str(value)
            row = QTreeWidgetItem(parent, [label, val_text])
            coord_rows[key] = row

        # keep dict refs
        self.roi_items[roi] = parent

        # --- Step 3: Update coordinates on ROI movement
        def _update_coords():
            c_dict = roi.get_coordinates(typed=True)
            for k, row in coord_rows.items():
                if k in c_dict:
                    val = c_dict[k]
                    if isinstance(val, (tuple, list)):
                        text = "(" + ", ".join(f"{v:.2f}" for v in val) + ")"
                    elif isinstance(val, (int, float)):
                        text = f"{val:.2f}"
                    else:
                        text = str(val)
                    row.setText(self.COL_PROPS, text)

        if isinstance(roi, RectangularROI):
            roi.edgesChanged.connect(_update_coords)
        else:
            roi.centerChanged.connect(_update_coords)

        # sync width edits back to spinbox
        roi.penChanged.connect(lambda r=roi, sp=width_spin: sp.setValue(r.line_width))
        roi.nameChanged.connect(lambda n, itm=parent: itm.setText(self.COL_ROI, n))

        # color changes
        roi.penChanged.connect(lambda r=roi, b=color_btn: b.set_color(r.line_color))

        # expand parent by default
        self.tree.expandItem(parent)
        for c in range(2):
            self.tree.resizeColumnToContents(c)

    def _on_roi_removed(self, roi: BaseROI):
        item = self.roi_items.pop(roi, None)
        if item:
            idx = self.tree.indexOfTopLevelItem(item)
            self.tree.takeTopLevelItem(idx)

    # ---------------------------------------------------------- event handlers
    def _pick_color(self, roi: BaseROI, btn: "ColorButton"):
        clr = QColorDialog.getColor(QColor(roi.line_color), self, "Select ROI Color")
        if clr.isValid():
            roi.line_color = clr.name()
            btn.set_color(clr)

    def _on_item_edited(self, item: QTreeWidgetItem, col: int):
        if col != self.COL_ROI:
            return
        # find which roi
        for r, it in self.roi_items.items():
            if it is item:
                r.name = item.text(self.COL_ROI)
                break

    # Qt convenience
    def treeExpandAll(self):
        self.tree.expandAll()

    def treeCollapseAll(self):
        self.tree.collapseAll()


# Demo
if __name__ == "__main__":
    import sys

    import numpy as np
    from qtpy.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = QWidget()
    win.setWindowTitle("Modular ROI Demo")
    ml = QHBoxLayout(win)
    left = QWidget()
    vl = QVBoxLayout(left)
    view = pg.GraphicsLayoutWidget()
    vl.addWidget(view)
    plot = view.addPlot()
    img = pg.ImageItem()
    plot.addItem(img)
    img.setImage(np.random.normal(size=(200, 200)))
    ml.addWidget(left)
    mgr = ROIManagerTree(plot)
    mgr.setFixedWidth(350)
    ml.addWidget(mgr)
    mgr_new = ROIPropertyTree(plot)
    mgr_new.setFixedWidth(350)
    ml.addWidget(mgr_new)
    win.resize(1500, 600)
    win.show()
    sys.exit(app.exec_())
