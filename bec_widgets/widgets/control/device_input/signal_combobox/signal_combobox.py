"""Editable combobox for selecting BEC device signals."""

from __future__ import annotations

from bec_lib.callback_handler import EventType
from bec_lib.device import Signal as BECSignal
from bec_lib.logger import bec_logger
from pydantic import Field
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
    """Serializable configuration for :class:`SignalComboBox`.

    Attributes:
        signal_filter: Enabled signal kind filters as ``Kind.name`` strings.
        signal_class_filter: Signal class names used to build the signal list from BEC.
        ndim_filter: Optional dimensionality filter for class-based signal lists.
        default: Signal selected by default.
        arg_name: Optional argument name used by scan/input widgets.
        device: Device name used to scope kind-based signal filtering.
        signals: Signal names available after filtering.
        autocomplete: Whether to use the explicit completer model instead of Qt's default
            editable-combobox completer.
    """

    signal_filter: list[str] = Field(default_factory=list)
    signal_class_filter: list[str] = Field(default_factory=list)
    ndim_filter: int | list[int] | None = None
    default: str | None = None
    arg_name: str | None = None
    device: str | None = None
    signals: list[str] = Field(default_factory=list)
    autocomplete: bool = False


class SignalComboBox(BECWidget, QComboBox):
    """Editable combobox for selecting a signal from a BEC device.

    Args:
        parent: Optional parent widget.
        client: Optional BEC client object.
        config: Signal combobox configuration as a ``SignalComboBoxConfig`` instance or
            dictionary.
        gui_id: Optional GUI identifier.
        device: Device name used to scope kind-based signal filtering.
        signal_filter: Signal kind filter or filters from ``Kind``.
        signal_class_filter: Signal class names used to build a class-based signal list.
        ndim_filter: Dimensionality filter for class-based signal lists.
        default: Signal selected during initialization.
        arg_name: Optional argument name used by scan/input widgets.
        store_signal_config: Whether to store each signal config in the item data.
        require_device: If True, class-based signal filtering requires a valid selected device.
        autocomplete: If True, use the explicit line-edit style completer. If False, keep
            Qt's default editable-combobox completion behavior.
        **kwargs: Additional keyword arguments passed to ``BECWidget``.
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
        """Normalize user-provided configuration.

        Args:
            config: Existing configuration, configuration dictionary, or None.

        Returns:
            A validated ``SignalComboBoxConfig`` instance.
        """
        if config is None:
            return SignalComboBoxConfig(widget_class="SignalComboBox")
        return SignalComboBoxConfig.model_validate(config)

    @SafeSlot(str)
    def set_signal(self, signal: str):
        """Set the current signal if it is available in the combobox.

        Args:
            signal: Signal display text, object name, or component name to select.
        """
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
        """Set the device that scopes kind-based signal filtering.

        Args:
            device: Device name to use for signal filtering. Invalid or empty values clear
                the current device and signal selection.
        """
        previous_device = self._device
        valid_device = device if self.validate_device(device) else None
        self._device = valid_device
        self.config.device = self._device
        if valid_device is None or valid_device != previous_device:
            self.setCurrentText("")
        self.update_signals_from_filters()

    @SafeSlot()
    @SafeSlot(dict, dict)
    def update_signals_from_filters(
        self, content: dict | None = None, metadata: dict | None = None
    ):
        """Refresh available signals from the current device and filters.

        Args:
            content: Optional callback payload from BEC device updates. Currently unused.
            metadata: Optional callback metadata from BEC device updates. Currently unused.
        """
        self.config.signal_filter = [kind.name for kind in self.signal_filter]

        logger.warning(f"SIGNAL COMBOBOX UPDATE: {content}")

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
            self.setCompleter(QCompleter(self._completer_model, self))
        else:
            self.setCompleter(QCompleter(self.model(), self))

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

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        super().setEnabled(enabled)
        self._update_validity_style(self._is_valid_input)

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
        """Enable one or more signal kind filters.

        Args:
            filter_selection: Filter or filters to enable. Strings must match ``Kind`` member
                names.
        """
        if filter_selection is None:
            return
        filters = filter_selection if isinstance(filter_selection, list) else [filter_selection]
        for signal_filter in filters:
            kind = self._normalize_kind(signal_filter)
            if kind is not None:
                self._signal_filter.add(kind)
        self.update_signals_from_filters()

    def get_device_object(self, device: str) -> object | None:
        """Return a BEC device object by name.

        Args:
            device: Device name.

        Returns:
            Device object if it exists in the device manager, otherwise None.
        """
        dev = getattr(self.dev, device, None)
        if dev is None:
            logger.warning(f"Device {device} not found in devicemanager.")
            return None
        return dev

    def validate_device(self, device: str | None, raise_on_false: bool = False) -> bool:
        """Validate that a device exists in the current device manager.

        Args:
            device: Device name to validate.
            raise_on_false: If True, raise instead of returning False for missing devices.

        Returns:
            True if the device exists in the current device manager.

        Raises:
            ValueError: If ``raise_on_false`` is True and the device is missing.
        """
        if device in self.dev:
            return True
        if raise_on_false:
            raise ValueError(f"Device {device} not found in devicemanager.")
        return False

    def validate_signal(self, signal: str) -> bool:
        """Validate a signal by display text, object name, or component name.

        Args:
            signal: Signal display text, object name, or component name.

        Returns:
            True if the signal is present in the current filtered signal list.
        """
        if not signal:
            return False
        return self._display_text_for_signal(signal) is not None

    def set_to_obj_name(self, obj_name: str) -> bool:
        """Select the item whose signal config has the given object name.

        Args:
            obj_name: Signal object name to select.

        Returns:
            True if a matching signal was selected.
        """
        index = self._find_signal_index(obj_name)
        if index < 0:
            return False
        self.setCurrentIndex(index)
        return True

    def set_to_first_enabled(self) -> bool:
        """Select the first enabled item.

        Returns:
            True if an enabled item was found and selected.
        """
        for index in range(self.count()):
            item = self.model().item(index)
            if item is not None and item.isEnabled():
                self.setCurrentIndex(index)
                return True
        return False

    def get_signal_name(self) -> str:
        """Return the selected signal object name when available.

        Returns:
            Signal object name from item data, or the current display text when no item data
            is available.
        """
        current_text = self.currentText()
        index = self._find_signal_index(current_text)
        if index < 0:
            return current_text

        signal_info = self.itemData(index)
        if isinstance(signal_info, dict):
            return signal_info.get("obj_name") or current_text
        return current_text

    def get_signal_config(self) -> dict | None:
        """Return the selected signal config if item-data storage is enabled.

        Returns:
            Selected signal configuration dictionary, or None when item-data storage is disabled
            or the current item has no configuration.
        """
        if not self._store_signal_config:
            return None
        signal_info = self.itemData(self.currentIndex())
        return signal_info if isinstance(signal_info, dict) else None

    def update_signals_from_signal_classes(self, ndim_filter: int | list[int] | None = None):
        """Refresh signals from ``device_manager.get_bec_signals`` for class-based filtering.

        Args:
            ndim_filter: Optional dimensionality filter overriding the configured value for
                this refresh.
        """
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

        combo_items: list[str | tuple[str, dict]] = []
        item_tooltips: dict[int, str] = {}
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
                combo_items.append((signal_name, signal_config))
            else:
                combo_items.append(signal_name)

            storage_name = signal_config.get("storage_name", "")
            if storage_name:
                item_tooltips[len(combo_items) - 1] = storage_name

        self.signals = combo_items
        tooltip_offset = 1 if self._set_first_element_as_empty and self.count() else 0
        for item_index, tooltip in item_tooltips.items():
            self.setItemData(item_index + tooltip_offset, tooltip, Qt.ItemDataRole.ToolTipRole)
        self.check_validity(self.currentText())

    @SafeSlot()
    def reset_selection(self):
        """Reset the current selection and refresh available signals."""
        self.setCurrentText("")
        self.update_signals_from_filters()
        self.device_signal_changed.emit("")

    @SafeSlot(str)
    def on_text_changed(self, text: str):
        """Validate the current text when edited or selected.

        Args:
            text: Current combobox text.
        """
        self.check_validity(text)

    @Slot(str)
    def check_validity(self, input_text: str) -> None:
        """Validate current text and update visual state.

        Args:
            input_text: Current combobox text.
        """
        if self._signal_class_filter:
            is_valid = not (self._require_device and not self._device) and self.validate_signal(
                input_text
            )
        else:
            is_valid = self.validate_device(self._device) and self.validate_signal(input_text)

        if is_valid:
            self._is_valid_input = True
            self.device_signal_changed.emit(input_text)
        else:
            self._is_valid_input = False
            self.signal_reset.emit()
        self._update_validity_style(self._is_valid_input)

    def cleanup(self):
        """Cleanup the widget."""
        if self._device_update_register is not None:
            self.bec_dispatcher.client.callbacks.remove(self._device_update_register)
            self._device_update_register = None
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
        self.check_validity(self.currentText())

    def _update_validity_style(self, is_valid: bool) -> None:
        border_color = "transparent" if is_valid or not self.isEnabled() else "red"
        self.setStyleSheet(f"border: 1px solid {border_color};")

    def _replace_signal_items(self, items: list[str | tuple[str, dict]] | None = None):
        combo_items = self._signals if items is None else items
        display_items = [""] + combo_items if self._set_first_element_as_empty else combo_items
        replace_combobox_items(
            self, display_items, preserve_current_text=bool(self.currentText()), block_signals=True
        )
        self._completer_model.setStringList(
            [entry if isinstance(entry, str) else entry[0] for entry in combo_items]
        )

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
        if not signal:
            return False
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
