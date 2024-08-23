# pylint: disable=no-name-in-module
import os
from abc import ABC, abstractmethod
from collections import defaultdict

from bec_qthemes._icon.material_icons import material_icon
from qtpy.QtCore import QSize
from qtpy.QtGui import QAction, QIcon
from qtpy.QtWidgets import QHBoxLayout, QLabel, QMenu, QToolBar, QToolButton, QWidget

import bec_widgets

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class ToolBarAction(ABC):
    """
    Abstract base class for toolbar actions.

    Args:
        icon_path (str, optional): The name of the icon file from `assets/toolbar_icons`. Defaults to None.
        tooltip (bool, optional): The tooltip for the action. Defaults to None.
        checkable (bool, optional): Whether the action is checkable. Defaults to False.
    """

    def __init__(self, icon_path: str = None, tooltip: str = None, checkable: bool = False):
        self.icon_path = (
            os.path.join(MODULE_PATH, "assets", "toolbar_icons", icon_path) if icon_path else None
        )
        self.tooltip = tooltip
        self.checkable = checkable
        self.action = None

    @abstractmethod
    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        """Adds an action or widget to a toolbar.

        Args:
            toolbar (QToolBar): The toolbar to add the action or widget to.
            target (QWidget): The target widget for the action.
        """


class SeparatorAction(ToolBarAction):
    """Separator action for the toolbar."""

    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        self.separator = QToolButton()
        self.separator.setFixedSize(2, 22)
        toolbar.addWidget(self.separator)


class IconAction(ToolBarAction):
    """
    Action with an icon for the toolbar.

    Args:
        icon_path (str): The path to the icon file.
        tooltip (str): The tooltip for the action.
        checkable (bool, optional): Whether the action is checkable. Defaults to False.
    """

    def __init__(self, icon_path: str = None, tooltip: str = None, checkable: bool = False):
        super().__init__(icon_path, tooltip, checkable)

    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        icon = QIcon()
        icon.addFile(self.icon_path, size=QSize(20, 20))
        self.action = QAction(icon, self.tooltip, target)
        self.action.setCheckable(self.checkable)
        toolbar.addAction(self.action)


class MaterialIconAction:
    """
    Action with a Material icon for the toolbar.

    Args:
        icon_path (str, optional): The name of the icon file from `assets/toolbar_icons`. Defaults to None.
        tooltip (bool, optional): The tooltip for the action. Defaults to None.
        checkable (bool, optional): Whether the action is checkable. Defaults to False.
    """

    def __init__(self, icon_name: str = None, tooltip: str = None, checkable: bool = False):
        self.icon_name = icon_name
        self.tooltip = tooltip
        self.checkable = checkable
        self.action = None

    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        color = {
            "dark": "#FFFFFF",
            "light": "#000000",
        }  # FIXME: This should be a theme color but the toolbar doesn't respect the theme atm
        # once fixed, change it to
        # palette = QGuiApplication.palette()
        # palette.toolTipBase().color()

        icon = material_icon(self.icon_name, size=(20, 20), color=color, convert_to_pixmap=False)
        self.action = QAction(icon, self.tooltip, target)
        self.action.setCheckable(self.checkable)
        toolbar.addAction(self.action)


class DeviceSelectionAction(ToolBarAction):
    """
    Action for selecting a device in a combobox.

    Args:
        label (str): The label for the combobox.
        device_combobox (DeviceComboBox): The combobox for selecting the device.

    """

    def __init__(self, label: str, device_combobox):
        super().__init__()
        self.label = label
        self.device_combobox = device_combobox
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


class ExpandableMenuAction(ToolBarAction):
    """
    Action for an expandable menu in the toolbar.

    Args:
        label (str): The label for the menu.
        actions (dict): A dictionary of actions to populate the menu.
        icon_path (str, optional): The path to the icon file. Defaults to None.

    """

    def __init__(self, label: str, actions: dict, icon_path: str = None):
        super().__init__(icon_path, label)
        self.actions = actions
        self.widgets = defaultdict(dict)

    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        button = QToolButton(toolbar)
        if self.icon_path:
            button.setIcon(QIcon(self.icon_path))
        button.setText(self.tooltip)
        button.setPopupMode(QToolButton.InstantPopup)
        button.setStyleSheet(
            """
                   QToolButton {
                       font-size: 14px;
                   }
                   QMenu {
                       font-size: 14px;
                   }
               """
        )
        menu = QMenu(button)
        for action_id, action in self.actions.items():
            sub_action = QAction(action.tooltip, target)
            if action.icon_path:
                icon = QIcon()
                icon.addFile(action.icon_path, size=QSize(20, 20))
                sub_action.setIcon(icon)
            sub_action.setCheckable(action.checkable)
            menu.addAction(sub_action)
            self.widgets[action_id] = sub_action
        button.setMenu(menu)
        toolbar.addWidget(button)


class ModularToolBar(QToolBar):
    """Modular toolbar with optional automatic initialization.
    Args:
        parent (QWidget, optional): The parent widget of the toolbar. Defaults to None.
        actions (list[ToolBarAction], optional): A list of action creators to populate the toolbar. Defaults to None.
        target_widget (QWidget, optional): The widget that the actions will target. Defaults to None.
        color (str, optional): The background color of the toolbar. Defaults to "black".
    """

    def __init__(
        self,
        parent=None,
        actions: dict | None = None,
        target_widget=None,
        color: str = "rgba(255, 255, 255, 0)",
    ):
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
