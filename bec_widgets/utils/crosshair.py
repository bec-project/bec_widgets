from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import QObject, Qt, Signal, Slot
from qtpy.QtWidgets import QApplication


class CrosshairScatterItem(pg.ScatterPlotItem):
    def setDownsampling(self, ds=None, auto=None, method=None):
        pass

    def setClipToView(self, state):
        pass

    def setAlpha(self, *args, **kwargs):
        pass


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

    @Slot(str)
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

    @Slot(int)
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
        else:
            # Handle all curves
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
                self.plot_item.addItem(self.marker_2d_row)

                # Create vertical ROI for column highlighting
                self.marker_2d_col = pg.ROI(
                    [0, 0], size=[1, item.image.shape[1]], pen=pg.mkPen("r", width=2), movable=False
                )
                self.marker_2d_col.skip_auto_range = True
                self.plot_item.addItem(self.marker_2d_col)

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
                # Clip the x and y values to the image dimensions to avoid out of bounds errors
                y_values[name] = int(np.clip(y, 0, image_2d.shape[1] - 1))
                x_values[name] = int(np.clip(x, 0, image_2d.shape[0] - 1))

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

    def mouse_moved(self, event):
        """Handles the mouse moved event, updating the crosshair position and emitting signals.

        Args:
            event: The mouse moved event
        """
        pos = event[0]
        self.update_markers()
        if self.plot_item.vb.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_item.vb.mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()
            self.v_line.setPos(x)
            self.h_line.setPos(y)
            scaled_x, scaled_y = self.scale_emitted_coordinates(mouse_point.x(), mouse_point.y())
            self.crosshairChanged.emit((scaled_x, scaled_y))
            self.positionChanged.emit((x, y))

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
                    self.marker_moved_1d[name].setData([x], [y])
                    x_snapped_scaled, y_snapped_scaled = self.scale_emitted_coordinates(x, y)
                    coordinate_to_emit = (
                        name,
                        round(x_snapped_scaled, precision),
                        round(y_snapped_scaled, precision),
                    )
                    self.coordinatesChanged1D.emit(coordinate_to_emit)
                elif isinstance(item, pg.ImageItem):
                    name = item.objectName() or str(id(item))
                    x, y = x_snap_values[name], y_snap_values[name]
                    if x is None or y is None:
                        continue
                    # Set position of horizontal ROI (row)
                    self.marker_2d_row.setPos([0, y])
                    # Set position of vertical ROI (column)
                    self.marker_2d_col.setPos([x, 0])
                    coordinate_to_emit = (name, x, y)
                    self.coordinatesChanged2D.emit(coordinate_to_emit)
                else:
                    continue

    def mouse_clicked(self, event):
        """Handles the mouse clicked event, updating the crosshair position and emitting signals.

        Args:
            event: The mouse clicked event
        """

        # we only accept left mouse clicks
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.update_markers()
        if self.plot_item.vb.sceneBoundingRect().contains(event._scenePos):
            mouse_point = self.plot_item.vb.mapSceneToView(event._scenePos)
            x, y = mouse_point.x(), mouse_point.y()
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
                    # Set position of horizontal ROI (row)
                    self.marker_2d_row.setPos([0, y])
                    # Set position of vertical ROI (column)
                    self.marker_2d_col.setPos([x, 0])
                    coordinate_to_emit = (name, x, y)
                    self.coordinatesClicked2D.emit(coordinate_to_emit)
                else:
                    continue

    def clear_markers(self):
        """Clears the markers from the plot."""
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
        x_scaled, y_scaled = self.scale_emitted_coordinates(x, y)
        precision = self._current_precision()
        text = f"({x_scaled:.{precision}f}, {y_scaled:.{precision}f})"
        for item in self.items:
            if isinstance(item, pg.ImageItem):
                image = item.image
                if image is None:
                    continue
                ix = int(np.clip(x, 0, image.shape[0] - 1))
                iy = int(np.clip(y, 0, image.shape[1] - 1))
                intensity = image[ix, iy]
                text += f"\nIntensity: {intensity:.{precision}f}"
                break
        # Update coordinate label
        self.coord_label.setText(text)
        self.coord_label.setPos(x, y)
        self.coord_label.setVisible(True)

    def check_log(self):
        """Checks if the x or y axis is in log scale and updates the internal state accordingly."""
        self.is_log_x = self.plot_item.axes["bottom"]["item"].logMode
        self.is_log_y = self.plot_item.axes["left"]["item"].logMode
        self.clear_markers()

    def check_derivatives(self):
        """Checks if the derivatives are enabled and updates the internal state accordingly."""
        self.is_derivative = self.plot_item.ctrl.derivativeCheck.isChecked()
        self.clear_markers()

    def cleanup(self):
        if self.marker_2d_row is not None:
            self.plot_item.removeItem(self.marker_2d_row)
            self.marker_2d_row = None
        if self.marker_2d_col is not None:
            self.plot_item.removeItem(self.marker_2d_col)
            self.marker_2d_col = None
        self.plot_item.removeItem(self.v_line)
        self.plot_item.removeItem(self.h_line)
        self.plot_item.removeItem(self.coord_label)

        self.clear_markers()
