import os

from bec_lib.logger import bec_logger
from qtpy.QtCore import QSize
from qtpy.QtGui import QAction, QActionGroup
from qtpy.QtWidgets import QApplication, QMainWindow, QSizePolicy, QStyle

import bec_widgets
from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils import UILoader
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.container_utils import WidgetContainerUtils
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea
from bec_widgets.widgets.containers.main_window.addons.web_links import BECWebLinksMixin

logger = bec_logger.logger
MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class LaunchWindow(BECWidget, QMainWindow):
    def __init__(self, gui_id: str = None, *args, **kwargs):
        QMainWindow.__init__(self, *args, **kwargs)
        BECWidget.__init__(self, gui_id=gui_id, **kwargs)

        self.setObjectName("LaunchWindow")

        self.app = QApplication.instance()

        self.resize(500, 300)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._init_ui()

    def _init_ui(self):
        # Set the window title
        self.setWindowTitle("BEC Launcher")

        # Load ui file
        ui_file_path = os.path.join(MODULE_PATH, "applications/launch_dialog.ui")
        self.load_ui(ui_file_path)

        # Set Menu and Status bar
        self._setup_menu_bar()

        # BEC Specific UI
        self._init_bec_specific_ui()

    # TODO can be implemented for toolbar
    def load_ui(self, ui_file):
        loader = UILoader(self)
        self.ui = loader.loader(ui_file)
        self.setCentralWidget(self.ui)
        self.ui.open_dock_area.setText("Open Dock Area")
        self.ui.open_dock_area.clicked.connect(lambda: self.launch("dock_area"))

    def _init_bec_specific_ui(self):
        if getattr(self.app, "gui_id", None):
            self.statusBar().showMessage(f"App ID: {self.app.gui_id}")
        else:
            logger.warning(
                "Application is not a BECApplication instance. Status bar will not show App ID. Please initialize the application with BECApplication."
            )

    # Set the window icon
    # FIXME this do not work
    def list_app_hierarchy(self):
        """
        List the hierarchy of the application.
        """
        self.app.list_hierarchy()

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

        debug_bar = menu_bar.addMenu(f"DEBUG {self.__class__.__name__}")
        list_hierarchy = QAction("List App Hierarchy", self)
        list_hierarchy.triggered.connect(self.list_app_hierarchy)
        debug_bar.addAction(list_hierarchy)

    def change_theme(self, theme):
        apply_theme(theme)

    def launch(
        self,
        launch_script: str,
        name: str | None = None,
        geometry: tuple[int, int, int, int] | None = None,
    ) -> "BECDockArea":
        """Create a new dock area.

        Args:
            name(str): The name of the dock area.
            geometry(tuple): The geometry parameters to be passed to the dock area.
        Returns:
            BECDockArea: The newly created dock area.
        """
        from bec_widgets.applications.bw_launch import dock_area

        with RPCRegister.delayed_broadcast() as rpc_register:
            existing_dock_areas = rpc_register.get_names_of_rpc_by_class_type(BECDockArea)
            if name is not None:
                if name in existing_dock_areas:
                    raise ValueError(
                        f"Name {name} must be unique for dock areas, but already exists: {existing_dock_areas}."
                    )
            else:
                name = "dock_area"
                name = WidgetContainerUtils.generate_unique_name(name, existing_dock_areas)
            dock_area = dock_area(name)  # BECDockArea(name=name)
            dock_area.resize(dock_area.minimumSizeHint())
            # TODO Should we simply use the specified name as title here?
            dock_area.window().setWindowTitle(f"BEC - {name}")
            logger.info(f"Created new dock area: {name}")
            logger.info(f"Existing dock areas: {geometry}")
            if geometry is not None:
                dock_area.setGeometry(*geometry)

            dock_area.show()
            return dock_area

    def show_launcher(self):
        self.show()

    def hide_launcher(self):
        self.hide()

    def cleanup(self):
        super().close()
