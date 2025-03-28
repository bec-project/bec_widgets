from bec_lib.logger import bec_logger
from qtpy.QtGui import QAction, QActionGroup
from qtpy.QtWidgets import QApplication, QMainWindow, QStyle

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils import UILoader
from bec_widgets.utils.bec_qapp import BECApplication
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.container_utils import WidgetContainerUtils
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea
from bec_widgets.widgets.containers.main_window.addons.web_links import BECWebLinksMixin

logger = bec_logger.logger


class LaunchWindow(BECWidget, QMainWindow):
    def __init__(self, gui_id: str = None, *args, **kwargs):
        BECWidget.__init__(self, gui_id=gui_id, **kwargs)
        QMainWindow.__init__(self, *args, **kwargs)

        self.app = QApplication.instance()

        # self._upgrade_qapp() #TODO consider to make upgrade function to any QApplication to BECQApplication
        self._init_ui()

    def _init_ui(self):
        # Set the window title
        self.setWindowTitle("BEC Launcher")

        # Set Menu and Status bar
        self._setup_menu_bar()

        # BEC Specific UI
        self._init_bec_specific_ui()
        # self.ui = UILoader
        # ui_file_path = os.path.join(os.path.dirname(__file__), "general_app.ui")
        # self.load_ui(ui_file_path)

    # TODO can be implemented for toolbar
    def load_ui(self, ui_file):
        loader = UILoader(self)
        self.ui = loader.loader(ui_file)
        self.setCentralWidget(self.ui)

    def _init_bec_specific_ui(self):
        if getattr(self.app, "gui_id", None):
            self.statusBar().showMessage(f"App ID: {self.app.gui_id}")
        else:
            logger.warning(
                "Application is not a BECApplication instance. Status bar will not show App ID. Please initialize the application with BECApplication."
            )

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
