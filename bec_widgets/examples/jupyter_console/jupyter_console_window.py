import os

import numpy as np
import pyqtgraph as pg
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from bec_widgets.utils import BECDispatcher, UILoader
from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.dock.dock_area import BECDockArea
from bec_widgets.widgets.figure import BECFigure
from bec_widgets.widgets.jupyter_console.jupyter_console import BECJupyterConsole


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
                    "w1_c": self.w1_c,
                    "w2_c": self.w2_c,
                    "w3_c": self.w3_c,
                    "w4": self.w4,
                    "d0": self.d0,
                    "d1": self.d1,
                    "d2": self.d2,
                    "plt": self.plt,
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
        self.figure.plot(x_name="samx", y_name="samy", z_name="bpm4i", color_map_z="cividis")
        self.figure.motor_map("samx", "samy")
        self.figure.image("eiger", color_map="viridis", vrange=(0, 100))
        self.figure.plot(
            x_name="samx", y_name="samy", z_name="bpm4i", color_map_z="magma", new=True
        )

        self.figure.change_layout(2, 2)

        self.w1 = self.figure[0, 0]
        self.w2 = self.figure[0, 1]
        self.w3 = self.figure[1, 0]
        self.w4 = self.figure[1, 1]

        # Plot Customisation
        self.w1.set_title("Waveform 1")
        self.w1.set_x_label("Motor Position (samx)")
        self.w1.set_y_label("Intensity A.U.")

        # Image Customisation
        self.w3.set_title("Eiger Image")
        self.w3.set_x_label("X")
        self.w3.set_y_label("Y")

        # Configs to try to pass
        self.w1_c = self.w1._config_dict
        self.w2_c = self.w2._config_dict
        self.w3_c = self.w3._config_dict

        # curves for w1
        self.c1 = self.w1.get_config()

        self.fig_c = self.figure._config_dict

    def _init_dock(self):

        self.d0 = self.dock.add_dock(name="dock_0")
        self.fig0 = self.d0.add_widget("BECFigure")
        data = np.random.rand(10, 2)
        self.fig0.plot(data, label="2d Data")
        self.fig0.image("eiger", vrange=(0, 100))

        self.d1 = self.dock.add_dock(name="dock_1", position="right")
        self.fig1 = self.d1.add_widget("BECFigure")
        self.fig1.plot(x_name="samx", y_name="bpm4i")
        self.fig1.plot(x_name="samx", y_name="bpm3a")

        self.d2 = self.dock.add_dock(name="dock_2", position="bottom")
        self.fig2 = self.d2.add_widget("BECFigure", row=0, col=0)
        self.plt = self.fig2.plot(x_name="samx", y_name="bpm3a")
        self.plt.plot(x_name="samx", y_name="bpm4i", dap="GaussianModel")
        self.bar = self.d2.add_widget("RingProgressBar", row=0, col=1)
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

    app = QApplication(sys.argv)
    app.setApplicationName("Jupyter Console")
    app.setApplicationDisplayName("Jupyter Console")
    apply_theme("dark")
    icon = QIcon()
    icon.addFile(os.path.join(module_path, "assets", "terminal_icon.png"), size=QSize(48, 48))
    app.setWindowIcon(icon)

    bec_dispatcher = BECDispatcher()
    client = bec_dispatcher.client
    client.start()

    win = JupyterConsoleWindow()
    win.show()

    app.aboutToQuit.connect(win.close)
    sys.exit(app.exec_())
