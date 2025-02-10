import pyqtgraph as pg

from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.qt_utils.toolbar import MaterialIconAction, ToolbarBundle


class MouseInteractionToolbarBundle(ToolbarBundle):
    """
    A bundle of actions that are hooked in this constructor itself,
    so that you can immediately connect the signals and toggle states.

    This bundle is for a toolbar that controls mouse interactions on a plot.
    """

    def __init__(self, bundle_id="mouse_interaction", target_widget=None, **kwargs):
        super().__init__(bundle_id=bundle_id, actions=[], **kwargs)
        self.target_widget = target_widget

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

        # Add them to the bundle
        self.add_action("drag_mode", drag)
        self.add_action("rectangle_mode", rect)
        self.add_action("auto_range", auto)
        self.add_action("aspect_ratio", aspect_ratio)

        # Immediately connect signals
        drag.action.toggled.connect(self.enable_mouse_pan_mode)
        rect.action.toggled.connect(self.enable_mouse_rectangle_mode)
        auto.action.triggered.connect(self.autorange_plot)
        aspect_ratio.action.toggled.connect(self.lock_aspect_ratio)

        mode = self.get_viewbox_mode()
        if mode == "PanMode":
            drag.action.setChecked(True)
        elif mode == "RectMode":
            rect.action.setChecked(True)

    def get_viewbox_mode(self) -> str:
        """
        Returns the current interaction mode of a PyQtGraph ViewBox.

        Returns:
            str: "PanMode" if pan is enabled, "RectMode" if zoom is enabled, "Unknown" otherwise.
        """
        if self.target_widget:
            viewbox = self.target_widget.plot_item.getViewBox()
            if viewbox.getState()["mouseMode"] == 3:
                return "PanMode"
            elif viewbox.getState()["mouseMode"] == 1:
                return "RectMode"
        return "Unknown"

    @SafeSlot(bool)
    def enable_mouse_rectangle_mode(self, checked: bool):
        """
        Enable the rectangle zoom mode on the plot widget.
        """
        self.actions["drag_mode"].action.setChecked(not checked)
        if self.target_widget and checked:
            self.target_widget.plot_item.getViewBox().setMouseMode(pg.ViewBox.RectMode)

    @SafeSlot(bool)
    def enable_mouse_pan_mode(self, checked: bool):
        """
        Enable the pan mode on the plot widget.
        """
        self.actions["rectangle_mode"].action.setChecked(not checked)
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
