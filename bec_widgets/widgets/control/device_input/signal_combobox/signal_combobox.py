from __future__ import annotations

from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtWidgets import QComboBox, QSizePolicy

from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.filter_io import ComboBoxFilterHandler, FilterIO
from bec_widgets.utils.ophyd_kind_util import Kind
from bec_widgets.widgets.control.device_input.base_classes.device_signal_input_base import (
    DeviceSignalInputBase,
    DeviceSignalInputBaseConfig,
)


class SignalComboBox(DeviceSignalInputBase, QComboBox):
    """
    Line edit widget for device input with autocomplete for device names.

    Args:
        parent: Parent widget.
        client: BEC client object.
        config: Device input configuration.
        gui_id: GUI ID.
        device: Device name to filter signals from.
        signal_filter: Signal filter, list of signal kinds from ophyd Kind enum. Check DeviceSignalInputBase for more details.
        signal_class_filter: List of signal classes to filter the signals by. Only signals of these classes will be shown.
        ndim_filter: Dimensionality filter, int or list of ints to filter signals by their number of dimensions. If signal do not support ndim, it will be included in the selection anyway.
        default: Default device name.
        arg_name: Argument name, can be used for the other widgets which has to call some other function in bec using correct argument names.
        store_signal_config: Whether to store the full signal config in the combobox item data.
        require_device: If True, signals are only shown/validated when a device is set.
    Signals:
        device_signal_changed: Emitted when the current text represents a valid signal selection.
        signal_reset: Emitted when validation fails and the selection should be treated as cleared.
    """

    USER_ACCESS = ["set_signal", "set_device", "signals", "get_signal_name"]

    ICON_NAME = "list_alt"
    PLUGIN = True
    RPC = True

    device_signal_changed = Signal(str)
    signal_reset = Signal()

    def __init__(
        self,
        parent=None,
        client=None,
        config: DeviceSignalInputBaseConfig | None = None,
        gui_id: str | None = None,
        device: str | None = None,
        signal_filter: list[Kind] | None = None,
        signal_class_filter: list[str] | None = None,
        ndim_filter: int | list[int] | None = None,
        default: str | None = None,
        arg_name: str | None = None,
        store_signal_config: bool = True,
        require_device: bool = False,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        if arg_name is not None:
            self.config.arg_name = arg_name
            self.arg_name = arg_name
        if default is not None:
            self.set_device(default)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumSize(QSize(100, 0))
        self._set_first_element_as_empty = True
        self._signal_class_filter = signal_class_filter or []
        self._store_signal_config = store_signal_config
        self.config.ndim_filter = ndim_filter or None
        self._require_device = require_device
        self._is_valid_input = False

        # Note: Runtime arguments (e.g. device, default, arg_name) intentionally take
        # precedence over values from the passed-in config. Full reconciliation and
        # restoration of state between designer-provided config and runtime arguments
        # is not yet implemented, as earlier attempts caused issues with QtDesigner.
        self.currentTextChanged.connect(self.on_text_changed)

        # Kind filtering is always applied; class filtering is additive. If signal_filter is None,
        # we default to hinted+normal, even when signal_class_filter is empty or None. To disable
        # kinds, pass an explicit signal_filter or toggle include_* after init.
        if signal_filter is not None:
            self.set_filter(signal_filter)
        else:
            self.set_filter([Kind.hinted, Kind.normal, Kind.config])

        if device is not None:
            self.set_device(device)
        if default is not None:
            self.set_signal(default)

    @SafeSlot(str)
    def set_device(self, device: str | None):
        """
        Set the device. When signal_class_filter is active, ensures base-class
        logic runs and then refreshes the signal list to show only signals from
        that device matching the signal class filter.

        Args:
            device(str): device name.
        """
        super().set_device(device)

        if self._signal_class_filter:
            # Refresh the signal list to show only this device's signals
            self.update_signals_from_signal_classes()

    @SafeSlot()
    @SafeSlot(dict, dict)
    def update_signals_from_filters(
        self, content: dict | None = None, metadata: dict | None = None
    ):
        """Update the filters for the combobox.
        When signal_class_filter is active, skip the normal Kind-based filtering.

        Args:
            content (dict | None): Content dictionary from BEC event.
            metadata (dict | None): Metadata dictionary from BEC event.
        """
        super().update_signals_from_filters(content, metadata)

        if self._signal_class_filter:
            self.update_signals_from_signal_classes()
            return
        # pylint: disable=protected-access
        if FilterIO._find_handler(self) is ComboBoxFilterHandler:
            if len(self._config_signals) > 0:
                self.insertItem(
                    len(self._hinted_signals) + len(self._normal_signals), "Config Signals"
                )
                self.model().item(len(self._hinted_signals) + len(self._normal_signals)).setEnabled(
                    False
                )
            if len(self._normal_signals) > 0:
                self.insertItem(len(self._hinted_signals), "Normal Signals")
                self.model().item(len(self._hinted_signals)).setEnabled(False)
            if len(self._hinted_signals) > 0:
                self.insertItem(0, "Hinted Signals")
                self.model().item(0).setEnabled(False)

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

    @SafeProperty("QStringList")
    def signal_class_filter(self) -> list[str]:
        """
        Get the list of signal classes to filter.

        Returns:
            list[str]: List of signal class names to filter.
        """
        return self._signal_class_filter

    @signal_class_filter.setter
    def signal_class_filter(self, value: list[str] | None):
        """
        Set the signal class filter.

        Args:
            value (list[str] | None): List of signal class names to filter, or None/empty
                to disable class-based filtering and revert to the default behavior.
        """
        normalized_value = value or []
        self._signal_class_filter = normalized_value
        self.config.signal_class_filter = normalized_value
        if self._signal_class_filter:
            self.update_signals_from_signal_classes()
        else:
            self.update_signals_from_filters()

    @SafeProperty(int)
    def ndim_filter(self) -> int:
        """Dimensionality filter for signals."""
        return self.config.ndim_filter if isinstance(self.config.ndim_filter, int) else -1

    @ndim_filter.setter
    def ndim_filter(self, value: int):
        self.config.ndim_filter = None if value < 0 else value
        if self._signal_class_filter:
            self.update_signals_from_signal_classes(ndim_filter=self.config.ndim_filter)

    @SafeProperty(bool)
    def require_device(self) -> bool:
        """
        If True, signals are only shown/validated when a device is set.

        Note:
            This property affects list rebuilding only when a signal_class_filter
            is active. Without a signal class filter, the available signals are
            managed by the standard Kind-based filtering.
        """
        return self._require_device

    @require_device.setter
    def require_device(self, value: bool):
        self._require_device = value
        # Rebuild list when toggled, but only when using signal_class_filter
        if self._signal_class_filter:
            self.update_signals_from_signal_classes()

    def set_to_obj_name(self, obj_name: str) -> bool:
        """
        Set the combobox to the object name of the signal.

        Args:
            obj_name (str): Object name of the signal.

        Returns:
            bool: True if the object name was found and set, False otherwise.
        """
        for i in range(self.count()):
            signal_data = self.itemData(i)
            if signal_data and signal_data.get("obj_name") == obj_name:
                self.setCurrentIndex(i)
                return True
        return False

    def set_to_first_enabled(self) -> bool:
        """
        Set the combobox to the first enabled item.

        Returns:
            bool: True if an enabled item was found and set, False otherwise.
        """
        for i in range(self.count()):
            if self.model().item(i).isEnabled():
                self.setCurrentIndex(i)
                return True
        return False

    def get_signal_name(self) -> str:
        """
        Get the signal name from the combobox.

        Returns:
            str: The signal name.
        """
        signal_name = self.currentText()
        index = self.findText(signal_name)
        if index == -1:
            return signal_name

        signal_info = self.itemData(index)
        if signal_info:
            signal_name = signal_info.get("obj_name", signal_name)

        return signal_name if signal_name else ""

    def get_signal_config(self) -> dict | None:
        """
        Get the signal config from the combobox for the currently selected signal.

        Returns:
            dict | None: The signal configuration dictionary or None if not available.
        """
        if not self._store_signal_config:
            return None

        index = self.currentIndex()
        if index == -1:
            return None

        signal_info = self.itemData(index)
        return signal_info if signal_info else None

    def update_signals_from_signal_classes(self, ndim_filter: int | list[int] | None = None):
        """
        Update the combobox with signals filtered by signal classes and optionally by ndim.
        Uses device_manager.get_bec_signals() to retrieve signals.
        If a device is set, only shows signals from that device.

        Args:
            ndim_filter (int | list[int] | None): Filter signals by dimensionality.
                If provided, only signals with matching ndim will be included.
                Can be a single int or a list of ints. Use None to include all dimensions.
                If not provided, uses the previously set ndim_filter.
        """
        if not self._signal_class_filter:
            return

        if self._require_device and not self._device:
            self.clear()
            self._signals = []
            FilterIO.set_selection(widget=self, selection=self._signals)
            return

        # Update stored ndim_filter if a new one is provided
        if ndim_filter is not None:
            self.config.ndim_filter = ndim_filter

        self.clear()

        # Get signals with ndim filtering applied at the FilterIO level
        signals = FilterIO.update_with_signal_class(
            widget=self,
            signal_class_filter=self._signal_class_filter,
            client=self.client,
            ndim_filter=self.config.ndim_filter,  # Pass ndim_filter to FilterIO
        )

        # Track signals for validation and FilterIO selection
        self._signals = []

        for device_name, signal_name, signal_config in signals:
            # Filter by device if one is set
            if self._device and device_name != self._device:
                continue
            if self._signal_filter:
                kind_str = signal_config.get("kind_str")
                if kind_str is not None and kind_str not in {
                    kind.name for kind in self._signal_filter
                }:
                    continue

            # Get storage_name for tooltip
            storage_name = signal_config.get("storage_name", "")

            # Store the full signal config as item data if requested
            if self._store_signal_config:
                self.addItem(signal_name, signal_config)
            else:
                self.addItem(signal_name)

            # Track for validation
            self._signals.append(signal_name)

            # Set tooltip to storage_name (Qt.ToolTipRole = 3)
            if storage_name:
                self.setItemData(self.count() - 1, storage_name, Qt.ItemDataRole.ToolTipRole)

        # Keep FilterIO selection in sync for validate_signal
        FilterIO.set_selection(widget=self, selection=self._signals)

    @SafeSlot()
    def reset_selection(self):
        """Reset the selection of the combobox."""
        self.clear()
        self.setItemText(0, "Select a device")
        self.update_signals_from_filters()
        self.device_signal_changed.emit("")

    @SafeSlot(str)
    def on_text_changed(self, text: str):
        """Validate and emit only when the signal is valid.
        For a positioner, the readback value has to be renamed to the device name.
        When using signal_class_filter, device validation is skipped.
        """
        self.check_validity(text)

    def check_validity(self, input_text: str) -> None:
        """Check if the current value is a valid signal and emit only when valid."""
        if self._signal_class_filter:
            if self._require_device and (not self._device or not input_text):
                is_valid = False
            else:
                is_valid = self.validate_signal(input_text)
        else:
            if self._require_device and not self.validate_device(self._device):
                is_valid = False
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

    @property
    def selected_signal_comp_name(self) -> str:
        return dict(self.signals).get(self.currentText(), {}).get("component_name", "")

    @property
    def is_valid_input(self) -> bool:
        """Whether the current text represents a valid signal selection."""
        return self._is_valid_input


if __name__ == "__main__":  # pragma: no cover
    # pylint: disable=import-outside-toplevel
    from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

    from bec_widgets.utils.colors import apply_theme

    app = QApplication([])
    apply_theme("dark")
    widget = QWidget()
    widget.setFixedSize(200, 200)
    layout = QVBoxLayout()
    widget.setLayout(layout)
    box = SignalComboBox(
        device="waveform",
        signal_class_filter=["AsyncSignal", "AsyncMultiSignal"],
        ndim_filter=[1, 2],
        store_signal_config=True,
        signal_filter=[Kind.hinted, Kind.normal, Kind.config],
    )  # change signal filter class to test
    box.setEditable(True)
    layout.addWidget(box)
    widget.show()
    app.exec_()
