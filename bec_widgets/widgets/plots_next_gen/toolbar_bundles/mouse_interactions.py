import pyqtgraph as pg
from qtpy.QtCore import QTimer

from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.qt_utils.toolbar import MaterialIconAction, SwitchableToolBarAction, ToolbarBundle


class MouseInteractionToolbarBundle(ToolbarBundle):
    """
    A bundle of actions that are hooked in this constructor itself,
    so that you can immediately connect the signals and toggle states.

    This bundle is for a toolbar that controls mouse interactions on a plot.
    """

    def __init__(self, bundle_id="mouse_interaction", target_widget=None, **kwargs):
        super().__init__(bundle_id=bundle_id, actions=[], **kwargs)
        self.target_widget = target_widget
        self.mouse_mode = None

        # Create each MaterialIconAction with a parent
        # so the signals can fire even if the toolbar isn't added yet.
        drag = MaterialIconAction(
            icon_name="drag_pan",
            tooltip="Drag Mouse Mode",
            checkable=True,
            parent=self.target_widget,  # or any valid parent
        )
        rect = MaterialIconAction(
            icon_name="frame_inspect",
            tooltip="Rectangle Zoom Mode",
            checkable=True,
            parent=self.target_widget,
        )
        auto = MaterialIconAction(
            icon_name="open_in_full",
            tooltip="Autorange Plot",
            checkable=False,
            parent=self.target_widget,
        )
        aspect_ratio = MaterialIconAction(
            icon_name="aspect_ratio",
            tooltip="Lock image aspect ratio",
            checkable=True,
            parent=self.target_widget,
        )

        self.switch_mouse_action = SwitchableToolBarAction(
            actions={"drag_mode": drag, "rectangle_mode": rect},
            initial_action="drag_mode",
            tooltip="Mouse Modes",
            checkable=True,
            parent=self,
        )

        # Add them to the bundle
        self.add_action("switch_mouse", self.switch_mouse_action)
        self.add_action("auto_range", auto)
        self.add_action("aspect_ratio", aspect_ratio)

        # Immediately connect signals
        drag.action.toggled.connect(self.enable_mouse_pan_mode)
        rect.action.toggled.connect(self.enable_mouse_rectangle_mode)
        auto.action.triggered.connect(self.autorange_plot)
        aspect_ratio.action.toggled.connect(self.lock_aspect_ratio)

        # Give some time to check the state
        QTimer.singleShot(10, self.get_viewbox_mode)

    def get_viewbox_mode(self):
        """
        Returns the current interaction mode of a PyQtGraph ViewBox and sets the corresponding action.
        """

        if self.target_widget:
            viewbox = self.target_widget.plot_item.getViewBox()
            if viewbox.getState()["mouseMode"] == 3:
                self.switch_mouse_action.set_default_action("drag_mode")
                self.switch_mouse_action.main_button.setChecked(True)
                self.mouse_mode = "PanMode"
            elif viewbox.getState()["mouseMode"] == 1:
                self.switch_mouse_action.set_default_action("rectangle_mode")
                self.switch_mouse_action.main_button.setChecked(True)
                self.mouse_mode = "RectMode"

    @SafeSlot(bool)
    def enable_mouse_rectangle_mode(self, checked: bool):
        """
        Enable the rectangle zoom mode on the plot widget.
        """
        if self.mouse_mode == "RectMode":
            self.switch_mouse_action.main_button.setChecked(True)
            return
        self.actions["switch_mouse"].actions["drag_mode"].action.setChecked(not checked)
        if self.target_widget and checked:
            self.target_widget.plot_item.getViewBox().setMouseMode(pg.ViewBox.RectMode)

    @SafeSlot(bool)
    def enable_mouse_pan_mode(self, checked: bool):
        """
        Enable the pan mode on the plot widget.
        """
        if self.mouse_mode == "PanMode":
            self.switch_mouse_action.main_button.setChecked(True)
            return
        self.actions["switch_mouse"].actions["rectangle_mode"].action.setChecked(not checked)
        if self.target_widget and checked:
            self.target_widget.plot_item.getViewBox().setMouseMode(pg.ViewBox.PanMode)

    @SafeSlot()
    def autorange_plot(self):
        """
        Enable autorange on the plot widget.
        """
        if self.target_widget:
            self.target_widget.auto_range_x = True
            self.target_widget.auto_range_y = True

    @SafeSlot(bool)
    def lock_aspect_ratio(self, checked: bool):
        if self.target_widget:
            self.target_widget.lock_aspect_ratio = checked
