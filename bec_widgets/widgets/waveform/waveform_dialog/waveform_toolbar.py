import os

from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon, QAction

from bec_widgets.widgets.toolbar.toolbar import ToolBarAction


class SettingsAction(ToolBarAction):
    def add_to_toolbar(self, toolbar, target):
        current_path = os.path.dirname(__file__)
        parent_path = os.path.dirname(current_path)
        icon = QIcon()
        icon.addFile(os.path.join(parent_path, "assets", "settings.svg"), size=QSize(20, 20))
        self.action = QAction(icon, "Open Configuration Dialog", target)
        toolbar.addAction(self.action)
