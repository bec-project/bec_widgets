from bec_widgets.qt_utils.toolbar import MaterialIconAction, ToolbarBundle


class ROIBundle(ToolbarBundle):
    """
    A bundle of actions that are hooked in this constructor itself,
    so that you can immediately connect the signals and toggle states.

    This bundle is for a toolbar that controls crosshair and ROI interaction.
    """

    def __init__(self, bundle_id="roi", target_widget=None, **kwargs):
        super().__init__(bundle_id=bundle_id, actions=[], **kwargs)
        self.target_widget = target_widget

        # Create each MaterialIconAction with a parent
        # so the signals can fire even if the toolbar isn't added yet.
        crosshair = MaterialIconAction(
            icon_name="point_scan", tooltip="Show Crosshair", checkable=True
        )
        roi = MaterialIconAction(
            icon_name="align_justify_space_between",
            tooltip="Add ROI region for DAP",
            checkable=True,
        )

        # Add them to the bundle
        self.add_action("crosshair", crosshair)
        self.add_action("roi_linear", roi)

        # Immediately connect signals
        crosshair.action.toggled.connect(self.target_widget.toggle_crosshair)
