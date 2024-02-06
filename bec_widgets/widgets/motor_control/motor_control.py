# pylint: disable = no-name-in-module,missing-module-docstring
import os
from enum import Enum

import qdarktheme
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import QPushButton, QTableWidgetItem, QCheckBox, QLineEdit

from qtpy import uic
from qtpy.QtCore import QThread, Slot as pyqtSlot
from qtpy.QtCore import Signal as pyqtSignal, Qt
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import (
    QApplication,
    QHeaderView,
    QWidget,
    QSpinBox,
    QDoubleSpinBox,
    QShortcut,
    QVBoxLayout,
    QTableWidget,
)

from qtpy.QtWidgets import QApplication, QMessageBox
from bec_lib.alarm_handler import AlarmBase
from bec_lib.device import Positioner
from bec_widgets.utils.bec_dispatcher import BECDispatcher

CONFIG_DEFAULT = {
    "motor_control": {
        "motor_x": "samx",
        "motor_y": "samy",
        "step_size_x": 3,
        "step_size_y": 50,
        "precision": 4,
        "step_x_y_same": False,
        "move_with_arrows": False,
    }
}


class MotorControlWidget(QWidget):
    """Base class for motor control widgets."""

    def __init__(self, parent=None, client=None, motor_thread=None, config=None):
        super().__init__(parent)
        self.client = client
        self.motor_thread = motor_thread
        self.config = config

        if not self.client:
            bec_dispatcher = BECDispatcher()
            self.client = bec_dispatcher.client

        if not self.motor_thread:
            self.motor_thread = MotorThread(client=self.client)

        self._load_ui()

        if self.config is None:
            print(f"No initial config found for {self.__class__.__name__}")
            self._init_ui()
        else:
            self.on_config_update(self.config)

    def _load_ui(self):
        """Load the UI from the .ui file."""

    def _init_ui(self):
        """Initialize the UI components specific to the widget."""

    @pyqtSlot(dict)
    def on_config_update(self, config):
        """Handle configuration updates."""
        self.config = config
        self._init_ui()


class MotorControlSelection(MotorControlWidget):
    """
    Widget for selecting the motors to control.

    Signals:
        selected_motors_signal (pyqtSignal): Signal to emit the selected motors.
    Slots:
        get_available_motors (pyqtSlot): Slot to populate the available motors in the combo boxes and set the index based on the configuration.
        select_motor (pyqtSlot): Slot to emit the selected motors.
        enable_motor_controls (pyqtSlot): Slot to enable/disable the motor controls GUI.
    """

    selected_motors_signal = pyqtSignal(str, str)

    def _load_ui(self):
        """Load the UI from the .ui file."""
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "motor_control_selection.ui"), self)

    def _init_ui(self):
        """Initialize the UI."""
        # Lock GUI while motors are moving
        self.motor_thread.lock_gui.connect(self.enable_motor_controls)

        self.pushButton_connecMotors.clicked.connect(self.select_motor)
        self.get_available_motors()

        # Connect change signals to change color
        self.comboBox_motor_x.currentIndexChanged.connect(
            lambda: self.set_combobox_style(self.comboBox_motor_x, "#ffa700")
        )
        self.comboBox_motor_y.currentIndexChanged.connect(
            lambda: self.set_combobox_style(self.comboBox_motor_y, "#ffa700")
        )

    @pyqtSlot(dict)
    def on_config_update(self, config: dict) -> None:
        """
        Update config dict
        Args:
            config(dict): New config dict
        """
        self.config = config

        # Get motor names
        self.motor_x, self.motor_y = (
            self.config["motor_control"]["motor_x"],
            self.config["motor_control"]["motor_y"],
        )

        self._init_ui()

    @pyqtSlot(bool)
    def enable_motor_controls(self, enable: bool) -> None:
        """
        Enable or disable the motor controls.
        Args:
            enable(bool): True to enable, False to disable.
        """
        self.motorSelection.setEnabled(enable)

    def get_available_motors(self):
        """
        Slot to populate the available motors in the combo boxes and set the index based on the configuration.
        """
        # Get all available motors
        self.motor_list = self.motor_thread.get_all_motors_names()

        # Populate the combo boxes
        self.comboBox_motor_x.addItems(self.motor_list)
        self.comboBox_motor_y.addItems(self.motor_list)

        # Set the index based on the config if provided
        if self.config:
            index_x = self.comboBox_motor_x.findText(self.motor_x)
            index_y = self.comboBox_motor_y.findText(self.motor_y)
            self.comboBox_motor_x.setCurrentIndex(index_x if index_x != -1 else 0)
            self.comboBox_motor_y.setCurrentIndex(index_y if index_y != -1 else 0)

    def set_combobox_style(self, combobox, color):
        """Set the background color of the combobox."""
        combobox.setStyleSheet(f"QComboBox {{ background-color: {color}; }}")

    def select_motor(self):
        """Emit the selected motors"""
        motor_x = self.comboBox_motor_x.currentText()
        motor_y = self.comboBox_motor_y.currentText()

        # Reset the combobox color to normal after selection
        self.set_combobox_style(self.comboBox_motor_x, "")
        self.set_combobox_style(self.comboBox_motor_y, "")

        self.selected_motors_signal.emit(motor_x, motor_y)


