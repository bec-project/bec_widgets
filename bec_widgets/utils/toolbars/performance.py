from __future__ import annotations

from typing import TYPE_CHECKING

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.connections import BundleConnection

if TYPE_CHECKING:
    from bec_widgets.utils.toolbars.toolbar import ToolbarComponents


def performance_bundle(components: ToolbarComponents) -> ToolbarBundle:
    """
    Creates a performance toolbar bundle.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The performance toolbar bundle.
    """
    components.add_safe(
        "fps_monitor",
        MaterialIconAction(
            icon_name="speed", tooltip="Show FPS Monitor", checkable=True, parent=components.toolbar
        ),
    )
    bundle = ToolbarBundle("performance", components)
    bundle.add_action("fps_monitor")
    return bundle


class PerformanceConnection(BundleConnection):

    def __init__(self, components: ToolbarComponents, target_widget=None):
        self.bundle_name = "performance"
        self.components = components
        self.target_widget = target_widget
        if not hasattr(self.target_widget, "enable_fps_monitor"):
            raise AttributeError("Target widget must implement 'enable_fps_monitor'.")
        super().__init__()
        self._connected = False

    @SafeSlot(bool)
    def set_fps_monitor(self, enabled: bool):
        setattr(self.target_widget, "enable_fps_monitor", enabled)

    def connect(self):
        self._connected = True
        # Connect the action to the target widget's method
        self.components.get_action_reference("fps_monitor")().action.toggled.connect(
            self.set_fps_monitor
        )

    def disconnect(self):
        if not self._connected:
            return
        # Disconnect the action from the target widget's method
        self.components.get_action_reference("fps_monitor")().action.toggled.disconnect(
            self.set_fps_monitor
        )
        self._connected = False
