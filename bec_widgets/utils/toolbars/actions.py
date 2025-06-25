# pylint: disable=no-name-in-module
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Dict, Literal

from bec_lib.device import ReadoutPriority
from bec_lib.logger import bec_logger
from bec_qthemes._icon.material_icons import material_icon
from qtpy.QtCore import QSize, Qt, QTimer
from qtpy.QtGui import QAction, QColor, QIcon
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QStyledItemDelegate,
    QToolBar,
    QToolButton,
    QWidget,
)

import bec_widgets
from bec_widgets.widgets.control.device_input.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox

logger = bec_logger.logger

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class NoCheckDelegate(QStyledItemDelegate):
    """To reduce space in combo boxes by removing the checkmark."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # Remove any check indicator
        option.checkState = Qt.Unchecked


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

    def cleanup(self):
        """Cleans up the action, if necessary."""
        pass


class SeparatorAction(ToolBarAction):
    """Separator action for the toolbar."""

    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        toolbar.addSeparator()


class QtIconAction(ToolBarAction):
    def __init__(self, standard_icon, tooltip=None, checkable=False, parent=None):
        super().__init__(icon_path=None, tooltip=tooltip, checkable=checkable)
        self.standard_icon = standard_icon
        self.icon = QApplication.style().standardIcon(standard_icon)
        self.action = QAction(icon=self.icon, text=self.tooltip, parent=parent)
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
        if parent is None:
            logger.warning(
                "MaterialIconAction was created without a parent. Please consider adding one. Using None as parent may cause issues."
            )
        self.action = QAction(icon=self.icon, text=self.tooltip, parent=parent)
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
        widget = QWidget(parent=target)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if self.label is not None:
            label = QLabel(text=f"{self.label}", parent=target)
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
            menu_action = QAction(
                icon=action_obj.get_icon(), text=action_obj.tooltip, parent=self.main_button
            )
            menu_action.setIconVisibleInMenu(True)
            menu_action.setCheckable(self.checkable)
            menu_action.setChecked(key == self.current_key)
            menu_action.triggered.connect(lambda checked, k=key: self.set_default_action(k))
            menu.addAction(menu_action)
        self.main_button.setMenu(menu)
        if self.default_state_checked:
            self.main_button.setChecked(True)
        self.action = toolbar.addWidget(self.main_button)

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
        if self.main_button is None:
            return
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

    def block_all_signals(self, block: bool = True):
        """
        Blocks or unblocks all signals for the actions in the toolbar.

        Args:
            block (bool): Whether to block signals. Defaults to True.
        """
        if self.main_button is not None:
            self.main_button.blockSignals(block)

        for action in self.actions.values():
            action.action.blockSignals(block)

    @contextmanager
    def signal_blocker(self):
        """
        Context manager to block signals for all actions in the toolbar.
        """
        self.block_all_signals(True)
        try:
            yield
        finally:
            self.block_all_signals(False)

    def set_state_all(self, state: bool):
        """
        Uncheck all actions in the toolbar.
        """
        for action in self.actions.values():
            action.action.setChecked(state)
        if self.main_button is None:
            return
        self.main_button.setChecked(state)

    def get_icon(self) -> QIcon:
        return self.actions[self.current_key].get_icon()


class WidgetAction(ToolBarAction):
    """
    Action for adding any widget to the toolbar.
    Please note that the injected widget must be life-cycled by the parent widget,
    i.e., the widget must be properly cleaned up outside of this action. The WidgetAction
    will not perform any cleanup on the widget itself, only on the container that holds it.

    Args:
        label (str|None): The label for the widget.
        widget (QWidget): The widget to be added to the toolbar.
        adjust_size (bool): Whether to adjust the size of the widget based on its contents. Defaults to True.
    """

    def __init__(
        self,
        label: str | None = None,
        widget: QWidget = None,
        adjust_size: bool = True,
        parent=None,
    ):
        super().__init__(icon_path=None, tooltip=label, checkable=False)
        self.label = label
        self.widget = widget
        self.container = None
        self.adjust_size = adjust_size

    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        """
        Adds the widget to the toolbar.

        Args:
            toolbar (QToolBar): The toolbar to add the widget to.
            target (QWidget): The target widget for the action.
        """
        self.container = QWidget(parent=target)
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self.label is not None:
            label_widget = QLabel(text=f"{self.label}", parent=target)
            label_widget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            label_widget.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            layout.addWidget(label_widget)

        if isinstance(self.widget, QComboBox) and self.adjust_size:
            self.widget.setSizeAdjustPolicy(QComboBox.AdjustToContents)

            size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.widget.setSizePolicy(size_policy)

            self.widget.setMinimumWidth(self.calculate_minimum_width(self.widget))

        layout.addWidget(self.widget)

        toolbar.addWidget(self.container)
        # Store the container as the action to allow toggling visibility.
        self.action = self.container

    def cleanup(self):
        """
        Cleans up the action by closing and deleting the container widget.
        This method will be called automatically when the toolbar is cleaned up.
        """
        if self.container is not None:
            self.container.close()
            self.container.deleteLater()
        return super().cleanup()

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
        for action_container in self.actions.values():
            action: QAction = action_container.action
            action.setIconVisibleInMenu(True)
            if action_container.icon_path:
                icon = QIcon()
                icon.addFile(action_container.icon_path, size=QSize(20, 20))
                action.setIcon(icon)
            elif hasattr(action, "get_icon") and callable(action_container.get_icon):
                sub_icon = action_container.get_icon()
                if sub_icon and not sub_icon.isNull():
                    action.setIcon(sub_icon)
            action.setCheckable(action_container.checkable)
            menu.addAction(action)
        button.setMenu(menu)
        toolbar.addWidget(button)


class DeviceComboBoxAction(WidgetAction):
    """
    Action for a device selection combobox in the toolbar.

    Args:
        label (str): The label for the combobox.
        device_combobox (QComboBox): The combobox for selecting the device.
    """

    def __init__(
        self,
        target_widget: QWidget,
        device_filter: list[BECDeviceFilter] | None = None,
        readout_priority_filter: (
            str | ReadoutPriority | list[str] | list[ReadoutPriority] | None
        ) = None,
        tooltip: str | None = None,
        add_empty_item: bool = False,
        no_check_delegate: bool = False,
    ):
        self.combobox = DeviceComboBox(
            parent=target_widget,
            device_filter=device_filter,
            readout_priority_filter=readout_priority_filter,
        )
        super().__init__(widget=self.combobox, adjust_size=False)

        if add_empty_item:
            self.combobox.addItem("", None)
            self.combobox.setCurrentText("")
        if tooltip is not None:
            self.combobox.setToolTip(tooltip)
        if no_check_delegate:
            self.combobox.setItemDelegate(NoCheckDelegate(self.combobox))

    def cleanup(self):
        """
        Cleans up the action by closing and deleting the combobox widget.
        This method will be called automatically when the toolbar is cleaned up.
        """
        if self.combobox is not None:
            self.combobox.close()
            self.combobox.deleteLater()
        return super().cleanup()
