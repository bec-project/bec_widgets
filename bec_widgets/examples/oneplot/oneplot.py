import os

import PyQt5.QtWidgets
import numpy as np

import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtWidgets import QTableWidgetItem
from pyqtgraph import mkBrush, mkPen
from pyqtgraph import mkBrush, mkColor, mkPen
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
        self.dap_worker = dap_worker

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

        colors_y_values = PlotApp.golden_angle_color(colormap="CET-R2", num=len(self.y_values))
        # colors_y_daps = PlotApp.golden_angle_color(
        #     colormap="CET-I2", num=len(self.dap_worker)
        # )  # TODO adapt for multiple dap_workers

        # Initialize curves for y_values
        for ii, (signal, color) in enumerate(zip(self.y_values, colors_y_values)):
            pen_curve = mkPen(color=color, width=2, style=QtCore.Qt.DashLine)
            brush_curve = mkBrush(color=color)
            curve_data = pg.PlotDataItem(
                symbolSize=5,
                symbolBrush=brush_curve,
                pen=pen_curve,
                skipFiniteCheck=True,
                name=f"{signal}",
            )
            self.curves_data.append(curve_data)
            self.plot.addItem(curve_data)

        # Initialize curves for DAP if dap_worker is not None
        if self.dap_worker is not None:
            # for ii, (monitor, color) in enumerate(zip(self.dap_worker, colors_y_daps)):#TODO adapt for multiple dap_workers
            pen_dap = mkPen(color="#3b5998", width=2, style=QtCore.Qt.DashLine)
            curve_dap = pg.PlotDataItem(
                pen=pen_dap,
                skipFiniteCheck=True,
                symbolSize=5,
                name=f"{self.dap_worker}",
            )
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
        for ii, curve in enumerate(self.curves_data):
            curve.setData(self.data_x, self.data_y[ii])

        if self.dap_worker is not None:
            # for ii, curve in enumerate(self.curves_dap): #TODO adapt for multiple dap_workers
            #     curve.setData(self.dap_x, self.dap_y[ii])
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

        # TODO adapt for multiple dap_workers
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
            self.data_y = [[] for _ in self.y_values]
            self.init_curves()

        dev_x = self.x_value
        data_x = msg["data"][dev_x][dev[dev_x]._hints[0]]["value"]
        self.data_x.append(data_x)

        for ii, dev_y in enumerate(self.y_values):
            data_y = msg["data"][dev_y][dev[dev_y]._hints[0]]["value"]
            self.data_y[ii].append(data_y)

        self.update_signal.emit()

    @staticmethod
    def golden_ratio(num: int) -> list:
        """Calculate the golden ratio for a given number of angles.

        Args:
            num (int): Number of angles
        """
        phi = 2 * np.pi * ((1 + np.sqrt(5)) / 2)
        angles = []
        for ii in range(num):
            x = np.cos(ii * phi)
            y = np.sin(ii * phi)
            angle = np.arctan2(y, x)
            angles.append(angle)
        return angles

    @staticmethod
    def golden_angle_color(colormap: str, num: int) -> list:
        """
        Extract num colors for from the specified colormap following golden angle distribution.

        Args:
            colormap (str): Name of the colormap
            num (int): Number of requested colors

        Returns:
            list: List of colors with length <num>

        Raises:
            ValueError: If the number of requested colors is greater than the number of colors in the colormap.
        """

        cmap = pg.colormap.get(colormap)
        cmap_colors = cmap.color
        if num > len(cmap_colors):
            raise ValueError(
                f"Number of colors requested ({num}) is greater than the number of colors in the colormap ({len(cmap_colors)})"
            )
        angles = PlotApp.golden_ratio(len(cmap_colors))
        color_selection = np.round(np.interp(angles, (-np.pi, np.pi), (0, len(cmap_colors))))
        colors = [
            mkColor(tuple((cmap_colors[int(ii)] * 255).astype(int))) for ii in color_selection[:num]
        ]
        return colors


if __name__ == "__main__":
    import yaml
    from bec_widgets import ctrl_c
    from bec_widgets.bec_dispatcher import bec_dispatcher

    with open("config_noworker.yaml", "r") as file:
        config = yaml.safe_load(file)

    x_value = config["x_value"]
    y_values = config["y_values"]
    dap_worker = config["dap_worker"]

    dap_worker = None if dap_worker == "None" else dap_worker

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
