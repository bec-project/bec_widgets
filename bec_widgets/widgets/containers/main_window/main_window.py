from __future__ import annotations
import os
import sys

from bec_lib.logger import bec_logger
from PySide6.QtCore import QSize
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QFileDialog, QMessageBox, QStyle, QWidget
from bec_widgets.examples.qapp_custom.bec_qapp import upgrade_to_becqapp, BECQApplication
from bec_widgets.utils import UILoader
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QMainWindow

import bec_widgets
from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.qt_utils.toolbar import MaterialIconAction
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.container_utils import WidgetContainerUtils
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea
from bec_widgets.widgets.containers.main_window.web_links import BECWebLinksMixin

logger = bec_logger.logger


class BECMainWindow(BECWidget, QMainWindow):
    USER_ACCESS = ["new_dock_area", "change_theme", "list_all_rpc"]

    def __init__(
        self, gui_id: str = None, name: str = None, default_widget=QWidget, *args, **kwargs
    ):
        BECWidget.__init__(self, gui_id=gui_id, name=name, **kwargs)
        QMainWindow.__init__(self, *args, **kwargs)
        # Upgrade qApp if necessary
        self.app = QApplication.instance()

        self._upgrade_qapp()
        self._init_ui()

    def _upgrade_qapp(self):
        if not getattr(self.app, "is_bec_app", False):
            print("[BECWidget]: Upgrading QApplication instance to BECQApplication.")
            self.app = upgrade_to_becqapp()
        else:
            print("[BECWidget]: BECQApplication already active.")

        self.app.inject_property("widget_initialized", True)

    def _init_ui(self):
        # Set the window title
        self.setWindowTitle("BEC")

        # Set Menu and Status bar
        self._setup_menu_bar()
        self.statusBar().showMessage(f"App ID: {self.app.gui_id}")

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
        # TODO can be fetched from app
        light_theme_action.setChecked(True)

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

    def _dump(self):
        """Return a dictionary with informations about the application state, for use in tests"""
        # TODO: ModularToolBar and something else leak top-level widgets (3 or 4 QMenu + 2 QWidget);
        # so, a filtering based on title is applied here, but the solution is to not have those widgets
        # as top-level (so for now, a window with no title does not appear in _dump() result)

        # NOTE: the main window itself is excluded, since we want to dump dock areas
        info = {
            tlw.gui_id: {
                "title": tlw.windowTitle(),
                "visible": tlw.isVisible(),
                "class": str(type(tlw)),
            }
            for tlw in QApplication.instance().topLevelWidgets()
            if tlw is not self and tlw.windowTitle()
        }
        # Add the main window dock area
        info[self.centralWidget().gui_id] = {
            "title": self.windowTitle(),
            "visible": self.isVisible(),
            "class": str(type(self.centralWidget())),
        }
        return info

    def change_theme(self, theme):
        apply_theme(theme)

    def new_dock_area(
        self, name: str | None = None, geometry: tuple[int, int, int, int] | None = None
    ) -> BECDockArea:
        """Create a new dock area.

        Args:
            name(str): The name of the dock area.
            geometry(tuple): The geometry parameters to be passed to the dock area.
        Returns:
            BECDockArea: The newly created dock area.
        """
        rpc_register = RPCRegister()
        existing_dock_areas = rpc_register.get_names_of_rpc_by_class_type(BECDockArea)
        if name is not None:
            if name in existing_dock_areas:
                raise ValueError(
                    f"Name {name} must be unique for dock areas, but already exists: {existing_dock_areas}."
                )
        else:
            name = "dock_area"
            name = WidgetContainerUtils.generate_unique_name(name, existing_dock_areas)
        new_q_main_window = BECMainWindow(gui_id=name)
        dock_area = BECDockArea(name=name)
        new_q_main_window.setCentralWidget(dock_area)
        new_q_main_window.resize(dock_area.minimumSizeHint())
        # TODO Should we simply use the specified name as title here?
        new_q_main_window.window().setWindowTitle(f"BEC - {name}")
        logger.info(f"Created new dock area: {name}")
        logger.info(f"Existing dock areas: {geometry}")
        if geometry is not None:
            new_q_main_window.setGeometry(*geometry)
        new_q_main_window.show()
        return dock_area

    def list_all_rpc(self) -> list:
        """
        List all the registered RPC objects.

        Returns:
            dict: A dictionary containing all the registered RPC objects.
        """
        all_connections = self.rpc_register.list_all_connections()
        all_connections_keys = list(all_connections.keys())
        return all_connections_keys

    def cleanup(self):
        super().close()


class WindowWithUi(BECMainWindow):
    """
    A class that represents a window with a user interface.
    It inherits from BECMainWindow and provides additional functionality.
    """

    USER_ACCESS = [
        "new_dock_area",
        "all_connections",
        "change_theme",
        "list_all_rpc",
        "dock_area",
        "register_all_rpc",
        "widget_list",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        ui_file_path = os.path.join(os.path.dirname(__file__), "general_app.ui")
        self.load_ui(ui_file_path)

    def load_ui(self, ui_file):
        loader = UILoader(self)
        self.ui = loader.loader(ui_file)
        self.setCentralWidget(self.ui)

    @property
    def dock_area(self):
        dock_area = self.ui.dock_area
        return dock_area

    @property
    def all_connections(self) -> list:
        all_connections = self.rpc_register.list_all_connections()
        all_connections_keys = list(all_connections.keys())
        return all_connections_keys

    def register_all_rpc(self):
        app = QApplication.instance()
        app.register_all()

    @property
    def widget_list(self) -> list:
        """Return a list of all widgets in the application."""
        app = QApplication.instance()
        all_widgets = app.list_all_bec_widgets()
        return all_widgets


if __name__ == "__main__":
    app = BECQApplication(sys.argv)

    window = WindowWithUi()
    window.resize(1280, 720)
    window.show()
    sys.exit(app.exec())
