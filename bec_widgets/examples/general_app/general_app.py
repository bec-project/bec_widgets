import os
import sys

import qdarktheme
from PySide6.QtWidgets import QStyle
from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication, QMainWindow

from bec_widgets.examples.general_app.web_links import BECWebLinksMixin
from bec_widgets.utils.ui_loader import UILoader


class BECGeneralApp(QMainWindow):
    def __init__(self, parent=None):
        super(BECGeneralApp, self).__init__(parent)
        ui_file_path = os.path.join(os.path.dirname(__file__), "general_app.ui")
        self.load_ui(ui_file_path)

        self.resize(1280, 720)

        self.ini_ui()

    def ini_ui(self):
        self._setup_icons()
        self._hook_menubar_docs()

    def load_ui(self, ui_file):
        loader = UILoader(self)
        self.ui = loader.loader(ui_file)
        self.setCentralWidget(self.ui)

    def _hook_menubar_docs(self):
        # BEC Docs
        self.ui.action_BEC_docs.triggered.connect(BECWebLinksMixin.open_bec_docs)
        # BEC Widgets Docs
        self.ui.action_BEC_widgets_docs.triggered.connect(BECWebLinksMixin.open_bec_widgets_docs)
        # Bug report
        self.ui.action_bug_report.triggered.connect(BECWebLinksMixin.open_bec_bug_report)

    def change_theme(self, theme):
        qdarktheme.setup_theme(theme)

    def _setup_icons(self):
        help_icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxQuestion)
        bug_icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation)
        computer_icon = QIcon.fromTheme("computer")

        self.ui.action_BEC_docs.setIcon(help_icon)
        self.ui.action_BEC_widgets_docs.setIcon(help_icon)
        self.ui.action_bug_report.setIcon(bug_icon)

        self.ui.central_tab.setTabIcon(0, computer_icon)  # Set icon for the first tab


def main():  # pragma: no cover
    from qtpy import PYSIDE6

    if not PYSIDE6:
        print(
            "PYSIDE6 is not available in the environment. UI files with BEC custom widgets are runnable only with PySide6."
        )
        return
    import bec_widgets

    module_path = os.path.dirname(bec_widgets.__file__)
    app = QApplication(sys.argv)
    icon = QIcon()
    icon.addFile(os.path.join(module_path, "assets", "BEC-Dark.png"), size=QSize(48, 48))
    app.setWindowIcon(icon)
    qdarktheme.setup_theme("dark")
    main_window = BECGeneralApp()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    main()
