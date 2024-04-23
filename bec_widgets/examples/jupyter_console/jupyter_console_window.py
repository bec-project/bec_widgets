import os

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from bec_widgets.cli.rpc_register import RPCRegister
from bec_widgets.utils import BECDispatcher, UILoader
from bec_widgets.widgets import BECFigure
from bec_widgets.widgets.dock.dock_area import BECDockArea
from bec_widgets.widgets.spiral_progress_bar.spiral_progress_bar import SpiralProgressBar


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
        self.ui = UILoader().load_ui(os.path.join(current_path, "jupyter_console_window.ui"), self)

        self._init_ui()

        self.ui.splitter.setSizes([200, 100])
        self.safe_close = False
        # self.figure.clean_signal.connect(self.confirm_close)

        self.register = RPCRegister()
        self.register.add_rpc(self.figure)

        # console push
        self.console.kernel_manager.kernel.shell.push(
            {
                "fig": self.figure,
                "register": self.register,
                "dock": self.dock,
                "w1": self.w1,
                "w2": self.w2,
                "w3": self.w3,
                "d1": self.d1,
                "d2": self.d2,
                "d3": self.d3,
                "bar": self.bar,
                "b2a": self.button_2_a,
                "b2b": self.button_2_b,
                "b2c": self.button_2_c,
                "bec": self.figure.client,
                "scans": self.figure.client.scans,
                "dev": self.figure.client.device_manager.devices,
            }
        )

    def _init_ui(self):
        # Plotting window
        self.glw_1_layout = QVBoxLayout(self.ui.glw)  # Create a new QVBoxLayout
        self.figure = BECFigure(parent=self, gui_id="remote")  # Create a new BECDeviceMonitor
        self.glw_1_layout.addWidget(self.figure)  # Add BECDeviceMonitor to the layout

        self.dock_layout = QVBoxLayout(self.ui.dock_placeholder)
        self.dock = BECDockArea(gui_id="remote")
        self.dock_layout.addWidget(self.dock)

        # add stuff to figure
        self._init_figure()

        # init dock for testing
        self._init_dock()

        self.console_layout = QVBoxLayout(self.ui.widget_console)
        self.console = JupyterConsoleWidget()
        self.console_layout.addWidget(self.console)
        self.console.set_default_style("linux")

    def _init_figure(self):
        self.figure.plot(x_name="samx", y_name="bpm4d")
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
        self.button_2_a = QtWidgets.QPushButton("Button to be added at place 0,0 in d3")
        self.button_2_b = QtWidgets.QPushButton("button after without postions specified")
        self.button_2_c = QtWidgets.QPushButton("button super late")
        self.button_3 = QtWidgets.QPushButton("Button above Figure ")
        self.bar = SpiralProgressBar()

        self.label_2 = QtWidgets.QLabel("label which is added separately")
        self.label_3 = QtWidgets.QLabel("Label above figure")

        self.d1 = self.dock.add_dock(widget=self.button_1, position="left")
        self.d1.addWidget(self.label_2)
        self.d2 = self.dock.add_dock(widget=self.bar, position="right")
        self.d3 = self.dock.add_dock(name="figure")
        self.fig_dock3 = BECFigure()
        self.fig_dock3.plot(x_name="samx", y_name="bpm4d")
        self.d3.add_widget(self.label_3)
        self.d3.add_widget(self.button_3)
        self.d3.add_widget(self.fig_dock3)

        self.dock.save_state()

    def closeEvent(self, event):
        """Override to handle things when main window is closed."""
        self.dock.cleanup()
        self.figure.clear_all()
        self.figure.client.shutdown()
        super().closeEvent(event)


if __name__ == "__main__":  # pragma: no cover
    import sys

    import bec_widgets

    module_path = os.path.dirname(bec_widgets.__file__)

    bec_dispatcher = BECDispatcher()
    client = bec_dispatcher.client
    client.start()

    app = QApplication(sys.argv)
    app.setApplicationName("Jupyter Console")
    app.setApplicationDisplayName("Jupyter Console")
    icon = QIcon()
    icon.addFile(os.path.join(module_path, "assets", "terminal_icon.png"), size=QSize(48, 48))
    app.setWindowIcon(icon)
    win = JupyterConsoleWindow()
    win.show()

    app.aboutToQuit.connect(win.close)
    sys.exit(app.exec_())
