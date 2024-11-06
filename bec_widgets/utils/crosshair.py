from collections import defaultdict

import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import QObject, Qt, Signal, Slot


class NonDownsamplingScatterPlotItem(pg.ScatterPlotItem):
    def setDownsampling(self, ds=None, auto=None, method=None):
        pass

    def setClipToView(self, state):
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

    def __init__(self, plot_item: pg.PlotItem, precision: int = 3, parent=None):
        """
        Crosshair for 1D and 2D plots.

        Args:
            plot_item (pyqtgraph.PlotItem): The plot item to which the crosshair will be attached.
            precision (int, optional): Number of decimal places to round the coordinates to. Defaults to None.
            parent (QObject, optional): Parent object for the QObject. Defaults to None.
        """
        super().__init__(parent)
        self.is_log_y = None
        self.is_log_x = None
        self.is_derivative = None
        self.plot_item = plot_item
        self.precision = precision
        self.v_line = pg.InfiniteLine(angle=90, movable=False)
        self.v_line.skip_auto_range = True
        self.h_line = pg.InfiniteLine(angle=0, movable=False)
        self.h_line.skip_auto_range = True
        self.plot_item.addItem(self.v_line, ignoreBounds=True)
        self.plot_item.addItem(self.h_line, ignoreBounds=True)

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
        self.marker_moved_1d = {}
        self.marker_clicked_1d = {}
        self.marker_2d = None
        self.update_markers()
        self.check_log()
        self.check_derivatives()

    def update_markers(self):
        """Update the markers for the crosshair, creating new ones if necessary."""

        # Create new markers
        for item in self.plot_item.items:
            if isinstance(item, pg.PlotDataItem):  # 1D plot
                if item.name() in self.marker_moved_1d:
                    continue
                pen = item.opts["pen"]
                color = pen.color() if hasattr(pen, "color") else pg.mkColor(pen)
                marker_moved = NonDownsamplingScatterPlotItem(
                    size=10, pen=pg.mkPen(color), brush=pg.mkBrush(None)
                )
                marker_moved.skip_auto_range = True
                self.marker_moved_1d[item.name()] = marker_moved
                self.plot_item.addItem(marker_moved)

                # Create glowing effect markers for clicked events
                for size, alpha in [(18, 64), (14, 128), (10, 255)]:
                    marker_clicked = NonDownsamplingScatterPlotItem(
                        size=size,
                        pen=pg.mkPen(None),
                        brush=pg.mkBrush(color.red(), color.green(), color.blue(), alpha),
                    )
                    marker_clicked.skip_auto_range = True
                    self.marker_clicked_1d[item.name()] = marker_clicked
                    self.plot_item.addItem(marker_clicked)

            elif isinstance(item, pg.ImageItem):  # 2D plot
                if self.marker_2d is not None:
                    continue
                self.marker_2d = pg.ROI(
                    [0, 0], size=[1, 1], pen=pg.mkPen("r", width=2), movable=False
                )
                self.plot_item.addItem(self.marker_2d)

    def snap_to_data(self, x, y) -> tuple[defaultdict[list], defaultdict[list]]:
        """
        Finds the nearest data points to the given x and y coordinates.

        Args:
            x: The x-coordinate of the mouse cursor
            y: The y-coordinate of the mouse cursor

        Returns:
            tuple: x and y values snapped to the nearest data
        """
        y_values = defaultdict(list)
        x_values = defaultdict(list)
        image_2d = None

        # Iterate through items in the plot
        for item in self.plot_item.items:
            if isinstance(item, pg.PlotDataItem):  # 1D plot
                name = item.name()
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
                name = item.config.monitor
                image_2d = item.image
                # clip the x and y values to the image dimensions to avoid out of bounds errors
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

            for item in self.plot_item.items:
                if isinstance(item, pg.PlotDataItem):
                    name = item.name()
                    x, y = x_snap_values[name], y_snap_values[name]
                    if x is None or y is None:
                        continue
                    self.marker_moved_1d[name].setData([x], [y])
                    x_snapped_scaled, y_snapped_scaled = self.scale_emitted_coordinates(x, y)
                    coordinate_to_emit = (
                        name,
                        round(x_snapped_scaled, self.precision),
                        round(y_snapped_scaled, self.precision),
                    )
                    self.coordinatesChanged1D.emit(coordinate_to_emit)
                elif isinstance(item, pg.ImageItem):
                    name = item.config.monitor
                    x, y = x_snap_values[name], y_snap_values[name]
                    if x is None or y is None:
                        continue
                    self.marker_2d.setPos([x, y])
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

            for item in self.plot_item.items:
                if isinstance(item, pg.PlotDataItem):
                    name = item.name()
                    x, y = x_snap_values[name], y_snap_values[name]
                    if x is None or y is None:
                        continue
                    self.marker_clicked_1d[name].setData([x], [y])
                    x_snapped_scaled, y_snapped_scaled = self.scale_emitted_coordinates(x, y)
                    coordinate_to_emit = (
                        name,
                        round(x_snapped_scaled, self.precision),
                        round(y_snapped_scaled, self.precision),
                    )
                    self.coordinatesClicked1D.emit(coordinate_to_emit)
                elif isinstance(item, pg.ImageItem):
                    name = item.config.monitor
                    x, y = x_snap_values[name], y_snap_values[name]
                    if x is None or y is None:
                        continue
                    self.marker_2d.setPos([x, y])
                    coordinate_to_emit = (name, x, y)
                    self.coordinatesClicked2D.emit(coordinate_to_emit)
                else:
                    continue

    def clear_markers(self):
        """Clears the markers from the plot."""
        for marker in self.marker_moved_1d.values():
            marker.clear()
        for marker in self.marker_clicked_1d.values():
            marker.clear()

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

        # # Update coordinate label
        self.coord_label.setText(f"({x_scaled:.{self.precision}f}, {y_scaled:.{self.precision}f})")
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
        self.plot_item.removeItem(self.v_line)
        self.plot_item.removeItem(self.h_line)
        self.plot_item.removeItem(self.coord_label)

        self.clear_markers()
