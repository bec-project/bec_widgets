import os

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QWidget, QTableWidgetItem, QTableWidget
from pyqtgraph import mkBrush, mkColor, mkPen
from pyqtgraph.Qt import QtCore, uic

from bec_lib.core import MessageEndpoints
from bec_widgets.qt_utils import Crosshair


# TODO implement:
#   - implement scanID database for visualizing previous scans
#   - change how dap is handled in bec_dispatcher to handle more workers


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

    def __init__(self, xy_pairs, parent=None):
        super(PlotApp, self).__init__(parent)
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "extreme.ui"), self)

        # xy pairs for setting number of windows
        self.xy_pairs = xy_pairs

        # Nested dictionary to hold x and y data for multiple plots
        self.data = {}

        self.crosshairs = None
        self.plots = None
        self.curves_data = None
        self.grid_coordinates = None
        self.scanID = None

        # Initialize the UI
        self.init_ui(self.spinBox_N_columns.value())
        self.splitter.setSizes([400, 100])

        # Connect the update signal to the update plot method
        self.proxy_update_plot = pg.SignalProxy(
            self.update_signal, rateLimit=25, slot=self.update_plot
        )
        self.spinBox_N_columns.valueChanged.connect(lambda x: self.init_ui(x))

    def init_ui(self, num_columns=3) -> None:
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

            plot = self.glw.addPlot(row=row, col=col, colspan=colspan)
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
            colors_ys = PlotApp.golden_angle_color(colormap="CET-R2", num=len(ys))

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

    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)

    xy_pairs = config["xy_pairs"]

    # BECclient global variables
    client = bec_dispatcher.client
    client.start()

    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    app = QApplication([])
    plotApp = PlotApp(xy_pairs=xy_pairs)

    # Connecting signals from bec_dispatcher
    bec_dispatcher.connect_slot(plotApp.on_scan_segment, MessageEndpoints.scan_segment())
    ctrl_c.setup(app)

    window = plotApp
    window.show()
    app.exec_()
