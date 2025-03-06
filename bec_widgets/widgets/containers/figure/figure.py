# pylint: disable = no-name-in-module,missing-module-docstring
from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Literal, Optional

import numpy as np
import pyqtgraph as pg
from bec_lib.logger import bec_logger
from pydantic import Field, ValidationError, field_validator
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtWidgets import QWidget
from typeguard import typechecked

from bec_widgets.utils import ConnectionConfig, WidgetContainerUtils
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.containers.figure.plots.image.image import BECImageShow, ImageConfig
from bec_widgets.widgets.containers.figure.plots.motor_map.motor_map import (
    BECMotorMap,
    MotorMapConfig,
)
from bec_widgets.widgets.containers.figure.plots.multi_waveform.multi_waveform import (
    BECMultiWaveform,
    BECMultiWaveformConfig,
)
from bec_widgets.widgets.containers.figure.plots.plot_base import BECPlotBase, SubplotConfig
from bec_widgets.widgets.containers.figure.plots.waveform.waveform import (
    BECWaveform,
    Waveform1DConfig,
)

logger = bec_logger.logger


class FigureConfig(ConnectionConfig):
    """Configuration for BECFigure. Inheriting from ConnectionConfig widget_class and gui_id"""

    theme: Literal["dark", "light"] = Field("dark", description="The theme of the figure widget.")
    num_cols: int = Field(1, description="The number of columns in the figure widget.")
    num_rows: int = Field(1, description="The number of rows in the figure widget.")
    widgets: dict[str, Waveform1DConfig | ImageConfig | MotorMapConfig | SubplotConfig] = Field(
        {}, description="The list of widgets to be added to the figure widget."
    )

    @field_validator("widgets", mode="before")
    @classmethod
    def validate_widgets(cls, v):
        """Validate the widgets configuration."""
        widget_class_map = {
            "BECWaveform": Waveform1DConfig,
            "BECImageShow": ImageConfig,
            "BECMotorMap": MotorMapConfig,
        }
        validated_widgets = {}
        for key, widget_config in v.items():
            if "widget_class" not in widget_config:
                raise ValueError(f"Widget config for {key} does not contain 'widget_class'.")
            widget_class = widget_config["widget_class"]
            if widget_class not in widget_class_map:
                raise ValueError(f"Unknown widget_class '{widget_class}' for widget '{key}'.")
            config_class = widget_class_map[widget_class]
            validated_widgets[key] = config_class(**widget_config)
        return validated_widgets


class WidgetHandler:
    """Factory for creating and configuring BEC widgets for BECFigure."""

    def __init__(self):
        self.widget_factory = {
            "BECPlotBase": (BECPlotBase, SubplotConfig),
            "BECWaveform": (BECWaveform, Waveform1DConfig),
            "BECImageShow": (BECImageShow, ImageConfig),
            "BECMotorMap": (BECMotorMap, MotorMapConfig),
            "BECMultiWaveform": (BECMultiWaveform, BECMultiWaveformConfig),
        }

    def create_widget(
        self,
        widget_type: str,
        widget_id: str,
        parent_figure,
        parent_id: str,
        config: dict = None,
        **axis_kwargs,
    ) -> BECPlotBase:
        """
        Create and configure a widget based on its type.

        Args:
            widget_type (str): The type of the widget to create.
            widget_id (str): Unique identifier for the widget.
            parent_id (str): Identifier of the parent figure.
            config (dict, optional): Additional configuration for the widget.
            **axis_kwargs: Additional axis properties to set on the widget after creation.

        Returns:
            BECPlotBase: The created and configured widget instance.
        """
        entry = self.widget_factory.get(widget_type)
        if not entry:
            raise ValueError(f"Unsupported widget type: {widget_type}")

        widget_class, config_class = entry
        if config is not None and isinstance(config, config_class):
            config = config.model_dump()
        widget_config_dict = {
            "widget_class": widget_class.__name__,
            "parent_id": parent_id,
            "gui_id": widget_id,
            **(config if config is not None else {}),
        }
        widget_config = config_class(**widget_config_dict)
        widget = widget_class(
            config=widget_config, parent_figure=parent_figure, client=parent_figure.client
        )

        if axis_kwargs:
            widget.set(**axis_kwargs)

        return widget


