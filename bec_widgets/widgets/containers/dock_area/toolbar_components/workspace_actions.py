from __future__ import annotations

from typing import Callable

from qtpy.QtCore import Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QComboBox, QSizePolicy

from bec_widgets import SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction, WidgetAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle, ToolbarComponents
from bec_widgets.utils.toolbars.connections import BundleConnection
from bec_widgets.widgets.containers.dock_area.profile_utils import list_quick_profiles


class ProfileComboBox(QComboBox):
    """Custom combobox that displays icons for read-only profiles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._quick_provider: Callable[[], list[str]] = list_quick_profiles

    def set_quick_profile_provider(self, provider: Callable[[], list[str]]) -> None:
        self._quick_provider = provider

    def refresh_profiles(
        self, active_profile: str | None = None, show_empty_profile: bool = False
    ) -> None:
        """
        Refresh the profile list and ensure the active profile is visible.

        Args:
            active_profile(str | None): The currently active profile name.
            show_empty_profile(bool): If True, show an explicit empty unsaved workspace entry.
        """

        current_text = active_profile or self.currentText()
        self.blockSignals(True)
        self.clear()

        quick_profiles = self._quick_provider()
        quick_set = set(quick_profiles)

        items: list[str] = []
        if show_empty_profile:
            items.append("")

        if active_profile and active_profile not in quick_set:
            items.append(active_profile)

        for profile in quick_profiles:
            if profile not in items:
                items.append(profile)

        if active_profile and active_profile not in quick_set:
            # keep active profile at the top when not in quick list
            items.remove(active_profile)
            insert_pos = 1 if show_empty_profile else 0
            items.insert(insert_pos, active_profile)

        for profile in items:
            self.addItem(profile)
            idx = self.count() - 1

            # Reset any custom styling
            self.setItemData(idx, None, Qt.ItemDataRole.FontRole)
            self.setItemData(idx, None, Qt.ItemDataRole.ToolTipRole)
            self.setItemData(idx, None, Qt.ItemDataRole.ForegroundRole)

            if profile == "":
                self.setItemData(idx, "Unsaved empty workspace", Qt.ItemDataRole.ToolTipRole)
                if active_profile is None:
                    font = QFont(self.font())
                    font.setItalic(True)
                    self.setItemData(idx, font, Qt.ItemDataRole.FontRole)
                    self.setCurrentIndex(idx)
                continue

            if active_profile and profile == active_profile:
                tooltip = "Active workspace profile"
                if profile not in quick_set:
                    font = QFont(self.font())
                    font.setItalic(True)
                    font.setBold(True)
                    self.setItemData(idx, font, Qt.ItemDataRole.FontRole)
                    self.setItemData(
                        idx, self.palette().highlight().color(), Qt.ItemDataRole.ForegroundRole
                    )
                    tooltip = "Active profile (not in quick select)"
                self.setItemData(idx, tooltip, Qt.ItemDataRole.ToolTipRole)
                self.setCurrentIndex(idx)
            elif profile not in quick_set:
                self.setItemData(idx, "Not in quick select", Qt.ItemDataRole.ToolTipRole)

        # Restore selection if possible
        if show_empty_profile and active_profile is None:
            empty_idx = self.findText("")
            if empty_idx >= 0:
                self.setCurrentIndex(empty_idx)
        else:
            index = self.findText(current_text)
            if index >= 0:
                self.setCurrentIndex(index)

        self.blockSignals(False)
        if active_profile and self.currentText() != active_profile:
            idx = self.findText(active_profile)
            if idx >= 0:
                self.setCurrentIndex(idx)
        if show_empty_profile and self.currentText() == "":
            self.setToolTip("Unsaved empty workspace")
        elif active_profile and active_profile not in quick_set:
            self.setToolTip("Active profile is not in quick select")
        else:
            self.setToolTip("")


def workspace_bundle(components: ToolbarComponents, enable_tools: bool = True) -> ToolbarBundle:
    """
    Creates a workspace toolbar bundle for AdvancedDockArea.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The workspace toolbar bundle.
    """
    # Workspace combo
    combo = ProfileComboBox(parent=components.toolbar)
    combo.setVisible(enable_tools)
    components.add_safe("workspace_combo", WidgetAction(widget=combo, adjust_size=False))

    components.add_safe(
        "save_workspace",
        MaterialIconAction(
            icon_name="save",
            tooltip="Save Current Workspace",
            checkable=False,
            parent=components.toolbar,
        ),
    )
    components.get_action("save_workspace").action.setVisible(enable_tools)

    components.add_safe(
        "reset_default_workspace",
        MaterialIconAction(
            icon_name="undo",
            tooltip="Refresh Current Workspace",
            checkable=False,
            parent=components.toolbar,
        ),
    )
    components.get_action("reset_default_workspace").action.setVisible(enable_tools)

    components.add_safe(
        "manage_workspaces",
        MaterialIconAction(
            icon_name="manage_accounts", tooltip="Manage", checkable=True, parent=components.toolbar
        ),
    )
    components.get_action("manage_workspaces").action.setVisible(enable_tools)

    bundle = ToolbarBundle("workspace", components)
    bundle.add_action("workspace_combo")
    bundle.add_action("save_workspace")
    bundle.add_action("reset_default_workspace")
    bundle.add_action("manage_workspaces")
    return bundle


class WorkspaceConnection(BundleConnection):
    """
    Connection class for workspace actions in AdvancedDockArea.
    """

    def __init__(self, components: ToolbarComponents, target_widget=None):
        super().__init__(parent=components.toolbar)
        self.bundle_name = "workspace"
        self.components = components
        self.target_widget = target_widget
        if not hasattr(self.target_widget, "workspace_is_locked"):
            raise AttributeError("Target widget must implement 'workspace_is_locked'.")
        self._connected = False

    def connect(self):
        self._connected = True
        # Connect the action to the target widget's method
        save_action = self.components.get_action("save_workspace").action
        if save_action.isVisible():
            save_action.triggered.connect(self.target_widget.save_profile_dialog)

        self.components.get_action("workspace_combo").widget.currentTextChanged.connect(
            self.target_widget.load_profile
        )

        reset_action = self.components.get_action("reset_default_workspace").action
        if reset_action.isVisible():
            reset_action.triggered.connect(self._reset_workspace_to_default)

        manage_action = self.components.get_action("manage_workspaces").action
        if manage_action.isVisible():
            manage_action.triggered.connect(self.target_widget.show_workspace_manager)

    def disconnect(self):
        if not self._connected:
            return
        # Disconnect the action from the target widget's method
        save_action = self.components.get_action("save_workspace").action
        if save_action.isVisible():
            save_action.triggered.disconnect(self.target_widget.save_profile_dialog)
        self.components.get_action("workspace_combo").widget.currentTextChanged.disconnect(
            self.target_widget.load_profile
        )

        reset_action = self.components.get_action("reset_default_workspace").action
        if reset_action.isVisible():
            reset_action.triggered.disconnect(self._reset_workspace_to_default)

        manage_action = self.components.get_action("manage_workspaces").action
        if manage_action.isVisible():
            manage_action.triggered.disconnect(self.target_widget.show_workspace_manager)
        self._connected = False

    @SafeSlot()
    def _reset_workspace_to_default(self):
        """
        Refreshes the current workspace.
        """
        self.target_widget.restore_user_profile_from_default()
