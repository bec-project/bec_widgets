from qtpy.QtWidgets import QApplication, QHBoxLayout, QStackedWidget, QWidget

from bec_widgets.applications.navigation_centre.side_bar import SideBar
from bec_widgets.applications.navigation_centre.side_bar_components import NavigationItem
from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area import AdvancedDockArea
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow


class BECMainApp(BECMainWindow):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        # --- Compose central UI (sidebar + stack)
        self.sidebar = SideBar(parent=self)
        self.stack = QStackedWidget(self)

        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar, 0)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(container)

        # Mapping for view switching
        self._view_index: dict[str, int] = {}
        self.sidebar.view_selected.connect(self._on_view_selected)

        self._add_views()

    def _add_views(self):
        self.add_section("BEC Applications", "bec_apps")
        self.ads = AdvancedDockArea(self)
        self.add_view(
            icon="widgets", title="Dock Area", id="dock_area", widget=self.ads, mini_text="Docks"
        )
        self.set_current("dock_area")
        self.sidebar.add_dark_mode_item()

    # --- Public API ------------------------------------------------------
    def add_section(self, title: str, id: str, position: int | None = None):
        return self.sidebar.add_section(title, id, position)

    def add_separator(self):
        return self.sidebar.add_separator()

    def add_dark_mode_item(self, id: str = "dark_mode", position: int | None = None):
        return self.sidebar.add_dark_mode_item(id=id, position=position)

    def add_view(
        self,
        *,
        icon: str,
        title: str,
        id: str,
        widget: QWidget,
        mini_text: str | None = None,
        position: int | None = None,
        from_top: bool = True,
        toggleable: bool = True,
        exclusive: bool = True,
    ) -> NavigationItem:
        """
        Register a view in the stack and create a matching nav item in the sidebar.

        Args:
            icon(str): Icon name for the nav item.
            title(str): Title for the nav item.
            id(str): Unique ID for the view/item.
            widget(QWidget): The widget to add to the stack.
            mini_text(str, optional): Short text for the nav item when sidebar is collapsed.
            position(int, optional): Position to insert the nav item.
            from_top(bool, optional): Whether to count position from the top or bottom.
            toggleable(bool, optional): Whether the nav item is toggleable.
            exclusive(bool, optional): Whether the nav item is exclusive.

        Returns:
            NavigationItem: The created navigation item.


        """
        item = self.sidebar.add_item(
            icon=icon,
            title=title,
            id=id,
            mini_text=mini_text,
            position=position,
            from_top=from_top,
            toggleable=toggleable,
            exclusive=exclusive,
        )
        idx = self.stack.addWidget(widget)
        self._view_index[id] = idx
        return item

    def set_current(self, id: str) -> None:
        if id in self._view_index:
            self.sidebar.activate_item(id)
            self._on_view_selected(id)

    # Internal: route sidebar selection to the stack
    def _on_view_selected(self, vid: str) -> None:
        idx = self._view_index.get(vid)
        if idx is not None and 0 <= idx < self.stack.count():
            self.stack.setCurrentIndex(idx)


if __name__ == "__main__":  # pragma: no cover

    import sys

    app = QApplication(sys.argv)
    apply_theme("dark")
    w = BECMainApp()
    w.show()

    sys.exit(app.exec())
