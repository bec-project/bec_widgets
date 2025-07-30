import PySide6QtAds as QtAds
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from bec_qthemes import material_icon

from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow
from bec_widgets.widgets.control.scan_control import ScanControl
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from bec_widgets.widgets.services.bec_queue.bec_queue import BECQueue


class AdvancedDockArea(BECMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Dock Area Example")
        self.setMinimumSize(1400, 1000)

        # Set the dock manager configuration flags
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.eConfigFlag.FocusHighlighting, True)
        QtAds.CDockManager.setConfigFlag(
            QtAds.CDockManager.eConfigFlag.DockAreaDynamicTabsMenuButtonVisibility, True
        )

        # Initialize the dock manager
        self.dock_manager = QtAds.CDockManager(self)

        # Some bec widgets setup
        self.wf1 = Waveform()
        self.wf1.plot("bpm4i")
        self.sc = ScanControl()
        self.qw = BECQueue()
        self.monaco_1 = MonacoWidget()
        self.monaco_2 = MonacoWidget()

        # put them into docks
        self.dock_wf1 = QtAds.CDockWidget("Waveform 1")
        self.dock_wf1.setWidget(self.wf1)
        self.dock_wf1.setIcon(material_icon(self.wf1.ICON_NAME))

        self.dock_sc = QtAds.CDockWidget("Scan Control")
        self.dock_sc.setWidget(self.sc)
        self.dock_sc.setIcon(material_icon(self.sc.ICON_NAME))

        self.dock_qw = QtAds.CDockWidget("Queue")
        self.dock_qw.setWidget(self.qw)
        self.dock_qw.setIcon(material_icon(self.qw.ICON_NAME))

        # Create Monaco editor docks
        self.dock_monaco_1 = QtAds.CDockWidget("Script 1")
        self.dock_monaco_1.setWidget(self.monaco_1)
        self.dock_monaco_1.setIcon(material_icon(self.monaco_1.ICON_NAME))
        self.dock_monaco_2 = QtAds.CDockWidget("Script 2")
        self.dock_monaco_2.setWidget(self.monaco_2)
        self.dock_monaco_2.setIcon(material_icon(self.monaco_2.ICON_NAME))

        # Put docks into the dock manager
        self.dock_manager.addDockWidget(QtAds.DockWidgetArea.RightDockWidgetArea, self.dock_sc)
        self.dock_manager.addDockWidget(QtAds.DockWidgetArea.RightDockWidgetArea, self.dock_qw)
        self.dock_manager.addDockWidget(QtAds.DockWidgetArea.TopDockWidgetArea, self.dock_wf1)

        editor_area = self.dock_manager.addDockWidgetTab(
            QtAds.DockWidgetArea.LeftDockWidgetArea, self.dock_monaco_1
        )
        self.dock_manager.addDockWidgetTabToArea(self.dock_monaco_2, editor_area)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    main_window = AdvancedDockArea()
    main_window.show()
    sys.exit(app.exec())
