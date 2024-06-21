from typing import TYPE_CHECKING

from qtpy.QtWidgets import QComboBox

from bec_widgets.widgets.device_inputs.device_input_base import DeviceInputBase, DeviceInputConfig

if TYPE_CHECKING:
    from bec_widgets.widgets.device_inputs.device_input_base import DeviceInputConfig


class DeviceComboBox(DeviceInputBase, QComboBox):
    """
    Line edit widget for device input with autocomplete for device names.

    Args:
        parent: Parent widget.
        client: BEC client object.
        config: Device input configuration.
        gui_id: GUI ID.
        device_filter: Device filter, name of the device class.
        default: Default device name.
        arg_name: Argument name, can be used for the other widgets which has to call some other function in bec using correct argument names.
    """

    def __init__(
        self,
        parent=None,
        client=None,
        config: DeviceInputConfig = None,
        gui_id: str | None = None,
        device_filter: str | None = None,
        default: str | None = None,
        arg_name: str | None = None,
    ):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QComboBox.__init__(self, parent=parent)

        self.populate_combobox()

        if arg_name is not None:
            self.config.arg_name = arg_name
        if device_filter is not None:
            self.set_device_filter(device_filter)
        if default is not None:
            self.set_default_device(default)

    def set_device_filter(self, device_filter: str):
        """
        Set the device filter.

        Args:
            device_filter(str): Device filter, name of the device class.
        """
        super().set_device_filter(device_filter)
        self.populate_combobox()

    def set_default_device(self, default_device: str):
        """
        Set the default device.

        Args:
            default_device(str): Default device name.
        """
        super().set_default_device(default_device)
        self.setCurrentText(default_device)

    def populate_combobox(self):
        """Populate the combobox with the devices."""
        self.devices = self.get_device_list(self.config.device_filter)
        self.clear()
        self.addItems(self.devices)

    def get_device(self) -> object:
        """
        Get the selected device object.

        Returns:
            object: Device object.
        """
        device_name = self.currentText()
        device_obj = getattr(self.dev, device_name.lower(), None)
        if device_obj is None:
            raise ValueError(f"Device {device_name} is not found.")
        return device_obj

    def cleanup(self):
        """Cleanup the widget."""
        super().cleanup()

    def closeEvent(self, event):
        super().cleanup()
        QComboBox().closeEvent(event)
