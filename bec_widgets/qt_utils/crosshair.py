import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QObject, pyqtSignal


class Crosshair(QObject):
    # Signal for 1D plot
    coordinatesChanged1D = pyqtSignal(float, list)
    coordinatesClicked1D = pyqtSignal(float, list)
    # Signal for 2D plot
    coordinatesChanged2D = pyqtSignal(float, float)
    coordinatesClicked2D = pyqtSignal(float, float)

    def __init__(self, plot_item, precision=None, parent=None):
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

        # Add marker for clicked and selected point
        data = self.get_data()
        if isinstance(data, list):  # 1D plot
            num_curves = len(data)
            self.marker_moved_1d = []
            self.marker_clicked_1d = []
            for i in range(num_curves):
                color = plot_item.listDataItems()[i].opts["pen"].color()
                marker_moved = pg.ScatterPlotItem(
                    size=10, pen=pg.mkPen(color), brush=pg.mkBrush(None)
                )  # Hollow
                marker_clicked = pg.ScatterPlotItem(
                    size=10, pen=pg.mkPen(None), brush=pg.mkBrush(color)
                )  # Full
                self.marker_moved_1d.append(marker_moved)
                self.marker_clicked_1d.append(marker_clicked)
                self.plot_item.addItem(marker_moved)
                self.plot_item.addItem(marker_clicked)
        else:  # 2D plot
            self.marker_2d = pg.ROI([0, 0], size=[1, 1], pen=pg.mkPen("r", width=2), movable=False)
            self.plot_item.addItem(self.marker_2d)

    def get_data(self):
        curves = []
        for item in self.plot_item.items:
            if isinstance(item, pg.PlotDataItem):  # 1D plot
                curves.append((item.xData, item.yData))
            elif isinstance(item, pg.ImageItem):  # 2D plot
                return item.image, None

        return curves

        # if curves:
        #     return curves
        # else:
        #     return None

    def snap_to_data(self, x, y):
        data = self.get_data()
        # if data is None: #TODO hadle if data are None
        #     return x, y

        if isinstance(data, list):  # 1D plot
            y_values = []
            for x_data, y_data in data:
                closest_x, closest_y = self.closest_x_y_value(x, x_data, y_data)
                y_values.append(closest_y)
            return x, y_values
        elif isinstance(data[0], np.ndarray):  # 2D plot
            x_idx = int(np.clip(x, 0, data[0].shape[0] - 1))
            y_idx = int(np.clip(y, 0, data[0].shape[1] - 1))
            return x_idx, y_idx
        return x, y

    def closest_x_y_value(self, input_value, list_x, list_y):
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

            if isinstance(y_values, list):  # 1D plot
                self.coordinatesChanged1D.emit(
                    round(x, self.precision), [round(y_val, self.precision) for y_val in y_values]
                )
                for i, y_val in enumerate(y_values):
                    self.marker_moved_1d[i].setData(
                        [x if not self.is_log_x else np.log10(x)],
                        [y_val if not self.is_log_y else np.log10(y_val)],
                    )
            else:  # 2D plot
                self.coordinatesChanged2D.emit(x, y_values)

    def mouse_clicked(self, event):
        self.check_log()
        if self.plot_item.vb.sceneBoundingRect().contains(event._scenePos):
            mouse_point = self.plot_item.vb.mapSceneToView(event._scenePos)
            x, y = mouse_point.x(), mouse_point.y()
            if self.is_log_x:
                x = 10**x
            if self.is_log_y:
                y = 10**y
            x, y_values = self.snap_to_data(x, y)
            if isinstance(y_values, list):  # 1D plot
                self.coordinatesClicked1D.emit(
                    round(x, self.precision), [round(y_val, self.precision) for y_val in y_values]
                )
                for i, y_val in enumerate(y_values):
                    self.marker_clicked_1d[i].setData(
                        [x if not self.is_log_x else np.log10(x)],
                        [y_val if not self.is_log_y else np.log10(y_val)],
                    )
            else:  # 2D plot
                self.coordinatesClicked2D.emit(x, y_values)
                self.marker_2d.setPos([x, y_values])

    def check_log(self):
        """
        Check if x or y axis is in log scale
        """
        self.is_log_x = self.plot_item.ctrl.logXCheck.isChecked()
        self.is_log_y = self.plot_item.ctrl.logYCheck.isChecked()
