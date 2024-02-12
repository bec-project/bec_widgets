# pylint: disable = no-name-in-module,missing-module-docstring
import os
from enum import Enum

import qdarktheme

from pyqtgraph.Qt import uic
from qtpy import uic
from qtpy.QtCore import QThread, Slot as pyqtSlot
from qtpy.QtCore import Signal as pyqtSignal, Qt
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import (
    QApplication,
    QWidget,
    QSpinBox,
    QDoubleSpinBox,
    QShortcut,
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

# class MotorControlConnectAbsoltue(QWidget):


# class MotorControlPanel(QWidget):
#     def __init__(self,parent=None):
#         super().__init__()
#         self.init_ui()
#     def init_ui(self):
#         """Initialize the UI."""
class MotorControlSelection(QWidget):
    update_signal = pyqtSignal()
    selected_motors_signal = pyqtSignal(str, str)

    def __init__(
        self,
        parent=None,
        client=None,
        motor_thread=None,
        config: dict = None,
    ):
        super().__init__(parent=parent)

        bec_dispatcher = BECDispatcher()
        self.client = bec_dispatcher.client if client is None else client
        self.dev = self.client.device_manager.devices
        self.config = config

        # Loading UI
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "motor_control_selection.ui"), self)

        # Motor Control Thread
        self.motor_thread = (
            MotorThread(client=self.client) if motor_thread is None else motor_thread
        )

        if self.config is None:
            print(f"No initial config found for {self.__class__.__name__}")
            self._init_ui()
        else:
            self.on_config_update(self.config)

    def _init_ui(self):
        """Initialize the UI."""
        self.pushButton_connecMotors.clicked.connect(self.select_motor)
        self.get_available_motors()

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
        if self.config is not None:
            index_x = self.comboBox_motor_x.findText(self.motor_x)
            index_y = self.comboBox_motor_y.findText(self.motor_y)

            if index_x != -1:
                self.comboBox_motor_x.setCurrentIndex(index_x)
            else:
                print(
                    f"Warning: Motor '{self.motor_x}' specified in the config file is not available."
                )
                self.comboBox_motor_x.setCurrentIndex(0)

            if index_y != -1:
                self.comboBox_motor_y.setCurrentIndex(index_y)
            else:
                print(
                    f"Warning: Motor '{self.motor_y}' specified in the config file is not available."
                )
                self.comboBox_motor_y.setCurrentIndex(0)
            if index_x != -1 and index_y != -1:
                self.selected_motors_signal.emit(self.motor_x, self.motor_y)
        # setup default index 0, if there is no config
        else:
            self.comboBox_motor_x.setCurrentIndex(0)
            self.comboBox_motor_y.setCurrentIndex(0)

    def select_motor(self):
        """Emit the selected motors"""
        motor_x = self.comboBox_motor_x.currentText()
        motor_y = self.comboBox_motor_y.currentText()

        self.selected_motors_signal.emit(motor_x, motor_y)
        print(f"emitted motors {motor_x} and {motor_y}")


class MotorControlAbsolute(QWidget):
    update_signal = pyqtSignal()
    coordinates_signal = pyqtSignal(tuple)

    def __init__(
        self,
        parent=None,
        client=None,
        motor_thread=None,
        config: dict = None,
    ):
        super().__init__(parent=parent)

        bec_dispatcher = BECDispatcher()
        self.client = bec_dispatcher.client if client is None else client
        self.dev = self.client.device_manager.devices
        self.config = config

        # Loading UI
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "motor_control_absolute.ui"), self)

        # Motor Control Thread
        self.motor_thread = (
            MotorThread(client=self.client) if motor_thread is None else motor_thread
        )

        if self.config is None:
            print(f"No initial config found for {self.__class__.__name__}")
            self._init_ui()
        else:
            self.on_config_update(self.config)

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

    def _init_ui(self):
        """Initialize the UI."""

        # Check if there are any motors connected
        if (
            self.motor_x is None or self.motor_y is None
        ):  # TODO change logic of checking -> jsut check names
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
        self.motor_thread.move_finished.connect(lambda: self._enable_motor_controls(True))

        # Error messages
        self.motor_thread.motor_error.connect(
            lambda error: MotorControlErrors.display_error_message(error)
        )

    def _enable_motor_controls(self, disable: bool) -> None:
        # Disable or enable all controls within the motorControl_absolute group box
        for widget in self.motorControl_absolute.findChildren(QWidget):
            widget.setEnabled(disable)

        # Enable the pushButton_stop if the motor is moving
        self.pushButton_stop.setEnabled(True)

    def move_motor_absolute(self, x: float, y: float) -> None:
        self._enable_motor_controls(False)
        target_coordinates = (x, y)
        self.motor_thread.move_absolute(self.motor_x, self.motor_y, target_coordinates)
        if self.checkBox_save_with_go.isChecked():
            self.save_absolute_coordinates()

    def _init_keyboard_shortcuts(self):
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
        x, y = self.motor_thread.retrieve_coordinates()
        self.coordinates_signal.emit((x, y))


