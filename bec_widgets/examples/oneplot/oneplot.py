import os
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
#   - add crosshair
#   - add crosshair table
#   - implement scanID database for visualizing previous scans
#   - multiple signals for different monitors
#   - user can choose what motor against what monitor to plot
#   - crosshair snaps now just to fit, not to actual data


class PlotApp(QWidget):
    update_signal = pyqtSignal()
    update_dap_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.scanID = None
        self.motor_data = []
        self.monitor_data = []

        self.dap_x = np.array([])
        self.dap_y = np.array([])

        self.fit = None

        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "oneplot.ui"), self)

        self.monitor_names = ["gauss_bpm"]

        self.init_ui()
        self.init_curves()
        self.hook_crosshair()

        self.proxy_update_plot = pg.SignalProxy(
            self.update_signal, rateLimit=25, slot=self.update_plot
        )
        self.proxy_update_fit = pg.SignalProxy(
            self.update_dap_signal, rateLimit=25, slot=self.update_fit_table
        )

    def init_ui(self):
        self.plot = pg.PlotItem()
        self.glw.addItem(self.plot)
        self.plot.setLabel("bottom", "Motor")
        self.plot.setLabel("left", "Monitor")
        self.plot.addLegend()

    def init_curves(self):
        self.plot.clear()

        self.curves = []
        self.scatters = []
        self.pens = []
        self.brushs = []  # todo check if needed

        color_list = ["#384c6b", "#e28a2b", "#5E3023", "#e41a1c", "#984e83", "#4daf4a"]

        for ii, monitor in enumerate(self.monitor_names):
            print(self.monitor_names[ii])
            pen = mkPen(color=color_list[ii], width=2, style=QtCore.Qt.DashLine)
            # brush = mkBrush(color=color_list[ii])
            curve = pg.PlotDataItem(pen=pen, skipFiniteCheck=True)  # ,symbolBrush=brush)
            scatter = pg.ScatterPlotItem(pen=pen, size=5, name=monitor)  # ,brush=brush,)
            # scatter = pg.PlotDataItem(
            #     pen=None, symbol="o", symbolBrush=color_list[ii], name=monitor
            # )
            self.curves.append(curve)
            self.scatters.append(scatter)
            self.pens.append(pen)
            # self.brushs.append(brush)
            self.plot.addItem(curve)
            self.plot.addItem(scatter)

        # TODO hook signals
        # TODO hook crosshair
        self.tableWidget_crosshair.setRowCount(len(self.monitor_names))
        self.tableWidget_crosshair.setVerticalHeaderLabels(self.monitor_names)
        self.hook_crosshair()

    def hook_crosshair(self):
        self.crosshair_1d = Crosshair(self.plot, precision=3)
        self.crosshair_1d.coordinatesChanged1D.connect(
            lambda x, y: self.update_table(self.tableWidget_crosshair, x, y, column=0)
        )
        self.crosshair_1d.coordinatesClicked1D.connect(
            lambda x, y: self.update_table(self.tableWidget_crosshair, x, y, column=1)
        )

    def update_table(self, table_widget, x, y_values, column):
        """Update the table with the new coordinates"""
        for i, y in enumerate(y_values):
            table_widget.setItem(i, column, QTableWidgetItem(f"({x}, {y})"))
            table_widget.resizeColumnsToContents()

    def update_plot(self):
        self.curves[0].setData(self.dap_x, self.dap_y)
        self.scatters[0].setData(self.motor_data, self.monitor_data)

    def update_fit_table(self):
        self.tableWidget_fit.setData(self.fit)

    @pyqtSlot(dict, dict)
    def on_dap_update(self, msg, metadata) -> None:
        """
        Getting processed data from DAP

        Args:
            msg (dict):
            metadata(dict):
        """
        ...
        print("on_dap_update")
        # print(f'msg "on_dap_update" = {msg}')

        dapMSG = msg
        metaMSG = metadata

        self.dap_x = msg["gaussian_fit_worker_3"]["x"]
        self.dap_y = msg["gaussian_fit_worker_3"]["y"]

        self.fit = metadata["fit_parameters"]

        self.update_dap_signal.emit()

    @pyqtSlot(dict, dict)
    def on_scan_segment(self, msg, metadata):
        # TODO x -> motor
        # TODO y -> monitor._hints :list
        print("on_scan_segment")

        current_scanID = msg["scanID"]
        # print(f"current_scanID = {current_scanID}")

        # implement if condition that if scan id is different than last one init new scan variables
        if current_scanID != self.scanID:
            self.scanID = current_scanID
            self.motor_data = []
            self.monitor_data = []
            self.init_curves()

        motor_data = msg["data"]["samx"]["samx"]["value"]
        monitor_data = msg["data"]["gauss_bpm"]["gauss_bpm"][
            "value"
        ]  # gaussbpm._hints -> implement logic with list
        #
        self.motor_data.append(motor_data)
        self.monitor_data.append(monitor_data)

        # self.update_plot.emit()
        self.update_signal.emit()

    # @pyqtSlot(dict, dict)
    # def on_new_scan(self, msg, metadata):  # TODO probably not needed
    #     """
    #     Initiate new scan and clear previous data
    #     Args:
    #         msg(dict):
    #         metadata(dict):
    #
    #     Returns:
    #
    #     """

    # print(40 * "#" + "on_new_scan" + 40 * "#")

    # self.motor_data = [msg["data"]["samx"]["samx"]["value"]]
    # self.monitor_data = [msg["data"]["gauss_bpm"]["gauss_bpm"]["value"]]
    # self.init_curves()


if __name__ == "__main__":
    # from bec_lib import BECClient
    from bec_widgets import ctrl_c
    from bec_widgets.bec_dispatcher import bec_dispatcher

    client = bec_dispatcher.client
    client.start()

    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    app = QApplication([])

    plotApp = PlotApp()

    bec_dispatcher.connect_dap_slot(plotApp.on_dap_update, "gaussian_fit_worker_3")
    bec_dispatcher.connect_slot(plotApp.on_scan_segment, MessageEndpoints.scan_segment())
    # bec_dispatcher.new_scan.connect(plotApp.on_new_scan)  # TODO check if works!
    # bec_dispatcher.connect_slot(plotApp.on_new_scan,)
    ctrl_c.setup(app)

    window = plotApp
    window.show()
    app.exec_()
