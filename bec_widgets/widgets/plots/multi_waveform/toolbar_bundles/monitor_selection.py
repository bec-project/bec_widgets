from bec_lib.device import ReadoutPriority
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QStyledItemDelegate

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbar import ToolbarBundle, WidgetAction
from bec_widgets.widgets.control.device_input.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget


class NoCheckDelegate(QStyledItemDelegate):
    """To reduce space in combo boxes by removing the checkmark."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # Remove any check indicator
        option.checkState = Qt.Unchecked


class MultiWaveformSelectionToolbarBundle(ToolbarBundle):
    """
    A bundle of actions for a toolbar that selects motors.
    """

    def __init__(self, bundle_id="monitor_selection", target_widget=None, **kwargs):
        super().__init__(bundle_id=bundle_id, actions=[], **kwargs)
        self.target_widget = target_widget

        # Monitor Selection
        self.monitor = DeviceComboBox(
            device_filter=BECDeviceFilter.DEVICE,
            readout_priority_filter=ReadoutPriority.ASYNC,
            parent_id=self.target_widget.gui_id,
        )
        self.monitor.addItem("", None)
        self.monitor.setCurrentText("")
        self.monitor.setToolTip("Select Monitor")
        self.monitor.setItemDelegate(NoCheckDelegate(self.monitor))
        self.add_action("monitor", WidgetAction(widget=self.monitor, adjust_size=False))

        # Colormap Selection
        self.colormap_widget = BECColorMapWidget(cmap="magma", parent_id=self.target_widget.gui_id)
        self.add_action("color_map", WidgetAction(widget=self.colormap_widget, adjust_size=False))

        # Connect slots, a device will be connected upon change of any combobox
        self.monitor.currentTextChanged.connect(lambda: self.connect())
        self.colormap_widget.colormap_changed_signal.connect(self.change_colormap)

    @SafeSlot()
    def connect(self):
        monitor = self.monitor.currentText()

        if monitor != "":
            if monitor != self.target_widget.config.monitor:
                self.target_widget.monitor = monitor

    @SafeSlot(str)
    def change_colormap(self, colormap: str):
        self.target_widget.color_palette = colormap