class MotorControlRelative(QWidget):
    update_signal = pyqtSignal()

    def __init__(
        self,
        parent=None,
        client=None,
        motor_thread=None,
        config: dict = None,
    ):
        super().__init__(parent=parent)

        # BECclient
        bec_dispatcher = BECDispatcher()
        self.client = bec_dispatcher.client if client is None else client
        self.dev = self.client.device_manager.devices
        self.config = config

        # Loading UI
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "motor_control_relative.ui"), self)

        # Motor Control Thread
        self.motor_thread = (
            MotorThread(client=self.client) if motor_thread is None else motor_thread
        )

        self._init_ui()
        if self.config is None:
            print(f"No initial config found for {self.__class__.__name__}")
        else:
            self.on_config_update(self.config)

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
        self.motor_thread.move_finished.connect(lambda: self.enable_motor_controls(True))

        # Precision update
        self.spinBox_precision.valueChanged.connect(lambda x: self._update_precision(x))

        # Error messages
        self.motor_thread.motor_error.connect(
            lambda error: MotorControlErrors.display_error_message(error)
        )

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

        # Increase/decrease step size for Y motor
        increase_y_shortcut = QShortcut(QKeySequence("Alt+A"), self)
        decrease_y_shortcut = QShortcut(QKeySequence("Alt+Z"), self)
        increase_y_shortcut.activated.connect(
            lambda: self._change_step_size(self.spinBox_step_y, 2)
        )
        decrease_y_shortcut.activated.connect(
            lambda: self._change_step_size(self.spinBox_step_y, 0.5)
        )

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

    @pyqtSlot()
    def enable_motor_control(self):
        """Enable the motor control buttons."""
        self.motorControl.setEnabled(True)

    @pyqtSlot(str, str)
    def change_motors(self, motor_x: str, motor_y: str):
        """
        Change the active motors and update config.
        Args:
            motor_x(str): New motor X to be controlled.
            motor_y(str): New motor Y to be controlled.
        """
        self.motor_x = motor_x
        self.motor_y = motor_y
        self.config["motor_control"]["motor_x"] = motor_x
        self.config["motor_control"]["motor_y"] = motor_y

    def enable_motor_controls(self, disable: bool) -> None:
        """
        Enable or disable the motor controls.
        Args:
            disable(bool): True to disable, False to enable.
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
        self.enable_motor_controls(False)
        if axis == "x":
            step = direction * self.spinBox_step_x.value()
        elif axis == "y":
            step = direction * self.spinBox_step_y.value()
        self.motor_thread.move_relative(motor, step)


class MotorControlErrors:
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

    Attributes:
        coordinates_updated (pyqtSignal): Signal to emit current coordinates.
        limits_retrieved (pyqtSignal): Signal to emit current limits.
        move_finished (pyqtSignal): Signal to emit when the move is finished.
        motors_loaded (pyqtSignal): Signal to emit when the motors are loaded.
        motors_selected (pyqtSignal): Signal to emit when the motors are selected.
    """

    coordinates_updated = pyqtSignal(float, float)  # Signal to emit current coordinates
    limits_retrieved = pyqtSignal(list, list)  # Signal to emit current limits #TODO remove?
    move_finished = pyqtSignal()  # Signal to emit when the move is finished
    motors_loaded = pyqtSignal(
        list, list
    )  # Signal to emit when the motors are loaded #todo remove?
    motors_selected = pyqtSignal(
        object, object
    )  # Signal to emit when the motors are selected #TODO remove?
    motor_error = pyqtSignal(str)  # Signal to emit when there is an error with the motors

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
            self.move_finished.emit()

    def _move_motor_relative(self, motor, value: float) -> None:
        """
        Move the motor relative to the current position.
        Args:
            motor(str): Motor to move.
            value(float): Value to move.
        """
        try:
            status = self.scans.mv(self.dev[motor], value, relative=True)
            status.wait()
        except AlarmBase as e:
            print(e)
            self.motor_error.emit(str(e))
        finally:
            self.move_finished.emit()

    def stop_movement(self):
        self.queue.request_scan_abortion()
        self.queue.request_queue_reset()


if __name__ == "__main__":
    bec_dispatcher = BECDispatcher()
    # BECclient global variables
    client = bec_dispatcher.client
    client.start()

    app = QApplication([])
    qdarktheme.setup_theme("auto")
    # motor_control = MotorControlRelative(client=client, config=CONFIG_DEFAULT)

    motor_control = MotorControlSelection(client=client, config=CONFIG_DEFAULT)
    window = motor_control
    window.show()
    app.exec()
