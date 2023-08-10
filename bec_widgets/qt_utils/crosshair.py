import pyqtgraph as pg
import numpy as np
from PyQt5.QtCore import pyqtSignal, QObject


class Crosshair(QObject):
    coordinatesChanged = pyqtSignal(float, float)
    dataPointClicked = pyqtSignal(float, float)

    def __init__(self, plot_item, is_image=False, parent=None):
        super().__init__(parent)
        self.plot_item = plot_item
        self.data_shape = None
        self.is_image = is_image
        self.v_line = pg.InfiniteLine(angle=90, movable=False)
        self.h_line = pg.InfiniteLine(angle=0, movable=False)
        self.plot_item.addItem(self.v_line, ignoreBounds=True)
        self.plot_item.addItem(self.h_line, ignoreBounds=True)
        self.proxy = pg.SignalProxy(
            self.plot_item.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved
        )
        self.plot_item.scene().sigMouseClicked.connect(self.mouse_clicked)

    def mouse_moved(self, event):
        pos = event[0]
        if self.data_shape is not None and self.plot_item.vb.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_item.vb.mapSceneToView(pos)
            x = int(np.clip(np.round(mouse_point.x()), 0, self.data_shape[1] - 1))
            y = int(np.clip(np.round(mouse_point.y()), 0, self.data_shape[0] - 1))
            self.v_line.setPos(x)
            self.h_line.setPos(y)
            self.coordinatesChanged.emit(x, y)

    def mouse_clicked(self, event):
        if self.data_shape is not None and self.plot_item.vb.sceneBoundingRect().contains(
            event._scenePos
        ):
            mouse_point = self.plot_item.vb.mapSceneToView(event._scenePos)
            x = int(np.clip(np.round(mouse_point.x()), 0, self.data_shape[1] - 1))
            y = int(np.clip(np.round(mouse_point.y()), 0, self.data_shape[0] - 1))
            self.v_line.setPos(x)
            self.h_line.setPos(y)
            self.dataPointClicked.emit(x, y)

    def set_data_shape(self, shape):
        self.data_shape = shape
