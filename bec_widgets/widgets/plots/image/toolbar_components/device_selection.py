from qtpy.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from bec_widgets.utils.toolbars.actions import WidgetAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle, ToolbarComponents
from bec_widgets.utils.toolbars.connections import BundleConnection
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.device_input.signal_combobox.signal_combobox import SignalComboBox


class DeviceSelection(QWidget):
    """Device and signal selection widget for image toolbar."""

    def __init__(self, parent=None, client=None):
        super().__init__(parent=parent)

        self.client = client
        self.supported_signals = [
            "PreviewSignal",
            "AsyncSignal",
            "AsyncMultiSignal",
            "DynamicSignal",
        ]

        # Create device combobox with signal class filter
        # This will only show devices that have signals matching the supported signal classes
        self.device_combo_box = DeviceComboBox(
            parent=self, client=self.client, signal_class_filter=self.supported_signals
        )
        self.device_combo_box.setToolTip("Select Device")
        self.device_combo_box.setEditable(True)
        # Set expanding size policy so it grows with available space
        self.device_combo_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.device_combo_box.lineEdit().setPlaceholderText("Select Device")

        # Configure SignalComboBox to filter by PreviewSignal and supported async signals
        # Also filter by ndim (1D and 2D only) for Image widget
        self.signal_combo_box = SignalComboBox(
            parent=self,
            client=self.client,
            signal_class_filter=[
                "PreviewSignal",
                "AsyncSignal",
                "AsyncMultiSignal",
                "DynamicSignal",
            ],
            ndim_filter=[1, 2],  # Only show 1D and 2D signals for Image widget
            store_signal_config=True,
            require_device=True,
        )
        self.signal_combo_box.setToolTip("Select Signal")
        self.signal_combo_box.setEditable(True)
        # Set expanding size policy so it grows with available space
        self.signal_combo_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.signal_combo_box.lineEdit().setPlaceholderText("Select Signal")

        # Connect comboboxes together
        self.device_combo_box.currentTextChanged.connect(self.signal_combo_box.set_device)
        self.device_combo_box.device_reset.connect(self.signal_combo_box.reset_selection)

        # Simple horizontal layout with stretch to fill space
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.device_combo_box, stretch=1)
        layout.addWidget(self.signal_combo_box, stretch=1)

    def set_device_and_signal(self, device: str | None, signal: str | None) -> None:
        """Set the displayed device and signal without emitting selection signals."""
        device = device or ""
        signal = signal or ""

        self.device_combo_box.blockSignals(True)
        self.signal_combo_box.blockSignals(True)

        try:
            if device:
                # Set device in device_combo_box
                index = self.device_combo_box.findText(device)
                if index >= 0:
                    self.device_combo_box.setCurrentIndex(index)
                else:
                    # Device not found in list, but still set it
                    self.device_combo_box.setCurrentText(device)

                # Only update signal combobox device filter if it's actually changing
                # This prevents redundant repopulation which can cause duplicates !!!!
                current_device = getattr(self.signal_combo_box, "_device", None)
                if current_device != device:
                    self.signal_combo_box.set_device(device)

                # Sync signal combobox selection
                if signal:
                    # Try to find the signal by component_name (which is what's displayed)
                    found = False
                    for i in range(self.signal_combo_box.count()):
                        text = self.signal_combo_box.itemText(i)
                        config_data = self.signal_combo_box.itemData(i)

                        # Check if this matches our signal
                        if config_data:
                            component_name = config_data.get("component_name", "")
                            if text == component_name or text == signal:
                                self.signal_combo_box.setCurrentIndex(i)
                                found = True
                                break

                    if not found:
                        # Fallback: try to match the signal directly
                        index = self.signal_combo_box.findText(signal)
                        if index >= 0:
                            self.signal_combo_box.setCurrentIndex(index)
            else:
                # No device set, clear selections
                self.device_combo_box.setCurrentText("")
                self.signal_combo_box.reset_selection()
        finally:
            # Always unblock signals
            self.device_combo_box.blockSignals(False)
            self.signal_combo_box.blockSignals(False)

    def set_connection_status(self, status: str, message: str | None = None) -> None:
        tooltip = f"Connection status: {status}"
        if message:
            tooltip = f"{tooltip}\n{message}"
        self.device_combo_box.setToolTip(tooltip)
        self.signal_combo_box.setToolTip(tooltip)

        if not self.device_combo_box.is_valid_input or not self.signal_combo_box.is_valid_input:
            return

        if status == "error":
            style = "border: 1px solid orange;"
        else:
            style = "border: 1px solid transparent;"

        self.device_combo_box.setStyleSheet(style)
        self.signal_combo_box.setStyleSheet(style)

    def cleanup(self):
        """Clean up the widget resources."""
        self.device_combo_box.close()
        self.device_combo_box.deleteLater()
        self.signal_combo_box.close()
        self.signal_combo_box.deleteLater()