class MotorControlAbsolute(MotorControlWidget):
    """
    Widget for controlling the motors to absolute coordinates.

    Signals:
        coordinates_signal (pyqtSignal): Signal to emit the coordinates.
    Slots:
        change_motors (pyqtSlot): Slot to change the active motors.
        enable_motor_controls (pyqtSlot): Slot to enable/disable the motor controls.
    """

    coordinates_signal = pyqtSignal(tuple)

    def _load_ui(self):
        """Load the UI from the .ui file."""
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "motor_control_absolute.ui"), self)

    def _init_ui(self):
        """Initialize the UI."""

        # Check if there are any motors connected
        if self.motor_x is None or self.motor_y is None:
            self.motorControl_absolute.setEnabled(False)
            return

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
        self.motor_thread.lock_gui.connect(self.enable_motor_controls)

        # Error messages
        self.motor_thread.motor_error.connect(
            lambda error: MotorControlErrors.display_error_message(error)
        )

    @pyqtSlot(dict)
    def on_config_update(self, config: dict) -> None:
        """Update config dict"""
        self.config = config

        # Get motor names
        self.motor_x, self.motor_y = (
            self.config["motor_control"]["motor_x"],
            self.config["motor_control"]["motor_y"],
        )

        # Update step precision
        self.precision = self.config["motor_control"]["precision"]

        self._init_ui()

    @pyqtSlot(bool)
    def enable_motor_controls(self, enable: bool) -> None:
        """
        Enable or disable the motor controls.
        Args:
            enable(bool): True to enable, False to disable.
        """

        # Disable or enable all controls within the motorControl_absolute group box
        for widget in self.motorControl_absolute.findChildren(QWidget):
            widget.setEnabled(enable)

        # Enable the pushButton_stop if the motor is moving
        self.pushButton_stop.setEnabled(True)

    @pyqtSlot(str, str)
    def change_motors(self, motor_x: str, motor_y: str):
        """
        Change the active motors and update config.
        Can be connected to the selected_motors_signal from MotorControlSelection.
        Args:
            motor_x(str): New motor X to be controlled.
            motor_y(str): New motor Y to be controlled.
        """
        self.motor_x = motor_x
        self.motor_y = motor_y
        self.config["motor_control"]["motor_x"] = motor_x
        self.config["motor_control"]["motor_y"] = motor_y

    def move_motor_absolute(self, x: float, y: float) -> None:
        """
        Move the motor to the target coordinates.
        Args:
            x(float): Target x coordinate.
            y(float): Target y coordinate.
        """
        # self._enable_motor_controls(False)
        target_coordinates = (x, y)
        self.motor_thread.move_absolute(self.motor_x, self.motor_y, target_coordinates)
        if self.checkBox_save_with_go.isChecked():
            self.save_absolute_coordinates()

    def _init_keyboard_shortcuts(self):
        """Initialize the keyboard shortcuts."""
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

    def save_absolute_coordinates(self):
        """Emit the setup coordinates from the spinboxes"""

        x, y = round(self.spinBox_absolute_x.value(), self.precision), round(
            self.spinBox_absolute_y.value(), self.precision
        )
        self.coordinates_signal.emit((x, y))

    def save_current_coordinates(self):
        """Emit the current coordinates from the motor thread"""
        x, y = self.motor_thread.get_coordinates(self.motor_x, self.motor_y)
        self.coordinates_signal.emit((round(x, self.precision), round(y, self.precision)))


