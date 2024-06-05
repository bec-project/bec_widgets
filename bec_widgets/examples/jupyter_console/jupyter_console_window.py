import os

import numpy as np
import pyqtgraph as pg
import qdarktheme
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from bec_widgets.utils import BECDispatcher, UILoader
from bec_widgets.widgets import BECFigure
from bec_widgets.widgets.dock.dock_area import BECDockArea
from bec_widgets.widgets.jupyter_console.jupyter_console import BECJupyterConsole

# class JupyterConsoleWidget(RichJupyterWidget):  # pragma: no cover:
#     def __init__(self):
#         super().__init__()
#
#         self.kernel_manager = QtInProcessKernelManager()
#         self.kernel_manager.start_kernel(show_banner=False)
#         self.kernel_client = self.kernel_manager.client()
#         self.kernel_client.start_channels()
#
#         self.kernel_manager.kernel.shell.push({"np": np, "pg": pg})
#
#     def shutdown_kernel(self):
#         self.kernel_client.stop_channels()
#         self.kernel_manager.shutdown_kernel()


class JupyterConsoleWindow(QWidget):  # pragma: no cover:
    """A widget that contains a Jupyter console linked to BEC Widgets with full API access (contains Qt and pyqtgraph API)."""

    def __init__(self, parent=None):
        super().__init__(parent)

        current_path = os.path.dirname(__file__)
        self.ui = UILoader().load_ui(os.path.join(current_path, "jupyter_console_window.ui"), self)

        self._init_ui()

        self.ui.splitter.setSizes([200, 100])
        self.safe_close = False

        # console push
        if self.console.inprocess is True:
            self.console.kernel_manager.kernel.shell.push(
                {
                    "np": np,
                    "pg": pg,
                    "fig": self.figure,
                    "dock": self.dock,
                    "w1": self.w1,
                    "w2": self.w2,
                    "w3": self.w3,
                    "d0": self.d0,
                    "d1": self.d1,
                    "d2": self.d2,
                    "fig0": self.fig0,
                    "fig1": self.fig1,
                    "fig2": self.fig2,
                    "bar": self.bar,
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
        self.console = BECJupyterConsole(inprocess=True)
        self.console_layout.addWidget(self.console)

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

        self.d0 = self.dock.add_dock(name="dock_0")
        self.fig0 = self.d0.add_widget("BECFigure")
        self.fig0.image("eiger", vrange=(0, 100))

        self.d1 = self.dock.add_dock(name="dock_1", position="right")
        self.fig1 = self.d1.add_widget("BECFigure")
        self.fig1.plot(x_name="samx", y_name="bpm4i")
        self.fig1.plot(x_name="samx", y_name="bpm3a")

        self.d2 = self.dock.add_dock(name="dock_2", position="bottom")
        self.fig2 = self.d2.add_widget("BECFigure", row=0, col=0)
        self.fig2.motor_map(x_name="samx", y_name="samy")
        self.fig2.plot(x_name="samx", y_name="bpm4i")
        self.bar = self.d2.add_widget("SpiralProgressBar", row=0, col=1)
        self.bar.set_diameter(200)

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
    # qdarktheme.setup_theme("auto")
    icon = QIcon()
    icon.addFile(os.path.join(module_path, "assets", "terminal_icon.png"), size=QSize(48, 48))
    app.setWindowIcon(icon)
    win = JupyterConsoleWindow()
    win.show()

    app.aboutToQuit.connect(win.close)
    sys.exit(app.exec_())
