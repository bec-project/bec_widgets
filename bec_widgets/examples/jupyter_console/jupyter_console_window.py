import os

import numpy as np
import pyqtgraph as pg
import qdarktheme
from PyQt6.QtWidgets import QPushButton, QTextEdit
from pyqtgraph.Qt import QtWidgets, uic
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from bec_widgets.cli.rpc_register import RPCRegister
from bec_widgets.utils import BECDispatcher
from bec_widgets.widgets import BECFigure
from bec_widgets.widgets.dock.dock_area import BECDockArea
from bec_widgets.widgets.dock_area.dock_area import BECDockAreaAlt
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
        uic.loadUi(os.path.join(current_path, "jupyter_console_window.ui"), self)

        self._init_ui()

        self.splitter.setSizes([200, 100])
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

        self.d0 = self.dock.add_dock(name="dock_0")
        self.fig0 = self.d0.add_widget_bec("BECFigure")
        self.fig0.image("eiger", vrange=(0, 100))

        self.d1 = self.dock.add_dock(name="dock_1", position="right")
        self.fig1 = self.d1.add_widget_bec("BECFigure")
        self.fig1.plot("samx", "bpm4i")
        self.fig1.plot("samx", "bpm3a")

        self.d2 = self.dock.add_dock(name="dock_2", position="bottom")
        self.fi2 = self.d2.add_widget_bec("BECFigure", row=0, col=0)
        self.fi2.motor_map("samx", "samy")
        self.bar2 = self.d2.add_widget_bec("SpiralProgressBar", row=0, col=1)
        self.bar2.set_diameter(200)

        self.dock.save_state()

    def ini_dock_alt(self):
        self.d0_alt = self.dock_alt.add_dock(title="dock_0", layout="grid", position="top")
        self.fig0_alt = self.d0_alt.add_widget_bec("BECFigure")
        self.fig0_alt.image("eiger", vrange=(0, 100))

        self.d1_alt = self.dock_alt.add_dock(title="dock_1", layout="grid", position="top")
        self.fig1_alt = self.d1_alt.add_widget_bec("BECFigure")
        self.fig1_alt.plot("samx", "bpm4i")
        self.fig1_alt.plot("samx", "bpm3a")

        self.d2_alt = self.dock_alt.add_dock(title="dock_2", layout="grid", position="bottom")
        self.fi2_alt = self.d2_alt.add_widget_bec("BECFigure", row=0, col=0)
        self.fi2_alt.motor_map("samx", "samy")
        self.bar2_alt = self.d2_alt.add_widget_bec("SpiralProgressBar", row=0, col=1)
        self.bar2_alt.set_diameter(200)

    def closeEvent(self, event):
        """Override to handle things when main window is closed."""
        self.dock.cleanup()
        self.figure.clear_all()
        self.figure.client.shutdown()
        super().closeEvent(event)


if __name__ == "__main__":  # pragma: no cover
    import sys

    bec_dispatcher = BECDispatcher()
    client = bec_dispatcher.client
    client.start()

    app = QApplication(sys.argv)
    app.setApplicationName("Jupyter Console")
    app.setApplicationDisplayName("Jupyter Console")
    qdarktheme.setup_theme("auto")
    icon = QIcon()
    icon.addFile("terminal_icon.png", size=QSize(48, 48))
    app.setWindowIcon(icon)
    win = JupyterConsoleWindow()
    win.show()

    app.aboutToQuit.connect(win.close)
    sys.exit(app.exec_())
