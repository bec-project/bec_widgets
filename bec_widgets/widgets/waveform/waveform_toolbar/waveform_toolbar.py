import os

from qtpy.QtCore import QSize
from qtpy.QtGui import QAction, QIcon

from bec_widgets.qt_utils.toolbar import ToolBarAction


class CurveAction(ToolBarAction):
    def add_to_toolbar(self, toolbar, target):
        current_path = os.path.dirname(__file__)
        parent_path = os.path.dirname(current_path)
        icon = QIcon()
        icon.addFile(os.path.join(parent_path, "assets", "line_axis.svg"), size=QSize(20, 20))
        self.action = QAction(icon, "Open Curves Configuration", target)
        toolbar.addAction(self.action)


class SettingsAction(ToolBarAction):
    def add_to_toolbar(self, toolbar, target):
        current_path = os.path.dirname(__file__)
        parent_path = os.path.dirname(current_path)
        icon = QIcon()
        icon.addFile(os.path.join(parent_path, "assets", "settings.svg"), size=QSize(20, 20))
        self.action = QAction(icon, "Open Configuration Dialog", target)
        toolbar.addAction(self.action)


class ImportAction(ToolBarAction):
    def add_to_toolbar(self, toolbar, target):
        current_path = os.path.dirname(__file__)
        parent_path = os.path.dirname(current_path)
        icon = QIcon()
        icon.addFile(os.path.join(parent_path, "assets", "import.svg"), size=QSize(20, 20))
        self.action = QAction(icon, "Import Configuration from YAML", target)
        toolbar.addAction(self.action)


class ExportAction(ToolBarAction):
    def add_to_toolbar(self, toolbar, target):
        current_path = os.path.dirname(__file__)
        parent_path = os.path.dirname(current_path)
        icon = QIcon()
        icon.addFile(os.path.join(parent_path, "assets", "export.svg"), size=QSize(20, 20))
        self.action = QAction(icon, "Export Current Configuration to YAML", target)
        toolbar.addAction(self.action)
