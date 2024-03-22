# pylint: disable = no-name-in-module,missing-module-docstring
import time

import pyqtgraph as pg
from bec_lib import MessageEndpoints
from pydantic import ValidationError
from pyqtgraph import mkBrush, mkPen
from qtpy import QtCore
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtWidgets import QApplication, QMessageBox

from bec_widgets.utils import Colors, Crosshair, yaml_dialog
from bec_widgets.utils.bec_dispatcher import BECDispatcher
from bec_widgets.validation import MonitorConfigValidator

# just for demonstration purposes if script run directly
CONFIG_SCAN_MODE = {
    "plot_settings": {
        "background_color": "white",
        "num_columns": 3,
        "colormap": "plasma",
        "scan_types": True,
    },
    "plot_data": {
        "grid_scan": [
            {
                "plot_name": "Grid plot 1",
                "x_label": "Motor X",
                "y_label": "BPM",
                "sources": [
                    {
                        "type": "scan_segment",
                        "signals": {
                            "x": [{"name": "samx", "entry": "samx"}],
                            "y": [{"name": "bpm4i"}],
                        },
                    }
                ],
            },
            {
                "plot_name": "Grid plot 2",
                "x_label": "Motor X",
                "y_label": "BPM",
                "sources": [
                    {
                        "type": "scan_segment",
                        "signals": {
                            "x": [{"name": "samx", "entry": "samx"}],
                            "y": [{"name": "bpm4i"}],
                        },
                    }
                ],
            },
            {
                "plot_name": "Grid plot 3",
                "x_label": "Motor X",
                "y_label": "BPM",
                "sources": [
                    {
                        "type": "scan_segment",
                        "signals": {"x": [{"name": "samy"}], "y": [{"name": "bpm4i"}]},
                    }
                ],
            },
            {
                "plot_name": "Grid plot 4",
                "x_label": "Motor X",
                "y_label": "BPM",
                "sources": [
                    {
                        "type": "scan_segment",
                        "signals": {
                            "x": [{"name": "samy", "entry": "samy"}],
                            "y": [{"name": "bpm4i"}],
                        },
                    }
                ],
            },
        ],
        "line_scan": [
            {
                "plot_name": "BPM plots vs samx",
                "x_label": "Motor X",
                "y_label": "Gauss",
                "sources": [
                    {
                        "type": "scan_segment",
                        "signals": {
                            "x": [{"name": "samx", "entry": "samx"}],
                            "y": [{"name": "bpm4i"}],
                        },
                    }
                ],
            },
            {
                "plot_name": "Gauss plots vs samx",
                "x_label": "Motor X",
                "y_label": "Gauss",
                "sources": [
                    {
                        "type": "scan_segment",
                        "signals": {
                            "x": [{"name": "samx", "entry": "samx"}],
                            "y": [{"name": "bpm4i"}, {"name": "bpm4i"}],
                        },
                    }
                ],
            },
        ],
    },
}


CONFIG_WRONG = {
    "plot_settings": {
        "background_color": "black",
        "num_columns": 2,
        "colormap": "plasma",
        "scan_types": False,
    },
    "plot_data": [
        {
            "plot_name": "BPM4i plots vs samx",
            "x_label": "Motor Y",
            "y_label": "bpm4i",
            "sources": [
                {
                    "type": "non_existing_source",
                    "signals": {
                        "x": [{"name": "samy"}],
                        "y": [{"name": "bpm4i", "entry": "bpm4i"}],
                    },
                },
                {
                    "type": "history",
                    "scan_id": "<scan_id>",
                    "signals": {
                        "x": [{"name": "samy"}],
                        "y": [{"name": "bpm4i", "entry": "bpm4i"}],
                    },
                },
            ],
        },
        {
            "plot_name": "Gauss plots vs samx",
            "x_label": "Motor X",
            "y_label": "Gauss",
            "sources": [
                {
                    "type": "scan_segment",
                    "signals": {
                        "x": [{"name": "samx", "entry": "non_sense_entry"}],
                        "y": [
                            {"name": "non_existing_name"},
                            {"name": "samy", "entry": "non_existing_entry"},
                        ],
                    },
                }
            ],
        },
        {
            "plot_name": "Gauss plots vs samx",
            "x_label": "Motor X",
            "y_label": "Gauss",
            "sources": [
                {
                    "signals": {
                        "x": [{"name": "samx", "entry": "samx"}],
                        "y": [{"name": "samx"}, {"name": "samy", "entry": "samx"}],
                    }
                }
            ],
        },
    ],
}


