from bec_lib.callback_handler import EventType
from bec_lib.device import ReadoutPriority
from qtpy.QtCore import QSize, Signal, Slot
from qtpy.QtGui import QPainter, QPaintEvent, QPen
from qtpy.QtWidgets import QComboBox, QSizePolicy

from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeProperty
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
        signal_class_filter: List of signal classes to filter the devices by. Only devices with signals of these classes will be shown.
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
        signal_class_filter: list[str] | None = None,
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
        self._set_first_element_as_empty = False

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

        if signal_class_filter is not None:
            self.signal_class_filter = signal_class_filter

        # Set default device if passed
        if default is not None:
            self.set_device(default)
        self._callback_id = self.bec_dispatcher.client.callbacks.register(
            EventType.DEVICE_UPDATE, self.on_device_update
        )
        self.device_config_update.connect(self.update_devices_from_filters)
        self.currentTextChanged.connect(self.check_validity)
        self.check_validity(self.currentText())

    @SafeProperty(bool)
    def set_first_element_as_empty(self) -> bool:
        """
        Whether the first element in the combobox should be empty.
        This is useful to allow the user to select a device from the list.
        """
        return self._set_first_element_as_empty

    @set_first_element_as_empty.setter
    def set_first_element_as_empty(self, value: bool) -> None:
        """
        Set whether the first element in the combobox should be empty.
        This is useful to allow the user to select a device from the list.

        Args:
            value (bool): True if the first element should be empty, False otherwise.
        """
        self._set_first_element_as_empty = value
        if self._set_first_element_as_empty:
            self.insertItem(0, "")
            self.setCurrentIndex(0)
        else:
            if self.count() > 0 and self.itemText(0) == "":
                self.removeItem(0)

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

    @Slot(str)
    def check_validity(self, input_text: str) -> None:
        """
        Check if the current value is a valid device name.
        """
        if self.validate_device(input_text) is True:
            self._is_valid_input = True
            self.device_selected.emit(input_text)
            self.setStyleSheet("border: 1px solid transparent;")
        else:
            self._is_valid_input = False
            self.device_reset.emit()
            if self.isEnabled():
                self.setStyleSheet("border: 1px solid red;")

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
    from qtpy.QtWidgets import (
        QApplication,
        QCheckBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QVBoxLayout,
        QWidget,
    )

    from bec_widgets.utils.colors import apply_theme

    app = QApplication([])
    apply_theme("dark")
    widget = QWidget()
    widget.setWindowTitle("DeviceComboBox demo")
    layout = QVBoxLayout(widget)

    layout.addWidget(QLabel("Device filter controls"))
    controls = QHBoxLayout()
    layout.addLayout(controls)

    class_input = QLineEdit()
    class_input.setPlaceholderText("signal_class_filter (comma-separated), e.g. AsyncSignal")
    controls.addWidget(class_input)

    filter_device = QCheckBox("Device")
    filter_positioner = QCheckBox("Positioner")
    filter_signal = QCheckBox("Signal")
    filter_computed = QCheckBox("ComputedSignal")
    controls.addWidget(filter_device)
    controls.addWidget(filter_positioner)
    controls.addWidget(filter_signal)
    controls.addWidget(filter_computed)

    combo = DeviceComboBox()
    combo.set_first_element_as_empty = True
    layout.addWidget(combo)

    def _apply_filters():
        raw = class_input.text().strip()
        if raw:
            combo.signal_class_filter = [entry.strip() for entry in raw.split(",") if entry.strip()]
        else:
            combo.signal_class_filter = []
        combo.filter_to_device = filter_device.isChecked()
        combo.filter_to_positioner = filter_positioner.isChecked()
        combo.filter_to_signal = filter_signal.isChecked()
        combo.filter_to_computed_signal = filter_computed.isChecked()

    class_input.textChanged.connect(_apply_filters)
    filter_device.toggled.connect(_apply_filters)
    filter_positioner.toggled.connect(_apply_filters)
    filter_signal.toggled.connect(_apply_filters)
    filter_computed.toggled.connect(_apply_filters)
    _apply_filters()

    widget.show()
    app.exec_()
