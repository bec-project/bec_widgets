"""Module for a PositionerBox2D widget to control two positioner devices."""

from __future__ import annotations

import os
from typing import Literal

from bec_lib.device import Positioner
from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import Signal
from qtpy.QtGui import QDoubleValidator
from qtpy.QtWidgets import QDoubleSpinBox

from bec_widgets.utils import UILoader
from bec_widgets.utils.colors import set_theme
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.control.device_control.positioner_box._base import PositionerBoxBase
from bec_widgets.widgets.control.device_control.positioner_box._base.positioner_box_base import (
    DeviceUpdateUIComponents,
)

logger = bec_logger.logger

MODULE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

DeviceId = Literal["horizontal", "vertical"]


class PositionerBox2D(PositionerBoxBase):
    """Simple Widget to control two positioners in box form"""

    ui_file = "positioner_box_2d.ui"

    PLUGIN = True
    RPC = True
    USER_ACCESS = ["set_positioner_hor", "set_positioner_ver"]

    device_changed_hor = Signal(str, str)
    device_changed_ver = Signal(str, str)
    # Signals emitted to inform listeners about a position update
    position_update_hor = Signal(float)
    position_update_ver = Signal(float)

    def __init__(
        self,
        parent=None,
        device_hor: Positioner | str | None = None,
        device_ver: Positioner | str | None = None,
        **kwargs,
    ):
        """Initialize the PositionerBox widget.

        Args:
            parent: The parent widget.
            device_hor (Positioner | str): The first device to control - assigned the horizontal axis.
            device_ver (Positioner | str): The second device to control - assigned the vertical axis.
        """
        super().__init__(parent=parent, **kwargs)

        self._device_hor = ""
        self._device_ver = ""
        self._limits_hor = None
        self._limits_ver = None
        self._dialog = None
        if self.current_path == "":
            self.current_path = os.path.dirname(__file__)
        self.init_ui()
        self.device_hor = device_hor
        self.device_ver = device_ver

        self.connect_ui()

    def init_ui(self):
        """Init the ui"""
        self.device_changed_hor.connect(self.on_device_change_hor)
        self.device_changed_ver.connect(self.on_device_change_ver)

        self.ui = UILoader(self).loader(os.path.join(self.current_path, self.ui_file))
        self.setpoint_validator_hor = QDoubleValidator()
        self.setpoint_validator_ver = QDoubleValidator()

    def connect_ui(self):
        """Connect the UI components to signals, data, or routines"""
        self.addWidget(self.ui)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        def _init_ui(val: QDoubleValidator, device_id: DeviceId):
            ui = self._device_ui_components_hv(device_id)
            tweak_inc = (
                self.on_tweak_inc_hor if device_id == "horizontal" else self.on_tweak_inc_ver
            )
            tweak_dec = (
                self.on_tweak_dec_hor if device_id == "horizontal" else self.on_tweak_dec_ver
            )
            ui["setpoint"].setValidator(val)
            ui["setpoint"].returnPressed.connect(
                self.on_setpoint_change_hor
                if device_id == "horizontal"
                else self.on_setpoint_change_ver
            )
            ui["stop"].setToolTip("Stop")
            ui["step_size"].setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
            ui["tweak_increase"].clicked.connect(tweak_inc)
            ui["tweak_decrease"].clicked.connect(tweak_dec)

        _init_ui(self.setpoint_validator_hor, "horizontal")
        _init_ui(self.setpoint_validator_ver, "vertical")

        self.ui.stop_button.button.clicked.connect(self.on_stop)

        self.ui.step_decrease_hor.clicked.connect(self.on_step_dec_hor)
        self.ui.step_decrease_ver.clicked.connect(self.on_step_dec_ver)
        self.ui.step_increase_hor.clicked.connect(self.on_step_inc_hor)
        self.ui.step_increase_ver.clicked.connect(self.on_step_inc_ver)

        self.ui.tool_button_hor.clicked.connect(
            self._open_dialog_selection(self.set_positioner_hor)
        )
        self.ui.tool_button_ver.clicked.connect(
            self._open_dialog_selection(self.set_positioner_ver)
        )
        icon = material_icon(icon_name="edit_note", size=(16, 16), convert_to_pixmap=False)
        self.ui.tool_button_hor.setIcon(icon)
        self.ui.tool_button_ver.setIcon(icon)

        step_tooltip = "Step by the step size"
        tweak_tooltip = "Tweak by 1/10th the step size"

        for b in [
            self.ui.step_increase_hor,
            self.ui.step_increase_ver,
            self.ui.step_decrease_hor,
            self.ui.step_decrease_ver,
        ]:
            b.setToolTip(step_tooltip)

        for b in [
            self.ui.tweak_increase_hor,
            self.ui.tweak_increase_ver,
            self.ui.tweak_decrease_hor,
            self.ui.tweak_decrease_ver,
        ]:
            b.setToolTip(tweak_tooltip)

        icon_options = {"size": (16, 16), "convert_to_pixmap": False}
        self.ui.tweak_increase_hor.setIcon(
            material_icon(icon_name="keyboard_arrow_right", **icon_options)
        )
        self.ui.step_increase_hor.setIcon(
            material_icon(icon_name="keyboard_double_arrow_right", **icon_options)
        )
        self.ui.tweak_decrease_hor.setIcon(
            material_icon(icon_name="keyboard_arrow_left", **icon_options)
        )
        self.ui.step_decrease_hor.setIcon(
            material_icon(icon_name="keyboard_double_arrow_left", **icon_options)
        )
        self.ui.tweak_increase_ver.setIcon(
            material_icon(icon_name="keyboard_arrow_up", **icon_options)
        )
        self.ui.step_increase_ver.setIcon(
            material_icon(icon_name="keyboard_double_arrow_up", **icon_options)
        )
        self.ui.tweak_decrease_ver.setIcon(
            material_icon(icon_name="keyboard_arrow_down", **icon_options)
        )
        self.ui.step_decrease_ver.setIcon(
            material_icon(icon_name="keyboard_double_arrow_down", **icon_options)
        )

    @SafeProperty(str)
    def device_hor(self):
        """SafeProperty to set the device"""
        return self._device_hor

    @device_hor.setter
    def device_hor(self, value: str):
        """Setter, checks if device is a string"""
        if not value or not isinstance(value, str):
            return
        if not self._check_device_is_valid(value):
            return
        if value == self.device_ver:
            return
        old_device = self._device_hor
        self._device_hor = value
        self.label = f"{self._device_hor}, {self._device_ver}"
        self.device_changed_hor.emit(old_device, value)
        self._init_device(self.device_hor, self.position_update_hor.emit, self.update_limits_hor)

    @SafeProperty(str)
    def device_ver(self):
        """SafeProperty to set the device"""
        return self._device_ver

    @device_ver.setter
    def device_ver(self, value: str):
        """Setter, checks if device is a string"""
        if not value or not isinstance(value, str):
            return
        if not self._check_device_is_valid(value):
            return
        if value == self.device_hor:
            return
        old_device = self._device_ver
        self._device_ver = value
        self.label = f"{self._device_hor}, {self._device_ver}"
        self.device_changed_ver.emit(old_device, value)
        self._init_device(self.device_ver, self.position_update_ver.emit, self.update_limits_ver)

    @SafeProperty(bool)
    def hide_device_selection(self):
        """Hide the device selection"""
        return not self.ui.tool_button_hor.isVisible()

    @hide_device_selection.setter
    def hide_device_selection(self, value: bool):
        """Set the device selection visibility"""
        self.ui.tool_button_hor.setVisible(not value)
        self.ui.tool_button_ver.setVisible(not value)

    @SafeProperty(bool)
    def hide_device_boxes(self):
        """Hide the device selection"""
        return not self.ui.device_box_hor.isVisible()

    @hide_device_boxes.setter
    def hide_device_boxes(self, value: bool):
        """Set the device selection visibility"""
        self.ui.device_box_hor.setVisible(not value)
        self.ui.device_box_ver.setVisible(not value)

    @SafeSlot(bool)
    def show_device_selection(self, value: bool):
        """Show the device selection

        Args:
            value (bool): Show the device selection
        """
        self.hide_device_selection = not value

    @SafeSlot(str)
    def set_positioner_hor(self, positioner: str | Positioner):
        """Set the device

        Args:
            positioner (Positioner | str) : Positioner to set, accepts str or the device
        """
        if isinstance(positioner, Positioner):
            positioner = positioner.name
        self.device_hor = positioner

    @SafeSlot(str)
    def set_positioner_ver(self, positioner: str | Positioner):
        """Set the device

        Args:
            positioner (Positioner | str) : Positioner to set, accepts str or the device
        """
        if isinstance(positioner, Positioner):
            positioner = positioner.name
        self.device_ver = positioner

    @SafeSlot(str, str)
    def on_device_change_hor(self, old_device: str, new_device: str):
        """Upon changing the device, a check will be performed if the device is a Positioner.

        Args:
            old_device (str): The old device name.
            new_device (str): The new device name.
        """
        if not self._check_device_is_valid(new_device):
            return
        self._on_device_change(
            old_device,
            new_device,
            self.position_update_hor.emit,
            self.update_limits_hor,
            self.on_device_readback_hor,
            self._device_ui_components_hv("horizontal"),
        )

    @SafeSlot(str, str)
    def on_device_change_ver(self, old_device: str, new_device: str):
        """Upon changing the device, a check will be performed if the device is a Positioner.

        Args:
            old_device (str): The old device name.
            new_device (str): The new device name.
        """
        if not self._check_device_is_valid(new_device):
            return
        self._on_device_change(
            old_device,
            new_device,
            self.position_update_ver.emit,
            self.update_limits_ver,
            self.on_device_readback_ver,
            self._device_ui_components_hv("vertical"),
        )

    def _device_ui_components_hv(self, device: DeviceId) -> DeviceUpdateUIComponents:
        if device == "horizontal":
            return {
                "spinner": self.ui.spinner_widget_hor,
                "position_indicator": self.ui.position_indicator_hor,
                "readback": self.ui.readback_hor,
                "setpoint": self.ui.setpoint_hor,
                "step_size": self.ui.step_size_hor,
                "device_box": self.ui.device_box_hor,
                "stop": self.ui.stop_button,
                "tweak_increase": self.ui.tweak_increase_hor,
                "tweak_decrease": self.ui.tweak_decrease_hor,
                "units": self.ui.units_hor,
            }
        elif device == "vertical":
            return {
                "spinner": self.ui.spinner_widget_ver,
                "position_indicator": self.ui.position_indicator_ver,
                "readback": self.ui.readback_ver,
                "setpoint": self.ui.setpoint_ver,
                "step_size": self.ui.step_size_ver,
                "device_box": self.ui.device_box_ver,
                "stop": self.ui.stop_button,
                "tweak_increase": self.ui.tweak_increase_ver,
                "tweak_decrease": self.ui.tweak_decrease_ver,
                "units": self.ui.units_ver,
            }
        else:
            raise ValueError(f"Device {device} is not represented by this UI")

    def _device_ui_components(self, device: str):
        if device == self.device_hor:
            return self._device_ui_components_hv("horizontal")
        if device == self.device_ver:
            return self._device_ui_components_hv("vertical")

    @SafeSlot(dict, dict)
    def on_device_readback_hor(self, msg_content: dict, metadata: dict):
        """Callback for device readback.

        Args:
            msg_content (dict): The message content.
            metadata (dict): The message metadata.
        """
        self._on_device_readback(
            self.device_hor,
            self._device_ui_components_hv("horizontal"),
            msg_content,
            metadata,
            self.position_update_hor.emit,
            self.update_limits_hor,
        )

    @SafeSlot(dict, dict)
    def on_device_readback_ver(self, msg_content: dict, metadata: dict):
        """Callback for device readback.

        Args:
            msg_content (dict): The message content.
            metadata (dict): The message metadata.
        """
        self._on_device_readback(
            self.device_ver,
            self._device_ui_components_hv("vertical"),
            msg_content,
            metadata,
            self.position_update_ver.emit,
            self.update_limits_ver,
        )

    def update_limits_hor(self, limits: tuple):
        """Update limits

        Args:
            limits (tuple): Limits of the positioner
        """
        if limits == self._limits_hor:
            return
        self._limits_hor = limits
        self._update_limits_ui(limits, self.ui.position_indicator_hor, self.setpoint_validator_hor)

    def update_limits_ver(self, limits: tuple):
        """Update limits

        Args:
            limits (tuple): Limits of the positioner
        """
        if limits == self._limits_ver:
            return
        self._limits_ver = limits
        self._update_limits_ui(limits, self.ui.position_indicator_ver, self.setpoint_validator_ver)

    @SafeSlot()
    def on_stop(self):
        self._stop_device(f"{self.device_hor} or {self.device_ver}")

    @SafeProperty(float)
    def step_size_hor(self):
        """Step size for tweak"""
        return self.ui.step_size_hor.value()

    @step_size_hor.setter
    def step_size_hor(self, val: float):
        """Step size for tweak"""
        self.ui.step_size_hor.setValue(val)

    @SafeProperty(float)
    def step_size_ver(self):
        """Step size for tweak"""
        return self.ui.step_size_ver.value()

    @step_size_ver.setter
    def step_size_ver(self, val: float):
        """Step size for tweak"""
        self.ui.step_size_ver.setValue(val)

    @SafeSlot()
    def on_tweak_inc_hor(self):
        """Tweak device a up"""
        self.dev[self.device_hor].move(self.step_size_hor / 10, relative=True)

    @SafeSlot()
    def on_tweak_dec_hor(self):
        """Tweak device a down"""
        self.dev[self.device_hor].move(-self.step_size_hor / 10, relative=True)

    @SafeSlot()
    def on_step_inc_hor(self):
        """Tweak device a up"""
        self.dev[self.device_hor].move(self.step_size_hor, relative=True)

    @SafeSlot()
    def on_step_dec_hor(self):
        """Tweak device a down"""
        self.dev[self.device_hor].move(-self.step_size_hor, relative=True)

    @SafeSlot()
    def on_tweak_inc_ver(self):
        """Tweak device a up"""
        self.dev[self.device_ver].move(self.step_size_ver / 10, relative=True)

    @SafeSlot()
    def on_tweak_dec_ver(self):
        """Tweak device b down"""
        self.dev[self.device_ver].move(-self.step_size_ver / 10, relative=True)

    @SafeSlot()
    def on_step_inc_ver(self):
        """Tweak device b up"""
        self.dev[self.device_ver].move(self.step_size_ver, relative=True)

    @SafeSlot()
    def on_step_dec_ver(self):
        """Tweak device a down"""
        self.dev[self.device_ver].move(-self.step_size_ver, relative=True)

    @SafeSlot()
    def on_setpoint_change_hor(self):
        """Change the setpoint for device a"""
        self.ui.setpoint_hor.clearFocus()
        setpoint = self.ui.setpoint_hor.text()
        self.dev[self.device_hor].move(float(setpoint), relative=False)

    @SafeSlot()
    def on_setpoint_change_ver(self):
        """Change the setpoint for device b"""
        self.ui.setpoint_ver.clearFocus()
        setpoint = self.ui.setpoint_ver.text()
        self.dev[self.device_ver].move(float(setpoint), relative=False)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication  # pylint: disable=ungrouped-imports

    app = QApplication(sys.argv)
    set_theme("dark")
    widget = PositionerBox2D()

    widget.show()
    sys.exit(app.exec_())
