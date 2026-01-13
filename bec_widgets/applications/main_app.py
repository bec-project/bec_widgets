from qtpy.QtWidgets import QApplication, QHBoxLayout, QStackedWidget, QWidget

from bec_widgets.applications.navigation_centre.reveal_animator import ANIMATION_DURATION
from bec_widgets.applications.navigation_centre.side_bar import SideBar
from bec_widgets.applications.navigation_centre.side_bar_components import NavigationItem
from bec_widgets.applications.views.developer_view.developer_view import DeveloperView
from bec_widgets.applications.views.device_manager_view.device_manager_view import DeviceManagerView
from bec_widgets.applications.views.view import ViewBase, WaveformViewInline, WaveformViewPopup
from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area import AdvancedDockArea
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow


class BECMainApp(BECMainWindow):

    def __init__(
        self,
        parent=None,
        *args,
        anim_duration: int = ANIMATION_DURATION,
        show_examples: bool = False,
        **kwargs,
    ):
        super().__init__(parent=parent, *args, **kwargs)
        self._show_examples = bool(show_examples)

        # --- Compose central UI (sidebar + stack)
        self.sidebar = SideBar(parent=self, anim_duration=anim_duration)
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
        self._current_view_id: str | None = None
        self.sidebar.view_selected.connect(self._on_view_selected)

        self._add_views()

    def _add_views(self):
        self.add_section("BEC Applications", "bec_apps")
        self.ads = AdvancedDockArea(
            self, profile_namespace="main_workspace", auto_profile_namespace=False
        )
        self.ads.setObjectName("MainWorkspace")
        self.device_manager = DeviceManagerView(self)
        self.developer_view = DeveloperView(self)

        self.add_view(
            icon="widgets", title="Dock Area", id="dock_area", widget=self.ads, mini_text="Docks"
        )
        self.add_view(
            icon="display_settings",
            title="Device Manager",
            id="device_manager",
            widget=self.device_manager,
            mini_text="DM",
        )
        self.add_view(
            icon="code_blocks",
            title="IDE",
            widget=self.developer_view,
            id="developer_view",
            exclusive=True,
        )

        if self._show_examples:
            self.add_section("Examples", "examples")
            waveform_view_popup = WaveformViewPopup(
                parent=self, id="waveform_view_popup", title="Waveform Plot"
            )
            waveform_view_stack = WaveformViewInline(
                parent=self, id="waveform_view_stack", title="Waveform Plot"
            )

            self.add_view(
                icon="show_chart",
                title="Waveform With Popup",
                id="waveform_popup",
                widget=waveform_view_popup,
                mini_text="Popup",
            )
            self.add_view(
                icon="show_chart",
                title="Waveform InLine Stack",
                id="waveform_stack",
                widget=waveform_view_stack,
                mini_text="Stack",
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
        # Wrap plain widgets into a ViewBase so enter/exit hooks are available
        if isinstance(widget, ViewBase):
            view_widget = widget
            view_widget.view_id = id
            view_widget.view_title = title
        else:
            view_widget = ViewBase(content=widget, parent=self, id=id, title=title)

        idx = self.stack.addWidget(view_widget)
        self._view_index[id] = idx
        return item

    def set_current(self, id: str) -> None:
        if id in self._view_index:
            self.sidebar.activate_item(id)

    # Internal: route sidebar selection to the stack
    def _on_view_selected(self, vid: str) -> None:
        # Determine current view
        current_index = self.stack.currentIndex()
        current_view = (
            self.stack.widget(current_index) if 0 <= current_index < self.stack.count() else None
        )

        # Ask current view whether we may leave
        if current_view is not None and hasattr(current_view, "on_exit"):
            may_leave = current_view.on_exit()
            if may_leave is False:
                # Veto: restore previous highlight without re-emitting selection
                if self._current_view_id is not None:
                    self.sidebar.activate_item(self._current_view_id, emit_signal=False)
                return

        # Proceed with switch
        idx = self._view_index.get(vid)
        if idx is None or not (0 <= idx < self.stack.count()):
            return
        self.stack.setCurrentIndex(idx)
        new_view = self.stack.widget(idx)
        self._current_view_id = vid
        if hasattr(new_view, "on_enter"):
            new_view.on_enter()


def main():  # pragma: no cover
    """
    Main function to run the BEC main application, exposed as a script entry point through
    pyproject.toml.
    """
    # pylint: disable=import-outside-toplevel
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="BEC Main Application")
    parser.add_argument(
        "--examples", action="store_true", help="Show the Examples section with waveform demo views"
    )
    # Let Qt consume the remaining args
    args, qt_args = parser.parse_known_args(sys.argv[1:])

    app = QApplication([sys.argv[0], *qt_args])
    apply_theme("dark")
    w = BECMainApp(show_examples=args.examples)

    screen = app.primaryScreen()
    screen_geometry = screen.availableGeometry()
    screen_width = screen_geometry.width()
    screen_height = screen_geometry.height()
    # 70% of screen height, keep 16:9 ratio
    height = int(screen_height * 0.9)
    width = int(height * (16 / 9))

    # If width exceeds screen width, scale down
    if width > screen_width * 0.9:
        width = int(screen_width * 0.9)
        height = int(width / (16 / 9))

    w.resize(width, height)
    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
