from __future__ import annotations

from typing import Literal, Optional

import pyqtgraph as pg
from pydantic import BaseModel, Field
from qtpy.QtWidgets import QWidget

from bec_widgets.utils import BECConnector, ConnectionConfig


class AxisConfig(BaseModel):
    title: Optional[str] = Field(None, description="The title of the axes.")
    title_size: Optional[int] = Field(None, description="The font size of the title.")
    x_label: Optional[str] = Field(None, description="The label for the x-axis.")
    x_label_size: Optional[int] = Field(None, description="The font size of the x-axis label.")
    y_label: Optional[str] = Field(None, description="The label for the y-axis.")
    y_label_size: Optional[int] = Field(None, description="The font size of the y-axis label.")
    legend_label_size: Optional[int] = Field(
        None, description="The font size of the legend labels."
    )
    x_scale: Literal["linear", "log"] = Field("linear", description="The scale of the x-axis.")
    y_scale: Literal["linear", "log"] = Field("linear", description="The scale of the y-axis.")
    x_lim: Optional[tuple] = Field(None, description="The limits of the x-axis.")
    y_lim: Optional[tuple] = Field(None, description="The limits of the y-axis.")
    x_grid: bool = Field(False, description="Show grid on the x-axis.")
    y_grid: bool = Field(False, description="Show grid on the y-axis.")
    model_config: dict = {"validate_assignment": True}


class SubplotConfig(ConnectionConfig):
    parent_id: Optional[str] = Field(None, description="The parent figure of the plot.")

    # Coordinates in the figure
    row: int = Field(0, description="The row coordinate in the figure.")
    col: int = Field(0, description="The column coordinate in the figure.")

    # Appearance settings
    axis: AxisConfig = Field(
        default_factory=AxisConfig, description="The axis configuration of the plot."
    )


