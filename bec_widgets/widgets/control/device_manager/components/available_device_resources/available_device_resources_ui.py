from qtpy.QtCore import QMetaObject, Qt
from qtpy.QtWidgets import QAbstractItemView, QListView, QListWidget, QVBoxLayout


class Ui_availableDeviceResources(object):
    def setupUi(self, availableDeviceResources):
        if not availableDeviceResources.objectName():
            availableDeviceResources.setObjectName("availableDeviceResources")
        self.verticalLayout = QVBoxLayout(availableDeviceResources)
        self.verticalLayout.setObjectName("verticalLayout")
        self.tag_groups_list = QListWidget(availableDeviceResources)
        self.tag_groups_list.setObjectName("tag_groups_list")
        self.tag_groups_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tag_groups_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.tag_groups_list.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.tag_groups_list.setMovement(QListView.Movement.Static)
        self.tag_groups_list.setSpacing(2)
        self.tag_groups_list.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        self.tag_groups_list.setDragEnabled(True)
        self.tag_groups_list.setAcceptDrops(False)
        self.tag_groups_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        availableDeviceResources.setMinimumWidth(250)
        availableDeviceResources.resize(250, availableDeviceResources.height())

        self.verticalLayout.addWidget(self.tag_groups_list)

        QMetaObject.connectSlotsByName(availableDeviceResources)
