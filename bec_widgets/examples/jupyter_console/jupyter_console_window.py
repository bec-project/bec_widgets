import os

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow
from pyqtgraph.Qt import QtWidgets, uic
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from bec_widgets.utils import BECDispatcher
from bec_widgets.widgets import BECDockArea, BECFigure


class JupyterConsoleWidget(RichJupyterWidget):  # pragma: no cover:
    def __init__(self):
        super().__init__()

        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=False)
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()

        self.kernel_manager.kernel.shell.push({"np": np, "pg": pg})
        # self.set_console_font_size(70)

    def shutdown_kernel(self):
        self.kernel_client.stop_channels()
        self.kernel_manager.shutdown_kernel()


class JupyterConsoleWindow(QWidget):  # pragma: no cover:
    """A widget that contains a Jupyter console linked to BEC Widgets with full API access (contains Qt and pyqtgraph API)."""

    def __init__(self, parent=None):
        super().__init__(parent)

        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "jupyter_console_window.ui"), self)

        self._init_ui()

        self.splitter.setSizes([200, 100])
        self.safe_close = False
        # self.figure.clean_signal.connect(self.confirm_close)

        # console push
        self.console.kernel_manager.kernel.shell.push(
            {
                "fig": self.figure,
                "dock": self.dock,
                "w1": self.w1,
                "w2": self.w2,
                "w3": self.w3,
                "d1": self.d1,
                "d2": self.d2,
                "d3": self.d3,
                "label_2": self.label_2,
                "bec": self.figure.client,
                "scans": self.figure.client.scans,
                "dev": self.figure.client.device_manager.devices,
            }
        )

    def _init_ui(self):
        # Plotting window
        self.glw_1_layout = QVBoxLayout(self.glw)  # Create a new QVBoxLayout
        self.figure = BECFigure(parent=self, gui_id="remote")  # Create a new BECDeviceMonitor
        self.glw_1_layout.addWidget(self.figure)  # Add BECDeviceMonitor to the layout

        self.dock_layout = QVBoxLayout(self.dock_placeholder)
        self.dock = BECDockArea(gui_id="remote")
        self.dock_layout.addWidget(self.dock)

        # add stuff to figure
        self._init_figure()

        # init dock for testing
        self._init_dock()

        self.console_layout = QVBoxLayout(self.widget_console)
        self.console = JupyterConsoleWidget()
        self.console_layout.addWidget(self.console)
        self.console.set_default_style("linux")

    def _init_figure(self):
        self.figure.plot("samx", "bpm4d")
        self.figure.motor_map("samx", "samy")
        self.figure.image("eiger", color_map="viridis", vrange=(0, 100))

        self.figure.change_layout(2, 2)

        self.w1 = self.figure[0, 0]
        self.w2 = self.figure[0, 1]
        self.w3 = self.figure[1, 0]

        # curves for w1
        self.w1.add_curve_scan("samx", "samy", "bpm4i", pen_style="dash")
        self.w1.add_curve_scan("samx", "samy", "bpm3a", pen_style="dash")
        self.c1 = self.w1.get_config()

    def _init_dock(self):
        self.button_1 = QtWidgets.QPushButton("Button 1 ")
        self.label_1 = QtWidgets.QLabel("some scan info label with useful information")

        self.label_2 = QtWidgets.QLabel("label which is added separately")

        self.d1 = self.dock.add_dock(widget=self.button_1, position="left")
        self.d2 = self.dock.add_dock(widget=self.label_1, position="right")
        self.d3 = self.dock.plot(x_name="samx", y_name="bpm4d")
        self.d4 = self.dock.image(monitor="eiger")

        self.d4.set_vrange(0, 100)


if __name__ == "__main__":  # pragma: no cover
    import sys

    bec_dispatcher = BECDispatcher()
    client = bec_dispatcher.client
    client.start()

    app = QApplication(sys.argv)
    app.setApplicationName("Jupyter Console")
    app.setApplicationDisplayName("Jupyter Console")
    icon = QIcon()
    icon.addFile("terminal_icon.png", size=QSize(48, 48))
    app.setWindowIcon(icon)
    win = JupyterConsoleWindow()
    win.show()

    sys.exit(app.exec_())
