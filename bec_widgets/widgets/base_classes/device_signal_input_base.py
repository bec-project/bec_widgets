import enum

from bec_lib.logger import bec_logger
from qtpy.QtCore import Property, Slot

from bec_widgets.utils import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.filter_io import FilterIO
from bec_widgets.utils.widget_io import WidgetIO

logger = bec_logger.logger


class BECSignalFilter(str, enum.Enum):
    """Filter for the device signals."""

    HINTED = "5"
    NORMAL = "1"
    CONFIG = "2"


class DeviceSignalInputBaseConfig(ConnectionConfig):
    """Configuration class for DeviceSignalInputBase."""

    signal_filter: str | list[str] | None = None
    default: str | None = None
    arg_name: str | None = None
    device: str | None = None
    signals: list[str] | None = None


class DeviceSignalInputBase(BECWidget):
    """
    Mixin base class for device signal input widgets.
    Mixin class for device signal input widgets. This class provides methods to get the device signal list and device
    signal object based on the current text of the widget.
    """

    _filter_handler = {
        BECSignalFilter.HINTED: "include_hinted_signals",
        BECSignalFilter.NORMAL: "include_normal_signals",
        BECSignalFilter.CONFIG: "include_config_signals",
    }

    def __init__(self, client=None, config=None, gui_id: str = None):
        if config is None:
            config = DeviceSignalInputBaseConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = DeviceSignalInputBaseConfig(**config)
            self.config = config
        super().__init__(client=client, config=config, gui_id=gui_id)

        self._device = None
        self.get_bec_shortcuts()
        self._signal_filter = []
        self._signals = []
        self._hinted_signals = []
        self._normal_signals = []
        self._config_signals = []

    ### Qt Slots ###

    @Slot(str)
    def set_signal(self, signal: str):
        """
        Set the signal.

        Args:
            signal (str): signal name.
        """
        if self.validate_signal(signal, raise_on_false=False) is True:
            WidgetIO.set_value(widget=self, value=signal)
            self.config.default = signal
        else:
            logger.warning(
                f"Signal {signal} not found for device {self.device} and filtered selection {self.signal_filter}."
            )

    @Slot(str)
    def set_device(self, device: str | None):
        """
        Set the device.

        Args:
            device(str): device name.
        """
        if device is None:
            self._device = None
        if self.validate_device(device, raise_on_false=False) is True:
            self._device = device
            self.update_signals_from_filters()
        else:
            logger.warning(f"Device {device} not found in device_manager.")

    @Slot()
    def update_signals_from_filters(self):
        """Update the filters for the device signals based on list in self.signal_filter.
        In addition, store the hinted, normal and config signals in separate lists to allow
        customisation within QLineEdit."""
        self.config.signal_filter = self.signal_filter
        # pylint: disable=protected-access
        self._hinted_signals = []
        self._normal_signals = []
        self._config_signals = []
        if self._device is None:
            return
        device = self.get_device_object(self._device)
        device_info = device._info["signals"]
        if BECSignalFilter.HINTED in self.signal_filter or len(self.signal_filter) == 0:
            hinted_signals = [
                signal
                for signal, signal_info in device_info.items()
                if (signal_info.get("kind_str", None) == BECSignalFilter.HINTED)
            ]
            self._hinted_signals = hinted_signals
        if BECSignalFilter.NORMAL in self.signal_filter or len(self.signal_filter) == 0:
            normal_signals = [
                signal
                for signal, signal_info in device_info.items()
                if (signal_info.get("kind_str", None) == BECSignalFilter.NORMAL)
            ]
            self._normal_signals = normal_signals
        if BECSignalFilter.CONFIG in self.signal_filter or len(self.signal_filter) == 0:
            config_signals = [
                signal
                for signal, signal_info in device_info.items()
                if (signal_info.get("kind_str", None) == BECSignalFilter.CONFIG)
            ]
            self._config_signals = config_signals
        self._signals = self._hinted_signals + self._normal_signals + self._config_signals
        FilterIO.set_selection(widget=self, selection=self.signals)

    ### Qt Properties ###

    @Property(str)
    def device(self) -> str:
        """Get the selected device."""
        if self._device is None:
            return ""
        return self._device

    @device.setter
    def device(self, value: str):
        """Set the device and update the filters, only allow devices present in the devicemanager."""
        if self.validate_device(value) is False:
            return
        self._device = value
        self.config.device = value
        self.update_signals_from_filters()

    @Property(bool)
    def include_hinted_signals(self):
        """Include hinted signals in filters."""
        return BECSignalFilter.HINTED in self.signal_filter

    @include_hinted_signals.setter
    def include_hinted_signals(self, value: bool):
        if value:
            self._signal_filter.append(BECSignalFilter.HINTED)
        else:
            self._signal_filter.remove(BECSignalFilter.HINTED)
        self.update_signals_from_filters()

    @Property(bool)
    def include_normal_signals(self):
        """Include normal signals in filters."""
        return BECSignalFilter.NORMAL in self.signal_filter

    @include_normal_signals.setter
    def include_normal_signals(self, value: bool):
        if value:
            self._signal_filter.append(BECSignalFilter.NORMAL)
        else:
            self._signal_filter.remove(BECSignalFilter.NORMAL)
        self.update_signals_from_filters()

    @Property(bool)
    def include_config_signals(self):
        """Include config signals in filters."""
        return BECSignalFilter.CONFIG in self.signal_filter

    @include_config_signals.setter
    def include_config_signals(self, value: bool):
        if value:
            self._signal_filter.append(BECSignalFilter.CONFIG)
        else:
            self._signal_filter.remove(BECSignalFilter.CONFIG)
        self.update_signals_from_filters()

    ### Properties and Methods ###

    @property
    def signals(self) -> list[str]:
        """
        Get the list of device signals for the applied filters.

        Returns:
            list[str]: List of device signals.
        """
        return self._signals

    @signals.setter
    def signals(self, value: list[str]):
        self._signals = value
        self.config.signals = value
        FilterIO.set_selection(widget=self, selection=value)

    @property
    def signal_filter(self) -> list[str]:
        """Get the list of filters to apply on the device signals."""
        return self._signal_filter

    def get_available_filters(self) -> list[str]:
        """Get the available filters."""
        return [entry for entry in self._filter_handler]

    def set_filter(self, filter_selection: str | list[str]):
        """
        Set the device filter. If None, all devices are included.

        Args:
            filter_selection (str | list[str]): Device filters from BECDeviceFilter and BECReadoutPriority.
        """
        filters = None
        if isinstance(filter_selection, list):
            filters = [self._filter_handler.get(entry) for entry in filter_selection]
        if isinstance(filter_selection, str):
            filters = [self._filter_handler.get(filter_selection)]
        if filters is None:
            return
        for entry in filters:
            setattr(self, entry, True)

    def get_device_object(self, device: str) -> object:
        """
        Get the device object based on the device name.

        Args:
            device(str): Device name.

        Returns:
            object: Device object, can be device of type Device, Positioner, Signal or ComputedSignal.
        """
        self.validate_device(device)
        dev = getattr(self.dev, device.lower(), None)
        if dev is None:
            raise ValueError(f"Device {device} is not found in devicemanager {self.dev}.")
        return dev

    def validate_device(self, device: str, raise_on_false: bool = False) -> bool:
        """
        Validate the device if it is present in current BEC instance.

        Args:
            device(str): Device to validate.
        """
        if device in self.dev:
            return True
        if raise_on_false is True:
            raise ValueError(f"Device {device} not found in devicemanager.")
        return False

    def validate_signal(self, signal: str, raise_on_false: bool = False) -> bool:
        """
        Validate the signal if it is present in the device signals.

        Args:
            signal(str): Signal to validate.
        """
        if signal in self.signals:
            return True
        if raise_on_false is True:
            raise ValueError(
                f"Signal {signal} not found for device {self.device} and filtered selection {self.signal_filter}."
            )
        return False
