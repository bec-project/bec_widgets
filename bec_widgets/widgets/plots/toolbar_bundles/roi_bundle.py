from bec_widgets.utils.toolbar import MaterialIconAction, ToolbarBundle


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
        reset_legend = MaterialIconAction(
            icon_name="restart_alt", tooltip="Reset the position of legend.", checkable=False
        )

        # Add them to the bundle
        self.add_action("crosshair", crosshair)
        self.add_action("reset_legend", reset_legend)

        # Immediately connect signals
        crosshair.action.toggled.connect(self.target_widget.toggle_crosshair)
        reset_legend.action.triggered.connect(self.target_widget.reset_legend)