class MotorControlRelative(MotorControlWidget):
    """
    Widget for controlling the motors to relative coordinates.

    Signals:
        coordinates_signal (pyqtSignal): Signal to emit the coordinates.
    Slots:
        change_motors (pyqtSlot): Slot to change the active motors.
        enable_motor_controls (pyqtSlot): Slot to enable/disable the motor controls.
    """

    def _load_ui(self):
        """Load the UI from the .ui file."""
        # Loading UI
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "motor_control_relative.ui"), self)

    def _init_ui(self):
        """Initialize the UI."""
        self._init_ui_motor_control()
        self._init_keyboard_shortcuts()

    @pyqtSlot(dict)
    def on_config_update(self, config: dict) -> None:
        """Update config dict"""
        self.config = config

        # Get motor names
        self.motor_x, self.motor_y = (
            self.config["motor_control"]["motor_x"],
            self.config["motor_control"]["motor_y"],
        )

        # Update step precision
        self.precision = self.config["motor_control"]["precision"]
        self.spinBox_precision.setValue(self.precision)

        # Update step sizes
        self.spinBox_step_x.setValue(self.config["motor_control"]["step_size_x"])
        self.spinBox_step_y.setValue(self.config["motor_control"]["step_size_y"])

        # Checkboxes for keyboard shortcuts and x/y step size link
        self.checkBox_same_xy.setChecked(self.config["motor_control"]["step_x_y_same"])
        self.checkBox_enableArrows.setChecked(self.config["motor_control"]["move_with_arrows"])

        self._init_ui()

    def _init_ui_motor_control(self) -> None:
        """Initialize the motor control elements"""

        # Connect checkbox and spinBoxes
        self.checkBox_same_xy.stateChanged.connect(self._sync_step_sizes)
        self.spinBox_step_x.valueChanged.connect(self._update_step_size_x)
        self.spinBox_step_y.valueChanged.connect(self._update_step_size_y)

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
        self.checkBox_enableArrows.stateChanged.connect(self._update_arrow_key_shortcuts)
        self._update_arrow_key_shortcuts()

        # Enable/Disable GUI
        self.motor_thread.lock_gui.connect(self.enable_motor_controls)

        # Precision update
        self.spinBox_precision.valueChanged.connect(lambda x: self._update_precision(x))

        # Error messages
        self.motor_thread.motor_error.connect(
            lambda error: MotorControlErrors.display_error_message(error)
        )

        # Stop Button
        self.pushButton_stop.clicked.connect(self.motor_thread.stop_movement)

    def _init_keyboard_shortcuts(self) -> None:
        """Initialize the keyboard shortcuts"""

        # Increase/decrease step size for X motor
        increase_x_shortcut = QShortcut(QKeySequence("Ctrl+A"), self)
        decrease_x_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        increase_x_shortcut.activated.connect(
            lambda: self._change_step_size(self.spinBox_step_x, 2)
        )
        decrease_x_shortcut.activated.connect(
            lambda: self._change_step_size(self.spinBox_step_x, 0.5)
        )
        self.spinBox_step_x.setToolTip("Increase step size: Ctrl+A\nDecrease step size: Ctrl+Z")

        # Increase/decrease step size for Y motor
        increase_y_shortcut = QShortcut(QKeySequence("Alt+A"), self)
        decrease_y_shortcut = QShortcut(QKeySequence("Alt+Z"), self)
        increase_y_shortcut.activated.connect(
            lambda: self._change_step_size(self.spinBox_step_y, 2)
        )
        decrease_y_shortcut.activated.connect(
            lambda: self._change_step_size(self.spinBox_step_y, 0.5)
        )
        self.spinBox_step_y.setToolTip("Increase step size: Alt+A\nDecrease step size: Alt+Z")

        # Stop Button
        self.pushButton_stop.setShortcut("Ctrl+X")
        self.pushButton_stop.setToolTip("Ctrl+X")

    def _update_arrow_key_shortcuts(self):
        """Update the arrow key shortcuts based on the checkbox state."""
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

    def _update_precision(self, precision: int):
        """Update the precision of the spinboxes."""
        self.spinBox_step_x.setDecimals(precision)
        self.spinBox_step_y.setDecimals(precision)

    def _change_step_size(self, spinBox: QDoubleSpinBox, factor: float) -> None:
        """
        Change the step size of the spinbox.
        Args:
            spinBox(QDoubleSpinBox): Spinbox to change the step size.
            factor(float): Factor to change the step size.
        """
        old_step = spinBox.value()
        new_step = old_step * factor
        spinBox.setValue(new_step)

    def _sync_step_sizes(self):
        """Sync step sizes based on checkbox state."""
        if self.checkBox_same_xy.isChecked():
            value = self.spinBox_step_x.value()
            self.spinBox_step_y.setValue(value)

    def _update_step_size_x(self):
        """Update step size for x if checkbox is checked."""
        if self.checkBox_same_xy.isChecked():
            value = self.spinBox_step_x.value()
            self.spinBox_step_y.setValue(value)

    def _update_step_size_y(self):
        """Update step size for y if checkbox is checked."""
        if self.checkBox_same_xy.isChecked():
            value = self.spinBox_step_y.value()
            self.spinBox_step_x.setValue(value)

    @pyqtSlot(str, str)
    def change_motors(self, motor_x: str, motor_y: str):
        """
        Change the active motors and update config.
        Can be connected to the selected_motors_signal from MotorControlSelection.
        Args:
            motor_x(str): New motor X to be controlled.
            motor_y(str): New motor Y to be controlled.
        """
        self.motor_x = motor_x
        self.motor_y = motor_y
        self.config["motor_control"]["motor_x"] = motor_x
        self.config["motor_control"]["motor_y"] = motor_y

    @pyqtSlot(bool)
    def enable_motor_controls(self, disable: bool) -> None:
        """
        Enable or disable the motor controls.
        Args:
            enable(bool): True to disable, False to enable.
        """

        # Disable or enable all controls within the motorControl_absolute group box
        for widget in self.motorControl.findChildren(QWidget):
            widget.setEnabled(disable)

        # Enable the pushButton_stop if the motor is moving
        self.pushButton_stop.setEnabled(True)

    def move_motor_relative(self, motor, axis: str, direction: int) -> None:
        """
        Move the motor relative to the current position.
        Args:
            motor: Motor to move.
            axis(str): Axis to move.
            direction(int): Direction to move. 1 for positive, -1 for negative.
        """
        if axis == "x":
            step = direction * self.spinBox_step_x.value()
        elif axis == "y":
            step = direction * self.spinBox_step_y.value()
        self.motor_thread.move_relative(motor, step)


