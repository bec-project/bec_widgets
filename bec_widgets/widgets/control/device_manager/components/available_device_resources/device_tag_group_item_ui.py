import math
from functools import partial

from bec_qthemes import material_icon
from qtpy.QtCore import QMetaObject, QSize, Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QSizePolicy,
    QSpacerItem,
    QToolButton,
    QVBoxLayout,
)


class AutoHeightListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setWrapping(True)
        self.setUniformItemSizes(True)
        self.setMovement(QListView.Movement.Static)
        self.setAcceptDrops(False)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSpacing(5)

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setMinimumHeight(self._calcSize().height())
        self.setMaximumHeight(self._calcSize().height())

    def sizeHint(self):
        return self._calcSize()

    def minimumSizeHint(self):
        return self._calcSize()

    def _calcSize(self):
        if self.count() == 0:
            return super().sizeHint()

        grid = self.gridSize()
        if not grid.isValid():
            grid = QSize(100, 100)  # fallback

        items_per_row = max(1, self.viewport().width() // grid.width())
        rows = math.ceil(self.count() / items_per_row)

        height = rows * grid.height() + 2 * self.frameWidth()
        return QSize(self.viewport().width(), height)


class Ui_DeviceTagGroup(object):
    def setupUi(self, DeviceTagGroup):
        if not DeviceTagGroup.objectName():
            DeviceTagGroup.setObjectName("DeviceTagGroup")
        DeviceTagGroup.setMinimumWidth(150)
        self.verticalLayout = QVBoxLayout(DeviceTagGroup)
        self.verticalLayout.setObjectName("verticalLayout")
        self.frame = QFrame(DeviceTagGroup)
        self.frame.setObjectName("frame")
        self.frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.frame)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")

        self.title = QLabel(self.frame)
        self.title.setObjectName("title")
        self.horizontalLayout.addWidget(self.title)

        self.n_included = QLabel(self.frame, text="...")
        self.n_included.setObjectName("n_included")
        self.horizontalLayout.addWidget(self.n_included)

        self.horizontalSpacer = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.delete_tag_button = QToolButton(self.frame)
        self.delete_tag_button.setObjectName("delete_tag_button")
        self.horizontalLayout.addWidget(self.delete_tag_button)

        self.remove_from_composition_button = QToolButton(self.frame)
        self.remove_from_composition_button.setObjectName("remove_from_composition_button")
        self.horizontalLayout.addWidget(self.remove_from_composition_button)

        self.add_to_composition_button = QToolButton(self.frame)
        self.add_to_composition_button.setObjectName("add_to_composition_button")
        self.horizontalLayout.addWidget(self.add_to_composition_button)

        self.remove_all_button = QToolButton(self.frame)
        self.remove_all_button.setObjectName("remove_all_from_composition_button")
        self.horizontalLayout.addWidget(self.remove_all_button)

        self.add_all_button = QToolButton(self.frame)
        self.add_all_button.setObjectName("add_all_to_composition_button")
        self.horizontalLayout.addWidget(self.add_all_button)

        self.verticalLayout_2.addLayout(self.horizontalLayout)

        self.device_list = AutoHeightListWidget(self.frame)
        self.device_list.setObjectName("device_list")

        self.verticalLayout_2.addWidget(self.device_list)

        self.verticalLayout.addWidget(self.frame)

        self.set_icons()

        QMetaObject.connectSlotsByName(DeviceTagGroup)

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
