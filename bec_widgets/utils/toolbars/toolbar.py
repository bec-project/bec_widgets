# pylint: disable=no-name-in-module
from __future__ import annotations

import sys
from collections import defaultdict
from typing import DefaultDict, Literal

from bec_lib.logger import bec_logger
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QAction, QColor
from qtpy.QtWidgets import QApplication, QLabel, QMainWindow, QMenu, QToolBar, QVBoxLayout, QWidget

from bec_widgets.utils.colors import get_theme_name, set_theme
from bec_widgets.utils.toolbars.actions import MaterialIconAction, ToolBarAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle, ToolbarComponents
from bec_widgets.utils.toolbars.connections import BundleConnection

logger = bec_logger.logger

# Ensure that icons are shown in menus (especially on macOS)
QApplication.setAttribute(Qt.AA_DontShowIconsInMenus, False)


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
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        background_color: str = "rgba(0, 0, 0, 0)",
    ):
        super().__init__(parent=parent)

        self.background_color = background_color
        self.set_background_color(self.background_color)

        # Set the initial orientation
        self.set_orientation(orientation)

        self.components = ToolbarComponents(self)

        # Initialize bundles
        self.bundles: dict[str, ToolbarBundle] = {}
        self.shown_bundles: list[str] = []

        #########################
        # outdated items... remove
        self.available_widgets: DefaultDict[str, ToolBarAction] = defaultdict()
        ########################

    def new_bundle(self, name: str) -> ToolbarBundle:
        """
        Creates a new bundle component.

        Args:
            name (str): Unique identifier for the bundle.

        Returns:
            ToolbarBundle: The new bundle component.
        """
        if name in self.bundles:
            raise ValueError(f"Bundle with name '{name}' already exists.")
        bundle = ToolbarBundle(name=name, components=self.components)
        self.bundles[name] = bundle
        return bundle

    def add_bundle(self, bundle: ToolbarBundle):
        """
        Adds a bundle component to the toolbar.

        Args:
            bundle (ToolbarBundle): The bundle component to add.
        """
        if bundle.name in self.bundles:
            raise ValueError(f"Bundle with name '{bundle.name}' already exists.")
        self.bundles[bundle.name] = bundle
        if not bundle.bundle_actions:
            logger.warning(f"Bundle '{bundle.name}' has no actions.")

    def remove_bundle(self, name: str):
        """
        Removes a bundle component by name.

        Args:
            name (str): The name of the bundle to remove.
        """
        if name not in self.bundles:
            raise KeyError(f"Bundle with name '{name}' does not exist.")
        del self.bundles[name]
        if name in self.shown_bundles:
            self.shown_bundles.remove(name)
        logger.info(f"Bundle '{name}' removed from the toolbar.")

    def get_bundle(self, name: str) -> ToolbarBundle:
        """
        Retrieves a bundle component by name.

        Args:
            name (str): The name of the bundle to retrieve.

        Returns:
            ToolbarBundle: The bundle component.
        """
        if name not in self.bundles:
            raise KeyError(
                f"Bundle with name '{name}' does not exist. Available bundles: {list(self.bundles.keys())}"
            )
        return self.bundles[name]

    def show_bundles(self, bundle_names: list[str]):
        """
        Sets the bundles to be shown for the toolbar.

        Args:
            bundle_names (list[str]): A list of bundle names to show. If a bundle is not in this list, its actions will be hidden.
        """
        self.clear()
        for requested_bundle in bundle_names:
            bundle = self.get_bundle(requested_bundle)
            for bundle_action in bundle.bundle_actions.values():
                action = bundle_action()
                if action is None:
                    logger.warning(
                        f"Action for bundle '{requested_bundle}' has been deleted. Skipping."
                    )
                    continue
                action.add_to_toolbar(self, self.parent())
            separator = self.components.get_action_reference("separator")()
            if separator is not None:
                separator.add_to_toolbar(self, self.parent())
        self.update_separators()  # Ensure separators are updated after showing bundles
        self.shown_bundles = bundle_names

    def add_action(self, action_name: str, action: ToolBarAction):
        """
        Adds a single action to the toolbar. It will create a new bundle
        with the same name as the action.

        Args:
            action_name (str): Unique identifier for the action.
            action (ToolBarAction): The action to add.
        """
        self.components.add_safe(action_name, action)
        bundle = ToolbarBundle(name=action_name, components=self.components)
        bundle.add_action(action_name)
        self.add_bundle(bundle)

    def hide_action(self, action_name: str):
        """
        Hides a specific action in the toolbar.

        Args:
            action_name (str): Unique identifier for the action to hide.
        """
        action = self.components.get_action(action_name)
        if hasattr(action, "action") and action.action is not None:
            action.action.setVisible(False)
            self.update_separators()

    def show_action(self, action_name: str):
        """
        Shows a specific action in the toolbar.

        Args:
            action_name (str): Unique identifier for the action to show.
        """
        action = self.components.get_action(action_name)
        if hasattr(action, "action") and action.action is not None:
            action.action.setVisible(True)
            self.update_separators()

    @property
    def toolbar_actions(self) -> list[ToolBarAction]:
        """
        Returns a list of all actions currently in the toolbar.

        Returns:
            list[ToolBarAction]: List of actions in the toolbar.
        """
        actions = []
        for bundle in self.shown_bundles:
            if bundle not in self.bundles:
                continue
            for action in self.bundles[bundle].bundle_actions.values():
                action_instance = action()
                if action_instance is not None:
                    actions.append(action_instance)
        return actions

    def refresh(self):
        """Refreshes the toolbar by clearing and re-populating it."""
        self.clear()
        self.show_bundles(self.shown_bundles)

    def connect_bundle(self, connection_name: str, connector: BundleConnection):
        """
        Connects a bundle to a target widget or application.

        Args:
            bundle_name (str): The name of the bundle to connect.
            connector (BundleConnection): The connector instance that implements the connection logic.
        """
        bundle_name = connector.bundle_name
        if bundle_name not in self.bundles:
            raise KeyError(f"Bundle with name '{bundle_name}' does not exist.")
        connector.connect()
        self.bundles[bundle_name].add_connection(connection_name, connector)

    def disconnect_bundle(self, bundle_name: str, connection_name: str | None = None):
        """
        Disconnects a bundle connection.

        Args:
            bundle_name (str): The name of the bundle to disconnect.
            connection_name (str): The name of the connection to disconnect. If None, disconnects all connections for the bundle.
        """
        if bundle_name not in self.bundles:
            raise KeyError(f"Bundle with name '{bundle_name}' does not exist.")
        bundle = self.bundles[bundle_name]
        if connection_name is None:
            # Disconnect all connections in the bundle
            bundle.disconnect()
        else:
            bundle.remove_connection(name=connection_name)

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
        for action in self.available_widgets.values():
            if isinstance(action, MaterialIconAction):
                action.color = new_color
                updated_icon = action.get_icon()
                action.action.setIcon(updated_icon)

    def contextMenuEvent(self, event):
        """
        Overrides the context menu event to show toolbar actions with checkboxes and icons.

        Args:
            event (QContextMenuEvent): The context menu event.
        """
        menu = QMenu(self)
        theme = get_theme_name()
        if theme == "dark":
            menu.setStyleSheet(
                """
                QMenu {
                    background-color: rgba(50, 50, 50, 0.9);
                    border: 1px solid rgba(255, 255, 255, 0.2);
                }
                QMenu::item:selected {
                    background-color: rgba(0, 0, 255, 0.2);
                }
            """
            )
        else:
            # Light theme styling
            menu.setStyleSheet(
                """
                QMenu {
                    background-color: rgba(255, 255, 255, 0.9);
                    border: 1px solid rgba(0, 0, 0, 0.2);
                }
                QMenu::item:selected {
                    background-color: rgba(0, 0, 255, 0.2);
                }
            """
            )
        for ii, bundle in enumerate(self.shown_bundles):
            self.handle_bundle_context_menu(menu, bundle)
            if ii < len(self.shown_bundles) - 1:
                menu.addSeparator()
        menu.triggered.connect(self.handle_menu_triggered)
        menu.exec_(event.globalPos())

    def handle_bundle_context_menu(self, menu: QMenu, bundle_id: str):
        """
        Adds bundle actions to the context menu.

        Args:
            menu (QMenu): The context menu.
            bundle_id (str): The bundle identifier.
        """
        bundle = self.bundles.get(bundle_id)
        if not bundle:
            return
        for act_id in bundle.bundle_actions:
            toolbar_action = self.components.get_action(act_id)
            if not isinstance(toolbar_action, ToolBarAction) or not hasattr(
                toolbar_action, "action"
            ):
                continue
            qaction = toolbar_action.action
            if not isinstance(qaction, QAction):
                continue
            self._add_qaction_to_menu(menu, qaction, toolbar_action, act_id)

    def _add_qaction_to_menu(
        self, menu: QMenu, qaction: QAction, toolbar_action: ToolBarAction, act_id: str
    ):
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
        toolbar_action = self.available_widgets.get(action_id)
        if not isinstance(toolbar_action, ToolBarAction) or not hasattr(toolbar_action, "action"):
            return
        qaction = toolbar_action.action
        if not isinstance(qaction, QAction):
            return
        display_name = qaction.text() or toolbar_action.tooltip or action_id
        menu_action = QAction(display_name, self)
        menu_action.setCheckable(True)
        menu_action.setChecked(qaction.isVisible())
        menu_action.setIconVisibleInMenu(True)
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
            self.toggle_action_visibility(action_id)

    def toggle_action_visibility(self, action_id: str, visible: bool | None = None):
        """
        Toggles the visibility of a specific action.

        Args:
            action_id (str): Unique identifier.
            visible (bool): Whether the action should be visible. If None, toggles the current visibility.
        """
        if not self.components.exists(action_id):
            return
        tool_action = self.components.get_action(action_id)
        if hasattr(tool_action, "action") and tool_action.action is not None:
            if visible is None:
                visible = not tool_action.action.isVisible()
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

        if not toolbar_actions:
            return

        # Make sure the first visible action is not a separator
        for i, action in enumerate(toolbar_actions):
            if action.isVisible():
                if action.isSeparator():
                    action.setVisible(False)
                break

        # Make sure the last visible action is not a separator
        for i, action in enumerate(reversed(toolbar_actions)):
            if action.isVisible():
                if action.isSeparator():
                    action.setVisible(False)
                break

    def cleanup(self):
        """
        Cleans up the toolbar by removing all actions and bundles.
        """
        # First, disconnect all bundles
        for bundle_name in list(self.bundles.keys()):
            self.disconnect_bundle(bundle_name)

        # Clear all components
        self.components.cleanup()
        self.bundles.clear()


