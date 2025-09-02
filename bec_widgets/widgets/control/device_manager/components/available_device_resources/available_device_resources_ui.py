from __future__ import annotations

import itertools

from qtpy.QtCore import QMetaObject, Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QVBoxLayout,
)

from bec_widgets.utils.list_of_expandable_frames import ListOfExpandableFrames
from bec_widgets.widgets.control.device_manager.components._util import mimedata_from_configs
from bec_widgets.widgets.control.device_manager.components.available_device_resources.available_device_group import (
    AvailableDeviceGroup,
)
from bec_widgets.widgets.control.device_manager.components.constants import (
    CONFIG_DATA_ROLE,
    MIME_DEVICE_CONFIG,
)


class _ListOfDeviceGroups(ListOfExpandableFrames[AvailableDeviceGroup]):
    def mimeTypes(self):
        return [MIME_DEVICE_CONFIG]

    def mimeData(self, items):
        return mimedata_from_configs(
            itertools.chain.from_iterable(item.data(CONFIG_DATA_ROLE) for item in items)
        )


class Ui_availableDeviceResources(object):
    def setupUi(self, availableDeviceResources):
        if not availableDeviceResources.objectName():
            availableDeviceResources.setObjectName("availableDeviceResources")
        self.verticalLayout = QVBoxLayout(availableDeviceResources)
        self.verticalLayout.setObjectName("verticalLayout")

        self.search_layout = QHBoxLayout()
        self.verticalLayout.addLayout(self.search_layout)
        self.search_layout.addWidget(QLabel("Filter groups: "))
        self.search_box = QLineEdit()
        self.search_layout.addWidget(self.search_box)
        self.search_layout.addWidget(QLabel("Group by: "))
        self.grouping_selector = QComboBox()
        self.search_layout.addWidget(self.grouping_selector)

        self.device_groups_list = _ListOfDeviceGroups(
            availableDeviceResources, AvailableDeviceGroup
        )
        self.device_groups_list.setObjectName("device_groups_list")
        self.device_groups_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.device_groups_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.device_groups_list.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.device_groups_list.setMovement(QListView.Movement.Static)
        self.device_groups_list.setSpacing(2)
        self.device_groups_list.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        self.device_groups_list.setSelectionBehavior(QListWidget.SelectionBehavior.SelectItems)
        self.device_groups_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.device_groups_list.setDragEnabled(True)
        self.device_groups_list.setAcceptDrops(False)
        self.device_groups_list.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.device_groups_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        availableDeviceResources.setMinimumWidth(250)
        availableDeviceResources.resize(250, availableDeviceResources.height())

        self.verticalLayout.addWidget(self.device_groups_list)

        QMetaObject.connectSlotsByName(availableDeviceResources)
