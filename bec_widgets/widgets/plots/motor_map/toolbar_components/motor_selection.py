from qtpy.QtWidgets import QHBoxLayout, QToolBar, QWidget

from bec_widgets.utils.toolbars.actions import NoCheckDelegate, ToolBarAction
from bec_widgets.widgets.control.device_input.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox


class MotorSelectionAction(ToolBarAction):
    def __init__(self, parent=None):
        super().__init__(icon_path=None, tooltip=None, checkable=False)
        self.motor_x = DeviceComboBox(parent=parent, device_filter=[BECDeviceFilter.POSITIONER])
        self.motor_x.addItem("", None)
        self.motor_x.setCurrentText("")
        self.motor_x.setToolTip("Select Motor X")
        self.motor_x.setItemDelegate(NoCheckDelegate(self.motor_x))
        self.motor_y = DeviceComboBox(parent=parent, device_filter=[BECDeviceFilter.POSITIONER])
        self.motor_y.addItem("", None)
        self.motor_y.setCurrentText("")
        self.motor_y.setToolTip("Select Motor Y")
        self.motor_y.setItemDelegate(NoCheckDelegate(self.motor_y))

        self.container = QWidget(parent)
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.motor_x)
        layout.addWidget(self.motor_y)
        self.container.setLayout(layout)
        self.action = self.container

    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        """
        Adds the widget to the toolbar.

        Args:
            toolbar (QToolBar): The toolbar to add the widget to.
            target (QWidget): The target widget for the action.
        """

        toolbar.addWidget(self.container)

    def cleanup(self):
        """
        Cleans up the action, if necessary.
        """
        self.motor_x.close()
        self.motor_x.deleteLater()
        self.motor_y.close()
        self.motor_y.deleteLater()
        self.container.close()
        self.container.deleteLater()
