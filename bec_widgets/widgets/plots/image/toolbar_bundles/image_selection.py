from bec_lib.device import ReadoutPriority
from qtpy.QtCore import Qt
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
            device_filter=BECDeviceFilter.DEVICE, readout_priority_filter=[ReadoutPriority.ASYNC]
        )
        self.device_combo_box.addItem("", None)
        self.device_combo_box.setCurrentText("")
        self.device_combo_box.setToolTip("Select Device")
        self.device_combo_box.setItemDelegate(NoCheckDelegate(self.device_combo_box))

        self.add_action("monitor", WidgetAction(widget=self.device_combo_box, adjust_size=True))

        # 2) Dimension combo box
        self.dim_combo_box = QComboBox()
        self.dim_combo_box.addItems(["auto", "1d", "2d"])
        self.dim_combo_box.setCurrentText("auto")
        self.dim_combo_box.setToolTip("Monitor Dimension")
        self.dim_combo_box.setFixedWidth(60)
        self.dim_combo_box.setItemDelegate(NoCheckDelegate(self.dim_combo_box))

        self.add_action("dim_combo", WidgetAction(widget=self.dim_combo_box, adjust_size=True))

        # Connect slots, a device will be connected upon change of any combobox
        self.device_combo_box.currentTextChanged.connect(lambda: self.connect_monitor())
        self.dim_combo_box.currentTextChanged.connect(lambda: self.connect_monitor())

    @SafeSlot()
    def connect_monitor(self):
        dim = self.dim_combo_box.currentText()
        self.target_widget.image(monitor=self.device_combo_box.currentText(), monitor_type=dim)
