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
#   - YAML config -> plot settings
#   - YAML config -> xy pairs -> multiple subsignals for different devices
#   - Internal logic -> if user specify


class PlotApp(QWidget):
    """
    Main class for PlotApp, designed to plot multiple signals in a grid layout.

    Attributes:
        update_signal (pyqtSignal): Signal to trigger plot updates.
        xy_pairs (list of tuples): List of tuples containing x-y pairs for each plot.
                                    Each tuple has the x-value as its first element and
                                    a list of y-values as its second element.

    Args:
        xy_pairs (list of lists): List of x-y pairs specifying the signals to plot.
                                   Each tuple consists of an x-value string and a list
                                   of y-value strings.
                                   Example: [["x1", ["y1", "y2"]], ["x2", ["y3"]]]
        parent (QWidget, optional): Parent widget.
    """

    update_signal = pyqtSignal()
    update_dap_signal = pyqtSignal()

    def __init__(self, plot_settings: dict, xy_pairs: list, plot_data: dict, parent=None):
        super(PlotApp, self).__init__(parent)

        # YAML config
        self.plot_settings = plot_settings
        self.xy_pairs = xy_pairs
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
        self.grid_coordinates = []  # List to keep track of grid positions for each plot

        num_plots = len(self.xy_pairs)
        num_rows = num_plots // num_columns  # Calculate the number of full rows
        last_row_cols = num_plots % num_columns  # Number of plots in the last row
        remaining_space = num_columns - last_row_cols  # Remaining space in the last row

        for i, (x, ys) in enumerate(self.xy_pairs):
            row, col = i // num_columns, i % num_columns  # Calculate grid position

            colspan = 1  # Default colspan

            # Check if we are in the last row and there's remaining space
            if row == num_rows and remaining_space > 0:
                if last_row_cols == 1:
                    colspan = num_columns  # Stretch across all columns
                else:
                    colspan = remaining_space // last_row_cols + 1  # Proportional stretch
                    remaining_space -= colspan - 1  # Update remaining space
                    last_row_cols -= 1  # Update remaining plots

            plot = self.glw.addPlot(
                row=row, col=col, colspan=colspan, title=list(self.plot_data[i].keys())[0]
            )
            plot.setLabel("bottom", x)
            plot.setLabel("left", ", ".join(ys))
            plot.addLegend()
            self.plots[(x, tuple(ys))] = plot
            self.grid_coordinates.append((row, col))

        self.init_curves()

    def init_curves(self) -> None:
        """
        Initialize curve data and properties, and update table row labels.

        This method initializes a nested dictionary `self.curves_data` to store
        the curve objects for each x and y signal pair. It also updates the row labels
        in `self.tableWidget_crosshair` to include the grid position for each y-value.
        """
        self.curves_data = {}  # Nested dictionary to hold curves

        row_labels = []  # List to keep track of row labels for the table

        for idx, ((x, ys), plot) in enumerate(self.plots.items()):
            plot.clear()
            self.curves_data[(x, tuple(ys))] = []
            colors_ys = Colors.golden_angle_color(colormap="plasma", num=len(ys))

            row, col = self.grid_coordinates[idx]  # Retrieve the grid position for this plot

            for i, (signal, color) in enumerate(zip(ys, colors_ys)):
                pen_curve = mkPen(color=color, width=2, style=QtCore.Qt.DashLine)
                brush_curve = mkBrush(color=color)
                curve_data = pg.PlotDataItem(
                    symbolSize=5,
                    symbolBrush=brush_curve,
                    pen=pen_curve,
                    skipFiniteCheck=True,
                    name=f"{signal}",
                )
                self.curves_data[(x, tuple(ys))].append(curve_data)
                plot.addItem(curve_data)
                row_labels.append(f"{signal} - [{row},{col}]")  # Add row label with grid position

        self.tableWidget_crosshair.setRowCount(len(row_labels))
        self.tableWidget_crosshair.setVerticalHeaderLabels(row_labels)
        self.hook_crosshair()

    def hook_crosshair(self):
        """Attach crosshairs to each plot and connect them to the update_table method."""
        self.crosshairs = {}  # Store crosshairs for each plot
        for (x, ys), plot in self.plots.items():
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
            self.crosshairs[(x, tuple(ys))] = crosshair

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
        plot_key = [key for key, value in self.plots.items() if value == plot][0]
        _, ys = plot_key  # Extract the y-values for the current plot

        # Find the starting row for the ys of the current plot
        starting_row = 0
        for _, other_ys in self.xy_pairs:
            if other_ys == list(ys):
                break
            starting_row += len(other_ys)

        # Update the table rows corresponding to the ys of the current plot
        for i, y in enumerate(y_values):
            row = starting_row + i
            table_widget.setItem(row, column, QTableWidgetItem(f"({x}, {y})"))
            table_widget.resizeColumnsToContents()

    def update_plot(self) -> None:
        """Update the plot data based on the stored data dictionary."""
        for (x, ys), curves in self.curves_data.items():
            data_x = self.data.get((x, tuple(ys)), {}).get("x", [])
            for i, curve in enumerate(curves):
                data_y = self.data.get((x, tuple(ys)), {}).get(ys[i], [])
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
            self.data = {}  # Wipe the data for a new scan
            self.init_curves()  # Re-initialize the curves

        for x, ys in self.xy_pairs:
            data_x = msg["data"].get(x, {}).get(x, {}).get("value", None)
            if data_x is not None:
                self.data.setdefault((x, tuple(ys)), {}).setdefault("x", []).append(data_x)

            for y in ys:
                data_y = msg["data"].get(y, {}).get(y, {}).get("value", None)
                if data_y is not None:
                    self.data.setdefault((x, tuple(ys)), {}).setdefault(y, []).append(data_y)

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
            xy_pairs = config.get("xy_pairs", [])
            plot_data = config.get("plot_data", {})
    except FileNotFoundError:
        print(f"The file {args.config} was not found.")
        exit(1)
    except Exception as e:
        print(f"An error occurred while loading the config file: {e}")
        exit(1)

        # TODO PUT RAISE ERROR HERE to check for xy_pairs

    # BECclient global variables
    client = bec_dispatcher.client
    client.start()

    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    app = QApplication([])
    plotApp = PlotApp(xy_pairs=xy_pairs, plot_settings=plot_settings, plot_data=plot_data)

    # Connecting signals from bec_dispatcher
    bec_dispatcher.connect_slot(plotApp.on_scan_segment, MessageEndpoints.scan_segment())
    ctrl_c.setup(app)

    window = plotApp
    window.show()
    app.exec_()
