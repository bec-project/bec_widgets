import os
import threading
import time
import warnings
from typing import Any

import numpy as np
import pyqtgraph
import pyqtgraph as pg
from bec_lib.core import BECMessage
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QCheckBox, QTableWidgetItem
from pyqtgraph import mkBrush, mkColor, mkPen
from pyqtgraph.Qt import QtCore, QtWidgets, uic
from pyqtgraph.Qt.QtCore import pyqtSignal

from bec_widgets.bec_dispatcher import bec_dispatcher
from bec_lib.core.redis_connector import MessageObject, RedisConnector

client = bec_dispatcher.client


class BasicPlot(QtWidgets.QWidget):
    update_signal = pyqtSignal()
    roi_signal = pyqtSignal(tuple)

    def __init__(self, name="", y_value_list=["gauss_bpm"]) -> None:
        """
        Basic plot widget for displaying scan data.

        Args:
            name (str, optional): Name of the plot. Defaults to "".
            y_value_list (list, optional): List of signals to be plotted. Defaults to ["gauss_bpm"].
        """

        super(BasicPlot, self).__init__()
        # Set style for pyqtgraph plots
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "line_plot.ui"), self)

        # Set splitter distribution of widgets
        self.splitter.setSizes([3, 1])

        self._idle_time = 100
        self.title = ""
        self.label_bottom = ""
        self.label_left = ""
        self.producer = RedisConnector(["localhost:6379"]).producer()

        self.scan_motors = []
        self.y_value_list = y_value_list
        self.previous_y_value_list = None
        self.plotter_data_x = []
        self.plotter_data_y = []
        self.curves = []
        self.pens = []
        self.brushs = []

        self.plotter_scan_id = None

        # TODO to be moved to utils function
        plotstyles = {
            "symbol": "o",
            "symbolSize": 10,
        }

        color_list = BasicPlot.golden_angle_color(colormap="CET-R2", num=len(self.y_value_list))

        # setup plots - GraphicsLayoutWidget
        # LabelItem
        self.label = pg.LabelItem(justify="center")
        self.glw.addItem(self.label)
        self.label.setText("ROI region")

        # PlotItem - main window
        self.glw.nextRow()
        self.plot = pg.PlotItem()
        self.plot.setLogMode(True, True)
        self.glw.addItem(self.plot)
        self.plot.addLegend()

        # ImageItem - 2D view #TODO add 2D plot for ROI and 1D plot for mouse click
        self.glw.nextRow()
        self.plot_roi = pg.PlotItem()
        self.img = pg.ImageItem()
        self.glw.addItem(self.plot_roi)
        self.plot_roi.addItem(self.img)

        # ROI selector - so far from [-1,1] #TODO update to scale with xrange
        self.roi_selector = pg.LinearRegionItem([-1, 1])

        for ii, y_value in enumerate(self.y_value_list):
            pen = mkPen(color=color_list[ii], width=2, style=QtCore.Qt.DashLine)
            brush = mkBrush(color=color_list[ii])
            curve = pg.PlotDataItem(
                **plotstyles, symbolBrush=brush, pen=pen, skipFiniteCheck=True, name=y_value
            )
            self.plot.addItem(curve)
            self.curves.append(curve)
            self.pens.append(pen)
            self.brushs.append(brush)

        self.add_crosshair(self.plot)
        self.add_crosshair(self.plot_roi)

        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False)
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False)
        #
        # for plot in (self.plot_roi, self.plot):
        #     plot.addItem(self.crosshair_v, ignoreBounds=True)
        #     plot.addItem(self.crosshair_h, ignoreBounds=True)

        # self.plot.addItem(self.crosshair_v, ignoreBounds=True)
        # self.plot.addItem(self.crosshair_h, ignoreBounds=True)

        # self.plot_roi.addItem(self.crosshair_v, ignoreBounds=True)
        # self.plot_roi.addItem(self.crosshair_h, ignoreBounds=True)

        # Add textItems
        self.add_text_items()

        # Manage signals
        self.proxy = pg.SignalProxy(
            self.plot.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved
        )
        self.proxy_update = pg.SignalProxy(self.update_signal, rateLimit=25, slot=self.update)
        self.roi_selector.sigRegionChangeFinished.connect(self.get_roi_region)

        # Debug functions
        self.pushButton_debug.clicked.connect(self.generate_2D_data_update)
        # self.generate_2D_data()

        self._current_proj = None
        self._current_metadata_ep = "px_stream/projection_{}/metadata"

        self.data_retriever = threading.Thread(target=self.on_projection, daemon=True)
        self.data_retriever.start()

    def debug(self):
        """
        Debug button just for quick testing
        """

    def generate_2D_data(self):
        data = np.random.normal(size=(1, 100))
        self.img.setImage(data)

    def generate_2D_data_update(self):
        data = np.random.normal(size=(200, 300))
        self.img.setImage(data, levels=(0.2, 0.5))

    def add_crosshair(self, plot):
        crosshair_v = pg.InfiniteLine(angle=90, movable=False)
        crosshair_h = pg.InfiniteLine(angle=0, movable=False)

        plot.addItem(crosshair_v)
        plot.addItem(crosshair_h)

    def get_roi_region(self):
        """For testing purpose now, get roi region and print it to self.label as tuple"""
        region = self.roi_selector.getRegion()
        self.label.setText(f"x = {(10**region[0]):.4f}, y ={(10**region[1]):.4f}")
        return_dict = {
            "qranges": [
                np.where(self.plotter_data_x[0] > 10 ** region[0])[0][0],
                np.where(self.plotter_data_x[0] < 10 ** region[1])[0][-1],
            ]
        }
        msg = BECMessage.DeviceMessage(signals=return_dict).dumps()
        self.producer.set_and_publish("px_stream/gui_event", msg=msg)
        self.roi_signal.emit(region)

    def add_text_items(self):  # TODO probably can be removed
        """Add text items to the plot"""

        # self.mouse_box_data.setText("Mouse cursor")
        # TODO Via StyleSheet, one may set the color of the full QLabel
        # self.mouse_box_data.setStyleSheet(f"QLabel {{color : rgba{self.pens[0].color().getRgb()}}}")

    def mouse_moved(self, event: tuple) -> None:
        """
        Update the mouse table with the current mouse position and the corresponding data.

        Args:
            event (tuple):  Mouse event containing the position of the mouse cursor.
                            The position is stored in first entry as horizontal, vertical pixel.
        """
        pos = event[0]
        if not self.plot.sceneBoundingRect().contains(pos):
            return
        mousePoint = self.plot.vb.mapSceneToView(pos)
        self.crosshair_v.setPos(mousePoint.x())
        self.crosshair_h.setPos(mousePoint.y())
        if not self.plotter_data_x:
            return

        closest_point = self.closest_x_y_value(
            mousePoint.x(), self.plotter_data_x[0], self.plotter_data_y[0]
        )
        # self.precision = 3
        # ii = 0
        # y_value = self.y_value_list[ii]
        # x_data = f"{10**closest_point[0]:.{self.precision}f}"
        # y_data = f"{10**closest_point[1]:.{self.precision}f}"
        #
        # # Write coordinate to QTable
        # self.mouse_table.setItem(ii, 1, QTableWidgetItem(str(y_value)))
        # self.mouse_table.setItem(ii, 2, QTableWidgetItem(str(x_data)))
        # self.mouse_table.setItem(ii, 3, QTableWidgetItem(str(y_data)))
        #
        # self.mouse_table.resizeColumnsToContents()

    def closest_x_y_value(self, input_value, list_x, list_y) -> tuple:
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

    def update(self):
        """Update the plot with the new data."""
        # check if roi selector is in the plot
        if self.roi_selector not in self.plot.items:
            self.plot.addItem(self.roi_selector)

        # check if QTable was initialised and if list of devices was changed
        if self.y_value_list != self.previous_y_value_list:
            self.setup_cursor_table()
            self.previous_y_value_list = self.y_value_list.copy() if self.y_value_list else None

        self.curves[0].setData(self.plotter_data_x[0], self.plotter_data_y[0])
        # if len(self.plotter_data_x[0]) <= 1:
        #     return
        # self.plot.setLabel("bottom", self.label_bottom)
        # self.plot.setLabel("left", self.label_left)
        # for ii in range(len(self.y_value_list)):
        #     self.curves[0].setData(self.plotter_data_x[0], self.plotter_data_y[0])

    @pyqtSlot(dict, dict)
    def on_scan_segment(self, data: dict, metadata: dict) -> None:
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
        # client = BECClient()
        remove_y_value_index = [
            index
            for index, y_value in enumerate(self.y_value_list)
            if y_value not in client.device_manager.devices
        ]
        if remove_y_value_index:
            for ii in sorted(remove_y_value_index, reverse=True):
                # TODO Use bec warning message??? to be discussed with Klaus
                warnings.warn(
                    f"Warning: no matching signal for {self.y_value_list[ii]} found in list of devices. Removing from plot."
                )
                self.remove_curve_by_name(self.plot, self.y_value_list[ii])
                self.y_value_list.pop(ii)

        self.precision = client.device_manager.devices[scan_motors[0]]._info["describe"][
            scan_motors[0]
        ]["precision"]
        # TODO after update of bec_lib, this will be new way to access data
        # self.precision = client.device_manager.devices[scan_motors[0]].precision

        x = data["data"][scan_motors[0]][scan_motors[0]]["value"]
        self.plotter_data_x.append(x)
        for ii, y_value in enumerate(self.y_value_list):
            y = data["data"][y_value][y_value]["value"]
            self.plotter_data_y[ii].append(y)
        self.label_bottom = scan_motors[0]
        self.label_left = f"{', '.join(self.y_value_list)}"

        # print(f'metadata scan N{metadata["scan_number"]}') #TODO put as label on top of plot
        # print(f'Data point = {data["point_id"]}') #TODO can be used for progress bar

        if len(self.plotter_data_x) <= 1:
            return
        self.update_signal.emit()

    def _reset_plot_data(self):
        """Reset the plot data."""
        self.plotter_data_x = []
        self.plotter_data_y = []
        for ii in range(len(self.y_value_list)):
            self.curves[ii].setData([], [])
            self.plotter_data_y.append([])

    def setup_cursor_table(self):
        """QTable formatting according to N of devices displayed in plot."""

        # Init number of rows in table according to n of devices
        self.mouse_table.setRowCount(len(self.y_value_list))

        for ii, y_value in enumerate(self.y_value_list):
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            # TODO just for testing, will be replaced by removing/adding curve
            checkbox.stateChanged.connect(lambda: print("status Changed"))
            # checkbox.stateChanged.connect(lambda: self.remove_curve_by_name(plot=self.plot, checkbox=checkbox, name=y_value))
            self.mouse_table.setCellWidget(ii, 0, checkbox)
            self.mouse_table.setItem(ii, 1, QTableWidgetItem(str(y_value)))

            self.mouse_table.resizeColumnsToContents()

    @staticmethod
    def remove_curve_by_name(plot: pyqtgraph.PlotItem, name: str) -> None:
        # def remove_curve_by_name(plot: pyqtgraph.PlotItem, checkbox: QtWidgets.QCheckBox, name: str) -> None:
        """Removes a curve from the given plot by the specified name.

        Args:
            plot (pyqtgraph.PlotItem): The plot from which to remove the curve.
            name (str): The name of the curve to remove.
        """
        # if checkbox.isChecked():
        for item in plot.items:
            if isinstance(item, pg.PlotDataItem) and getattr(item, "opts", {}).get("name") == name:
                plot.removeItem(item)
                return

        # else:
        #     return

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
        angles = BasicPlot.golden_ratio(len(cmap_colors))
        color_selection = np.round(np.interp(angles, (-np.pi, np.pi), (0, len(cmap_colors))))
        colors = [
            mkColor(tuple((cmap_colors[int(ii)] * 255).astype(int))) for ii in color_selection[:num]
        ]
        return colors

    def on_projection(self):
        while True:
            if self._current_proj is None:
                time.sleep(0.1)
                continue
            endpoint = f"px_stream/projection_{self._current_proj}/data"
            msgs = client.producer.lrange(topic=endpoint, start=-1, end=-1)
            data = [BECMessage.DeviceMessage.loads(msg) for msg in msgs]
            if not data:
                continue
            with np.errstate(divide="ignore", invalid="ignore"):
                self.plotter_data_y = [
                    np.sum(
                        np.sum(data[-1].content["signals"]["data"] * self._current_norm, axis=1)
                        / np.sum(self._current_norm, axis=0),
                        axis=0,
                    ).squeeze()
                ]

            self.update_signal.emit()

    @pyqtSlot(dict, dict)
    def on_dap_update(self, data: dict, metadata: dict):
        self.img.setImage(data["z"].T)
        # time.sleep(0,1)

    @pyqtSlot(dict)
    def new_proj(self, data):
        proj_nr = data["proj_nr"]
        endpoint = f"px_stream/projection_{proj_nr}/metadata"
        msg_raw = client.producer.get(topic=endpoint)
        msg = BECMessage.DeviceMessage.loads(msg_raw)
        self._current_q = msg.content["signals"]["q"]
        self._current_norm = msg.content["signals"]["norm_sum"]
        self._current_metadata = msg.content["signals"]["metadata"]

        self.plotter_data_x = [self._current_q]
        self._current_proj = proj_nr


if __name__ == "__main__":
    import argparse

    from bec_widgets import ctrl_c
    from bec_widgets.bec_dispatcher import bec_dispatcher

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--signals",
        help="specify recorded signals",
        nargs="+",
        default=["gauss_bpm"],
    )
    # default = ["gauss_bpm", "bpm4i", "bpm5i", "bpm6i", "xert"],
    value = parser.parse_args()
    print(f"Plotting signals for: {', '.join(value.signals)}")
    client = bec_dispatcher.client
    # client.start()
    app = QtWidgets.QApplication([])
    ctrl_c.setup(app)
    plot = BasicPlot(y_value_list=value.signals)
    # bec_dispatcher.connect(plot)
    bec_dispatcher.connect_proj_id(plot.new_proj)
    bec_dispatcher.connect_dap_slot(plot.on_dap_update, "px_dap_worker")
    plot.show()
    # client.callbacks.register("scan_segment", plot, sync=False)
    app.exec_()
