# pylint: disable=no-name-in-module
from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Dict, List, Literal, Tuple

from bec_qthemes._icon.material_icons import material_icon
from qtpy.QtCore import QSize, Qt, QTimer
from qtpy.QtGui import QAction, QColor, QIcon
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QSizePolicy,
    QStyle,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import bec_widgets
from bec_widgets.utils.colors import set_theme
from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

MODULE_PATH = os.path.dirname(bec_widgets.__file__)

# Ensure that icons are shown in menus (especially on macOS)
QApplication.setAttribute(Qt.AA_DontShowIconsInMenus, False)


class LongPressToolButton(QToolButton):
    def __init__(self, *args, long_press_threshold=500, **kwargs):
        super().__init__(*args, **kwargs)
        self.long_press_threshold = long_press_threshold
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.timeout.connect(self.handleLongPress)
        self._pressed = False
        self._longPressed = False

    def mousePressEvent(self, event):
        self._pressed = True
        self._longPressed = False
        self._long_press_timer.start(self.long_press_threshold)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        if self._longPressed:
            self._longPressed = False
            self._long_press_timer.stop()
            event.accept()  # Prevent normal click action after a long press
            return
        self._long_press_timer.stop()
        super().mouseReleaseEvent(event)

    def handleLongPress(self):
        if self._pressed:
            self._longPressed = True
            self.showMenu()


