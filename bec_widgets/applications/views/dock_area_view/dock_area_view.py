from qtpy.QtWidgets import QWidget

from bec_widgets.applications.views.view import ViewBase
from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea


class DockAreaView(ViewBase):
    """
    Modular dock area view for arranging and managing multiple dockable widgets.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        content: QWidget | None = None,
        *,
        id: str | None = None,
        title: str | None = None,
    ):
        super().__init__(parent=parent, content=content, id=id, title=title)
        self.dock_area = BECDockArea(
            self, profile_namespace="bec", auto_profile_namespace=False, object_name="DockArea"
        )
        self.set_content(self.dock_area)
