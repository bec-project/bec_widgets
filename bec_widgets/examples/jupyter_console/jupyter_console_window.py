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

from bec_widgets.utils import BECDispatcher
from bec_widgets.utils.widget_io import WidgetHierarchy as wh
from bec_widgets.widgets.containers.dock import BECDockArea
from bec_widgets.widgets.containers.figure import BECFigure
from bec_widgets.widgets.containers.layout_manager.layout_manager import LayoutManagerWidget
from bec_widgets.widgets.editors.jupyter_console.jupyter_console import BECJupyterConsole
from bec_widgets.widgets.plots_next_gen.image.image import Image
from bec_widgets.widgets.plots_next_gen.motor_map.motor_map import MotorMap
from bec_widgets.widgets.plots_next_gen.plot_base import PlotBase
from bec_widgets.widgets.plots_next_gen.scatter_waveform.scatter_waveform import ScatterWaveform
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
                    "wh": wh,
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
                    "im": self.im,
                    "mi": self.mi,
                    "mm": self.mm,
                    "lm": self.lm,
                    "btn1": self.btn1,
                    "btn2": self.btn2,
                    "btn3": self.btn3,
                    "btn4": self.btn4,
                    "btn5": self.btn5,
                    "btn6": self.btn6,
                    "pb": self.pb,
                    "pi": self.pi,
                    "wf": self.wf,
                    "scatter": self.scatter,
                    "scatter_mi": self.scatter,
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
        self.wf = Waveform()
        fifth_tab_layout.addWidget(self.wf)
        tab_widget.addTab(fifth_tab, "Waveform Next Gen")
        tab_widget.setCurrentIndex(4)

        sixth_tab = QWidget()
        sixth_tab_layout = QVBoxLayout(sixth_tab)
        self.im = Image()
        self.mi = self.im.main_image
        sixth_tab_layout.addWidget(self.im)
        tab_widget.addTab(sixth_tab, "Image Next Gen")
        tab_widget.setCurrentIndex(5)

        seventh_tab = QWidget()
        seventh_tab_layout = QVBoxLayout(seventh_tab)
        self.scatter = ScatterWaveform()
        self.scatter_mi = self.scatter.main_curve
        self.scatter.plot("samx", "samy", "bpm4i")
        seventh_tab_layout.addWidget(self.scatter)
        tab_widget.addTab(seventh_tab, "Scatter Waveform")
        tab_widget.setCurrentIndex(6)

        eighth_tab = QWidget()
        eighth_tab_layout = QVBoxLayout(eighth_tab)
        self.mm = MotorMap()
        eighth_tab_layout.addWidget(self.mm)
        tab_widget.addTab(eighth_tab, "Motor Map")
        tab_widget.setCurrentIndex(7)

        # add stuff to the new Waveform widget
        self._init_waveform()

        # add stuff to figure
        self._init_figure()

        self.setWindowTitle("Jupyter Console Window")

    def _init_waveform(self):
        # self.wfng._add_curve_custom(x=np.arange(10), y=np.random.rand(10), label="curve1")
        # self.wfng._add_curve_custom(x=np.arange(10), y=np.random.rand(10), label="curve2")
        # self.wfng._add_curve_custom(x=np.arange(10), y=np.random.rand(10), label="curve3")
        self.wf.plot(y_name="bpm4i", y_entry="bpm4i", dap="GaussianModel")
        self.wf.plot(y_name="bpm3a", y_entry="bpm3a", dap="GaussianModel")

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
    icon = material_icon("terminal", color=(255, 255, 255, 255), filled=True)
    app.setWindowIcon(icon)

    bec_dispatcher = BECDispatcher()
    client = bec_dispatcher.client
    client.start()

    win = JupyterConsoleWindow()
    win.show()
    win.resize(1500, 800)

    app.aboutToQuit.connect(win.close)
    sys.exit(app.exec_())
