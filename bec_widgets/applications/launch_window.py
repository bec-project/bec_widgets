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
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow

logger = bec_logger.logger
MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class LaunchWindow(BECMainWindow):
    RPC = True

    def __init__(
        self, parent=None, gui_id: str = None, window_title="BEC Launcher", *args, **kwargs
    ):
        super().__init__(parent=parent, gui_id=gui_id, window_title=window_title, **kwargs)

        self.app = QApplication.instance()

        self.resize(500, 300)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        ui_file_path = os.path.join(MODULE_PATH, "applications/launch_dialog.ui")
        self.load_ui(ui_file_path)
        self.ui.open_dock_area.setText("Open Dock Area")
        self.ui.open_dock_area.clicked.connect(lambda: self.launch("dock_area"))

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
        from bec_widgets.applications import bw_launch

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

            if launch_script is None:
                launch_script = "dock_area"
            if not isinstance(launch_script, str):
                raise ValueError(f"Launch script must be a string, but got {type(launch_script)}.")
            launch = getattr(bw_launch, launch_script, None)
            if launch is None:
                raise ValueError(f"Launch script {launch_script} not found.")

            result_widget = launch(name)
            result_widget.resize(result_widget.minimumSizeHint())
            # TODO Should we simply use the specified name as title here?
            result_widget.window().setWindowTitle(f"BEC - {name}")
            logger.info(f"Created new dock area: {name}")
            logger.info(f"Existing dock areas: {geometry}")
            if geometry is not None:
                result_widget.setGeometry(*geometry)
            if isinstance(result_widget, BECMainWindow):
                result_widget.show()
            else:
                window = BECMainWindow()
                window.setCentralWidget(result_widget)
                window.show()
            return result_widget

    def show_launcher(self):
        self.show()

    def hide_launcher(self):
        self.hide()

    def cleanup(self):
        super().close()
