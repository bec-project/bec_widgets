import pyqtgraph as pg
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication
from pyqtgraph import mkPen, mkBrush

from bec_widgets.qt_utils import Crosshair, Colors

config_simple = {
    "plot_settings": {
        "background_color": "white",
        "num_columns": 1,
        "colormap": "plasma",
        "scan_types": False,
    },
    "plot_data": {
        "plot_name": "BPM4i plots vs samx",
        "x": {
            "label": "Motor Y",
            "signals": [{"name": "samx"}],  # Entry is missing
        },
        "y": {
            "label": "bpm4i",
            "signals": [{"name": "bpm4i"}],  # Entry is missing
        },
    },
}


class BECDeviceMonitor(pg.GraphicsLayoutWidget):
    update_signal = pyqtSignal()

    def __init__(self, config: dict = config_simple, parent=None):  # , client=None, parent=None):
        super(BECDeviceMonitor, self).__init__(parent=None)

        # Client and device manager from BEC
        # self.client = bec_dispatcher.client if client is None else client
        # self.dev = self.client.device_manager.devices

        # Current configuration
        self.config = config

        # Displayed Data
        self.data = {}

        self.crosshairs = None
        self.plots = None
        self.curves_data = None
        self.grid_coordinates = None
        self.scanID = None

        # Connect the update signal to the update plot method #TODO enable when update is fixed
        # self.proxy_update_plot = pg.SignalProxy(
        #     self.update_signal, rateLimit=25, slot=self.update_plot
        # )

        # Init UI
        self._init_config()
        self._init_plot()
        # self._init_curves()

    def _init_config(self):
        # Separate configs
        self.plot_settings = self.config.get("plot_settings", {})
        self.plot_data_config = self.config.get("plot_data", {})

    def _init_plot(self):
        self.clear()
        self.plots = {}
        # self.grid_coordinates = {}  # TODO will be extended in the next version

        plot_config = self.plot_data_config

        # TODO here will go for cycle for multiple plots

        # Plot Settings
        plot_name = plot_config.get("plot_name", "")
        x_label = plot_config["x"].get("label", "")
        y_label = plot_config["y"].get("label", "")

        plot = self.addPlot(title=plot_name)
        plot.setLabel("bottom", x_label)
        plot.setLabel("left", y_label)
        # Adding some data to plot for testing
        plot.plot([1, 2, 3, 4, 5], [5, 4, 3, 2, 1])

        self.plots[plot_name] = plot

    # def _init_curves(self):
    #     self.curves_data = {}
    #     row_labels = []
    #
    #     plot_config = self.plot_data_config  # TODO will be change to loop as in extreme.py
    #
    #     plot_name = self.plot_data_config.get("plot_name", "")
    #     plot = self.plots[plot_name]
    #     plot.clear()
    #
    #     y_config = plot_config["y"]["signals"]
    #     colors_ys = Colors.golden_angle_color(
    #         colormap=self.plot_settings["colormap"], num=len(y_config)
    #     )
    #
    #     curve_list = []
    #     for i, (y_config, color) in enumerate(zip(y_config, colors_ys)):
    #         # print(y_config)
    #         y_name = y_config["name"]
    #         y_entries = y_config.get("entry", [y_name])
    #
    #         if not isinstance(y_entries, list):
    #             y_entries = [y_entries]
    #
    #         for y_entry in y_entries:
    #             user_color = self.user_colors.get((plot_name, y_name, y_entry), None)
    #             color_to_use = user_color if user_color else color
    #
    #             pen_curve = mkPen(color=color_to_use, width=2, style=QtCore.Qt.DashLine)
    #             brush_curve = mkBrush(color=color_to_use)
    #
    #             curve_data = pg.PlotDataItem(
    #                 symbolSize=5,
    #                 symbolBrush=brush_curve,
    #                 pen=pen_curve,
    #                 skipFiniteCheck=True,
    #                 name=f"{y_name} ({y_entry})",
    #             )
    #
    #         curve_list.append((y_name, y_entry, curve_data))
    #         plot.addItem(curve_data)
    #         row_labels.append(f"{y_name} ({y_entry}) - {plot_name}")
    #
    #     self.curves_data[plot_name] = curve_list

    def update_plot(self):
        ...


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    monitor = BECDeviceMonitor()
    monitor.show()
    sys.exit(app.exec_())
