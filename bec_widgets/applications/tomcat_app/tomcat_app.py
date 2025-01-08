import os
import sys

from qtpy.QtCore import QSize
from qtpy.QtGui import QActionGroup, QIcon
from qtpy.QtWidgets import QApplication, QMainWindow, QStyle

import bec_widgets
from bec_widgets.examples.general_app.web_links import BECWebLinksMixin
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.ui_loader import UILoader

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class TomcatApp(QMainWindow):
    def __init__(self, parent=None):
        super(TomcatApp, self).__init__(parent)
        ui_file_path = os.path.join(os.path.dirname(__file__), "tomcat_app.ui")
        self.load_ui(ui_file_path)

        self.resize(1280, 720)

    def load_ui(self, ui_file):
        loader = UILoader(self)
        self.ui = loader.loader(ui_file)
        self.setCentralWidget(self.ui)


def main():  # pragma: no cover

    app = QApplication(sys.argv)
    icon = QIcon()
    icon.addFile(
        os.path.join(MODULE_PATH, "assets", "app_icons", "BEC-General-App.png"), size=QSize(48, 48)
    )
    app.setWindowIcon(icon)
    main_window = TomcatApp()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    main()
