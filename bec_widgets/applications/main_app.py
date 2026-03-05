from bec_qthemes import material_icon
from qtpy.QtGui import QAction  # type: ignore
from qtpy.QtWidgets import QApplication, QHBoxLayout, QStackedWidget, QWidget

from bec_widgets.applications.navigation_centre.reveal_animator import ANIMATION_DURATION
from bec_widgets.applications.navigation_centre.side_bar import SideBar
from bec_widgets.applications.navigation_centre.side_bar_components import NavigationItem
from bec_widgets.applications.views.admin_view.admin_view import AdminView
from bec_widgets.applications.views.developer_view.developer_view import DeveloperView
from bec_widgets.applications.views.device_manager_view.device_manager_view import DeviceManagerView
from bec_widgets.applications.views.dock_area_view.dock_area_view import DockAreaView
from bec_widgets.applications.views.view import ViewBase, WaveformViewInline, WaveformViewPopup
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.guided_tour import GuidedTour
from bec_widgets.utils.name_utils import sanitize_namespace
from bec_widgets.utils.screen_utils import (
    apply_centered_size,
    available_screen_geometry,
    main_app_size_for_screen,
)
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow


class BECMainApp(BECMainWindow):
    RPC = False
    PLUGIN = False

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

        # Initialize guided tour
        self.guided_tour = GuidedTour(self)
        self._setup_guided_tour()

    def _add_views(self):
        self.add_section("BEC Applications", "bec_apps")
        self.dock_area = DockAreaView(self)
        self.device_manager = DeviceManagerView(self)
        # self.developer_view = DeveloperView(self) #TODO temporary disable until the bugs with BECShell are resolved
        self.admin_view = AdminView(self)

        self.add_view(icon="widgets", title="Dock Area", widget=self.dock_area, mini_text="Docks")
        self.add_view(
            icon="display_settings",
            title="Device Manager",
            widget=self.device_manager,
            mini_text="DM",
        )
        # TODO temporary disable until the bugs with BECShell are resolved
        # self.add_view(
        #     icon="code_blocks",
        #     title="IDE",
        #     widget=self.developer_view,
        #     mini_text="IDE",
        #     exclusive=True,
        # )
        self.add_view(
            icon="admin_panel_settings",
            title="Admin View",
            widget=self.admin_view,
            mini_text="Admin",
            from_top=False,
        )

        if self._show_examples:
            self.add_section("Examples", "examples")
            waveform_view_popup = WaveformViewPopup(
                parent=self, view_id="waveform_view_popup", title="Waveform Plot"
            )
            waveform_view_stack = WaveformViewInline(
                parent=self, view_id="waveform_view_stack", title="Waveform Plot"
            )

            self.add_view(
                icon="show_chart",
                title="Waveform With Popup",
                widget=waveform_view_popup,
                mini_text="Popup",
            )
            self.add_view(
                icon="show_chart",
                title="Waveform InLine Stack",
                widget=waveform_view_stack,
                mini_text="Stack",
            )

        self.set_current("dock_area")
        self.sidebar.add_dark_mode_item()

        # Add guided tour to Help menu
        self._add_guided_tour_to_menu()

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
        view_id: str | None = None,
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
            view_id(str, optional): Unique ID for the view/item. If omitted, uses mini_text;
                if mini_text is also omitted, uses title.
            widget(QWidget): The widget to add to the stack.
            mini_text(str, optional): Short text for the nav item when sidebar is collapsed.
            position(int, optional): Position to insert the nav item.
            from_top(bool, optional): Whether to count position from the top or bottom.
            toggleable(bool, optional): Whether the nav item is toggleable.
            exclusive(bool, optional): Whether the nav item is exclusive.

        Returns:
            NavigationItem: The created navigation item.


        """
        resolved_id = sanitize_namespace(view_id or mini_text or title)
        item = self.sidebar.add_item(
            icon=icon,
            title=title,
            id=resolved_id,
            mini_text=mini_text,
            position=position,
            from_top=from_top,
            toggleable=toggleable,
            exclusive=exclusive,
        )
        # Wrap plain widgets into a ViewBase so enter/exit hooks are available
        if isinstance(widget, ViewBase):
            view_widget = widget
            view_widget.view_id = resolved_id
            view_widget.view_title = title
        else:
            view_widget = ViewBase(content=widget, parent=self, view_id=resolved_id, title=title)

        view_widget.change_object_name(resolved_id)

        idx = self.stack.addWidget(view_widget)
        self._view_index[resolved_id] = idx
        return item

    def set_current(self, id: str) -> None:
        if id in self._view_index:
            self.sidebar.activate_item(id)

    # Internal: route sidebar selection to the stack
    def _on_view_selected(self, vid: str) -> None:
        # Special handling for views that can not be switched to (e.g. dark mode toggle)
        # Not registered as proper view with a stack index, so we ignore any logic below
        # as it will anyways not result in a stack switch.
        idx = self._view_index.get(vid)
        if idx is None or not (0 <= idx < self.stack.count()):
            return
        # if vid == "dark_mode":
        #     # Special handling for dark mode toggle item
        #     return
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

    def _setup_guided_tour(self):
        """
        Setup the guided tour for the main application.
        Registers key UI components and delegates to views for their internal components.
        """
        tour_steps = []

        # --- General Layout Components ---

        # Register the sidebar toggle button
        toggle_step = self.guided_tour.register_widget(
            widget=self.sidebar.toggle,
            title="Sidebar Toggle",
            text="Click this button to expand or collapse the sidebar. When expanded, you can see full navigation item titles and section names.",
        )
        tour_steps.append(toggle_step)

        # Register the sidebar icons
        sidebar_dock_area = self.sidebar.components.get("dock_area")
        if sidebar_dock_area:
            dock_step = self.guided_tour.register_widget(
                widget=sidebar_dock_area,
                title="Dock Area View",
                text="Click here to access the Dock Area view, where you can manage and arrange your dockable panels.",
            )
            tour_steps.append(dock_step)

        sidebar_device_manager = self.sidebar.components.get("device_manager")
        if sidebar_device_manager:
            device_manager_step = self.guided_tour.register_widget(
                widget=sidebar_device_manager,
                title="Device Manager View",
                text="Click here to open the Device Manager view, where you can view and manage device configs.",
            )
            tour_steps.append(device_manager_step)

        sidebar_developer_view = self.sidebar.components.get("developer_view")
        if sidebar_developer_view:
            developer_view_step = self.guided_tour.register_widget(
                widget=sidebar_developer_view,
                title="Developer View",
                text="Click here to access the Developer view to write scripts and makros.",
            )
            tour_steps.append(developer_view_step)

        # Register the dark mode toggle
        dark_mode_item = self.sidebar.components.get("dark_mode")
        if dark_mode_item:
            dark_mode_step = self.guided_tour.register_widget(
                widget=dark_mode_item,
                title="Theme Toggle",
                text="Switch between light and dark themes. The theme preference is saved and will be applied when you restart the application.",
            )
            tour_steps.append(dark_mode_step)

        # Register the client info label
        if hasattr(self, "_client_info_hover"):
            client_info_step = self.guided_tour.register_widget(
                widget=self._client_info_hover,
                title="Client Status",
                text="Displays status messages and information from the BEC Server.",
            )
            tour_steps.append(client_info_step)

        # Register the scan progress bar if available
        if hasattr(self, "_scan_progress_hover"):
            progress_step = self.guided_tour.register_widget(
                widget=self._scan_progress_hover,
                title="Scan Progress",
                text="Monitor the progress of ongoing scans. Hover over the progress bar to see detailed information including elapsed time and estimated completion.",
            )
            tour_steps.append(progress_step)

        # Register the notification indicator in the status bar
        if hasattr(self, "notification_indicator"):
            notif_step = self.guided_tour.register_widget(
                widget=self.notification_indicator,
                title="Notification Center",
                text="View system notifications, errors, and status updates. Click to filter notifications by type or expand to see all details.",
            )
            tour_steps.append(notif_step)

        # --- View-Specific Components ---

        # Register all views that can extend the tour
        for view_id, view_index in self._view_index.items():
            view_widget = self.stack.widget(view_index)
            if not view_widget or not hasattr(view_widget, "register_tour_steps"):
                continue

            # Get the view's tour steps
            view_tour = view_widget.register_tour_steps(self.guided_tour, self)
            if view_tour is None:
                if hasattr(view_widget.content, "register_tour_steps"):
                    view_tour = view_widget.content.register_tour_steps(self.guided_tour, self)
                if view_tour is None:
                    continue

            # Get the corresponding sidebar navigation item
            nav_item = self.sidebar.components.get(view_id)
            if not nav_item:
                continue

            # Use the view's title for the navigation button
            nav_step = self.guided_tour.register_widget(
                widget=nav_item,
                title=view_tour.view_title,
                text=f"Let's explore the features of the {view_tour.view_title}.",
            )
            tour_steps.append(nav_step)
            tour_steps.extend(view_tour.step_ids)

        # Create the tour with all registered steps
        if tour_steps:
            self.guided_tour.create_tour(tour_steps)

    def start_guided_tour(self):
        """
        Public method to start the guided tour.
        This can be called programmatically or connected to a menu/button action.
        """
        self.guided_tour.start_tour()

    def _add_guided_tour_to_menu(self):
        """
        Add a 'Guided Tour' action to the Help menu.
        """

        # Find the Help menu
        menu_bar = self.menuBar()
        help_menu = None
        for action in menu_bar.actions():
            if action.text() == "Help":
                help_menu = action.menu()
                break

        if help_menu:
            # Add separator before the tour action
            help_menu.addSeparator()

            # Create and add the guided tour action
            tour_action = QAction("Start Guided Tour", self)
            tour_action.setIcon(material_icon("help"))
            tour_action.triggered.connect(self.start_guided_tour)
            tour_action.setShortcut("F1")  # Add keyboard shortcut
            help_menu.addAction(tour_action)

    def cleanup(self):
        for view_id, idx in self._view_index.items():
            view = self.stack.widget(idx)
            view.close()
            view.deleteLater()
        super().cleanup()


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
    app.setApplicationName("BEC")
    apply_theme("dark")
    w = BECMainApp(show_examples=args.examples)

    screen_geometry = available_screen_geometry()
    if screen_geometry is not None:
        width, height = main_app_size_for_screen(screen_geometry)
        apply_centered_size(w, width, height, available=screen_geometry)
    else:
        w.resize(w.minimumSizeHint())

    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
