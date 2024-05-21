import os

from qtpy import uic
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot

from bec_widgets.widgets.motor_control.motor_control import MotorControlWidget


class MotorControlAbsolute(MotorControlWidget):
    """
    Widget for controlling the motors to absolute coordinates.

    Signals:
        coordinates_signal (pyqtSignal(tuple)): Signal to emit the coordinates.
    Slots:
        change_motors (pyqtSlot): Slot to change the active motors.
        enable_motor_controls (pyqtSlot(bool)): Slot to enable/disable the motor controls.
    """

    coordinates_signal = pyqtSignal(tuple)

    def _load_ui(self):
        """Load the UI from the .ui file."""
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "movement_absolute.ui"), self)

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

        # Keyboard shortcuts
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

    @pyqtSlot(int)
    def set_precision(self, precision: int) -> None:
        """
        Set the precision of the coordinates.
        Args:
            precision(int): Precision of the coordinates.
        """
        self.precision = precision
        self.config["motor_control"]["precision"] = precision
        self.spinBox_absolute_x.setDecimals(precision)
        self.spinBox_absolute_y.setDecimals(precision)

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
