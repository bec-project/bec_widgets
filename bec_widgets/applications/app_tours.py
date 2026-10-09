"""Task tours of the BEC main app for the tour guide (``BEC_TOUR_UI=qwidget|qml``).

Each tour covers one task in three to six steps. Views can add their own tours by implementing
``guide_tours(main_app) -> list[Tour]``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bec_widgets.utils.tour_guide.model import Tour, TourStep

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.applications.main_app import BECMainApp


def _toolbar_component(app: BECMainApp, name: str):
    """Lazily look up a component of the dock area toolbar (the toolbar is rebuilt at times)."""

    def resolve():
        dock_area = getattr(app.dock_area, "dock_area", None)
        if dock_area is None or not dock_area.toolbar.components.exists(name):
            return None
        component = dock_area.toolbar.components.get_action(name)
        return getattr(component, "widget", None) or component

    return resolve


def view_id_of(app: BECMainApp, view: object) -> str | None:
    """Id under which ``view`` was added to the app (ids derive from the sidebar labels)."""
    if view is None:
        return None
    index = app.stack.indexOf(view)
    for view_id, view_index in app._view_index.items():  # pylint: disable=protected-access
        if view_index == index:
            return view_id
    return None


def app_tours(app: BECMainApp) -> list[Tour]:
    """The built-in tours of the main app."""
    docks = view_id_of(app, app.dock_area)
    devices = view_id_of(app, app.device_manager)
    tours = [
        Tour(
            id="first_steps",
            title="Find your way around",
            summary="The sidebar, the status bar and where to get help.",
            icon="explore",
            order=0,
            steps=[
                TourStep(
                    title="Views",
                    text=(
                        "Each entry is a full view: Docks for plots and device controls, the"
                        " Device Manager for configurations. Your work in a view stays put"
                        " when you switch."
                    ),
                    target=app.sidebar,
                    hint="Click the arrow at the top to show the names.",
                ),
                TourStep(
                    title="Server messages",
                    text="Messages from the BEC server appear here. Hover for the full text.",
                    target=lambda: getattr(app, "_client_info_hover", None),
                ),
                TourStep(
                    title="Scan progress",
                    text="Progress of the running scan, with elapsed and remaining time on hover.",
                    target=lambda: getattr(app, "_scan_progress_hover", None),
                ),
                TourStep(
                    title="Notifications",
                    text="Errors and warnings are collected here, so none get lost.",
                    target=lambda: getattr(app, "notification_indicator", None),
                    hint="Click to filter by type.",
                ),
                TourStep(
                    title="Light or dark",
                    text="Switch the theme. BEC remembers your choice.",
                    target=lambda: app.sidebar.components.get("dark_mode"),
                ),
                TourStep(
                    title="Help is always here",
                    text=(
                        "Open the tours again from here or with F1. Shift+F1 turns on"
                        " What's this?, which explains any control you click."
                    ),
                    target=lambda: app.sidebar.components.get("help"),
                ),
            ],
        ),
        Tour(
            id="workspace",
            title="Build a workspace",
            summary="Add plots and device controls, then save the layout as a profile.",
            icon="dashboard_customize",
            view=docks,
            order=10,
            steps=[
                TourStep(
                    title="Add a plot",
                    text="Waveforms, images, heatmaps and more. Each one opens as a dock.",
                    target=_toolbar_component(app, "menu_plots"),
                    view=docks,
                    hint="Open the menu and pick Waveform.",
                ),
                TourStep(
                    title="Add device controls",
                    text="Motor boxes, scan control and other controls go next to your plots.",
                    target=_toolbar_component(app, "menu_devices"),
                    view=docks,
                ),
                TourStep(
                    title="Add utilities",
                    text="Queue, logs, terminals and other tools.",
                    target=_toolbar_component(app, "menu_utils"),
                    view=docks,
                ),
                TourStep(
                    title="Arrange",
                    text=(
                        "Drag a dock's title bar to move it. Drop it on an edge to split, or on"
                        " another dock to make tabs."
                    ),
                    target=lambda: getattr(
                        getattr(app.dock_area, "dock_area", None), "dock_manager", None
                    ),
                    view=docks,
                ),
                TourStep(
                    title="Save as a profile",
                    text=(
                        "Save the layout as a profile and switch between profiles here. BEC"
                        " reopens the last one on start."
                    ),
                    target=_toolbar_component(app, "workspace_combo"),
                    view=docks,
                ),
            ],
        ),
        Tour(
            id="device_config",
            title="Load and check a device config",
            summary="Load the session's devices, review them and check they connect.",
            icon="display_settings",
            view=devices,
            order=20,
            steps=[
                TourStep(
                    title="Start from the running session",
                    text="Loads the configuration the BEC server is using right now.",
                    target=lambda: _dm_widget(app, "button_load_current_config"),
                    view=devices,
                    hint="Click it to fill the table.",
                ),
                TourStep(
                    title="Or from a file",
                    text="Opens a YAML configuration from disk instead.",
                    target=lambda: _dm_widget(app, "button_load_config_from_file"),
                    view=devices,
                ),
                TourStep(
                    title="Review the devices",
                    text=(
                        "One row per device. The first two columns show whether its config is"
                        " valid and whether it connects; Readout priority decides when BEC"
                        " reads it during a scan."
                    ),
                    target=lambda: _dm_table(app),
                    view=devices,
                ),
            ],
        ),
    ]
    developer = getattr(app, "developer_view", None)
    if developer is not None:
        widget = developer.developer_widget
        ide = view_id_of(app, developer)
        tours.append(
            Tour(
                id="macros",
                title="Write and run a macro",
                summary="Edit a script, run it and see its plots.",
                icon="code_blocks",
                view=ide,
                order=30,
                steps=[
                    TourStep(
                        title="Your files",
                        text="Macros and scripts live here. Create a file or open one.",
                        target=widget.explorer_dock.widget,
                        view=ide,
                    ),
                    TourStep(
                        title="Editor",
                        text="Python with completion and signature help.",
                        target=widget.monaco_dock.widget,
                        view=ide,
                    ),
                    TourStep(
                        title="Run",
                        text="Save and run the file from the toolbar.",
                        target=widget.toolbar,
                        view=ide,
                    ),
                    TourStep(
                        title="Console",
                        text="An IPython shell connected to BEC, for quick commands.",
                        target=widget.console_dock.widget,
                        view=ide,
                    ),
                    TourStep(
                        title="Plots",
                        text="Plots your scripts create appear here.",
                        target=widget.plotting_ads,
                        view=ide,
                    ),
                ],
            )
        )
    return tours


def _dm_widget(app: BECMainApp, name: str):
    widget = getattr(app.device_manager, "device_manager_widget", None)
    if widget is None or getattr(widget, "_initialized", False):
        return None
    return getattr(widget, name, None)


def _dm_table(app: BECMainApp):
    widget = getattr(app.device_manager, "device_manager_widget", None)
    if widget is None or not getattr(widget, "_initialized", False):
        return None
    return widget.device_manager_display.device_table_view
