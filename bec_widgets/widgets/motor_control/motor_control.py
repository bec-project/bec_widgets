# pylint: disable = no-name-in-module,missing-module-docstring
from enum import Enum

from bec_lib.alarm_handler import AlarmBase
from bec_lib.device import Positioner
from qtpy.QtCore import QThread
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtWidgets import QMessageBox, QWidget

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

        self.motor_x = None
        self.motor_y = None

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
