from qtpy.QtWidgets import QApplication, QMainWindow

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils import BECConnector
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea


class BECMainWindow(QMainWindow, BECConnector):
    def __init__(self, *args, **kwargs):
        BECConnector.__init__(self, **kwargs)
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

    def new_dock_area(self, name=None):
        name = name or "BEC Widgets"
        self.rpc_register = RPCRegister()
        gui_id = name.replace(" ", "_")
        existing_widgets = self.rpc_register.get_rpc_by_type(gui_id)
        if existing_widgets:
            name = f"{name} {len(existing_widgets) + 1}"

        dock_area = BECDockArea(gui_id=name.replace(" ", "_"))
        dock_area.resize(dock_area.minimumSizeHint())
        dock_area.window().setWindowTitle(name)
        dock_area.show()
        return dock_area
