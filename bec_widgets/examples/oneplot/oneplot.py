import os

import PyQt5.QtWidgets
import numpy as np

import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtWidgets import QTableWidgetItem
from pyqtgraph import mkBrush, mkPen
from pyqtgraph.Qt import QtCore, uic

from bec_widgets.qt_utils import Crosshair
from bec_lib.core import MessageEndpoints

# TODO implement:
#   - implement scanID database for visualizing previous scans
#   - multiple signals for different monitors


class PlotApp(QWidget):
    """
    Main class for the PlotApp used to plot two signals from the BEC.

    Attributes:
        update_signal (pyqtSignal): Signal to trigger plot updates.
        update_dap_signal (pyqtSignal): Signal to trigger DAP updates.

    Args:
        x_value (str): The x device/signal for plotting.
        y_values (list of str): List of y device/signals for plotting.
        dap_worker (str, optional): DAP process to specify. Set to None to disable.
        parent (QWidget, optional): Parent widget.
    """

    update_signal = pyqtSignal()
    update_dap_signal = pyqtSignal()

    def __init__(self, x_value, y_values, dap_worker=None, parent=None):
        super(PlotApp, self).__init__(parent)
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "oneplot.ui"), self)

        self.x_value = x_value
        self.y_values = y_values
        self.dap_worker = dap_worker  # if dap_worker is not None else ""

        self.scanID = None
        self.data_x = []
        self.data_y = []

        self.dap_x = np.array([])
        self.dap_y = np.array([])

        self.fit = None

        self.init_ui()
        self.init_curves()
        self.hook_crosshair()

        self.proxy_update_plot = pg.SignalProxy(
            self.update_signal, rateLimit=25, slot=self.update_plot
        )
        self.proxy_update_fit = pg.SignalProxy(
            self.update_dap_signal, rateLimit=25, slot=self.update_fit_table
        )

    def init_ui(self) -> None:
        """Initialize the UI components."""
        self.plot = pg.PlotItem()
        self.glw.addItem(self.plot)
        self.plot.setLabel("bottom", self.x_value)
        self.plot.setLabel("left", ", ".join(self.y_values))
        self.plot.addLegend()

    def init_curves(self) -> None:
        """Initialize curve data and properties."""
        self.plot.clear()

        self.curves_data = []
        self.curves_dap = []
        self.pens = []
        self.brushs = []  # todo check if needed

        color_list = [
            "#384c6b",
            "#e28a2b",
            "#5E3023",
            "#e41a1c",
            "#984e83",
            "#4daf4a",
        ]  # todo change to cmap

        for ii, monitor in enumerate(self.y_values):
            pen_curve = mkPen(color=color_list[ii], width=2, style=QtCore.Qt.DashLine)
            brush = mkBrush(color=color_list[ii], width=2, style=QtCore.Qt.DashLine)
            curve_data = pg.PlotDataItem(
                pen=pen_curve,
                skipFiniteCheck=True,
                symbolBrush=brush,
                symbolSize=5,
                name=monitor + "_data",
            )
            self.curves_data.append(curve_data)
            self.pens.append(pen_curve)
            self.plot.addItem(curve_data)
            if self.dap_worker is not None:
                pen_dap = mkPen(color=color_list[ii + 1], width=2, style=QtCore.Qt.DashLine)
                curve_dap = pg.PlotDataItem(pen=pen_dap, size=5, name=monitor + "_fit")
                self.curves_dap.append(curve_dap)
                self.plot.addItem(curve_dap)

        self.tableWidget_crosshair.setRowCount(len(self.y_values))
        self.tableWidget_crosshair.setVerticalHeaderLabels(self.y_values)
        self.hook_crosshair()

    def hook_crosshair(self) -> None:
        """Attach the crosshair to the plot."""
        self.crosshair_1d = Crosshair(self.plot, precision=3)
        self.crosshair_1d.coordinatesChanged1D.connect(
            lambda x, y: self.update_table(self.tableWidget_crosshair, x, y, column=0)
        )
        self.crosshair_1d.coordinatesClicked1D.connect(
            lambda x, y: self.update_table(self.tableWidget_crosshair, x, y, column=1)
        )

    def update_table(
        self, table_widget: PyQt5.QtWidgets.QTableWidget, x: float, y_values: list, column: int
    ) -> None:
        for i, y in enumerate(y_values):
            table_widget.setItem(i, column, QTableWidgetItem(f"({x}, {y})"))
            table_widget.resizeColumnsToContents()

    def update_plot(self) -> None:
        """Update the plot data."""
        self.curves_data[0].setData(self.data_x, self.data_y)
        if self.dap_worker is not None:
            self.curves_dap[0].setData(self.dap_x, self.dap_y)

    def update_fit_table(self):
        """Update the table for fit data."""

        self.tableWidget_fit.setData(self.fit)

    @pyqtSlot(dict, dict)
    def on_dap_update(self, msg: dict, metadata: dict) -> None:
        """
        Update DAP  related data.

        Args:
            msg (dict): Message received with data.
            metadata (dict): Metadata of the DAP.
        """

        self.dap_x = msg[self.dap_worker]["x"]
        self.dap_y = msg[self.dap_worker]["y"]

        self.fit = metadata["fit_parameters"]

        self.update_dap_signal.emit()

    @pyqtSlot(dict, dict)
    def on_scan_segment(self, msg: dict, metadata: dict):
        """
        Handle new scan segments.

        Args:
            msg (dict): Message received with scan data.
            metadata (dict): Metadata of the scan.
        """
        current_scanID = msg["scanID"]

        if current_scanID != self.scanID:
            self.scanID = current_scanID
            self.data_x = []
            self.data_y = []
            self.init_curves()

        dev_x = self.x_value
        dev_y = self.y_values[0]

        # TODO put warning that I am putting 1st one

        data_x = msg["data"][dev_x][dev[dev_x]._hints[0]]["value"]
        data_y = msg["data"][dev_y][dev[dev_y]._hints[0]]["value"]

        self.data_x.append(data_x)
        self.data_y.append(data_y)

        self.update_signal.emit()


if __name__ == "__main__":
    import argparse

    from bec_widgets import ctrl_c
    from bec_widgets.bec_dispatcher import bec_dispatcher

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--x_value",
        type=str,
        default="samx",
        help="Specify the x device/signal for plotting",
    )
    parser.add_argument(
        "--y_values",
        type=str,
        nargs="+",
        default=["gauss_bpm"],
        help="Specify the y device/signals for plotting",
    )
    parser.add_argument("--dap_worker", type=str, default=None, help="Specify the DAP process")

    args = parser.parse_args()

    x_value = args.x_value
    y_values = args.y_values
    dap_worker = None if args.dap_worker == "None" else args.dap_worker

    # Convert dap_worker to None if it's the string "None", for testing "gaussian_fit_worker_3"
    dap_worker = None if args.dap_worker == "None" else args.dap_worker

    # Retrieve the dap_process value
    # dap_worker = args.dap_worker

    # BECclient global variables
    client = bec_dispatcher.client
    client.start()

    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    app = QApplication([])
    plotApp = PlotApp(x_value=x_value, y_values=y_values, dap_worker=dap_worker)

    # Connecting signals from bec_dispatcher
    bec_dispatcher.connect_dap_slot(plotApp.on_dap_update, dap_worker)
    bec_dispatcher.connect_slot(plotApp.on_scan_segment, MessageEndpoints.scan_segment())
    ctrl_c.setup(app)

    window = plotApp
    window.show()
    app.exec_()
