from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QComboBox, QSizePolicy, QWidget

from bec_widgets import SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction, WidgetAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle, ToolbarComponents


class ProfileComboBox(QComboBox):
    """Custom combobox that displays icons for read-only profiles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def refresh_profiles(self):
        """Refresh the profile list with appropriate icons."""
        from ..advanced_dock_area import is_profile_readonly, list_profiles

        current_text = self.currentText()
        self.blockSignals(True)
        self.clear()

        lock_icon = material_icon("edit_off", size=(16, 16), convert_to_pixmap=False)

        for profile in list_profiles():
            if is_profile_readonly(profile):
                self.addItem(lock_icon, f"{profile}")
                # Set tooltip for read-only profiles
                self.setItemData(self.count() - 1, "Read-only profile", Qt.ToolTipRole)
            else:
                self.addItem(profile)

        # Restore selection if possible
        index = self.findText(current_text)
        if index >= 0:
            self.setCurrentIndex(index)

        self.blockSignals(False)


def workspace_bundle(components: ToolbarComponents) -> ToolbarBundle:
    """
    Creates a workspace toolbar bundle for AdvancedDockArea.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The workspace toolbar bundle.
    """
    # Lock icon action
    components.add_safe(
        "lock",
        MaterialIconAction(
            icon_name="lock_open_right",
            tooltip="Lock Workspace",
            checkable=True,
            parent=components.toolbar,
        ),
    )

    # Workspace combo
    combo = ProfileComboBox(parent=components.toolbar)
    components.add_safe("workspace_combo", WidgetAction(widget=combo, adjust_size=False))

    # Save the current workspace icon
    components.add_safe(
        "save_workspace",
        MaterialIconAction(
            icon_name="save",
            tooltip="Save Current Workspace",
            checkable=False,
            parent=components.toolbar,
        ),
    )
    # Delete workspace icon
    components.add_safe(
        "refresh_workspace",
        MaterialIconAction(
            icon_name="refresh",
            tooltip="Refresh Current Workspace",
            checkable=False,
            parent=components.toolbar,
        ),
    )
    # Delete workspace icon
    components.add_safe(
        "delete_workspace",
        MaterialIconAction(
            icon_name="delete",
            tooltip="Delete Current Workspace",
            checkable=False,
            parent=components.toolbar,
        ),
    )

    bundle = ToolbarBundle("workspace", components)
    bundle.add_action("lock")
    bundle.add_action("workspace_combo")
    bundle.add_action("save_workspace")
    bundle.add_action("refresh_workspace")
    bundle.add_action("delete_workspace")
    return bundle


class WorkspaceConnection:
    """
    Connection class for workspace actions in AdvancedDockArea.
    """

    def __init__(self, components: ToolbarComponents, target_widget=None):
        self.bundle_name = "workspace"
        self.components = components
        self.target_widget = target_widget
        if not hasattr(self.target_widget, "lock_workspace"):
            raise AttributeError("Target widget must implement 'lock_workspace'.")
        super().__init__()
        self._connected = False

    def connect(self):
        self._connected = True
        # Connect the action to the target widget's method
        self.components.get_action("lock").action.toggled.connect(self._lock_workspace)
        self.components.get_action("save_workspace").action.triggered.connect(
            self.target_widget.save_profile
        )
        self.components.get_action("workspace_combo").widget.currentTextChanged.connect(
            self.target_widget.load_profile
        )
        self.components.get_action("refresh_workspace").action.triggered.connect(
            self._refresh_workspace
        )
        self.components.get_action("delete_workspace").action.triggered.connect(
            self.target_widget.delete_profile
        )

    def disconnect(self):
        if not self._connected:
            return
        # Disconnect the action from the target widget's method
        self.components.get_action("lock").action.toggled.disconnect(self._lock_workspace)
        self.components.get_action("save_workspace").action.triggered.disconnect(
            self.target_widget.save_profile
        )
        self.components.get_action("workspace_combo").widget.currentTextChanged.disconnect(
            self.target_widget.load_profile
        )
        self.components.get_action("refresh_workspace").action.triggered.disconnect(
            self._refresh_workspace
        )
        self.components.get_action("delete_workspace").action.triggered.disconnect(
            self.target_widget.delete_profile
        )

    @SafeSlot(bool)
    def _lock_workspace(self, value: bool):
        """
        Switches the workspace lock state and change the icon accordingly.
        """
        setattr(self.target_widget, "lock_workspace", value)
        self.components.get_action("lock").action.setChecked(value)
        icon = material_icon(
            "lock" if value else "lock_open_right", size=(20, 20), convert_to_pixmap=False
        )
        self.components.get_action("lock").action.setIcon(icon)

    @SafeSlot()
    def _refresh_workspace(self):
        """
        Refreshes the current workspace.
        """
        combo = self.components.get_action("workspace_combo").widget
        current_workspace = combo.currentText()
        self.target_widget.load_profile(current_workspace)
