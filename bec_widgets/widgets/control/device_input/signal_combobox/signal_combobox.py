from __future__ import annotations

from bec_lib.callback_handler import EventType
from bec_lib.device import Signal as BECSignal
from bec_lib.logger import bec_logger
from qtpy.QtCore import Property, QSize, QStringListModel, Qt, Signal, Slot
from qtpy.QtWidgets import QComboBox, QCompleter, QSizePolicy

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.filter_io import (
    get_bec_signals_for_classes,
    replace_combobox_items,
    signal_items_for_kind,
)
from bec_widgets.utils.ophyd_kind_util import Kind

logger = bec_logger.logger


class SignalComboBoxConfig(ConnectionConfig):
    """Configuration for SignalComboBox."""

    signal_filter: list[str] | None = None
    signal_class_filter: list[str] | None = None
    ndim_filter: int | list[int] | None = None
    default: str | None = None
    arg_name: str | None = None
    device: str | None = None
    signals: list[str] | None = None
    autocomplete: bool = False


class SignalComboBox(BECWidget, QComboBox):
    """
    Editable combobox for selecting BEC device signals.

    Args:
        parent: Parent widget.
        client: BEC client object.
        config: Signal combobox configuration.
        gui_id: GUI ID.
        device: Device name to filter signals from.
        signal_filter: Signal kind filters from Kind.
        signal_class_filter: Signal classes to show.
        ndim_filter: Dimensionality filter for signal-class based lists.
        default: Default signal name.
        arg_name: Argument name used by scan/input widgets.
        store_signal_config: Whether to store signal config in item data.
        require_device: If True, signals are only shown/validated when a device is set.
    """

    USER_ACCESS = ["set_signal", "set_device", "signals", "get_signal_name"]

    ICON_NAME = "list_alt"
    PLUGIN = True
    RPC = False

    device_signal_changed = Signal(str)
    signal_reset = Signal()

    def __init__(
        self,
        parent=None,
        client=None,
        config: SignalComboBoxConfig | dict | None = None,
        gui_id: str | None = None,
        device: str | None = None,
        signal_filter: list[Kind | str] | Kind | str | None = None,
        signal_class_filter: list[str] | None = None,
        ndim_filter: int | list[int] | None = None,
        default: str | None = None,
        arg_name: str | None = None,
        store_signal_config: bool = True,
        require_device: bool = False,
        autocomplete: bool | None = None,
        **kwargs,
    ):
        self.config = self._process_config(config)
        super().__init__(parent=parent, client=client, config=self.config, gui_id=gui_id, **kwargs)
        self.get_bec_shortcuts()

        self._device: str | None = None
        self._signal_filter: set[Kind] = set()
        self._signals: list[str | tuple[str, dict]] = []
        self._hinted_signals: list[tuple[str, dict]] = []
        self._normal_signals: list[tuple[str, dict]] = []
        self._config_signals: list[tuple[str, dict]] = []
        self._set_first_element_as_empty = False
        self._signal_class_filter = signal_class_filter or []
        self._store_signal_config = store_signal_config
        self._require_device = require_device
        self._is_valid_input = False
        self._completer_model = QStringListModel(self)

        if arg_name is not None:
            self.config.arg_name = arg_name
            self.arg_name = arg_name

        if signal_filter is None and self.config.signal_filter:
            signal_filter = self.config.signal_filter
        if signal_class_filter is None and self.config.signal_class_filter:
            self._signal_class_filter = self.config.signal_class_filter
        if ndim_filter is None and self.config.ndim_filter is not None:
            ndim_filter = self.config.ndim_filter
        if device is None and self.config.device:
            device = self.config.device
        if default is None and self.config.default:
            default = self.config.default
        if autocomplete is not None:
            self.config.autocomplete = autocomplete
        self.config.ndim_filter = ndim_filter

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumSize(QSize(100, 0))
        if self.config.autocomplete:
            self.autocomplete = True

        self._device_update_register = self.bec_dispatcher.client.callbacks.register(
            EventType.DEVICE_UPDATE, self.update_signals_from_filters
        )
        self.currentTextChanged.connect(self.on_text_changed)

        self.set_filter(signal_filter or [Kind.hinted, Kind.normal, Kind.config])

        if device is not None:
            self.set_device(device)
        if default is not None:
            self.set_signal(default)
        self.check_validity(self.currentText())

    @staticmethod
    def _process_config(config: SignalComboBoxConfig | dict | None) -> SignalComboBoxConfig:
        if config is None:
            return SignalComboBoxConfig(widget_class="SignalComboBox")
        return SignalComboBoxConfig.model_validate(config)

    @SafeSlot(str)
    def set_signal(self, signal: str):
        """Set the current signal if it is available in the combobox."""
        display_text = self._display_text_for_signal(signal)
        if display_text is None:
            logger.warning(
                f"Signal {signal} not found for device {self.device} and filtered selection {self.signal_filter}."
            )
            return
        self.setCurrentText(display_text)
        self.config.default = signal

    @SafeSlot(str)
    def set_device(self, device: str | None):
        """Set the device that scopes kind-based signal filtering."""
        if not self.validate_device(device):
            self._device = None
        else:
            self._device = device
        self.config.device = self._device
        self.update_signals_from_filters()

    @SafeSlot()
    @SafeSlot(dict, dict)
    def update_signals_from_filters(
        self, content: dict | None = None, metadata: dict | None = None
    ):
        """Refresh available signals from the current device and filters."""
        self.config.signal_filter = [kind.name for kind in self.signal_filter]

        if self._signal_class_filter:
            self.update_signals_from_signal_classes()
            return

        if not self.validate_device(self._device):
            self._device = None
            self.config.device = None
            self._set_signal_groups([], [], [])
            return

        device = self.get_device_object(self._device)
        device_info = device._info.get("signals", {})

        if isinstance(device, BECSignal):
            self._set_signal_groups([(self._device, {})], [], [])
            return

        self._set_signal_groups(
            signal_items_for_kind(
                kind=Kind.hinted,
                signal_filter=self.signal_filter,
                device_info=device_info,
                device_name=self._device,
            ),
            signal_items_for_kind(
                kind=Kind.normal,
                signal_filter=self.signal_filter,
                device_info=device_info,
                device_name=self._device,
            ),
            signal_items_for_kind(
                kind=Kind.config,
                signal_filter=self.signal_filter,
                device_info=device_info,
                device_name=self._device,
            ),
        )

    @Property(str)
    def device(self) -> str:
        """Selected device."""
        return self._device or ""

    @device.setter
    def device(self, value: str):
        self.set_device(value)

    @Property(bool)
    def include_hinted_signals(self):
        """Include hinted signals."""
        return Kind.hinted in self.signal_filter

    @include_hinted_signals.setter
    def include_hinted_signals(self, value: bool):
        self._set_kind_filter_enabled(Kind.hinted, value)

    @Property(bool)
    def include_normal_signals(self):
        """Include normal signals."""
        return Kind.normal in self.signal_filter

    @include_normal_signals.setter
    def include_normal_signals(self, value: bool):
        self._set_kind_filter_enabled(Kind.normal, value)

    @Property(bool)
    def include_config_signals(self):
        """Include config signals."""
        return Kind.config in self.signal_filter

    @include_config_signals.setter
    def include_config_signals(self, value: bool):
        self._set_kind_filter_enabled(Kind.config, value)

    @SafeProperty(bool)
    def set_first_element_as_empty(self) -> bool:
        """Whether an empty choice is inserted as the first item."""
        return self._set_first_element_as_empty

    @set_first_element_as_empty.setter
    def set_first_element_as_empty(self, value: bool) -> None:
        self._set_first_element_as_empty = value
        if value:
            if self.count() == 0 or self.itemText(0) != "":
                self.insertItem(0, "")
            self.setCurrentIndex(0)
        elif self.count() > 0 and self.itemText(0) == "":
            self.removeItem(0)

    @SafeProperty("QStringList")
    def signal_class_filter(self) -> list[str]:
        """Signal class names used to build the signal list."""
        return self._signal_class_filter

    @signal_class_filter.setter
    def signal_class_filter(self, value: list[str] | None):
        self._signal_class_filter = value or []
        self.config.signal_class_filter = self._signal_class_filter
        self.update_signals_from_filters()

    @SafeProperty(int)
    def ndim_filter(self) -> int:
        """Dimensionality filter for signal-class based lists."""
        return self.config.ndim_filter if isinstance(self.config.ndim_filter, int) else -1

    @ndim_filter.setter
    def ndim_filter(self, value: int):
        self.config.ndim_filter = None if value < 0 else value
        self.update_signals_from_filters()

    @SafeProperty(bool)
    def require_device(self) -> bool:
        """Whether validation/listing requires a selected device."""
        return self._require_device

    @require_device.setter
    def require_device(self, value: bool):
        self._require_device = value
        self.update_signals_from_filters()

    @SafeProperty(bool)
    def autocomplete(self) -> bool:
        """Whether autocomplete suggestions are enabled while editing."""
        return self.config.autocomplete

    @autocomplete.setter
    def autocomplete(self, value: bool) -> None:
        self.config.autocomplete = value
        if value:
            completer = QCompleter(self._completer_model, self)
            self.setCompleter(completer)
        else:
            self._restore_default_completer()

    @property
    def signals(self) -> list[str | tuple[str, dict]]:
        """Available signals after filtering."""
        return self._signals

    @signals.setter
    def signals(self, value: list[str | tuple[str, dict]]):
        self._signals = value
        self.config.signals = [entry[0] if isinstance(entry, tuple) else entry for entry in value]
        self._replace_signal_items()

    @property
    def signal_filter(self) -> set[Kind]:
        """Signal kind filters."""
        return self._signal_filter

    @property
    def is_valid_input(self) -> bool:
        """Whether the current text represents a valid signal selection."""
        return self._is_valid_input

    @property
    def selected_signal_comp_name(self) -> str:
        """Component name for the current signal, falling back to object name."""
        index = self._find_signal_index(self.currentText())
        if index < 0:
            return self.get_signal_name()
        signal_info = self.itemData(index)
        if isinstance(signal_info, dict):
            return signal_info.get("component_name") or self.get_signal_name()
        return self.get_signal_name()

    def set_filter(self, filter_selection: Kind | str | list[Kind | str] | None):
        """Enable one or more signal kind filters."""
        if filter_selection is None:
            return
        filters = filter_selection if isinstance(filter_selection, list) else [filter_selection]
        for signal_filter in filters:
            kind = self._normalize_kind(signal_filter)
            if kind is not None:
                self._signal_filter.add(kind)
        self.update_signals_from_filters()

    def get_available_filters(self) -> list[Kind]:
        """Return available signal kind filters."""
        return [Kind.hinted, Kind.normal, Kind.config]

    def get_device_object(self, device: str) -> object | None:
        """Return a BEC device object by name."""
        dev = getattr(self.dev, device, None)
        if dev is None:
            logger.warning(f"Device {device} not found in devicemanager.")
            return None
        return dev

    def validate_device(self, device: str | None, raise_on_false: bool = False) -> bool:
        """Validate that a device exists in the current device manager."""
        if device in self.dev:
            return True
        if raise_on_false:
            raise ValueError(f"Device {device} not found in devicemanager.")
        return False

    def validate_signal(self, signal: str) -> bool:
        """Validate a signal by display text, object name, or component name."""
        return self._display_text_for_signal(signal) is not None

    def set_to_obj_name(self, obj_name: str) -> bool:
        """Select the item whose signal config has the given object name."""
        index = self._find_signal_index(obj_name)
        if index < 0:
            return False
        self.setCurrentIndex(index)
        return True

    def set_to_first_enabled(self) -> bool:
        """Select the first enabled item."""
        for index in range(self.count()):
            item = self.model().item(index)
            if item is not None and item.isEnabled():
                self.setCurrentIndex(index)
                return True
        return False

    def get_signal_name(self) -> str:
        """Return the selected signal object name when available."""
        current_text = self.currentText()
        index = self._find_signal_index(current_text)
        if index < 0:
            return current_text

        signal_info = self.itemData(index)
        if isinstance(signal_info, dict):
            return signal_info.get("obj_name") or current_text
        return current_text

    def get_signal_config(self) -> dict | None:
        """Return the selected signal config if item-data storage is enabled."""
        if not self._store_signal_config:
            return None
        signal_info = self.itemData(self.currentIndex())
        return signal_info if isinstance(signal_info, dict) else None

    def update_signals_from_signal_classes(self, ndim_filter: int | list[int] | None = None):
        """Refresh signals from device_manager.get_bec_signals for class-based filtering."""
        if not self._signal_class_filter:
            return

        if self._require_device and not self._device:
            self.signals = []
            return

        if ndim_filter is not None:
            self.config.ndim_filter = ndim_filter

        signals = get_bec_signals_for_classes(
            client=self.client,
            signal_class_filter=self._signal_class_filter,
            ndim_filter=self.config.ndim_filter,
        )

        self.clear()
        self._signals = []
        for device_name, signal_name, signal_config in signals:
            if self._device and device_name != self._device:
                continue
            if self._signal_filter:
                kind_str = signal_config.get("kind_str")
                if kind_str is not None and kind_str not in {
                    kind.name for kind in self._signal_filter
                }:
                    continue

            if self._store_signal_config:
                self.addItem(signal_name, signal_config)
            else:
                self.addItem(signal_name)

            self._signals.append(signal_name)
            storage_name = signal_config.get("storage_name", "")
            if storage_name:
                self.setItemData(self.count() - 1, storage_name, Qt.ItemDataRole.ToolTipRole)

        self.config.signals = [
            entry if isinstance(entry, str) else entry[0] for entry in self._signals
        ]
        self._update_completer_model(self.config.signals)
        if self._set_first_element_as_empty and self.count() > 0 and self.itemText(0) != "":
            self.insertItem(0, "")

    @SafeSlot()
    def reset_selection(self):
        """Reset the current selection and refresh available signals."""
        self.setCurrentText("")
        self.update_signals_from_filters()
        self.device_signal_changed.emit("")

    @SafeSlot(str)
    def on_text_changed(self, text: str):
        """Validate the current text when edited or selected."""
        self.check_validity(text)

    @Slot(str)
    def check_validity(self, input_text: str) -> None:
        """Validate current text and update visual state."""
        if self._signal_class_filter:
            is_valid = not (self._require_device and not self._device) and self.validate_signal(
                input_text
            )
        else:
            is_valid = self.validate_device(self._device) and self.validate_signal(input_text)

        if is_valid:
            self._is_valid_input = True
            self.device_signal_changed.emit(input_text)
            self.setStyleSheet("border: 1px solid transparent;")
        else:
            self._is_valid_input = False
            self.signal_reset.emit()
            if self.isEnabled():
                self.setStyleSheet("border: 1px solid red;")

    def cleanup(self):
        """Cleanup the widget."""
        self.bec_dispatcher.client.callbacks.remove(self._device_update_register)
        super().cleanup()

    @staticmethod
    def _normalize_kind(value: Kind | str) -> Kind | None:
        if isinstance(value, Kind):
            return value
        return Kind.__members__.get(value) or Kind.__members__.get(value.lower())

    def _set_kind_filter_enabled(self, kind: Kind, enabled: bool):
        if enabled:
            self._signal_filter.add(kind)
        else:
            self._signal_filter.discard(kind)
        self.update_signals_from_filters()

    def _set_signal_groups(
        self,
        hinted: list[tuple[str, dict]],
        normal: list[tuple[str, dict]],
        config: list[tuple[str, dict]],
    ) -> None:
        self._hinted_signals = hinted
        self._normal_signals = normal
        self._config_signals = config
        self.signals = self._hinted_signals + self._normal_signals + self._config_signals
        self._insert_group_headers()

    def _replace_signal_items(self):
        replace_combobox_items(self, self._signals)
        self._update_completer_model(self._signal_display_texts(self._signals))
        if self._set_first_element_as_empty and self.count() > 0 and self.itemText(0) != "":
            self.insertItem(0, "")

    def _insert_group_headers(self):
        offset = (
            1
            if self._set_first_element_as_empty and self.count() > 0 and self.itemText(0) == ""
            else 0
        )
        if self._config_signals:
            index = offset + len(self._hinted_signals) + len(self._normal_signals)
            self.insertItem(index, "Config Signals")
            self.model().item(index).setEnabled(False)
        if self._normal_signals:
            index = offset + len(self._hinted_signals)
            self.insertItem(index, "Normal Signals")
            self.model().item(index).setEnabled(False)
        if self._hinted_signals:
            index = offset
            self.insertItem(index, "Hinted Signals")
            self.model().item(index).setEnabled(False)

    def _display_text_for_signal(self, signal: str) -> str | None:
        for entry in self._signals:
            display_text = entry[0] if isinstance(entry, tuple) else entry
            if display_text == signal:
                return display_text
            if isinstance(entry, tuple) and self._signal_info_matches(entry[1], signal):
                return display_text
        return None

    @staticmethod
    def _signal_info_matches(signal_info: dict, signal: str) -> bool:
        return signal in {
            signal_info.get("obj_name"),
            signal_info.get("component_name"),
            signal_info.get("component_name", "").replace(".", "_"),
        }

    def _find_signal_index(self, signal: str) -> int:
        index = self.findText(signal)
        if index >= 0:
            return index
        for item_index in range(self.count()):
            signal_info = self.itemData(item_index)
            if isinstance(signal_info, dict) and self._signal_info_matches(signal_info, signal):
                return item_index
        return -1

    @staticmethod
    def _signal_display_texts(signals: list[str | tuple[str, dict]]) -> list[str]:
        return [entry[0] if isinstance(entry, tuple) else entry for entry in signals]

    def _update_completer_model(self, items: list[str]) -> None:
        self._completer_model.setStringList(items)

    def _restore_default_completer(self) -> None:
        if self.completer() is not None and self.completer().model() == self.model():
            return
        current_text = self.currentText()
        self.setEditable(False)
        self.setEditable(True)
        self.setCurrentText(current_text)


if __name__ == "__main__":  # pragma: no cover
    from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

    from bec_widgets.utils.colors import apply_theme

    app = QApplication([])
    apply_theme("dark")
    widget = QWidget()
    widget.setFixedSize(200, 200)
    layout = QVBoxLayout(widget)
    box = SignalComboBox(
        device="waveform",
        signal_class_filter=["AsyncSignal", "AsyncMultiSignal"],
        ndim_filter=[1, 2],
        store_signal_config=True,
        signal_filter=[Kind.hinted, Kind.normal, Kind.config],
    )
    layout.addWidget(box)
    widget.show()
    app.exec_()
