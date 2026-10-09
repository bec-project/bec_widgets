from qtpy.QtWidgets import QWidget

from bec_widgets.applications.views.view import ViewBase
from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea
from bec_widgets.widgets.utility.command_palette.palette_core import PaletteCommand
from bec_widgets.widgets.utility.command_palette.palette_sources import (
    device_commands,
    dock_area_commands,
)


class DockAreaView(ViewBase):
    """
    Modular dock area view for arranging and managing multiple dockable widgets.
    """

    RPC_CONTENT_CLASS = BECDockArea

    def __init__(
        self,
        parent: QWidget | None = None,
        content: QWidget | None = None,
        *,
        view_id: str | None = None,
        title: str | None = None,
        **kwargs,
    ):
        super().__init__(parent=parent, content=content, view_id=view_id, title=title, **kwargs)
        self.dock_area = BECDockArea(
            self,
            profile_namespace="bec",
            auto_profile_namespace=False,
            object_name="DockArea",
            rpc_exposed=False,
        )
        self.set_content(self.dock_area)

    def palette_commands(self) -> list[PaletteCommand]:
        """Commands this view adds to the main app's command palette: widgets to add,
        workspaces to open and devices to control or plot."""
        return [
            *dock_area_commands(self.dock_area, self.activate),
            *device_commands(self.dock_area, self.activate),
        ]
