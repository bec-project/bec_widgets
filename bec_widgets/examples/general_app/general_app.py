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
        self._hook_theme_bar()

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
        apply_theme(theme)

    def _setup_icons(self):
        help_icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxQuestion)
        bug_icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation)
        computer_icon = QIcon.fromTheme("computer")
        widget_icon = QIcon(os.path.join(MODULE_PATH, "assets", "designer_icons", "dock_area.png"))

        self.ui.action_BEC_docs.setIcon(help_icon)
        self.ui.action_BEC_widgets_docs.setIcon(help_icon)
        self.ui.action_bug_report.setIcon(bug_icon)

        self.ui.central_tab.setTabIcon(0, widget_icon)
        self.ui.central_tab.setTabIcon(1, computer_icon)

    def _hook_theme_bar(self):
        self.ui.action_light.setCheckable(True)
        self.ui.action_dark.setCheckable(True)

        # Create an action group to make sure only one can be checked at a time
        theme_group = QActionGroup(self)
        theme_group.addAction(self.ui.action_light)
        theme_group.addAction(self.ui.action_dark)
        theme_group.setExclusive(True)

        # Connect the actions to the theme change method

        self.ui.action_light.triggered.connect(lambda: self.change_theme("light"))
        self.ui.action_dark.triggered.connect(lambda: self.change_theme("dark"))

        self.ui.action_dark.trigger()


def main():  # pragma: no cover

    app = QApplication(sys.argv)
    icon = QIcon()
    icon.addFile(
        os.path.join(MODULE_PATH, "assets", "app_icons", "BEC-Dark.png"), size=QSize(48, 48)
    )
    app.setWindowIcon(icon)
    main_window = BECGeneralApp()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    main()
