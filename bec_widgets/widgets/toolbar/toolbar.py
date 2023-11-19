from PyQt6.QtWidgets import QToolBar
from qtpy.QtCore import QTimer
from qtpy.QtGui import QAction
from qtpy.QtWidgets import QPushButton
from abc import ABC, abstractmethod

from qtpy.QtWidgets import QHBoxLayout, QWidget

from bec_widgets.widgets.editor.editor import BECEditor


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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.handler = {
            BECEditor: [OpenFileAction(), SaveFileAction(), RunScriptAction()],
            # BECMonitor: [SomeOtherAction(), AnotherAction()],  # Example for another widget
        }  # TODO also buggy fox later
        QTimer.singleShot(0, self.detect_context_and_update_actions)  # TODO buggy disabled for now
        self.setStyleSheet("QToolBar { background: transparent; }")

    def detect_context_and_update_actions(self):  # TODO buggy disabled for now
        parent_widget = self.parent()
        if parent_widget is None:
            return

        for child in parent_widget.children():
            for widget_type, actions in self.handler.items():
                if isinstance(child, widget_type):
                    self.populate_toolbar(child, actions)
                    return

    def set_target_widget(self, widget):
        self.populate_toolbar(
            widget, actions=[OpenFileAction(), SaveFileAction(), RunScriptAction()]
        )
        # for widget_type, actions in self.handler.items(): #TODO for automatic population
        #     if isinstance(widget, widget_type):
        #         self.populate_toolbar(widget, actions)
        #         break

    def populate_toolbar(self, target_widget, actions):
        self.clear()
        for action_creator in actions:
            action = action_creator.create(target_widget)
            self.addAction(action)
