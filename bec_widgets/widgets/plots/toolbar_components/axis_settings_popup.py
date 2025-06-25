from __future__ import annotations

from typing import TYPE_CHECKING

from bec_widgets.utils.settings_dialog import SettingsDialog
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.connections import BundleConnection
from bec_widgets.widgets.plots.setting_menus.axis_settings import AxisSettings

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.utils.toolbars.toolbar import ToolbarComponents


def axis_popup_bundle(components: ToolbarComponents) -> ToolbarBundle:
    """
    Creates an axis popup toolbar bundle.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The axis popup toolbar bundle.
    """
    components.add_safe(
        "axis_settings_popup",
        MaterialIconAction(
            icon_name="settings",
            tooltip="Show Axis Settings",
            checkable=True,
            parent=components.toolbar,
        ),
    )
    bundle = ToolbarBundle("axis_popup", components)
    bundle.add_action("axis_settings_popup")
    return bundle


class AxisSettingsPopupConnection(BundleConnection):

    def __init__(self, components: ToolbarComponents, target_widget=None):
        self.bundle_name = "axis_popup"
        self.components = components
        self.target_widget = target_widget
        self.axis_settings_dialog = None
        self._connected = False
        super().__init__()

    def connect(self):
        self._connected = True
        # Connect the action to the target widget's method
        self.components.get_action_reference("axis_settings_popup")().action.triggered.connect(
            self.show_axis_settings_popup
        )

    def disconnect(self):
        if not self._connected:
            return
        # Disconnect the action from the target widget's method
        self.components.get_action_reference("axis_settings_popup")().action.triggered.disconnect(
            self.show_axis_settings_popup
        )

    def show_axis_settings_popup(self):
        """
        Show the axis settings dialog.
        """
        settings_action = self.components.get_action_reference("axis_settings_popup")().action
        if self.axis_settings_dialog is None or not self.axis_settings_dialog.isVisible():
            axis_setting = AxisSettings(
                parent=self.target_widget, target_widget=self.target_widget, popup=True
            )
            self.axis_settings_dialog = SettingsDialog(
                self.target_widget,
                settings_widget=axis_setting,
                window_title="Axis Settings",
                modal=False,
            )
            # When the dialog is closed, update the toolbar icon and clear the reference
            self.axis_settings_dialog.finished.connect(self._axis_settings_closed)
            self.axis_settings_dialog.show()
            settings_action.setChecked(True)
        else:
            # If already open, bring it to the front
            self.axis_settings_dialog.raise_()
            self.axis_settings_dialog.activateWindow()
            settings_action.setChecked(True)  # keep it toggled

    def _axis_settings_closed(self):
        """
        Slot for when the axis settings dialog is closed.
        """
        self.axis_settings_dialog = None
        self.components.get_action_reference("axis_settings_popup")().action.setChecked(False)
