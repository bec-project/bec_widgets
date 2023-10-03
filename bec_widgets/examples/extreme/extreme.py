import os

import pyqtgraph
import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QTableWidgetItem,
    QTableWidget,
    QFileDialog,
    QMessageBox,
)
from pyqtgraph import ColorButton
from pyqtgraph import mkBrush, mkPen
from pyqtgraph.Qt import QtCore, uic
from pyqtgraph.Qt import QtWidgets

from bec_lib.core import MessageEndpoints
from bec_widgets.qt_utils import Crosshair, Colors


# TODO implement:
#   - implement scanID database for visualizing previous scans


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
        config (dict): Configuration dictionary containing all settings for the plotting app.
                      It should include the following keys:
                      - 'plot_settings': Dictionary containing global plot settings.
                      - 'plot_data': List of dictionaries specifying the signals to plot.
        parent (QWidget, optional): Parent widget.

    Example:
        General Plot Configuration:
        {
            'plot_settings': {'background_color': 'black', 'num_columns': 2, 'colormap': 'plasma', 'scan_types': False},
            'plot_data': [
                {
                    'plot_name': 'Plot A',
                    'x': {'label': 'X-axis', 'signals': [{'name': 'device_x', 'entry': 'entry_x'}]},
                    'y': {'label': 'Y-axis', 'signals': [{'name': 'device_y', 'entry': 'entry_y'}]}
                }
            ]
        }

        Different Scans Mode Configuration:
        {
            'plot_settings': {'background_color': 'black', 'num_columns': 2, 'colormap': 'plasma', 'scan_types': True},
            'plot_data': {
                'scan_type_1': [
                    {
                        'plot_name': 'Plot 1',
                        'x': {'label': 'X-axis', 'signals': [{'name': 'device_x1', 'entry': 'entry_x1'}]},
                        'y': {'label': 'Y-axis', 'signals': [{'name': 'device_y1', 'entry': 'entry_y1'}]}
                    }
                ],
                'scan_type_2': [
                    {
                        'plot_name': 'Plot 2',
                        'x': {'label': 'X-axis', 'signals': [{'name': 'device_x2', 'entry': 'entry_x2'}]},
                        'y': {'label': 'Y-axis', 'signals': [{'name': 'device_y2', 'entry': 'entry_y2'}]}
                    }
                ]
            }
        }
    """

    update_signal = pyqtSignal()
    update_dap_signal = pyqtSignal()

    def __init__(self, config: dict, client=None, parent=None):
        super(PlotApp, self).__init__(parent)

        # Client and device manager from BEC
        self.client = bec_dispatcher.client if client is None else client
        self.dev = self.client.device_manager.devices

        # Loading UI
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "extreme.ui"), self)

        self.data = {}

        self.crosshairs = None
        self.plots = None
        self.curves_data = None
        self.grid_coordinates = None
        self.scanID = None

        self.user_colors = {}  # key: (plot_name, y_name, y_entry), value: color

        # Validate the configuration before proceeding
        self.load_config(config)

        # YAML config
        self.init_config(config)

        self.splitter.setSizes([400, 100])

        # Buttons
        self.pushButton_save.clicked.connect(self.save_settings_to_yaml)
        self.pushButton_load.clicked.connect(self.load_settings_from_yaml)

        # Connect the update signal to the update plot method
        self.proxy_update_plot = pg.SignalProxy(
            self.update_signal, rateLimit=25, slot=self.update_plot
        )

        # Change layout of plots when the number of columns is changed in GUI
        self.spinBox_N_columns.valueChanged.connect(lambda x: self.init_ui(x))

    def validate_config(self, config: dict) -> None:
        """
        Validate the configuration dictionary.
        Args:
            config (dict): Configuration dictionary form .yaml file.

        Returns:
            None
        """
        errors = []

        # Validate common keys
        required_top_level_keys = ["plot_settings", "plot_data"]
        for key in required_top_level_keys:
            if key not in config:
                errors.append(f"Missing required key: {key}")

        # Determine the configuration mode (device or scan)
        plot_settings = config.get("plot_settings", {})
        is_scan_mode = plot_settings.get("scan_types", False)

        plot_data = config.get("plot_data", [])

        if is_scan_mode:
            # Validate scan mode configuration
            for scan_type, plots in plot_data.items():
                for i, plot_config in enumerate(plots):
                    self.validate_plot_config(plot_config, errors, i)
        else:
            # Validate device mode configuration
            for i, plot_config in enumerate(plot_data):
                self.validate_plot_config(plot_config, errors, i)

        if errors:
            error_message = "\n".join(errors)
            # self.display_error(error_message)
            raise ValueError(error_message)

    # def display_error(self, error_message: str) -> None: #TODO maybe can be used for some other error messages
    #     """
    #     Display an error message in a QMessageBox.
    #     Args:
    #         error_message (str): The error message to display.
    #
    #     Returns:
    #
    #     """
    #     QMessageBox.critical(self, "Configuration Error", error_message)

    def load_config(self, initial_config: dict) -> None:
        """
        Load and validate the configuration, retrying until a valid configuration is provided or the user cancels.
        Args:
            config (dict): Configuration dictionary form .yaml file.

        Returns:
            None
        """
        valid_config = False
        config = initial_config  # Use the initial_config if provided
        while not valid_config:
            if config is None:
                config = self.load_settings_from_yaml()  # Load config if it hasn't been loaded yet
            try:
                self.validate_config(config)
                valid_config = True
            except ValueError as e:
                choice = QMessageBox.critical(
                    self,
                    "Configuration Error",
                    str(e) + "\n\nWould you like to reload the configuration?",
                    QMessageBox.Retry | QMessageBox.Cancel,
                )
                if choice == QMessageBox.Retry:
                    config = (
                        self.load_settings_from_yaml()
                    )  # Update config with newly loaded config
                else:
                    exit(1)  # Exit the program if the user selects Cancel

    def validate_plot_config(self, plot_config: dict, errors: list, i: int):
        """
        Validate individual plot configuration.
        Args:
            plot_config (dict): Individual plot configuration.
            errors (list): List to collect error messages.
            i (int): Index of the plot configuration.

        Returns:
            None
        """
        for axis in ["x", "y"]:
            axis_config = plot_config.get(axis)
            plot_name = plot_config.get("plot_name", "")
            if axis_config is None:
                errors.append(f"Missing '{axis}' configuration in plot {i} - {plot_name}")

            signals_config = axis_config.get("signals")
            if signals_config is None:
                errors.append(
                    f"Missing 'signals' configuration for {axis} axis in plot {i} - '{plot_name}'"
                )
            elif not isinstance(signals_config, list) or len(signals_config) == 0:
                errors.append(
                    f"'signals' configuration for {axis} axis in plot {i} must be a non-empty list"
                )

    def init_config(self, config: dict) -> None:
        """
        Initializes or update the configuration settings for the PlotApp.

        Args:
            config (dict): Dictionary containing plot settings and data configurations.
        """

        # YAML config
        self.plot_settings = config.get("plot_settings", {})
        self.plot_data_config = config.get("plot_data", {})
        self.scan_types = self.plot_settings.get("scan_types", False)

        if self.scan_types is False:  # Device tracking mode
            self.plot_data = self.plot_data_config  # TODO logic has to be improved
        else:  # setup first line scan as default, then changed with different scan type
            self.plot_data = self.plot_data_config[list(self.plot_data_config.keys())[0]]

        # Setting global plot settings
        self.init_plot_background(self.plot_settings["background_color"])

        # Initialize the UI
        self.init_ui(self.plot_settings["num_columns"])
        self.spinBox_N_columns.setValue(
            self.plot_settings["num_columns"]
        )  # TODO has to be checked if it will not setup more columns than plots
        self.spinBox_N_columns.setMaximum(len(self.plot_data))

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
            raise ValueError(
                f"Invalid background color {background_color}. Allowed values are 'white' or 'black'."
            )

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

        # Check if num_columns exceeds the number of plots
        if num_columns >= num_plots:
            num_columns = num_plots
            self.plot_settings["num_columns"] = num_columns  # Update the settings
            print(
                f"Warning: num_columns in the YAML file was greater than the number of plots. Resetting num_columns to number of plots:{num_columns}."
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
                # print(y_config)
                y_name = y_config["name"]
                y_entries = y_config.get("entry", [y_name])

                if not isinstance(y_entries, list):
                    y_entries = [y_entries]

                for y_entry in y_entries:
                    user_color = self.user_colors.get((plot_name, y_name, y_entry), None)
                    color_to_use = user_color if user_color else color

                    pen_curve = mkPen(color=color_to_use, width=2, style=QtCore.Qt.DashLine)
                    brush_curve = mkBrush(color=color_to_use)

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

                    # Create a ColorButton and set its color
                    color_btn = ColorButton()
                    color_btn.setColor(color_to_use)
                    color_btn.sigColorChanged.connect(
                        lambda btn=color_btn, plot=plot_name, yname=y_name, yentry=y_entry, curve=curve_data: self.change_curve_color(
                            btn, plot, yname, yentry, curve
                        )
                    )

                    # Add the ColorButton as a QWidget to the table
                    color_widget = QtWidgets.QWidget()
                    layout = QtWidgets.QHBoxLayout()
                    layout.addWidget(color_btn)
                    layout.setContentsMargins(0, 0, 0, 0)
                    color_widget.setLayout(layout)

                    row = len(row_labels) - 1  # The row index in the table
                    self.tableWidget_crosshair.setCellWidget(row, 2, color_widget)

            self.curves_data[plot_name] = curve_list

        self.tableWidget_crosshair.setRowCount(len(row_labels))
        self.tableWidget_crosshair.setVerticalHeaderLabels(row_labels)
        self.hook_crosshair()

    def change_curve_color(
        self,
        btn: pyqtgraph.ColorButton,
        plot_name: str,
        y_name: str,
        y_entry: str,
        curve: pyqtgraph.PlotDataItem,
    ) -> None:
        """
        Change the color of a curve and update the corresponding ColorButton.

        Args:
            btn (ColorButton): The ColorButton that was clicked.
            plot_name (str): The name of the plot where the curve belongs.
            y_name (str): The name of the y signal.
            y_entry (str): The entry of the y signal.
            curve (PlotDataItem): The curve to be changed.
        """
        color = btn.color()
        pen_curve = mkPen(color=color, width=2, style=QtCore.Qt.DashLine)
        brush_curve = mkBrush(color=color)
        curve.setPen(pen_curve)
        curve.setSymbolBrush(brush_curve)
        self.user_colors[(plot_name, y_name, y_entry)] = color

    def hook_crosshair(self) -> None:
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
        Handle new scan segments and saves data to a dictionary. Linked through bec_dispatcher.

        Args:
            msg (dict): Message received with scan data.
            metadata (dict): Metadata of the scan.
        """

        current_scanID = msg.get("scanID", None)
        if current_scanID is None:
            return

        if current_scanID != self.scanID:
            if self.scan_types is False:
                self.plot_data = self.plot_data_config
            elif self.scan_types is True:
                currentName = metadata.get("scan_name")
                if currentName is None:
                    raise ValueError(
                        f"Scan name not found in metadata. Please check the scan_name in the YAML config or in bec "
                        f"configuration."
                    )
                    return
                self.plot_data = self.plot_data_config.get(currentName, [])
                if self.plot_data == []:
                    raise ValueError(
                        f"Scan name {currentName} not found in the YAML config. Please check the scan_name in the "
                        f"YAML config or in bec configuration."
                    )
                    return

                # Init UI
                self.init_ui(self.plot_settings["num_columns"])
                self.spinBox_N_columns.setValue(
                    self.plot_settings["num_columns"]
                )  # TODO has to be checked if it will not setup more columns than plots
                self.spinBox_N_columns.setMaximum(len(self.plot_data))

            self.scanID = current_scanID
            self.data = {}
            self.init_curves()

        for plot_config in self.plot_data:
            plot_name = plot_config.get("plot_name", "Unnamed Plot")
            x_config = plot_config["x"]
            x_signal_config = x_config["signals"][0]  # Assuming there's at least one signal for x

            x_name = x_signal_config.get("name", "")
            if not x_name:
                raise ValueError(f"Name for x signal must be specified in plot: {plot_name}.")

            x_entry_list = x_signal_config.get("entry", [])
            if not x_entry_list:
                x_entry_list = (
                    self.dev[x_name]._hints if hasattr(self.dev[x_name], "_hints") else [x_name]
                )

            if not isinstance(x_entry_list, list):
                x_entry_list = [x_entry_list]

            y_configs = plot_config["y"]["signals"]

            for x_entry in x_entry_list:
                for y_config in y_configs:
                    y_name = y_config.get("name", "")
                    if not y_name:
                        raise ValueError(
                            f"Name for y signal must be specified in plot: {plot_name}."
                        )

                    y_entry_list = y_config.get("entry", [])
                    if not y_entry_list:
                        y_entry_list = (
                            self.dev[y_name]._hints
                            if hasattr(self.dev[y_name], "_hints")
                            else [y_name]
                        )

                    if not isinstance(y_entry_list, list):
                        y_entry_list = [y_entry_list]

                    for y_entry in y_entry_list:
                        key = (x_name, x_entry, y_name, y_entry)

                        data_x = msg["data"].get(x_name, {}).get(x_entry, {}).get("value", None)
                        data_y = msg["data"].get(y_name, {}).get(y_entry, {}).get("value", None)

                        if data_x is None:
                            raise ValueError(
                                f"Incorrect entry '{x_entry}' specified for x in plot: {plot_name}, x name: {x_name}"
                            )

                        if data_y is None:
                            if hasattr(self.dev[y_name], "_hints"):
                                raise ValueError(
                                    f"Incorrect entry '{y_entry}' specified for y in plot: {plot_name}, y name: {y_name}"
                                )
                            else:
                                raise ValueError(
                                    f"No hints available for y in plot: {plot_name}, and name '{y_name}' did not work as entry"
                                )

                        if data_x is not None:
                            self.data.setdefault(key, {}).setdefault("x", []).append(data_x)

                        if data_y is not None:
                            self.data.setdefault(key, {}).setdefault("y", []).append(data_y)

        self.update_signal.emit()

    def save_settings_to_yaml(self):
        """Save the current settings to a .yaml file using a file dialog."""
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Settings", "", "YAML Files (*.yaml);;All Files (*)", options=options
        )

        if file_path:
            try:
                if not file_path.endswith(".yaml"):
                    file_path += ".yaml"

                with open(file_path, "w") as file:
                    yaml.dump(
                        {"plot_settings": self.plot_settings, "plot_data": self.plot_data_config},
                        file,
                    )
                print(f"Settings saved to {file_path}")
            except Exception as e:
                print(f"An error occurred while saving the settings to {file_path}: {e}")

    def load_settings_from_yaml(self) -> dict:
        """Load settings from a .yaml file using a file dialog and update the current settings."""
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Settings", "", "YAML Files (*.yaml);;All Files (*)", options=options
        )

        if file_path:
            try:
                with open(file_path, "r") as file:
                    config = yaml.safe_load(file)

                # Validate config
                self.load_config(config)

                # YAML config
                self.init_config(config)

                print(f"Settings loaded from {file_path}")
                return config
            except FileNotFoundError:
                print(f"The file {file_path} was not found.")
            except Exception as e:
                print(f"An error occurred while loading the settings from {file_path}: {e}")


if __name__ == "__main__":
    import yaml
    import argparse

    # from bec_widgets import ctrl_c
    from bec_widgets.bec_dispatcher import bec_dispatcher

    parser = argparse.ArgumentParser(description="Plotting App")
    parser.add_argument(
        "--config",
        "-c",
        help="Path to the .yaml configuration file",
        default="config_wrong.yaml",
    )
    args = parser.parse_args()

    try:
        with open(args.config, "r") as file:
            config = yaml.safe_load(file)

    except FileNotFoundError:
        print(f"The file {args.config} was not found.")
        exit(1)
    except Exception as e:
        print(f"An error occurred while loading the config file: {e}")
        exit(1)

    # BECclient global variables
    client = bec_dispatcher.client
    client.start()

    app = QApplication([])
    plotApp = PlotApp(config=config, client=client)

    # Connecting signals from bec_dispatcher
    bec_dispatcher.connect_slot(plotApp.on_scan_segment, MessageEndpoints.scan_segment())
    # ctrl_c.setup(app)

    window = plotApp
    window.show()
    app.exec_()
