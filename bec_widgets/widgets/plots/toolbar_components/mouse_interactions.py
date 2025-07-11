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
        self.mouse_mode = None
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
        Returns the current interaction mode of a PyQtGraph ViewBox and sets the corresponding action.
        """

        if self.target_widget:
            viewbox = self.target_widget.plot_item.getViewBox()
            switch_mouse_action = self.components.get_action_reference("switch_mouse_mode")()
            if viewbox.getState()["mouseMode"] == 3:
                switch_mouse_action.set_default_action("drag_mode")
                switch_mouse_action.main_button.setChecked(True)
                self.mouse_mode = "PanMode"
            elif viewbox.getState()["mouseMode"] == 1:
                switch_mouse_action.set_default_action("rectangle_mode")
                switch_mouse_action.main_button.setChecked(True)
                self.mouse_mode = "RectMode"

    @SafeSlot(bool)
    def enable_mouse_rectangle_mode(self, checked: bool):
        """
        Enable the rectangle zoom mode on the plot widget.
        """
        switch_mouse_action = self.components.get_action_reference("switch_mouse_mode")()
        if self.mouse_mode == "RectMode":
            switch_mouse_action.main_button.setChecked(True)
            return
        drag_mode = self.components.get_action_reference("mouse_drag")()
        drag_mode.action.setChecked(not checked)
        if self.target_widget and checked:
            self.target_widget.plot_item.getViewBox().setMouseMode(pg.ViewBox.RectMode)
            self.mouse_mode = "RectMode"

    @SafeSlot(bool)
    def enable_mouse_pan_mode(self, checked: bool):
        """
        Enable the pan mode on the plot widget.
        """
        if self.mouse_mode == "PanMode":
            switch_mouse_action = self.components.get_action_reference("switch_mouse_mode")()
            switch_mouse_action.main_button.setChecked(True)
            return
        rect_mode = self.components.get_action_reference("mouse_rect")()
        rect_mode.action.setChecked(not checked)
        if self.target_widget and checked:
            self.target_widget.plot_item.getViewBox().setMouseMode(pg.ViewBox.PanMode)
            self.mouse_mode = "PanMode"

    @SafeSlot()
    def autorange_plot(self):
        """
        Enable autorange on the plot widget.
        """
        if self.target_widget:
            self.target_widget.auto_range()