def device_selection_bundle(components: ToolbarComponents, client=None) -> ToolbarBundle:
    """
    Creates a device selection toolbar bundle for Image widget.

    Includes a resizable splitter after the device selection. All subsequent bundles'
    actions will appear compactly after the splitter with no gaps.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.
        client: The BEC client instance.

    Returns:
        ToolbarBundle: The device selection toolbar bundle.
    """
    device_selection_widget = DeviceSelection(parent=components.toolbar, client=client)
    components.add_safe(
        "device_selection", WidgetAction(widget=device_selection_widget, adjust_size=False)
    )

    bundle = ToolbarBundle("device_selection", components)
    bundle.add_action("device_selection")

    bundle.add_splitter(
        name="device_selection_splitter",
        target_widget=device_selection_widget,
        min_width=210,
        max_width=600,
    )

    return bundle


class DeviceSelectionConnection(BundleConnection):
    """
    Connection helper for the device selection bundle.
    """

    def __init__(self, components: ToolbarComponents, target_widget=None):
        super().__init__(parent=components.toolbar)
        self.bundle_name = "device_selection"
        self.components = components
        self.target_widget = target_widget
        self._connected = False
        self.register_property_sync("device", self._sync_from_device)
        self.register_property_sync("signal", self._sync_from_signal)
        self.register_property_sync("connection_status", self._sync_connection_status)
        self.register_property_sync("connection_error", self._sync_connection_status)

    def _widget(self) -> DeviceSelection:
        return self.components.get_action("device_selection").widget

    def connect(self):
        if self._connected:
            return
        widget = self._widget()
        widget.device_combo_box.device_selected.connect(
            self.target_widget.on_device_selection_changed
        )
        widget.signal_combo_box.device_signal_changed.connect(
            self.target_widget.on_device_selection_changed
        )
        self.connect_property_sync(self.target_widget)
        self._connected = True

    def disconnect(self):
        if not self._connected:
            return
        widget = self._widget()
        widget.device_combo_box.device_selected.disconnect(
            self.target_widget.on_device_selection_changed
        )
        widget.signal_combo_box.device_signal_changed.disconnect(
            self.target_widget.on_device_selection_changed
        )
        self.disconnect_property_sync(self.target_widget)
        self._connected = False
        widget.cleanup()

    def _sync_from_device(self, _):
        try:
            widget = self._widget()
        except Exception:
            return

        widget.set_device_and_signal(self.target_widget.device, self.target_widget.signal)
        self.target_widget._sync_signal_from_toolbar()

    def _sync_from_signal(self, _):
        try:
            widget = self._widget()
        except Exception:
            return

        widget.set_device_and_signal(self.target_widget.device, self.target_widget.signal)

    def _sync_connection_status(self, _):
        try:
            widget = self._widget()
        except Exception:
            return

        widget.set_connection_status(
            self.target_widget._config.connection_status,
            self.target_widget._config.connection_error,
        )
