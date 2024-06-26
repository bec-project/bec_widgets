import os

from qtpy import uic
from qtpy.QtCore import Qt
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import QDoubleSpinBox, QShortcut, QWidget

from bec_widgets.utils.ui_loader import UILoader
from bec_widgets.widgets.motor_control.motor_control import MotorControlWidget


class MotorControlRelative(MotorControlWidget):
    """
    Widget for controlling the motors to relative coordinates.

    Signals:
        precision_signal (pyqtSignal): Signal to emit the precision of the coordinates.
    Slots:
        change_motors (pyqtSlot(str,str)): Slot to change the active motors.
        enable_motor_controls (pyqtSlot): Slot to enable/disable the motor controls.
    """

    precision_signal = pyqtSignal(int)

    def _load_ui(self):
        """Load the UI from the .ui file."""
        # Loading UI
        current_path = os.path.dirname(__file__)
        self.ui = UILoader().load_ui(os.path.join(current_path, "movement_relative.ui"), self)

    def _init_ui(self):
        """Initialize the UI."""
        self._init_ui_motor_control()
        self._init_keyboard_shortcuts()

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

        # Update step precision
        self.precision = self.config["motor_control"]["precision"]
        self.ui.spinBox_precision.setValue(self.precision)

        # Update step sizes
        self.ui.spinBox_step_x.setValue(self.config["motor_control"]["step_size_x"])
        self.ui.spinBox_step_y.setValue(self.config["motor_control"]["step_size_y"])

        # Checkboxes for keyboard shortcuts and x/y step size link
        self.ui.checkBox_same_xy.setChecked(self.config["motor_control"]["step_x_y_same"])
        self.ui.checkBox_enableArrows.setChecked(self.config["motor_control"]["move_with_arrows"])

        self._init_ui()

    def _init_ui_motor_control(self) -> None:
        """Initialize the motor control elements"""

        # Connect checkbox and spinBoxes
        self.ui.checkBox_same_xy.stateChanged.connect(self._sync_step_sizes)
        self.ui.spinBox_step_x.valueChanged.connect(self._update_step_size_x)
        self.ui.spinBox_step_y.valueChanged.connect(self._update_step_size_y)

        self.ui.toolButton_right.clicked.connect(
            lambda: self.move_motor_relative(self.motor_x, "x", 1)
        )
        self.ui.toolButton_left.clicked.connect(
            lambda: self.move_motor_relative(self.motor_x, "x", -1)
        )
        self.ui.toolButton_up.clicked.connect(
            lambda: self.move_motor_relative(self.motor_y, "y", 1)
        )
        self.ui.toolButton_down.clicked.connect(
            lambda: self.move_motor_relative(self.motor_y, "y", -1)
        )

        # Switch between key shortcuts active
        self.ui.checkBox_enableArrows.stateChanged.connect(self._update_arrow_key_shortcuts)
        self._update_arrow_key_shortcuts()

        # Enable/Disable GUI
        self.motor_thread.lock_gui.connect(self.enable_motor_controls)

        # Precision update
        self.ui.spinBox_precision.valueChanged.connect(lambda x: self._update_precision(x))

        # Error messages
        self.motor_thread.motor_error.connect(
            lambda error: MotorControlErrors.display_error_message(error)
        )

        # Stop Button
        self.ui.pushButton_stop.clicked.connect(self.motor_thread.stop_movement)

    def _init_keyboard_shortcuts(self) -> None:
        """Initialize the keyboard shortcuts"""

        # Increase/decrease step size for X motor
        increase_x_shortcut = QShortcut(QKeySequence("Ctrl+A"), self)
        decrease_x_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        increase_x_shortcut.activated.connect(
            lambda: self._change_step_size(self.ui.spinBox_step_x, 2)
        )
        decrease_x_shortcut.activated.connect(
            lambda: self._change_step_size(self.ui.spinBox_step_x, 0.5)
        )
        self.ui.spinBox_step_x.setToolTip("Increase step size: Ctrl+A\nDecrease step size: Ctrl+Z")

        # Increase/decrease step size for Y motor
        increase_y_shortcut = QShortcut(QKeySequence("Alt+A"), self)
        decrease_y_shortcut = QShortcut(QKeySequence("Alt+Z"), self)
        increase_y_shortcut.activated.connect(
            lambda: self._change_step_size(self.ui.spinBox_step_y, 2)
        )
        decrease_y_shortcut.activated.connect(
            lambda: self._change_step_size(self.ui.spinBox_step_y, 0.5)
        )
        self.ui.spinBox_step_y.setToolTip("Increase step size: Alt+A\nDecrease step size: Alt+Z")

        # Stop Button
        self.ui.pushButton_stop.setShortcut("Ctrl+X")
        self.ui.pushButton_stop.setToolTip("Ctrl+X")

    def _update_arrow_key_shortcuts(self) -> None:
        """Update the arrow key shortcuts based on the checkbox state."""
        if self.ui.checkBox_enableArrows.isChecked():
            # Set the arrow key shortcuts for motor movement
            self.ui.toolButton_right.setShortcut(Qt.Key_Right)
            self.ui.toolButton_left.setShortcut(Qt.Key_Left)
            self.ui.toolButton_up.setShortcut(Qt.Key_Up)
            self.ui.toolButton_down.setShortcut(Qt.Key_Down)
        else:
            # Clear the shortcuts
            self.ui.toolButton_right.setShortcut("")
            self.ui.toolButton_left.setShortcut("")
            self.ui.toolButton_up.setShortcut("")
            self.ui.toolButton_down.setShortcut("")

    def _update_precision(self, precision: int) -> None:
        """
        Update the precision of the coordinates.
        Args:
            precision(int): Precision of the coordinates.
        """
        self.ui.spinBox_step_x.setDecimals(precision)
        self.ui.spinBox_step_y.setDecimals(precision)
        self.precision_signal.emit(precision)

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
        if self.ui.checkBox_same_xy.isChecked():
            value = self.ui.spinBox_step_x.value()
            self.ui.spinBox_step_y.setValue(value)

    def _update_step_size_x(self):
        """Update step size for x if checkbox is checked."""
        if self.ui.checkBox_same_xy.isChecked():
            value = self.ui.spinBox_step_x.value()
            self.ui.spinBox_step_y.setValue(value)

    def _update_step_size_y(self):
        """Update step size for y if checkbox is checked."""
        if self.ui.checkBox_same_xy.isChecked():
            value = self.ui.spinBox_step_y.value()
            self.ui.spinBox_step_x.setValue(value)

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
            disable(bool): True to disable, False to enable.
        """

        # Disable or enable all controls within the motorControl_absolute group box
        for widget in self.ui.motorControl.findChildren(QWidget):
            widget.setEnabled(disable)

        # Enable the pushButton_stop if the motor is moving
        self.ui.pushButton_stop.setEnabled(True)

    def move_motor_relative(self, motor, axis: str, direction: int) -> None:
        """
        Move the motor relative to the current position.
        Args:
            motor: Motor to move.
            axis(str): Axis to move.
            direction(int): Direction to move. 1 for positive, -1 for negative.
        """
        if axis == "x":
            step = direction * self.ui.spinBox_step_x.value()
        elif axis == "y":
            step = direction * self.ui.spinBox_step_y.value()
        self.motor_thread.move_relative(motor, step)
