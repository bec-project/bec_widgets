from __future__ import annotations

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction, SwitchableToolBarAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle, ToolbarComponents
from bec_widgets.utils.toolbars.connections import BundleConnection


def image_roi_bundle(components: ToolbarComponents) -> ToolbarBundle:
    """
    Creates a toolbar bundle for ROI and crosshair interaction.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The ROI toolbar bundle.
    """
    components.add_safe(
        "image_crosshair",
        MaterialIconAction(
            icon_name="point_scan",
            tooltip="Show Crosshair",
            checkable=True,
            parent=components.toolbar,
        ),
    )
    components.add_safe(
        "image_crosshair_roi",
        MaterialIconAction(
            icon_name="my_location",
            tooltip="Show Crosshair with ROI plots",
            checkable=True,
            parent=components.toolbar,
        ),
    )
    components.add_safe(
        "image_switch_crosshair",
        SwitchableToolBarAction(
            actions={
                "crosshair": components.get_action_reference("image_crosshair")(),
                "crosshair_roi": components.get_action_reference("image_crosshair_roi")(),
            },
            initial_action="crosshair",
            tooltip="Crosshair",
            checkable=True,
            parent=components.toolbar,
        ),
    )
    bundle = ToolbarBundle("image_crosshair", components)
    bundle.add_action("image_switch_crosshair")
    return bundle


class ImageRoiConnection(BundleConnection):
    """
    Connection class for the ROI toolbar bundle.
    """

    def __init__(self, components: ToolbarComponents, target_widget=None):
        self.bundle_name = "roi"
        self.components = components
        self.target_widget = target_widget
        if not hasattr(self.target_widget, "toggle_roi_panels") or not hasattr(
            self.target_widget, "toggle_crosshair"
        ):
            raise AttributeError(
                "Target widget must implement 'toggle_roi_panels' and 'toggle_crosshair'."
            )
        super().__init__()
        self._connected = False

    def connect(self):
        self._connected = True
        # Connect the action to the target widget's method
        self.components.get_action("image_crosshair").action.toggled.connect(
            self.target_widget.toggle_crosshair
        )
        self.components.get_action("image_crosshair_roi").action.triggered.connect(
            self.target_widget.toggle_roi_panels
        )

    def disconnect(self):
        if not self._connected:
            return
        # Disconnect the action from the target widget's method
        self.components.get_action("image_crosshair").action.toggled.disconnect(
            self.target_widget.toggle_crosshair
        )
        self.components.get_action("image_crosshair_roi").action.triggered.disconnect(
            self.target_widget.toggle_roi_panels
        )


def image_autorange(components: ToolbarComponents) -> ToolbarBundle:
    """
    Creates a toolbar bundle for image autorange functionality.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The autorange toolbar bundle.
    """
    components.add_safe(
        "image_autorange_mean",
        MaterialIconAction(
            icon_name="hdr_auto",
            tooltip="Enable Auto Range (Mean)",
            checkable=True,
            parent=components.toolbar,
        ),
    )
    components.add_safe(
        "image_autorange_max",
        MaterialIconAction(
            icon_name="hdr_auto",
            tooltip="Enable Auto Range (Max)",
            checkable=True,
            parent=components.toolbar,
            filled=True,
        ),
    )
    components.add_safe(
        "image_autorange",
        SwitchableToolBarAction(
            actions={
                "mean": components.get_action_reference("image_autorange_mean")(),
                "max": components.get_action_reference("image_autorange_max")(),
            },
            initial_action="mean",
            tooltip="Autorange",
            checkable=True,
            parent=components.toolbar,
            default_state_checked=True,
        ),
    )
    bundle = ToolbarBundle("image_autorange", components)
    bundle.add_action("image_autorange")
    return bundle


def image_colorbar(components: ToolbarComponents) -> ToolbarBundle:
    """
    Creates a toolbar bundle for image colorbar functionality.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The colorbar toolbar bundle.
    """
    components.add_safe(
        "image_full_colorbar",
        MaterialIconAction(
            icon_name="edgesensor_low",
            tooltip="Enable Full Colorbar",
            checkable=True,
            parent=components.toolbar,
        ),
    )
    components.add_safe(
        "image_simple_colorbar",
        MaterialIconAction(
            icon_name="smartphone",
            tooltip="Enable Simple Colorbar",
            checkable=True,
            parent=components.toolbar,
        ),
    )
    components.add_safe(
        "image_colorbar_switch",
        SwitchableToolBarAction(
            actions={
                "full_colorbar": components.get_action_reference("image_full_colorbar")(),
                "simple_colorbar": components.get_action_reference("image_simple_colorbar")(),
            },
            initial_action="full_colorbar",
            tooltip="Colorbar",
            checkable=True,
            parent=components.toolbar,
        ),
    )
    bundle = ToolbarBundle("image_colorbar", components)
    bundle.add_action("image_colorbar_switch")
    return bundle


