"""Editable combobox for selecting BEC devices."""

from __future__ import annotations

import enum

from bec_lib.callback_handler import EventType
from bec_lib.device import ComputedSignal, Device, Positioner, ReadoutPriority
from bec_lib.device import Signal as BECSignal
from bec_lib.logger import bec_logger
from pydantic import Field, field_validator
from qtpy.QtCore import QSize, QStringListModel, Signal, Slot
from qtpy.QtWidgets import QComboBox, QCompleter, QSizePolicy

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.filter_io import get_bec_signals_for_classes, replace_combobox_items

logger = bec_logger.logger


class BECDeviceFilter(enum.Enum):
    """Device class filters accepted by :class:`DeviceComboBox`."""

    DEVICE = "Device"
    POSITIONER = "Positioner"
    SIGNAL = "Signal"
    COMPUTED_SIGNAL = "ComputedSignal"


class DeviceInputConfig(ConnectionConfig):
    """Serializable configuration for :class:`DeviceComboBox`.

    Attributes:
        device_filter: Enabled device class filters as ``BECDeviceFilter.value`` strings.
        readout_filter: Enabled readout priority filters as ``ReadoutPriority.value`` strings.
        devices: Explicit device names shown by the combobox.
        default: Device selected by default.
        arg_name: Optional argument name used by scan/input widgets.
        apply_filter: Whether the combobox should refresh devices from the BEC device manager.
        signal_class_filter: Signal class names used to restrict listed devices.
        autocomplete: Whether to use the explicit completer model instead of Qt's default
            editable-combobox completer.
    """

    device_filter: list[str] = Field(default_factory=list)
    readout_filter: list[str] = Field(default_factory=list)
    devices: list[str] = Field(default_factory=list)
    default: str | None = None
    arg_name: str | None = None
    apply_filter: bool = True
    signal_class_filter: list[str] = Field(default_factory=list)
    autocomplete: bool = False

    @field_validator("device_filter")
    @classmethod
    def check_device_filter(cls, value):
        """Validate configured device class filters.

        Args:
            value: Device class filter values from the persisted widget configuration.

        Returns:
            The validated filter values.

        Raises:
            ValueError: If any configured filter is not a valid ``BECDeviceFilter`` value.
        """
        valid_filters = [entry.value for entry in BECDeviceFilter]
        for device_filter in value:
            if device_filter not in valid_filters:
                raise ValueError(
                    f"Device filter {device_filter} is not a valid device filter {valid_filters}."
                )
        return value

    @field_validator("readout_filter")
    @classmethod
    def check_readout_filter(cls, value):
        """Validate configured readout priority filters.

        Args:
            value: Readout priority filter values from the persisted widget configuration.

        Returns:
            The validated filter values.

        Raises:
            ValueError: If any configured filter is not a valid ``ReadoutPriority`` value.
        """
        valid_filters = [entry.value for entry in ReadoutPriority]
        for readout_filter in value:
            if readout_filter not in valid_filters:
                raise ValueError(
                    f"Readout filter {readout_filter} is not a valid readout filter {valid_filters}."
                )
        return value


