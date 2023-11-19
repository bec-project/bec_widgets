from abc import ABC, abstractmethod

from qtpy.QtWidgets import QToolBar
from qtpy.QtCore import QTimer
from qtpy.QtGui import QAction
from qtpy.QtWidgets import QWidget


class ToolBarAction(ABC):
    @abstractmethod
    def create(self, target: QWidget):
        pass


class OpenFileAction:  # (ToolBarAction):
    def create(self, target: QWidget):
        action = QAction("Open File", target)
        action.triggered.connect(target.openFile)
        return action


class SaveFileAction:
    def create(self, target):
        action = QAction("Save File", target)
        action.triggered.connect(target.saveFile)
        return action


class RunScriptAction:
    def create(self, target):
        action = QAction("Run Script", target)
        action.triggered.connect(target.runScript)
        return action


class ModularToolBar(QToolBar):
    def __init__(self, parent=None, auto_init=True):
        super().__init__(parent)
        self.auto_init = auto_init
        self.handler = {
            "BECEditor": [OpenFileAction(), SaveFileAction(), RunScriptAction()],
            # BECMonitor: [SomeOtherAction(), AnotherAction()],  # Example for another widget
        }
        self.setStyleSheet("QToolBar { background: transparent; }")
        if self.auto_init:
            QTimer.singleShot(0, self.auto_detect_and_populate)

    def auto_detect_and_populate(self):
        if not self.auto_init:
            return

        parent_widget = self.parent()
        if parent_widget is None:
            return

        parent_widget_class_name = type(parent_widget).__name__
        for widget_type_name, actions in self.handler.items():
            if parent_widget_class_name == widget_type_name:
                self.populate_toolbar(actions, parent_widget)
                return

    def populate_toolbar(self, actions, target_widget):
        self.clear()
        for action_creator in actions:
            action = action_creator.create(target_widget)
            self.addAction(action)

    def set_manual_actions(self, actions, target_widget):
        self.clear()
        for action in actions:
            if isinstance(action, QAction):
                self.addAction(action)
            elif isinstance(action, ToolBarAction):
                self.addAction(action.create(target_widget))
