from abc import ABC, abstractmethod

# pylint: disable=no-name-in-module
from qtpy.QtCore import QSize
from qtpy.QtWidgets import QToolBar, QStyle, QApplication
from qtpy.QtCore import QTimer
from qtpy.QtGui import QAction
from qtpy.QtWidgets import QWidget


class ToolBarAction(ABC):
    @abstractmethod
    def create(self, target: QWidget):
        """Creates and returns an action to be added to a toolbar.

        This method must be implemented by subclasses.

        Args:
            target (QWidget): The widget that the action will target.

        Returns:
            QAction: The action created for the toolbar.
        """
        pass


class OpenFileAction:  # (ToolBarAction):
    def create(self, target: QWidget):
        """Creates an 'Open File' action for the toolbar.

        Args:
            target (QWidget): The widget that the 'Open File' action will be targeted.

        Returns:
            QAction: The 'Open File' action created for the toolbar.
        """
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        action = QAction(icon, "Open File", target)
        # action = QAction("Open File", target)
        action.triggered.connect(target.open_file)
        return action


class SaveFileAction:
    def create(self, target):
        """Creates a 'Save File' action for the toolbar.

        Args:
            target (QWidget): The widget that the 'Save File' action will be targeted.

        Returns:
            QAction: The 'Save File' action created for the toolbar.
        """
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        action = QAction(icon, "Save File", target)
        # action = QAction("Save File", target)
        action.triggered.connect(target.save_file)
        return action


class RunScriptAction:
    def create(self, target):
        """Creates a 'Run Script' action for the toolbar.

        Args:
            target (QWidget): The widget that the 'Run Script' action will be targeted.

        Returns:
            QAction: The 'Run Script' action created for the toolbar.
        """
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        action = QAction(icon, "Run Script", target)
        # action = QAction("Run Script", target)
        action.triggered.connect(target.run_script)
        return action


class ModularToolBar(QToolBar):
    """Modular toolbar with optional automatic initialization.
    Args:
        parent (QWidget, optional): The parent widget of the toolbar. Defaults to None.
        auto_init (bool, optional): If True, automatically populates the toolbar based on the parent widget.
    """

    def __init__(self, parent=None, auto_init=True):
        super().__init__(parent)
        self.auto_init = auto_init
        self.handler = {
            "BECEditor": [OpenFileAction(), SaveFileAction(), RunScriptAction()],
            # BECMonitor: [SomeOtherAction(), AnotherAction()],  # Example for another widget
        }
        self.setStyleSheet("QToolBar { background: transparent; }")
        # Set the icon size for the toolbar
        self.setIconSize(QSize(20, 20))

        if self.auto_init:
            QTimer.singleShot(0, self.auto_detect_and_populate)

    def auto_detect_and_populate(self):
        """Automatically detects the parent widget and populates the toolbar with relevant actions."""
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
        """Populates the toolbar with a set of actions.

        Args:
            actions (list[ToolBarAction]): A list of action creators to populate the toolbar.
            target_widget (QWidget): The widget that the actions will target.
        """
        self.clear()
        for action_creator in actions:
            action = action_creator.create(target_widget)
            self.addAction(action)

    def set_manual_actions(self, actions, target_widget):
        """Manually sets the actions for the toolbar.

        Args:
            actions (list[QAction or ToolBarAction]): A list of actions or action creators to populate the toolbar.
            target_widget (QWidget): The widget that the actions will target.
        """
        self.clear()
        for action in actions:
            if isinstance(action, QAction):
                self.addAction(action)
            elif isinstance(action, ToolBarAction):
                self.addAction(action.create(target_widget))
