from functools import partial

from bec_qthemes import material_icon
from PySide6.QtWidgets import QFrame
from qtpy.QtCore import QMetaObject
from qtpy.QtWidgets import QLabel, QListWidget, QToolButton, QVBoxLayout


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

        self.delete_tag_button = QToolButton(AvailableDeviceGroup)
        self.delete_tag_button.setObjectName("delete_tag_button")
        title_layout.addWidget(self.delete_tag_button)

        self.remove_from_composition_button = QToolButton(AvailableDeviceGroup)
        self.remove_from_composition_button.setObjectName("remove_from_composition_button")
        title_layout.addWidget(self.remove_from_composition_button)

        self.add_to_composition_button = QToolButton(AvailableDeviceGroup)
        self.add_to_composition_button.setObjectName("add_to_composition_button")
        title_layout.addWidget(self.add_to_composition_button)

        self.remove_all_button = QToolButton(AvailableDeviceGroup)
        self.remove_all_button.setObjectName("remove_all_from_composition_button")
        title_layout.addWidget(self.remove_all_button)

        self.add_all_button = QToolButton(AvailableDeviceGroup)
        self.add_all_button.setObjectName("add_all_to_composition_button")
        title_layout.addWidget(self.add_all_button)

        self.device_list = QListWidget(AvailableDeviceGroup)
        self.device_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.device_list.setObjectName("device_list")
        self.device_list.setFrameStyle(0)

        self.verticalLayout.addWidget(self.device_list)

        self.set_icons()

        QMetaObject.connectSlotsByName(AvailableDeviceGroup)

    def set_icons(self):
        icon = partial(material_icon, size=(15, 15), convert_to_pixmap=False)
        self.delete_tag_button.setIcon(icon("delete"))
        self.delete_tag_button.setToolTip("Delete tag group")
        self.remove_from_composition_button.setIcon(icon("remove"))
        self.remove_from_composition_button.setToolTip("Remove selected from composition")
        self.add_to_composition_button.setIcon(icon("add"))
        self.add_to_composition_button.setToolTip("Add selected to composition")
        self.remove_all_button.setIcon(icon("chips"))
        self.remove_all_button.setToolTip("Remove all with this tag from composition")
        self.add_all_button.setIcon(icon("add_box"))
        self.add_all_button.setToolTip("Add all with this tag to composition")
