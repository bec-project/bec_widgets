# pylint: disable = no-name-in-module,missing-module-docstring
import itertools
import os
from typing import Literal, Optional

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout, QMainWindow
from pydantic import Field
from pyqtgraph.Qt import uic
from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.utils import BECDispatcher, BECConnector, ConnectionConfig
from bec_widgets.widgets.plots import WidgetConfig, BECPlotBase


class FigureConfig(ConnectionConfig):
    """Configuration for BECFigure. Inheriting from ConnectionConfig widget_class and gui_id"""

    theme: Literal["dark", "light"] = Field("dark", description="The theme of the figure widget.")
    num_columns: int = Field(1, description="The number of columns in the figure widget.")
    widgets: dict[str, WidgetConfig] = Field(
        {}, description="The list of widgets to be added to the figure widget."
    )


class BECFigure(BECConnector, pg.GraphicsLayoutWidget):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        config: Optional[FigureConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
    ):
        if config is None:
            config = FigureConfig(widget_class=self.__class__.__name__)
        else:
            self.config = config
        super().__init__(client=client, config=config, gui_id=gui_id)
        pg.GraphicsLayoutWidget.__init__(self, parent)  # in case of inheritance

        self.widgets = {}

        # TODO just testing adding plot
        self.add_widget("widget_1", row=0, col=0, title="Plot 1")
        self.widgets["widget_1"].plot_data(
            np.linspace(0, 10, 100), np.sin(np.linspace(0, 10, 100)), label="sin(x)"
        )

    # def show(self):  # TODO check if useful for anything
    #     self.window = QMainWindow()
    #     self.window.setCentralWidget(self)
    #     self.window.show()
    #
    # def close(self):  # TODO check if useful for anything
    #     if hasattr(self, "window"):
    #         self.window.close()

    def add_widget(self, widget_id: str = None, row: int = None, col: int = None, **kwargs):
        # Generate unique widget_id if not provided
        if not widget_id:
            widget_id = self._generate_unique_widget_id()

        # Check if id is available
        if widget_id in self.widgets:
            print(f"Widget with ID {widget_id} already exists.")  # TODO change to raise error)
            return

        # Crete widget instance and its config
        widget_config = WidgetConfig(
            parent_figure_id=self.gui_id, widget_class="BECPlotBase", gui_id=widget_id, **kwargs
        )

        widget = BECPlotBase(config=widget_config)

        # Check if position is occupied
        if row is not None and col is not None:
            print("adding plot")
            if self.getItem(row, col):
                print(
                    f"Position at row {row} and column {col} is already occupied."
                )  # TODO change to raise error
                return
            else:
                widget_config.row = row
                widget_config.column = col

                # Add widget to the figure
                self.addItem(widget, row=row, col=col)
        else:
            row, col = self._find_next_empty_position()
            widget_config.row = row
            widget_config.column = col

            # Add widget to the figure
            self.addItem(widget, row=row, col=col)

        # Saving config for future referencing
        self.config.widgets[widget_id] = widget_config
        self.widgets[widget_id] = widget

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
                "Key must be a string (widget id) or a tuple of two integers (coordinates)"
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

    def _add_waveform1d(self, widget_id: str = None, row: int = None, col: int = None, **kwargs):
        """
        Add a 1D waveform widget to the figure.
        Args:
            widget_id:
            row:
            col:
            **kwargs:

        Returns:

        """

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


##################################################
##################################################
# Debug window
##################################################
##################################################

from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager


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

        # console push
        self.console.kernel_manager.kernel.shell.push({"fig": self.figure})

    def _init_ui(self):
        # Plotting window
        self.glw_1_layout = QVBoxLayout(self.glw)  # Create a new QVBoxLayout
        self.figure = BECFigure(parent=self)  # Create a new BECDeviceMonitor
        self.glw_1_layout.addWidget(self.figure)  # Add BECDeviceMonitor to the layout

        self.console_layout = QVBoxLayout(self.widget_console)
        self.console = JupyterConsoleWidget()
        self.console_layout.addWidget(self.console)
        self.console.set_default_style("linux")


if __name__ == "__main__":  # pragma: no cover
    import sys

    bec_dispatcher = BECDispatcher()
    client = bec_dispatcher.client
    client.start()

    app = QApplication(sys.argv)
    win = DebugWindow()
    win.show()

    sys.exit(app.exec_())

# if __name__ == "__main__":  # pragma: no cover
#     from PyQt6.QtWidgets import QApplication
#
#     app = QApplication([])
#
#     fig = BECFigure()
#     fig.show()
#
#     app.exec()
