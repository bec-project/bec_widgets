from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import QObject, QPointF, Qt, Signal
from qtpy.QtGui import QCursor, QTransform
from qtpy.QtWidgets import QApplication, QMenu

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.plots.image.image_item import ImageItem


class CrosshairScatterItem(pg.ScatterPlotItem):
    def setDownsampling(self, ds=None, auto=None, method=None):
        pass

    def setClipToView(self, state):
        pass

    def setAlpha(self, *args, **kwargs):
        pass


class PinScatterItem(CrosshairScatterItem):
    """Scatter item for the pinned marker, owning its removal context menu.

    Right-clicks must be handled at the item level: item click events are
    delivered before the ViewBox's, so accepting the event here is the only way
    to keep pyqtgraph's plot context menu from opening on top of the pin menu.
    """

    def __init__(self, *args, on_remove=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_remove = on_remove

    def mouseClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.RightButton and self._on_remove is not None:
            ev.accept()
            menu = QMenu()
            remove_action = menu.addAction("Remove pinned marker")
            chosen = menu.exec_(QCursor.pos())
            menu.deleteLater()
            if chosen == remove_action:
                self._on_remove()
            return
        super().mouseClickEvent(ev)


class Crosshair(QObject):
    # QT Position of mouse cursor
    positionChanged = Signal(tuple)
    positionClicked = Signal(tuple)
    # Plain crosshair position signals mapped to real coordinates
    crosshairChanged = Signal(tuple)
    crosshairClicked = Signal(tuple)
    # Signal for 1D plot
    coordinatesChanged1D = Signal(tuple)
    coordinatesClicked1D = Signal(tuple)
    # Signal for 2D plot
    coordinatesChanged2D = Signal(tuple)
    coordinatesClicked2D = Signal(tuple)
    # Pinned marker signals (a persistent marker placed on click)
    coordinatesPinned1D = Signal(tuple)
    coordinatesPinned2D = Signal(tuple)
    pinCleared = Signal()

    def __init__(
        self,
        plot_item: pg.PlotItem,
        precision: int | None = None,
        *,
        min_precision: int = 2,
        parent=None,
    ):
        """
        Crosshair for 1D and 2D plots.

        Args:
            plot_item (pyqtgraph.PlotItem): The plot item to which the crosshair will be attached.
            precision (int | None, optional): Fixed number of decimal places to display. If *None*, precision is chosen dynamically from the current view range.
            min_precision (int, optional): The lower bound (in decimal places) used when dynamic precision is enabled. Defaults to 2.
            parent (QObject, optional): Parent object for the QObject. Defaults to None.
        """
        super().__init__(parent)
        self.is_log_y = None
        self.is_log_x = None
        self.is_derivative = None
        self.plot_item = plot_item
        self._precision = precision
        self._min_precision = max(0, int(min_precision))  # ensure non‑negative

        self.v_line = pg.InfiniteLine(angle=90, movable=False)
        self.v_line.skip_auto_range = True
        self.h_line = pg.InfiniteLine(angle=0, movable=False)
        self.h_line.skip_auto_range = True
        # Add custom attribute to identify crosshair lines
        self.v_line.is_crosshair = True
        self.h_line.is_crosshair = True
        self.plot_item.addItem(self.v_line, ignoreBounds=True)
        self.plot_item.addItem(self.h_line, ignoreBounds=True)

        # Initialize highlighted curve in a case of multiple curves
        self.highlighted_curve_index = None

        # Add TextItem to display coordinates
        self.coord_label = pg.TextItem("", anchor=(1, 1), fill=(0, 0, 0, 100))
        self.coord_label.setVisible(False)  # Hide initially
        self.coord_label.skip_auto_range = True
        self.plot_item.addItem(self.coord_label)

        # Signals to connect
        self.proxy = pg.SignalProxy(
            self.plot_item.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved
        )
        self.positionChanged.connect(self.update_coord_label)
        self.plot_item.scene().sigMouseClicked.connect(self.mouse_clicked)

        # Connect signals from pyqtgraph right click menu
        self.plot_item.ctrl.derivativeCheck.checkStateChanged.connect(self.check_derivatives)
        self.plot_item.ctrl.logXCheck.checkStateChanged.connect(self.check_log)
        self.plot_item.ctrl.logYCheck.checkStateChanged.connect(self.check_log)
        self.plot_item.ctrl.downsampleSpin.valueChanged.connect(self.clear_markers)

        # Initialize markers
        self.items = []
        self.marker_moved_1d = {}
        self.marker_clicked_1d = {}
        self.marker_2d_row = None
        self.marker_2d_col = None
        self._image_marker_geometry = None
        # Pinned marker (a single persistent marker placed on click). The live
        # crosshair keeps tracking the cursor; the pin stays until removed.
        self.pinned_point = None
        self.pinned_label = None
        self.pinned_v_line = None
        self.pinned_h_line = None
        self.pinned_pos = None
        # Last emitted pin payload, kept so the pin can be re-announced to consumers
        # after it is re-adopted: ("2d", payload) | ("1d", payload) | None.
        self._pinned_emit = None
        self._pin_hit_radius_px = 12  # how close (scene px) a click counts as "on the pin"
        self.update_markers()
        self.check_log()
        self.check_derivatives()

        self._connect_to_theme_change()

    @property
    def precision(self) -> int | None:
        """Fixed number of decimals; ``None`` enables dynamic mode."""
        return self._precision

    @precision.setter
    def precision(self, value: int | None):
        """
        Set the fixed number of decimals to display.

        Args:
            value(int | None): The number of decimals to display. If `None`, dynamic precision is used based on the view range.
        """
        self._precision = value

    @property
    def min_precision(self) -> int:
        """Lower bound on decimals when dynamic precision is used."""
        return self._min_precision

    @min_precision.setter
    def min_precision(self, value: int):
        """
        Set the lower bound on decimals when dynamic precision is used.

        Args:
            value(int): The minimum number of decimals to display. Must be non-negative.
        """
        self._min_precision = max(0, int(value))

    def _current_precision(self) -> int:
        """
        Get the current precision based on the view range or fixed precision.
        """
        if self._precision is not None:
            return self._precision

        # Dynamically choose precision from the smaller visible span
        view_range = self.plot_item.vb.viewRange()
        x_span = abs(view_range[0][1] - view_range[0][0])
        y_span = abs(view_range[1][1] - view_range[1][0])

        # Ignore zero spans that can appear during initialisation
        spans = [s for s in (x_span, y_span) if s > 0]
        span = min(spans) if spans else 1.0

        exponent = np.floor(np.log10(span))  # order of magnitude
        decimals = max(0, int(-exponent) + 1)
        return max(self._min_precision, decimals)

    def _connect_to_theme_change(self):
        """Connect to the theme change signal."""
        qapp = QApplication.instance()
        if hasattr(qapp, "theme_signal"):
            qapp.theme_signal.theme_updated.connect(self._update_theme)
            self._update_theme()

    @SafeSlot(str)
    def _update_theme(self, theme: str | None = None):
        """Update the theme."""
        if theme is None:
            qapp = QApplication.instance()
            if hasattr(qapp, "theme"):
                theme = qapp.theme.theme
            else:
                theme = "dark"
        self.apply_theme(theme)

    def apply_theme(self, theme: str):
        """Apply the theme to the plot."""
        if theme == "dark":
            text_color = "w"
            label_bg_color = (50, 50, 50, 150)
        elif theme == "light":
            text_color = "k"
            label_bg_color = (240, 240, 240, 150)
        else:
            text_color = "w"
            label_bg_color = (50, 50, 50, 150)

        self.coord_label.setColor(text_color)
        self.coord_label.fill = pg.mkBrush(label_bg_color)
        self.coord_label.border = pg.mkPen(None)

    @SafeSlot(int)
    def update_highlighted_curve(self, curve_index: int):
        """
        Update the highlighted curve in the case of multiple curves in a plot item.

        Args:
            curve_index(int): The index of curve to highlight
        """
        self.highlighted_curve_index = curve_index
        self.clear_markers()
        self.update_markers()

    def update_markers(self):
        """Update the markers for the crosshair, creating new ones if necessary."""

        if self.highlighted_curve_index is not None and hasattr(self.plot_item, "visible_curves"):
            # Focus on the highlighted curve only
            self.items = [self.plot_item.visible_curves[self.highlighted_curve_index]]
        elif hasattr(self.plot_item, "visible_items"):  # PlotBase general case
            # Handle visible items in the plot item
            self.items = self.plot_item.visible_items()
        else:  # Non PlotBase case
            # Handle all items
            self.items = self.plot_item.items

        # Create or update markers
        for item in self.items:
            if isinstance(item, pg.PlotDataItem):  # 1D plot
                pen = item.opts["pen"]
                color = pen.color() if hasattr(pen, "color") else pg.mkColor(pen)
                name = item.name() or str(id(item))
                if name in self.marker_moved_1d:
                    # Update existing markers
                    marker_moved = self.marker_moved_1d[name]
                    marker_moved.setPen(pg.mkPen(color))
                    # Update clicked markers' brushes
                    for marker_clicked in self.marker_clicked_1d[name]:
                        alpha = marker_clicked.opts["brush"].color().alpha()
                        marker_clicked.setBrush(
                            pg.mkBrush(color.red(), color.green(), color.blue(), alpha)
                        )
                    # Update z-values
                    marker_moved.setZValue(item.zValue() + 1)
                    for marker_clicked in self.marker_clicked_1d[name]:
                        marker_clicked.setZValue(item.zValue() + 1)
                else:
                    # Create new markers
                    marker_moved = CrosshairScatterItem(
                        size=10, pen=pg.mkPen(color), brush=pg.mkBrush(None)
                    )
                    marker_moved.skip_auto_range = True
                    marker_moved.is_crosshair = True
                    self.marker_moved_1d[name] = marker_moved
                    self.plot_item.addItem(marker_moved)
                    # Set marker z-value higher than the curve
                    marker_moved.setZValue(item.zValue() + 1)

                    # Create glowing effect markers for clicked events
                    marker_clicked_list = []
                    for size, alpha in [(18, 64), (14, 128), (10, 255)]:
                        marker_clicked = CrosshairScatterItem(
                            size=size,
                            pen=pg.mkPen(None),
                            brush=pg.mkBrush(color.red(), color.green(), color.blue(), alpha),
                        )
                        marker_clicked.skip_auto_range = True
                        marker_clicked.is_crosshair = True
                        self.plot_item.addItem(marker_clicked)
                        marker_clicked.setZValue(item.zValue() + 1)
                        marker_clicked_list.append(marker_clicked)
                    self.marker_clicked_1d[name] = marker_clicked_list
            elif isinstance(item, pg.ImageItem):  # 2D plot
                if self.marker_2d_row is not None and self.marker_2d_col is not None:
                    continue
                # Create horizontal ROI for row highlighting
                if item.image is None:
                    continue
                self.marker_2d_row = pg.ROI(
                    [0, 0], size=[item.image.shape[0], 1], pen=pg.mkPen("r", width=2), movable=False
                )
                self.marker_2d_row.skip_auto_range = True
                if item.image_transform is not None:
                    self.marker_2d_row.setTransform(item.image_transform)
                self.plot_item.addItem(self.marker_2d_row)

                # Create vertical ROI for column highlighting
                self.marker_2d_col = pg.ROI(
                    [0, 0], size=[1, item.image.shape[1]], pen=pg.mkPen("r", width=2), movable=False
                )
                if item.image_transform is not None:
                    self.marker_2d_col.setTransform(item.image_transform)
                self.marker_2d_col.skip_auto_range = True
                self.plot_item.addItem(self.marker_2d_col)

    @SafeSlot()
    def update_markers_on_image_change(self):
        """
        Update markers when the image changes, e.g. when the
        image shape or transformation changes.
        """
        self.update_image_marker_geometry()
        self.update_pinned_label()

        # Explicit callers may need the live crosshair refreshed from the
        # cursor. Image update notifications intentionally do not take this
        # path: synthesizing mouse moves for each incoming frame is expensive.
        views = self.plot_item.vb.scene().views()
        if not views:
            return
        view = views[0]
        global_pos = QCursor.pos()
        view_pos = view.mapFromGlobal(global_pos)
        scene_pos = view.mapToScene(view_pos)

        if self.plot_item.vb.sceneBoundingRect().contains(scene_pos):
            plot_pt = self.plot_item.vb.mapSceneToView(scene_pos)
            self.mouse_moved(manual_pos=(plot_pt.x(), plot_pt.y()))

    def update_image_marker_geometry(self) -> None:
        """Update 2D marker geometry only when the image geometry changes."""
        geometry = {}
        for item in self.items:
            if not isinstance(item, pg.ImageItem) or item.image is None:
                continue
            transform = item.image_transform or QTransform()
            geometry[id(item)] = (
                item.image.shape[0],
                item.image.shape[1],
                self._transform_signature(transform),
            )

        if geometry == self._image_marker_geometry:
            return

        self._image_marker_geometry = geometry
        for item in self.items:
            if not isinstance(item, pg.ImageItem) or item.image is None:
                continue
            transform = item.image_transform or QTransform()
            if self.marker_2d_row is not None:
                self.marker_2d_row.setSize([item.image.shape[0], 1])
                self.marker_2d_row.setTransform(transform)
            if self.marker_2d_col is not None:
                self.marker_2d_col.setSize([1, item.image.shape[1]])
                self.marker_2d_col.setTransform(transform)

    @staticmethod
    def _transform_signature(transform: QTransform) -> tuple[float, ...]:
        """Return a value-based transform signature for geometry change detection."""
        return (
            transform.m11(),
            transform.m12(),
            transform.m13(),
            transform.m21(),
            transform.m22(),
            transform.m23(),
            transform.m31(),
            transform.m32(),
            transform.m33(),
        )

    @SafeSlot()
    def update_on_image_change(self) -> None:
        """Refresh image-dependent crosshair state after the image data changed.

        The live and the pinned coordinate use the same mechanism: each label is
        rebuilt from its coordinate against the current image (the live label
        otherwise only refreshes on mouse moves, which would leave a stale
        intensity under a streaming image).
        """
        self.update_image_marker_geometry()
        if self.coord_label.isVisible():
            self.update_coord_label((self.v_line.value(), self.h_line.value()))
        self.update_pinned_label()

    def update_pinned_label(self) -> None:
        """Refresh the pinned marker label against the current plotted data."""
        if self.pinned_pos is None or self.pinned_label is None:
            return
        self.pinned_label.setText(self._coord_label_text(*self.pinned_pos, prefix="pin "))

    def snap_to_data(
        self, x: float, y: float
    ) -> tuple[None, None] | tuple[defaultdict[Any, list], defaultdict[Any, list]]:
        """
        Finds the nearest data points to the given x and y coordinates.

        Args:
            x(float): The x-coordinate of the mouse cursor
            y(float): The y-coordinate of the mouse cursor

        Returns:
            tuple: x and y values snapped to the nearest data
        """
        y_values = defaultdict(list)
        x_values = defaultdict(list)

        # Iterate through items in the plot
        for item in self.items:
            if isinstance(item, pg.PlotDataItem):  # 1D plot
                name = item.name() or str(id(item))
                plot_data = item._getDisplayDataset()
                if plot_data is None:
                    continue
                x_data, y_data = plot_data.x, plot_data.y
                if x_data is not None and y_data is not None:
                    if self.is_log_x:
                        min_x_data = np.min(x_data[x_data > 0])
                    else:
                        min_x_data = np.min(x_data)
                    max_x_data = np.max(x_data)
                    if x < min_x_data or x > max_x_data:
                        y_values[name] = None
                        x_values[name] = None
                        continue
                    closest_x, closest_y = self.closest_x_y_value(x, x_data, y_data)
                    y_values[name] = closest_y
                    x_values[name] = closest_x
            elif isinstance(item, pg.ImageItem):  # 2D plot
                name = item.objectName() or str(id(item))
                image_2d = item.image
                if image_2d is None:
                    continue
                # Map scene coordinates (plot units) back to image pixel coordinates
                if item.image_transform is not None:
                    inv_transform, _ = item.image_transform.inverted()
                    xy_trans = inv_transform.map(QPointF(x, y))
                else:
                    xy_trans = QPointF(x, y)

                # Define valid pixel coordinate bounds
                min_x_px, min_y_px = 0, 0
                max_x_px = image_2d.shape[0] - 1  # columns
                max_y_px = image_2d.shape[1] - 1  # rows

                # Clip the mapped coordinates to the image bounds
                px = int(np.clip(xy_trans.x(), min_x_px, max_x_px))
                py = int(np.clip(xy_trans.y(), min_y_px, max_y_px))

                # Store snapped pixel positions
                x_values[name] = px
                y_values[name] = py

        if x_values and y_values:
            if all(v is None for v in x_values.values()) or all(
                v is None for v in y_values.values()
            ):
                return None, None
            return x_values, y_values

        return None, None

    def closest_x_y_value(self, input_x: float, list_x: list, list_y: list) -> tuple:
        """
        Find the closest x and y value to the input value.

        Args:
            input_x (float): Input value
            list_x (list): List of x values
            list_y (list): List of y values

        Returns:
            tuple: Closest x and y value
        """
        # Convert lists to NumPy arrays
        arr_x = np.asarray(list_x)

        # Get the indices where x is not NaN
        valid_indices = ~np.isnan(arr_x)

        # Filter x array to exclude NaN values
        filtered_x = arr_x[valid_indices]

        # Find the index of the closest value in the filtered x array
        closest_index = np.abs(filtered_x - input_x).argmin()

        # Map back to the original index in the list_x and list_y arrays
        original_index = np.where(valid_indices)[0][closest_index]

        return list_x[original_index], list_y[original_index]

    @SafeSlot(object, tuple)
    def mouse_moved(self, event=None, manual_pos=None):
        """
        Handles the mouse moved event, updating the crosshair position and emitting signals.

        Args:
            event(object): The mouse moved event, which contains the scene position.
            manual_pos(tuple, optional): A tuple containing the (x, y) coordinates to manually set the crosshair position.
        """
        # Determine target (x, y) in *plot* coordinates
        if manual_pos is not None:
            x, y = manual_pos
        else:
            if event is None:
                return  # nothing to do
            scene_pos = event[0]  # SignalProxy bundle
            if not self.plot_item.vb.sceneBoundingRect().contains(scene_pos):
                return
            view_pos = self.plot_item.vb.mapSceneToView(scene_pos)
            x, y = view_pos.x(), view_pos.y()

        # Update cross‑hair visuals
        self.v_line.setPos(x)
        self.h_line.setPos(y)

        self.update_markers()
        scaled_x, scaled_y = self.scale_emitted_coordinates(x, y)
        self.crosshairChanged.emit((scaled_x, scaled_y))
        self.positionChanged.emit((x, y))

        snap_x_vals, snap_y_vals = self.snap_to_data(x, y)
        if snap_x_vals is None or snap_y_vals is None:
            return
        if all(v is None for v in snap_x_vals.values()) or all(
            v is None for v in snap_y_vals.values()
        ):
            return

        precision = self._current_precision()

        for item in self.items:
            if isinstance(item, pg.PlotDataItem):
                name = item.name() or str(id(item))
                sx, sy = snap_x_vals[name], snap_y_vals[name]
                if sx is None or sy is None:
                    continue
                self.marker_moved_1d[name].setData([sx], [sy])
                sx_s, sy_s = self.scale_emitted_coordinates(sx, sy)
                self.coordinatesChanged1D.emit(
                    (name, round(sx_s, precision), round(sy_s, precision))
                )

            elif isinstance(item, pg.ImageItem):
                name = item.objectName() or str(id(item))
                px, py = snap_x_vals[name], snap_y_vals[name]
                if px is None or py is None:
                    continue

                # Respect image transforms
                if isinstance(item, ImageItem) and item.image_transform is not None:
                    row, col = self._get_transformed_position(px, py, item.image_transform)
                    self.marker_2d_row.setPos(row)
                    self.marker_2d_col.setPos(col)
                else:
                    self.marker_2d_row.setPos([0, py])
                    self.marker_2d_col.setPos([px, 0])

                self.coordinatesChanged2D.emit((name, px, py))

    def mouse_clicked(self, event):
        """Handles the mouse clicked event, updating the crosshair position and emitting signals.

        Args:
            event: The mouse clicked event
        """

        # we only accept left mouse clicks; right-clicks on the pin are handled
        # by the PinScatterItem itself (item events precede the ViewBox menu).
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.update_markers()
        if self.plot_item.vb.sceneBoundingRect().contains(event._scenePos):
            mouse_point = self.plot_item.vb.mapSceneToView(event._scenePos)
            x, y = mouse_point.x(), mouse_point.y()
            # Keep the raw click position; ``x``/``y`` are reused/snapped below.
            pin_x, pin_y = mouse_point.x(), mouse_point.y()
            scaled_x, scaled_y = self.scale_emitted_coordinates(mouse_point.x(), mouse_point.y())
            self.crosshairClicked.emit((scaled_x, scaled_y))
            self.positionClicked.emit((x, y))

            x_snap_values, y_snap_values = self.snap_to_data(x, y)

            if x_snap_values is None or y_snap_values is None:
                return
            if all(v is None for v in x_snap_values.values()) or all(
                v is None for v in y_snap_values.values()
            ):
                # not sure how we got here, but just to be safe...
                return

            precision = self._current_precision()
            for item in self.items:
                if isinstance(item, pg.PlotDataItem):
                    name = item.name() or str(id(item))
                    x, y = x_snap_values[name], y_snap_values[name]
                    if x is None or y is None:
                        continue
                    for marker_clicked in self.marker_clicked_1d[name]:
                        marker_clicked.setData([x], [y])
                    x_snapped_scaled, y_snapped_scaled = self.scale_emitted_coordinates(x, y)
                    coordinate_to_emit = (
                        name,
                        round(x_snapped_scaled, precision),
                        round(y_snapped_scaled, precision),
                    )
                    self.coordinatesClicked1D.emit(coordinate_to_emit)
                elif isinstance(item, pg.ImageItem):
                    name = item.objectName() or str(id(item))
                    x, y = x_snap_values[name], y_snap_values[name]
                    if x is None or y is None:
                        continue

                    if isinstance(item, ImageItem) and item.image_transform is not None:
                        row, col = self._get_transformed_position(x, y, item.image_transform)
                        self.marker_2d_row.setPos(row)
                        self.marker_2d_col.setPos(col)
                    else:
                        self.marker_2d_row.setPos([0, y])
                        self.marker_2d_col.setPos([x, 0])

                    coordinate_to_emit = (name, x, y)
                    self.coordinatesClicked2D.emit(coordinate_to_emit)
                else:
                    continue

            # Pinned marker: double-click clears it, clicking the existing pin
            # removes it, otherwise (re)place a single pin at the clicked point.
            if event.double():
                self.clear_pin()
            elif self._pin_hit(event._scenePos):
                self.clear_pin()
            else:
                self.set_pin(pin_x, pin_y, x_snap_values, y_snap_values)

    def set_pin(self, x: float, y: float, x_snap=None, y_snap=None):
        """Place (or move) the single pinned marker at the data point nearest to (x, y).

        The pin is independent of the live crosshair: it stays in place until removed.
        Emits :attr:`coordinatesPinned1D` / :attr:`coordinatesPinned2D` with the snapped
        coordinates so consumers (e.g. the image ROI panels) can freeze a reference.

        Args:
            x (float): The x-coordinate of the click, in plot coordinates.
            y (float): The y-coordinate of the click, in plot coordinates.
            x_snap, y_snap: Optionally pre-computed snap dictionaries (from
                :meth:`snap_to_data`) to avoid recomputing them.
        """
        # Make sure the tracked items are current (e.g. when called programmatically).
        self.update_markers()
        if x_snap is None or y_snap is None:
            x_snap, y_snap = self.snap_to_data(x, y)
        if x_snap is None or y_snap is None:
            return

        precision = self._current_precision()
        draw_pt = None
        pinned_1d = None
        pinned_2d = None
        for item in self.items:
            if isinstance(item, pg.PlotDataItem):
                name = item.name() or str(id(item))
                sx, sy = x_snap.get(name), y_snap.get(name)
                if sx is None or sy is None:
                    continue
                draw_pt = (sx, sy)
                sx_s, sy_s = self.scale_emitted_coordinates(sx, sy)
                pinned_1d = (name, round(sx_s, precision), round(sy_s, precision))
                break
            elif isinstance(item, pg.ImageItem):
                name = item.objectName() or str(id(item))
                px, py = x_snap.get(name), y_snap.get(name)
                if px is None or py is None:
                    continue
                # Pin the marker at the pixel centre, mapped back into plot coordinates.
                if isinstance(item, ImageItem) and item.image_transform is not None:
                    pt = item.image_transform.map(QPointF(px + 0.5, py + 0.5))
                    draw_pt = (pt.x(), pt.y())
                else:
                    draw_pt = (px + 0.5, py + 0.5)
                pinned_2d = (name, px, py)
                break

        if draw_pt is None:
            return

        self._draw_pin(draw_pt[0], draw_pt[1])
        self.pinned_pos = draw_pt
        if pinned_2d is not None:
            self._pinned_emit = ("2d", pinned_2d)
            self.coordinatesPinned2D.emit(pinned_2d)
        elif pinned_1d is not None:
            self._pinned_emit = ("1d", pinned_1d)
            self.coordinatesPinned1D.emit(pinned_1d)

    def _draw_pin(self, x: float, y: float):
        """Create/move the pinned marker at plot coordinates (x, y).

        The pin is drawn as a frozen crosshair: dashed infinite lines plus a small dot
        and a coordinate label, so it is visually distinct from the live crosshair.
        """
        pin_pen = pg.mkPen("#f2c037", width=1, style=Qt.PenStyle.DashLine)
        if self.pinned_v_line is None:
            self.pinned_v_line = pg.InfiniteLine(angle=90, movable=False, pen=pin_pen)
            self.pinned_v_line.skip_auto_range = True
            self.pinned_v_line.is_crosshair = True
            self.pinned_v_line.setZValue(999)
            self.plot_item.addItem(self.pinned_v_line, ignoreBounds=True)
        if self.pinned_h_line is None:
            self.pinned_h_line = pg.InfiniteLine(angle=0, movable=False, pen=pin_pen)
            self.pinned_h_line.skip_auto_range = True
            self.pinned_h_line.is_crosshair = True
            self.pinned_h_line.setZValue(999)
            self.plot_item.addItem(self.pinned_h_line, ignoreBounds=True)
        self.pinned_v_line.setPos(x)
        self.pinned_h_line.setPos(y)

        if self.pinned_point is None:
            self.pinned_point = PinScatterItem(
                size=9,
                symbol="o",
                pen=pg.mkPen("#3a2d00", width=1.5),
                brush=pg.mkBrush("#f2c037"),
                on_remove=self.clear_pin,
            )
            self.pinned_point.skip_auto_range = True
            self.pinned_point.is_crosshair = True
            self.pinned_point.setZValue(1000)
            self.plot_item.addItem(self.pinned_point)
        self.pinned_point.setData([x], [y])

        if self.pinned_label is None:
            self.pinned_label = pg.TextItem("", anchor=(0, 1), color="#f2c037", fill=(0, 0, 0, 150))
            self.pinned_label.skip_auto_range = True
            self.pinned_label.setZValue(1000)
            self.plot_item.addItem(self.pinned_label)
        self.pinned_pos = (x, y)
        self.pinned_label.setPos(x, y)
        self.pinned_label.setVisible(True)
        self.update_pinned_label()

    def clear_pin(self):
        """Remove the pinned marker (if any) and notify consumers via :attr:`pinCleared`."""
        had_pin = self.pinned_pos is not None
        if self.pinned_point is not None:
            self.plot_item.removeItem(self.pinned_point)
            self.pinned_point = None
        if self.pinned_v_line is not None:
            self.plot_item.removeItem(self.pinned_v_line)
            self.pinned_v_line = None
        if self.pinned_h_line is not None:
            self.plot_item.removeItem(self.pinned_h_line)
            self.pinned_h_line = None
        if self.pinned_label is not None:
            self.plot_item.removeItem(self.pinned_label)
            self.pinned_label = None
        self.pinned_pos = None
        self._pinned_emit = None
        if had_pin:
            self.pinCleared.emit()

    def release_pin(self):
        """Detach the pin from this crosshair *without* removing it from the plot.

        Used when the crosshair is unhooked (e.g. toggled off) but the pin should
        stay on the plot. Returns a state dict that :meth:`adopt_pin` can use to
        re-attach the same items to a future crosshair, or ``None`` if there is no pin.
        """
        if self.pinned_pos is None:
            return None
        state = {
            "point": self.pinned_point,
            "v_line": self.pinned_v_line,
            "h_line": self.pinned_h_line,
            "label": self.pinned_label,
            "pos": self.pinned_pos,
            "emit": self._pinned_emit,
        }
        # Detach the removal callback: this crosshair is about to be deleted and a
        # detached pin has no owner to clear it through.
        if self.pinned_point is not None:
            self.pinned_point._on_remove = None
        # Drop our references without removing the graphics items from the plot.
        self.pinned_point = None
        self.pinned_v_line = None
        self.pinned_h_line = None
        self.pinned_label = None
        self.pinned_pos = None
        self._pinned_emit = None
        return state

    def adopt_pin(self, state):
        """Re-attach a pin previously detached with :meth:`release_pin`.

        The graphics items are already on the plot item; this only restores the
        references so the crosshair can manage (move / clear) the pin again.
        """
        if not state:
            return
        self.pinned_point = state.get("point")
        self.pinned_v_line = state.get("v_line")
        self.pinned_h_line = state.get("h_line")
        self.pinned_label = state.get("label")
        self.pinned_pos = state.get("pos")
        self._pinned_emit = state.get("emit")
        # Rebind the removal callback to this crosshair (the previous owner is gone).
        if self.pinned_point is not None:
            self.pinned_point._on_remove = self.clear_pin

    def reemit_pin(self):
        """Re-announce the current pin's coordinates to consumers.

        Used after :meth:`adopt_pin` so dependent state (e.g. the image ROI panels'
        frozen reference profiles) can be rebuilt for a pin that survived a toggle.
        """
        if self._pinned_emit is None:
            return
        kind, payload = self._pinned_emit
        if kind == "2d":
            self.coordinatesPinned2D.emit(payload)
        elif kind == "1d":
            self.coordinatesPinned1D.emit(payload)

    def _pin_hit(self, scene_pos) -> bool:
        """Return True if a click at ``scene_pos`` (scene pixels) lands on the pinned marker."""
        if self.pinned_pos is None:
            return False
        pin_scene = self.plot_item.vb.mapViewToScene(QPointF(*self.pinned_pos))
        delta = pin_scene - scene_pos
        return (delta.x() ** 2 + delta.y() ** 2) ** 0.5 <= self._pin_hit_radius_px

    def _get_transformed_position(
        self, x: float, y: float, transform: QTransform
    ) -> tuple[QPointF, QPointF]:
        """
        Maps the given x and y coordinates to the transformed position using the provided transform.
        Args:
            x (float): The x-coordinate to transform.
            y (float): The y-coordinate to transform.
            transform (QTransform): The transformation to apply.
        """
        origin = transform.map(QPointF(0, 0))
        row = transform.map(QPointF(0, y)) - origin
        col = transform.map(QPointF(x, 0)) - origin
        return row, col

    def clear_markers(self):
        """Clears the markers from the plot."""
        self._image_marker_geometry = None
        for marker in self.marker_moved_1d.values():
            self.plot_item.removeItem(marker)
        for markers in self.marker_clicked_1d.values():
            for marker in markers:
                self.plot_item.removeItem(marker)
        self.marker_moved_1d.clear()
        self.marker_clicked_1d.clear()

    def scale_emitted_coordinates(self, x, y):
        """Scales the emitted coordinates if the axes are in log scale.

        Args:
            x (float): The x-coordinate
            y (float): The y-coordinate

        Returns:
            tuple: The scaled x and y coordinates
        """
        if self.is_log_x:
            x = 10**x
        if self.is_log_y:
            y = 10**y
        return x, y

    def update_coord_label(self, pos: tuple):
        """Updates the coordinate label based on the crosshair position and axis scales.

        Args:
            pos (tuple): The (x, y) position of the crosshair.
        """
        x, y = pos
        # Update coordinate label
        self.coord_label.setText(self._coord_label_text(x, y))
        self.coord_label.setPos(x, y)
        self.coord_label.setVisible(True)

    def _coord_label_text(self, x: float, y: float, *, prefix: str = "") -> str:
        """Return coordinate label text, including image intensity for 2D plots."""
        x_scaled, y_scaled = self.scale_emitted_coordinates(x, y)
        precision = self._current_precision()
        text = f"{prefix}({x_scaled:.{precision}f}, {y_scaled:.{precision}f})"
        for item in self.items:
            if isinstance(item, pg.ImageItem):
                image = item.image
                if image is None:
                    continue

                if item.image_transform is not None:
                    inv_transform, _ = item.image_transform.inverted()
                    pt = inv_transform.map(QPointF(x, y))
                    px, py = pt.x(), pt.y()
                else:
                    px, py = x, y

                # Clip to valid pixel indices
                ix = int(np.clip(px, 0, image.shape[0] - 1))  # column
                iy = int(np.clip(py, 0, image.shape[1] - 1))  # row

                intensity = image[ix, iy]
                text += f"\nIntensity: {intensity:.{precision}f}"
                break
        return text

    def check_log(self):
        """Checks if the x or y axis is in log scale and updates the internal state accordingly."""
        self.is_log_x = self.plot_item.axes["bottom"]["item"].logMode
        self.is_log_y = self.plot_item.axes["left"]["item"].logMode
        self.clear_markers()
        # The pin is stored in view coordinates, which change meaning when the
        # axis scale changes; a stale pin would be drawn at the wrong data point.
        self.clear_pin()

    def check_derivatives(self):
        """Checks if the derivatives are enabled and updates the internal state accordingly."""
        self.is_derivative = self.plot_item.ctrl.derivativeCheck.isChecked()
        self.clear_markers()
        # Same as check_log: the plotted data changes meaning, so drop the pin.
        self.clear_pin()

    @SafeSlot()
    def reset(self):
        """Reset the transient crosshair markers (e.g. on new data / a new scan).

        The pinned marker is intentionally *not* cleared here: it is a persistent
        user annotation that survives data and scan changes. Use :meth:`clear_pin`
        for an explicit removal and :meth:`cleanup` for full teardown.
        """
        if self.marker_2d_row is not None:
            self.plot_item.removeItem(self.marker_2d_row)
            self.marker_2d_row = None
        if self.marker_2d_col is not None:
            self.plot_item.removeItem(self.marker_2d_col)
            self.marker_2d_col = None
        self.clear_markers()

    def cleanup(self):
        self.reset()
        self.clear_pin()
        self.plot_item.removeItem(self.v_line)
        self.plot_item.removeItem(self.h_line)
        self.plot_item.removeItem(self.coord_label)
