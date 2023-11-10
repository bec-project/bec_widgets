from pydantic import BaseModel, Field, ValidationError
from typing import List, Dict, Union, Optional


class Signal(BaseModel):
    """
    Represents a signal in a plot configuration.

    Attributes:
        name (str): The name of the signal.
        entry (Optional[str]): The entry point of the signal, optional.
    """

    name: str
    entry: Optional[str]


class PlotAxis(BaseModel):
    """
    Represents an axis (X or Y) in a plot configuration.

    Attributes:
        label (Optional[str]): The label for the axis.
        signals (List[Signal]): A list of signals to be plotted on this axis.
    """

    label: Optional[str]
    signals: List[Signal]


class PlotConfig(BaseModel):
    """
    Configuration for a single plot.

    Attributes:
        plot_name (Optional[str]): Name of the plot.
        x (PlotAxis): Configuration for the X axis.
        y (PlotAxis): Configuration for the Y axis.
    """

    plot_name: Optional[str]
    x: PlotAxis
    y: PlotAxis


class PlotSettings(BaseModel):
    """
    Global settings for plotting.

    Attributes:
        background_color (str): Color of the plot background.
        num_columns (int): Number of columns in the plot layout.
        colormap (str): Colormap to be used.
        scan_types (bool): Indicates if the configuration is for different scan types.
    """

    background_color: str
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


def validate_config(config_data: dict) -> Union[DeviceMonitorConfig, ScanModeConfig]:
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
        return ScanModeConfig(**config_data)
    else:
        return DeviceMonitorConfig(**config_data)
