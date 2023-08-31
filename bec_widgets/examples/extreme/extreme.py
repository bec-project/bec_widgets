import os

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QWidget, QTableWidgetItem, QTableWidget
from pyqtgraph import mkBrush, mkColor, mkPen
from pyqtgraph.Qt import QtCore, uic

from bec_lib.core import MessageEndpoints
from bec_widgets.qt_utils import Crosshair, Colors


# TODO implement:
#   - implement scanID database for visualizing previous scans
#   - change how dap is handled in bec_dispatcher to handle more workers


class PlotApp(QWidget):
    """
    Main class for PlotApp, designed to plot multiple signals in a grid layout
    based on a flexible YAML configuration.

    Attributes:
        update_signal (pyqtSignal): Signal to trigger plot updates.
        plot_data (list of dict): List of dictionaries containing plot configurations.
                                  Each dictionary specifies x and y signals, including their
                                  name and entry, for a particular plot.

    Args:
        plot_settings (dict): Dictionary containing global plot settings such as background color.
        plot_data (list of dict): List of dictionaries specifying the signals to plot.
                                  Each dictionary should contain:
                                  - 'x': Dictionary specifying the x-axis settings including
                                        a 'signals' list with 'name' and 'entry' fields.
                                        If there are multiple entries for one device name, they can be passed as a list.
                                  - 'y': Similar to 'x', but for the y-axis.
                                  Example:
                                  [
                                      {
                                          'plot_name': 'Plot 1',
                                          'x': {'label': 'X Label', 'signals': [{'name': 'x1', 'entry': 'x1_entry'}]},
                                          'y': {'label': 'Y Label', 'signals': [{'name': 'y1', 'entry': 'y1_entry'}]}
                                      },
                                      ...
                                  ]
        parent (QWidget, optional): Parent widget.
    """

    update_signal = pyqtSignal()
    update_dap_signal = pyqtSignal()

    def __init__(self, plot_settings: dict, plot_data: list, parent=None):
        super(PlotApp, self).__init__(parent)

        # YAML config
        self.plot_settings = plot_settings
        self.plot_data = plot_data

        # Setting global plot settings
        self.init_plot_background(self.plot_settings["background_color"])

        # Loading UI
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "extreme.ui"), self)

        # Nested dictionary to hold x and y data for multiple plots
        self.data = {}

        self.crosshairs = None
        self.plots = None
        self.curves_data = None
        self.grid_coordinates = None
        self.scanID = None

        # Initialize the UI
        self.init_ui(self.plot_settings["num_columns"])
        self.spinBox_N_columns.setValue(self.plot_settings["num_columns"])
        self.splitter.setSizes([400, 100])

        # Connect the update signal to the update plot method
        self.proxy_update_plot = pg.SignalProxy(
            self.update_signal, rateLimit=25, slot=self.update_plot
        )

        # Change layout of plots when the number of columns is changed in GUI
        self.spinBox_N_columns.valueChanged.connect(lambda x: self.init_ui(x))

    def init_plot_background(self, background_color: str) -> None:
        """
        Initialize plot settings based on the background color.

        Args:
            background_color (str): The background color ('white' or 'black').

        This method sets the background and foreground colors for pyqtgraph.
        If the background is dark ('black'), the foreground will be set to 'white',
        and vice versa.
        """
        if background_color.lower() == "black":
            pg.setConfigOption("background", "k")
            pg.setConfigOption("foreground", "w")
        elif background_color.lower() == "white":
            pg.setConfigOption("background", "w")
            pg.setConfigOption("foreground", "k")
        else:
            print(f"Warning: Unknown background color {background_color}. Using default settings.")

    def init_ui(self, num_columns: int = 3) -> None:
        """
        Initialize the UI components, create plots and store their grid positions.

        Args:
            num_columns (int): Number of columns to wrap the layout.

        This method initializes a dictionary `self.plots` to store the plot objects
        along with their corresponding x and y signal names. It dynamically arranges
        the plots in a grid layout based on the given number of columns and dynamically
        stretches the last plots to fit the remaining space.
        """
        self.glw.clear()
        self.plots = {}
        self.grid_coordinates = []

        num_plots = len(self.plot_data)
        num_rows = num_plots // num_columns
        last_row_cols = num_plots % num_columns
        remaining_space = num_columns - last_row_cols

        for i, plot_config in enumerate(self.plot_data):
            row, col = i // num_columns, i % num_columns
            colspan = 1

            if row == num_rows and remaining_space > 0:
                if last_row_cols == 1:
                    colspan = num_columns
                else:
                    colspan = remaining_space // last_row_cols + 1
                    remaining_space -= colspan - 1
                    last_row_cols -= 1

            plot_name = plot_config.get("plot_name", "")
            x_label = plot_config["x"].get("label", "")
            y_label = plot_config["y"].get("label", "")

            plot = self.glw.addPlot(row=row, col=col, colspan=colspan, title=plot_name)
            plot.setLabel("bottom", x_label)
            plot.setLabel("left", y_label)
            plot.addLegend()

            self.plots[plot_name] = plot
            self.grid_coordinates.append((row, col))

        self.init_curves()

    def init_curves(self) -> None:
        """
        Initialize curve data and properties, and update table row labels.

        This method initializes a nested dictionary `self.curves_data` to store
        the curve objects for each x and y signal pair. It also updates the row labels
        in `self.tableWidget_crosshair` to include the grid position for each y-value.
        """
        self.curves_data = {}
        row_labels = []

        for idx, plot_config in enumerate(self.plot_data):
            plot_name = plot_config.get("plot_name", "")
            plot = self.plots[plot_name]
            plot.clear()

            y_configs = plot_config["y"]["signals"]
            colors_ys = Colors.golden_angle_color(
                colormap=self.plot_settings["colormap"], num=len(y_configs)
            )

            curve_list = []
            for i, (y_config, color) in enumerate(zip(y_configs, colors_ys)):
                y_name = y_config["name"]
                y_entries = y_config.get("entry", [y_name])

                if not isinstance(y_entries, list):
                    y_entries = [y_entries]

                for y_entry in y_entries:
                    pen_curve = mkPen(color=color, width=2, style=QtCore.Qt.DashLine)
                    brush_curve = mkBrush(color=color)

                    curve_data = pg.PlotDataItem(
                        symbolSize=5,
                        symbolBrush=brush_curve,
                        pen=pen_curve,
                        skipFiniteCheck=True,
                        name=f"{y_name} ({y_entry})",
                    )

                    curve_list.append((y_name, y_entry, curve_data))
                    plot.addItem(curve_data)
                    row_labels.append(f"{y_name} ({y_entry}) - {plot_name}")

            self.curves_data[plot_name] = curve_list

        self.tableWidget_crosshair.setRowCount(len(row_labels))
        self.tableWidget_crosshair.setVerticalHeaderLabels(row_labels)
        self.hook_crosshair()

    def hook_crosshair(self):
        """Attach crosshairs to each plot and connect them to the update_table method."""
        self.crosshairs = {}
        for plot_name, plot in self.plots.items():
            crosshair = Crosshair(plot, precision=3)
            crosshair.coordinatesChanged1D.connect(
                lambda x, y, plot=plot: self.update_table(
                    self.tableWidget_crosshair, x, y, column=0, plot=plot
                )
            )
            crosshair.coordinatesClicked1D.connect(
                lambda x, y, plot=plot: self.update_table(
                    self.tableWidget_crosshair, x, y, column=1, plot=plot
                )
            )
            self.crosshairs[plot_name] = crosshair

    def update_table(
        self, table_widget: QTableWidget, x: float, y_values: list, column: int, plot: pg.PlotItem
    ) -> None:
        """
        Update the table with coordinates based on cursor movements and clicks.

        Args:
            table_widget (QTableWidget): The table to be updated.
            x (float): The x-coordinate from the plot.
            y_values (list): The y-coordinates from the plot.
            column (int): The column in the table to be updated.
            plot (PlotItem): The plot from which the coordinates are taken.

        This method calculates the correct row in the table for each y-value
        and updates the cell at (row, column) with the new x and y coordinates.
        """
        plot_name = [name for name, value in self.plots.items() if value == plot][0]

        starting_row = 0
        for plot_config in self.plot_data:
            if plot_config.get("plot_name", "") == plot_name:
                break
            for y_config in plot_config.get("y", {}).get("signals", []):
                y_entries = y_config.get("entry", [y_config.get("name", "")])
                if not isinstance(y_entries, list):
                    y_entries = [y_entries]
                starting_row += len(y_entries)

        for i, y in enumerate(y_values):
            row = starting_row + i
            table_widget.setItem(row, column, QTableWidgetItem(f"({x}, {y})"))
            table_widget.resizeColumnsToContents()

    def update_plot(self) -> None:
        """Update the plot data based on the stored data dictionary."""
        for plot_name, curve_list in self.curves_data.items():
            for y_name, y_entry, curve in curve_list:
                x_config = next(
                    (pc["x"] for pc in self.plot_data if pc.get("plot_name") == plot_name), {}
                )
                x_signal_config = x_config["signals"][0]
                x_name = x_signal_config.get("name", "")
                x_entry = x_signal_config.get("entry", x_name)

                key = (x_name, x_entry, y_name, y_entry)
                data_x = self.data.get(key, {}).get("x", [])
                data_y = self.data.get(key, {}).get("y", [])

                curve.setData(data_x, data_y)

    @pyqtSlot(dict, dict)
    def on_scan_segment(self, msg, metadata) -> None:
        """
        Handle new scan segments and saves data to a dictionary.

        Args:
            msg (dict): Message received with scan data.
            metadata (dict): Metadata of the scan.
        """
        current_scanID = msg.get("scanID", None)
        if current_scanID is None:
            return

        if current_scanID != self.scanID:
            self.scanID = current_scanID
            self.data = {}
            self.init_curves()

        for plot_config in self.plot_data:
            x_config = plot_config["x"]
            x_signal_config = x_config["signals"][0]
            x_name = x_signal_config.get("name", "")
            x_entry_list = x_signal_config.get("entry", [])

            if not x_entry_list:
                x_entry_list = dev[x_name]._hints if hasattr(dev[x_name], "_hints") else [x_name]

            if not isinstance(x_entry_list, list):
                x_entry_list = [x_entry_list]

            y_configs = plot_config["y"]["signals"]

            for x_entry in x_entry_list:
                for y_config in y_configs:
                    y_name = y_config.get("name", "")
                    y_entry_list = y_config.get("entry", [])

                    if not y_entry_list:
                        y_entry_list = (
                            dev[y_name]._hints if hasattr(dev[y_name], "_hints") else [y_name]
                        )

                    if not isinstance(y_entry_list, list):
                        y_entry_list = [y_entry_list]

                    for y_entry in y_entry_list:
                        key = (x_name, x_entry, y_name, y_entry)

                        data_x = msg["data"].get(x_name, {}).get(x_entry, {}).get("value", None)
                        data_y = msg["data"].get(y_name, {}).get(y_entry, {}).get("value", None)

                        if data_x is not None:
                            self.data.setdefault(key, {}).setdefault("x", []).append(data_x)

                        if data_y is not None:
                            self.data.setdefault(key, {}).setdefault("y", []).append(data_y)

        self.update_signal.emit()


if __name__ == "__main__":
    import yaml
    import argparse

    from bec_widgets import ctrl_c
    from bec_widgets.bec_dispatcher import bec_dispatcher

    parser = argparse.ArgumentParser(description="Plotting App")
    parser.add_argument(
        "--config", "-c", help="Path to the .yaml configuration file", default="config.yaml"
    )
    args = parser.parse_args()

    try:
        with open(args.config, "r") as file:
            config = yaml.safe_load(file)

            plot_settings = config.get("plot_settings", {})
            plot_data = config.get("plot_data", {})
    except FileNotFoundError:
        print(f"The file {args.config} was not found.")
        exit(1)
    except Exception as e:
        print(f"An error occurred while loading the config file: {e}")
        exit(1)

    # BECclient global variables
    client = bec_dispatcher.client
    client.start()

    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    app = QApplication([])
    plotApp = PlotApp(plot_settings=plot_settings, plot_data=plot_data)

    # Connecting signals from bec_dispatcher
    bec_dispatcher.connect_slot(plotApp.on_scan_segment, MessageEndpoints.scan_segment())
    ctrl_c.setup(app)

    window = plotApp
    window.show()
    app.exec_()
