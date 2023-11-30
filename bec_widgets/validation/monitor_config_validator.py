from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError


class Signal(BaseModel):
    """
    Represents a signal in a plot configuration.

    Attributes:
        name (str): The name of the signal.
        entry (Optional[str]): The entry point of the signal, optional.
    """

    name: str
    entry: Optional[str] = Field(None, validate_default=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        devices = MonitorConfigValidator.devices
        # Check if device name provided
        if v is None:
            raise PydanticCustomError(
                "no_device_name", "Device name must be provided", dict(wrong_value=v)
            )

        # Check if device exists in BEC
        if v not in devices:
            raise PydanticCustomError(
                "no_device_bec",
                'Device "{wrong_value}" not found in current BEC session',
                dict(wrong_value=v),
            )

        device = devices.get(v)  # get the device to check if it has signals

        # Check if device have signals
        if not hasattr(device, "signals"):
            raise PydanticCustomError(
                "no_device_signals",
                'Device "{wrong_value}" do not have "signals" defined. Check device configuration.',
                dict(wrong_value=v),
            )

        return v

    @field_validator("entry")
    @classmethod
    def set_and_validate_entry(cls, v, values):
        devices = MonitorConfigValidator.devices

        # Get device name from values -> device is already validated
        device_name = values.data.get("name")
        if device_name is not None:
            device = getattr(devices, device_name, None)
        else:  # if device is not in bec than validator_name return None and entry validation is not executed
            return

        # Set entry based on hints if not provided
        if v is None and hasattr(device, "_hints"):
            v = next(
                iter(device._hints), device_name
            )  # TODO check if devices[device_name]._hints in not enough?
        elif v is None:
            v = device_name

        # Validate that the entry exists in device signals
        if v not in device.signals:
            raise PydanticCustomError(
                "no_entry_for_device",
                "Entry '{wrong_value}' not found in device '{device_name}' signals",
                dict(wrong_value=v, device_name=device_name),
            )

        return v


class PlotAxis(BaseModel):
    """
    Represents an axis (X or Y) in a plot configuration.

    Attributes:
        label (Optional[str]): The label for the axis.
        signals (List[Signal]): A list of signals to be plotted on this axis.
    """

    label: Optional[str]
    signals: List[Signal] = Field(default_factory=list)


class PlotConfig(BaseModel):
    """
    Configuration for a single plot.

    Attributes:
        plot_name (Optional[str]): Name of the plot.
        x (PlotAxis): Configuration for the X axis.
        y (PlotAxis): Configuration for the Y axis.
    """

    plot_name: Optional[str]
    x: PlotAxis = Field(...)
    y: PlotAxis = Field(...)

    @field_validator("x")
    def validate_x_signals(cls, v):
        if len(v.signals) != 1:
            raise PydanticCustomError(
                "no_entry_for_device",
                "There must be exactly one signal for x axis. Number of x signals: '{wrong_value}'",
                dict(wrong_value=v),
            )

        return v


class PlotSettings(BaseModel):
    """
    Global settings for plotting.

    Attributes:
        background_color (str): Color of the plot background.
        axis_width (Optional[int]): Width of the plot axes.
        axis_color (Optional[str]): Color of the plot axes.
        num_columns (int): Number of columns in the plot layout.
        colormap (str): Colormap to be used.
        scan_types (bool): Indicates if the configuration is for different scan types.
    """

    background_color: str
    axis_width: Optional[int] = 2
    axis_color: Optional[str] = None
    num_columns: int
    colormap: str
    scan_types: bool


class DeviceMonitorConfig(BaseModel):
    """
    Configuration model for the device monitor mode.

    Attributes:
        plot_settings (PlotSettings): Global settings for plotting.
        plot_data (List[PlotConfig]): List of plot configurations.
    """

    plot_settings: PlotSettings
    plot_data: List[PlotConfig]


class ScanModeConfig(BaseModel):
    """
    Configuration model for scan mode.

    Attributes:
        plot_settings (PlotSettings): Global settings for plotting.
        plot_data (Dict[str, List[PlotConfig]]): Dictionary of plot configurations,
                                                 keyed by scan type.
    """

    plot_settings: PlotSettings
    plot_data: Dict[str, List[PlotConfig]]


class MonitorConfigValidator:
    devices = None

    def __init__(self, devices):
        # self.device_manager = device_manager
        MonitorConfigValidator.devices = devices

    def validate_monitor_config(
        self, config_data: dict
    ) -> Union[DeviceMonitorConfig, ScanModeConfig]:
        """
        Validates the configuration data based on the provided schema.

        Args:
            config_data (dict): Configuration data to be validated.

        Returns:
            Union[DeviceMonitorConfig, ScanModeConfig]: Validated configuration object.

        Raises:
            ValidationError: If the configuration data does not conform to the schema.
        """
        if config_data["plot_settings"]["scan_types"]:
            validated_config = ScanModeConfig(**config_data)
        else:
            validated_config = DeviceMonitorConfig(**config_data)

        return validated_config
