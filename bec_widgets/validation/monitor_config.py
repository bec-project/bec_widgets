from pydantic import BaseModel, Field, ValidationError
from typing import List, Dict, Union, Optional


class Signal(BaseModel):
    name: str
    entry: Optional[str]


class PlotAxis(BaseModel):
    label: Optional[str]
    signals: List[Signal]


class PlotConfig(BaseModel):
    plot_name: Optional[str]
    x: PlotAxis
    y: PlotAxis


class PlotSettings(BaseModel):
    background_color: str
    num_columns: int
    colormap: str
    scan_types: bool


class DeviceMonitorConfig(BaseModel):
    plot_settings: PlotSettings
    plot_data: List[PlotConfig]


class ScanModeConfig(BaseModel):
    plot_settings: PlotSettings
    plot_data: Dict[str, List[PlotConfig]]


def validate_config(config_data: dict) -> Union[DeviceMonitorConfig, ScanModeConfig]:
    if config_data["plot_settings"]["scan_types"]:
        return ScanModeConfig(**config_data)
    else:
        return DeviceMonitorConfig(**config_data)
