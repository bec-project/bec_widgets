import os

import numpy as np
import pyqtgraph as pg
from bec_qthemes import material_icon
from qtpy.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.widgets.containers.expantion_panel.expansion_panel import ExpansionPanel
from bec_widgets.utils import BECDispatcher
from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.containers.dock import BECDockArea
from bec_widgets.widgets.containers.figure import BECFigure
from bec_widgets.widgets.containers.layout_manager.layout_manager import LayoutManagerWidget
from bec_widgets.widgets.editors.jupyter_console.jupyter_console import BECJupyterConsole
from bec_widgets.widgets.plots_next_gen.plot_base import PlotBase
from bec_widgets.widgets.plots_next_gen.waveform.waveform import Waveform


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
                    "im": self.im,
                    "mm": self.mm,
                    "mw": self.mw,
                    "lm": self.lm,
                    "btn1": self.btn1,
                    "btn2": self.btn2,
                    "btn3": self.btn3,
                    "btn4": self.btn4,
                    "btn5": self.btn5,
                    "btn6": self.btn6,
                    "pb": self.pb,
                    "pi": self.pi,
                    "wfng": self.wfng,
                    "ep": self.ep,
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

        third_tab = QWidget()
        third_tab_layout = QVBoxLayout(third_tab)
        self.lm = LayoutManagerWidget()
        third_tab_layout.addWidget(self.lm)
        tab_widget.addTab(third_tab, "Layout Manager Widget")

        fourth_tab = QWidget()
        fourth_tab_layout = QVBoxLayout(fourth_tab)
        self.pb = PlotBase()
        self.pi = self.pb.plot_item
        fourth_tab_layout.addWidget(self.pb)
        tab_widget.addTab(fourth_tab, "PlotBase")

        tab_widget.setCurrentIndex(3)

        group_box = QGroupBox("Jupyter Console", splitter)
        group_box_layout = QVBoxLayout(group_box)
        self.console = BECJupyterConsole(inprocess=True)
        group_box_layout.addWidget(self.console)

        # Some buttons for layout testing
        self.btn1 = QPushButton("Button 1")
        self.btn2 = QPushButton("Button 2")
        self.btn3 = QPushButton("Button 3")
        self.btn4 = QPushButton("Button 4")
        self.btn5 = QPushButton("Button 5")
        self.btn6 = QPushButton("Button 6")

        fifth_tab = QWidget()
        fifth_tab_layout = QVBoxLayout(fifth_tab)
        self.wfng = Waveform()
        fifth_tab_layout.addWidget(self.wfng)
        tab_widget.addTab(fifth_tab, "Waveform Next Gen")
        tab_widget.setCurrentIndex(4)
        # add stuff to the new Waveform widget
        self._init_waveform()

        six_tab = QWidget()
        six_tab_layout = QVBoxLayout(six_tab)
        self.ep = ExpansionPanel()
        self.ep.content_layout.addWidget(self.btn1)
        self.ep.content_layout.addWidget(self.btn2)
        self.ep.content_layout.addWidget(self.btn3)
        self.ep.content_layout.addWidget(self.btn4)
        six_tab_layout.addWidget(self.ep)
        tab_widget.addTab(six_tab, "Exp Panel")
        tab_widget.setCurrentIndex(5)

        # add stuff to figure
        self._init_figure()

        # init dock for testing
        self._init_dock()

        self.setWindowTitle("Jupyter Console Window")

    def _init_waveform(self):
        # self.wfng._add_curve_custom(x=np.arange(10), y=np.random.rand(10), label="curve1")
        # self.wfng._add_curve_custom(x=np.arange(10), y=np.random.rand(10), label="curve2")
        # self.wfng._add_curve_custom(x=np.arange(10), y=np.random.rand(10), label="curve3")
        self.wfng.plot(y_name="bpm4i", y_entry="bpm4i", dap="GaussianModel")
        self.wfng.plot(y_name="bpm3a", y_entry="bpm3a", dap="GaussianModel")

    def _init_figure(self):
        self.w1 = self.figure.plot(x_name="samx", y_name="bpm4i", row=0, col=0)
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
        self.wf = self.d2.add_widget("BECWaveformWidget", row=0, col=0)
        self.wf.plot("bpm4i")
        self.wf.plot("bpm3a")

        self.mw = None  # self.wf.multi_waveform(monitor="waveform")  # , config=config)

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
    icon = material_icon("terminal", color=(255, 255, 255, 255), filled=True)
    app.setWindowIcon(icon)

    bec_dispatcher = BECDispatcher()
    client = bec_dispatcher.client
    client.start()

    win = JupyterConsoleWindow()
    win.show()
    win.resize(1200, 800)

    app.aboutToQuit.connect(win.close)
    sys.exit(app.exec_())
