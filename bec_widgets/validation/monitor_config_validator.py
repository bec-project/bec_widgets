from typing import List, Dict, Union, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
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

    @model_validator(mode="before")
    @classmethod
    def validate_fields(cls, values):
        """Validate the fields of the model.
        First validate the 'name' field, then validate the 'entry' field.
        Args:
            values (dict): The values to be validated."""
        devices = MonitorConfigValidator.devices

        # Validate 'name'
        name = values.get("name")

        # Check if device name provided
        if name is None:
            raise PydanticCustomError(
                "no_device_name", "Device name must be provided", {"wrong_value": name}
            )
        # Check if device exists in BEC
        if name not in devices:
            raise PydanticCustomError(
                "no_device_bec",
                'Device "{wrong_value}" not found in current BEC session',
                {"wrong_value": name},
            )

        device = devices[name]  # get the device to check if it has signals

        # Check if device have signals
        if not hasattr(device, "signals"):
            raise PydanticCustomError(
                "no_device_signals",
                'Device "{wrong_value}" does not have "signals" defined. Check device configuration.',
                {"wrong_value": name},
            )

        # Validate 'entry'
        entry = values.get("entry")

        # Set entry based on hints if not provided
        if entry is None:
            entry = next(iter(device._hints), name) if hasattr(device, "_hints") else name
        if entry not in device.signals:
            raise PydanticCustomError(
                "no_entry_for_device",
                'Entry "{wrong_value}" not found in device "{device_name}" signals',
                {"wrong_value": entry, "device_name": name},
            )

        values["entry"] = entry
        return values


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
    @classmethod
    def validate_x_signals(cls, v):
        if len(v.signals) != 1:
            raise PydanticCustomError(
                "x_axis_multiple_signals",
                'There must be exactly one signal for x axis. Number of x signals: "{wrong_value}"',
                {"wrong_value": v},
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
    """Validates the configuration data for the BECMonitor."""

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
