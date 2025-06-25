from __future__ import annotations

import traceback

from bec_widgets.utils.error_popups import SafeSlot, WarningPopupUtility
from bec_widgets.utils.toolbars.actions import MaterialIconAction, SwitchableToolBarAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle, ToolbarComponents
from bec_widgets.utils.toolbars.connections import BundleConnection


def plot_export_bundle(components: ToolbarComponents) -> ToolbarBundle:
    """
    Creates a plot export toolbar bundle.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The plot export toolbar bundle.
    """
    components.add_safe(
        "save",
        MaterialIconAction(
            icon_name="save", tooltip="Open Export Dialog", parent=components.toolbar
        ),
    )
    components.add_safe(
        "matplotlib",
        MaterialIconAction(
            icon_name="photo_library", tooltip="Open Matplotlib Dialog", parent=components.toolbar
        ),
    )
    components.add_safe(
        "export_switch",
        SwitchableToolBarAction(
            actions={
                "save": components.get_action_reference("save")(),
                "matplotlib": components.get_action_reference("matplotlib")(),
            },
            initial_action="save",
            tooltip="Export Plot",
            checkable=False,
            parent=components.toolbar,
        ),
    )
    bundle = ToolbarBundle("plot_export", components)
    bundle.add_action("export_switch")
    return bundle


def plot_export_connection(components: ToolbarComponents, target_widget=None):
    """
    Connects the plot export actions to the target widget.
    Args:
        components (ToolbarComponents): The components to be connected.
        target_widget: The widget to which the actions will be connected.
    """


class PlotExportConnection(BundleConnection):
    def __init__(self, components: ToolbarComponents, target_widget):
        super().__init__()
        self.bundle_name = "plot_export"
        self.components = components
        self.target_widget = target_widget
        self._connected = False  # Track if the connection has been made

    def connect(self):
        self._connected = True
        # Connect the actions to the target widget
        self.components.get_action_reference("save")().action.triggered.connect(self.export_dialog)
        self.components.get_action_reference("matplotlib")().action.triggered.connect(
            self.matplotlib_dialog
        )

    def disconnect(self):
        if not self._connected:
            return
        # Disconnect the actions from the target widget
        self.components.get_action_reference("save")().action.triggered.disconnect(
            self.export_dialog
        )
        self.components.get_action_reference("matplotlib")().action.triggered.disconnect(
            self.matplotlib_dialog
        )

    @SafeSlot()
    def export_dialog(self):
        """
        Open the export dialog for the plot widget.
        """
        if self.target_widget:
            scene = self.target_widget.plot_item.scene()
            scene.contextMenuItem = self.target_widget.plot_item
            scene.showExportDialog()

    @SafeSlot()
    def matplotlib_dialog(self):
        """
        Export the plot widget to Matplotlib.
        """
        if self.target_widget:
            try:
                import matplotlib as mpl

                MatplotlibExporter(self.target_widget.plot_item).export()
            except ModuleNotFoundError:
                warning_util = WarningPopupUtility()
                warning_util.show_warning(
                    title="Matplotlib not installed",
                    message="Matplotlib is required for this feature.",
                    detailed_text="Please install matplotlib in your Python environment by using 'pip install matplotlib'.",
                )
                return
            except TypeError:
                warning_util = WarningPopupUtility()
                error_msg = traceback.format_exc()
                warning_util.show_warning(
                    title="Matplotlib TypeError",
                    message="Matplotlib exporter could not resolve the plot item.",
                    detailed_text=error_msg,
                )
                return
