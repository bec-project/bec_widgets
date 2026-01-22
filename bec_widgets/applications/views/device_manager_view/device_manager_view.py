"""Module for Device Manager View."""

from qtpy.QtWidgets import QWidget

from bec_widgets.applications.views.device_manager_view.device_manager_widget import (
    DeviceManagerWidget,
)
from bec_widgets.applications.views.view import ViewBase, ViewTourSteps
from bec_widgets.utils.error_popups import SafeSlot


class DeviceManagerView(ViewBase):
    """
    A view for users to manage devices within the application.
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
        self.device_manager_widget = DeviceManagerWidget(parent=self)
        self.set_content(self.device_manager_widget)

    @SafeSlot()
    def on_enter(self) -> None:
        """Called after the view becomes current/visible.

        Default implementation does nothing. Override in subclasses.
        """
        self.device_manager_widget.on_enter()

    def register_tour_steps(self, guided_tour, main_app) -> ViewTourSteps | None:
        """Register Device Manager components with the guided tour.

        Args:
            guided_tour: The GuidedTour instance to register with.
            main_app: The main application instance (for accessing set_current).

        Returns:
            ViewTourSteps | None: Model containing view title and step IDs.
        """
        step_ids = []
        dm_widget = self.device_manager_widget

        # Register Load Current Config button
        def get_load_current():
            main_app.set_current("device_manager")
            return (dm_widget.button_load_current_config, None)

        step_id = guided_tour.register_widget(
            widget=get_load_current,
            title="Load Current Config",
            text="Load the current device configuration from the BEC server. This will display all available devices and their current status.",
        )
        step_ids.append(step_id)

        # Register Load Config From File button
        def get_load_file():
            main_app.set_current("device_manager")
            return (dm_widget.button_load_config_from_file, None)

        step_id = guided_tour.register_widget(
            widget=get_load_file,
            title="Load Config From File",
            text="Load a device configuration from a YAML file on disk. Useful for testing or working offline.",
        )
        step_ids.append(step_id)

        return ViewTourSteps(view_title="Device Manager", step_ids=step_ids)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_qthemes import apply_theme
    from qtpy.QtWidgets import QApplication

    from bec_widgets.applications.main_app import BECMainApp

    app = QApplication(sys.argv)
    apply_theme("dark")

    _app = BECMainApp()
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

    _app.resize(width, height)
    device_manager_view = DeviceManagerView()
    _app.add_view(
        icon="display_settings",
        title="Device Manager",
        id="device_manager",
        widget=device_manager_view.device_manager_widget,
        mini_text="DM",
    )
    _app.show()
    sys.exit(app.exec_())
