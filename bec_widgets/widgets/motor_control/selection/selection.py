# pylint: disable = no-name-in-module,missing-module-docstring
import os

from qtpy import uic
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtWidgets import QComboBox

from bec_widgets.widgets.motor_control.motor_control import MotorControlWidget


class MotorControlSelection(MotorControlWidget):
    """
    Widget for selecting the motors to control.

    Signals:
        selected_motors_signal (pyqtSignal(str,str)): Signal to emit the selected motors.
    Slots:
        get_available_motors (pyqtSlot): Slot to populate the available motors in the combo boxes and set the index based on the configuration.
        enable_motor_controls (pyqtSlot(bool)): Slot to enable/disable the motor controls GUI.
        on_config_update (pyqtSlot(dict)): Slot to update the config dict.
    """

    selected_motors_signal = pyqtSignal(str, str)

    def _load_ui(self):
        """Load the UI from the .ui file."""
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "selection.ui"), self)

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

    @pyqtSlot()
    def get_available_motors(self) -> None:
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

    def set_combobox_style(self, combobox, color: str) -> None:
        """
        Set the combobox style to a specific color.
        Args:
            combobox(QComboBox): Combobox to change the color.
            color(str): Color to set the combobox to.
        """
        combobox.setStyleSheet(f"QComboBox {{ background-color: {color}; }}")

    def select_motor(self):
        """Emit the selected motors"""
        motor_x = self.comboBox_motor_x.currentText()
        motor_y = self.comboBox_motor_y.currentText()

        # Reset the combobox color to normal after selection
        self.set_combobox_style(self.comboBox_motor_x, "")
        self.set_combobox_style(self.comboBox_motor_y, "")

        self.selected_motors_signal.emit(motor_x, motor_y)
