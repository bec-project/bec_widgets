# pylint: disable = no-name-in-module,missing-module-docstring
from __future__ import annotations

import itertools
import os
from collections import defaultdict
from typing import Literal, Optional

import numpy as np
import pyqtgraph as pg
import qdarktheme
from pydantic import Field
from pyqtgraph.Qt import uic
from qtpy.QtWidgets import QApplication, QWidget
from qtpy.QtWidgets import QVBoxLayout, QMainWindow

from bec_widgets.utils import BECConnector, BECDispatcher, ConnectionConfig
from bec_widgets.widgets.plots import BECPlotBase, BECWaveform1D, Waveform1DConfig, WidgetConfig


class FigureConfig(ConnectionConfig):
    """Configuration for BECFigure. Inheriting from ConnectionConfig widget_class and gui_id"""

    theme: Literal["dark", "light"] = Field("dark", description="The theme of the figure widget.")
    num_columns: int = Field(1, description="The number of columns in the figure widget.")
    num_rows: int = Field(1, description="The number of rows in the figure widget.")
    widgets: dict[str, WidgetConfig] = Field(
        {}, description="The list of widgets to be added to the figure widget."
    )


class WidgetHandler:
    """Factory for creating and configuring BEC widgets for BECFigure."""

    def __init__(self):
        self.widget_factory = {
            "PlotBase": (BECPlotBase, WidgetConfig),
            "Waveform1D": (BECWaveform1D, Waveform1DConfig),
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


class BECFigure(BECConnector, pg.GraphicsLayoutWidget):
    USER_ACCESS = ["add_plot", "remove", "change_layout", "change_theme"]

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        config: Optional[FigureConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
    ) -> None:
        if config is None:
            config = FigureConfig(widget_class=self.__class__.__name__)
        else:
            self.config = config
        super().__init__(client=client, config=config, gui_id=gui_id)
        pg.GraphicsLayoutWidget.__init__(self, parent)

        self.widget_handler = WidgetHandler()

        # Widget container to reference widgets by 'widget_id'
        self.widgets = defaultdict(dict)

        # Container to keep track of the grid
        self.grid = []

    def change_theme(self, theme: Literal["dark", "light"]) -> None:
        """
        Change the theme of the figure widget.
        Args:
            theme(Literal["dark","light"]): The theme to set for the figure widget.
        """
        qdarktheme.setup_theme(theme)
        self.setBackground("k" if theme == "dark" else "w")
        self.config.theme = theme

    def add_plot(
        self, widget_id: str = None, row: int = None, col: int = None, config=None, **axis_kwargs
    ) -> BECWaveform1D:
        """
        Add a Waveform1D plot to the figure at the specified position.
        Args:
            widget_id(str): The unique identifier of the widget. If not provided, a unique ID will be generated.
            row(int): The row coordinate of the widget in the figure. If not provided, the next empty row will be used.
            col(int): The column coordinate of the widget in the figure. If not provided, the next empty column will be used.
            config(dict): Additional configuration for the widget.
            **axis_kwargs(dict): Additional axis properties to set on the widget after creation.
        """
        return self.add_widget(
            widget_type="Waveform1D",
            widget_id=widget_id,
            row=row,
            col=col,
            config=config,
            **axis_kwargs,
        )

    def add_widget(
        self,
        widget_type: Literal["PlotBase", "Waveform1D"] = "PlotBase",
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
            widget_id = self._generate_unique_widget_id()
        if widget_id in self.widgets:
            raise ValueError(f"Widget with ID {widget_id} already exists.")

        widget = self.widget_handler.create_widget(
            widget_type=widget_type,
            widget_id=widget_id,
            parent_figure=self,
            parent_id=self.gui_id,
            config=config,
            **axis_kwargs,
        )

        # Check if position is occupied
        if row is not None and col is not None:
            if self.getItem(row, col):
                raise ValueError(f"Position at row {row} and column {col} is already occupied.")
            else:
                widget.config.row = row
                widget.config.col = col

                # Add widget to the figure
                self.addItem(widget, row=row, col=col)
        else:
            row, col = self._find_next_empty_position()
            widget.config.row = row
            widget.config.col = col

            # Add widget to the figure
            self.addItem(widget, row=row, col=col)

        # TODO decide if needed
        # Update num_columns and num_rows based on the added widget
        self.config.num_rows = max(self.config.num_rows, row + 1)
        self.config.num_columns = max(self.config.num_columns, col + 1)

        # Saving config for future referencing
        self.config.widgets[widget_id] = widget.config
        self.widgets[widget_id] = widget

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

    def _remove_by_coordinates(self, row: int, col: int) -> None:
        """
        Remove a widget from the figure by its coordinates.
        Args:
            row(int): The row coordinate of the widget to remove.
            col(int): The column coordinate of the widget to remove.
        """
        widget = self._get_widget_by_coordinates(row, col)
        if widget:
            widget_id = widget.config.gui_id
            if widget_id and widget_id in self.widgets:
                self._remove_by_id(widget_id)
            else:
                raise ValueError(f"No widget found at coordinates ({row}, {col}).")
        else:
            raise ValueError(f"No widget found at coordinates ({row}, {col}).")

    def _remove_by_id(self, widget_id: str) -> None:
        """
        Remove a widget from the figure by its unique identifier.
        Args:
            widget_id(str): The unique identifier of the widget to remove.
        """
        if widget_id in self.widgets:
            widget = self.widgets.pop(widget_id)
            widget.cleanup()
            self.removeItem(widget)
            self.grid[widget.config.row][widget.config.col] = None
            self._reindex_grid()
            if widget_id in self.config.widgets:
                self.config.widgets.pop(widget_id)
            print(f"Removed widget {widget_id}.")
        else:
            raise ValueError(f"Widget with ID {widget_id} does not exist.")

    def __getitem__(self, key: tuple | str):
        if isinstance(key, tuple) and len(key) == 2:
            return self._get_widget_by_coordinates(*key)
        elif isinstance(key, str):
            widget = self.widgets.get(key)
            if widget is None:
                raise KeyError(f"No widget with ID {key}")
            return self.widgets.get(key)
        else:
            raise TypeError(
                "Key must be a string (widget id) or a tuple of two integers (grid coordinates)"
            )

    def _get_widget_by_coordinates(self, row: int, col: int) -> BECPlotBase:
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
            raise KeyError(f"No widget at coordinates ({row}, {col})")
        return widget

    def _find_next_empty_position(self):
        """Find the next empty position (new row) in the figure."""
        row, col = 0, 0
        while self.getItem(row, col):
            row += 1
        return row, col

    def _generate_unique_widget_id(self):
        """Generate a unique widget ID."""
        existing_ids = set(self.widgets.keys())
        for i in itertools.count(1):
            widget_id = f"widget_{i}"
            if widget_id not in existing_ids:
                return widget_id

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
        print(f"old grid: {self.grid}")
        new_grid = []
        for row in self.grid:
            new_row = [widget for widget in row if widget is not None]
            if new_row:
                new_grid.append(new_row)
        #
        # Update the config of each object to reflect its new position
        for row_idx, row in enumerate(new_grid):
            for col_idx, widget in enumerate(row):
                self.widgets[widget].config.row, self.widgets[widget].config.col = row_idx, col_idx

        self.grid = new_grid
        self._replot_layout()

    def _replot_layout(self):
        """Replot the layout based on the current grid configuration."""
        self.clear()
        for row_idx, row in enumerate(self.grid):
            for col_idx, widget in enumerate(row):
                self.addItem(self.widgets[widget], row=row_idx, col=col_idx)

    def change_layout(self, max_columns=None, max_rows=None):
        """
        Reshuffle the layout of the figure to adjust to a new number of max_columns or max_rows.
        If both max_columns and max_rows are provided, max_rows is ignored.

        Args:
            max_columns (Optional[int]): The new maximum number of columns in the figure.
            max_rows (Optional[int]): The new maximum number of rows in the figure.
        """
        # Calculate total number of widgets
        total_widgets = len(self.widgets)

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
        for widget_id, widget in self.widgets.items():
            row = current_idx // len(new_grid[0])
            col = current_idx % len(new_grid[0])
            new_grid[row][col] = widget_id
            current_idx += 1

        # Update widgets' positions and replot them according to the new grid
        self.grid = new_grid
        self._reindex_grid()  # This method should be updated to handle reshuffling correctly
        self._replot_layout()  # Assumes this method re-adds widgets to the layout based on self.grid

    def start(self):
        import sys

        app = QApplication(sys.argv)
        win = QMainWindow()
        win.setCentralWidget(self)
        win.show()

        sys.exit(app.exec_())


##################################################
##################################################
# Debug window
##################################################
##################################################

from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget


class JupyterConsoleWidget(RichJupyterWidget):
    def __init__(self):
        super().__init__()

        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=False)
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()

        self.kernel_manager.kernel.shell.push({"np": np, "pg": pg})

    def shutdown_kernel(self):
        self.kernel_client.stop_channels()
        self.kernel_manager.shutdown_kernel()


class DebugWindow(QWidget):
    """Debug window for BEC widgets"""

    def __init__(self, parent=None):
        super().__init__(parent)

        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "figure_debug_minimal.ui"), self)

        self._init_ui()

        self.splitter.setSizes([200, 100])

        # console push
        self.console.kernel_manager.kernel.shell.push(
            {"fig": self.figure, "w1": self.w1, "w2": self.w2}
        )

    def _init_ui(self):
        # Plotting window
        self.glw_1_layout = QVBoxLayout(self.glw)  # Create a new QVBoxLayout
        self.figure = BECFigure(parent=self)  # Create a new BECDeviceMonitor
        self.glw_1_layout.addWidget(self.figure)  # Add BECDeviceMonitor to the layout

        # add stuff to figure
        self._init_figure()

        self.console_layout = QVBoxLayout(self.widget_console)
        self.console = JupyterConsoleWidget()
        self.console_layout.addWidget(self.console)
        self.console.set_default_style("linux")

    def _init_figure(self):
        self.figure.add_widget(widget_type="Waveform1D", row=0, col=0, title="Widget 1")
        self.figure.add_widget(widget_type="Waveform1D", row=1, col=0, title="Widget 2")
        self.figure.add_widget(widget_type="Waveform1D", row=0, col=1, title="Widget 3")
        self.figure.add_widget(widget_type="Waveform1D", row=1, col=1, title="Widget 4")

        self.w1 = self.figure[0, 0]
        self.w2 = self.figure[1, 0]
        self.w3 = self.figure[0, 1]
        self.w4 = self.figure[1, 1]

        # curves for w1
        self.w1.add_curve_scan("samx", "bpm4i", pen_style="dash")
        self.w1.add_curve_custom(
            x=[1, 2, 3, 4, 5],
            y=[1, 2, 3, 4, 5],
            label="curve-custom",
            color="blue",
            pen_style="dashdot",
        )
        self.c1 = self.w1.get_config()

        # curves for w2
        self.w2.add_curve_scan("samx", "bpm3a", pen_style="solid")
        self.w2.add_curve_scan("samx", "bpm4d", pen_style="dot")
        self.w2.add_curve_custom(
            x=[1, 2, 3, 4, 5], y=[5, 4, 3, 2, 1], color="red", pen_style="dashdot"
        )

        # curves for w3
        self.w3.add_curve_scan("samx", "bpm4i", pen_style="dash")
        self.w3.add_curve_custom(
            x=[1, 2, 3, 4, 5],
            y=[1, 2, 3, 4, 5],
            label="curve-custom",
            color="blue",
            pen_style="dashdot",
        )

        # curves for w4
        self.w4.add_curve_scan("samx", "bpm4i", pen_style="dash")
        self.w4.add_curve_custom(
            x=[1, 2, 3, 4, 5],
            y=[1, 2, 3, 4, 5],
            label="curve-custom",
            color="blue",
            pen_style="dashdot",
        )


if __name__ == "__main__":  # pragma: no cover
    import sys

    bec_dispatcher = BECDispatcher()
    client = bec_dispatcher.client
    client.start()

    app = QApplication(sys.argv)
    win = DebugWindow()
    win.show()

    sys.exit(app.exec_())
