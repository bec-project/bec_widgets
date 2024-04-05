# pylint: disable = no-name-in-module,missing-module-docstring
import time
from collections import defaultdict

import numpy as np
import pyqtgraph as pg
from bec_lib import MessageEndpoints
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from bec_widgets.utils import yaml_dialog
from bec_widgets.utils.bec_dispatcher import BECDispatcher

CONFIG_DEFAULT = {
    "plot_settings": {"colormap": "CET-L4", "num_columns": 1},
    "waveform2D": [
        {
            "plot_name": "Waveform 2D Scatter (1)",
            "x_label": "Sam X",
            "y_label": "Sam Y",
            "signals": {
                "x": [{"name": "samx", "entry": "samx"}],
                "y": [{"name": "samy", "entry": "samy"}],
                "z": [{"name": "bpm4i", "entry": "bpm4i"}],
            },
        },
        {
            "plot_name": "Waveform 2D Scatter (2)",
            "x_label": "Sam Y",
            "y_label": "Sam X",
            "signals": {
                "x": [{"name": "samy", "entry": "samy"}],
                "y": [{"name": "samx", "entry": "samx"}],
                "z": [{"name": "gauss_bpm", "entry": "gauss_bpm"}],
            },
        },
    ],
}


class BECMonitor2DScatter(QWidget):
    update_signal = pyqtSignal()

    def __init__(
        self,
        parent=None,
        client=None,
        config: dict = None,
        enable_crosshair: bool = True,
        gui_id=None,
        skip_validation: bool = True,
        toolbar_enabled=True,
    ):
        super().__init__(parent=parent)

        # Client and device manager from BEC
        self.plot_data = None
        bec_dispatcher = BECDispatcher()
        self.client = bec_dispatcher.client if client is None else client
        self.dev = self.client.device_manager.devices
        self.queue = self.client.queue

        self.validator = None  # TODO implement validator when ready
        self.gui_id = gui_id

        if self.gui_id is None:
            self.gui_id = self.__class__.__name__ + str(time.time())

        # Connect dispatcher slots #TODO connect endpoints related to CLI
        bec_dispatcher.connect_slot(self.on_scan_segment, MessageEndpoints.scan_segment())

        # Config related variables
        self.plot_data = None
        self.plot_settings = None
        self.num_columns = None
        self.database = {}
        self.plots = {}
        self.grid_coordinates = []

        self.curves_data = {}
        # Current configuration
        self.config = config
        self.skip_validation = skip_validation

        # Enable crosshair
        self.enable_crosshair = enable_crosshair

        # Displayed Data
        self.database = {}

        self.crosshairs = None
        self.plots = None
        self.curves_data = None
        self.grid_coordinates = None
        self.scan_id = None

        # Connect the update signal to the update plot method
        self.proxy_update_plot = pg.SignalProxy(
            self.update_signal, rateLimit=10, slot=self.update_plot
        )

        # Init UI
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)
        if toolbar_enabled:  # TODO implement toolbar when ready
            self._init_toolbar()

        self.glw = pg.GraphicsLayoutWidget()
        self.layout.addWidget(self.glw)

        if self.config is None:
            print("No initial config found for BECDeviceMonitor")
        else:
            self.on_config_update(self.config)

    def _init_toolbar(self):
        """Initialize the toolbar."""
        # TODO implement toolbar when ready
        # from bec_widgets.widgets import ModularToolBar
        #
        # # Create and configure the toolbar
        # self.toolbar = ModularToolBar(self)
        #
        # # Add the toolbar to the layout
        # self.layout.addWidget(self.toolbar)

    def _init_config(self):
        """Initialize the configuration."""
        # Global widget settings
        self._get_global_settings()

        # Plot data
        self.plot_data = self.config.get("waveform2D", [])

        # Initiate database
        self.database = self._init_database()

        # Initialize the plot UI
        self._init_ui()

    def _get_global_settings(self):
        """Get the global widget settings."""

        self.plot_settings = self.config.get("plot_settings", {})

        self.num_columns = self.plot_settings.get("num_columns", 1)
        self.colormap = self.plot_settings.get("colormap", "viridis")

    def _init_database(self) -> dict:
        """
        Initialize the database to store the data for each plot.
        Returns:
            dict: The database.
        """

        database = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        return database

    def _init_ui(self, num_columns: int = 3) -> None:
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
        self.imageItems = {}
        self.grid_coordinates = []
        self.scatterPlots = {}
        self.colorBars = {}

        num_plots = len(self.plot_data)
        # Check if num_columns exceeds the number of plots
        if num_columns >= num_plots:
            num_columns = num_plots
            self.plot_settings["num_columns"] = num_columns  # Update the settings
            print(
                "Warning: num_columns in the YAML file was greater than the number of plots."
                f" Resetting num_columns to number of plots:{num_columns}."
            )
        else:
            self.plot_settings["num_columns"] = num_columns  # Update the settings

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

            x_label = plot_config.get("x_label", "")
            y_label = plot_config.get("y_label", "")

            plot = self.glw.addPlot(row=row, col=col, colspan=colspan, title=plot_name)
            plot.setLabel("bottom", x_label)
            plot.setLabel("left", y_label)
            plot.addLegend()

            self.plots[plot_name] = plot

            self.grid_coordinates.append((row, col))

        self._init_curves()

    def _init_curves(self):
        """Init scatter plot pg containers"""
        self.scatterPlots = {}
        for i, plot_config in enumerate(self.plot_data):
            plot_name = plot_config.get("plot_name", "")
            plot = self.plots[plot_name]
            plot.clear()

            # Create ScatterPlotItem for each plot
            scatterPlot = pg.ScatterPlotItem(size=10)
            plot.addItem(scatterPlot)
            self.scatterPlots[plot_name] = scatterPlot

    @pyqtSlot(dict)
    def on_config_update(self, config: dict):
        """
        Validate and update the configuration settings.
        Args:
            config(dict): Configuration settings
        """
        # TODO implement BEC CLI commands similar to BECPlotter
        # convert config from BEC CLI to correct formatting
        config_tag = config.get("config", None)
        if config_tag is not None:
            config = config["config"]

        if self.skip_validation is True:
            self.config = config
            self._init_config()

        else:  # TODO implement validator
            print("Do validation")

    def flush(self):
        """Reset current plot"""

        self.database = self._init_database()
        self._init_curves()

    @pyqtSlot(dict, dict)
    def on_scan_segment(self, msg, metadata):
        """
        Handle new scan segments and saves data to a dictionary. Linked through bec_dispatcher.

        Args:
            msg (dict): Message received with scan data.
            metadata (dict): Metadata of the scan.
        """

        # TODO check if this is correct
        current_scan_id = msg.get("scan_id", None)
        if current_scan_id is None:
            return

        if current_scan_id != self.scan_id:
            self.scan_id = current_scan_id
            self.scan_data = self.queue.scan_storage.find_scan_by_ID(self.scan_id)
            if not self.scan_data:
                print(f"No data found for scan_id: {self.scan_id}")  # TODO better error
                return
            self.flush()

        # Update the database with new data
        self.update_database_with_scan_data(msg)

        # Emit signal to update plot #TODO could be moved to update_database_with_scan_data just for coresponding plot name
        self.update_signal.emit()

    def update_database_with_scan_data(self, msg):
        """
        Update the database with data from the new scan segment.

        Args:
            msg (dict): Message containing the new scan data.
        """
        data = msg.get("data", {})
        for plot_config in self.plot_data:  # Iterate over the list
            plot_name = plot_config["plot_name"]
            x_signal = plot_config["signals"]["x"][0]["name"]
            y_signal = plot_config["signals"]["y"][0]["name"]
            z_signal = plot_config["signals"]["z"][0]["name"]

            if x_signal in data and y_signal in data and z_signal in data:
                x_value = data[x_signal][x_signal]["value"]
                y_value = data[y_signal][y_signal]["value"]
                z_value = data[z_signal][z_signal]["value"]

                # Update database for the corresponding plot
                self.database[plot_name]["x"][x_signal].append(x_value)
                self.database[plot_name]["y"][y_signal].append(y_value)
                self.database[plot_name]["z"][z_signal].append(z_value)

    def update_plot(self):
        """
        Update the plots with the latest data from the database.
        """
        for plot_name, scatterPlot in self.scatterPlots.items():
            x_data = self.database[plot_name]["x"]
            y_data = self.database[plot_name]["y"]
            z_data = self.database[plot_name]["z"]

            if x_data and y_data and z_data:
                # Extract values for each axis
                x_values = next(iter(x_data.values()), [])
                y_values = next(iter(y_data.values()), [])
                z_values = next(iter(z_data.values()), [])

                # Check if the data lists are not empty
                if x_values and y_values and z_values:
                    # Normalize z_values for color mapping
                    z_min, z_max = np.min(z_values), np.max(z_values)
                    if z_max != z_min:  # Ensure that there is a range in the z values
                        z_values_norm = (z_values - z_min) / (z_max - z_min)
                        colormap = pg.colormap.get(
                            self.colormap
                        )  # using colormap from global settings
                        colors = [colormap.map(z) for z in z_values_norm]

                        # Update scatter plot data with colors
                        scatterPlot.setData(x=x_values, y=y_values, brush=colors)
                    else:
                        # Handle case where all z values are the same (e.g., avoid division by zero)
                        scatterPlot.setData(x=x_values, y=y_values)  # Default brush can be used


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--config_file", help="Path to the config file.")
    parser.add_argument("--config", help="Path to the config file.")
    parser.add_argument("--id", help="GUI ID.")
    args = parser.parse_args()

    if args.config is not None:
        # Load config from file
        config = json.loads(args.config)
    elif args.config_file is not None:
        # Load config from file
        config = yaml_dialog.load_yaml(args.config_file)
    else:
        config = CONFIG_DEFAULT

    client = BECDispatcher().client
    client.start()
    app = QApplication(sys.argv)
    monitor = BECMonitor2DScatter(config=config, gui_id=args.id, skip_validation=True)
    monitor.show()
    sys.exit(app.exec())
