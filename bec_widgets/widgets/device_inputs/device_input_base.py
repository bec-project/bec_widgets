from __future__ import annotations

from bec_widgets.utils import BECConnector, ConnectionConfig


class DeviceInputConfig(ConnectionConfig):
    device_filter: str | list[str] | None = None
    default: str | None = None
    arg_name: str | None = None


class DeviceInputBase(BECConnector):
    """
    Mixin class for device input widgets. This class provides methods to get the device list and device object based
    on the current text of the widget.
    """

    def __init__(self, client=None, config=None, gui_id=None):
        if config is None:
            config = DeviceInputConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = DeviceInputConfig(**config)
            self.config = config
        super().__init__(client=client, config=config, gui_id=gui_id)

        self.get_bec_shortcuts()
        self._devices = []

    @property
    def devices(self) -> list[str]:
        """
        Get the list of devices.

        Returns:
            list[str]: List of devices.
        """
        return self._devices

    @devices.setter
    def devices(self, value: list[str]):
        """
        Set the list of devices.

        Args:
            value: List of devices.
        """
        self._devices = value

    def set_device_filter(self, device_filter: str | list[str]):
        """
        Set the device filter.

        Args:
            device_filter(str): Device filter, name of the device class.
        """
        self.validate_device_filter(device_filter)
        self.config.device_filter = device_filter

    def set_default_device(self, default_device: str):
        """
        Set the default device.

        Args:
            default_device(str): Default device name.
        """
        self.validate_device(default_device)
        self.config.default = default_device

    def get_device_list(self, filter: str | list[str] | None = None) -> list[str]:
        """
        Get the list of device names based on the filter of current BEC client.

        Args:
            filter(str|None): Class name filter to apply on the device list.

        Returns:
            devices(list[str]): List of device names.
        """
        all_devices = self.dev.enabled_devices
        if filter is not None:
            self.validate_device_filter(filter)
            if isinstance(filter, str):
                filter = [filter]
            devices = [device.name for device in all_devices if device.__class__.__name__ in filter]
        else:
            devices = [device.name for device in all_devices]
        return devices

    def get_available_filters(self):
        """
        Get the available device classes which can be used as filters.
        """
        all_devices = self.dev.enabled_devices
        filters = {device.__class__.__name__ for device in all_devices}
        return filters

    def validate_device_filter(self, filter: str | list[str]) -> None:
        """
        Validate the device filter if the class name is present in the current BEC instance.

        Args:
            filter(str|list[str]): Class name to use as a device filter.
        """
        if isinstance(filter, str):
            filter = [filter]
        available_filters = self.get_available_filters()
        for f in filter:
            if f not in available_filters:
                raise ValueError(f"Device filter {f} is not valid.")

    def validate_device(self, device: str) -> None:
        """
        Validate the device if it is present in current BEC instance.

        Args:
            device(str): Device to validate.
        """
        if device not in self.get_device_list(self.config.device_filter):
            raise ValueError(f"Device {device} is not valid.")

    def cleanup(self):
        super().cleanup()
