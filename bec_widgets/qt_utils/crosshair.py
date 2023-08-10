import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal, QObject


class Crosshair(QObject):
    coordinatesChanged = pyqtSignal(float, float)
    dataPointClicked = pyqtSignal(float, float)

    def __init__(self, plot_item, precision=None, parent=None):
        super().__init__(parent)
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

    def get_data(self):
        x_data, y_data = [], []
        for item in self.plot_item.items:
            if isinstance(item, pg.ImageItem):
                return item.image, None  # Return image data for 2D plot
            elif isinstance(item, pg.PlotDataItem):
                x_data.extend(item.xData)
                y_data.extend(item.yData)
        if x_data and y_data:
            return np.array(x_data), np.array(y_data)  # Return x and y data for 1D plot
        return None, None

    def mouse_moved(self, event):
        pos = event[0]
        if self.plot_item.vb.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_item.vb.mapSceneToView(pos)
            x, y = self.snap_to_data(mouse_point.x(), mouse_point.y())
            self.v_line.setPos(x)
            self.h_line.setPos(y)
            self.coordinatesChanged.emit(x, y)

    def mouse_clicked(self, event):
        if self.plot_item.vb.sceneBoundingRect().contains(event._scenePos):
            mouse_point = self.plot_item.vb.mapSceneToView(event._scenePos)
            x, y = self.snap_to_data(mouse_point.x(), mouse_point.y())
            self.dataPointClicked.emit(x, y)

    def snap_to_data(self, x, y):
        x_data, y_data = self.get_data()
        if x_data is not None and y_data is not None:
            distance = (x_data - x) ** 2 + (y_data - y) ** 2
            index = np.argmin(distance)
            x, y = x_data[index], y_data[index]
            if self.precision is not None:
                x, y = round(x, self.precision), round(y, self.precision)
            return x, y
        elif x_data is not None and y_data is None:  # For 2D plot (ImageItem)
            x_idx = int(np.clip(x, 0, x_data.shape[1] - 1))
            y_idx = int(np.clip(y, 0, x_data.shape[0] - 1))
            return x_idx, y_idx
        return x, y