CONFIG_SIMPLE = {
    "plot_settings": {
        "background_color": "black",
        "num_columns": 2,
        "colormap": "plasma",
        "scan_types": False,
    },
    "plot_data": [
        {
            "plot_name": "BPM4i plots vs samx",
            "x_label": "Motor X",
            "y_label": "bpm4i",
            "sources": [
                {
                    "type": "scan_segment",
                    "signals": {
                        "x": [{"name": "samx"}],
                        "y": [{"name": "bpm4i", "entry": "bpm4i"}],
                    },
                },
                # {
                #     "type": "history",
                #     "signals": {
                #         "x": [{"name": "samx"}],
                #         "y": [{"name": "bpm4i", "entry": "bpm4i"}],
                #     },
                # },
                # {
                #     "type": "dap",
                #     'worker':'some_worker',
                #     "signals": {
                #         "x": [{"name": "samx"}],
                #         "y": [{"name": "bpm4i", "entry": "bpm4i"}],
                #     },
                # },
            ],
        },
        {
            "plot_name": "Gauss plots vs samx",
            "x_label": "Motor X",
            "y_label": "Gauss",
            "sources": [
                {
                    "type": "scan_segment",
                    "signals": {
                        "x": [{"name": "samx", "entry": "samx"}],
                        "y": [{"name": "bpm4i"}, {"name": "bpm4i"}],
                    },
                }
            ],
        },
    ],
}

CONFIG_REDIS = {
    "plot_settings": {
        "background_color": "white",
        "axis_width": 2,
        "num_columns": 5,
        "colormap": "plasma",
        "scan_types": False,
    },
    "plot_data": [
        {
            "plot_name": "BPM4i plots vs samx",
            "x_label": "Motor Y",
            "y_label": "bpm4i",
            "sources": [
                {
                    "type": "scan_segment",
                    "signals": {"x": [{"name": "samx"}], "y": [{"name": "gauss_bpm"}]},
                },
                {
                    "type": "redis",
                    "endpoint": "public/gui/data/6cd5ea3f-a9a9-4736-b4ed-74ab9edfb996",
                    "update": "append",
                    "signals": {"x": [{"name": "x_default_tag"}], "y": [{"name": "y_default_tag"}]},
                },
            ],
        }
    ],
}