class DeviceComboBox(BECWidget, QComboBox):
    """Editable combobox for selecting a BEC device.

    Args:
        parent: Optional parent widget.
        client: Optional BEC client object.
        config: Device input configuration as a ``DeviceInputConfig`` instance or dictionary.
        gui_id: Optional GUI identifier.
        device_filter: Device class filter or filters from ``BECDeviceFilter``.
        readout_priority_filter: Readout priority filter or filters from ``ReadoutPriority``.
        available_devices: Explicit device names to show. Passing this disables automatic
            BEC filtering.
        default: Device name selected during initialization.
        arg_name: Optional argument name used by scan/input widgets.
        signal_class_filter: Signal class names used to restrict listed devices.
        autocomplete: If True, use the explicit line-edit style completer. If False, keep
            Qt's default editable-combobox completion behavior.
        **kwargs: Additional keyword arguments passed to ``BECWidget``.
    """

    ICON_NAME = "list_alt"
    PLUGIN = True
    RPC = False

    device_selected = Signal(str)
    device_reset = Signal()
    device_config_update = Signal()

    _device_handler = {
        BECDeviceFilter.DEVICE: Device,
        BECDeviceFilter.POSITIONER: Positioner,
        BECDeviceFilter.SIGNAL: BECSignal,
        BECDeviceFilter.COMPUTED_SIGNAL: ComputedSignal,
    }

    def __init__(
        self,
        parent=None,
        client=None,
        config: DeviceInputConfig | dict | None = None,
        gui_id: str | None = None,
        device_filter: BECDeviceFilter | str | list[BECDeviceFilter | str] | None = None,
        readout_priority_filter: str | ReadoutPriority | list[str | ReadoutPriority] | None = None,
        available_devices: list[str] | None = None,
        default: str | None = None,
        arg_name: str | None = None,
        signal_class_filter: list[str] | None = None,
        autocomplete: bool | None = None,
        **kwargs,
    ):
        self.config = self._process_config(config)
        super().__init__(
            parent=parent,
            client=client,
            config=self.config,
            gui_id=gui_id,
            theme_update=True,
            **kwargs,
        )
        self.get_bec_shortcuts()

        self._device_filter: list[BECDeviceFilter] = []
        self._readout_filter: list[ReadoutPriority] = []
        self._devices: list[str] = []
        self._callback_id = None
        self._is_valid_input = False
        self._set_first_element_as_empty = False
        self._completer_model = QStringListModel(self)

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumSize(QSize(100, 0))

        if arg_name is not None:
            self.config.arg_name = arg_name
            self.arg_name = arg_name

        if available_devices is None and self.config.devices:
            available_devices = self.config.devices
        if device_filter is None and self.config.device_filter:
            device_filter = self.config.device_filter
        if readout_priority_filter is None and self.config.readout_filter:
            readout_priority_filter = self.config.readout_filter
        if signal_class_filter is None and self.config.signal_class_filter:
            signal_class_filter = self.config.signal_class_filter
        if default is None and self.config.default:
            default = self.config.default
        if autocomplete is not None:
            self.config.autocomplete = autocomplete
        if self.config.autocomplete:
            self.autocomplete = True

        if available_devices is not None:
            self.set_available_devices(available_devices)

        self.set_readout_priority_filter(
            readout_priority_filter
            or [
                ReadoutPriority.MONITORED,
                ReadoutPriority.BASELINE,
                ReadoutPriority.ASYNC,
                ReadoutPriority.CONTINUOUS,
                ReadoutPriority.ON_REQUEST,
            ]
        )

        if device_filter is not None:
            self.set_device_filter(device_filter)

        if signal_class_filter is not None:
            self.signal_class_filter = signal_class_filter

        if default is not None:
            self.set_device(default)
        else:
            self.setCurrentText("")

        self._callback_id = self.bec_dispatcher.client.callbacks.register(
            EventType.DEVICE_UPDATE, self.on_device_update
        )
        self.device_config_update.connect(self.update_devices_from_filters)
        self.currentTextChanged.connect(self.check_validity)
        self.check_validity(self.currentText())

    @staticmethod
    def _process_config(config: DeviceInputConfig | dict | None) -> DeviceInputConfig:
        """Normalize user-provided configuration.

        Args:
            config: Existing configuration, configuration dictionary, or None.

        Returns:
            A validated ``DeviceInputConfig`` instance.
        """
        if config is None:
            return DeviceInputConfig(widget_class="DeviceComboBox")
        return DeviceInputConfig.model_validate(config)

    @SafeSlot(str)
    def set_device(self, device: str):
        """Set the current device if it is valid for the current filters.

        Args:
            device: Device name to select.
        """
        if self.validate_device(device):
            self.setCurrentText(device)
            self.config.default = device
        else:
            logger.warning(
                f"Device {device} is not in the filtered selection of {self}: {self.devices}."
            )

    @SafeSlot()
    def update_devices_from_filters(self):
        """Refresh the available device list from current device/readout/signal filters."""
        self.config.device_filter = [entry.value for entry in self.device_filter]
        self.config.readout_filter = [entry.value for entry in self.readout_filter]
        self.config.signal_class_filter = self.signal_class_filter
        if not self.apply_filter:
            return

        devices = self._filter_devices_by_signal_class(self.dev.enabled_devices)
        devices = [device for device in devices if self._check_device_filter(device)]
        devices = [device for device in devices if self._check_readout_filter(device)]
        self.devices = [device.name for device in devices]

    @SafeSlot(list)
    def set_available_devices(self, devices: list[str]):
        """Use an explicit device list and disable automatic BEC filtering.

        Args:
            devices: Device names to show in the combobox.
        """
        self.apply_filter = False
        self.devices = devices

    @SafeProperty("QStringList")
    def devices(self) -> list[str]:
        """Devices available after filtering."""
        return self._devices

    @devices.setter
    def devices(self, value: list[str]):
        self._devices = value
        self.config.devices = value
        self._replace_items(value)

    @SafeProperty(str)
    def default(self):
        """Default selected device."""
        return self.config.default

    @default.setter
    def default(self, value: str):
        self.set_device(value)

    @SafeProperty(bool)
    def apply_filter(self):
        """Whether BEC filters are applied to the device list."""
        return self.config.apply_filter

    @apply_filter.setter
    def apply_filter(self, value: bool):
        self.config.apply_filter = value
        if value:
            self.update_devices_from_filters()

    @SafeProperty("QStringList")
    def signal_class_filter(self) -> list[str]:
        """Signal class names used to restrict devices."""
        return self.config.signal_class_filter

    @signal_class_filter.setter
    def signal_class_filter(self, value: list[str] | None):
        self.config.signal_class_filter = value or []
        self.update_devices_from_filters()

    @SafeProperty(bool)
    def filter_to_device(self):
        """Include generic Device objects."""
        return BECDeviceFilter.DEVICE in self.device_filter

    @filter_to_device.setter
    def filter_to_device(self, value: bool):
        self._set_device_filter_enabled(BECDeviceFilter.DEVICE, value)

    @SafeProperty(bool)
    def filter_to_positioner(self):
        """Include Positioner devices."""
        return BECDeviceFilter.POSITIONER in self.device_filter

    @filter_to_positioner.setter
    def filter_to_positioner(self, value: bool):
        self._set_device_filter_enabled(BECDeviceFilter.POSITIONER, value)

    @SafeProperty(bool)
    def filter_to_signal(self):
        """Include Signal devices."""
        return BECDeviceFilter.SIGNAL in self.device_filter

    @filter_to_signal.setter
    def filter_to_signal(self, value: bool):
        self._set_device_filter_enabled(BECDeviceFilter.SIGNAL, value)

    @SafeProperty(bool)
    def filter_to_computed_signal(self):
        """Include ComputedSignal devices."""
        return BECDeviceFilter.COMPUTED_SIGNAL in self.device_filter

    @filter_to_computed_signal.setter
    def filter_to_computed_signal(self, value: bool):
        self._set_device_filter_enabled(BECDeviceFilter.COMPUTED_SIGNAL, value)

    @SafeProperty(bool)
    def readout_monitored(self):
        """Include monitored devices."""
        return ReadoutPriority.MONITORED in self.readout_filter

    @readout_monitored.setter
    def readout_monitored(self, value: bool):
        self._set_readout_filter_enabled(ReadoutPriority.MONITORED, value)

    @SafeProperty(bool)
    def readout_baseline(self):
        """Include baseline devices."""
        return ReadoutPriority.BASELINE in self.readout_filter

    @readout_baseline.setter
    def readout_baseline(self, value: bool):
        self._set_readout_filter_enabled(ReadoutPriority.BASELINE, value)

    @SafeProperty(bool)
    def readout_async(self):
        """Include async devices."""
        return ReadoutPriority.ASYNC in self.readout_filter

    @readout_async.setter
    def readout_async(self, value: bool):
        self._set_readout_filter_enabled(ReadoutPriority.ASYNC, value)

    @SafeProperty(bool)
    def readout_continuous(self):
        """Include continuous devices."""
        return ReadoutPriority.CONTINUOUS in self.readout_filter

    @readout_continuous.setter
    def readout_continuous(self, value: bool):
        self._set_readout_filter_enabled(ReadoutPriority.CONTINUOUS, value)

    @SafeProperty(bool)
    def readout_on_request(self):
        """Include on-request devices."""
        return ReadoutPriority.ON_REQUEST in self.readout_filter

    @readout_on_request.setter
    def readout_on_request(self, value: bool):
        self._set_readout_filter_enabled(ReadoutPriority.ON_REQUEST, value)

    @SafeProperty(bool)
    def set_first_element_as_empty(self) -> bool:
        """Whether an empty choice is inserted as the first item."""
        return self._set_first_element_as_empty

    @set_first_element_as_empty.setter
    def set_first_element_as_empty(self, value: bool) -> None:
        self._set_first_element_as_empty = value
        current_text = self.currentText()
        if value:
            if self.count() == 0 or self.itemText(0) != "":
                self.insertItem(0, "")
            self.setCurrentIndex(0)
        elif self.count() > 0 and self.itemText(0) == "":
            self.removeItem(0)
            if not current_text:
                self.setCurrentText("")

    @SafeProperty(bool)
    def autocomplete(self) -> bool:
        """Whether autocomplete suggestions are enabled while editing."""
        return self.config.autocomplete

    @autocomplete.setter
    def autocomplete(self, value: bool) -> None:
        self.config.autocomplete = value
        if value:
            self.setCompleter(QCompleter(self._completer_model, self))
        else:
            self.setCompleter(QCompleter(self.model(), self))

    @property
    def device_filter(self) -> list[BECDeviceFilter]:
        """Device class filters."""
        return self._device_filter

    @property
    def readout_filter(self) -> list[ReadoutPriority]:
        """Readout priority filters."""
        return self._readout_filter

    @property
    def is_valid_input(self) -> bool:
        """Whether the current text represents a valid device selection."""
        return self._is_valid_input

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        super().setEnabled(enabled)
        self._update_validity_style(self._is_valid_input)

    def set_device_filter(
        self, filter_selection: BECDeviceFilter | str | list[BECDeviceFilter | str]
    ):
        """Enable one or more device class filters.

        Args:
            filter_selection: Filter or filters to enable. Strings must match
                ``BECDeviceFilter.value``.
        """
        for device_filter in self._as_list(filter_selection):
            normalized = self._normalize_device_filter(device_filter)
            if normalized is None:
                logger.warning(f"Device filter {device_filter} is not in the device filter list.")
                continue
            self._set_device_filter_enabled(normalized, True)

    def set_readout_priority_filter(
        self, filter_selection: ReadoutPriority | str | list[ReadoutPriority | str]
    ):
        """Enable one or more readout priority filters.

        Args:
            filter_selection: Readout priority filter or filters to enable. Strings must match
                ``ReadoutPriority.value``.
        """
        for readout_filter in self._as_list(filter_selection):
            normalized = self._normalize_readout_filter(readout_filter)
            if normalized is None:
                logger.warning(
                    f"Readout priority filter {readout_filter} is not in the readout priority list."
                )
                continue
            self._set_readout_filter_enabled(normalized, True)

    def on_device_update(self, action: str, content: dict) -> None:
        """Refresh filters when the BEC device configuration changes.

        Args:
            action: Device update action emitted by BEC.
            content: Device update payload. Currently unused.
        """
        if self._callback_id is None or getattr(self, "_destroyed", False):
            return
        if action in ["add", "remove", "reload"]:
            self.device_config_update.emit()

    def cleanup(self):
        """Cleanup the widget."""
        if self._callback_id is not None:
            callback_id = self._callback_id
            self._callback_id = None
            self.bec_dispatcher.client.callbacks.remove(callback_id)
        super().cleanup()

    def get_current_device(self) -> object:
        """Return the current BEC device object.

        Returns:
            Device object for the current combobox text.
        """
        return self.get_device_object(self._device_name_from_text(self.currentText()))

    @Slot(str)
    def check_validity(self, input_text: str) -> None:
        """Validate current text and update visual state.

        Args:
            input_text: Current combobox text.
        """
        if self.validate_device(input_text):
            self._is_valid_input = True
            self.device_selected.emit(input_text)
        else:
            self._is_valid_input = False
            self.device_reset.emit()
        self._update_validity_style(self._is_valid_input)

    def validate_device(self, device: str | None) -> bool:
        """Validate a device against the current filtered device selection.

        Args:
            device: Device name or displayed device text to validate.

        Returns:
            True if the device exists in the current BEC device manager and is present in the
            filtered combobox list.
        """
        if not device:
            return False
        device_name = self._device_name_from_text(device)
        all_devices = [dev.name for dev in self.dev.enabled_devices]
        return device_name in self.devices and device_name in all_devices

    def get_device_object(self, device: str) -> object:
        """Return a device object by name.

        Args:
            device: Device name.

        Returns:
            BEC device object.

        Raises:
            ValueError: If the device is not available in the device manager.
        """
        dev = getattr(self.dev, device, None)
        if dev is None:
            raise ValueError(
                f"Device {device} is not found in the device manager {self.dev} as enabled device."
            )
        return dev

    @staticmethod
    def _as_list(value):
        return value if isinstance(value, list) else [value]

    @staticmethod
    def _normalize_device_filter(value: BECDeviceFilter | str) -> BECDeviceFilter | None:
        if isinstance(value, BECDeviceFilter):
            return value
        return BECDeviceFilter._value2member_map_.get(value)

    @staticmethod
    def _normalize_readout_filter(value: ReadoutPriority | str) -> ReadoutPriority | None:
        if isinstance(value, ReadoutPriority):
            return value
        return ReadoutPriority._value2member_map_.get(value)

    def _set_device_filter_enabled(self, device_filter: BECDeviceFilter, enabled: bool):
        if enabled and device_filter not in self._device_filter:
            self._device_filter.append(device_filter)
        elif not enabled and device_filter in self._device_filter:
            self._device_filter.remove(device_filter)
        self.update_devices_from_filters()

    def _set_readout_filter_enabled(self, readout_filter: ReadoutPriority, enabled: bool):
        if enabled and readout_filter not in self._readout_filter:
            self._readout_filter.append(readout_filter)
        elif not enabled and readout_filter in self._readout_filter:
            self._readout_filter.remove(readout_filter)
        self.update_devices_from_filters()

    def _check_device_filter(
        self, device: Device | BECSignal | ComputedSignal | Positioner
    ) -> bool:
        if not self.device_filter:
            return True
        return all(isinstance(device, self._device_handler[entry]) for entry in self.device_filter)

    def _check_readout_filter(
        self, device: Device | BECSignal | ComputedSignal | Positioner
    ) -> bool:
        return device.readout_priority in self.readout_filter

    def _update_validity_style(self, is_valid: bool) -> None:
        border_color = "transparent" if is_valid or not self.isEnabled() else "red"
        self.setStyleSheet(f"border: 1px solid {border_color};")

    def _filter_devices_by_signal_class(
        self, devices: list[Device | BECSignal | ComputedSignal | Positioner]
    ) -> list[Device | BECSignal | ComputedSignal | Positioner]:
        if not self.config.signal_class_filter:
            return devices
        signals = get_bec_signals_for_classes(
            client=self.client, signal_class_filter=self.config.signal_class_filter
        )
        allowed_devices = {device_name for device_name, _, _ in signals}
        return [device for device in devices if device.name in allowed_devices]

    def _replace_items(self, devices: list[str]):
        items = [""] + devices if self._set_first_element_as_empty else devices
        replace_combobox_items(self, items, preserve_current_text=True, block_signals=True)
        self._completer_model.setStringList(devices)
        self.check_validity(self.currentText())

    def _device_name_from_text(self, text: str) -> str:
        index = self.findText(text)
        if index >= 0 and isinstance(self.itemData(index), tuple):
            return self.itemData(index)[0]
        return text


if __name__ == "__main__":  # pragma: no cover
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
        combo.signal_class_filter = [entry.strip() for entry in raw.split(",") if entry.strip()]
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
