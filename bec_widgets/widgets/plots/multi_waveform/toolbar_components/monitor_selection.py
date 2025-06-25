from bec_lib.device import ReadoutPriority
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QStyledItemDelegate, QWidget

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import DeviceComboBoxAction, WidgetAction
from bec_widgets.utils.toolbars.bundles import ToolbarComponents
from bec_widgets.utils.toolbars.toolbar import ToolbarBundle
from bec_widgets.widgets.control.device_input.base_classes.device_input_base import BECDeviceFilter
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget


class NoCheckDelegate(QStyledItemDelegate):
    """To reduce space in combo boxes by removing the checkmark."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # Remove any check indicator
        option.checkState = Qt.Unchecked


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


class MultiWaveformSelectionToolbarBundle(ToolbarBundle):
    """
    A bundle of actions for a toolbar that selects motors.
    """

    def __init__(self, bundle_id="monitor_selection", target_widget=None, **kwargs):
        super().__init__(bundle_id=bundle_id, actions=[], **kwargs)
        self.target_widget = target_widget

        # Monitor Selection
        self.monitor = DeviceComboBox(
            device_filter=BECDeviceFilter.DEVICE, readout_priority_filter=ReadoutPriority.ASYNC
        )
        self.monitor.addItem("", None)
        self.monitor.setCurrentText("")
        self.monitor.setToolTip("Select Monitor")
        self.monitor.setItemDelegate(NoCheckDelegate(self.monitor))
        self.add_action("monitor", WidgetAction(widget=self.monitor, adjust_size=False))

        # Colormap Selection
        self.colormap_widget = BECColorMapWidget(cmap="plasma")
        self.add_action("color_map", WidgetAction(widget=self.colormap_widget, adjust_size=False))

        # Connect slots, a device will be connected upon change of any combobox
        self.monitor.currentTextChanged.connect(lambda: self.connect())
        self.colormap_widget.colormap_changed_signal.connect(self.change_colormap)

    @SafeSlot()
    def connect(self):
        monitor = self.monitor.currentText()

        if monitor != "":
            if monitor != self.target_widget.config.monitor:
                self.target_widget.monitor = monitor

    @SafeSlot(str)
    def change_colormap(self, colormap: str):
        self.target_widget.color_palette = colormap

    def cleanup(self):
        """
        Cleanup the toolbar bundle.
        """
        self.monitor.close()
        self.monitor.deleteLater()
