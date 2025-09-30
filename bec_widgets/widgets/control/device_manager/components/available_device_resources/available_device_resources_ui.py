from __future__ import annotations

import itertools

from qtpy.QtCore import QMetaObject, Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
)

from bec_widgets.utils.list_of_expandable_frames import ListOfExpandableFrames
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.control.device_manager.components._util import mimedata_from_configs
from bec_widgets.widgets.control.device_manager.components.available_device_resources.available_device_group import (
    AvailableDeviceGroup,
)
from bec_widgets.widgets.control.device_manager.components.constants import (
    CONFIG_DATA_ROLE,
    MIME_DEVICE_CONFIG,
)


class _ListOfDeviceGroups(ListOfExpandableFrames[AvailableDeviceGroup]):

    def itemWidget(self, item: QListWidgetItem) -> AvailableDeviceGroup:
        return super().itemWidget(item)  # type: ignore

    def any_selected_devices(self):
        return self.selected_individual_devices() or self.selected_devices_from_groups()

    def selected_individual_devices(self):
        for widget in (self.itemWidget(self.item(i)) for i in range(self.count())):
            if (selected := widget.get_selection()) != set():
                return [dev.as_normal_device().model_dump() for dev in selected]
        return []

    def selected_devices_from_groups(self):
        selected_items = (self.item(r.row()) for r in self.selectionModel().selectedRows())
        widgets = (self.itemWidget(item) for item in selected_items)
        return list(itertools.chain.from_iterable(w.device_list.all_configs() for w in widgets))

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

        self._add_toolbar()

        # Main area with search and filter using a grid layout
        self.search_layout = QVBoxLayout()
        self.grid_layout = QGridLayout()

        self.grouping_selector = QComboBox()
        self.grouping_selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lbl_group = QLabel("Group by:")
        lbl_group.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.grid_layout.addWidget(lbl_group, 0, 0)
        self.grid_layout.addWidget(self.grouping_selector, 0, 1)

        self.search_box = QLineEdit()
        self.search_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lbl_filter = QLabel("Filter:")
        lbl_filter.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.grid_layout.addWidget(lbl_filter, 1, 0)
        self.grid_layout.addWidget(self.search_box, 1, 1)

        self.grid_layout.setColumnStretch(0, 0)
        self.grid_layout.setColumnStretch(1, 1)

        self.search_layout.addLayout(self.grid_layout)
        self.verticalLayout.addLayout(self.search_layout)

        self.device_groups_list = _ListOfDeviceGroups(
            availableDeviceResources, AvailableDeviceGroup
        )
        self.device_groups_list.setObjectName("device_groups_list")
        self.device_groups_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.device_groups_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.device_groups_list.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.device_groups_list.setMovement(QListView.Movement.Static)
        self.device_groups_list.setSpacing(4)
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

    def _add_toolbar(self):
        self.toolbar = ModularToolBar(self)
        io_bundle = ToolbarBundle("IO", self.toolbar.components)

        self.tb_add_selected = MaterialIconAction(
            icon_name="add_box", parent=self, tooltip="Add selected devices to composition"
        )
        self.toolbar.components.add_safe("add_selected", self.tb_add_selected)
        io_bundle.add_action("add_selected")

        self.tb_del_selected = MaterialIconAction(
            icon_name="chips", parent=self, tooltip="Remove selected devices from composition"
        )
        self.toolbar.components.add_safe("del_selected", self.tb_del_selected)
        io_bundle.add_action("del_selected")

        self.verticalLayout.addWidget(self.toolbar)
        self.toolbar.add_bundle(io_bundle)
        self.toolbar.show_bundles(["IO"])
