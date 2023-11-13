import numpy as np
import pyqtgraph as pg

# from qtpy.QtCore import QObject, pyqtSignal
from qtpy.QtCore import QObject, Signal as pyqtSignal


class Crosshair(QObject):
    # Signal for 1D plot
    coordinatesChanged1D = pyqtSignal(float, list)
    coordinatesClicked1D = pyqtSignal(float, list)
    # Signal for 2D plot
    coordinatesChanged2D = pyqtSignal(float, float)
    coordinatesClicked2D = pyqtSignal(float, float)

    def __init__(self, plot_item: pg.PlotItem, precision: int = None, parent=None):
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
        self.plot_item = plot_item
        self.precision = precision
        self.v_line = pg.InfiniteLine(angle=90, movable=False)
        self.h_line = pg.InfiniteLine(angle=0, movable=False)
        self.plot_item.addItem(self.v_line, ignoreBounds=True)
        self.plot_item.addItem(self.h_line, ignoreBounds=True)
        self.proxy = pg.SignalProxy(
            self.plot_item.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved
        )
        self.plot_item.scene().sigMouseClicked.connect(self.mouse_clicked)

        # Initialize markers
        self.marker_moved_1d = []
        self.marker_clicked_1d = []
        self.marker_2d = None
        self.update_markers()

    def update_markers(self):
        """Update the markers for the crosshair, creating new ones if necessary."""

        # Clear existing markers
        for marker in self.marker_moved_1d + self.marker_clicked_1d:
            self.plot_item.removeItem(marker)
        if self.marker_2d:
            self.plot_item.removeItem(self.marker_2d)

        # Create new markers
        self.marker_moved_1d = []
        self.marker_clicked_1d = []
        self.marker_2d = None
        for item in self.plot_item.items:
            if isinstance(item, pg.PlotDataItem):  # 1D plot
                pen = item.opts["pen"]
                color = pen.color() if hasattr(pen, "color") else pg.mkColor(pen)
                marker_moved = pg.ScatterPlotItem(
                    size=10, pen=pg.mkPen(color), brush=pg.mkBrush(None)
                )
                marker_clicked = pg.ScatterPlotItem(
                    size=10, pen=pg.mkPen(None), brush=pg.mkBrush(color)
                )
                self.marker_moved_1d.append(marker_moved)
                self.plot_item.addItem(marker_moved)
                # Create glowing effect markers for clicked events
                marker_clicked_list = []
                for size, alpha in [(18, 64), (14, 128), (10, 255)]:
                    marker_clicked = pg.ScatterPlotItem(
                        size=size,
                        pen=pg.mkPen(None),
                        brush=pg.mkBrush(color.red(), color.green(), color.blue(), alpha),
                    )
                    marker_clicked_list.append(marker_clicked)
                    self.plot_item.addItem(marker_clicked)

                self.marker_clicked_1d.append(marker_clicked_list)
            elif isinstance(item, pg.ImageItem):  # 2D plot
                self.marker_2d = pg.ROI(
                    [0, 0], size=[1, 1], pen=pg.mkPen("r", width=2), movable=False
                )
                self.plot_item.addItem(self.marker_2d)

    def snap_to_data(self, x, y) -> tuple:
        """
        Finds the nearest data points to the given x and y coordinates.

        Args:
            x: The x-coordinate
            y: The y-coordinate

        Returns:
            tuple: The nearest x and y values
        """
        y_values_1d = []
        x_values_1d = []
        image_2d = None

        # Iterate through items in the plot
        for item in self.plot_item.items:
            if isinstance(item, pg.PlotDataItem):  # 1D plot
                x_data, y_data = item.xData, item.yData
                if x_data is not None and y_data is not None:
                    if self.is_log_x:
                        min_x_data = np.min(x_data[x_data > 0])
                    else:
                        min_x_data = np.min(x_data)
                    max_x_data = np.max(x_data)
                    if x < min_x_data or x > max_x_data:
                        return None, None
                    closest_x, closest_y = self.closest_x_y_value(x, x_data, y_data)
                    y_values_1d.append(closest_y)
                    x_values_1d.append(closest_x)
            elif isinstance(item, pg.ImageItem):  # 2D plot
                image_2d = item.image

        # Handle 1D plot
        if y_values_1d:
            if all(v is None for v in x_values_1d) or all(v is None for v in y_values_1d):
                return None, None
            closest_x = min(x_values_1d, key=lambda xi: abs(xi - x))  # Snap x to closest data point
            return closest_x, y_values_1d

        # Handle 2D plot
        if image_2d is not None:
            x_idx = int(np.clip(x, 0, image_2d.shape[0] - 1))
            y_idx = int(np.clip(y, 0, image_2d.shape[1] - 1))
            return x_idx, y_idx

        return None, None

    def closest_x_y_value(self, input_value: float, list_x: list, list_y: list) -> tuple:
        """
        Find the closest x and y value to the input value.

        Args:
            input_value (float): Input value
            list_x (list): List of x values
            list_y (list): List of y values

        Returns:
            tuple: Closest x and y value
        """
        arr = np.asarray(list_x)
        i = (np.abs(arr - input_value)).argmin()
        return list_x[i], list_y[i]

    def mouse_moved(self, event):
        """Handles the mouse moved event, updating the crosshair position and emitting signals.

        Args:
            event: The mouse moved event
        """
        self.check_log()
        pos = event[0]
        if self.plot_item.vb.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_item.vb.mapSceneToView(pos)
            self.v_line.setPos(mouse_point.x())
            self.h_line.setPos(mouse_point.y())

            x, y = mouse_point.x(), mouse_point.y()
            if self.is_log_x:
                x = 10**x
            if self.is_log_y:
                y = 10**y
            x, y_values = self.snap_to_data(x, y)

            for item in self.plot_item.items:
                if isinstance(item, pg.PlotDataItem):
                    if x is None or all(v is None for v in y_values):
                        return
                    self.coordinatesChanged1D.emit(
                        round(x, self.precision),
                        [round(y_val, self.precision) for y_val in y_values],
                    )
                    for i, y_val in enumerate(y_values):
                        self.marker_moved_1d[i].setData(
                            [x if not self.is_log_x else np.log10(x)],
                            [y_val if not self.is_log_y else np.log10(y_val)],
                        )
                elif isinstance(item, pg.ImageItem):
                    if x is None or y_values is None:
                        return
                    self.coordinatesChanged2D.emit(x, y_values)

    def mouse_clicked(self, event):
        """Handles the mouse clicked event, updating the crosshair position and emitting signals.

        Args:
            event: The mouse clicked event
        """
        self.check_log()
        if self.plot_item.vb.sceneBoundingRect().contains(event._scenePos):
            mouse_point = self.plot_item.vb.mapSceneToView(event._scenePos)
            x, y = mouse_point.x(), mouse_point.y()

            if self.is_log_x:
                x = 10**x
            if self.is_log_y:
                y = 10**y
            x, y_values = self.snap_to_data(x, y)

            for item in self.plot_item.items:
                if isinstance(item, pg.PlotDataItem):
                    if x is None or all(v is None for v in y_values):
                        return
                    self.coordinatesClicked1D.emit(
                        round(x, self.precision),
                        [round(y_val, self.precision) for y_val in y_values],
                    )
                    for i, y_val in enumerate(y_values):
                        for marker in self.marker_clicked_1d[i]:
                            marker.setData(
                                [x if not self.is_log_x else np.log10(x)],
                                [y_val if not self.is_log_y else np.log10(y_val)],
                            )
                elif isinstance(item, pg.ImageItem):
                    if x is None or y_values is None:
                        return
                    self.coordinatesClicked2D.emit(x, y_values)
                    self.marker_2d.setPos([x, y_values])

    def check_log(self):
        """Checks if the x or y axis is in log scale and updates the internal state accordingly."""
        self.is_log_x = self.plot_item.ctrl.logXCheck.isChecked()
        self.is_log_y = self.plot_item.ctrl.logYCheck.isChecked()
