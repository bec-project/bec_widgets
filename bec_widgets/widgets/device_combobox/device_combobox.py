from bec_lib.device import ReadoutPriority
from qtpy.QtCore import QSize
from qtpy.QtWidgets import QComboBox, QSizePolicy

from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.widgets.base_classes.device_input_base import (
    BECDeviceFilter,
    DeviceInputBase,
    DeviceInputConfig,
)


class DeviceComboBox(DeviceInputBase, QComboBox):
    """
    Combobox widget for device input with autocomplete for device names.

    Args:
        parent: Parent widget.
        client: BEC client object.
        config: Device input configuration.
        gui_id: GUI ID.
        device_filter: Device filter, name of the device class from BECDeviceFilter and BECReadoutPriority. Check DeviceInputBase for more details.
        default: Default device name.
        arg_name: Argument name, can be used for the other widgets which has to call some other function in bec using correct argument names.
    """

    ICON_NAME = "list_alt"

    def __init__(
        self,
        parent=None,
        client=None,
        config: DeviceInputConfig = None,
        gui_id: str | None = None,
        device_filter: BECDeviceFilter | list[BECDeviceFilter] | None = None,
        readout_priority_filter: (
            str | ReadoutPriority | list[str] | list[ReadoutPriority] | None
        ) = None,
        device_list: list[str] | None = None,
        default: str | None = None,
        arg_name: str | None = None,
    ):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QComboBox.__init__(self, parent=parent)
        if arg_name is not None:
            self.config.arg_name = arg_name
            self.arg_name = arg_name
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumSize(QSize(100, 0))
        self._is_valid_input = False
        self._accent_colors = get_accent_colors()
        # Set readout priority filter and device filter.
        # If value is set directly in init, this overrules value from the config
        readout_priority_filter = (
            readout_priority_filter
            if readout_priority_filter is not None
            else self.config.readout_filter
        )
        if readout_priority_filter is not None:
            self.set_readout_priority_filter(readout_priority_filter)
        device_filter = device_filter if device_filter is not None else self.config.device_filter
        if device_filter is not None:
            self.set_device_filter(device_filter)
        device_list = device_list if device_list is not None else self.config.devices
        if device_list is not None:
            self.set_available_devices(device_list)
        else:
            self.update_devices_from_filters()
        default = default if default is not None else self.config.default
        if default is not None:
            self.set_device(default)

    def get_current_device(self) -> object:
        """
        Get the current device object based on the current value.

        Returns:
            object: Device object, can be device of type Device, Positioner, Signal or ComputedSignal.
        """
        dev_name = self.currentText()
        return self.get_device_object(dev_name)


if __name__ == "__main__":  # pragma: no cover
    # pylint: disable=import-outside-toplevel
    from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

    from bec_widgets.utils.colors import set_theme

    app = QApplication([])
    set_theme("dark")
    widget = QWidget()
    widget.setFixedSize(200, 200)
    layout = QVBoxLayout()
    widget.setLayout(layout)
    combo = DeviceComboBox()
    layout.addWidget(combo)
    widget.show()
    app.exec_()
