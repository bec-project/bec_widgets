from typing import Optional, Union, Literal

from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError
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

        # Get device description
        description = device.describe()

        # Validate 'entry'
        entry = values.get("entry")

        # Set entry based on hints if not provided
        if entry is None:
            entry = next(iter(device._hints), name) if hasattr(device, "_hints") else name
        if entry not in description:
            raise PydanticCustomError(
                "no_entry_for_device",
                'Entry "{wrong_value}" not found in device "{device_name}" signals',
                {"wrong_value": entry, "device_name": name},
            )

        values["entry"] = entry
        return values


class AxisSignal(BaseModel):
    """
    Configuration signal axis for a single plot.
    Attributes:
        x (list): Signal for the X axis.
        y (list): Signals for the Y axis.
    """

    x: list[Signal] = Field(default_factory=list)
    y: list[Signal] = Field(default_factory=list)

    @field_validator("x")
    @classmethod
    def validate_x_signals(cls, v):
        """Ensure that there is only one signal for x-axis."""
        if len(v) != 1:
            raise PydanticCustomError(
                "x_axis_multiple_signals",
                'There must be exactly one signal for x axis. Number of x signals: "{wrong_value}"',
                {"wrong_value": v},
            )

        return v


class SourceHistoryValidator(BaseModel):
    """History source validator
    Attributes:
        type (str): type of source - history
        scanID (str): Scan ID for history source.
        signals (list): Signal for the source.
    """

    type: Literal["history"]
    scanID: str  # TODO can be validated if it is a valid scanID
    signals: AxisSignal


class SourceSegmentValidator(BaseModel):
    """Scan Segment source validator
    Attributes:
        type (str): type of source - scan_segment
        signals (AxisSignal): Signal for the source.
    """

    type: Literal["scan_segment"]
    signals: AxisSignal


class SourceRedisValidator(BaseModel):
    """Scan Segment source validator
    Attributes:
        type (str): type of source - scan_segment
        endpoint (str): Endpoint reference in redis.
        update (str): Update type.
    """

    type: Literal["redis"]
    endpoint: str
    update: str
    signals: dict


class Source(BaseModel):  # TODO decide if it should stay for general Source validation
    """
    General source validation, includes all Optional arguments of all other sources.
    Attributes:
        type (list): type of source (scan_segment, history)
        scanID (Optional[str]): Scan ID for history source.
        signals (Optional[AxisSignal]): Signal for the source.
    """

    type: Literal["scan_segment", "history", "redis"]
    scanID: Optional[str] = None
    signals: Optional[dict] = None


class PlotConfig(BaseModel):
    """
    Configuration for a single plot.

    Attributes:
        plot_name (Optional[str]): Name of the plot.
        x_label (Optional[str]): The label for the x-axis.
        y_label (Optional[str]): The label for the y-axis.
        sources (list): A list of sources to be plotted on this axis.
    """

    plot_name: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    sources: list = Field(default_factory=list)

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, values):
        """Validate the sources of the plot configuration, based on the type of source."""
        validated_sources = []
        for source in values:
            # Check if source type is supported
            Source(**source)
            source_type = source.get("type", None)

            # Validate source based on type
            if source_type == "scan_segment":
                validated_sources.append(SourceSegmentValidator(**source))
            elif source_type == "history":
                validated_sources.append(SourceHistoryValidator(**source))
            elif source_type == "redis":
                validated_sources.append(SourceRedisValidator(**source))
        return validated_sources


class PlotSettings(BaseModel):
    """
    Global settings for plotting affecting mostly visuals.

    Attributes:
        background_color (str): Color of the plot background.
        axis_width (Optional[int]): Width of the plot axes.
        axis_color (Optional[str]): Color of the plot axes.
        num_columns (int): Number of columns in the plot layout.
        colormap (str): Colormap to be used.
        scan_types (bool): Indicates if the configuration is for different scan types.
    """

    background_color: Literal["black", "white"] = "black"
    axis_width: Optional[int] = 2
    axis_color: Optional[str] = None
    num_columns: Optional[int] = 1
    colormap: Optional[str] = "magma"
    scan_types: Optional[bool] = False


class DeviceMonitorConfig(BaseModel):
    """
    Configuration model for the device monitor mode.

    Attributes:
        plot_settings (PlotSettings): Global settings for plotting.
        plot_data (list[PlotConfig]): List of plot configurations.
    """

    plot_settings: PlotSettings
    plot_data: list[PlotConfig]


class ScanModeConfig(BaseModel):
    """
    Configuration model for scan mode.

    Attributes:
        plot_settings (PlotSettings): Global settings for plotting.
        plot_data (dict[str, list[PlotConfig]]): Dictionary of plot configurations,
                                                 keyed by scan type.
    """

    plot_settings: PlotSettings
    plot_data: dict[str, list[PlotConfig]]


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
        config_type = config_data.get("plot_settings", {}).get("scan_types", False)
        if config_type:
            validated_config = ScanModeConfig(**config_data)
        else:
            validated_config = DeviceMonitorConfig(**config_data)

        return validated_config