class BECMonitor(pg.GraphicsLayoutWidget):
    update_signal = pyqtSignal()

    def __init__(
        self,
        parent=None,
        client=None,
        config: dict = None,
        enable_crosshair: bool = True,
        gui_id=None,
        skip_validation: bool = False,
    ):
        super().__init__(parent=parent)

        # Client and device manager from BEC
        self.plot_data = None
        bec_dispatcher = BECDispatcher()
        self.client = bec_dispatcher.client if client is None else client
        self.dev = self.client.device_manager.devices
        self.queue = self.client.queue

        self.validator = MonitorConfigValidator(self.dev)
        self.gui_id = gui_id

        if self.gui_id is None:
            self.gui_id = self.__class__.__name__ + str(time.time())

        # Connect slots dispatcher
        bec_dispatcher.connect_slot(self.on_scan_segment, MessageEndpoints.scan_segment())
        bec_dispatcher.connect_slot(self.on_config_update, MessageEndpoints.gui_config(self.gui_id))
        bec_dispatcher.connect_slot(
            self.on_instruction, MessageEndpoints.gui_instructions(self.gui_id)
        )
        bec_dispatcher.connect_slot(self.on_data_from_redis, MessageEndpoints.gui_data(self.gui_id))

        # Current configuration
        self.config = config
        self.skip_validation = skip_validation

        # Enable crosshair
        self.enable_crosshair = enable_crosshair

        # Displayed Data
        self.database = None

        self.crosshairs = None
        self.plots = None
        self.curves_data = None
        self.grid_coordinates = None
        self.scan_id = None

        # TODO make colors accessible to users
        self.user_colors = {}  # key: (plot_name, y_name, y_entry), value: color

        # Connect the update signal to the update plot method
        self.proxy_update_plot = pg.SignalProxy(
            self.update_signal, rateLimit=25, slot=self.update_scan_segment_plot
        )

        # Init UI
        if self.config is None:
            print("No initial config found for BECDeviceMonitor")
        else:
            self.on_config_update(self.config)

    def _init_config(self):
        """
        Initializes or update the configuration settings for the PlotApp.
        """

        # Separate configs
        self.plot_settings = self.config.get("plot_settings", {})
        self.plot_data_config = self.config.get("plot_data", {})
        self.scan_types = self.plot_settings.get("scan_types", False)

        if self.scan_types is False:  # Device tracking mode
            self.plot_data = self.plot_data_config  # TODO logic has to be improved
        else:  # without incoming data setup the first configuration to the first scan type sorted alphabetically by name
            self.plot_data = self.plot_data_config[min(list(self.plot_data_config.keys()))]

        # Initialize the database
        self.database = self._init_database(self.plot_data)

        # Initialize the UI
        self._init_ui(self.plot_settings["num_columns"])

        if self.scan_id is not None:
            self.replot_last_scan()

    def _init_database(self, plot_data_config: dict, source_type_to_init=None) -> dict:
        """
        Initializes or updates the database for the PlotApp.
        Args:
            plot_data_config(dict): Configuration settings for plots.
            source_type_to_init(str, optional): Specific source type to initialize. If None, initialize all.
        Returns:
            dict: Updated or new database dictionary.
        """
        database = {} if source_type_to_init is None else self.database.copy()

        for plot in plot_data_config:
            for source in plot["sources"]:
                source_type = source["type"]
                if source_type_to_init and source_type != source_type_to_init:
                    continue  # Skip if not the specified source type

                if source_type not in database:
                    database[source_type] = {}

                for axis, signals in source["signals"].items():
                    for signal in signals:
                        name = signal["name"]
                        entry = signal.get("entry", name)
                        if name not in database[source_type]:
                            database[source_type][name] = {}
                        if entry not in database[source_type][name]:
                            database[source_type][name][entry] = []

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
        self.clear()
        self.plots = {}
        self.grid_coordinates = []

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

            plot = self.addPlot(row=row, col=col, colspan=colspan, title=plot_name)
            plot.setLabel("bottom", x_label)
            plot.setLabel("left", y_label)
            plot.addLegend()
            self._set_plot_colors(plot, self.plot_settings)

            self.plots[plot_name] = plot
            self.grid_coordinates.append((row, col))

        # Initialize curves
        self.init_curves()

    def _set_plot_colors(self, plot: pg.PlotItem, plot_settings: dict) -> None:
        """
        Set the plot colors based on the plot config.

        Args:
            plot (pg.PlotItem): Plot object to set the colors.
            plot_settings (dict): Plot settings dictionary.
        """
        if plot_settings.get("show_grid", False):
            plot.showGrid(x=True, y=True, alpha=0.5)
        pen_width = plot_settings.get("axis_width")
        color = plot_settings.get("axis_color")
        if color is None:
            if plot_settings["background_color"].lower() == "black":
                color = "w"
                self.setBackground("k")
            elif plot_settings["background_color"].lower() == "white":
                color = "k"
                self.setBackground("w")
            else:
                raise ValueError(
                    f"Invalid background color {plot_settings['background_color']}. Allowed values"
                    " are 'white' or 'black'."
                )
        pen = pg.mkPen(color=color, width=pen_width)
        x_axis = plot.getAxis("bottom")  # 'bottom' corresponds to the x-axis
        x_axis.setPen(pen)
        x_axis.setTextPen(pen)
        x_axis.setTickPen(pen)

        y_axis = plot.getAxis("left")  # 'left' corresponds to the y-axis
        y_axis.setPen(pen)
        y_axis.setTextPen(pen)
        y_axis.setTickPen(pen)

    def init_curves(self) -> None:
        """
        Initialize curve data and properties for each plot and data source.
        """
        self.curves_data = {}

        for idx, plot_config in enumerate(self.plot_data):
            plot_name = plot_config.get("plot_name", "")
            plot = self.plots[plot_name]
            plot.clear()

            for source in plot_config["sources"]:
                source_type = source["type"]
                y_signals = source["signals"].get("y", [])
                colors_ys = Colors.golden_angle_color(
                    colormap=self.plot_settings["colormap"], num=len(y_signals)
                )

                if source_type not in self.curves_data:
                    self.curves_data[source_type] = {}
                if plot_name not in self.curves_data[source_type]:
                    self.curves_data[source_type][plot_name] = []

                for i, (y_signal, color) in enumerate(zip(y_signals, colors_ys)):
                    y_name = y_signal["name"]
                    y_entry = y_signal.get("entry", y_name)
                    curve_name = f"{y_name} ({y_entry})-{source_type[0].upper()}"
                    curve_data = self.create_curve(curve_name, color)
                    plot.addItem(curve_data)
                    self.curves_data[source_type][plot_name].append((y_name, y_entry, curve_data))

        # Render static plot elements
        self.update_plot()
        # # Hook Crosshair #TODO enable later, currently not working
        if self.enable_crosshair is True:
            self.hook_crosshair()

    def create_curve(self, curve_name: str, color: str) -> pg.PlotDataItem:
        """
        Create
        Args:
            curve_name: Name of the curve
            color(str): Color of the curve

        Returns:
            pg.PlotDataItem: Assigned curve object
        """
        user_color = self.user_colors.get(curve_name, None)
        color_to_use = user_color if user_color else color
        pen_curve = mkPen(color=color_to_use, width=2, style=QtCore.Qt.DashLine)
        brush_curve = mkBrush(color=color_to_use)

        return pg.PlotDataItem(
            symbolSize=5,
            symbolBrush=brush_curve,
            pen=pen_curve,
            skipFiniteCheck=True,
            name=curve_name,
        )

    def hook_crosshair(self) -> None:
        """Hook the crosshair to all plots."""
        # TODO can be extended to hook crosshair signal for mouse move/clicked
        self.crosshairs = {}
        for plot_name, plot in self.plots.items():
            crosshair = Crosshair(plot, precision=3)
            self.crosshairs[plot_name] = crosshair

    def update_scan_segment_plot(self):
        """
        Update the plot with the latest scan segment data.
        """
        self.update_plot(source_type="scan_segment")

    def update_plot(self, source_type=None) -> None:
        """
        Update the plot data based on the stored data dictionary.
        Only updates data for the specified source_type if provided.
        """
        for src_type, plots in self.curves_data.items():
            if source_type and src_type != source_type:
                continue

            for plot_name, curve_list in plots.items():
                plot_config = next(
                    (pc for pc in self.plot_data if pc.get("plot_name") == plot_name), None
                )
                if not plot_config:
                    continue

                x_name, x_entry = self.extract_x_config(plot_config, src_type)

                for y_name, y_entry, curve in curve_list:
                    data_x = self.database.get(src_type, {}).get(x_name, {}).get(x_entry, [])
                    data_y = self.database.get(src_type, {}).get(y_name, {}).get(y_entry, [])
                    curve.setData(data_x, data_y)

    def extract_x_config(self, plot_config: dict, source_type: str) -> tuple:
        """Extract the signal configurations for x and y axes from plot_config.
        Args:
            plot_config (dict): Plot configuration.
        Returns:
            tuple: Tuple containing the x name and x entry.
        """
        x_name, x_entry = None, None

        for source in plot_config["sources"]:
            if source["type"] == source_type and "x" in source["signals"]:
                x_signal = source["signals"]["x"][0]
                x_name = x_signal.get("name")
                x_entry = x_signal.get("entry", x_name)
                return x_name, x_entry

    def get_config(self):
        """Return the current configuration settings."""
        return self.config

    def show_config_dialog(self):
        """Show the configuration dialog."""
        from bec_widgets.widgets import ConfigDialog

        dialog = ConfigDialog(
            client=self.client, default_config=self.config, skip_validation=self.skip_validation
        )
        dialog.config_updated.connect(self.on_config_update)
        dialog.show()

    def update_client(self, client) -> None:
        """Update the client and device manager from BEC.
        Args:
            client: BEC client
        """
        self.client = client
        self.dev = self.client.device_manager.devices

    def _close_all_plots(self):
        """Close all plots."""
        for plot in self.plots.values():
            plot.clear()

    @pyqtSlot(dict)
    def on_instruction(self, msg_content: dict) -> None:
        """
        Handle instructions sent to the GUI.
        Possible actions are:
            - clear: Clear the plots
            - close: Close the GUI
            - config_dialog: Open the configuration dialog

        Args:
            msg_content (dict): Message content with the instruction and parameters.
        """
        action = msg_content.get("action", None)
        parameters = msg_content.get("parameters", None)

        if action == "clear":
            self.flush()
            self._close_all_plots()
        elif action == "close":
            self.close()
        elif action == "config_dialog":
            self.show_config_dialog()
        else:
            print(f"Unknown instruction received: {msg_content}")

    @pyqtSlot(dict)
    def on_config_update(self, config: dict) -> None:
        """
        Validate and update the configuration settings for the PlotApp.
        Args:
            config(dict): Configuration settings
        """
        # convert config from BEC CLI to correct formatting
        config_tag = config.get("config", None)
        if config_tag is not None:
            config = config["config"]

        if self.skip_validation is True:
            self.config = config
            self._init_config()
        else:
            try:
                validated_config = self.validator.validate_monitor_config(config)
                self.config = validated_config.model_dump()
                self._init_config()
            except ValidationError as e:
                error_str = str(e)
                formatted_error_message = BECMonitor.format_validation_error(error_str)

                # Display the formatted error message in a popup
                QMessageBox.critical(self, "Configuration Error", formatted_error_message)

    @staticmethod
    def format_validation_error(error_str: str) -> str:
        """
        Format the validation error string to be displayed in a popup.
        Args:
            error_str(str): Error string from the validation error.
        """
        error_lines = error_str.split("\n")
        # The first line contains the number of errors.
        error_header = f"<p><b>{error_lines[0]}</b></p><hr>"

        formatted_error_message = error_header
        # Skip the first line as it's the header.
        error_details = error_lines[1:]

        # Iterate through pairs of lines (each error's two lines).
        for i in range(0, len(error_details), 2):
            location = error_details[i]
            message = error_details[i + 1] if i + 1 < len(error_details) else ""

            formatted_error_message += f"<p><b>{location}</b><br>{message}</p><hr>"

        return formatted_error_message

    def flush(self, flush_all=False, source_type_to_flush=None) -> None:
        """Update or reset the database to match the current configuration.

        Args:
            flush_all (bool): If True, reset the entire database.
            source_type_to_flush (str): Specific source type to reset. Ignored if flush_all is True.
        """
        if flush_all:
            self.database = self._init_database(self.plot_data)
            self.init_curves()
        else:
            if source_type_to_flush in self.database:
                # TODO maybe reinit the database from config again instead of cycle through names/entries
                # Reset only the specified source type
                for name in self.database[source_type_to_flush]:
                    for entry in self.database[source_type_to_flush][name]:
                        self.database[source_type_to_flush][name][entry] = []
                # Reset curves for the specified source type
                if source_type_to_flush in self.curves_data:
                    self.init_curves()

    @pyqtSlot(dict, dict)
    def on_scan_segment(self, msg: dict, metadata: dict):
        """
        Handle new scan segments and saves data to a dictionary. Linked through bec_dispatcher.

        Args:
            msg (dict): Message received with scan data.
            metadata (dict): Metadata of the scan.
        """
        current_scan_id = msg.get("scan_id", None)
        if current_scan_id is None:
            return

        if current_scan_id != self.scan_id:
            if self.scan_types is False:
                self.plot_data = self.plot_data_config
            elif self.scan_types is True:
                current_name = metadata.get("scan_name")
                if current_name is None:
                    raise ValueError(
                        "Scan name not found in metadata. Please check the scan_name in the YAML"
                        " config or in bec configuration."
                    )
                self.plot_data = self.plot_data_config.get(current_name, None)
                if not self.plot_data:
                    raise ValueError(
                        f"Scan name {current_name} not found in the YAML config. Please check the scan_name in the "
                        "YAML config or in bec configuration."
                    )

                # Init UI
                self._init_ui(self.plot_settings["num_columns"])

            self.scan_id = current_scan_id
            self.scan_data = self.queue.scan_storage.find_scan_by_ID(self.scan_id)
            if not self.scan_data:
                print(f"No data found for scan_id: {self.scan_id}")  # TODO better error
                return
            self.flush(source_type_to_flush="scan_segment")

        self.scan_segment_update()

        self.update_signal.emit()

    def scan_segment_update(self):
        """
        Update the database with data from scan storage based on the provided scan_id.
        """
        scan_data = self.scan_data.data
        for device_name, device_entries in self.database.get("scan_segment", {}).items():
            for entry in device_entries.keys():
                dataset = scan_data[device_name][entry].val
                if dataset:
                    self.database["scan_segment"][device_name][entry] = dataset
                else:
                    print(f"No data found for {device_name} {entry}")

    def replot_last_scan(self):
        """
        Replot the last scan.
        """
        self.scan_segment_update()
        self.update_plot(source_type="scan_segment")

    @pyqtSlot(dict)
    def on_data_from_redis(self, msg) -> None:
        """
        Handle new data sent from redis.
        Args:
            msg (dict): Message received with  data.
        """

        # wait until new config is loaded
        while "redis" not in self.database:
            time.sleep(0.1)
        self._init_database(
            self.plot_data, source_type_to_init="redis"
        )  # add database entry for redis dataset

        data = msg.get("data", {})
        x_data = data.get("x", {})
        y_data = data.get("y", {})

        # Update x data
        if x_data:
            x_tag = x_data.get("tag")
            self.database["redis"][x_tag][x_tag] = x_data["data"]

        # Update y data
        for y_tag, y_info in y_data.items():
            self.database["redis"][y_tag][y_tag] = y_info["data"]

        # Trigger plot update
        self.update_plot(source_type="redis")
        print(f"database after: {self.database}")


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
        config = CONFIG_SIMPLE

    client = BECDispatcher().client
    client.start()
    app = QApplication(sys.argv)
    monitor = BECMonitor(config=config, gui_id=args.id, skip_validation=False)
    monitor.show()
    # just to test redis data
    # redis_data = {
    #     "x": {"data": [1, 2, 3], "tag": "x_default_tag"},
    #     "y": {"y_default_tag": {"data": [1, 2, 3]}},
    # }
    # monitor.on_data_from_redis({"data": redis_data})
    sys.exit(app.exec())
