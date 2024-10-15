import os

import numpy as np
import pyqtgraph as pg
from bec_qthemes import material_icon
from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils import BECDispatcher
from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.dock.dock_area import BECDockArea
from bec_widgets.widgets.figure import BECFigure
from bec_widgets.widgets.jupyter_console.jupyter_console import BECJupyterConsole


class JupyterConsoleWindow(QWidget):  # pragma: no cover:
    """A widget that contains a Jupyter console linked to BEC Widgets with full API access (contains Qt and pyqtgraph API)."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._init_ui()

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
                    "w4": self.w4,
                    "w5": self.w5,
                    "w6": self.w6,
                    "w7": self.w7,
                    "w8": self.w8,
                    "w9": self.w9,
                    "w10": self.w10,
                    "d0": self.d0,
                    "d1": self.d1,
                    "d2": self.d2,
                    "wave": self.wf,
                    # "bar": self.bar,
                    # "cm": self.colormap,
                    "im": self.im,
                    "mm": self.mm,
                    "mw": self.mw,
                }
            )

    def _init_ui(self):
        self.layout = QHBoxLayout(self)

        # Horizontal splitter
        splitter = QSplitter(self)
        self.layout.addWidget(splitter)

        tab_widget = QTabWidget(splitter)

        first_tab = QWidget()
        first_tab_layout = QVBoxLayout(first_tab)
        self.dock = BECDockArea(gui_id="dock")
        first_tab_layout.addWidget(self.dock)
        tab_widget.addTab(first_tab, "Dock Area")

        second_tab = QWidget()
        second_tab_layout = QVBoxLayout(second_tab)
        self.figure = BECFigure(parent=self, gui_id="figure")
        second_tab_layout.addWidget(self.figure)
        tab_widget.addTab(second_tab, "BEC Figure")

        group_box = QGroupBox("Jupyter Console", splitter)
        group_box_layout = QVBoxLayout(group_box)
        self.console = BECJupyterConsole(inprocess=True)
        group_box_layout.addWidget(self.console)

        # add stuff to figure
        self._init_figure()

        # init dock for testing
        self._init_dock()

        self.setWindowTitle("Jupyter Console Window")

    def _init_figure(self):
        self.w1 = self.figure.plot(
            x_name="samx",
            y_name="bpm4i",
            # title="Standard Plot with sync device, custom labels - w1",
            # x_label="Motor Position",
            # y_label="Intensity (A.U.)",
            row=0,
            col=0,
        )
        self.w1.set(
            title="Standard Plot with sync device, custom labels - w1",
            x_label="Motor Position",
            y_label="Intensity (A.U.)",
        )
        self.w2 = self.figure.motor_map("samx", "samy", row=0, col=1)
        self.w3 = self.figure.image(
            "eiger", color_map="viridis", vrange=(0, 100), title="Eiger Image - w3", row=0, col=2
        )
        self.w4 = self.figure.plot(
            x_name="samx",
            y_name="samy",
            z_name="bpm4i",
            color_map_z="magma",
            new=True,
            title="2D scatter plot - w4",
            row=0,
            col=3,
        )
        self.w5 = self.figure.plot(
            y_name="bpm4i",
            new=True,
            title="Best Effort Plot - w5",
            dap="GaussianModel",
            row=1,
            col=0,
        )
        self.w6 = self.figure.plot(
            x_name="timestamp", y_name="bpm4i", new=True, title="Timestamp Plot - w6", row=1, col=1
        )
        self.w7 = self.figure.plot(
            x_name="index", y_name="bpm4i", new=True, title="Index Plot - w7", row=1, col=2
        )
        self.w8 = self.figure.plot(
            y_name="monitor_async", new=True, title="Async Plot - Best Effort - w8", row=2, col=0
        )
        self.w9 = self.figure.plot(
            x_name="timestamp",
            y_name="monitor_async",
            new=True,
            title="Async Plot - timestamp - w9",
            row=2,
            col=1,
        )
        self.w10 = self.figure.plot(
            x_name="index",
            y_name="monitor_async",
            new=True,
            title="Async Plot - index - w10",
            row=2,
            col=2,
        )

    def _init_dock(self):

        self.d0 = self.dock.add_dock(name="dock_0")
        self.mm = self.d0.add_widget("BECMotorMapWidget")
        self.mm.change_motors("samx", "samy")

        self.d1 = self.dock.add_dock(name="dock_1", position="right")
        self.im = self.d1.add_widget("BECImageWidget")
        self.im.image("waveform", "1d")

        self.d2 = self.dock.add_dock(name="dock_2", position="bottom")
        self.wf = self.d2.add_widget("BECFigure", row=0, col=0)

        self.mw = self.wf.multi_waveform(monitor="waveform")  # , config=config)
        # self.wf.plot(x_name="samx", y_name="bpm3a")
        # self.wf.plot(x_name="samx", y_name="bpm4i", dap="GaussianModel")
        # self.bar = self.d2.add_widget("RingProgressBar", row=0, col=1)
        # self.bar.set_diameter(200)

        # self.d3 = self.dock.add_dock(name="dock_3", position="bottom")
        # self.colormap = pg.GradientWidget()
        # self.d3.add_widget(self.colormap, row=0, col=0)

        self.dock.save_state()

    def closeEvent(self, event):
        """Override to handle things when main window is closed."""
        self.dock.cleanup()
        self.dock.close()
        self.figure.cleanup()
        self.figure.close()
        self.console.close()

        super().closeEvent(event)


if __name__ == "__main__":  # pragma: no cover
    import sys

    import bec_widgets

    module_path = os.path.dirname(bec_widgets.__file__)

    app = QApplication(sys.argv)
    app.setApplicationName("Jupyter Console")
    app.setApplicationDisplayName("Jupyter Console")
    apply_theme("dark")
    icon = material_icon("terminal", color="#434343", filled=True)
    app.setWindowIcon(icon)

    bec_dispatcher = BECDispatcher()
    client = bec_dispatcher.client
    client.start()

    win = JupyterConsoleWindow()
    win.show()
    win.resize(1200, 800)

    app.aboutToQuit.connect(win.close)
    sys.exit(app.exec_())
