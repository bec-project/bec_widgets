from typing import Any

import numpy as np
import pyqtgraph as pg
from pyqtgraph import mkPen, mkBrush

from pyqtgraph.Qt import QtCore, QtWidgets, uic
from pyqtgraph.Qt.QtCore import pyqtSignal
import os


class BasicPlot(QtWidgets.QWidget):
    update_signal = pyqtSignal()

    def __init__(self, name="", y_value_list=["gauss_bpm"]):
        super(BasicPlot, self).__init__()
        # Set style for pyqtgraph plots
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "line_plot.ui"), self)

        self._idle_time = 100
        self.title = ""
        self.label_bottom = ""
        self.label_left = ""

        self.scan_motors = []
        self.y_value_list = y_value_list
        self.plotter_data_x = []
        self.plotter_data_y = []
        self.curves = []
        self.pens = []

        self.plotter_scan_id = None

        # TODO to be moved to utils function
        plotstyles = {
            "symbol": "o",
            "symbolSize": 12,
        }
        color_list = ["#384c6b", "#e28a2b", "#5E3023", "#e41a1c", "#984e83", "#4daf4a"]

        # setup plots
        self.plot = self.plot_window.getPlotItem()
        for ii in range(len(self.y_value_list)):
            if ii < len(color_list):
                pen = mkPen(color=color_list[ii], width=2, style=QtCore.Qt.DashLine)
            else:
                pen = mkPen(
                    color=list(np.random.choice(range(255), size=3)),
                    width=2,
                    style=QtCore.Qt.DashLine,
                )
            curve = pg.ScatterPlotItem(**plotstyles, pen=pen, skipFiniteCheck=True)
            self.plot.addItem(curve)
            self.curves.append(curve)
            self.pens.append(pen)

        # self.plot.plot(**plotstyles)
        # self.plot_data = self.plot.plot([], [], **plotstyles, pen=self.pen, title=name)
        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False)
        self.plot.addItem(self.crosshair_v, ignoreBounds=True)

        # Add textItems
        self.add_text_items()

        # Manage signals
        self.proxy = pg.SignalProxy(
            self.plot.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved
        )
        self.proxy_update = pg.SignalProxy(self.update_signal, rateLimit=25, slot=self.update)

    def add_text_items(self):
        self.mouse_box_data.setText("Mouse cursor")
        # self.mouse_box_data.setStyleSheet(f"QLabel {{color : rgba{self.pens[0].color().getRgb()}}}")

    def mouse_moved(self, event):
        pos = event[0]
        if self.plot.sceneBoundingRect().contains(pos):
            mousePoint = self.plot.vb.mapSceneToView(pos)
            self.crosshair_v.setPos(mousePoint.x())
            if self.plotter_data_x:
                self.mouse_box_data.setText("Mouse cursor")
                for ii, y_value in enumerate(self.y_value_list):
                    closest_point = self.closest_x_y_value(
                        mousePoint.x(), self.plotter_data_x, self.plotter_data_y[ii]
                    )
                    self.mouse_box_data.setText(
                        "".join(
                            [
                                self.mouse_box_data.text(),
                                "\n",
                                f"<p'FONT COLOR=red';>",  # rgba{self.pens[ii].color().getRgb()
                                f"{y_value}",
                                "\n",
                                f"X_data: {closest_point[0]:.{self.precision}f}",
                                "\n",
                                f"Y_data: {closest_point[1]:.{self.precision}f}</p>",
                            ]
                        )
                        # f"Mouse cursor\n"
                        # \n"
                        # f"Y_data: {closest_point[1]:.{self.precision}f}\n"
                    )

    def closest_x_y_value(self, input_value, list_x, list_y):
        arr = np.asarray(list_x)
        i = (np.abs(arr - input_value)).argmin()
        return list_x[i], list_y[i]

    def update(self):
        if len(self.plotter_data_x) <= 1:
            return
        self.plot.setLabel("bottom", self.label_bottom)
        self.plot.setLabel("left", self.label_left)
        for ii in range(len(self.y_value_list)):
            self.curves[ii].setData(self.plotter_data_x, self.plotter_data_y[ii])

    def __call__(self, data: dict, metadata: dict, **kwds: Any) -> None:
        """Update function that is called during the scan callback. To avoid
        too many renderings, the GUI is only processing events every <_idle_time> ms.

        Args:
            data (dict): Dictionary containing a new scan segment
            metadata (dict): Scan metadata

        """
        if metadata["scanID"] != self.plotter_scan_id:
            self.plotter_scan_id = metadata["scanID"]
            self._reset_plot_data()

        self.title = f"Scan {metadata['scan_number']}"

        self.scan_motors = scan_motors = metadata.get("scan_report_devices")
        client = BECClient()
        self.precision = client.device_manager.devices[scan_motors[0]]._info["describe"][
            scan_motors[0]
        ]["precision"]
        # TODO
        # self.precision = client.device_manager.devices[scan_motors[0]].precision
        x = data["data"][scan_motors[0]][scan_motors[0]]["value"]
        self.plotter_data_x.append(x)
        for ii, y_value in enumerate(self.y_value_list):
            y = data["data"][y_value][y_value]["value"]
            self.plotter_data_y[ii].append(y)
        self.label_bottom = scan_motors[0]
        self.label_left = f"{', '.join(self.y_value_list)}"

        if len(self.plotter_data_x) <= 1:
            return
        self.update_signal.emit()

    def _reset_plot_data(self):
        self.plotter_data_x = []
        self.plotter_data_y = []
        for ii in range(len(self.y_value_list)):
            self.curves[ii].setData([], [])
            self.plotter_data_y.append([])
        self.mouse_box_data.setText("Mouse cursor")  # Crashes the Thread


if __name__ == "__main__":
    import argparse
    from bec_lib import BECClient
    from bec_widgets import ctrl_c

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--signals", help="specify recorded signals", nargs="+", default=["gauss_bpm"]
    )
    value = parser.parse_args()
    print(f"Plotting signals for: {', '.join(value.signals)}")
    client = BECClient()
    client.start()
    app = QtWidgets.QApplication([])
    ctrl_c.setup(app)
    plot = BasicPlot(y_value_list=value.signals)
    plot.show()
    client.callbacks.register("scan_segment", plot, sync=False)
    app.exec_()
