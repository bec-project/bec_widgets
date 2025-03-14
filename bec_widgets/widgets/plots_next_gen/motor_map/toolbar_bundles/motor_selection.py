from bec_lib.device import ReadoutPriority
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QStyledItemDelegate

from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.qt_utils.toolbar import ToolbarBundle, WidgetAction
from bec_widgets.widgets.control.device_input.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox


class NoCheckDelegate(QStyledItemDelegate):
    """To reduce space in combo boxes by removing the checkmark."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # Remove any check indicator
        option.checkState = Qt.Unchecked


class MotorSelectionToolbarBundle(ToolbarBundle):
    """
    A bundle of actions for a toolbar that selects motors.
    """

    def __init__(self, bundle_id="motor_selection", target_widget=None, **kwargs):
        super().__init__(bundle_id=bundle_id, actions=[], **kwargs)
        self.target_widget = target_widget

        # Motor X
        self.motor_x = DeviceComboBox(device_filter=[BECDeviceFilter.POSITIONER])
        self.motor_x.addItem("", None)
        self.motor_x.setCurrentText("")
        self.motor_x.setToolTip("Select Motor X")
        self.motor_x.setItemDelegate(NoCheckDelegate(self.motor_x))

        # Motor X
        self.motor_y = DeviceComboBox(device_filter=[BECDeviceFilter.POSITIONER])
        self.motor_y.addItem("", None)
        self.motor_y.setCurrentText("")
        self.motor_y.setToolTip("Select Motor Y")
        self.motor_y.setItemDelegate(NoCheckDelegate(self.motor_y))

        self.add_action("motor_x", WidgetAction(widget=self.motor_x, adjust_size=False))
        self.add_action("motor_y", WidgetAction(widget=self.motor_y, adjust_size=False))

        # Connect slots, a device will be connected upon change of any combobox
        self.motor_x.currentTextChanged.connect(lambda: self.connect_motors())
        self.motor_y.currentTextChanged.connect(lambda: self.connect_motors())

    @SafeSlot()
    def connect_motors(self):
        motor_x = self.motor_x.currentText()
        motor_y = self.motor_y.currentText()

        if motor_x != "" and motor_y != "":
            if (
                motor_x != self.target_widget.config.x_motor.name
                or motor_y != self.target_widget.config.y_motor.name
            ):
                self.target_widget.map(motor_x, motor_y)
