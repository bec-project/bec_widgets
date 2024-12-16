from qtpy.QtWidgets import QMainWindow

from bec_widgets.utils import BECConnector
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea


class BECMainWindow(QMainWindow, BECConnector):
    def __init__(self, *args, **kwargs):
        BECConnector.__init__(self, **kwargs)
        QMainWindow.__init__(self, *args, **kwargs)

    def new_dock_area(self, name):
        dock_area = BECDockArea()
        dock_area.resize(dock_area.minimumSizeHint())
        dock_area.window().setWindowTitle(name)
        dock_area.show()
        return dock_area
