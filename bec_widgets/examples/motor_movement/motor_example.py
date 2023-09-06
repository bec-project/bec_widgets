import os
from enum import Enum
from functools import partial

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtGui
from PyQt5.QtCore import QThread, pyqtSlot, QPoint
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QApplication, QWidget, QTableWidget
from PyQt5.QtWidgets import QShortcut
from pyqtgraph.Qt import QtWidgets, uic, QtCore

from bec_lib.core import MessageEndpoints, BECMessage
from bec_widgets.qt_utils import DoubleValidationDelegate


# TODO - General features
#  - put motor status (moving, stopped, etc)
#  - add mouse interactions with the plot -> click to select coordinates, double click to move?
#  - adjust right click actions


class MotorApp(QWidget):
    """
    Main class for MotorApp, designed to control motor positions based on a flexible YAML configuration.

    Attributes:
        coordinates_updated (pyqtSignal): Signal to trigger coordinate updates.
        selected_motors (dict): Dictionary containing pre-selected motors from the configuration file.
        plot_motors (dict): Dictionary containing settings for plotting motor positions.

    Args:
        selected_motors (dict): Dictionary specifying the selected motors.
        plot_motors (dict): Dictionary specifying settings for plotting motor positions.
        parent (QWidget, optional): Parent widget.
    """

    coordinates_updated = pyqtSignal(float, float)

    def __init__(self, selected_motors: dict = {}, plot_motors: dict = {}, parent=None):
        super(MotorApp, self).__init__(parent)
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "motor_controller.ui"), self)

        # Motor Control Thread
        self.motor_thread = MotorControl()

        self.motor_x, self.motor_y = None, None
        self.limit_x, self.limit_y = None, None

        # Coordinates tracking
        self.motor_positions = np.array([])

        # Config file settings
        self.max_points = plot_motors.get("max_points", 5000)
        self.num_dim_points = plot_motors.get("num_dim_points", 100)
        self.scatter_size = plot_motors.get("scatter_size", 5)
        self.precision = plot_motors.get("precision", 2)
        self.extra_columns = plot_motors.get("extra_columns", None)

        # Saved motors from config file
        self.selected_motors = selected_motors

        # QThread for motor movement + signals
        self.motor_thread.motors_loaded.connect(self.get_available_motors)
        self.motor_thread.motors_selected.connect(self.get_selected_motors)
        self.motor_thread.limits_retrieved.connect(self.update_limits)

        # UI
        self.init_ui()
        self.tag_N = 1  # position label for saved coordinates

        # Get all motors available
        self.motor_thread.retrieve_all_motors()  # TODO link to combobox that it always refresh

    def connect_motor(self, motor_x_name: str, motor_y_name: str):
        """
        Connects to the specified motors and initializes the UI for motor control.

        Args:
            motor_x_name (str): Name of the motor controlling the x-axis.
            motor_y_name (str): Name of the motor controlling the y-axis.
        """
        self.motor_thread.connect_motors(motor_x_name, motor_y_name)
        self.motor_thread.retrieve_motor_limits(self.motor_x, self.motor_y)

        # self.init_motor_map()

        self.motorControl.setEnabled(True)
        self.motorControl_absolute.setEnabled(True)
        self.tabWidget_tables.setTabEnabled(1, True)

        self.generate_table_coordinate(
            self.tableWidget_coordinates,
            self.motor_thread.retrieve_coordinates(),
            tag=f"{motor_x_name},{motor_y_name}",
            precision=self.precision,
        )

    @pyqtSlot(object, object)
    def get_selected_motors(self, motor_x, motor_y):
        """
        Slot to receive and set the selected motors.

        Args:
            motor_x (object): The selected motor for the x-axis.
            motor_y (object): The selected motor for the y-axis.
        """
        self.motor_x, self.motor_y = motor_x, motor_y

    @pyqtSlot(list, list)
    def get_available_motors(self, motors_x, motors_y):
        """
        Slot to populate the available motors in the combo boxes and set the index based on the configuration.

        Args:
            motors_x (list): List of available motors for the x-axis.
            motors_y (list): List of available motors for the y-axis.
        """
        self.comboBox_motor_x.addItems(motors_x)
        self.comboBox_motor_y.addItems(motors_y)

        # Set index based on the motor names in the configuration, if available
        selected_motor_x = ""
        selected_motor_y = ""

        if self.selected_motors:
            selected_motor_x = self.selected_motors.get("motor_x", "")
            selected_motor_y = self.selected_motors.get("motor_y", "")

        index_x = self.comboBox_motor_x.findText(selected_motor_x)
        index_y = self.comboBox_motor_y.findText(selected_motor_y)

        if index_x != -1:
            self.comboBox_motor_x.setCurrentIndex(index_x)
        else:
            print(
                f"Warning: Motor '{selected_motor_x}' specified in the config file is not available."
            )
            self.comboBox_motor_x.setCurrentIndex(0)  # Optionally set to first item or any default

        if index_y != -1:
            self.comboBox_motor_y.setCurrentIndex(index_y)
        else:
            print(
                f"Warning: Motor '{selected_motor_y}' specified in the config file is not available."
            )
            self.comboBox_motor_y.setCurrentIndex(0)  # Optionally set to first item or any default

    @pyqtSlot(list, list)
    def update_limits(self, x_limits: list, y_limits: list) -> None:
        """
        Slot to update the limits for x and y motors.

        Args:
            x_limits (list): List containing the lower and upper limits for the x-axis motor.
            y_limits (list): List containing the lower and upper limits for the y-axis motor.
        """
        self.limit_x = x_limits
        self.limit_y = y_limits
        self.spinBox_x_min.setValue(self.limit_x[0])
        self.spinBox_x_max.setValue(self.limit_x[1])
        self.spinBox_y_min.setValue(self.limit_y[0])
        self.spinBox_y_max.setValue(self.limit_y[1])

        for spinBox in (
            self.spinBox_x_min,
            self.spinBox_x_max,
            self.spinBox_y_min,
            self.spinBox_y_max,
        ):
            spinBox.setStyleSheet("")

        # TODO - names can be get from MotorController
        self.label_Y_max.setText(f"+ ({self.motor_y.name})")
        self.label_Y_min.setText(f"- ({self.motor_y.name})")
        self.label_X_max.setText(f"+ ({self.motor_x.name})")
        self.label_X_min.setText(f"- ({self.motor_x.name})")

        self.init_motor_map()  # reinitialize the map with the new limits

    @pyqtSlot()
    def enable_motor_control(self):
        self.motorControl.setEnabled(True)

    def enable_motor_controls(self, disable: bool) -> None:
        self.motorControl.setEnabled(disable)
        self.motorSelection.setEnabled(disable)

        # Disable or enable all controls within the motorControl_absolute group box
        for widget in self.motorControl_absolute.findChildren(QtWidgets.QWidget):
            widget.setEnabled(disable)

        # Enable the pushButton_stop if the motor is moving
        self.pushButton_stop.setEnabled(True)

    def move_motor_absolute(self, x: float, y: float) -> None:
        self.enable_motor_controls(False)
        target_coordinates = (x, y)
        self.motor_thread.move_to_coordinates(target_coordinates)
        if self.checkBox_save_with_go.isChecked():
            self.save_absolute_coordinates()

    def move_motor_relative(self, motor, axis: str, direction: int) -> None:
        self.enable_motor_controls(False)
        if axis == "x":
            step = direction * self.spinBox_step_x.value()
        elif axis == "y":
            step = direction * self.spinBox_step_y.value()
        self.motor_thread.move_relative(motor, step)

    def update_plot_setting(self, max_points, num_dim_points, scatter_size):
        self.max_points = max_points
        self.num_dim_points = num_dim_points
        self.scatter_size = scatter_size

        for spinBox in (
            self.spinBox_max_points,
            self.spinBox_num_dim_points,
            self.spinBox_scatter_size,
        ):
            spinBox.setStyleSheet("")

    def set_from_config(self) -> None:
        """Set the values from the config file to the UI elements"""

        self.spinBox_max_points.setValue(self.max_points)
        self.spinBox_num_dim_points.setValue(self.num_dim_points)
        self.spinBox_scatter_size.setValue(self.scatter_size)
        self.spinBox_precision.setValue(self.precision)
        self.update_precision(self.precision)

    def init_ui_plot_elements(self) -> None:
        """Initialize the plot elements"""
        self.label_coorditanes = self.glw.addLabel(f"Motor position: (X, Y)", row=0, col=0)
        self.plot_map = self.glw.addPlot(row=1, col=0)
        self.limit_map = pg.ImageItem()
        self.plot_map.addItem(self.limit_map)
        self.motor_map = pg.ScatterPlotItem(
            size=self.scatter_size, pen=pg.mkPen(None), brush=pg.mkBrush(255, 255, 255, 255)
        )
        self.motor_map.setZValue(0)

        self.saved_motor_positions = np.array([])  # to track saved motor positions
        self.saved_point_visibility = []  # to track visibility of saved motor positions

        self.saved_motor_map = pg.ScatterPlotItem(
            size=self.scatter_size, pen=pg.mkPen(None), brush=pg.mkBrush(255, 0, 0, 255)
        )
        self.saved_motor_map.setZValue(1)  # for saved motor positions

        self.plot_map.addItem(self.motor_map)
        self.plot_map.addItem(self.saved_motor_map)
        self.plot_map.showGrid(x=True, y=True)

    def init_ui_motor_control(self) -> None:
        """Initialize the motor control elements"""

        # Connect CheckBox stateChanged signal to sync function
        self.checkBox_same_xy.stateChanged.connect(
            lambda: self.sync_step_sizes(self.spinBox_step_x, self.spinBox_step_y)
        )

        self.toolButton_right.clicked.connect(
            lambda: self.move_motor_relative(self.motor_x, "x", 1)
        )
        self.toolButton_left.clicked.connect(
            lambda: self.move_motor_relative(self.motor_x, "x", -1)
        )
        self.toolButton_up.clicked.connect(lambda: self.move_motor_relative(self.motor_y, "y", 1))
        self.toolButton_down.clicked.connect(
            lambda: self.move_motor_relative(self.motor_y, "y", -1)
        )

        # Switch between key shortcuts active
        self.checkBox_enableArrows.stateChanged.connect(self.update_arrow_key_shortcuts)
        self.update_arrow_key_shortcuts()

        # Move to absolute coordinates
        self.pushButton_go_absolute.clicked.connect(
            lambda: self.move_motor_absolute(
                self.spinBox_absolute_x.value(), self.spinBox_absolute_y.value()
            )
        )

        self.pushButton_set.clicked.connect(self.save_absolute_coordinates)
        self.pushButton_save.clicked.connect(self.save_current_coordinates)
        self.pushButton_stop.clicked.connect(self.motor_thread.stop_movement)

        # Enable/Disable GUI
        self.motor_thread.move_finished.connect(lambda: self.enable_motor_controls(True))

        # Precision update
        self.spinBox_precision.valueChanged.connect(lambda x: self.update_precision(x))

    def init_ui_motor_configs(self) -> None:
        """Limit and plot spinBoxes"""

        # SpinBoxes change color to yellow before updated, limits are updated with update button
        self.spinBox_x_min.valueChanged.connect(lambda: self.param_changed(self.spinBox_x_min))
        self.spinBox_x_max.valueChanged.connect(lambda: self.param_changed(self.spinBox_x_max))
        self.spinBox_y_min.valueChanged.connect(lambda: self.param_changed(self.spinBox_y_min))
        self.spinBox_y_max.valueChanged.connect(lambda: self.param_changed(self.spinBox_y_max))

        # SpinBoxes - Max Points and N Dim Points
        self.spinBox_max_points.valueChanged.connect(
            lambda: self.param_changed(self.spinBox_max_points)
        )
        self.spinBox_num_dim_points.valueChanged.connect(
            lambda: self.param_changed(self.spinBox_num_dim_points)
        )
        self.spinBox_scatter_size.valueChanged.connect(
            lambda: self.param_changed(self.spinBox_scatter_size)
        )

        # Limit Update
        self.pushButton_updateLimits.clicked.connect(
            lambda: self.update_all_motor_limits(
                x_limit=[self.spinBox_x_min.value(), self.spinBox_x_max.value()],
                y_limit=[self.spinBox_y_min.value(), self.spinBox_y_max.value()],
            )
        )

        # Plot Update
        self.pushButton_update_config.clicked.connect(
            lambda: self.update_plot_setting(
                max_points=self.spinBox_max_points.value(),
                num_dim_points=self.spinBox_num_dim_points.value(),
                scatter_size=self.spinBox_scatter_size.value(),
            )
        )

        self.pushButton_enableGUI.clicked.connect(lambda: self.enable_motor_controls(True))

    def init_ui_motor_connections(self) -> None:
        # Signal from motor thread to update coordinates
        self.motor_thread.coordinates_updated.connect(
            lambda x, y: self.update_image_map(round(x, self.precision), round(y, self.precision))
        )

        # Motor connections button
        self.pushButton_connecMotors.clicked.connect(
            lambda: self.connect_motor(
                self.comboBox_motor_x.currentText(), self.comboBox_motor_y.currentText()
            )
        )

        # Check if there are any motors connected
        if self.motor_x or self.motor_y is None:
            self.motorControl.setEnabled(False)
            self.motorControl_absolute.setEnabled(False)
            self.tabWidget_tables.setTabEnabled(1, False)

    def init_keyboard_shortcuts(self) -> None:
        """Initialize the keyboard shortcuts"""

        # Delete table entry
        delete_shortcut = QShortcut(QKeySequence("Delete"), self)
        backspace_shortcut = QShortcut(QKeySequence("Backspace"), self)
        delete_shortcut.activated.connect(self.delete_selected_row)
        backspace_shortcut.activated.connect(self.delete_selected_row)

        # Increase/decrease step size for X motor
        increase_x_shortcut = QShortcut(QKeySequence("Ctrl+A"), self)
        decrease_x_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        increase_x_shortcut.activated.connect(lambda: self.change_step_size(self.spinBox_step_x, 2))
        decrease_x_shortcut.activated.connect(
            lambda: self.change_step_size(self.spinBox_step_x, 0.5)
        )

        # Increase/decrease step size for Y motor
        increase_y_shortcut = QShortcut(QKeySequence("Alt+A"), self)
        decrease_y_shortcut = QShortcut(QKeySequence("Alt+Z"), self)
        increase_y_shortcut.activated.connect(lambda: self.change_step_size(self.spinBox_step_y, 2))
        decrease_y_shortcut.activated.connect(
            lambda: self.change_step_size(self.spinBox_step_y, 0.5)
        )

        # Go absolute button
        self.pushButton_go_absolute.setShortcut("Ctrl+G")
        self.pushButton_go_absolute.setToolTip("Ctrl+G")

        # Set absolute coordinates
        self.pushButton_set.setShortcut("Ctrl+D")
        self.pushButton_set.setToolTip("Ctrl+D")

        # Save Current coordinates
        self.pushButton_save.setShortcut("Ctrl+S")
        self.pushButton_save.setToolTip("Ctrl+S")

        # Stop Button
        self.pushButton_stop.setShortcut("Ctrl+X")
        self.pushButton_stop.setToolTip("Ctrl+X")

    def init_ui_table(self) -> None:
        """Initialize the table validators for x and y coordinates and table signals"""
        # Validators
        self.double_delegate = DoubleValidationDelegate(self.tableWidget_coordinates)
        self.tableWidget_coordinates.setItemDelegateForColumn(2, self.double_delegate)
        self.tableWidget_coordinates.setItemDelegateForColumn(3, self.double_delegate)

        # Signals
        self.tableWidget_coordinates.itemChanged.connect(self.update_saved_coordinates)

    def init_ui(self) -> None:
        """Setup all ui elements"""

        self.set_from_config()  # Set default parameters
        self.init_ui_plot_elements()  # 2D Plot
        self.init_ui_motor_control()  # Motor Controls
        self.init_ui_motor_configs()  # Motor Configs
        self.init_ui_motor_connections()  # Motor Connections
        self.init_keyboard_shortcuts()  # Keyboard Shortcuts
        self.init_ui_table()  # Table validators for x and y coordinates

    def init_motor_map(self):
        # Get motor limits
        limit_x_min, limit_x_max = self.motor_thread.get_motor_limits(self.motor_x)
        limit_y_min, limit_y_max = self.motor_thread.get_motor_limits(self.motor_y)

        self.offset_x = limit_x_min
        self.offset_y = limit_y_min

        # Define the size of the image map based on the motor's limits
        map_width = limit_x_max - limit_x_min + 1
        map_height = limit_y_max - limit_y_min + 1

        # Create an empty image map
        self.background_value = 25
        self.limit_map_data = np.full(
            (map_width, map_height), self.background_value, dtype=np.float32
        )
        self.limit_map.setImage(self.limit_map_data)

        # Set the initial position on the map
        init_pos = self.motor_thread.retrieve_coordinates()
        self.motor_positions = np.array([init_pos])
        self.brushes = [pg.mkBrush(255, 255, 255, 255)]

        self.motor_map.setData(pos=self.motor_positions, brush=self.brushes)

        # Translate and scale the image item to match the motor coordinates
        self.tr = QtGui.QTransform()
        self.tr.translate(limit_x_min, limit_y_min)
        self.limit_map.setTransform(self.tr)

        if hasattr(self, "highlight_V") and hasattr(self, "highlight_H"):
            self.plot_map.removeItem(self.highlight_V)
            self.plot_map.removeItem(self.highlight_H)

        # Crosshair to highlight the current position
        self.highlight_V = pg.InfiniteLine(
            angle=90, movable=False, pen=pg.mkPen(color="r", width=1, style=QtCore.Qt.DashLine)
        )
        self.highlight_H = pg.InfiniteLine(
            angle=0, movable=False, pen=pg.mkPen(color="r", width=1, style=QtCore.Qt.DashLine)
        )

        self.plot_map.addItem(self.highlight_V)
        self.plot_map.addItem(self.highlight_H)

        self.highlight_V.setPos(init_pos[0])
        self.highlight_H.setPos(init_pos[1])

    def update_image_map(self, x, y):
        # Update label
        self.label_coorditanes.setText(f"Motor position: ({x}, {y})")

        # Add new point with full brightness
        new_pos = np.array([x, y])
        self.motor_positions = np.vstack((self.motor_positions, new_pos))

        # If the number of points exceeds max_points, delete the oldest points
        if len(self.motor_positions) > self.max_points:
            self.motor_positions = self.motor_positions[-self.max_points :]

        # Determine brushes based on position in the array
        self.brushes = [pg.mkBrush(50, 50, 50, 255)] * len(self.motor_positions)

        # Calculate the decrement step based on self.num_dim_points
        decrement_step = (255 - 50) / self.num_dim_points

        for i in range(1, min(self.num_dim_points + 1, len(self.motor_positions) + 1)):
            brightness = max(60, 255 - decrement_step * (i - 1))
            self.brushes[-i] = pg.mkBrush(brightness, brightness, brightness, 255)

        self.brushes[-1] = pg.mkBrush(255, 255, 255, 255)  # Newest point is always full brightness

        self.motor_map.setData(pos=self.motor_positions, brush=self.brushes, size=self.scatter_size)

        # Set Highlight
        self.highlight_V.setPos(x)
        self.highlight_H.setPos(y)

    def update_all_motor_limits(self, x_limit: list = None, y_limit: list = None) -> None:
        self.motor_thread.update_all_motor_limits(x_limit=x_limit, y_limit=y_limit)

    def update_arrow_key_shortcuts(self):
        if self.checkBox_enableArrows.isChecked():
            # Set the arrow key shortcuts for motor movement
            self.toolButton_right.setShortcut(Qt.Key_Right)
            self.toolButton_left.setShortcut(Qt.Key_Left)
            self.toolButton_up.setShortcut(Qt.Key_Up)
            self.toolButton_down.setShortcut(Qt.Key_Down)
        else:
            # Clear the shortcuts
            self.toolButton_right.setShortcut("")
            self.toolButton_left.setShortcut("")
            self.toolButton_up.setShortcut("")
            self.toolButton_down.setShortcut("")

    def generate_table_coordinate(
        self, table: QtWidgets.QTableWidget, coordinates: tuple, tag: str = None, precision: int = 0
    ) -> None:
        current_row_count = table.rowCount()
        table.setRowCount(current_row_count + 1)

        # Create QDoubleValidator
        validator = QDoubleValidator()
        validator.setDecimals(precision)  # TODO not sure if necessary

        checkBox = QtWidgets.QCheckBox()
        checkBox.setChecked(True)
        button = QtWidgets.QPushButton("Go")

        checkBox.stateChanged.connect(
            lambda state, widget=checkBox: self.toggle_point_visibility(state, widget)
        )

        table.setItem(current_row_count, 4, QtWidgets.QTableWidgetItem(str(tag)))
        table.setCellWidget(current_row_count, 1, checkBox)

        # Apply validator to x and y coordinate QTableWidgetItem
        item_x = QtWidgets.QTableWidgetItem(str(f"{coordinates[0]:.{precision}f}"))
        item_y = QtWidgets.QTableWidgetItem(str(f"{coordinates[1]:.{precision}f}"))
        item_x.setFlags(item_x.flags() | Qt.ItemIsEditable)
        item_y.setFlags(item_y.flags() | Qt.ItemIsEditable)

        table.setItem(
            current_row_count, 2, QtWidgets.QTableWidgetItem(str(f"{coordinates[0]:.{precision}f}"))
        )
        table.setItem(
            current_row_count, 3, QtWidgets.QTableWidgetItem(str(f"{coordinates[1]:.{precision}f}"))
        )

        table.setCellWidget(current_row_count, 0, button)

        button.clicked.connect(partial(self.move_to_row_coordinates, table, current_row_count))

        brushes = [
            pg.mkBrush(255, 165, 0, 255) if visible else pg.mkBrush(255, 165, 0, 0)
            for visible in self.saved_point_visibility
        ]

        # Adding extra columns
        if extra_columns:
            col_index = 5  # Starting index for extra columns
            table.setColumnCount(col_index + len(self.extra_columns))
            for col_dict in self.extra_columns:
                for col_name, default_value in col_dict.items():
                    if current_row_count == 0:
                        item = QtWidgets.QTableWidgetItem(str(default_value))
                    else:
                        item = QtWidgets.QTableWidgetItem(
                            table.item(current_row_count - 1, col_index).text()
                        )

                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                    table.setItem(current_row_count, col_index, item)

                    if current_row_count == 0:
                        table.setHorizontalHeaderItem(
                            col_index, QtWidgets.QTableWidgetItem(col_name)
                        )

                    col_index += 1

        self.saved_motor_map.setData(pos=self.saved_motor_positions, brush=brushes)

        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignCenter)

        table.resizeColumnsToContents()

    def move_to_row_coordinates(self, table, row):
        x = float(table.item(row, 2).text())
        y = float(table.item(row, 3).text())
        self.move_motor_absolute(x, y)

    def toggle_point_visibility(self, state, checkBox_widget):
        parent = checkBox_widget.parent()
        while not isinstance(parent, QTableWidget):
            parent = parent.parent()

        table = parent

        pos = checkBox_widget.pos()
        item = table.indexAt(pos)
        row_index = item.row()

        # print(f"Row {row_index} visibility changed to {state == Qt.Checked}")

        self.saved_point_visibility[row_index] = state == Qt.Checked

        # Generate brushes based on visibility state
        brushes = [
            pg.mkBrush(255, 165, 0, 255) if visible else pg.mkBrush(255, 165, 0, 0)
            for visible in self.saved_point_visibility
        ]

        # brushed_rgb = [brush.color().getRgb() for brush in brushes]

        # print(f"Poinst: {self.saved_motor_positions}")
        # print(f"Brushes: {brushed_rgb}")

        self.saved_motor_map.setData(pos=self.saved_motor_positions, brush=brushes)

    def update_saved_coordinates(self):
        """
        Update the saved coordinates and replot them.
        """
        rows = self.tableWidget_coordinates.rowCount()
        # Initialize an empty array to hold new coordinates
        new_saved_positions = np.empty((0, 2))
        new_visibility = []

        for row in range(rows):
            x = (
                float(self.tableWidget_coordinates.item(row, 2).text())
                if self.tableWidget_coordinates.item(row, 2) is not None
                else None
            )
            y = (
                float(self.tableWidget_coordinates.item(row, 3).text())
                if self.tableWidget_coordinates.item(row, 3) is not None
                else None
            )

            # Only add the point if both x and y are not None
            if x is not None and y is not None:
                new_saved_positions = np.vstack((new_saved_positions, [x, y]))
                checkbox = self.tableWidget_coordinates.cellWidget(row, 1)
                new_visibility.append(checkbox.isChecked())

        # Update saved positions and visibility
        self.saved_motor_positions = new_saved_positions
        self.saved_point_visibility = new_visibility

        # Replot saved positions based on new data
        brushes = [
            pg.mkBrush(255, 165, 0, 255) if visible else pg.mkBrush(255, 165, 0, 0)
            for visible in self.saved_point_visibility
        ]
        self.saved_motor_map.setData(pos=self.saved_motor_positions, brush=brushes)

    def delete_selected_row(self):
        selected_rows = self.tableWidget_coordinates.selectionModel().selectedRows()
        rows_to_delete = [row.row() for row in selected_rows]
        rows_to_delete.sort(reverse=True)  # Sort in descending order

        for row_index in rows_to_delete:
            self.saved_motor_positions = np.delete(self.saved_motor_positions, row_index, axis=0)
            del self.saved_point_visibility[row_index]

            # Update the plot
            brushes = [
                pg.mkBrush(255, 165, 0, 255) if visible else pg.mkBrush(255, 165, 0, 0)
                for visible in self.saved_point_visibility
            ]
            self.saved_motor_map.setData(pos=self.saved_motor_positions, brush=brushes)

            # Remove the row from the table
            self.tableWidget_coordinates.removeRow(row_index)

        # Update the 'Go' buttons
        for row in range(self.tableWidget_coordinates.rowCount()):
            button = self.tableWidget_coordinates.cellWidget(row, 0)
            button.clicked.disconnect()
            button.clicked.connect(
                partial(self.move_to_row_coordinates, self.tableWidget_coordinates, row)
            )

    def save_absolute_coordinates(self):
        self.generate_table_coordinate(
            self.tableWidget_coordinates,
            (self.spinBox_absolute_x.value(), self.spinBox_absolute_y.value()),
            tag=f"Pos {self.tag_N}",
            precision=self.precision,
        )

        self.tag_N += 1

    def save_current_coordinates(self):
        self.generate_table_coordinate(
            self.tableWidget_coordinates,
            self.motor_thread.retrieve_coordinates(),
            tag=f"Cur {self.tag_N}",
            precision=self.precision,
        )

        self.tag_N += 1

    def update_precision(self, precision: int):
        self.precision = precision
        self.spinBox_step_x.setDecimals(self.precision)
        self.spinBox_step_y.setDecimals(self.precision)
        self.spinBox_absolute_x.setDecimals(self.precision)
        self.spinBox_absolute_y.setDecimals(self.precision)

    def change_step_size(self, spinBox: QtWidgets.QDoubleSpinBox, factor: float) -> None:
        old_step = spinBox.value()
        new_step = old_step * factor
        spinBox.setValue(new_step)

    def sync_step_sizes(self, spinBox1, spinBox2):
        if self.checkBox_same_xy.isChecked():
            value = spinBox1.value()
            spinBox2.setValue(value)

    @staticmethod
    def param_changed(ui_element):
        ui_element.setStyleSheet("background-color: #FFA700;")


