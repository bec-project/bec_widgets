import os

from qtpy.QtCore import QSize
from qtpy.QtGui import QAction, QIcon
from qtpy.QtWidgets import QHBoxLayout, QLabel, QWidget

from bec_widgets.widgets.device_inputs import DeviceComboBox
from bec_widgets.widgets.toolbar.toolbar import ToolBarAction


class DeviceSelectionAction(ToolBarAction):
    def __init__(self, label: str):
        self.label = label
        self.device_combobox = DeviceComboBox(device_filter="Positioner")

        self.device_combobox.currentIndexChanged.connect(lambda: self.set_combobox_style("#ffa700"))

    def add_to_toolbar(self, toolbar, target):
        widget = QWidget()
        layout = QHBoxLayout(widget)

        label = QLabel(f"{self.label}")

        layout.addWidget(label)
        layout.addWidget(self.device_combobox)
        toolbar.addWidget(widget)

    def set_combobox_style(self, color: str):
        self.device_combobox.setStyleSheet(f"QComboBox {{ background-color: {color}; }}")


class ConnectAction(ToolBarAction):
    def add_to_toolbar(self, toolbar, target):
        current_path = os.path.dirname(__file__)
        icon = QIcon()
        icon.addFile(os.path.join(current_path, "assets", "connection.svg"), size=QSize(20, 20))
        self.action = QAction(icon, "Connect Motors", target)
        toolbar.addAction(self.action)


class ResetHistoryAction(ToolBarAction):
    def add_to_toolbar(self, toolbar, target):
        current_path = os.path.dirname(__file__)
        icon = QIcon()
        icon.addFile(os.path.join(current_path, "assets", "history.svg"), size=QSize(20, 20))
        self.action = QAction(icon, "Reset History", target)
        toolbar.addAction(self.action)


class SettingsAction(ToolBarAction):
    def add_to_toolbar(self, toolbar, target):
        current_path = os.path.dirname(__file__)
        icon = QIcon()
        icon.addFile(os.path.join(current_path, "assets", "settings.svg"), size=QSize(20, 20))
        self.action = QAction(icon, "Config", target)
        toolbar.addAction(self.action)