class ImageColorbarConnection(BundleConnection):
    """
    Connection class for the image colorbar toolbar bundle.
    """

    def __init__(self, components: ToolbarComponents, target_widget=None):
        self.bundle_name = "image_colorbar"
        self.components = components
        self.target_widget = target_widget
        if not hasattr(self.target_widget, "enable_colorbar"):
            raise AttributeError("Target widget must implement 'enable_colorbar' method.")
        super().__init__()
        self._connected = False

    def _enable_full_colorbar(self, checked: bool):
        """
        Enable or disable the full colorbar based on the checked state.
        """
        self.target_widget.enable_colorbar(checked, style="full")

    def _enable_simple_colorbar(self, checked: bool):
        """
        Enable or disable the simple colorbar based on the checked state.
        """
        self.target_widget.enable_colorbar(checked, style="simple")

    def connect(self):
        self._connected = True
        # Connect the action to the target widget's method
        self.components.get_action("image_full_colorbar").action.toggled.connect(
            self._enable_full_colorbar
        )
        self.components.get_action("image_simple_colorbar").action.toggled.connect(
            self._enable_simple_colorbar
        )

    def disconnect(self):
        if not self._connected:
            return
        # Disconnect the action from the target widget's method
        self.components.get_action("image_full_colorbar").action.toggled.disconnect(
            self._enable_full_colorbar
        )
        self.components.get_action("image_simple_colorbar").action.toggled.disconnect(
            self._enable_simple_colorbar
        )


def image_processing(components: ToolbarComponents) -> ToolbarBundle:
    """
    Creates a toolbar bundle for image processing functionality.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The image processing toolbar bundle.
    """
    components.add_safe(
        "image_processing_fft",
        MaterialIconAction(
            icon_name="fft", tooltip="Toggle FFT", checkable=True, parent=components.toolbar
        ),
    )
    components.add_safe(
        "image_processing_log",
        MaterialIconAction(
            icon_name="log_scale", tooltip="Toggle Log", checkable=True, parent=components.toolbar
        ),
    )
    components.add_safe(
        "image_processing_transpose",
        MaterialIconAction(
            icon_name="transform",
            tooltip="Transpose Image",
            checkable=True,
            parent=components.toolbar,
        ),
    )
    components.add_safe(
        "image_processing_rotate_right",
        MaterialIconAction(
            icon_name="rotate_right",
            tooltip="Rotate image clockwise by 90 deg",
            parent=components.toolbar,
        ),
    )
    components.add_safe(
        "image_processing_rotate_left",
        MaterialIconAction(
            icon_name="rotate_left",
            tooltip="Rotate image counterclockwise by 90 deg",
            parent=components.toolbar,
        ),
    )
    components.add_safe(
        "image_processing_reset",
        MaterialIconAction(
            icon_name="reset_settings", tooltip="Reset Image Settings", parent=components.toolbar
        ),
    )
    bundle = ToolbarBundle("image_processing", components)
    bundle.add_action("image_processing_fft")
    bundle.add_action("image_processing_log")
    bundle.add_action("image_processing_transpose")
    bundle.add_action("image_processing_rotate_right")
    bundle.add_action("image_processing_rotate_left")
    bundle.add_action("image_processing_reset")
    return bundle


class ImageProcessingConnection(BundleConnection):
    """
    Connection class for the image processing toolbar bundle.
    """

    def __init__(self, components: ToolbarComponents, target_widget=None):
        self.bundle_name = "image_processing"
        self.components = components
        self.target_widget = target_widget
        if (
            not hasattr(self.target_widget, "fft")
            or not hasattr(self.target_widget, "log")
            or not hasattr(self.target_widget, "transpose")
            or not hasattr(self.target_widget, "num_rotation_90")
        ):
            raise AttributeError(
                "Target widget must implement 'fft', 'log', 'transpose', and 'num_rotation_90' attributes."
            )
        super().__init__()
        self.fft = components.get_action("image_processing_fft")
        self.log = components.get_action("image_processing_log")
        self.transpose = components.get_action("image_processing_transpose")
        self.right = components.get_action("image_processing_rotate_right")
        self.left = components.get_action("image_processing_rotate_left")
        self.reset = components.get_action("image_processing_reset")
        self._connected = False

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

    def connect(self):
        """
        Connect the actions to the target widget's methods.
        """
        self._connected = True
        self.fft.action.triggered.connect(self.toggle_fft)
        self.log.action.triggered.connect(self.toggle_log)
        self.transpose.action.triggered.connect(self.toggle_transpose)
        self.right.action.triggered.connect(self.rotate_right)
        self.left.action.triggered.connect(self.rotate_left)
        self.reset.action.triggered.connect(self.reset_settings)

    def disconnect(self):
        """
        Disconnect the actions from the target widget's methods.
        """
        if not self._connected:
            return
        self.fft.action.triggered.disconnect(self.toggle_fft)
        self.log.action.triggered.disconnect(self.toggle_log)
        self.transpose.action.triggered.disconnect(self.toggle_transpose)
        self.right.action.triggered.disconnect(self.rotate_right)
        self.left.action.triggered.disconnect(self.rotate_left)
        self.reset.action.triggered.disconnect(self.reset_settings)
