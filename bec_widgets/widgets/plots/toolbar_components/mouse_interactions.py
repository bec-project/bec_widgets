from __future__ import annotations

from typing import TYPE_CHECKING

import pyqtgraph as pg

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction, SwitchableToolBarAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.connections import BundleConnection

if TYPE_CHECKING:
    from bec_widgets.utils.toolbars.toolbar import ToolbarComponents


def mouse_interaction_bundle(components: ToolbarComponents) -> ToolbarBundle:
    """
    Creates a mouse interaction toolbar bundle.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The mouse interaction toolbar bundle.
    """
    components.add_safe(
        "mouse_drag",
        MaterialIconAction(
            icon_name="drag_pan",
            tooltip="Drag Mouse Mode",
            checkable=True,
            parent=components.toolbar,
        ),
    )
    components.add_safe(
        "mouse_rect",
        MaterialIconAction(
            icon_name="frame_inspect",
            tooltip="Rectangle Zoom Mode",
            checkable=True,
            parent=components.toolbar,
        ),
    )
    components.add_safe(
        "auto_range",
        MaterialIconAction(
            icon_name="open_in_full",
            tooltip="Autorange Plot",
            checkable=False,
            parent=components.toolbar,
        ),
    )
    components.add_safe(
        "switch_mouse_mode",
        SwitchableToolBarAction(
            actions={
                "drag_mode": components.get_action_reference("mouse_drag")(),
                "rectangle_mode": components.get_action_reference("mouse_rect")(),
            },
            initial_action="drag_mode",
            tooltip="Mouse Modes",
            checkable=True,
            parent=components.toolbar,
            default_state_checked=True,
        ),
    )
    bundle = ToolbarBundle("mouse_interaction", components)
    bundle.add_action("switch_mouse_mode")
    bundle.add_action("auto_range")
    return bundle


class MouseInteractionConnection(BundleConnection):
    """
    Connection class for mouse interaction toolbar bundle.
    """

    def __init__(self, components: ToolbarComponents, target_widget=None):
        self.bundle_name = "mouse_interaction"
        self.components = components
        self.target_widget = target_widget
        if (
            not hasattr(self.target_widget, "plot_item")
            or not hasattr(self.target_widget, "auto_range_x")
            or not hasattr(self.target_widget, "auto_range_y")
        ):
            raise AttributeError(
                "Target widget must implement required methods for mouse interactions."
            )
        super().__init__()
        self._connected = False  # Track if the connection has been made

    def connect(self):
        self._connected = True
        drag = self.components.get_action_reference("mouse_drag")()
        rect = self.components.get_action_reference("mouse_rect")()
        auto = self.components.get_action_reference("auto_range")()

        drag.action.toggled.connect(self.enable_mouse_pan_mode)
        rect.action.toggled.connect(self.enable_mouse_rectangle_mode)
        auto.action.triggered.connect(self.autorange_plot)

    def disconnect(self):
        if not self._connected:
            return
        # Disconnect the action from the target widget's method
        drag = self.components.get_action_reference("mouse_drag")()
        rect = self.components.get_action_reference("mouse_rect")()
        auto = self.components.get_action_reference("auto_range")()
        drag.action.toggled.disconnect(self.enable_mouse_pan_mode)
        rect.action.toggled.disconnect(self.enable_mouse_rectangle_mode)
        auto.action.triggered.disconnect(self.autorange_plot)

    def get_viewbox_mode(self):
        """
        Synchronise the toolbar selection with the plot's current mouse interaction mode.
        """

        if not self.target_widget:
            return
        mouse_mode = self.target_widget.plot_item.getViewBox().getState()["mouseMode"]
        switch_mouse_action = self.components.get_action_reference("switch_mouse_mode")()
        if mouse_mode == pg.ViewBox.PanMode:
            switch_mouse_action.set_default_action("drag_mode")
        elif mouse_mode == pg.ViewBox.RectMode:
            switch_mouse_action.set_default_action("rectangle_mode")

    @SafeSlot(bool)
    def enable_mouse_rectangle_mode(self, checked: bool):
        """
        Enable the rectangle zoom mode on the plot widget.

        A mouse mode is always active. When the rectangle action is unchecked because the
        user switched to pan, the pan action becomes checked and takes over. When it is
        unchecked directly (e.g. clicking the active main button), no other mode is active,
        so the rectangle action is re-checked to avoid leaving every sub-action unchecked.
        """

        if not checked:
            self.components.get_action_reference("switch_mouse_mode")().main_button.setChecked(True)
            if not self.components.get_action_reference("mouse_drag")().action.isChecked():
                self.components.get_action_reference("mouse_rect")().action.setChecked(True)
            return
        if self.target_widget:
            self.target_widget.plot_item.getViewBox().setMouseMode(pg.ViewBox.RectMode)

    @SafeSlot(bool)
    def enable_mouse_pan_mode(self, checked: bool):
        """
        Enable the pan mode on the plot widget.

        See :meth:`enable_mouse_rectangle_mode`: the pan action is re-checked when it is
        unchecked directly while no other mode is active, so a mouse mode is always selected.
        """
        if not checked:
            self.components.get_action_reference("switch_mouse_mode")().main_button.setChecked(True)
            if not self.components.get_action_reference("mouse_rect")().action.isChecked():
                self.components.get_action_reference("mouse_drag")().action.setChecked(True)
            return
        if self.target_widget:
            self.target_widget.plot_item.getViewBox().setMouseMode(pg.ViewBox.PanMode)

    @SafeSlot()
    def autorange_plot(self):
        """
        Enable autorange on the plot widget.
        """
        if self.target_widget:
            self.target_widget.auto_range()