if __name__ == "__main__":  # pragma: no cover
    from bec_widgets.utils.toolbars.performance import PerformanceConnection, performance_bundle
    from bec_widgets.widgets.plots.toolbar_components.plot_export import plot_export_bundle

    class MainWindow(QMainWindow):  # pragma: no cover
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Toolbar / ToolbarBundle Demo")
            self.central_widget = QWidget()
            self.setCentralWidget(self.central_widget)
            self.test_label = QLabel(text="This is a test label.")
            self.central_widget.layout = QVBoxLayout(self.central_widget)
            self.central_widget.layout.addWidget(self.test_label)

            self.toolbar = ModularToolBar(parent=self)
            self.addToolBar(self.toolbar)
            self.toolbar.add_bundle(performance_bundle(self.toolbar.components))
            self.toolbar.add_bundle(plot_export_bundle(self.toolbar.components))
            self.toolbar.connect_bundle(
                "base", PerformanceConnection(self.toolbar.components, self)
            )
            self.toolbar.show_bundles(["performance", "plot_export"])
            self.toolbar.get_bundle("performance").add_action("save")
            self.toolbar.refresh()

        def enable_fps_monitor(self, enabled: bool):
            """
            Example method to enable or disable FPS monitoring.
            This method should be implemented in the target widget.
            """
            if enabled:
                self.test_label.setText("FPS Monitor Enabled")
            else:
                self.test_label.setText("FPS Monitor Disabled")

    app = QApplication(sys.argv)
    set_theme("light")
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