class MotorCoordinateTable(MotorControlWidget):
    plot_coordinates_signal = pyqtSignal(list)

    def _load_ui(self):
        """Load the UI for the coordinate table."""
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "motor_control_table.ui"), self)

    def _init_ui(self):
        """Initialize the UI"""
        # Setup table behaviour
        self._setup_table()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        # for tag columns default tag
        self.tag_counter = 1

        # Connect signals and slots
        self.checkBox_resize_auto.stateChanged.connect(self.resize_table_auto)

        # Keyboard shortcuts for deleting a row
        self.delete_shortcut = QShortcut(QKeySequence(Qt.Key_Delete), self.table)
        self.delete_shortcut.activated.connect(self.delete_selected_row)
        self.backspace_shortcut = QShortcut(QKeySequence(Qt.Key_Backspace), self.table)
        self.backspace_shortcut.activated.connect(self.delete_selected_row)

    @pyqtSlot(dict)
    def on_config_update(self, config: dict) -> None:
        """
        Update config dict
        Args:
            config(dict): New config dict
        """
        self.config = config

        # Get motor names
        self.motor_x, self.motor_y = (
            self.config["motor_control"]["motor_x"],
            self.config["motor_control"]["motor_y"],
        )

        # Decimal precision of the table coordinates
        self.precision = self.config["motor_control"].get("precision", 3)

        # Mode switch default option
        self.mode = self.config["motor_control"].get("mode", "Individual")

        # Set combobox to default mode
        self.mode_combobox.setCurrentText(self.mode)

        self._init_ui()

    def _setup_table(self):
        """Setup the table with appropriate headers and configurations."""
        mode = self.mode_combobox.currentText()

        if mode == "Individual":
            self._setup_individual_mode()
        elif mode == "Start/Stop":
            self._setup_start_stop_mode()
            self.start_stop_counter = 0

    def _setup_individual_mode(self):
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Show", "Move", "Tag", "X", "Y"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)

    def _setup_start_stop_mode(self):
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "Show",
                "Move [start]",
                "Move [end]" "Tag",
                "X [start]",
                "Y [start]",
                "X [end]",
                "Y [end]",
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)

    @pyqtSlot(tuple)
    def add_coordinate(self, coordinates: tuple):
        """
        Add a coordinate to the table.
        Args:
            coordinates(tuple): Coordinates (x,y) to add to the table.
        """
        tag = f"Pos {self.tag_counter}"
        self.tag_counter += 1
        x, y = coordinates
        self._add_row(tag, x, y)

    def _add_row(self, tag, x, y):
        """Internal method to add a row to the table."""
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)

        # Checkbox for toggling visibility
        show_checkbox = QCheckBox()
        show_checkbox.setChecked(True)
        show_checkbox.stateChanged.connect(self.emit_plot_coordinates)
        self.table.setCellWidget(row_count, 0, show_checkbox)

        # TODO add mode switch recognision
        # Move button
        move_button = QPushButton("Move")
        move_button.clicked.connect(self.handle_move_button_click)
        self.table.setCellWidget(row_count, 1, move_button)

        # Tag
        self.table.setItem(row_count, 2, QTableWidgetItem(tag))

        # Adding validator
        validator = QDoubleValidator()
        validator.setDecimals(self.precision)

        # X as QLineEdit with validator
        x_edit = QLineEdit(str(f"{x:.{self.precision}f}"))
        x_edit.setValidator(validator)
        self.table.setCellWidget(row_count, 3, x_edit)
        x_edit.textChanged.connect(self.emit_plot_coordinates)

        # Y as QLineEdit with validator
        y_edit = QLineEdit(str(f"{y:.{self.precision}f}"))
        y_edit.setValidator(validator)
        self.table.setCellWidget(row_count, 4, y_edit)
        y_edit.textChanged.connect(self.emit_plot_coordinates)

        # Emit the coordinates to be plotted
        self.emit_plot_coordinates()

        # Connect item edit to emit coordinates
        self.table.itemChanged.connect(self.emit_plot_coordinates)

        # Auto table resize
        self.resize_table_auto()

        # Align table center
        self._align_table_center()

    def handle_move_button_click(self):
        """Handle the click event of the move button."""
        button = self.sender()
        row = self.table.indexAt(button.pos()).row()

        x = self.get_coordinate(row, 3)
        y = self.get_coordinate(row, 4)
        self.move_motor(x, y)

        # Emit updated coordinates to update the map
        self.emit_plot_coordinates()

    def emit_plot_coordinates(self):
        """Emit the coordinates to be plotted."""
        coordinates = []
        for row in range(self.table.rowCount()):
            show = self.table.cellWidget(row, 0).isChecked()
            x = self.get_coordinate(row, 3)
            y = self.get_coordinate(row, 4)

            coordinates.append((x, y, show))  # (x, y, show_flag)
        self.plot_coordinates_signal.emit(coordinates)

    def get_coordinate(self, row: int, column: int) -> float:
        """
        Helper function to get the coordinate from the table QLineEdit cells.
        Args:
            row(int): Row of the table.
            column(int): Column of the table.
        Returns:
            float: Value of the coordinate.
        """
        edit = self.table.cellWidget(row, column)
        if edit.text() is not None and edit.text() != "":
            value = float(edit.text()) if edit else None
        return value

    def delete_selected_row(self):
        """Delete the selected row from the table."""
        selected_rows = self.table.selectionModel().selectedRows()
        for row in selected_rows:
            self.table.removeRow(row.row())
        self.emit_plot_coordinates()

    def resize_table_auto(self):
        """Resize the table to fit the contents."""
        if self.checkBox_resize_auto.isChecked():
            self.table.resizeColumnsToContents()

    def _align_table_center(self) -> None:
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignCenter)

    def move_motor(self, x, y):
        """Move the motor to the specified coordinates."""
        self.motor_thread.move_absolute(self.motor_x, self.motor_y, (x, y))

    @pyqtSlot(str, str)
    def change_motors(self, motor_x: str, motor_y: str):
        """
        Change the active motors and update config.
        Can be connected to the selected_motors_signal from MotorControlSelection.
        Args:
            motor_x(str): New motor X to be controlled.
            motor_y(str): New motor Y to be controlled.
        """
        self.motor_x = motor_x
        self.motor_y = motor_y
        self.config["motor_control"]["motor_x"] = motor_x
        self.config["motor_control"]["motor_y"] = motor_y

    @pyqtSlot(int)
    def set_precision(self, precision: int) -> None:
        """
        Set the precision of the coordinates.
        Args:
            precision(int): Precision of the coordinates.
        """
        self.precision = precision
        self.config["motor_control"]["precision"] = precision


