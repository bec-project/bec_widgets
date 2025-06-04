from bec_lib.device import ReadoutPriority
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QComboBox, QStyledItemDelegate

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbar import ToolbarBundle, WidgetAction
from bec_widgets.widgets.control.device_input.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox


class NoCheckDelegate(QStyledItemDelegate):
    """To reduce space in combo boxes by removing the checkmark."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # Remove any check indicator
        option.checkState = Qt.Unchecked


class MonitorSelectionToolbarBundle(ToolbarBundle):
    """
    A bundle of actions for a toolbar that controls monitor selection on a plot.
    """

    def __init__(self, bundle_id="device_selection", target_widget=None, **kwargs):
        super().__init__(bundle_id=bundle_id, actions=[], **kwargs)
        self.target_widget = target_widget

        # 1) Device combo box
        self.device_combo_box = DeviceComboBox(
            parent=self.target_widget,
            device_filter=BECDeviceFilter.DEVICE,
            readout_priority_filter=[ReadoutPriority.ASYNC],
        )
        self.device_combo_box.addItem("", None)
        self.device_combo_box.setCurrentText("")
        self.device_combo_box.setToolTip("Select Device")
        self.device_combo_box.setFixedWidth(150)
        self.device_combo_box.setItemDelegate(NoCheckDelegate(self.device_combo_box))

        self.add_action("monitor", WidgetAction(widget=self.device_combo_box, adjust_size=False))

        # 2) Dimension combo box
        self.dim_combo_box = QComboBox(parent=self.target_widget)
        self.dim_combo_box.addItems(["auto", "1d", "2d"])
        self.dim_combo_box.setCurrentText("auto")
        self.dim_combo_box.setToolTip("Monitor Dimension")
        self.dim_combo_box.setFixedWidth(100)
        self.dim_combo_box.setItemDelegate(NoCheckDelegate(self.dim_combo_box))

        self.add_action("dim_combo", WidgetAction(widget=self.dim_combo_box, adjust_size=False))

        self.device_combo_box.currentTextChanged.connect(self.connect_monitor)
        self.dim_combo_box.currentTextChanged.connect(self.connect_monitor)

        QTimer.singleShot(0, self._adjust_and_connect)

    def _adjust_and_connect(self):
        """
        Adjust the size of the device combo box and populate it with preview signals.
        Has to be done with QTimer.singleShot to ensure the UI is fully initialized, needed for testing.
        """
        self._populate_preview_signals()
        self._reverse_device_items()
        self.device_combo_box.setCurrentText("")  # set again default to empty string

    def _populate_preview_signals(self) -> None:
        """
        Populate the device combo box with preview‑signal devices in the
        format '<device>_<signal>' and store the tuple(device, signal) in
        the item's userData for later use.
        """
        preview_signals = self.target_widget.client.device_manager.get_bec_signals("PreviewSignal")
        for device, signal, signal_config in preview_signals:
            label = signal_config.get("obj_name", f"{device}_{signal}")
            self.device_combo_box.addItem(label, (device, signal, signal_config))

    def _reverse_device_items(self) -> None:
        """
        Reverse the current order of items in the device combo box while
        keeping their userData and restoring the previous selection.
        """
        current_text = self.device_combo_box.currentText()
        items = [
            (self.device_combo_box.itemText(i), self.device_combo_box.itemData(i))
            for i in range(self.device_combo_box.count())
        ]
        self.device_combo_box.clear()
        for text, data in reversed(items):
            self.device_combo_box.addItem(text, data)
        if current_text:
            self.device_combo_box.setCurrentText(current_text)

    @SafeSlot()
    def connect_monitor(self, *args, **kwargs):
        """
        Connect the target widget to the selected monitor based on the current device and dimension.

        If the selected device is a preview-signal device, it will use the tuple (device, signal) as the monitor.
        """
        dim = self.dim_combo_box.currentText()
        data = self.device_combo_box.currentData()

        if isinstance(data, tuple):
            self.target_widget.image(monitor=data, monitor_type="auto")
        else:
            self.target_widget.image(monitor=self.device_combo_box.currentText(), monitor_type=dim)
