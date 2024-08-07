""" Module for a PositionerBox widget to control a positioner device."""

import os
import uuid

from bec_lib.device import Positioner
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import ScanQueueMessage
from qtpy.QtCore import Property, Signal, Slot
from qtpy.QtGui import QDoubleValidator
from qtpy.QtWidgets import QDoubleSpinBox, QVBoxLayout, QWidget

from bec_widgets.utils import UILoader
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme

logger = bec_logger.logger


class PositionerBox(BECWidget, QWidget):
    """Simple Widget to control a positioner in box form"""

    USER_ACCESS = ["set_positioner"]
    device_changed = Signal(str, str)

    def __init__(self, parent=None, device: Positioner = None, *args, **kwargs):
        """Initialize the PositionerBox widget.

        Args:
            parent: The parent widget.
            device (Positioner): The device to control.
        """
        super().__init__(**kwargs)
        QWidget.__init__(self, parent=parent)
        self.get_bec_shortcuts()
        self._device = ""
        self._limits = None

        self.init_ui()

        if device is not None:
            self.device = device
            self.init_device()

    def init_ui(self):
        """Init the ui"""
        self.device_changed.connect(self.on_device_change)

        current_path = os.path.dirname(__file__)
        self.ui = UILoader(self).loader(os.path.join(current_path, "positioner_box.ui"))

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.ui)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # fix the size of the device box
        db = self.ui.device_box
        db.setFixedHeight(234)
        db.setFixedWidth(224)

        self.ui.step_size.setStepType(QDoubleSpinBox.AdaptiveDecimalStepType)
        self.ui.stop.clicked.connect(self.on_stop)
        self.ui.tweak_right.clicked.connect(self.on_tweak_right)
        self.ui.tweak_right.setToolTip("Tweak right")
        self.ui.tweak_left.clicked.connect(self.on_tweak_left)
        self.ui.tweak_left.setToolTip("Tweak left")
        self.ui.setpoint.returnPressed.connect(self.on_setpoint_change)

        self.setpoint_validator = QDoubleValidator()
        self.ui.setpoint.setValidator(self.setpoint_validator)
        self.ui.spinner_widget.start()

    def init_device(self):
        """Init the device view and readback"""
        if self._check_device_is_valid(self.device):
            data = self.dev[self.device].read()
            self.on_device_readback({"signals": data}, {})

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
        old_device = self._device
        self._device = value
        self.device_changed.emit(old_device, value)

    def set_positioner(self, positioner: str):
        """Set the device

        Args:
            positioner (Positioner | str) : Positioner to set, accepts str or the device
        """
        if isinstance(positioner, Positioner):
            positioner = positioner.name
        self.device = positioner

    def _check_device_is_valid(self, device: str):
        """Check if the device is a positioner

        Args:
            device (str): The device name
        """
        if device not in self.dev:
            logger.info(f"Device {device} not found in the device list")
            return False
        if not isinstance(self.dev[device], Positioner):
            logger.info(f"Device {device} is not a positioner")
            return False
        return True

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
        self.init_device()
        self.bec_dispatcher.disconnect_slot(
            self.on_device_readback, MessageEndpoints.device_readback(old_device)
        )
        self.bec_dispatcher.connect_slot(
            self.on_device_readback, MessageEndpoints.device_readback(new_device)
        )
        self.ui.device_box.setTitle(new_device)
        self.ui.readback.setToolTip(f"{self.device} readback")
        self.ui.setpoint.setToolTip(f"{self.device} setpoint")
        self.ui.step_size.setToolTip(f"Step size for {new_device}")

        precision = self.dev[new_device].precision
        if precision is not None:
            self.ui.step_size.setDecimals(precision)
            self.ui.step_size.setValue(10**-precision * 10)

    @Slot(dict, dict)
    def on_device_readback(self, msg_content: dict, metadata: dict):
        """Callback for device readback.

        Args:
            msg_content (dict): The message content.
            metadata (dict): The message metadata.
        """
        signals = msg_content.get("signals", {})
        # pylint: disable=protected-access
        hinted_signals = self.dev[self.device]._hints
        precision = self.dev[self.device].precision

        readback_val = None
        setpoint_val = None

        if len(hinted_signals) == 1:
            signal = hinted_signals[0]
            readback_val = signals.get(signal, {}).get("value")

        if f"{self.device}_setpoint" in signals:
            setpoint_val = signals.get(f"{self.device}_setpoint", {}).get("value")

        if f"{self.device}_motor_is_moving" in signals:
            is_moving = signals.get(f"{self.device}_motor_is_moving", {}).get("value")
            if is_moving:
                self.ui.spinner_widget.start()
                self.ui.spinner_widget.setToolTip("Device is moving")
            else:
                self.ui.spinner_widget.stop()
                self.ui.spinner_widget.setToolTip("Device is idle")

        if readback_val is not None:
            self.ui.readback.setText(f"{readback_val:.{precision}f}")

        if setpoint_val is not None:
            self.ui.setpoint.setText(f"{setpoint_val:.{precision}f}")

        limits = self.dev[self.device].limits
        self.update_limits(limits)
        if limits is not None and readback_val is not None and limits[0] != limits[1]:
            pos = (readback_val - limits[0]) / (limits[1] - limits[0])
            self.ui.position_indicator.on_position_update(pos)

    def update_limits(self, limits: tuple):
        """Update limits

        Args:
            limits (tuple): Limits of the positioner
        """
        if limits == self._limits:
            return
        self._limits = limits
        if limits is not None and limits[0] != limits[1]:
            self.ui.position_indicator.setToolTip(f"Min: {limits[0]}, Max: {limits[1]}")
            self.setpoint_validator.setRange(limits[0], limits[1])
        else:
            self.ui.position_indicator.setToolTip("No limits set")
            self.setpoint_validator.setRange(float("-inf"), float("inf"))

    @Slot()
    def on_stop(self):
        """Stop call"""
        request_id = str(uuid.uuid4())
        params = {
            "device": self.device,
            "rpc_id": request_id,
            "func": "stop",
            "args": [],
            "kwargs": {},
        }
        msg = ScanQueueMessage(
            scan_type="device_rpc",
            parameter=params,
            queue="emergency",
            metadata={"RID": request_id, "response": False},
        )
        self.client.connector.send(MessageEndpoints.scan_queue_request(), msg)

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

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    apply_theme("light")
    widget = PositionerBox(device="bpm4i")

    widget.show()
    sys.exit(app.exec_())