class BECFigure(BECWidget, pg.GraphicsLayoutWidget):
    USER_ACCESS = [
        "_rpc_id",
        "_config_dict",
        "_get_all_rpc",
        "axes",
        "widgets",
        "plot",
        "image",
        "motor_map",
        "remove",
        "change_layout",
        "change_theme",
        "export",
        "clear_all",
        "widget_list",
    ]
    subplot_map = {
        "PlotBase": BECPlotBase,
        "BECWaveform": BECWaveform,
        "BECImageShow": BECImageShow,
        "BECMotorMap": BECMotorMap,
        "BECMultiWaveform": BECMultiWaveform,
    }
    widget_method_map = {
        "BECWaveform": "plot",
        "BECImageShow": "image",
        "BECMotorMap": "motor_map",
        "BECMultiWaveform": "multi_waveform",
    }

    clean_signal = pyqtSignal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        config: Optional[FigureConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        if config is None:
            config = FigureConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = FigureConfig(**config)
        super().__init__(client=client, gui_id=gui_id, config=config, **kwargs)
        pg.GraphicsLayoutWidget.__init__(self, parent)

        self.widget_handler = WidgetHandler()

        # Widget container to reference widgets by 'widget_id'
        self._widgets = defaultdict(dict)

        # Container to keep track of the grid
        self.grid = []
        # Create config and apply it
        self.apply_config(config)

    def __getitem__(self, key: tuple | str):
        if isinstance(key, tuple) and len(key) == 2:
            return self.axes(*key)
        if isinstance(key, str):
            widget = self._widgets.get(key)
            if widget is None:
                raise KeyError(f"No widget with ID {key}")
            return self._widgets.get(key)
        else:
            raise TypeError(
                "Key must be a string (widget id) or a tuple of two integers (grid coordinates)"
            )

    def apply_config(self, config: dict | FigureConfig):  # ,generate_new_id: bool = False):
        if isinstance(config, dict):
            try:
                config = FigureConfig(**config)
            except ValidationError as e:
                logger.error(f"Error in applying config: {e}")
                return
        self.config = config

        # widget_config has to be reset for not have each widget config twice when added to the figure
        widget_configs = list(self.config.widgets.values())
        self.config.widgets = {}
        for widget_config in widget_configs:
            getattr(self, self.widget_method_map[widget_config.widget_class])(
                config=widget_config.model_dump(), row=widget_config.row, col=widget_config.col
            )

    @property
    def widget_list(self) -> list[BECPlotBase]:
        """
        Access all widget in BECFigure as a list
        Returns:
            list[BECPlotBase]: List of all widgets in the figure.
        """
        axes = [value for value in self._widgets.values() if isinstance(value, BECPlotBase)]
        return axes

    @widget_list.setter
    def widget_list(self, value: list[BECPlotBase]):
        """
        Access all widget in BECFigure as a list
        Returns:
            list[BECPlotBase]: List of all widgets in the figure.
        """
        self._axes = value

    @property
    def widgets(self) -> dict:
        """
        All widgets within the figure with gui ids as keys.
        Returns:
            dict: All widgets within the figure.
        """
        return self._widgets

    @widgets.setter
    def widgets(self, value: dict):
        """
        All widgets within the figure with gui ids as keys.
        Returns:
            dict: All widgets within the figure.
        """
        self._widgets = value

    def export(self):
        """Export the plot widget."""
        try:
            plot_item = self.widget_list[0]
        except Exception as exc:
            raise ValueError("No plot widget available to export.") from exc

        scene = plot_item.scene()
        scene.contextMenuItem = plot_item
        scene.showExportDialog()

    @typechecked
    def plot(
        self,
        arg1: list | np.ndarray | str | None = None,
        y: list | np.ndarray | None = None,
        x: list | np.ndarray | None = None,
        x_name: str | None = None,
        y_name: str | None = None,
        z_name: str | None = None,
        x_entry: str | None = None,
        y_entry: str | None = None,
        z_entry: str | None = None,
        color: str | None = None,
        color_map_z: str | None = "magma",
        label: str | None = None,
        validate: bool = True,
        new: bool = False,
        row: int | None = None,
        col: int | None = None,
        dap: str | None = None,
        config: dict | None = None,  # TODO make logic more transparent
        **axis_kwargs,
    ) -> BECWaveform:
        """
        Add a 1D waveform plot to the figure. Always access the first waveform widget in the figure.

        Args:
            arg1(list | np.ndarray | str | None): First argument which can be x data, y data, or y_name.
            y(list | np.ndarray): Custom y data to plot.
            x(list | np.ndarray): Custom x data to plot.
            x_name(str): The name of the device for the x-axis.
            y_name(str): The name of the device for the y-axis.
            z_name(str): The name of the device for the z-axis.
            x_entry(str): The name of the entry for the x-axis.
            y_entry(str): The name of the entry for the y-axis.
            z_entry(str): The name of the entry for the z-axis.
            color(str): The color of the curve.
            color_map_z(str): The color map to use for the z-axis.
            label(str): The label of the curve.
            validate(bool): If True, validate the device names and entries.
            new(bool): If True, create a new plot instead of using the first plot.
            row(int): The row coordinate of the widget in the figure. If not provided, the next empty row will be used.
            col(int): The column coordinate of the widget in the figure. If not provided, the next empty column will be used.
            dap(str): The DAP model to use for the curve.
            config(dict): Recreates the whole BECWaveform widget from provided configuration.
            **axis_kwargs: Additional axis properties to set on the widget after creation.

        Returns:
            BECWaveform: The waveform plot widget.
        """
        waveform = self.subplot_factory(
            widget_type="BECWaveform", config=config, row=row, col=col, new=new, **axis_kwargs
        )
        if config is not None:
            return waveform

        if arg1 is not None or y_name is not None or (y is not None and x is not None):
            waveform.plot(
                arg1=arg1,
                y=y,
                x=x,
                x_name=x_name,
                y_name=y_name,
                z_name=z_name,
                x_entry=x_entry,
                y_entry=y_entry,
                z_entry=z_entry,
                color=color,
                color_map_z=color_map_z,
                label=label,
                validate=validate,
                dap=dap,
            )
        return waveform

    def _init_image(
        self,
        image,
        monitor: str = None,
        monitor_type: Literal["1d", "2d"] = "2d",
        color_bar: Literal["simple", "full"] = "full",
        color_map: str = "magma",
        data: np.ndarray = None,
        vrange: tuple[float, float] = None,
    ) -> BECImageShow:
        """
        Configure the image based on the provided parameters.

        Args:
            image (BECImageShow): The image to configure.
            monitor (str): The name of the monitor to display.
            color_bar (Literal["simple","full"]): The type of color bar to display.
            color_map (str): The color map to use for the image.
            data (np.ndarray): Custom data to display.
        """
        if monitor is not None and data is None:
            image.image(
                monitor=monitor,
                monitor_type=monitor_type,
                color_map=color_map,
                vrange=vrange,
                color_bar=color_bar,
            )
        elif data is not None and monitor is None:
            image.add_custom_image(
                name="custom", data=data, color_map=color_map, vrange=vrange, color_bar=color_bar
            )
        elif data is None and monitor is None:
            # Setting appearance
            if vrange is not None:
                image.set_vrange(vmin=vrange[0], vmax=vrange[1])
            if color_map is not None:
                image.set_color_map(color_map)
        else:
            raise ValueError("Invalid input. Provide either monitor name or custom data.")
        return image

    def image(
        self,
        monitor: str = None,
        monitor_type: Literal["1d", "2d"] = "2d",
        color_bar: Literal["simple", "full"] = "full",
        color_map: str = "magma",
        data: np.ndarray = None,
        vrange: tuple[float, float] = None,
        new: bool = False,
        row: int | None = None,
        col: int | None = None,
        config: dict | None = None,
        **axis_kwargs,
    ) -> BECImageShow:
        """
        Add an image to the figure. Always access the first image widget in the figure.

        Args:
            monitor(str): The name of the monitor to display.
            color_bar(Literal["simple","full"]): The type of color bar to display.
            color_map(str): The color map to use for the image.
            data(np.ndarray): Custom data to display.
            vrange(tuple[float, float]): The range of values to display.
            new(bool): If True, create a new plot instead of using the first plot.
            row(int): The row coordinate of the widget in the figure. If not provided, the next empty row will be used.
            col(int): The column coordinate of the widget in the figure. If not provided, the next empty column will be used.
            config(dict): Recreates the whole BECImageShow widget from provided configuration.
            **axis_kwargs: Additional axis properties to set on the widget after creation.

        Returns:
            BECImageShow: The image widget.
        """

        image = self.subplot_factory(
            widget_type="BECImageShow", config=config, row=row, col=col, new=new, **axis_kwargs
        )
        if config is not None:
            return image

        image = self._init_image(
            image=image,
            monitor=monitor,
            monitor_type=monitor_type,
            color_bar=color_bar,
            color_map=color_map,
            data=data,
            vrange=vrange,
        )
        return image

    def motor_map(
        self,
        motor_x: str = None,
        motor_y: str = None,
        new: bool = False,
        row: int | None = None,
        col: int | None = None,
        config: dict | None = None,
        **axis_kwargs,
    ) -> BECMotorMap:
        """
        Add a motor map to the figure. Always access the first motor map widget in the figure.

        Args:
            motor_x(str): The name of the motor for the X axis.
            motor_y(str): The name of the motor for the Y axis.
            new(bool): If True, create a new plot instead of using the first plot.
            row(int): The row coordinate of the widget in the figure. If not provided, the next empty row will be used.
            col(int): The column coordinate of the widget in the figure. If not provided, the next empty column will be used.
            config(dict): Recreates the whole BECImageShow widget from provided configuration.
            **axis_kwargs: Additional axis properties to set on the widget after creation.

        Returns:
            BECMotorMap: The motor map widget.
        """
        motor_map = self.subplot_factory(
            widget_type="BECMotorMap", config=config, row=row, col=col, new=new, **axis_kwargs
        )
        if config is not None:
            return motor_map

        if motor_x is not None and motor_y is not None:
            motor_map.change_motors(motor_x, motor_y)

        return motor_map

    def multi_waveform(
        self,
        monitor: str = None,
        new: bool = False,
        row: int | None = None,
        col: int | None = None,
        config: dict | None = None,
        **axis_kwargs,
    ):
        multi_waveform = self.subplot_factory(
            widget_type="BECMultiWaveform", config=config, row=row, col=col, new=new, **axis_kwargs
        )
        if config is not None:
            return multi_waveform
        multi_waveform.set_monitor(monitor)
        return multi_waveform

    def subplot_factory(
        self,
        widget_type: Literal[
            "BECPlotBase", "BECWaveform", "BECImageShow", "BECMotorMap", "BECMultiWaveform"
        ] = "BECPlotBase",
        row: int = None,
        col: int = None,
        config=None,
        new: bool = False,
        **axis_kwargs,
    ) -> BECPlotBase:
        # Case 1 - config provided, new plot, possible to define coordinates
        if config is not None:
            widget_cls = config["widget_class"]
            if widget_cls != widget_type:
                raise ValueError(
                    f"Widget type '{widget_type}' does not match the provided configuration ({widget_cls})."
                )
            widget = self.add_widget(
                widget_type=widget_type, config=config, row=row, col=col, **axis_kwargs
            )
            return widget

        # Case 2 - find first plot or create first plot if no plot available, no config provided, no coordinates
        if new is False and (row is None or col is None):
            widget = WidgetContainerUtils.find_first_widget_by_class(
                self._widgets, self.subplot_map[widget_type], can_fail=True
            )
            if widget is not None:
                if axis_kwargs:
                    widget.set(**axis_kwargs)
            else:
                widget = self.add_widget(widget_type=widget_type, **axis_kwargs)
            return widget

        # Case 3 - modifying existing plot wit coordinates provided
        if new is False and (row is not None and col is not None):
            try:
                widget = self.axes(row, col)
            except ValueError:
                widget = None
            if widget is not None:
                if axis_kwargs:
                    widget.set(**axis_kwargs)
            else:
                widget = self.add_widget(widget_type=widget_type, row=row, col=col, **axis_kwargs)
            return widget

        # Case 4 - no previous plot or new plot, no config provided, possible to define coordinates
        widget = self.add_widget(widget_type=widget_type, row=row, col=col, **axis_kwargs)
        return widget

    def add_widget(
        self,
        widget_type: Literal[
            "BECPlotBase", "BECWaveform", "BECImageShow", "BECMotorMap", "BECMultiWaveform"
        ] = "BECPlotBase",
        widget_id: str = None,
        row: int = None,
        col: int = None,
        config=None,
        **axis_kwargs,
    ) -> BECPlotBase:
        """
        Add a widget to the figure at the specified position.

        Args:
            widget_type(Literal["PlotBase","Waveform1D"]): The type of the widget to add.
            widget_id(str): The unique identifier of the widget. If not provided, a unique ID will be generated.
            row(int): The row coordinate of the widget in the figure. If not provided, the next empty row will be used.
            col(int): The column coordinate of the widget in the figure. If not provided, the next empty column will be used.
            config(dict): Additional configuration for the widget.
            **axis_kwargs(dict): Additional axis properties to set on the widget after creation.
        """
        if not widget_id:
            widget_id = str(uuid.uuid4())
        if widget_id in self._widgets:
            raise ValueError(f"Widget with ID '{widget_id}' already exists.")

        # Check if position is occupied
        if row is not None and col is not None:
            if self.getItem(row, col):
                raise ValueError(f"Position at row {row} and column {col} is already occupied.")
        else:
            row, col = self._find_next_empty_position()

        widget = self.widget_handler.create_widget(
            widget_type=widget_type,
            widget_id=widget_id,
            parent_figure=self,
            parent_id=self.gui_id,
            config=config,
            **axis_kwargs,
        )
        widget.set_gui_id(widget_id)
        widget.config.row = row
        widget.config.col = col

        # Add widget to the figure
        self.addItem(widget, row=row, col=col)

        # Update num_cols and num_rows based on the added widget
        self.config.num_rows = max(self.config.num_rows, row + 1)
        self.config.num_cols = max(self.config.num_cols, col + 1)

        # Saving config for future referencing

        self.config.widgets[widget_id] = widget.config
        self._widgets[widget_id] = widget

        # Reflect the grid coordinates
        self._change_grid(widget_id, row, col)

        return widget

    def remove(
        self,
        row: int = None,
        col: int = None,
        widget_id: str = None,
        coordinates: tuple[int, int] = None,
    ) -> None:
        """
        Remove a widget from the figure. Can be removed by its unique identifier or by its coordinates.

        Args:
            row(int): The row coordinate of the widget to remove.
            col(int): The column coordinate of the widget to remove.
            widget_id(str): The unique identifier of the widget to remove.
            coordinates(tuple[int, int], optional): The coordinates of the widget to remove.
        """
        if widget_id:
            self._remove_by_id(widget_id)
        elif row is not None and col is not None:
            self._remove_by_coordinates(row, col)
        elif coordinates:
            self._remove_by_coordinates(*coordinates)
        else:
            raise ValueError("Must provide either widget_id or coordinates for removal.")

    def change_theme(self, theme: Literal["dark", "light"]) -> None:
        """
        Change the theme of the figure widget.

        Args:
            theme(Literal["dark","light"]): The theme to set for the figure widget.
        """
        self.config.theme = theme
        apply_theme(theme)
        for plot in self.widget_list:
            plot.set_x_label(plot.plot_item.getAxis("bottom").label.toPlainText())
            plot.set_y_label(plot.plot_item.getAxis("left").label.toPlainText())
            if plot.plot_item.titleLabel.text:
                plot.set_title(plot.plot_item.titleLabel.text)
            plot.set_legend_label_size()

    def _remove_by_coordinates(self, row: int, col: int) -> None:
        """
        Remove a widget from the figure by its coordinates.

        Args:
            row(int): The row coordinate of the widget to remove.
            col(int): The column coordinate of the widget to remove.
        """
        widget = self.axes(row, col)
        if widget:
            widget_id = widget.config.gui_id
            if widget_id in self._widgets:
                self._remove_by_id(widget_id)

    def _remove_by_id(self, widget_id: str) -> None:
        """
        Remove a widget from the figure by its unique identifier.

        Args:
            widget_id(str): The unique identifier of the widget to remove.
        """
        if widget_id in self._widgets:
            widget = self._widgets.pop(widget_id)
            widget.cleanup_pyqtgraph()
            widget.cleanup()
            self.removeItem(widget)
            self.grid[widget.config.row][widget.config.col] = None
            self._reindex_grid()
            if widget_id in self.config.widgets:
                self.config.widgets.pop(widget_id)
            widget.deleteLater()
        else:
            raise ValueError(f"Widget with ID '{widget_id}' does not exist.")

    def axes(self, row: int, col: int) -> BECPlotBase:
        """
        Get widget by its coordinates in the figure.

        Args:
            row(int): the row coordinate
            col(int): the column coordinate

        Returns:
            BECPlotBase: the widget at the given coordinates
        """
        widget = self.getItem(row, col)
        if widget is None:
            raise ValueError(f"No widget at coordinates ({row}, {col})")
        return widget

    def _find_next_empty_position(self):
        """Find the next empty position (new row) in the figure."""
        row, col = 0, 0
        while self.getItem(row, col):
            row += 1
        return row, col

    def _change_grid(self, widget_id: str, row: int, col: int):
        """
        Change the grid to reflect the new position of the widget.

        Args:
            widget_id(str): The unique identifier of the widget.
            row(int): The new row coordinate of the widget in the figure.
            col(int): The new column coordinate of the widget in the figure.
        """
        while len(self.grid) <= row:
            self.grid.append([])
        row = self.grid[row]
        while len(row) <= col:
            row.append(None)
        row[col] = widget_id

    def _reindex_grid(self):
        """Reindex the grid to remove empty rows and columns."""
        new_grid = []
        for row in self.grid:
            new_row = [widget for widget in row if widget is not None]
            if new_row:
                new_grid.append(new_row)
        #
        # Update the config of each object to reflect its new position
        for row_idx, row in enumerate(new_grid):
            for col_idx, widget in enumerate(row):
                self._widgets[widget].config.row, self._widgets[widget].config.col = (
                    row_idx,
                    col_idx,
                )

        self.grid = new_grid
        self._replot_layout()

    def _replot_layout(self):
        """Replot the layout based on the current grid configuration."""
        self.clear()
        for row_idx, row in enumerate(self.grid):
            for col_idx, widget in enumerate(row):
                self.addItem(self._widgets[widget], row=row_idx, col=col_idx)

    def change_layout(self, max_columns=None, max_rows=None):
        """
        Reshuffle the layout of the figure to adjust to a new number of max_columns or max_rows.
        If both max_columns and max_rows are provided, max_rows is ignored.

        Args:
            max_columns (Optional[int]): The new maximum number of columns in the figure.
            max_rows (Optional[int]): The new maximum number of rows in the figure.
        """
        # Calculate total number of widgets
        total_widgets = len(self._widgets)

        if max_columns:
            # Calculate the required number of rows based on max_columns
            required_rows = (total_widgets + max_columns - 1) // max_columns
            new_grid = [[None for _ in range(max_columns)] for _ in range(required_rows)]
        elif max_rows:
            # Calculate the required number of columns based on max_rows
            required_columns = (total_widgets + max_rows - 1) // max_rows
            new_grid = [[None for _ in range(required_columns)] for _ in range(max_rows)]
        else:
            # If neither max_columns nor max_rows is specified, just return without changing the layout
            return

        # Populate the new grid with widgets' IDs
        current_idx = 0
        for widget_id in self._widgets:
            row = current_idx // len(new_grid[0])
            col = current_idx % len(new_grid[0])
            new_grid[row][col] = widget_id
            current_idx += 1

        self.config.num_rows = row
        self.config.num_cols = col

        # Update widgets' positions and replot them according to the new grid
        self.grid = new_grid
        self._reindex_grid()  # This method should be updated to handle reshuffling correctly
        self._replot_layout()  # Assumes this method re-adds widgets to the layout based on self.grid

    def clear_all(self):
        """Clear all widgets from the figure and reset to default state"""
        for widget in list(self._widgets.values()):
            widget.remove()
        self._widgets.clear()
        self.grid = []
        theme = self.config.theme
        self.config = FigureConfig(
            widget_class=self.__class__.__name__, gui_id=self.gui_id, theme=theme
        )

    def cleanup_pyqtgraph_all_widgets(self):
        """Clean up the pyqtgraph widget."""
        for widget in self.widget_list:
            widget.cleanup_pyqtgraph()

    def cleanup(self):
        """Close the figure widget."""
        self.cleanup_pyqtgraph_all_widgets()
