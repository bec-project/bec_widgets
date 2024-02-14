from typing import Optional, Literal

import pyqtgraph as pg
import numpy as np
from pydantic import BaseModel, Field
from qtpy.QtWidgets import QWidget

from bec_widgets.utils import BECConnector, ConnectionConfig


class AxisConfig(BaseModel):
    title: Optional[str] = Field(None, description="The title of the axes.")
    x_label: Optional[str] = Field(None, description="The label for the x-axis.")
    y_label: Optional[str] = Field(None, description="The label for the y-axis.")
    x_scale: Literal["linear", "log"] = Field("linear", description="The scale of the x-axis.")
    y_scale: Literal["linear", "log"] = Field("linear", description="The scale of the y-axis.")
    x_lim: Optional[tuple] = Field(None, description="The limits of the x-axis.")
    y_lim: Optional[tuple] = Field(None, description="The limits of the y-axis.")
    x_grid: bool = Field(False, description="Show grid on the x-axis.")
    y_grid: bool = Field(False, description="Show grid on the y-axis.")


class WidgetConfig(ConnectionConfig):
    parent_figure_id: Optional[str] = Field(None, description="The parent figure of the plot.")

    # Coordinates in the figure
    row: int = Field(0, description="The row coordinate in the figure.")
    column: int = Field(0, description="The column coordinate in the figure.")

    # Appearance settings
    axis: AxisConfig = Field(
        default_factory=AxisConfig, description="The axis configuration of the plot."
    )


class BECPlotBase(BECConnector, pg.PlotItem):
    USER_ACCESS = [
        "set",
        "set_title",
        "set_x_label",
        "set_y_label",
        "set_x_scale",
        "set_y_scale",
        "set_x_lim",
        "set_y_lim",
        "plot",
    ]

    def __init__(
        self,
        parent: Optional[QWidget] = None,  # TODO decide if needed for this class
        config: Optional[WidgetConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
    ):
        if config is None:
            config = WidgetConfig(widget_class=self.__class__.__name__)
        super().__init__(client=client, config=config, gui_id=gui_id)
        pg.PlotItem.__init__(self, parent)

    def set(self, **kwargs) -> None:
        """
        Set the properties of the plot widget.
        Args:
            **kwargs: Keyword arguments for the properties to be set.
        Possible properties:
            - title: str
            - x_label: str
            - y_label: str
            - x_scale: Literal["linear", "log"]
            - y_scale: Literal["linear", "log"]
            - x_lim: tuple
            - y_lim: tuple
        """

        # Mapping of keywords to setter methods
        method_map = {
            "title": self.set_title,
            "x_label": self.set_x_label,
            "y_label": self.set_y_label,
            "x_scale": self.set_x_scale,
            "y_scale": self.set_y_scale,
            "x_lim": self.set_x_lim,
            "y_lim": self.set_y_lim,
        }
        for key, value in kwargs.items():
            if key in method_map:
                method_map[key](value)
            else:
                print(f"Warning: '{key}' is not a recognized property.")

    def apply_axis_config(self):
        """Apply the axis configuration to the plot widget."""
        config_mappings = {
            "title": self.config.axis.title,
            "x_label": self.config.axis.x_label,
            "y_label": self.config.axis.y_label,
            "x_scale": self.config.axis.x_scale,
            "y_scale": self.config.axis.y_scale,
        }

        self.set(**{k: v for k, v in config_mappings.items() if v is not None})

    def set_title(self, title: str):
        """
        Set the title of the plot widget.
        Args:
            title(str): Title of the plot widget.
        """
        self.plt.setTitle(title)
        self.config.axis.title = title

    def set_x_label(self, label: str):
        """
        Set the label of the x-axis.
        Args:
            label(str): Label of the x-axis.
        """
        self.plt.setLabel("bottom", label)
        self.config.axis.x_label = label

    def set_y_label(self, label: str):
        """
        Set the label of the y-axis.
        Args:
            label(str): Label of the y-axis.
        """
        self.plt.setLabel("left", label)
        self.config.axis.y_label = label

    def set_x_scale(self, scale: Literal["linear", "log"] = "linear"):
        """
        Set the scale of the x-axis.
        Args:
            scale(Literal["linear", "log"]): Scale of the x-axis.
        """
        self.plt.setLogMode(x=(scale == "log"))
        self.config.axis.x_scale = scale

    def set_y_scale(self, scale: Literal["linear", "log"] = "linear"):
        """
        Set the scale of the y-axis.
        Args:
            scale(Literal["linear", "log"]): Scale of the y-axis.
        """
        self.plt.setLogMode(y=(scale == "log"))
        self.config.axis.y_scale = scale

    def set_x_lim(self, x_lim: tuple) -> None:
        """
        Set the limits of the x-axis.
        Args:
            x_lim(tuple): Limits of the x-axis.
        """
        self.plt.setXRange(x_lim[0], x_lim[1])
        self.config.axis.x_lim = x_lim

    def set_y_lim(self, y_lim: tuple) -> None:
        """
        Set the limits of the y-axis.
        Args:
            y_lim(tuple): Limits of the y-axis.
        """
        self.plt.setYRange(y_lim[0], y_lim[1])
        self.config.axis.y_lim = y_lim

    def set_grid(self, x: bool = False, y: bool = False):
        """
        Set the grid of the plot widget.
        Args:
            x(bool): Show grid on the x-axis.
            y(bool): Show grid on the y-axis.
        """
        self.plt.showGrid(x, y)
        self.config.axis.x_grid = x
        self.config.axis.y_grid = y

    def plot_data(self, data_x: list | np.ndarray, data_y: list | np.ndarray, label: str = None):
        """
        Plot custom data on the plot widget. These data are not saved in config.
        Args:
            data_x(list|np.ndarray): x-axis data
            data_y(list|np.ndarray): y-axis data
            label(str): label of the plot
        """
        self.plot(data_x, data_y, name=label)
