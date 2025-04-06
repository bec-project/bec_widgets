import os

from qtpy.QtWidgets import QSizePolicy

import bec_widgets
from bec_lib.logger import bec_logger
from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils import UILoader
from bec_widgets.utils.container_utils import WidgetContainerUtils
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow

logger = bec_logger.logger
MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class LaunchWindow(BECMainWindow):
    def __init__(self, gui_id: str = None, *args, **kwargs):
        BECMainWindow.__init__(self, gui_id=gui_id, window_title="BEC Launcher", *args, **kwargs)

        self.setObjectName("LaunchWindow")

        self.resize(500, 300)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.loader = UILoader(self)
        self._init_ui()

    def _init_ui(self):
        super()._init_ui()
        # Load ui file
        ui_file_path = os.path.join(MODULE_PATH, "applications/launch_dialog.ui")
        self.load_ui(ui_file_path)

    def load_ui(self, ui_file):
        self.ui = self.loader.loader(ui_file)
        self.setCentralWidget(self.ui)
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

            # TODO somehow we need to encapsulate this into BECMainWindow and keep dock area as top widget
            # window = BECMainWindow()
            # window.setCentralWidget(dock_area)
            # window.show()
            # dock_area.parent_id = None
            dock_area.show()
            return dock_area

    def custom_ui_launcher(self): ...

    def show_launcher(self):
        self.show()

    def hide_launcher(self):
        self.hide()

    def cleanup(self):
        super().close()