class ToolBarAction(ABC):
    """
    Abstract base class for toolbar actions.

    Args:
        icon_path (str, optional): The name of the icon file from `assets/toolbar_icons`. Defaults to None.
        tooltip (str, optional): The tooltip for the action. Defaults to None.
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
        toolbar.addSeparator()


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


class QtIconAction(ToolBarAction):
    def __init__(self, standard_icon, tooltip=None, checkable=False, parent=None):
        super().__init__(icon_path=None, tooltip=tooltip, checkable=checkable)
        self.standard_icon = standard_icon
        self.icon = QApplication.style().standardIcon(standard_icon)
        self.action = QAction(self.icon, self.tooltip, parent)
        self.action.setCheckable(self.checkable)

    def add_to_toolbar(self, toolbar, target):
        toolbar.addAction(self.action)

    def get_icon(self):
        return self.icon


class MaterialIconAction(ToolBarAction):
    """
    Action with a Material icon for the toolbar.

    Args:
        icon_name (str, optional): The name of the Material icon. Defaults to None.
        tooltip (str, optional): The tooltip for the action. Defaults to None.
        checkable (bool, optional): Whether the action is checkable. Defaults to False.
        filled (bool, optional): Whether the icon is filled. Defaults to False.
        color (str | tuple | QColor | dict[Literal["dark", "light"], str] | None, optional): The color of the icon.
            Defaults to None.
        parent (QWidget or None, optional): Parent widget for the underlying QAction.
    """

    def __init__(
        self,
        icon_name: str = None,
        tooltip: str = None,
        checkable: bool = False,
        filled: bool = False,
        color: str | tuple | QColor | dict[Literal["dark", "light"], str] | None = None,
        parent=None,
    ):
        super().__init__(icon_path=None, tooltip=tooltip, checkable=checkable)
        self.icon_name = icon_name
        self.filled = filled
        self.color = color
        # Generate the icon using the material_icon helper
        self.icon = material_icon(
            self.icon_name,
            size=(20, 20),
            convert_to_pixmap=False,
            filled=self.filled,
            color=self.color,
        )
        self.action = QAction(self.icon, self.tooltip, parent=parent)
        self.action.setCheckable(self.checkable)

    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        """
        Adds the action to the toolbar.

        Args:
            toolbar(QToolBar): The toolbar to add the action to.
            target(QWidget): The target widget for the action.
        """
        toolbar.addAction(self.action)

    def get_icon(self):
        """
        Returns the icon for the action.

        Returns:
            QIcon: The icon for the action.
        """
        return self.icon


class DeviceSelectionAction(ToolBarAction):
    """
    Action for selecting a device in a combobox.

    Args:
        label (str): The label for the combobox.
        device_combobox (DeviceComboBox): The combobox for selecting the device.
    """

    def __init__(self, label: str | None = None, device_combobox=None):
        super().__init__()
        self.label = label
        self.device_combobox = device_combobox
        self.device_combobox.currentIndexChanged.connect(lambda: self.set_combobox_style("#ffa700"))

    def add_to_toolbar(self, toolbar, target):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if self.label is not None:
            label = QLabel(f"{self.label}")
            layout.addWidget(label)
        if self.device_combobox is not None:
            layout.addWidget(self.device_combobox)
            toolbar.addWidget(widget)

    def set_combobox_style(self, color: str):
        self.device_combobox.setStyleSheet(f"QComboBox {{ background-color: {color}; }}")


class SwitchableToolBarAction(ToolBarAction):
    """
    A split toolbar action that combines a main action and a drop-down menu for additional actions.

    The main button displays the currently selected action's icon and tooltip. Clicking on the main button
    triggers that action. Clicking on the drop-down arrow displays a menu with alternative actions. When an
    alternative action is selected, it becomes the new default and its callback is immediately executed.

    This design mimics the behavior seen in Adobe Photoshop or Affinity Designer toolbars.

    Args:
        actions (dict): A dictionary mapping a unique key to a ToolBarAction instance.
        initial_action (str, optional): The key of the initial default action. If not provided, the first action is used.
        tooltip (str, optional): An optional tooltip for the split action; if provided, it overrides the default action's tooltip.
        checkable (bool, optional): Whether the action is checkable. Defaults to True.
        parent (QWidget, optional): Parent widget for the underlying QAction.
    """

    def __init__(
        self,
        actions: Dict[str, ToolBarAction],
        initial_action: str = None,
        tooltip: str = None,
        checkable: bool = True,
        default_state_checked: bool = False,
        parent=None,
    ):
        super().__init__(icon_path=None, tooltip=tooltip, checkable=checkable)
        self.actions = actions
        self.current_key = initial_action if initial_action is not None else next(iter(actions))
        self.parent = parent
        self.checkable = checkable
        self.default_state_checked = default_state_checked
        self.main_button = None
        self.menu_actions: Dict[str, QAction] = {}

    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        """
        Adds the split action to the toolbar.

        Args:
            toolbar (QToolBar): The toolbar to add the action to.
            target (QWidget): The target widget for the action.
        """
        self.main_button = LongPressToolButton(toolbar)
        self.main_button.setPopupMode(QToolButton.MenuButtonPopup)
        self.main_button.setCheckable(self.checkable)
        default_action = self.actions[self.current_key]
        self.main_button.setIcon(default_action.get_icon())
        self.main_button.setToolTip(default_action.tooltip)
        self.main_button.clicked.connect(self._trigger_current_action)
        menu = QMenu(self.main_button)
        for key, action_obj in self.actions.items():
            menu_action = QAction(action_obj.get_icon(), action_obj.tooltip, self.main_button)
            menu_action.setIconVisibleInMenu(True)
            menu_action.setCheckable(self.checkable)
            menu_action.setChecked(key == self.current_key)
            menu_action.triggered.connect(lambda checked, k=key: self.set_default_action(k))
            menu.addAction(menu_action)
        self.main_button.setMenu(menu)
        toolbar.addWidget(self.main_button)

    def _trigger_current_action(self):
        """
        Triggers the current action associated with the main button.
        """
        action_obj = self.actions[self.current_key]
        action_obj.action.trigger()

    def set_default_action(self, key: str):
        """
        Sets the default action for the split action.

        Args:
            key(str): The key of the action to set as default.
        """
        self.current_key = key
        new_action = self.actions[self.current_key]
        self.main_button.setIcon(new_action.get_icon())
        self.main_button.setToolTip(new_action.tooltip)
        # Update check state of menu items
        for k, menu_act in self.actions.items():
            menu_act.action.setChecked(False)
        new_action.action.trigger()
        # Active action chosen from menu is always checked, uncheck through main button
        if self.checkable:
            new_action.action.setChecked(True)
            self.main_button.setChecked(True)

    def uncheck_all(self):
        """
        Uncheck all actions in the toolbar.
        """
        for action in self.actions.values():
            action.action.setChecked(False)
        self.main_button.setChecked(False)

    def get_icon(self) -> QIcon:
        return self.actions[self.current_key].get_icon()


class WidgetAction(ToolBarAction):
    """
    Action for adding any widget to the toolbar.

    Args:
        label (str|None): The label for the widget.
        widget (QWidget): The widget to be added to the toolbar.
    """

    def __init__(self, label: str | None = None, widget: QWidget = None, parent=None):
        super().__init__(icon_path=None, tooltip=label, checkable=False)
        self.label = label
        self.widget = widget
        self.container = None

    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        """
        Adds the widget to the toolbar.

        Args:
            toolbar (QToolBar): The toolbar to add the widget to.
            target (QWidget): The target widget for the action.
        """
        self.container = QWidget()
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self.label is not None:
            label_widget = QLabel(f"{self.label}")
            label_widget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            label_widget.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            layout.addWidget(label_widget)

        if isinstance(self.widget, QComboBox):
            self.widget.setSizeAdjustPolicy(QComboBox.AdjustToContents)

            size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.widget.setSizePolicy(size_policy)

            self.widget.setMinimumWidth(self.calculate_minimum_width(self.widget))

        else:
            self.widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        layout.addWidget(self.widget)

        toolbar.addWidget(self.container)
        # Store the container as the action to allow toggling visibility.
        self.action = self.container

    @staticmethod
    def calculate_minimum_width(combo_box: QComboBox) -> int:
        font_metrics = combo_box.fontMetrics()
        max_width = max(font_metrics.width(combo_box.itemText(i)) for i in range(combo_box.count()))
        return max_width + 60


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
            sub_action.setIconVisibleInMenu(True)
            if action.icon_path:
                icon = QIcon()
                icon.addFile(action.icon_path, size=QSize(20, 20))
                sub_action.setIcon(icon)
            elif hasattr(action, "get_icon") and callable(action.get_icon):
                sub_icon = action.get_icon()
                if sub_icon and not sub_icon.isNull():
                    sub_action.setIcon(sub_icon)
            sub_action.setCheckable(action.checkable)
            menu.addAction(sub_action)
            self.widgets[action_id] = sub_action
        button.setMenu(menu)
        toolbar.addWidget(button)


class ToolbarBundle:
    """
    Represents a bundle of toolbar actions, keyed by action_id.
    Allows direct dictionary-like access: self.actions["some_id"] -> ToolBarAction object.
    """

    def __init__(self, bundle_id: str = None, actions=None):
        """
        Args:
            bundle_id (str): Unique identifier for the bundle.
            actions: Either None or a list of (action_id, ToolBarAction) tuples.
        """
        self.bundle_id = bundle_id
        self._actions: dict[str, ToolBarAction] = {}

        if actions is not None:
            for action_id, action in actions:
                self._actions[action_id] = action

    def add_action(self, action_id: str, action: ToolBarAction):
        """
        Adds or replaces an action in the bundle.

        Args:
            action_id (str): Unique identifier for the action.
            action (ToolBarAction): The action to add.
        """
        self._actions[action_id] = action

    def remove_action(self, action_id: str):
        """
        Removes an action from the bundle by ID.
        Ignores if not present.

        Args:
            action_id (str): Unique identifier for the action to remove.
        """
        self._actions.pop(action_id, None)

    @property
    def actions(self) -> dict[str, ToolBarAction]:
        """
        Return the internal dictionary of actions so that you can do
        bundle.actions["drag_mode"] -> ToolBarAction instance.
        """
        return self._actions


class ModularToolBar(QToolBar):
    """Modular toolbar with optional automatic initialization.

    Args:
        parent (QWidget, optional): The parent widget of the toolbar. Defaults to None.
        actions (dict, optional): A dictionary of action creators to populate the toolbar. Defaults to None.
        target_widget (QWidget, optional): The widget that the actions will target. Defaults to None.
        orientation (Literal["horizontal", "vertical"], optional): The initial orientation of the toolbar. Defaults to "horizontal".
        background_color (str, optional): The background color of the toolbar. Defaults to "rgba(0, 0, 0, 0)".
    """

    def __init__(
        self,
        parent=None,
        actions: dict | None = None,
        target_widget=None,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        background_color: str = "rgba(0, 0, 0, 0)",
    ):
        super().__init__(parent)

        self.widgets = defaultdict(dict)
        self.background_color = background_color
        self.set_background_color(self.background_color)

        # Set the initial orientation
        self.set_orientation(orientation)

        # Initialize bundles
        self.bundles = {}
        self.toolbar_items = []

        if actions is not None and target_widget is not None:
            self.populate_toolbar(actions, target_widget)

    def populate_toolbar(self, actions: dict, target_widget: QWidget):
        """Populates the toolbar with a set of actions.

        Args:
            actions (dict): A dictionary of action creators to populate the toolbar.
            target_widget (QWidget): The widget that the actions will target.
        """
        self.clear()
        self.toolbar_items.clear()  # Reset the order tracking
        for action_id, action in actions.items():
            action.add_to_toolbar(self, target_widget)
            self.widgets[action_id] = action
            self.toolbar_items.append(("action", action_id))
        self.update_separators()  # Ensure separators are updated after populating

    def set_background_color(self, color: str = "rgba(0, 0, 0, 0)"):
        """
        Sets the background color and other appearance settings.

        Args:
            color (str): The background color of the toolbar.
        """
        self.setIconSize(QSize(20, 20))
        self.setMovable(False)
        self.setFloatable(False)
        self.setContentsMargins(0, 0, 0, 0)
        self.background_color = color
        self.setStyleSheet(f"QToolBar {{ background-color: {color}; border: none; }}")

    def set_orientation(self, orientation: Literal["horizontal", "vertical"]):
        """Sets the orientation of the toolbar.

        Args:
            orientation (Literal["horizontal", "vertical"]): The desired orientation of the toolbar.
        """
        if orientation == "horizontal":
            self.setOrientation(Qt.Horizontal)
        elif orientation == "vertical":
            self.setOrientation(Qt.Vertical)
        else:
            raise ValueError("Orientation must be 'horizontal' or 'vertical'.")

    def update_material_icon_colors(self, new_color: str | tuple | QColor):
        """
        Updates the color of all MaterialIconAction icons.

        Args:
            new_color (str | tuple | QColor): The new color.
        """
        for action in self.widgets.values():
            if isinstance(action, MaterialIconAction):
                action.color = new_color
                updated_icon = action.get_icon()
                action.action.setIcon(updated_icon)

    def add_action(self, action_id: str, action: ToolBarAction, target_widget: QWidget):
        """
        Adds a new standalone action dynamically.

        Args:
            action_id (str): Unique identifier.
            action (ToolBarAction): The action to add.
            target_widget (QWidget): The target widget.
        """
        if action_id in self.widgets:
            raise ValueError(f"Action with ID '{action_id}' already exists.")
        action.add_to_toolbar(self, target_widget)
        self.widgets[action_id] = action
        self.toolbar_items.append(("action", action_id))
        self.update_separators()

    def hide_action(self, action_id: str):
        """
        Hides a specific action.

        Args:
            action_id (str): Unique identifier.
        """
        if action_id not in self.widgets:
            raise ValueError(f"Action with ID '{action_id}' does not exist.")
        action = self.widgets[action_id]
        if hasattr(action, "action") and action.action is not None:
            action.action.setVisible(False)
            self.update_separators()

    def show_action(self, action_id: str):
        """
        Shows a specific action.

        Args:
            action_id (str): Unique identifier.
        """
        if action_id not in self.widgets:
            raise ValueError(f"Action with ID '{action_id}' does not exist.")
        action = self.widgets[action_id]
        if hasattr(action, "action") and action.action is not None:
            action.action.setVisible(True)
            self.update_separators()

    def add_bundle(self, bundle: ToolbarBundle, target_widget: QWidget):
        """
        Adds a bundle of actions, separated by a separator.

        Args:
            bundle (ToolbarBundle): The bundle.
            target_widget (QWidget): The target widget.
        """
        if bundle.bundle_id in self.bundles:
            raise ValueError(f"ToolbarBundle with ID '{bundle.bundle_id}' already exists.")

        if self.toolbar_items:
            sep = SeparatorAction()
            sep.add_to_toolbar(self, target_widget)
            self.toolbar_items.append(("separator", None))

        for action_id, action_obj in bundle.actions.items():
            action_obj.add_to_toolbar(self, target_widget)
            self.widgets[action_id] = action_obj

        self.bundles[bundle.bundle_id] = list(bundle.actions.keys())
        self.toolbar_items.append(("bundle", bundle.bundle_id))
        self.update_separators()

    def add_action_to_bundle(self, bundle_id: str, action_id: str, action, target_widget: QWidget):
        """
        Dynamically adds an action to an existing bundle.

        Args:
            bundle_id (str): The bundle ID.
            action_id (str): Unique identifier.
            action (ToolBarAction): The action to add.
            target_widget (QWidget): The target widget.
        """
        if bundle_id not in self.bundles:
            raise ValueError(f"Bundle '{bundle_id}' does not exist.")
        if action_id in self.widgets:
            raise ValueError(f"Action with ID '{action_id}' already exists.")

        action.add_to_toolbar(self, target_widget)
        new_qaction = action.action
        self.removeAction(new_qaction)

        bundle_action_ids = self.bundles[bundle_id]
        if bundle_action_ids:
            last_bundle_action = self.widgets[bundle_action_ids[-1]].action
            actions_list = self.actions()
            try:
                index = actions_list.index(last_bundle_action)
            except ValueError:
                self.addAction(new_qaction)
            else:
                if index + 1 < len(actions_list):
                    before_action = actions_list[index + 1]
                    self.insertAction(before_action, new_qaction)
                else:
                    self.addAction(new_qaction)
        else:
            self.addAction(new_qaction)

        self.widgets[action_id] = action
        self.bundles[bundle_id].append(action_id)
        self.update_separators()

    def contextMenuEvent(self, event):
        """
        Overrides the context menu event to show toolbar actions with checkboxes and icons.

        Args:
            event (QContextMenuEvent): The context menu event.
        """
        menu = QMenu(self)
        for item_type, identifier in self.toolbar_items:
            if item_type == "separator":
                menu.addSeparator()
            elif item_type == "bundle":
                self.handle_bundle_context_menu(menu, identifier)
            elif item_type == "action":
                self.handle_action_context_menu(menu, identifier)
        menu.triggered.connect(self.handle_menu_triggered)
        menu.exec_(event.globalPos())

    def handle_bundle_context_menu(self, menu: QMenu, bundle_id: str):
        """
        Adds bundle actions to the context menu.

        Args:
            menu (QMenu): The context menu.
            bundle_id (str): The bundle identifier.
        """
        action_ids = self.bundles.get(bundle_id, [])
        for act_id in action_ids:
            toolbar_action = self.widgets.get(act_id)
            if not isinstance(toolbar_action, ToolBarAction) or not hasattr(
                toolbar_action, "action"
            ):
                continue
            qaction = toolbar_action.action
            if not isinstance(qaction, QAction):
                continue
            display_name = qaction.text() or toolbar_action.tooltip or act_id
            menu_action = QAction(display_name, self)
            menu_action.setCheckable(True)
            menu_action.setChecked(qaction.isVisible())
            menu_action.setData(act_id)  # Store the action_id

            # Set the icon if available
            if qaction.icon() and not qaction.icon().isNull():
                menu_action.setIcon(qaction.icon())
            menu.addAction(menu_action)

    def handle_action_context_menu(self, menu: QMenu, action_id: str):
        """
        Adds a single toolbar action to the context menu.

        Args:
            menu (QMenu): The context menu to which the action is added.
            action_id (str): Unique identifier for the action.
        """
        toolbar_action = self.widgets.get(action_id)
        if not isinstance(toolbar_action, ToolBarAction) or not hasattr(toolbar_action, "action"):
            return
        qaction = toolbar_action.action
        if not isinstance(qaction, QAction):
            return
        display_name = qaction.text() or toolbar_action.tooltip or action_id
        menu_action = QAction(display_name, self)
        menu_action.setCheckable(True)
        menu_action.setChecked(qaction.isVisible())
        menu_action.setData(action_id)  # Store the action_id

        # Set the icon if available
        if qaction.icon() and not qaction.icon().isNull():
            menu_action.setIcon(qaction.icon())

        menu.addAction(menu_action)

    def handle_menu_triggered(self, action):
        """
        Handles the triggered signal from the context menu.

        Args:
            action: Action triggered.
        """
        action_id = action.data()
        if action_id:
            self.toggle_action_visibility(action_id, action.isChecked())

    def toggle_action_visibility(self, action_id: str, visible: bool):
        """
        Toggles the visibility of a specific action.

        Args:
            action_id (str): Unique identifier.
            visible (bool): Whether the action should be visible.
        """
        if action_id not in self.widgets:
            return
        tool_action = self.widgets[action_id]
        if hasattr(tool_action, "action") and tool_action.action is not None:
            tool_action.action.setVisible(visible)
            self.update_separators()

    def update_separators(self):
        """
        Hide separators that are adjacent to another separator or have no non-separator actions between them.
        """
        toolbar_actions = self.actions()
        # First pass: set visibility based on surrounding non-separator actions.
        for i, action in enumerate(toolbar_actions):
            if not action.isSeparator():
                continue
            prev_visible = None
            for j in range(i - 1, -1, -1):
                if toolbar_actions[j].isVisible():
                    prev_visible = toolbar_actions[j]
                    break
            next_visible = None
            for j in range(i + 1, len(toolbar_actions)):
                if toolbar_actions[j].isVisible():
                    next_visible = toolbar_actions[j]
                    break
            if (prev_visible is None or prev_visible.isSeparator()) and (
                next_visible is None or next_visible.isSeparator()
            ):
                action.setVisible(False)
            else:
                action.setVisible(True)
        # Second pass: ensure no two visible separators are adjacent.
        prev = None
        for action in toolbar_actions:
            if action.isVisible() and action.isSeparator():
                if prev and prev.isSeparator():
                    action.setVisible(False)
                else:
                    prev = action
            else:
                if action.isVisible():
                    prev = action


class MainWindow(QMainWindow):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Toolbar / ToolbarBundle Demo")
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.test_label = QLabel(text="This is a test label.")
        self.central_widget.layout = QVBoxLayout(self.central_widget)
        self.central_widget.layout.addWidget(self.test_label)

        self.toolbar = ModularToolBar(parent=self, target_widget=self)
        self.addToolBar(self.toolbar)

        self.add_switchable_button_checkable()
        self.add_switchable_button_non_checkable()
        self.add_widget_actions()
        self.add_bundles()
        self.add_menus()

        # For theme testing

        self.dark_button = DarkModeButton(toolbar=True)
        dark_mode_action = WidgetAction(label=None, widget=self.dark_button)
        self.toolbar.add_action("dark_mode", dark_mode_action, self)

    def add_bundles(self):
        home_action = MaterialIconAction(
            icon_name="home", tooltip="Home", checkable=False, parent=self
        )
        settings_action = MaterialIconAction(
            icon_name="settings", tooltip="Settings", checkable=True, parent=self
        )
        profile_action = MaterialIconAction(
            icon_name="person", tooltip="Profile", checkable=True, parent=self
        )
        main_actions_bundle = ToolbarBundle(
            bundle_id="main_actions",
            actions=[
                ("home_action", home_action),
                ("settings_action", settings_action),
                ("profile_action", profile_action),
            ],
        )
        self.toolbar.add_bundle(main_actions_bundle, target_widget=self)
        home_action.action.triggered.connect(self.switchable_action.uncheck_all)

        search_action = MaterialIconAction(
            icon_name="search", tooltip="Search", checkable=False, parent=self
        )
        help_action = MaterialIconAction(
            icon_name="help", tooltip="Help", checkable=False, parent=self
        )
        second_bundle = ToolbarBundle(
            bundle_id="secondary_actions",
            actions=[("search_action", search_action), ("help_action", help_action)],
        )
        self.toolbar.add_bundle(second_bundle, target_widget=self)

        new_action = MaterialIconAction(
            icon_name="counter_1", tooltip="New Action", checkable=True, parent=self
        )
        self.toolbar.add_action_to_bundle(
            "main_actions", "new_action", new_action, target_widget=self
        )

    def add_menus(self):
        menu_material_actions = {
            "mat1": MaterialIconAction(
                icon_name="home", tooltip="Material Home", checkable=True, parent=self
            ),
            "mat2": MaterialIconAction(
                icon_name="settings", tooltip="Material Settings", checkable=True, parent=self
            ),
            "mat3": MaterialIconAction(
                icon_name="info", tooltip="Material Info", checkable=True, parent=self
            ),
        }
        menu_qt_actions = {
            "qt1": QtIconAction(
                standard_icon=QStyle.SP_FileIcon, tooltip="Qt File", checkable=True, parent=self
            ),
            "qt2": QtIconAction(
                standard_icon=QStyle.SP_DirIcon, tooltip="Qt Directory", checkable=True, parent=self
            ),
            "qt3": QtIconAction(
                standard_icon=QStyle.SP_TrashIcon, tooltip="Qt Trash", checkable=True, parent=self
            ),
        }
        expandable_menu_material = ExpandableMenuAction(
            label="Material Menu", actions=menu_material_actions
        )
        expandable_menu_qt = ExpandableMenuAction(label="Qt Menu", actions=menu_qt_actions)

        self.toolbar.add_action("material_menu", expandable_menu_material, self)
        self.toolbar.add_action("qt_menu", expandable_menu_qt, self)

    def add_switchable_button_checkable(self):
        action1 = MaterialIconAction(
            icon_name="hdr_auto", tooltip="Action 1", checkable=True, parent=self
        )
        action2 = MaterialIconAction(
            icon_name="hdr_auto", tooltip="Action 2", checkable=True, filled=True, parent=self
        )

        self.switchable_action = SwitchableToolBarAction(
            actions={"action1": action1, "action2": action2},
            initial_action="action1",
            tooltip="Switchable Action",
            checkable=True,
            parent=self,
        )
        self.toolbar.add_action("switchable_action", self.switchable_action, self)

        action1.action.toggled.connect(
            lambda checked: self.test_label.setText(f"Action 1 triggered, checked = {checked}")
        )
        action2.action.toggled.connect(
            lambda checked: self.test_label.setText(f"Action 2 triggered, checked = {checked}")
        )

    def add_switchable_button_non_checkable(self):
        action1 = MaterialIconAction(
            icon_name="counter_1", tooltip="Action 1", checkable=False, parent=self
        )
        action2 = MaterialIconAction(
            icon_name="counter_2", tooltip="Action 2", checkable=False, parent=self
        )

        switchable_action = SwitchableToolBarAction(
            actions={"action1": action1, "action2": action2},
            initial_action="action1",
            tooltip="Switchable Action",
            checkable=False,
            parent=self,
        )
        self.toolbar.add_action("switchable_action_no_toggle", switchable_action, self)

        action1.action.triggered.connect(
            lambda checked: self.test_label.setText(
                f"Action 1 (non-checkable) triggered, checked = {checked}"
            )
        )
        action2.action.triggered.connect(
            lambda checked: self.test_label.setText(
                f"Action 2 (non-checkable) triggered, checked = {checked}"
            )
        )
        switchable_action.actions["action1"].action.setChecked(True)

    def add_widget_actions(self):
        combo = QComboBox()
        combo.addItems(["Option 1", "Option 2", "Option 3"])
        self.toolbar.add_action("device_combo", WidgetAction(label="Device:", widget=combo), self)


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)
    set_theme("light")
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
