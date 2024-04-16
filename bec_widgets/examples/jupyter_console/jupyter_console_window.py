import os

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import uic
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from bec_widgets.utils import BECDispatcher
from bec_widgets.widgets import BECFigure


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
                "w1": self.w1,
                "w2": self.w2,
                "w3": self.w3,
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

        # add stuff to figure
        self._init_figure()

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


if __name__ == "__main__":  # pragma: no cover
    import sys

    bec_dispatcher = BECDispatcher()
    client = bec_dispatcher.client
    client.start()

    app = QApplication(sys.argv)
    app.setApplicationName("Jupyter Console")
    win = JupyterConsoleWindow()
    win.show()

    sys.exit(app.exec_())
