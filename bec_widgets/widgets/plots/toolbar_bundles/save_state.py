from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.qt_utils.toolbar import MaterialIconAction, ToolbarBundle


class SaveStateBundle(ToolbarBundle):
    """
    A bundle of actions that are hooked in this constructor itself,
    so that you can immediately connect the signals and toggle states.

    This bundle is for a toolbar that controls saving the state of the widget.
    """

    def __init__(self, bundle_id="mouse_interaction", target_widget=None, **kwargs):
        super().__init__(bundle_id=bundle_id, actions=[], **kwargs)
        self.target_widget = target_widget

        # Create each MaterialIconAction with a parent
        # so the signals can fire even if the toolbar isn't added yet.
        save_state = MaterialIconAction(
            icon_name="download", tooltip="Save Widget State", parent=self.target_widget
        )
        load_state = MaterialIconAction(
            icon_name="upload", tooltip="Load Widget State", parent=self.target_widget
        )

        # Add them to the bundle
        self.add_action("save", save_state)
        self.add_action("matplotlib", load_state)

        # Immediately connect signals
        save_state.action.triggered.connect(self.save_state_dialog)
        load_state.action.triggered.connect(self.load_state_dialog)

    @SafeSlot()
    def save_state_dialog(self):
        """
        Open the export dialog to save a state of the widget.
        """
        if self.target_widget:
            self.target_widget.state_manager.save_state()

    @SafeSlot()
    def load_state_dialog(self):
        """
        Load a saved state of the widget.
        """
        if self.target_widget:
            self.target_widget.state_manager.load_state()
