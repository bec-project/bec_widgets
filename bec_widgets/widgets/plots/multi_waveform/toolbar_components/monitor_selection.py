from bec_lib.device import ReadoutPriority
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.toolbars.actions import DeviceComboBoxAction, WidgetAction
from bec_widgets.utils.toolbars.bundles import ToolbarComponents
from bec_widgets.utils.toolbars.toolbar import ToolbarBundle
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import BECDeviceFilter
from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget


def monitor_selection_bundle(
    components: ToolbarComponents, target_widget: QWidget
) -> ToolbarBundle:
    """
    Creates a monitor selection toolbar bundle.

    Args:
        components (ToolbarComponents): The components to be added to the bundle.

    Returns:
        ToolbarBundle: The monitor selection toolbar bundle.
    """
    components.add_safe(
        "monitor_selection",
        DeviceComboBoxAction(
            target_widget=target_widget,
            device_filter=[BECDeviceFilter.DEVICE],
            readout_priority_filter=ReadoutPriority.ASYNC,
            add_empty_item=True,
            no_check_delegate=True,
        ),
    )
    components.add_safe(
        "color_map", WidgetAction(widget=BECColorMapWidget(cmap="plasma"), adjust_size=False)
    )
    bundle = ToolbarBundle("monitor_selection", components)
    bundle.add_action("monitor_selection")
    bundle.add_action("color_map")
    return bundle
