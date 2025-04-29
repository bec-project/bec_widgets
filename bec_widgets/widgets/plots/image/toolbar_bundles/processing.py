from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbar import MaterialIconAction, ToolbarBundle


class ImageProcessingToolbarBundle(ToolbarBundle):
    """
    A bundle of actions for a toolbar that controls processing of monitor.
    """

    def __init__(self, bundle_id="mouse_interaction", target_widget=None, **kwargs):
        super().__init__(bundle_id=bundle_id, actions=[], **kwargs)
        self.target_widget = target_widget

        self.fft = MaterialIconAction(icon_name="fft", tooltip="Toggle FFT", checkable=True)
        self.log = MaterialIconAction(icon_name="log_scale", tooltip="Toggle Log", checkable=True)
        self.transpose = MaterialIconAction(
            icon_name="transform", tooltip="Transpose Image", checkable=True
        )
        self.right = MaterialIconAction(
            icon_name="rotate_right", tooltip="Rotate image clockwise by 90 deg"
        )
        self.left = MaterialIconAction(
            icon_name="rotate_left", tooltip="Rotate image counterclockwise by 90 deg"
        )
        self.reset = MaterialIconAction(icon_name="reset_settings", tooltip="Reset Image Settings")

        self.add_action("fft", self.fft)
        self.add_action("log", self.log)
        self.add_action("transpose", self.transpose)
        self.add_action("rotate_right", self.right)
        self.add_action("rotate_left", self.left)
        self.add_action("reset", self.reset)

        self.fft.action.triggered.connect(self.toggle_fft)
        self.log.action.triggered.connect(self.toggle_log)
        self.transpose.action.triggered.connect(self.toggle_transpose)
        self.right.action.triggered.connect(self.rotate_right)
        self.left.action.triggered.connect(self.rotate_left)
        self.reset.action.triggered.connect(self.reset_settings)

    @SafeSlot()
    def toggle_fft(self):
        checked = self.fft.action.isChecked()
        self.target_widget.fft = checked

    @SafeSlot()
    def toggle_log(self):
        checked = self.log.action.isChecked()
        self.target_widget.log = checked

    @SafeSlot()
    def toggle_transpose(self):
        checked = self.transpose.action.isChecked()
        self.target_widget.transpose = checked

    @SafeSlot()
    def rotate_right(self):
        if self.target_widget.num_rotation_90 is None:
            return
        rotation = (self.target_widget.num_rotation_90 - 1) % 4
        self.target_widget.num_rotation_90 = rotation

    @SafeSlot()
    def rotate_left(self):
        if self.target_widget.num_rotation_90 is None:
            return
        rotation = (self.target_widget.num_rotation_90 + 1) % 4
        self.target_widget.num_rotation_90 = rotation

    @SafeSlot()
    def reset_settings(self):
        self.target_widget.fft = False
        self.target_widget.log = False
        self.target_widget.transpose = False
        self.target_widget.num_rotation_90 = 0

        self.fft.action.setChecked(False)
        self.log.action.setChecked(False)
        self.transpose.action.setChecked(False)
