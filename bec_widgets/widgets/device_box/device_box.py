import os
import uuid

from bec_lib.device import Positioner
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import ScanQueueMessage
from qtpy.QtCore import Property, Signal, Slot
from qtpy.QtGui import QDoubleValidator
from qtpy.QtWidgets import QDoubleSpinBox, QVBoxLayout, QWidget

from bec_widgets.utils import UILoader
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme


class DeviceBox(BECWidget, QWidget):
    device_changed = Signal(str, str)

    def __init__(self, parent=None, device: Positioner = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QWidget.__init__(self, parent=parent)
        self.get_bec_shortcuts()
        self._device = ""
        self._limits = None

        self.init_ui()

        if device is not None:
            self.device = device
            self.init_device()

    def init_ui(self):
        self.device_changed.connect(self.on_device_change)

        current_path = os.path.dirname(__file__)
        self.ui = UILoader(self).loader(os.path.join(current_path, "device_box.ui"))

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
        if self.device in self.dev and isinstance(self.dev[self.device], Positioner):
            data = self.dev[self.device].read()
            self.on_device_readback({"signals": data}, {})

    def _toogle_enable_buttons(self, enable: bool) -> None:
        self.ui.tweak_left.setEnabled(enable)
        self.ui.tweak_right.setEnabled(enable)
        self.ui.stop.setEnabled(enable)
        self.ui.setpoint.setEnabled(enable)
        self.ui.step_size.setEnabled(enable)

    @Property(str)
    def device(self):
        return self._device

    @device.setter
    def device(self, value: str):
        if not value or not isinstance(value, str):
            return
        old_device = self._device
        self._device = value
        self.device_changed.emit(old_device, value)

    @Slot(str, str)
    def on_device_change(self, old_device: str, new_device: str):
        if new_device not in self.dev:
            print(f"Device {new_device} not found in the device list")
            return
        if not isinstance(self.dev[new_device], Positioner):
            print(f"Device {new_device} is not a positioner")
            return
        print(f"Device changed from {old_device} to {new_device}")
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

    def update_limits(self, limits):
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
        return self.ui.step_size.value()

    @Slot()
    def on_tweak_right(self):
        self.dev[self.device].move(self.step_size, relative=True)

    @Slot()
    def on_tweak_left(self):
        self.dev[self.device].move(-self.step_size, relative=True)

    @Slot()
    def on_setpoint_change(self):
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
    widget = DeviceBox(device="bpm4i")

    widget.show()
    sys.exit(app.exec_())
