from typing import TYPE_CHECKING

from qtpy.QtWidgets import QCompleter, QLineEdit

from bec_widgets.widgets.device_inputs.device_input_base import DeviceInputBase, DeviceInputConfig

if TYPE_CHECKING:
    from bec_widgets.widgets.device_inputs.device_input_base import DeviceInputConfig


class DeviceLineEdit(DeviceInputBase, QLineEdit):
    def __init__(
        self,
        parent=None,
        client=None,
        config: DeviceInputConfig = None,
        gui_id: str | None = None,
        device_filter: str | list[str] = None,
        default_device: str = None,
    ):
        QLineEdit.__init__(self, parent=parent)
        DeviceInputBase.__init__(
            self,
            client=client,
            config=config,
            gui_id=gui_id,
            device_filter=device_filter,
            default_device=default_device,
        )

        self.completer = QCompleter(self)
        self.setCompleter(self.completer)

        self.populate_completer()
        self._set_defaults()

    def _set_defaults(self):
        """Set the default device and device filter."""
        if self.config.default_device is not None:
            self.set_default_device(self.config.default_device)
        if self.config.device_filter is not None:
            self.set_device_filter(self.config.device_filter)

    def set_device_filter(self, device_filter: str | list[str]):
        """
        Set the device filter.

        Args:
            device_filter (str | list[str]): Device filter, name of the device class.
        """
        super().set_device_filter(device_filter)
        self.populate_completer()

    def set_default_device(self, default_device: str):
        """
        Set the default device.

        Args:
            default_device (str): Default device name.
        """
        super().set_default_device(default_device)
        self.setText(default_device)

    def populate_completer(self):
        """Populate the completer with the devices."""
        self.devices = self.get_device_list(self.config.device_filter)
        self.completer.setModel(self.create_completer_model(self.devices))

    def create_completer_model(self, devices: list[str]):
        """Create a model for the completer."""
        from qtpy.QtCore import QStringListModel

        return QStringListModel(devices, self)

    def get_device(self) -> object:
        """
        Get the selected device object.

        Returns:
            object: Device object.
        """
        device_name = self.text()
        device_obj = getattr(self.dev, device_name.lower(), None)
        if device_obj is None:
            raise ValueError(f"Device {device_name} is not found.")
        return device_obj


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = DeviceLineEdit(default_device="samx")
    w.show()
    sys.exit(app.exec_())
