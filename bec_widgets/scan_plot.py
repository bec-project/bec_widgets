import itertools

import pyqtgraph as pg
from bec_lib.core.logger import bec_logger
from PyQt5.QtCore import pyqtProperty, pyqtSlot

logger = bec_logger.logger


pg.setConfigOptions(background="w", foreground="k", antialias=True)
COLORS = ["#fd7f6f", "#7eb0d5", "#b2e061", "#bd7ebe", "#ffb55a"]


class BECScanPlot(pg.PlotWidget):
    def __init__(self, parent=None, background="default"):
        super().__init__(parent, background)

        self._x_channel = ""
        self._y_channel_list = []

        self.scan_curves = {}
        self.dap_curves = {}

    def initialize(self):
        plot_item = self.getPlotItem()
        plot_item.addLegend()
        colors = itertools.cycle(COLORS)

        for y_chan in self.y_channel_list:
            if y_chan.startswith("dap."):
                y_chan = y_chan.partition("dap.")[-1]
                curves = self.dap_curves
            else:
                curves = self.scan_curves

            curves[y_chan] = plot_item.plot(
                x=[], y=[], pen=pg.mkPen(color=next(colors), width=2), name=y_chan
            )

        plot_item.setLabel("bottom", self._x_channel)
        if len(self.scan_curves) == 1:
            plot_item.setLabel("left", next(iter(self.scan_curves)))

    @pyqtSlot("PyQt_PyObject")
    def clearData(self, _msg):
        for plot_curve in {**self.scan_curves, **self.dap_curves}.values():
            plot_curve.setData(x=[], y=[])

    @pyqtSlot("PyQt_PyObject")
    def redraw_scan(self, msg):
        if not self.x_channel:
            return

        data = msg.content["data"]

        if self.x_channel not in data:
            logger.warning(f"Unknown channel `{self.x_channel}` for X data in {self.objectName()}")
            return

        x_new = data[self.x_channel][self.x_channel]["value"]
        for chan, plot_curve in self.scan_curves.items():
            if not chan:
                continue

            if chan not in data:
                logger.warning(f"Unknown channel `{chan}` for Y data in {self.objectName()}")
                continue

            y_new = data[chan][chan]["value"]
            x, y = plot_curve.getData()  # TODO: is it a good approach?
            if x is None:
                x = []
            if y is None:
                y = []

            plot_curve.setData(x=[*x, x_new], y=[*y, y_new])

    @pyqtSlot(dict)
    def redraw_dap(self, data):
        for chan, plot_curve in self.dap_curves.items():
            if not chan:
                continue

            if chan not in data:
                logger.warning(f"Unknown channel `{chan}` for DAP data in {self.objectName()}")
                continue

            x_new = data[chan]["x"]
            y_new = data[chan]["y"]

            plot_curve.setData(x=x_new, y=y_new)

    @pyqtProperty("QStringList")
    def y_channel_list(self):
        return self._y_channel_list

    @y_channel_list.setter
    def y_channel_list(self, new_list):
        self._y_channel_list = new_list

    @pyqtProperty(str)
    def x_channel(self):
        return self._x_channel

    @x_channel.setter
    def x_channel(self, new_val):
        self._x_channel = new_val


if __name__ == "__main__":
    import sys

    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    plot = BECScanPlot()
    plot.y_channel_list = ["a", "b", "c"]

    plot.initialize()
    plot.show()

    sys.exit(app.exec_())
