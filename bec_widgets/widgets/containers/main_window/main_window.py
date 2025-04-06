import os

from qtpy.QtCore import QSize
from qtpy.QtGui import QAction, QActionGroup, QIcon
from qtpy.QtWidgets import QApplication, QMainWindow, QStyle

import bec_widgets
from bec_lib.logger import bec_logger
from bec_widgets.utils import UILoader
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.container_utils import WidgetContainerUtils
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.widget_io import WidgetHierarchy
from bec_widgets.widgets.containers.main_window.addons.web_links import BECWebLinksMixin

logger = bec_logger.logger

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class BECMainWindow(BECWidget, QMainWindow):
    def __init__(self, gui_id: str = None, client=None, window_title: str = "BEC", *args, **kwargs):
        QMainWindow.__init__(self, *args, **kwargs)
        BECWidget.__init__(self, gui_id=gui_id, client=client, **kwargs)

        self.app = QApplication.instance()
        self.setWindowTitle(window_title)
        self._init_ui()

    def _init_ui(self):

        # Set the icon
        self._init_bec_icon()

        # Set Menu and Status bar
        self._setup_menu_bar()

        # BEC Specific UI
        self.display_app_id()

    def _init_bec_icon(self):
        icon = self.app.windowIcon()
        if icon.isNull():
            print("No icon is set, setting default icon")
            icon = QIcon()
            icon.addFile(
                os.path.join(MODULE_PATH, "assets", "app_icons", "bec_widgets_icon.png"),
                size=QSize(48, 48),
            )
            self.app.setWindowIcon(icon)
        else:
            print("An icon is set")

    def load_ui(self, ui_file):
        loader = UILoader(self)
        self.ui = loader.loader(ui_file)
        self.setCentralWidget(self.ui)

    def display_app_id(self):
        server_id = self.bec_dispatcher.cli_server.gui_id
        self.statusBar().showMessage(f"App ID: {server_id}")

    def _fetch_theme(self) -> str:
        return self.app.theme.theme

    def _setup_menu_bar(self):
        """
        Setup the menu bar for the main window.
        """
        menu_bar = self.menuBar()

        ########################################
        # Theme menu
        theme_menu = menu_bar.addMenu("Theme")

        theme_group = QActionGroup(self)
        light_theme_action = QAction("Light Theme", self, checkable=True)
        dark_theme_action = QAction("Dark Theme", self, checkable=True)
        theme_group.addAction(light_theme_action)
        theme_group.addAction(dark_theme_action)
        theme_group.setExclusive(True)

        theme_menu.addAction(light_theme_action)
        theme_menu.addAction(dark_theme_action)

        # Connect theme actions
        light_theme_action.triggered.connect(lambda: self.change_theme("light"))
        dark_theme_action.triggered.connect(lambda: self.change_theme("dark"))

        # Set the default theme
        theme = self.app.theme.theme
        if theme == "light":
            light_theme_action.setChecked(True)
        elif theme == "dark":
            dark_theme_action.setChecked(True)

        ########################################
        # Help menu
        help_menu = menu_bar.addMenu("Help")

        help_icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxQuestion)
        bug_icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation)

        bec_docs = QAction("BEC Docs", self)
        bec_docs.setIcon(help_icon)
        widgets_docs = QAction("BEC Widgets Docs", self)
        widgets_docs.setIcon(help_icon)
        bug_report = QAction("Bug Report", self)
        bug_report.setIcon(bug_icon)

        bec_docs.triggered.connect(BECWebLinksMixin.open_bec_docs)
        widgets_docs.triggered.connect(BECWebLinksMixin.open_bec_widgets_docs)
        bug_report.triggered.connect(BECWebLinksMixin.open_bec_bug_report)

        help_menu.addAction(bec_docs)
        help_menu.addAction(widgets_docs)
        help_menu.addAction(bug_report)

    @SafeSlot(str)
    def change_theme(self, theme: str):
        apply_theme(theme)

    def cleanup(self):
        super().close()


class WindowWithUi(BECMainWindow):
    """
    This is just testing app wiht UI file which could be connected to RPC.

    """

    USER_ACCESS = ["new_dock_area", "all_connections", "change_theme", "hierarchy"]

    def __init__(self, *args, name: str = None, **kwargs):
        super().__init__(gui_id="test", *args, **kwargs)
        if name is None:
            name = self.__class__.__name__
        else:
            if not WidgetContainerUtils.has_name_valid_chars(name):
                raise ValueError(f"Name {name} contains invalid characters.")
        self._name = name if name else self.__class__.__name__
        ui_file_path = os.path.join(os.path.dirname(__file__), "example_app.ui")
        self.load_ui(ui_file_path)

    def load_ui(self, ui_file):
        loader = UILoader(self)
        self.ui = loader.loader(ui_file)
        self.setCentralWidget(self.ui)

    @property
    def all_connections(self) -> list:
        all_connections = self.rpc_register.list_all_connections()
        all_connections_keys = list(all_connections.keys())
        return all_connections_keys

    def hierarchy(self):
        WidgetHierarchy.print_widget_hierarchy(self, only_bec_widgets=True)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    print(id(app))
    # app = BECApplication(sys.argv)
    # print(id(app))
    main_window = WindowWithUi()
    main_window.show()
    sys.exit(app.exec())
