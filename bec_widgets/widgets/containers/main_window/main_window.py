from bec_lib.logger import bec_logger
from qtpy.QtWidgets import QApplication, QMainWindow

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.container_utils import WidgetContainerUtils
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea

logger = bec_logger.logger


class BECMainWindow(BECWidget, QMainWindow):
    def __init__(self, gui_id: str = None, *args, **kwargs):
        BECWidget.__init__(self, gui_id=gui_id, **kwargs)
        QMainWindow.__init__(self, *args, **kwargs)

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
        dock_area = BECDockArea(name=name)
        dock_area.resize(dock_area.minimumSizeHint())
        # TODO Should we simply use the specified name as title here?
        dock_area.window().setWindowTitle(f"BEC - {name}")
        logger.info(f"Created new dock area: {name}")
        logger.info(f"Existing dock areas: {geometry}")
        if geometry is not None:
            dock_area.setGeometry(*geometry)
        dock_area.show()
        return dock_area

    def cleanup(self):
        super().cleanup()
