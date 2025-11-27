from qtpy.QtWidgets import QHBoxLayout, QWidget

from bec_widgets.utils.toolbars.actions import NoCheckDelegate, WidgetAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle, ToolbarComponents
from bec_widgets.utils.toolbars.connections import BundleConnection
from bec_widgets.widgets.control.device_input.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox


class MotorSelection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.motor_x = DeviceComboBox(parent=self, device_filter=[BECDeviceFilter.POSITIONER])
        self.motor_x.addItem("", None)
        self.motor_x.setCurrentText("")
        self.motor_x.setToolTip("Select Motor X")
        self.motor_x.setItemDelegate(NoCheckDelegate(self.motor_x))
        self.motor_x.setEditable(True)
        self.motor_y = DeviceComboBox(parent=self, device_filter=[BECDeviceFilter.POSITIONER])
        self.motor_y.addItem("", None)
        self.motor_y.setCurrentText("")
        self.motor_y.setToolTip("Select Motor Y")
        self.motor_y.setItemDelegate(NoCheckDelegate(self.motor_y))
        self.motor_y.setEditable(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.motor_x)
        layout.addWidget(self.motor_y)

    def set_motors(self, motor_x: str | None, motor_y: str | None) -> None:
        """Set the displayed motors without emitting selection signals."""
        motor_x = motor_x or ""
        motor_y = motor_y or ""
        self.motor_x.blockSignals(True)
        self.motor_y.blockSignals(True)
        try:
            if motor_x:
                self.motor_x.set_device(motor_x)
                self.motor_x.check_validity(motor_x)
            else:
                self.motor_x.setCurrentText("")
            if motor_y:
                self.motor_y.set_device(motor_y)
                self.motor_y.check_validity(motor_y)
            else:
                self.motor_y.setCurrentText("")
        finally:
            self.motor_x.blockSignals(False)
            self.motor_y.blockSignals(False)

    def cleanup(self):
        """
        Cleans up the action, if necessary.
        """
        self.motor_x.close()
        self.motor_x.deleteLater()
        self.motor_y.close()
        self.motor_y.deleteLater()


def motor_selection_bundle(components: ToolbarComponents) -> ToolbarBundle:
    """
    Creates a workspace toolbar bundle for MotorMap.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The workspace toolbar bundle.
    """

    motor_selection_widget = MotorSelection(parent=components.toolbar)
    components.add_safe(
        "motor_selection", WidgetAction(widget=motor_selection_widget, adjust_size=False)
    )

    bundle = ToolbarBundle("motor_selection", components)
    bundle.add_action("motor_selection")
    return bundle


class MotorSelectionConnection(BundleConnection):
    """
    Connection helper for the motor selection bundle.
    """

    def __init__(self, components: ToolbarComponents, target_widget=None):
        super().__init__(parent=components.toolbar)
        self.bundle_name = "motor_selection"
        self.components = components
        self.target_widget = target_widget
        self._connected = False

    def _widget(self) -> MotorSelection:
        return self.components.get_action("motor_selection").widget

    def connect(self):
        if self._connected:
            return
        widget = self._widget()
        widget.motor_x.currentTextChanged.connect(self.target_widget.on_motor_selection_changed)
        widget.motor_y.currentTextChanged.connect(self.target_widget.on_motor_selection_changed)
        self._connected = True

    def disconnect(self):
        if not self._connected:
            return
        widget = self._widget()
        widget.motor_x.currentTextChanged.disconnect(self.target_widget.on_motor_selection_changed)
        widget.motor_y.currentTextChanged.disconnect(self.target_widget.on_motor_selection_changed)
        self._connected = False
        widget.cleanup()
