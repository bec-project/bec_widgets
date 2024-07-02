from abc import ABC, abstractmethod
from collections import defaultdict

# pylint: disable=no-name-in-module
from qtpy.QtCore import QSize
from qtpy.QtGui import QAction
from qtpy.QtWidgets import QHBoxLayout, QLabel, QSpinBox, QToolBar, QWidget


class ToolBarAction(ABC):
    @abstractmethod
    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        """Adds an action or widget to a toolbar.

        Args:
            toolbar (QToolBar): The toolbar to add the action or widget to.
            target (QWidget): The target widget for the action.
        """


class ColumnAdjustAction(ToolBarAction):
    """Toolbar spinbox to adjust number of columns in the plot layout"""

    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        """Creates a access history button for the toolbar.

        Args:
            toolbar (QToolBar): The toolbar to add the action to.
            target (QWidget): The widget that the 'Access Scan History' action will be targeted.

        Returns:
            QAction: The 'Access Scan History' action created for the toolbar.
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)

        label = QLabel("Columns:")
        spin_box = QSpinBox()
        spin_box.setMinimum(1)  # Set minimum value
        spin_box.setMaximum(10)  # Set maximum value
        spin_box.setValue(target.get_column_count())  # Initial value
        spin_box.valueChanged.connect(lambda value: target.set_column_count(value))

        layout.addWidget(label)
        layout.addWidget(spin_box)
        toolbar.addWidget(widget)


class ModularToolBar(QToolBar):
    """Modular toolbar with optional automatic initialization.
    Args:
        parent (QWidget, optional): The parent widget of the toolbar. Defaults to None.
        actions (list[ToolBarAction], optional): A list of action creators to populate the toolbar. Defaults to None.
        target_widget (QWidget, optional): The widget that the actions will target. Defaults to None.
        color (str, optional): The background color of the toolbar. Defaults to "black".
    """

    def __init__(self, parent=None, actions=None, target_widget=None, color: str = "black"):
        super().__init__(parent)

        self.widgets = defaultdict(dict)
        self.set_background_color(color)

        if actions is not None and target_widget is not None:
            self.populate_toolbar(actions, target_widget)

    def populate_toolbar(self, actions: dict, target_widget):
        """Populates the toolbar with a set of actions.

        Args:
            actions (list[ToolBarAction]): A list of action creators to populate the toolbar.
            target_widget (QWidget): The widget that the actions will target.
        """
        self.clear()
        for action_id, action in actions.items():
            action.add_to_toolbar(self, target_widget)
            self.widgets[action_id] = action

    def set_background_color(self, color: str):
        self.setStyleSheet(f"QToolBar {{ background: {color}; }}")
        self.setIconSize(QSize(20, 20))
        self.setMovable(False)
        self.setFloatable(False)
        self.setContentsMargins(0, 0, 0, 0)
