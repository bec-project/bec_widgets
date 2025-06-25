from __future__ import annotations

from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle, ToolbarComponents
from bec_widgets.utils.toolbars.connections import BundleConnection


def roi_bundle(components: ToolbarComponents) -> ToolbarBundle:
    """
    Creates a toolbar bundle for ROI and crosshair interaction.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The ROI toolbar bundle.
    """
    components.add_safe(
        "crosshair",
        MaterialIconAction(
            icon_name="point_scan",
            tooltip="Show Crosshair",
            checkable=True,
            parent=components.toolbar,
        ),
    )
    components.add_safe(
        "reset_legend",
        MaterialIconAction(
            icon_name="restart_alt",
            tooltip="Reset the position of legend.",
            checkable=False,
            parent=components.toolbar,
        ),
    )
    bundle = ToolbarBundle("roi", components)
    bundle.add_action("crosshair")
    bundle.add_action("reset_legend")
    return bundle


class RoiConnection(BundleConnection):
    """
    Connection class for the ROI toolbar bundle.
    """

    def __init__(self, components: ToolbarComponents, target_widget=None):
        self.bundle_name = "roi"
        self.components = components
        self.target_widget = target_widget
        if not hasattr(self.target_widget, "toggle_crosshair") or not hasattr(
            self.target_widget, "reset_legend"
        ):
            raise AttributeError(
                "Target widget must implement 'toggle_crosshair' and 'reset_legend'."
            )
        super().__init__()
        self._connected = False

    def connect(self):
        self._connected = True
        # Connect the action to the target widget's method
        self.components.get_action_reference("crosshair")().action.toggled.connect(
            self.target_widget.toggle_crosshair
        )
        self.components.get_action_reference("reset_legend")().action.triggered.connect(
            self.target_widget.reset_legend
        )

    def disconnect(self):
        if not self._connected:
            return
        # Disconnect the action from the target widget's method
        self.components.get_action_reference("crosshair")().action.toggled.disconnect(
            self.target_widget.toggle_crosshair
        )
        self.components.get_action_reference("reset_legend")().action.triggered.disconnect(
            self.target_widget.reset_legend
        )
