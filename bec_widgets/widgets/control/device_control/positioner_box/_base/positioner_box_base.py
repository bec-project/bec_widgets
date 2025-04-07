import uuid
from abc import abstractmethod
from typing import Callable, TypedDict

from bec_lib.device import Positioner
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import ScanQueueMessage
from qtpy.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.compact_popup import CompactPopupWidget
from bec_widgets.widgets.control.device_control.position_indicator.position_indicator import (
    PositionIndicator,
)
from bec_widgets.widgets.control.device_input.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.control.device_input.device_line_edit.device_line_edit import (
    DeviceLineEdit,
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


class PositionerBoxBase(BECWidget, CompactPopupWidget):
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
        super().__init__(parent=parent, layout=QVBoxLayout, **kwargs)
        self._dialog = None
        self.get_bec_shortcuts()

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
        if self._check_device_is_valid(device):
            data = self.dev[device].read()
            self._on_device_readback(
                device,
                self._device_ui_components(device),
                {"signals": data},
                {},
                position_emit,
                limit_update,
            )

    def _stop_device(self, device: str):
        """Stop call"""
        request_id = str(uuid.uuid4())
        params = {"device": device, "rpc_id": request_id, "func": "stop", "args": [], "kwargs": {}}
        msg = ScanQueueMessage(
            scan_type="device_rpc",
            parameter=params,
            queue="emergency",
            metadata={"RID": request_id, "response": False},
        )
        self.client.connector.send(MessageEndpoints.scan_queue_request(), msg)

    # pylint: disable=unused-argument
    def _on_device_readback(
        self,
        device: str,
        ui_components: DeviceUpdateUIComponents,
        msg_content: dict,
        metadata: dict,
        position_emit: Callable[[float], None],
        limit_update: Callable[[tuple[float, float]], None],
    ):
        signals = msg_content.get("signals", {})
        # pylint: disable=protected-access
        hinted_signals = self.dev[device]._hints
        precision = self.dev[device].precision

        spinner = ui_components["spinner"]
        position_indicator = ui_components["position_indicator"]
        readback = ui_components["readback"]
        setpoint = ui_components["setpoint"]

        readback_val = None
        setpoint_val = None

        if len(hinted_signals) == 1:
            signal = hinted_signals[0]
            readback_val = signals.get(signal, {}).get("value")

        for setpoint_signal in ["setpoint", "user_setpoint"]:
            setpoint_val = signals.get(f"{device}_{setpoint_signal}", {}).get("value")
            if setpoint_val is not None:
                break

        if f"{device}_motor_done_move" in signals:
            is_moving = not signals[f"{device}_motor_done_move"].get("value")
        elif f"{device}_motor_is_moving" in signals:
            is_moving = signals[f"{device}_motor_is_moving"].get("value")
        else:
            is_moving = None

        if is_moving is not None:
            spinner.setVisible(True)
            if is_moving:
                spinner.start()
                spinner.setToolTip("Device is moving")
                self.set_global_state("warning")
            else:
                spinner.stop()
                spinner.setToolTip("Device is idle")
                self.set_global_state("success")
        else:
            spinner.setVisible(False)

        if readback_val is not None:
            readback.setText(f"{readback_val:.{precision}f}")
            position_emit(readback_val)

        if setpoint_val is not None:
            setpoint.setText(f"{setpoint_val:.{precision}f}")

        limits = self.dev[device].limits
        limit_update(limits)
        if limits is not None and readback_val is not None and limits[0] != limits[1]:
            pos = (readback_val - limits[0]) / (limits[1] - limits[0])
            position_indicator.set_value(pos)

    def _update_limits_ui(
        self, limits: tuple[float, float], position_indicator, setpoint_validator
    ):
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
        precision = self.dev[device].precision
        if precision is not None:
            ui["step_size"].setDecimals(precision)
            ui["step_size"].setValue(10**-precision * 10)

    def _swap_readback_signal_connection(self, slot, old_device, new_device):
        self.bec_dispatcher.disconnect_slot(slot, MessageEndpoints.device_readback(old_device))
        self.bec_dispatcher.connect_slot(slot, MessageEndpoints.device_readback(new_device))

    def _toggle_enable_buttons(self, ui: DeviceUpdateUIComponents, enable: bool) -> None:
        """Toogle enable/disable on available buttons

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
        on_device_readback: Callable,
        ui: DeviceUpdateUIComponents,
    ):
        logger.info(f"Device changed from {old_device} to {new_device}")
        self._toggle_enable_buttons(ui, True)
        self._init_device(new_device, position_emit, limit_update)
        self._swap_readback_signal_connection(on_device_readback, old_device, new_device)
        self._update_device_ui(new_device, ui)

    def _open_dialog_selection(self, set_positioner: Callable):
        def _ods():
            """Open dialog window for positioner selection"""
            self._dialog = QDialog(self)
            self._dialog.setWindowTitle("Positioner Selection")
            layout = QVBoxLayout()
            line_edit = DeviceLineEdit(
                self, client=self.client, device_filter=[BECDeviceFilter.POSITIONER]
            )
            line_edit.textChanged.connect(set_positioner)
            layout.addWidget(line_edit)
            close_button = QPushButton("Close")
            close_button.clicked.connect(self._dialog.accept)
            layout.addWidget(close_button)
            self._dialog.setLayout(layout)
            self._dialog.exec()
            self._dialog = None

        return _ods
