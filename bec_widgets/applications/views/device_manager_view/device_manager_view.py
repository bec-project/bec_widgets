"""Module for Device Manager View."""

from qtpy.QtCore import QRect
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
        view_id: str | None = None,
        title: str | None = None,
        **kwargs,
    ):
        super().__init__(
            parent=parent,
            content=content,
            view_id=view_id,
            title=title,
            rpc_passthrough_children=False,
            **kwargs,
        )
        self.device_manager_widget = DeviceManagerWidget(
            parent=self, rpc_exposed=False, rpc_passthrough_children=False
        )
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

        # The device_manager_widget is not yet initialized, so we will register
        # tour steps for its uninitialized state.

        # Register Load Current Config button
        def get_load_current():
            main_app.set_current("device_manager")
            if dm_widget._initialized is True:
                return (None, None)
            return (dm_widget.button_load_current_config, None)

        step_id = guided_tour.register_widget(
            widget=get_load_current,
            title="Load Current Config",
            text="Load the current device configuration from the BEC server.",
        )
        step_ids.append(step_id)

        # Register Load Config From File button
        def get_load_file():
            main_app.set_current("device_manager")
            if dm_widget._initialized is True:
                return (None, None)
            return (dm_widget.button_load_config_from_file, None)

        step_id = guided_tour.register_widget(
            widget=get_load_file,
            title="Load Config From File",
            text="Load a device configuration from a YAML file on disk.",
        )
        step_ids.append(step_id)

        ## Register steps for the initialized state
        # Register main device table
        def get_device_table():
            main_app.set_current("device_manager")
            if dm_widget._initialized is False:
                return (None, None)
            return (dm_widget.device_manager_display.device_table_view, None)

        step_id = guided_tour.register_widget(
            widget=get_device_table,
            title="Device Table",
            text="This table displays the config that is prepared to be uploaded to the BEC server. It allows users to review and modify device config settings, and also validate them before uploading to the BEC server.",
        )
        step_ids.append(step_id)

        col_text_mapping = {
            0: "Shows if a device configuration is valid. Automatically validated when adding a new device.",
            1: "Shows if a device is connectable. Validated on demand.",
            2: "Device name, unique across all devices within a config.",
            3: "Device class used to initialize the device on the BEC server.",
            4: "Defines how BEC treats readings of the device during scans. The options are 'monitored', 'baseline', 'async', 'continuous' or 'on_demand'.",
            5: "Defines how BEC reacts if a device readback fails. Options are 'raise', 'retry', or 'buffer'.",
            6: "User-defined tags associated with the device.",
            7: "A brief description of the device.",
            8: "Device is enabled when the configuration is loaded.",
            9: "Device is set to read-only.",
            10: "This flag allows to configure if the 'trigger' method of the device is called during scans.",
        }

        # We have at least one device registered
        def get_device_table_row(column: int):
            main_app.set_current("device_manager")
            if dm_widget._initialized is False:
                return (None, None)
            table = dm_widget.device_manager_display.device_table_view.table
            header = table.horizontalHeader()
            x = header.sectionViewportPosition(column)
            table.horizontalScrollBar().setValue(x)
            # Recompute after scrolling
            x = header.sectionViewportPosition(column)
            w = header.sectionSize(column)
            h = header.height()
            rect = QRect(x, 0, w, h)
            top_left = header.viewport().mapTo(main_app, rect.topLeft())

            return (QRect(top_left, rect.size()), col_text_mapping.get(column, ""))

        for col, text in col_text_mapping.items():
            step_id = guided_tour.register_widget(
                widget=lambda col=col: get_device_table_row(col),
                title=f"{dm_widget.device_manager_display.device_table_view.table.horizontalHeaderItem(col).text()}",
                text=text,
            )
            step_ids.append(step_id)

        if not step_ids:
            return None

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
        view_id="device_manager",
        widget=device_manager_view.device_manager_widget,
        mini_text="DM",
    )
    _app.show()
    sys.exit(app.exec_())
