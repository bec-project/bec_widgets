""" Module for a PositionerBox widget to control a positioner device."""

from __future__ import annotations

import os

from bec_lib.device import Positioner
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import Property, Signal, Slot
from qtpy.QtGui import QDoubleValidator
from qtpy.QtWidgets import QDialog, QDoubleSpinBox, QPushButton, QVBoxLayout

from bec_widgets.widgets.control.device_control.positioner_box._base import PositionerBoxBase
from bec_widgets.utils import UILoader
from bec_widgets.utils.colors import get_accent_colors, set_theme
from bec_widgets.widgets.control.device_control.positioner_box._base.positioner_box_base import (
    DeviceUpdateUIComponents,
)
from bec_widgets.widgets.control.device_input.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.control.device_input.device_line_edit.device_line_edit import (
    DeviceLineEdit,
)


logger = bec_logger.logger

MODULE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


class PositionerBox(PositionerBoxBase):
    """Simple Widget to control a positioner in box form"""

    ui_file = "positioner_box.ui"
    dimensions = (234, 224)

    PLUGIN = True

    USER_ACCESS = ["set_positioner"]
    device_changed = Signal(str, str)
    # Signal emitted to inform listeners about a position update
    position_update = Signal(float)

    def __init__(self, parent=None, device: Positioner | str | None = None, **kwargs):
        """Initialize the PositionerBox widget.

        Args:
            parent: The parent widget.
            device (Positioner): The device to control.
        """
        super().__init__(parent=parent, **kwargs)

        self._device = ""
        self._limits = None
        self._dialog = None
        if self.current_path == "":
            self.current_path = os.path.dirname(__file__)

        self.init_ui()
        self.device = device
        self._init_device(self.device, self.position_update.emit, self.update_limits)

    def init_ui(self):
        """Init the ui"""
        self.device_changed.connect(self.on_device_change)

        self.ui = UILoader(self).loader(os.path.join(self.current_path, self.ui_file))

        self.addWidget(self.ui)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # fix the size of the device box
        db = self.ui.device_box
        db.setFixedHeight(self.dimensions[0])
        db.setFixedWidth(self.dimensions[1])

        self.ui.step_size.setStepType(QDoubleSpinBox.AdaptiveDecimalStepType)
        self.ui.stop.clicked.connect(self.on_stop)
        self.ui.stop.setToolTip("Stop")
        self.ui.stop.setStyleSheet(
            f"QPushButton {{background-color: {get_accent_colors().emergency.name()}; color: white;}}"
        )
        self.ui.tweak_right.clicked.connect(self.on_tweak_right)
        self.ui.tweak_right.setToolTip("Tweak right")
        self.ui.tweak_left.clicked.connect(self.on_tweak_left)
        self.ui.tweak_left.setToolTip("Tweak left")
        self.ui.setpoint.returnPressed.connect(self.on_setpoint_change)

        self.setpoint_validator = QDoubleValidator()
        self.ui.setpoint.setValidator(self.setpoint_validator)
        self.ui.spinner_widget.start()
        self.ui.tool_button.clicked.connect(self._open_dialog_selection)
        icon = material_icon(icon_name="edit_note", size=(16, 16), convert_to_pixmap=False)
        self.ui.tool_button.setIcon(icon)

    def _open_dialog_selection(self):
        """Open dialog window for positioner selection"""
        self._dialog = QDialog(self)
        self._dialog.setWindowTitle("Positioner Selection")
        layout = QVBoxLayout()
        line_edit = DeviceLineEdit(
            self, client=self.client, device_filter=[BECDeviceFilter.POSITIONER]
        )
        line_edit.textChanged.connect(self.set_positioner)
        layout.addWidget(line_edit)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self._dialog.accept)
        layout.addWidget(close_button)
        self._dialog.setLayout(layout)
        self._dialog.exec()
        self._dialog = None

    def _toogle_enable_buttons(self, enable: bool) -> None:
        """Toogle enable/disable on available buttons

        Args:
            enable (bool): Enable buttons
        """
        self.ui.tweak_left.setEnabled(enable)
        self.ui.tweak_right.setEnabled(enable)
        self.ui.stop.setEnabled(enable)
        self.ui.setpoint.setEnabled(enable)
        self.ui.step_size.setEnabled(enable)

    @Property(str)
    def device(self):
        """Property to set the device"""
        return self._device

    @device.setter
    def device(self, value: str):
        """Setter, checks if device is a string"""
        if not value or not isinstance(value, str):
            return
        if not self._check_device_is_valid(value):
            return
        old_device = self._device
        self._device = value
        if not self.label:
            self.label = value
        self.device_changed.emit(old_device, value)

    @Property(bool)
    def hide_device_selection(self):
        """Hide the device selection"""
        return not self.ui.tool_button.isVisible()

    @hide_device_selection.setter
    def hide_device_selection(self, value: bool):
        """Set the device selection visibility"""
        self.ui.tool_button.setVisible(not value)

    @Slot(bool)
    def show_device_selection(self, value: bool):
        """Show the device selection

        Args:
            value (bool): Show the device selection
        """
        self.hide_device_selection = not value

    @Slot(str)
    def set_positioner(self, positioner: str | Positioner):
        """Set the device

        Args:
            positioner (Positioner | str) : Positioner to set, accepts str or the device
        """
        if isinstance(positioner, Positioner):
            positioner = positioner.name
        self.device = positioner

    @Slot(str, str)
    def on_device_change(self, old_device: str, new_device: str):
        """Upon changing the device, a check will be performed if the device is a Positioner.

        Args:
            old_device (str): The old device name.
            new_device (str): The new device name.
        """
        if not self._check_device_is_valid(new_device):
            return
        logger.info(f"Device changed from {old_device} to {new_device}")
        self._toogle_enable_buttons(True)
        self._init_device(new_device, self.position_update.emit, self.update_limits)
        self._swap_readback_signal_connection(self.on_device_readback, old_device, new_device)
        self._update_device_ui(new_device, self._device_ui_components(new_device))

    def _device_ui_components(self, device: str) -> DeviceUpdateUIComponents:
        return {
            "spinner": self.ui.spinner_widget,
            "position_indicator": self.ui.position_indicator,
            "readback": self.ui.readback,
            "setpoint": self.ui.setpoint,
            "step_size": self.ui.step_size,
            "device_box": self.ui.device_box,
        }

    @Slot(dict, dict)
    def on_device_readback(self, msg_content: dict, metadata: dict):
        """Callback for device readback.

        Args:
            msg_content (dict): The message content.
            metadata (dict): The message metadata.
        """
        self._on_device_readback(
            self.device,
            self._device_ui_components(self.device),
            msg_content,
            metadata,
            self.position_update.emit,
            self.update_limits,
        )

    def update_limits(self, limits: tuple):
        """Update limits

        Args:
            limits (tuple): Limits of the positioner
        """
        if limits == self._limits:
            return
        self._limits = limits
        self._update_limits_ui(limits, self.ui.position_indicator, self.setpoint_validator)

    @Slot()
    def on_stop(self):
        self._stop_device(self.device)

    @property
    def step_size(self):
        """Step size for tweak"""
        return self.ui.step_size.value()

    @Slot()
    def on_tweak_right(self):
        """Tweak motor right"""
        self.dev[self.device].move(self.step_size, relative=True)

    @Slot()
    def on_tweak_left(self):
        """Tweak motor left"""
        self.dev[self.device].move(-self.step_size, relative=True)

    @Slot()
    def on_setpoint_change(self):
        """Change the setpoint for the motor"""
        self.ui.setpoint.clearFocus()
        setpoint = self.ui.setpoint.text()
        self.dev[self.device].move(float(setpoint), relative=False)
        self.ui.tweak_left.setToolTip(f"Tweak left by {self.step_size}")
        self.ui.tweak_right.setToolTip(f"Tweak right by {self.step_size}")


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication  # pylint: disable=ungrouped-imports

    app = QApplication(sys.argv)
    set_theme("dark")
    widget = PositionerBox(device="bpm4i")

    widget.show()
    sys.exit(app.exec_())
