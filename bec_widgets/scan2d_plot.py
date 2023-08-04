import numpy as np
import pyqtgraph as pg
from bec_lib.core.logger import bec_logger
from PyQt5.QtCore import pyqtProperty, pyqtSlot

from bec_widgets.bec_dispatcher import bec_dispatcher

logger = bec_logger.logger


pg.setConfigOptions(background="w", foreground="k", antialias=True)


class BECScanPlot2D(pg.GraphicsView):
    def __init__(self, parent=None, background="default"):
        super().__init__(parent, background)
        bec_dispatcher.connect(self)

        self._x_channel = ""
        self._y_channel = ""
        self._z_channel = ""

        self._xpos = []
        self._ypos = []

        self._x_ind = None
        self._y_ind = None

        self.plot_item = pg.PlotItem()
        self.setCentralItem(self.plot_item)
        self.plot_item.setAspectLocked(True)

        self.imageItem = pg.ImageItem()
        self.plot_item.addItem(self.imageItem)

    @pyqtSlot(dict, dict)
    def on_new_scan(self, _scan_segment, metadata):
        # TODO: Do we reset in case of a scan type change?
        self.imageItem.clear()

        # TODO: better to check the number of coordinates in metadata["positions"]?
        if metadata["scan_name"] != "grid_scan":
            return

        positions = [sorted(set(pos)) for pos in zip(*metadata["positions"])]

        motors = metadata["scan_motors"]
        if self.x_channel and self.y_channel:
            self._x_ind = motors.index(self.x_channel) if self.x_channel in motors else None
            self._y_ind = motors.index(self.y_channel) if self.y_channel in motors else None
        elif not self.x_channel and not self.y_channel:
            # Plot the first and second motors along x and y axes respectively
            self._x_ind = 0
            self._y_ind = 1
        else:
            logger.warning(
                f"X and Y channels should be either both empty or both set in {self.objectName()}"
            )

        if self._x_ind is None or self._y_ind is None:
            return

        xpos = positions[self._x_ind]
        ypos = positions[self._y_ind]

        self._xpos = xpos
        self._ypos = ypos

        self.imageItem.setImage(np.zeros(shape=(len(xpos), len(ypos))))

        w = max(xpos) - min(xpos)
        h = max(ypos) - min(ypos)
        w_pix = w / (len(xpos) - 1)
        h_pix = h / (len(ypos) - 1)
        self.imageItem.setRect(min(xpos) - w_pix / 2, min(ypos) - h_pix / 2, w + w_pix, h + h_pix)

        self.plot_item.setLabel("bottom", motors[self._x_ind])
        self.plot_item.setLabel("left", motors[self._y_ind])

    @pyqtSlot(dict, dict)
    def on_scan_segment(self, scan_segment, metadata):
        if not self.z_channel or metadata["scan_name"] != "grid_scan":
            return

        if self._x_ind is None or self._y_ind is None:
            return

        point_coord = metadata["positions"][scan_segment["point_id"]]

        x_coord_ind = self._xpos.index(point_coord[self._x_ind])
        y_coord_ind = self._ypos.index(point_coord[self._y_ind])

        data = scan_segment["data"]
        z_new = data[self.z_channel][self.z_channel]["value"]

        image = self.imageItem.image
        image[x_coord_ind, y_coord_ind] = z_new
        self.imageItem.setImage()

    @pyqtProperty(str)
    def x_channel(self):
        return self._x_channel

    @x_channel.setter
    def x_channel(self, new_val):
        self._x_channel = new_val
        self.plot_item.setLabel("bottom", new_val)

    @pyqtProperty(str)
    def y_channel(self):
        return self._y_channel

    @y_channel.setter
    def y_channel(self, new_val):
        self._y_channel = new_val
        self.plot_item.setLabel("left", new_val)

    @pyqtProperty(str)
    def z_channel(self):
        return self._z_channel

    @z_channel.setter
    def z_channel(self, new_val):
        self._z_channel = new_val


if __name__ == "__main__":
    import sys

    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    plot = BECScanPlot2D()
    # If x_channel and y_channel are both omitted, they will be inferred from each running grid scan
    plot.z_channel = "bpm3y"

    plot.show()

    sys.exit(app.exec_())
