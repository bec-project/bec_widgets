from qtpy.QtCore import QMetaObject, Qt
from qtpy.QtWidgets import QLabel, QListWidget, QVBoxLayout

from bec_widgets.widgets.control.device_manager.components._util import mimedata_from_configs
from bec_widgets.widgets.control.device_manager.components.constants import (
    CONFIG_DATA_ROLE,
    MIME_DEVICE_CONFIG,
)


class _DeviceListWiget(QListWidget):

    def _item_iter(self):
        return (self.item(i) for i in range(self.count()))

    def all_configs(self):
        return [item.data(CONFIG_DATA_ROLE) for item in self._item_iter()]

    def mimeTypes(self):
        return [MIME_DEVICE_CONFIG]

    def mimeData(self, items):
        return mimedata_from_configs(item.data(CONFIG_DATA_ROLE) for item in items)


class Ui_AvailableDeviceGroup(object):
    def setupUi(self, AvailableDeviceGroup):
        if not AvailableDeviceGroup.objectName():
            AvailableDeviceGroup.setObjectName("AvailableDeviceGroup")
        AvailableDeviceGroup.setMinimumWidth(150)
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        AvailableDeviceGroup.set_layout(self.verticalLayout)

        title_layout = AvailableDeviceGroup.get_title_layout()

        self.n_included = QLabel(AvailableDeviceGroup, text="...")
        self.n_included.setObjectName("n_included")
        title_layout.addWidget(self.n_included)

        self.device_list = _DeviceListWiget(AvailableDeviceGroup)
        self.device_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.device_list.setObjectName("device_list")
        self.device_list.setFrameStyle(0)
        self.device_list.setDragEnabled(True)
        self.device_list.setAcceptDrops(False)
        self.device_list.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.verticalLayout.addWidget(self.device_list)

        QMetaObject.connectSlotsByName(AvailableDeviceGroup)
