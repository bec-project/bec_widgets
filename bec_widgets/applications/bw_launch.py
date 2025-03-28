import os

from qtpy.QtWidgets import QApplication, QMainWindow

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.ui_loader import UILoader
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea


class Launcher(BECWidget, QMainWindow):
    def __init__(self, gui_id: str = None, *args, **kwargs):
        BECWidget.__init__(self, gui_id=gui_id, **kwargs)
        QMainWindow.__init__(self, *args, **kwargs)

        ui_file_path = os.path.join(os.path.dirname(__file__), "launcher.ui")
        self.load_ui(ui_file_path)

    def load_ui(self, ui_file):
        loader = UILoader(self)
        self.ui = loader.loader(ui_file)
        self.setCentralWidget(self.ui)


def dock_area(name: str | None = None):
    dock_area = BECDockArea(name=name)
    return dock_area


def launcher():
    launcher = Launcher()
    return launcher


if __name__ == "__main__":
    dock_area()
