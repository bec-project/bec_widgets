from __future__ import annotations

import time
from typing import Any, Union

import numpy as np
import pyqtgraph as pg
from bec_lib import MessageEndpoints
from qtpy import QtCore
from qtpy import QtGui
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtWidgets import QApplication

from bec_widgets.utils.yaml_dialog import load_yaml
from bec_widgets.utils.bec_dispatcher import bec_dispatcher

CONFIG_DEFAULT = {
    "plot_settings": {
        "colormap": "Greys",
        "scatter_size": 5,
        "max_points": 1000,
        "num_dim_points": 100,
        "precision": 2,
        "num_columns": 1,
        "background_value": 25,
    },
    "motors": [
        {
            "plot_name": "Motor Map",
            "x_label": "Motor X",
            "y_label": "Motor Y",
            "signals": {
                "x": [{"name": "samx", "entry": "samx"}],
                "y": [{"name": "samy", "entry": "samy"}],
            },
        },
        {
            "plot_name": "Motor Map 2 ",
            "x_label": "Motor X",
            "y_label": "Motor Y",
            "signals": {
                "x": [{"name": "aptrx", "entry": "aptrx"}],
                "y": [{"name": "aptry", "entry": "aptry"}],
            },
        },
    ],
}


class MotorMap(pg.GraphicsLayoutWidget):
    update_signal = pyqtSignal()

    def __init__(
        self,
        parent=None,
        client=None,
        config: dict = None,
        gui_id=None,
        skip_validation: bool = False,
    ):
        super().__init__(parent=parent)

        # Import BEC related stuff
        self.client = bec_dispatcher.client if client is None else client
        self.dev = self.client.device_manager.devices

        # TODO import validator when prepared
        self.gui_id = gui_id

        if self.gui_id is None:
            self.gui_id = self.__class__.__name__ + str(time.time())

        # Current configuration
        self.config = config
        self.skip_validation = skip_validation  # TODO implement validation when validator is ready

        # Connect the update signal to the update plot method
        self.proxy_update_plot = pg.SignalProxy(
            self.update_signal, rateLimit=25, slot=self._update_plots
        )

        # Init UI with config
        if self.config is None:
            print("No initial config found for MotorMap. Using default config.")
        else:
            self.on_config_update(self.config)

    @pyqtSlot(dict)
    def on_config_update(self, config: dict) -> None:
        """
        Validate and update the configuration settings for the PlotApp.
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

    def _init_config(self):
        """Initiate the configuration."""

        # Global widget settings
        self._get_global_settings()
        # Motor settings
        self.plot_data = self.config.get("motors", {})

        # Include motor limits into the config
        # unique_signals = self._find_unique_signals(self.plot_data) #TODO is it needed?
        self._add_limits_to_plot_data()

        # Initialize the database
        self.database = self._init_database()

        # Initialize the plot UI
        self._init_ui()

        # Connect motors to slots
        self._connect_motors_to_slots()

    def _get_global_settings(self):
        """Get global settings from the config."""
        self.plot_settings = self.config.get("plot_settings", {})

        self.max_points = self.plot_settings.get("max_points", 5000)
        self.num_dim_points = self.plot_settings.get("num_dim_points", 100)
        self.scatter_size = self.plot_settings.get("scatter_size", 5)
        self.precision = self.plot_settings.get("precision", 2)
        self.background_value = self.plot_settings.get("background_value", 25)

    def _connect_motors_to_slots(self):
        """Connect motors to slots."""

        # Disconnect all slots before connecting a new ones
        bec_dispatcher.disconnect_all()

        # Get list of all unique motors
        unique_motors = []
        for motor_config in self.plot_data:
            for axis in ["x", "y"]:
                for signal in motor_config["signals"][axis]:
                    unique_motors.append(signal["name"])
        unique_motors = list(set(unique_motors))

        # Create list of endpoint
        endpoints = []
        for motor in unique_motors:
            endpoints.append(MessageEndpoints.device_readback(motor))

        # Connect all topics to a single slot
        bec_dispatcher.connect_slot(
            self.on_device_readback,
            endpoints,
            single_callback_for_all_topics=True,
        )

    def _add_limits_to_plot_data(self):
        """
        Add limits to each motor signal in the plot_data.
        """
        for motor_config in self.plot_data:
            for axis in ["x", "y"]:
                for signal in motor_config["signals"][axis]:
                    motor_name = signal["name"]
                    motor_limits = self._get_motor_limit(motor_name)
                    signal["limits"] = motor_limits

    def _get_motor_limit(self, motor: str) -> Union[Any | None]:
        """
        Get the motor limit from the config.
        Args:
            motor(str): Motor name.

        Returns:
            float: Motor limit.
        """
        try:
            limits = self.dev[motor].limits
            if limits == [0, 0]:
                return None
            else:
                return limits
        except AttributeError:  # TODO maybe not needed, if no limits it returns [0,0]
            # If the motor doesn't have a 'limits' attribute, return a default value or raise a custom exception
            print(f"The device '{motor}' does not have defined limits.")

    def _find_unique_signals(self, plot_data: dict) -> list:  # TODO needed or not?
        """
        Find unique signals in the plot data.

        Args:
            plot_data(dict): Plot data.

        Returns:
            list: List of unique signals.
        """
        unique_pairs = set()
        for motor in plot_data:
            for axis in ["x", "y"]:
                for signal in motor["signals"][axis]:
                    unique_pairs.add((signal["name"], signal["entry"]))
        unique_pairs_list = list(unique_pairs)

        return unique_pairs_list

    def _init_database(self):
        """Initiate the database according the config."""
        # TODO maybe implement _find_unique_signals here instead of doing it in this method?
        database = {}

        for plot in self.plot_data:
            for axis, signals in plot["signals"].items():
                for signal in signals:
                    name = signal["name"]
                    entry = signal.get("entry", name)
                    if name not in database:
                        database[name] = {}
                    if entry not in database[name]:
                        initial_value = self._get_initial_coordinate(name, entry)
                        database[name][entry] = [initial_value]
        return database

    def _get_initial_coordinate(self, name, entry):
        """Get the initial coordinate value for a motor."""
        try:
            return self.dev[name].readback.read()[entry]["value"]
        except Exception as e:
            print(f"Error getting initial value for {name}: {e}")
            return None

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
        self.curves_data = {}  # TODO moved from init_curves

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

            if "plot_name" not in plot_config:
                plot_name = f"Plot ({row}, {col})"
                plot_config["plot_name"] = plot_name
            else:
                plot_name = plot_config["plot_name"]

            x_label = plot_config.get("x_label", "")
            y_label = plot_config.get("y_label", "")

            plot = self.addPlot(row=row, col=col, colspan=colspan, title="Motor position: (X, Y)")
            plot.setLabel("bottom", f"{x_label} ({plot_config['signals']['x'][0]['name']})")
            plot.setLabel("left", f"{y_label} ({plot_config['signals']['y'][0]['name']})")
            plot.addLegend()
            # self._set_plot_colors(plot, self.plot_settings) #TODO implement colors

            self.plots[plot_name] = plot
            self.grid_coordinates.append((row, col))

            self._init_motor_map(plot_config)

    def _init_motor_map(self, plot_config: dict) -> None:
        """
        Initialize the motor map.
        Args:
            plot_config(dict): Plot configuration.
        """

        # Get plot name to find appropriate plot
        plot_name = plot_config.get("plot_name", "")

        # Reset the curves data
        plot = self.plots[plot_name]
        plot.clear()

        limits_x, limits_y = plot_config["signals"]["x"][0].get("limits", None), plot_config[
            "signals"
        ]["y"][0].get("limits", None)
        if limits_x is not None and limits_y is not None:
            self._make_limit_map(plot, [limits_x, limits_y])

        # Initiate ScatterPlotItem for motor coordinates
        self.curves_data[plot_name] = {
            "pos": pg.ScatterPlotItem(
                size=self.scatter_size, pen=pg.mkPen(None), brush=pg.mkBrush(255, 255, 255, 255)
            )
        }

        # Add the scatter plot to the plot
        plot.addItem(self.curves_data[plot_name]["pos"])
        # Set the point map to be always on the top
        self.curves_data[plot_name]["pos"].setZValue(0)

        # Add all layers to the plot
        plot.showGrid(x=True, y=True)

        # Add the crosshair for motor coordinates
        init_position_x = self._get_motor_init_position(
            plot_config["signals"]["x"][0]["name"], plot_config["signals"]["x"][0]["entry"]
        )
        init_position_y = self._get_motor_init_position(
            plot_config["signals"]["y"][0]["name"], plot_config["signals"]["y"][0]["entry"]
        )
        self._add_coordinantes_crosshair(plot_name, init_position_x, init_position_y)

    def _add_coordinantes_crosshair(self, plot_name: str, x: float, y: float) -> None:
        """
        Add crosshair to the plot to highlight the current position.
        Args:
            plot_name(str): Name of the plot.
            x(float): X coordinate.
            y(float): Y coordinate.
        """
        # find the current plot
        plot = self.plots[plot_name]

        # Crosshair to highlight the current position
        highlight_H = pg.InfiniteLine(
            angle=0, movable=False, pen=pg.mkPen(color="r", width=1, style=QtCore.Qt.DashLine)
        )
        highlight_V = pg.InfiniteLine(
            angle=90, movable=False, pen=pg.mkPen(color="r", width=1, style=QtCore.Qt.DashLine)
        )

        # Add crosshair to the curve list for future referencing
        self.curves_data[plot_name]["highlight_H"] = highlight_H
        self.curves_data[plot_name]["highlight_V"] = highlight_V

        # Add crosshair to the plot
        plot.addItem(highlight_H)
        plot.addItem(highlight_V)

        highlight_H.setPos(x)
        highlight_V.setPos(y)

    def _make_limit_map(self, plot: pg.PlotItem, limits: list):
        """
        Make a limit map from the limits list.

        Args:
            plot(pg.PlotItem): Plot to add the limit map to.
            limits(list): List of limits.
        """
        # Define the size of the image map based on the motor's limits
        limit_x_min, limit_x_max = limits[0]
        limit_y_min, limit_y_max = limits[1]

        map_width = int(limit_x_max - limit_x_min + 1)
        map_height = int(limit_y_max - limit_y_min + 1)

        limit_map_data = np.full((map_width, map_height), self.background_value, dtype=np.float32)

        # Create the image map
        limit_map = pg.ImageItem()
        limit_map.setImage(limit_map_data)
        plot.addItem(limit_map)

        # Translate and scale the image item to match the motor coordinates
        tr = QtGui.QTransform()
        tr.translate(limit_x_min, limit_y_min)
        limit_map.setTransform(tr)

    def _get_motor_init_position(self, name: str, entry: str) -> float:
        """
        Get the motor initial position from the config.
        Args:
            name(str): Motor name.
            entry(str): Motor entry.
        Returns:
            float: Motor initial position.
        """
        init_position = round(self.dev[name].read()[entry]["value"], self.precision)
        return init_position

    def _update_plots(self):
        """Update the motor position on plots."""
        for plot_name, curve_list in self.curves_data.items():
            plot_config = next(
                (pc for pc in self.plot_data if pc.get("plot_name") == plot_name), None
            )
            if not plot_config:
                continue

            # Get the motor coordinates
            x_motor_name = plot_config["signals"]["x"][0]["name"]
            x_motor_entry = plot_config["signals"]["x"][0]["entry"]
            y_motor_name = plot_config["signals"]["y"][0]["name"]
            y_motor_entry = plot_config["signals"]["y"][0]["entry"]

            # update motor position only if there is data
            if (
                len(self.database[x_motor_name][x_motor_entry]) >= 1
                and len(self.database[y_motor_name][y_motor_entry]) >= 1
            ):
                # Relevant data for the plot
                motor_x_data = self.database[x_motor_name][x_motor_entry]
                motor_y_data = self.database[y_motor_name][y_motor_entry]

                # Setup gradient brush for history
                brushes = [pg.mkBrush(50, 50, 50, 255)] * len(motor_x_data)

                # Calculate the decrement step based on self.num_dim_points
                decrement_step = (255 - 50) / self.num_dim_points

                for i in range(1, min(self.num_dim_points + 1, len(motor_x_data) + 1)):
                    brightness = max(60, 255 - decrement_step * (i - 1))
                    brushes[-i] = pg.mkBrush(brightness, brightness, brightness, 255)

                brushes[-1] = pg.mkBrush(
                    255, 255, 255, 255
                )  # Newest point is always full brightness

                # Update the scatter plot
                self.curves_data[plot_name]["pos"].setData(
                    x=motor_x_data,
                    y=motor_y_data,
                    brush=brushes,
                    pen=None,
                    size=self.scatter_size,
                )

                # Get last know position for crosshair
                current_x = motor_x_data[-1]
                current_y = motor_y_data[-1]

                # Update the crosshair
                self.curves_data[plot_name]["highlight_V"].setPos(current_x)
                self.curves_data[plot_name]["highlight_H"].setPos(current_y)

    @pyqtSlot(dict)
    def on_device_readback(self, msg: dict):
        """
        Update the motor coordinates on the plots.
        Args:
            msg (dict): Message received with device readback data.
        """

        for device_name, device_info in msg["signals"].items():
            print(f'Updating device "{device_name}" with value {device_info["value"]}.')
            is_in_config, x_device, y_device = self._find_xy_devices(device_name)
            if is_in_config:
                value = device_info["value"]

                # Update the database with the new value
                self._update_database(device_name, value)

                # Find the corresponding coordinate and update
                corresponding_device = y_device if device_name == x_device else x_device
                self._update_corresponding_coordinate(corresponding_device)

        self.update_signal.emit()

    def _find_xy_devices(self, device_name):
        for motor in self.config.get("motors", []):
            x_signals = [signal["name"] for signal in motor["signals"]["x"]]
            y_signals = [signal["name"] for signal in motor["signals"]["y"]]
            if device_name in x_signals:
                return True, device_name, motor["signals"]["y"][0]["name"]
            elif device_name in y_signals:
                return True, motor["signals"]["x"][0]["name"], device_name
        return False, None, None

    def _update_database(self, device_name: str, value: float):
        """
        Update the database with the new value.
        Args:
            device_name (str): Device name.
            value (float): Device value.
        """
        # Update the database with the new value
        if device_name in self.database:
            self.database[device_name][device_name].append(value)

    def _update_corresponding_coordinate(self, corresponding_device: str):
        """
        Update the corresponding coordinate with the last known value.
        Args:
            corresponding_device: device name of the corresponding coordinate
        """
        # Update the database for the corresponding device with the last known value
        if corresponding_device and corresponding_device in self.database:
            if self.database[corresponding_device][corresponding_device]:
                last_value = self.database[corresponding_device][corresponding_device][-1]
            else:
                last_value = None  # Default value if no data is available

            self.database[corresponding_device][corresponding_device].append(last_value)


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
        config = load_yaml(args.config_file)
    else:
        config = CONFIG_DEFAULT

    client = bec_dispatcher.client
    client.start()
    app = QApplication(sys.argv)
    motor_map = MotorMap(
        config=config,
        gui_id=args.id,
        skip_validation=True,
    )
    motor_map.show()

    sys.exit(app.exec())
