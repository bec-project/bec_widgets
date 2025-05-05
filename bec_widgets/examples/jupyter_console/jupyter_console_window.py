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
from bec_widgets.widgets.containers.layout_manager.layout_manager import LayoutManagerWidget
from bec_widgets.widgets.editors.jupyter_console.jupyter_console import BECJupyterConsole
from bec_widgets.widgets.plots.image.image import Image
from bec_widgets.widgets.plots.motor_map.motor_map import MotorMap
from bec_widgets.widgets.plots.multi_waveform.multi_waveform import MultiWaveform
from bec_widgets.widgets.plots.plot_base import PlotBase
from bec_widgets.widgets.plots.scatter_waveform.scatter_waveform import ScatterWaveform
from bec_widgets.widgets.plots.waveform.waveform import Waveform


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
                    "dock": self.dock,
                    "im": self.im,
                    # "mi": self.mi,
                    # "mm": self.mm,
                    # "lm": self.lm,
                    # "btn1": self.btn1,
                    # "btn2": self.btn2,
                    # "btn3": self.btn3,
                    # "btn4": self.btn4,
                    # "btn5": self.btn5,
                    # "btn6": self.btn6,
                    # "pb": self.pb,
                    # "pi": self.pi,
                    # "wf": self.wf,
                    # "scatter": self.scatter,
                    # "scatter_mi": self.scatter,
                    # "mwf": self.mwf,
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

        # third_tab = QWidget()
        # third_tab_layout = QVBoxLayout(third_tab)
        # self.lm = LayoutManagerWidget()
        # third_tab_layout.addWidget(self.lm)
        # tab_widget.addTab(third_tab, "Layout Manager Widget")
        #
        # fourth_tab = QWidget()
        # fourth_tab_layout = QVBoxLayout(fourth_tab)
        # self.pb = PlotBase()
        # self.pi = self.pb.plot_item
        # fourth_tab_layout.addWidget(self.pb)
        # tab_widget.addTab(fourth_tab, "PlotBase")
        #
        # tab_widget.setCurrentIndex(3)
        #
        group_box = QGroupBox("Jupyter Console", splitter)
        group_box_layout = QVBoxLayout(group_box)
        self.console = BECJupyterConsole(inprocess=True)
        group_box_layout.addWidget(self.console)
        #
        # # Some buttons for layout testing
        # self.btn1 = QPushButton("Button 1")
        # self.btn2 = QPushButton("Button 2")
        # self.btn3 = QPushButton("Button 3")
        # self.btn4 = QPushButton("Button 4")
        # self.btn5 = QPushButton("Button 5")
        # self.btn6 = QPushButton("Button 6")
        #
        # fifth_tab = QWidget()
        # fifth_tab_layout = QVBoxLayout(fifth_tab)
        # self.wf = Waveform()
        # fifth_tab_layout.addWidget(self.wf)
        # tab_widget.addTab(fifth_tab, "Waveform Next Gen")
        # tab_widget.setCurrentIndex(4)
        #
        sixth_tab = QWidget()
        sixth_tab_layout = QVBoxLayout(sixth_tab)
        self.im = Image()
        self.mi = self.im.main_image
        sixth_tab_layout.addWidget(self.im)
        tab_widget.addTab(sixth_tab, "Image Next Gen")
        tab_widget.setCurrentIndex(1)
        #
        # seventh_tab = QWidget()
        # seventh_tab_layout = QVBoxLayout(seventh_tab)
        # self.scatter = ScatterWaveform()
        # self.scatter_mi = self.scatter.main_curve
        # self.scatter.plot("samx", "samy", "bpm4i")
        # seventh_tab_layout.addWidget(self.scatter)
        # tab_widget.addTab(seventh_tab, "Scatter Waveform")
        # tab_widget.setCurrentIndex(6)
        #
        # eighth_tab = QWidget()
        # eighth_tab_layout = QVBoxLayout(eighth_tab)
        # self.mm = MotorMap()
        # eighth_tab_layout.addWidget(self.mm)
        # tab_widget.addTab(eighth_tab, "Motor Map")
        # tab_widget.setCurrentIndex(7)
        #
        # ninth_tab = QWidget()
        # ninth_tab_layout = QVBoxLayout(ninth_tab)
        # self.mwf = MultiWaveform()
        # ninth_tab_layout.addWidget(self.mwf)
        # tab_widget.addTab(ninth_tab, "MultiWaveform")
        # tab_widget.setCurrentIndex(8)
        #
        # # add stuff to the new Waveform widget
        # self._init_waveform()
        #
        # self.setWindowTitle("Jupyter Console Window")

    def _init_waveform(self):
        self.wf.plot(y_name="bpm4i", y_entry="bpm4i", dap="GaussianModel")
        self.wf.plot(y_name="bpm3a", y_entry="bpm3a", dap="GaussianModel")

    def closeEvent(self, event):
        """Override to handle things when main window is closed."""
        self.dock.cleanup()
        self.dock.close()
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

    bec_dispatcher = BECDispatcher(gui_id="jupyter_console")
    client = bec_dispatcher.client
    client.start()

    win = JupyterConsoleWindow()
    win.show()
    win.resize(1500, 800)

    app.aboutToQuit.connect(win.close)
    sys.exit(app.exec_())
