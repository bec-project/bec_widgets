from bec_lib.callback_handler import EventType
from bec_lib.device import ReadoutPriority
from qtpy.QtCore import QSize, Signal, Slot
from qtpy.QtGui import QPainter, QPaintEvent, QPen
from qtpy.QtWidgets import QComboBox, QSizePolicy

from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.widgets.control.device_input.base_classes.device_input_base import (
    BECDeviceFilter,
    DeviceInputBase,
    DeviceInputConfig,
)


class DeviceComboBox(DeviceInputBase, QComboBox):
    """
    Combobox widget for device input with autocomplete for device names.

    Args:
        parent: Parent widget.
        client: BEC client object.
        config: Device input configuration.
        gui_id: GUI ID.
        device_filter: Device filter, name of the device class from BECDeviceFilter and BECReadoutPriority. Check DeviceInputBase for more details.
        readout_priority_filter: Readout priority filter, name of the readout priority class from BECDeviceFilter and BECReadoutPriority. Check DeviceInputBase for more details.
        available_devices: List of available devices, if passed, it sets apply filters to false and device/readout priority filters will not be applied.
        default: Default device name.
        arg_name: Argument name, can be used for the other widgets which has to call some other function in bec using correct argument names.
    """

    USER_ACCESS = ["set_device", "devices"]

    ICON_NAME = "list_alt"
    PLUGIN = True

    device_selected = Signal(str)
    device_reset = Signal()
    device_config_update = Signal()

    def __init__(
        self,
        parent=None,
        client=None,
        config: DeviceInputConfig = None,
        gui_id: str | None = None,
        device_filter: BECDeviceFilter | list[BECDeviceFilter] | None = None,
        readout_priority_filter: (
            str | ReadoutPriority | list[str] | list[ReadoutPriority] | None
        ) = None,
        available_devices: list[str] | None = None,
        default: str | None = None,
        arg_name: str | None = None,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        if arg_name is not None:
            self.config.arg_name = arg_name
            self.arg_name = arg_name
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumSize(QSize(100, 0))
        self._callback_id = None
        self._is_valid_input = False
        self._accent_colors = get_accent_colors()
        # We do not consider the config that is passed here, this produced problems
        # with QtDesigner, since config and input arguments may differ and resolve properly
        # Implementing this logic and config recoverage is postponed.
        # Set available devices if passed
        if available_devices is not None:
            self.set_available_devices(available_devices)
        # Set readout priority filter default is all
        if readout_priority_filter is not None:
            self.set_readout_priority_filter(readout_priority_filter)
        else:
            self.set_readout_priority_filter(
                [
                    ReadoutPriority.MONITORED,
                    ReadoutPriority.BASELINE,
                    ReadoutPriority.ASYNC,
                    ReadoutPriority.CONTINUOUS,
                    ReadoutPriority.ON_REQUEST,
                ]
            )
        # Device filter default is None
        if device_filter is not None:
            self.set_device_filter(device_filter)
        # Set default device if passed
        if default is not None:
            self.set_device(default)
        self._callback_id = self.bec_dispatcher.client.callbacks.register(
            EventType.DEVICE_UPDATE, self.on_device_update
        )
        self.device_config_update.connect(self.update_devices_from_filters)
        self.currentTextChanged.connect(self.check_validity)
        self.check_validity(self.currentText())

    def on_device_update(self, action: str, content: dict) -> None:
        """
        Callback for device update events. Triggers the device_update signal.

        Args:
            action (str): The action that triggered the event.
            content (dict): The content of the config update.
        """
        if action in ["add", "remove", "reload"]:
            self.device_config_update.emit()

    def cleanup(self):
        """Cleanup the widget."""
        if self._callback_id is not None:
            self.bec_dispatcher.client.callbacks.remove(self._callback_id)
        super().cleanup()

    def get_current_device(self) -> object:
        """
        Get the current device object based on the current value.

        Returns:
            object: Device object, can be device of type Device, Positioner, Signal or ComputedSignal.
        """
        dev_name = self.currentText()
        return self.get_device_object(dev_name)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Extend the paint event to set the border color based on the validity of the input.

        Args:
            event (PySide6.QtGui.QPaintEvent) : Paint event.
        """
        # logger.info(f"Received paint event: {event} in {self.__class__}")
        super().paintEvent(event)

        if self._is_valid_input is False and self.isEnabled() is True:
            painter = QPainter(self)
            pen = QPen()
            pen.setWidth(2)
            pen.setColor(self._accent_colors.emergency)
            painter.setPen(pen)
            painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
            painter.end()

    @Slot(str)
    def check_validity(self, input_text: str) -> None:
        """
        Check if the current value is a valid device name.
        """
        if self.validate_device(input_text) is True:
            self._is_valid_input = True
            self.device_selected.emit(input_text)
        else:
            self._is_valid_input = False
            self.device_reset.emit()
        self.update()

    def validate_device(self, device: str) -> bool:  # type: ignore[override]
        """
        Extend validation so that preview‑signal pseudo‑devices (labels like
        ``"eiger_preview"``) are accepted as valid choices.

        The validation run only on device not on the preview‑signal.

        Args:
            device: The text currently entered/selected.

        Returns:
            True if the device is a genuine BEC device *or* one of the
            whitelisted preview‑signal entries.
        """
        idx = self.findText(device)
        if idx >= 0 and isinstance(self.itemData(idx), tuple):
            device = self.itemData(idx)[0]  # type: ignore[assignment]
        return super().validate_device(device)


if __name__ == "__main__":  # pragma: no cover
    # pylint: disable=import-outside-toplevel
    from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

    from bec_widgets.utils.colors import set_theme

    app = QApplication([])
    set_theme("dark")
    widget = QWidget()
    widget.setFixedSize(200, 200)
    layout = QVBoxLayout()
    widget.setLayout(layout)
    combo = DeviceComboBox()
    combo.devices = ["samx", "dev1", "dev2", "dev3", "dev4"]
    layout.addWidget(combo)
    widget.show()
    app.exec_()