class BECPlotBase(BECConnector, pg.GraphicsLayout):
    USER_ACCESS = [
        "_config_dict",
        "set",
        "set_title",
        "set_x_label",
        "set_y_label",
        "set_x_scale",
        "set_y_scale",
        "set_x_lim",
        "set_y_lim",
        "set_grid",
        "lock_aspect_ratio",
        "export",
        "remove",
        "set_legend_label_size",
    ]

    def __init__(
        self,
        parent: Optional[QWidget] = None,  # TODO decide if needed for this class
        parent_figure=None,
        config: Optional[SubplotConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
    ):
        if config is None:
            config = SubplotConfig(widget_class=self.__class__.__name__)
        super().__init__(client=client, config=config, gui_id=gui_id)
        pg.GraphicsLayout.__init__(self, parent)

        self.figure = parent_figure
        self.plot_item = self.addPlot(row=0, col=0)

        self.add_legend()

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
            - legend_label_size: int
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
            "legend_label_size": self.set_legend_label_size,
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
            "x_lim": self.config.axis.x_lim,
            "y_lim": self.config.axis.y_lim,
        }

        self.set(**{k: v for k, v in config_mappings.items() if v is not None})

    def set_legend_label_size(self, size: int = None):
        """
        Set the font size of the legend.

        Args:
            size(int): Font size of the legend.
        """
        if not self.plot_item.legend:
            return
        if self.config.axis.legend_label_size or size:
            if size:
                self.config.axis.legend_label_size = size
                scale = (
                    size / 9
                )  # 9 is the default font size of the legend, so we always scale it against 9
                self.plot_item.legend.setScale(scale)

    def get_text_color(self):
        return "#FFF" if self.figure.config.theme == "dark" else "#000"

    def set_title(self, title: str, size: int = None):
        """
        Set the title of the plot widget.

        Args:
            title(str): Title of the plot widget.
            size(int): Font size of the title.
        """
        if self.config.axis.title_size or size:
            if size:
                self.config.axis.title_size = size
            style = {"color": self.get_text_color(), "size": f"{self.config.axis.title_size}pt"}
        else:
            style = {}
        self.plot_item.setTitle(title, **style)
        self.config.axis.title = title

    def set_x_label(self, label: str, size: int = None):
        """
        Set the label of the x-axis.

        Args:
            label(str): Label of the x-axis.
            size(int): Font size of the label.
        """
        if self.config.axis.x_label_size or size:
            if size:
                self.config.axis.x_label_size = size
            style = {
                "color": self.get_text_color(),
                "font-size": f"{self.config.axis.x_label_size}pt",
            }
        else:
            style = {}
        self.plot_item.setLabel("bottom", label, **style)
        self.config.axis.x_label = label

    def set_y_label(self, label: str, size: int = None):
        """
        Set the label of the y-axis.

        Args:
            label(str): Label of the y-axis.
            size(int): Font size of the label.
        """
        if self.config.axis.y_label_size or size:
            if size:
                self.config.axis.y_label_size = size
            color = self.get_text_color()
            style = {"color": color, "font-size": f"{self.config.axis.y_label_size}pt"}
        else:
            style = {}
        self.plot_item.setLabel("left", label, **style)
        self.config.axis.y_label = label

    def set_x_scale(self, scale: Literal["linear", "log"] = "linear"):
        """
        Set the scale of the x-axis.

        Args:
            scale(Literal["linear", "log"]): Scale of the x-axis.
        """
        self.plot_item.setLogMode(x=(scale == "log"))
        self.config.axis.x_scale = scale

    def set_y_scale(self, scale: Literal["linear", "log"] = "linear"):
        """
        Set the scale of the y-axis.

        Args:
            scale(Literal["linear", "log"]): Scale of the y-axis.
        """
        self.plot_item.setLogMode(y=(scale == "log"))
        self.config.axis.y_scale = scale

    def set_x_lim(self, *args) -> None:
        """
        Set the limits of the x-axis. This method can accept either two separate arguments
        for the minimum and maximum x-axis values, or a single tuple containing both limits.

        Usage:
            set_x_lim(x_min, x_max)
            set_x_lim((x_min, x_max))

        Args:
            *args: A variable number of arguments. Can be two integers (x_min and x_max)
                   or a single tuple with two integers.
        """
        if len(args) == 1 and isinstance(args[0], tuple):
            x_min, x_max = args[0]
        elif len(args) == 2:
            x_min, x_max = args
        else:
            raise ValueError("set_x_lim expects either two separate arguments or a single tuple")

        self.plot_item.setXRange(x_min, x_max)
        self.config.axis.x_lim = (x_min, x_max)

    def set_y_lim(self, *args) -> None:
        """
        Set the limits of the y-axis. This method can accept either two separate arguments
        for the minimum and maximum y-axis values, or a single tuple containing both limits.

        Usage:
            set_y_lim(y_min, y_max)
            set_y_lim((y_min, y_max))

        Args:
            *args: A variable number of arguments. Can be two integers (y_min and y_max)
                   or a single tuple with two integers.
        """
        if len(args) == 1 and isinstance(args[0], tuple):
            y_min, y_max = args[0]
        elif len(args) == 2:
            y_min, y_max = args
        else:
            raise ValueError("set_y_lim expects either two separate arguments or a single tuple")

        self.plot_item.setYRange(y_min, y_max)
        self.config.axis.y_lim = (y_min, y_max)

    def set_grid(self, x: bool = False, y: bool = False):
        """
        Set the grid of the plot widget.

        Args:
            x(bool): Show grid on the x-axis.
            y(bool): Show grid on the y-axis.
        """
        self.plot_item.showGrid(x, y)
        self.config.axis.x_grid = x
        self.config.axis.y_grid = y

    def add_legend(self):
        """Add legend to the plot"""
        self.plot_item.addLegend()

    def lock_aspect_ratio(self, lock):
        """
        Lock aspect ratio.

        Args:
            lock(bool): True to lock, False to unlock.
        """
        self.plot_item.setAspectLocked(lock)

    def export(self):
        """Show the Export Dialog of the plot widget."""
        scene = self.plot_item.scene()
        scene.contextMenuItem = self.plot_item
        scene.showExportDialog()

    def remove(self):
        """Remove the plot widget from the figure."""
        if self.figure is not None:
            self.figure.remove(widget_id=self.gui_id)
