import PySide6QtAds as QtAds
from bec_qthemes import material_icon
from qtpy.QtWidgets import QApplication

from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow
from bec_widgets.widgets.control.scan_control import ScanControl
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from bec_widgets.widgets.services.bec_queue.bec_queue import BECQueue

# ── Fancy dock styles ──
_LIGHT_DOCK_QSS = """
QDockWidget {
    background: #fafafa;
    border: 1px solid #ccc;
    border-radius: 4px;
}
QTabBar::tab {
    background: #e0e0e0;
    padding: 6px;
    margin: 1px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #333;
}
QTabBar::tab:selected {
    background: #fff;
    font-weight: bold;
}
"""

_DARK_DOCK_QSS = """
QDockWidget {
    background: #2b2b2b;
    border: 1px solid #444;
    border-radius: 4px;
}
QTabBar::tab {
    background: #3c3f41;
    padding: 6px;
    margin: 1px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #bbb;
}
QTabBar::tab:selected {
    background: #323232;
    color: #fff;
    font-weight: bold;
}
"""


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

        theme = getattr(self.app, "theme", None)
        current = theme.theme if theme else "light"
        qss = _DARK_DOCK_QSS if current.lower() == "dark" else _LIGHT_DOCK_QSS
        self.dock_manager.setStyleSheet(qss)
        editor_area.resize(500, 1000)

    def change_theme(self, theme: str):
        # call base so palettes, icons, etc. switch
        super().change_theme(theme)
        # then reapply our dock QSS
        qss = _DARK_DOCK_QSS if theme.lower() == "dark" else _LIGHT_DOCK_QSS
        self.dock_manager.setStyleSheet(qss)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    main_window = AdvancedDockArea()
    main_window.show()
    sys.exit(app.exec())