class MotorActions(Enum):
    MOVE_TO_COORDINATES = "move_to_coordinates"
    MOVE_RELATIVE = "move_relative"


class MotorControl(QThread):
    """
    QThread subclass for controlling motor actions asynchronously.

    Attributes:
        coordinates_updated (pyqtSignal): Signal to emit current coordinates.
        limits_retrieved (pyqtSignal): Signal to emit current limits.
        move_finished (pyqtSignal): Signal to emit when the move is finished.
        motors_loaded (pyqtSignal): Signal to emit when the motors are loaded.
        motors_selected (pyqtSignal): Signal to emit when the motors are selected.
    """

    coordinates_updated = pyqtSignal(float, float)  # Signal to emit current coordinates
    limits_retrieved = pyqtSignal(list, list)  # Signal to emit current limits
    move_finished = pyqtSignal()  # Signal to emit when the move is finished
    motors_loaded = pyqtSignal(list, list)  # Signal to emit when the motors are loaded
    motors_selected = pyqtSignal(object, object)  # Signal to emit when the motors are selected
    # progress_updated = pyqtSignal(int)  #TODO  Signal to emit progress percentage

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(parent)

        self.action = None
        self._initialize_motor()

    def connect_motors(self, motor_x_name: str, motor_y_name: str) -> None:
        """
        Connect to the specified motors by their names.

        Args:
            motor_x_name (str): The name of the motor for the x-axis.
            motor_y_name (str): The name of the motor for the y-axis.
        """

        self.motor_x, self.motor_y = (
            dev[motor_x_name],
            dev[motor_y_name],
        )

        (self.current_x, self.current_y) = self.get_coordinates()

        if self.motors_consumer is not None:
            self.motors_consumer.shutdown()

        self.motors_consumer = client.connector.consumer(
            topics=[
                MessageEndpoints.device_readback(self.motor_x.name),
                MessageEndpoints.device_readback(self.motor_y.name),
            ],
            cb=self._device_status_callback_motors,
            parent=self,
        )

        self.motors_consumer.start()

        self.motors_selected.emit(self.motor_x, self.motor_y)

    def get_all_motors(self) -> list:
        """
        Retrieve a list of all available motors.

        Returns:
            list: List of all available motors.
        """
        all_motors = (
            client.device_manager.devices.enabled_devices
        )  # .acquisition_group("motor") #TODO remove motor group?
        return all_motors

    def get_all_motors_names(self) -> list:
        all_motors = client.device_manager.devices.enabled_devices  # .acquisition_group("motor")
        all_motors_names = [motor.name for motor in all_motors]
        return all_motors_names

    def retrieve_all_motors(self):
        self.all_motors = self.get_all_motors()
        self.all_motors_names = self.get_all_motors_names()
        self.motors_loaded.emit(self.all_motors_names, self.all_motors_names)

        return self.all_motors, self.all_motors_names

    def get_coordinates(self) -> tuple:
        """Get current motor position"""
        x = self.motor_x.read(cached=True)["value"]
        y = self.motor_y.read(cached=True)["value"]
        return x, y

    def retrieve_coordinates(self) -> tuple:
        """Get current motor position for export to main app"""
        return self.current_x, self.current_y

    def get_motor_limits(self, motor) -> list:
        """
        Retrieve the limits for a specific motor.

        Args:
            motor (object): Motor object.

        Returns:
            tuple: Lower and upper limit for the motor.
        """
        try:
            return motor.limits
        except AttributeError:
            # If the motor doesn't have a 'limits' attribute, return a default value or raise a custom exception
            print(f"The device {motor} does not have defined limits.")
            return None

    def retrieve_motor_limits(self, motor_x, motor_y):
        limit_x = self.get_motor_limits(motor_x)
        limit_y = self.get_motor_limits(motor_y)
        self.limits_retrieved.emit(limit_x, limit_y)

    def update_motor_limits(self, motor, low_limit=None, high_limit=None) -> None:
        current_low_limit, current_high_limit = self.get_motor_limits(motor)

        # Check if the low limit has changed and is not None
        if low_limit is not None and low_limit != current_low_limit:
            motor.low_limit = low_limit

        # Check if the high limit has changed and is not None
        if high_limit is not None and high_limit != current_high_limit:
            motor.high_limit = high_limit

    def update_all_motor_limits(self, x_limit: list = None, y_limit: list = None) -> None:
        current_position = self.get_coordinates()

        if x_limit is not None:
            if current_position[0] < x_limit[0] or current_position[0] > x_limit[1]:
                raise ValueError("Current motor position is outside the new limits (X)")
            else:
                self.update_motor_limits(self.motor_x, low_limit=x_limit[0], high_limit=x_limit[1])

        if y_limit is not None:
            if current_position[1] < y_limit[0] or current_position[1] > y_limit[1]:
                raise ValueError("Current motor position is outside the new limits (Y)")
            else:
                self.update_motor_limits(self.motor_y, low_limit=y_limit[0], high_limit=y_limit[1])

        self.retrieve_motor_limits(self.motor_x, self.motor_y)

    def move_to_coordinates(self, target_coordinates: tuple):
        self.action = MotorActions.MOVE_TO_COORDINATES
        self.target_coordinates = target_coordinates
        self.start()

    def move_relative(self, motor, value: float):
        self.action = MotorActions.MOVE_RELATIVE
        self.motor = motor
        self.value = value
        self.start()

    def run(self):
        if self.action == MotorActions.MOVE_TO_COORDINATES:
            self._move_motor_coordinate()
        elif self.action == MotorActions.MOVE_RELATIVE:
            self._move_motor_relative(self.motor, self.value)

    def set_target_coordinates(self, target_coordinates: tuple) -> None:
        self.target_coordinates = target_coordinates

    def _initialize_motor(self) -> None:
        self.motor_x, self.motor_y = None, None
        self.current_x, self.current_y = None, None

        self.motors_consumer = None

        # Get all available motors in the client
        self.all_motors = self.get_all_motors()
        self.all_motors_names = self.get_all_motors_names()
        self.retrieve_all_motors()  # send motor list to GUI

        self.target_coordinates = None

    def _move_motor_coordinate(self) -> None:
        """Move the motor to the specified coordinates"""
        status = scans.mv(
            self.motor_x,
            self.target_coordinates[0],
            self.motor_y,
            self.target_coordinates[1],
            relative=False,
        )

        status.wait()
        self.move_finished.emit()

    def _move_motor_relative(self, motor, value: float) -> None:
        status = scans.mv(motor, value, relative=True)

        status.wait()
        self.move_finished.emit()

    def stop_movement(self):
        queue.request_scan_abortion()
        queue.request_queue_reset()

    @staticmethod
    def _device_status_callback_motors(msg, *, parent, **_kwargs) -> None:
        deviceMSG = BECMessage.DeviceMessage.loads(msg.value)
        if parent.motor_x.name in deviceMSG.content["signals"]:
            parent.current_x = deviceMSG.content["signals"][parent.motor_x.name]["value"]
        elif parent.motor_y.name in deviceMSG.content["signals"]:
            parent.current_y = deviceMSG.content["signals"][parent.motor_y.name]["value"]
        parent.coordinates_updated.emit(parent.current_x, parent.current_y)


if __name__ == "__main__":
    import yaml
    import argparse

    from bec_lib import BECClient

    from bec_lib.core import ServiceConfig

    parser = argparse.ArgumentParser(description="Motor App")

    parser.add_argument(
        "--config", "-c", help="Path to the .yaml configuration file", default="config_example.yaml"
    )
    parser.add_argument(
        "--bec-config", "-b", help="Path to the BEC .yaml configuration file", default=None
    )

    args = parser.parse_args()

    try:
        with open(args.config, "r") as file:
            config = yaml.safe_load(file)

            selected_motors = config.get("selected_motors", {})
            plot_motors = config.get("plot_motors", {})
            extra_columns = config.get("plot_motors", {}).get("extra_columns", [])

    except FileNotFoundError:
        print(f"The file {args.config} was not found.")
        exit(1)
    except Exception as e:
        print(f"An error occurred while loading the config file: {e}")
        exit(1)

    client = BECClient()

    if args.bec_config:
        client.initialize(config=ServiceConfig(config_path=args.bec_config))

    client.start()
    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    app = QApplication([])
    MotorApp = MotorApp(selected_motors=selected_motors, plot_motors=plot_motors)
    window = MotorApp
    window.show()
    app.exec_()
