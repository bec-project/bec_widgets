from qtpy.QtWidgets import QWidget

from bec_widgets.applications.views.view import ViewBase, ViewTourSteps
from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea
from bec_widgets.widgets.containers.dock_area.workspace_tabs import WorkspaceTabs


class DockAreaView(ViewBase):
    """
    Modular dock area view for arranging and managing multiple dockable widgets.

    Each workspace lives in its own tab with its own dock area and layout. RPC calls are
    forwarded to the dock area of the current tab.
    """

    RPC_CONTENT_CLASS = BECDockArea
    RPC_CONTENT_ATTR = "dock_area"

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
        self.workspaces = WorkspaceTabs(self, profile_namespace="bec", rpc_exposed=False)
        self.set_content(self.workspaces)

    @property
    def dock_area(self) -> BECDockArea | None:
        """The dock area of the current workspace tab."""
        return self.workspaces.current_dock_area()

    def register_tour_steps(self, guided_tour, main_app):
        """Register the current dock area's components with the guided tour."""
        tabs = self.workspaces

        def get_workspace_tabs():
            main_app.set_current("dock_area")
            return (tabs.tabBar(), None)

        step_id = guided_tour.register_widget(
            widget=get_workspace_tabs,
            title="Workspace Tabs",
            text="Each tab is its own workspace with its own layout. Use + to open a new or "
            "saved workspace, double-click a tab to rename it, and drag tabs to reorder them. "
            "Open tabs are restored on the next start.",
        )
        dock_area = self.dock_area
        view_tour = dock_area.register_tour_steps(guided_tour, main_app) if dock_area else None
        if view_tour is None:
            return ViewTourSteps(view_title="Dock Area Workspace", step_ids=[step_id])
        view_tour.step_ids.insert(0, step_id)
        return view_tour

    def cleanup(self):
        self.workspaces.cleanup()
        super().cleanup()
