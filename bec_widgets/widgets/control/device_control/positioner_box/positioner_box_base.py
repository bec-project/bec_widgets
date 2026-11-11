from abc import abstractmethod
from typing import Callable, Sequence, TypedDict

from bec_lib.data_api import SubscriptionUpdate
from bec_lib.device import Positioner
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import VariableMessage
from qtpy.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.qt_data_subscription import QtDataSubscription
from bec_widgets.widgets.control.device_control.position_indicator.position_indicator import (
    PositionIndicator,
)
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import (
    BECDeviceFilter,
    DeviceComboBox,
)
from bec_widgets.widgets.utility.spinner.spinner import SpinnerWidget

logger = bec_logger.logger


class DeviceUpdateUIComponents(TypedDict):
    spinner: SpinnerWidget
    setpoint: QLineEdit
    readback: QLabel
    position_indicator: PositionIndicator
    step_size: QDoubleSpinBox
    device_box: QGroupBox
    stop: QPushButton
    tweak_increase: QPushButton
    tweak_decrease: QPushButton
    units: QLabel


class PositionerBoxBase(BECWidget, QWidget):
    """Contains some core logic for positioner box widgets"""

    current_path = ""
    ICON_NAME = "switch_right"
    RPC = False

    def __init__(self, parent=None, **kwargs):
        """Initialize the PositionerBox widget.

        Args:
            parent: The parent widget.
            device (Positioner): The device to control.
        """
        super().__init__(parent=parent, **kwargs)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self._dialog = None
        self.get_bec_shortcuts()
        self._readback_subscriptions: dict[QLabel, QtDataSubscription] = {}
        self._device_values: dict[str, dict] = {}
        self._device_roles: dict[str, dict[str, str]] = {}

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

    @abstractmethod
    def _device_ui_components(self, device: str) -> DeviceUpdateUIComponents: ...

    def _init_device(
        self,
        device: str,
        position_emit: Callable[[float], None],
        limit_update: Callable[[tuple[float, float]], None],
    ):
        """Init the device view and readback"""
        if not self._check_device_is_valid(device):
            return

        ui = self._device_ui_components(device)
        previous = self._readback_subscriptions.pop(ui["readback"], None)
        if previous is not None:
            previous.close()
            previous.deleteLater()
        self._device_values[device] = {}
        ui["readback"].setText("__")
        ui["setpoint"].clear()
        ui["spinner"].stop()
        ui["spinner"].hide()
        limit_update(self.dev[device].limits)
        roles = {}
        for component, info in self.dev[device]._info.get("signals", {}).items():
            role = info.get("component_name", component)
            if role in {"setpoint", "user_setpoint", "motor_done_move", "motor_is_moving"}:
                entry = info.get("obj_name")
                if entry:
                    roles[role] = entry
        self._device_roles[device] = roles
        entries = list(dict.fromkeys([*self.dev[device]._hints, *roles.values()]))
        if entries:
            subscription = QtDataSubscription(
                self.client,
                sources=[(device, entry) for entry in entries],
                scan=None,
                parent=self,
                max_points=1,
            )
            subscription.updated.connect(
                lambda update: self._on_device_update(
                    device, ui, update, position_emit, limit_update
                )
            )
            self._readback_subscriptions[ui["readback"]] = subscription

        if not ui.get("units"):
            return

        try:
            egu = f"[{self.dev[device].egu()}]"
        except Exception:
            egu = ""

        if egu:
            ui["units"].setVisible(True)
            ui["units"].setText(egu)
        else:
            ui["units"].setVisible(False)

    def _stop_device(self, device: str | Sequence[str]):
        """Stop call"""
        devices = [device] if isinstance(device, str) else list(device)
        devices = [dev for dev in devices if dev]
        if not devices:
            logger.warning("Stop requested without a valid device.")
            return

        msg = VariableMessage(value=devices)
        self.client.connector.send(MessageEndpoints.stop_devices(), msg)

    def _on_device_update(
        self,
        device: str,
        ui_components: DeviceUpdateUIComponents,
        update: SubscriptionUpdate,
        position_emit: Callable[[float], None],
        limit_update: Callable[[tuple[float, float]], None],
    ):
        signals = self._device_values.setdefault(device, {})
        for (source_device, entry), source in update.sources.items():
            if source_device == device and len(source.values):
                signals[entry] = source.values[-1]
        # pylint: disable=protected-access
        hinted_signals = self.dev[device]._hints
        precision = getattr(self.dev[device], "precision", 8)
        try:
            precision = int(precision)
        except (TypeError, ValueError):
            precision = int(8)

        spinner = ui_components["spinner"]
        position_indicator = ui_components["position_indicator"]
        readback = ui_components["readback"]
        setpoint = ui_components["setpoint"]

        readback_val = None
        setpoint_val = None

        if len(hinted_signals) == 1:
            signal = hinted_signals[0]
            readback_val = signals.get(signal)

        roles = self._device_roles.get(device, {})
        for setpoint_signal in ["setpoint", "user_setpoint"]:
            setpoint_val = signals.get(roles.get(setpoint_signal))
            if setpoint_val is not None:
                break

        if roles.get("motor_done_move") in signals:
            is_moving = not signals[roles["motor_done_move"]]
        elif roles.get("motor_is_moving") in signals:
            is_moving = signals[roles["motor_is_moving"]]
        else:
            is_moving = None

        if is_moving is not None:
            spinner.setVisible(True)
            if is_moving:
                spinner.start()
                spinner.setToolTip("Device is moving")
            else:
                spinner.stop()
                spinner.setToolTip("Device is idle")
        else:
            spinner.setVisible(False)

        if readback_val is not None:
            text = f"{readback_val:.{precision}f}"
            readback.setText(text)
            position_emit(readback_val)

        if setpoint_val is not None:
            text = f"{setpoint_val:.{precision}f}"
            setpoint.setText(text)

        limits = self.dev[device].limits
        limit_update(limits)
        if limits is not None and readback_val is not None and limits[0] != limits[1]:
            pos = (readback_val - limits[0]) / (limits[1] - limits[0])
            position_indicator.set_value(pos)

    @staticmethod
    def _update_limits_ui(limits: tuple[float, float], position_indicator, setpoint_validator):
        if limits is not None and limits[0] != limits[1]:
            position_indicator.setToolTip(f"Min: {limits[0]}, Max: {limits[1]}")
            setpoint_validator.setRange(limits[0], limits[1])
        else:
            position_indicator.setToolTip("No limits set")
            setpoint_validator.setRange(float("-inf"), float("inf"))

    def _update_device_ui(self, device: str, ui: DeviceUpdateUIComponents):
        ui["device_box"].setTitle(device)
        ui["readback"].setToolTip(f"{device} readback")
        ui["setpoint"].setToolTip(f"{device} setpoint")
        ui["step_size"].setToolTip(f"Step size for {device}")
        precision = getattr(self.dev[device], "precision", 8)
        try:
            precision = int(precision)
        except (TypeError, ValueError):
            precision = int(8)
        ui["step_size"].setDecimals(precision)
        ui["step_size"].setValue(10**-precision * 10)

    @staticmethod
    def _toggle_enable_buttons(ui: DeviceUpdateUIComponents, enable: bool) -> None:
        """Toggle enable/disable on available buttons

        Args:
            enable (bool): Enable buttons
        """
        ui["tweak_increase"].setEnabled(enable)
        ui["tweak_decrease"].setEnabled(enable)
        ui["stop"].setEnabled(enable)
        ui["setpoint"].setEnabled(enable)
        ui["step_size"].setEnabled(enable)

    def _on_device_change(
        self,
        old_device: str,
        new_device: str,
        position_emit: Callable[[float], None],
        limit_update: Callable[[tuple[float, float]], None],
        ui: DeviceUpdateUIComponents,
    ):
        logger.info(f"Device changed from {old_device} to {new_device}")
        if not new_device:
            previous = self._readback_subscriptions.pop(ui["readback"], None)
            if previous is not None:
                previous.close()
                previous.deleteLater()
            self._device_values.pop(old_device, None)
            self._device_roles.pop(old_device, None)
            ui["readback"].setText("__")
            ui["setpoint"].clear()
            ui["spinner"].stop()
            ui["spinner"].hide()
            self._toggle_enable_buttons(ui, False)
            return
        self._toggle_enable_buttons(ui, True)
        self._init_device(new_device, position_emit, limit_update)
        if old_device != new_device:
            self._device_values.pop(old_device, None)
            self._device_roles.pop(old_device, None)
        self._update_device_ui(new_device, ui)

    def cleanup(self):
        for subscription in self._readback_subscriptions.values():
            subscription.close()
        self._readback_subscriptions.clear()
        self._device_values.clear()
        self._device_roles.clear()
        super().cleanup()

    def _open_dialog_selection(self, set_positioner: Callable):
        def _ods():
            """Open dialog window for positioner selection"""
            self._dialog = QDialog(self)
            self._dialog.setWindowTitle("Positioner Selection")
            layout = QVBoxLayout()
            line_edit = DeviceComboBox(
                self, client=self.client, device_filter=[BECDeviceFilter.POSITIONER]
            )
            line_edit.currentTextChanged.connect(set_positioner)
            layout.addWidget(line_edit)
            close_button = QPushButton("Close")
            close_button.clicked.connect(self._dialog.accept)
            layout.addWidget(close_button)
            self._dialog.setLayout(layout)
            self._dialog.exec()
            self._dialog = None

        return _ods