class MotorControlErrors:
    """Class for displaying formatted error messages."""

    @staticmethod
    def display_error_message(error_message: str) -> None:
        """
        Display a critical error message.
        Args:
            error_message(str): Error message to display.
        """
        # Create a QMessageBox
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Critical Error")

        # Format the message
        formatted_message = MotorControlErrors._format_error_message(error_message)
        msg.setText(formatted_message)

        # Display the message box
        msg.exec_()

    @staticmethod
    def _format_error_message(error_message: str) -> str:
        """
        Format the error message.
        Args:
            error_message(str): Error message to format.

        Returns:
            str: Formatted error message.
        """
        # Split the message into lines
        lines = error_message.split("\n")
        formatted_lines = [
            f"<b>{line.strip()}</b>" if i == 0 else line.strip()
            for i, line in enumerate(lines)
            if line.strip()
        ]

        # Join the lines with double breaks for empty lines in between
        formatted_message = "<br><br>".join(formatted_lines)

        return formatted_message


class MotorActions(Enum):
    """Enum for motor actions."""

    MOVE_ABSOLUTE = "move_absolute"
    MOVE_RELATIVE = "move_relative"


class MotorThread(QThread):
    """
    QThread subclass for controlling motor actions asynchronously.

    Signals:
        coordinates_updated (pyqtSignal): Signal to emit current coordinates.
        motor_error (pyqtSignal): Signal to emit when there is an error with the motors.
        lock_gui (pyqtSignal): Signal to lock/unlock the GUI.
    """

    coordinates_updated = pyqtSignal(float, float)  # Signal to emit current coordinates
    motor_error = pyqtSignal(str)  # Signal to emit when there is an error with the motors
    lock_gui = pyqtSignal(bool)  # Signal to lock/unlock the GUI

    def __init__(self, parent=None, client=None):
        super().__init__(parent)

        bec_dispatcher = BECDispatcher()
        self.client = bec_dispatcher.client if client is None else client
        self.dev = self.client.device_manager.devices
        self.scans = self.client.scans
        self.queue = self.client.queue
        self.action = None

        self.motor = None
        self.motor_x = None
        self.motor_y = None
        self.target_coordinates = None
        self.value = None

    def get_all_motors_names(self) -> list:
        """
        Get all the motors names.
        Returns:
            list: List of all the motors names.
        """
        all_devices = self.client.device_manager.devices.enabled_devices
        all_motors_names = [motor.name for motor in all_devices if isinstance(motor, Positioner)]
        return all_motors_names

    def get_coordinates(self, motor_x: str, motor_y: str) -> tuple:
        """
        Get the current coordinates of the motors.
        Args:
            motor_x(str): Motor X to get positions from.
            motor_y(str): Motor Y to get positions from.

        Returns:
            tuple: Current coordinates of the motors.
        """
        x = self.dev[motor_x].readback.get()
        y = self.dev[motor_y].readback.get()
        return x, y

    def move_absolute(self, motor_x: str, motor_y: str, target_coordinates: tuple) -> None:
        """
        Wrapper for moving the motor to the target coordinates.
        Args:
            motor_x(str): Motor X to move.
            motor_y(str): Motor Y to move.
            target_coordinates(tuple): Target coordinates.
        """
        self.action = MotorActions.MOVE_ABSOLUTE
        self.motor_x = motor_x
        self.motor_y = motor_y
        self.target_coordinates = target_coordinates
        self.start()

    def move_relative(self, motor: str, value: float) -> None:
        """
        Wrapper for moving the motor relative to the current position.
        Args:
            motor(str): Motor to move.
            value(float): Value to move.
        """
        self.action = MotorActions.MOVE_RELATIVE
        self.motor = motor
        self.value = value
        self.start()

    def run(self):
        """
        Run the thread.
        Possible actions:
            - Move to coordinates
            - Move relative
        """
        if self.action == MotorActions.MOVE_ABSOLUTE:
            self._move_motor_absolute(self.motor_x, self.motor_y, self.target_coordinates)
        elif self.action == MotorActions.MOVE_RELATIVE:
            self._move_motor_relative(self.motor, self.value)

    def _move_motor_absolute(self, motor_x: str, motor_y: str, target_coordinates: tuple) -> None:
        """
        Move the motor to the target coordinates.
        Args:
            motor_x(str): Motor X to move.
            motor_y(str): Motor Y to move.
            target_coordinates(tuple): Target coordinates.
        """
        self.lock_gui.emit(False)
        try:
            status = self.scans.mv(
                self.dev[motor_x],
                target_coordinates[0],
                self.dev[motor_y],
                target_coordinates[1],
                relative=False,
            )
            status.wait()
        except AlarmBase as e:
            self.motor_error.emit(str(e))
        finally:
            self.lock_gui.emit(True)

    def _move_motor_relative(self, motor, value: float) -> None:
        """
        Move the motor relative to the current position.
        Args:
            motor(str): Motor to move.
            value(float): Value to move.
        """
        self.lock_gui.emit(False)
        try:
            status = self.scans.mv(self.dev[motor], value, relative=True)
            status.wait()
        except AlarmBase as e:
            self.motor_error.emit(str(e))
        finally:
            self.lock_gui.emit(True)

    def stop_movement(self):
        self.queue.request_scan_abortion()
        self.queue.request_queue_reset()
