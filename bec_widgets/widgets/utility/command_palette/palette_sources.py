"""Command sources of the BEC main app's command palette.

A source is a callable returning :class:`PaletteCommand` objects. Sources run every time the
palette opens, so they always reflect the current menus, workspaces and devices. Views of the
main app contribute their own commands by implementing ``palette_commands()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Iterable

from bec_lib.device import Positioner
from qtpy.QtGui import QAction, QKeySequence
from qtpy.QtWidgets import QMenu, QMenuBar

from bec_widgets.utils.name_utils import pascal_to_title
from bec_widgets.widgets.utility.command_palette.palette_core import PaletteCommand

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.applications.main_app import BECMainApp
    from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea


def _clean(text: str) -> str:
    return text.replace("&&", "\x00").replace("&", "").replace("\x00", "&").strip()


def _shortcut(action: QAction) -> str:
    shortcut = action.shortcut()
    if shortcut.isEmpty():
        return ""
    return shortcut.toString(QKeySequence.SequenceFormat.NativeText)


def menu_commands(menu_bar: QMenuBar, skip: Iterable[QAction] = ()) -> list[PaletteCommand]:
    """Turn every enabled, visible menu bar action into a command.

    Args:
        menu_bar(QMenuBar): Menu bar to walk, including sub-menus.
        skip(Iterable[QAction]): Actions to leave out, e.g. the one opening the palette.

    Returns:
        list[PaletteCommand]: One command per action, titled ``"<Menu> › <Action>"``.
    """
    skipped = set(skip)
    commands: list[PaletteCommand] = []

    def walk(menu: QMenu, path: list[str]) -> None:
        for action in menu.actions():
            if action.isSeparator() or not action.isVisible() or action in skipped:
                continue
            text = _clean(action.text())
            if action.menu() is not None:
                walk(action.menu(), [*path, text])
                continue
            if not text or not action.isEnabled():
                continue
            state = ""
            if action.isCheckable():
                state = " · on" if action.isChecked() else " · off"
            commands.append(
                PaletteCommand(
                    uid=f"menu:{'/'.join(path)}/{text}",
                    title=text,
                    subtitle=f"{' › '.join(path)} menu{state}",
                    callback=action.trigger,
                    category="actions",
                    icon="toggle_on" if action.isCheckable() else "menu",
                    shortcut=_shortcut(action),
                    keywords=" ".join(path),
                )
            )

    for top_action in menu_bar.actions():
        if top_action.menu() is not None and top_action.isVisible():
            walk(top_action.menu(), [_clean(top_action.text())])
    return commands


def main_app_commands(app: BECMainApp) -> list[PaletteCommand]:
    """Navigation between the app's views, app-level actions and the views' own commands."""
    commands: list[PaletteCommand] = []
    for view_id in app._view_index:  # pylint: disable=protected-access
        view = app.stack.widget(app._view_index[view_id])  # pylint: disable=protected-access
        item = app.sidebar.components.get(view_id)
        title = getattr(view, "view_title", None) or view_id
        commands.append(
            PaletteCommand(
                uid=f"view:{view_id}",
                title=f"Go to {title}",
                subtitle="View",
                callback=lambda vid=view_id: app.set_current(vid),
                category="navigate",
                icon=getattr(item, "_icon_name", None) or "view_quilt",
                keywords="open switch show view page",
                hint="Open",
            )
        )
    commands.append(
        PaletteCommand(
            uid="app:toggle_sidebar",
            title="Toggle Sidebar",
            subtitle="Expand or collapse the navigation sidebar",
            callback=app.sidebar.toggle.click,
            category="actions",
            icon="side_navigation",
            keywords="navigation menu collapse expand",
        )
    )
    theme = getattr(getattr(app, "app", None), "theme", None)
    current = str(getattr(theme, "theme", "dark")).lower()
    target = "light" if "dark" in current else "dark"
    commands.append(
        PaletteCommand(
            uid="app:toggle_theme",
            title=f"Switch to {target.title()} Theme",
            subtitle="Appearance",
            callback=lambda: app.change_theme(target),
            category="actions",
            icon="light_mode" if target == "light" else "dark_mode",
            keywords="theme dark light mode colour color appearance",
        )
    )
    for view_id in app._view_index:  # pylint: disable=protected-access
        view = app.stack.widget(app._view_index[view_id])  # pylint: disable=protected-access
        for owner in (view, getattr(view, "content", None)):
            provider: Callable[[], Iterable[PaletteCommand]] | None = getattr(
                owner, "palette_commands", None
            )
            if callable(provider):
                commands.extend(provider())
                break
    return commands


def _config_value(device, key: str, default=None):
    config = getattr(device, "_config", None)
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


def dock_area_commands(
    dock_area: BECDockArea, activate: Callable[[], None]
) -> list[PaletteCommand]:
    """Commands that add widgets to the dock area and manage its workspaces.

    Args:
        dock_area(BECDockArea): The dock area the commands act on.
        activate(Callable[[], None]): Shows the view holding the dock area before acting.
    """
    commands: list[PaletteCommand] = []

    def add_widget(widget_type: str) -> None:
        activate()
        dock_area.new(widget=widget_type)

    for group, mapping in dock_area.widget_catalog().items():
        for icon, label, widget_type in mapping.values():
            commands.append(
                PaletteCommand(
                    uid=f"widget:{widget_type}",
                    title=label.strip(),
                    subtitle=f"Add to dock area · {group}",
                    callback=lambda t=widget_type: add_widget(t),
                    category="widgets",
                    icon=icon,
                    keywords=f"add new dock {widget_type} {pascal_to_title(widget_type)}",
                    hint="Add",
                )
            )

    def load(name: str) -> None:
        activate()
        dock_area.load_profile(name)

    current = getattr(dock_area, "_current_profile_name", None)
    for name in dock_area.list_profiles():
        commands.append(
            PaletteCommand(
                uid=f"workspace:{name}",
                title=name,
                subtitle="Current workspace" if name == current else "Open workspace",
                callback=lambda n=name: load(n),
                category="workspaces",
                icon="space_dashboard",
                keywords="workspace profile layout load open",
                hint="Open",
            )
        )
    locked = dock_area.workspace_is_locked
    workspace_actions = [
        ("save", "Save Workspace As…", "save", dock_area.save_profile_dialog, "store profile"),
        ("manage", "Manage Workspaces", "tune", dock_area.show_workspace_manager, "profiles"),
        (
            "lock",
            "Unlock Workspace" if locked else "Lock Workspace",
            "lock_open" if locked else "lock",
            lambda: setattr(dock_area, "workspace_is_locked", not locked),
            "freeze edit layout",
        ),
    ]
    for key, title, icon, func, keywords in workspace_actions:
        commands.append(
            PaletteCommand(
                uid=f"workspace_action:{key}",
                title=title,
                subtitle="Workspace",
                callback=lambda f=func: (activate(), f()),
                category="actions",
                icon=icon,
                keywords=f"workspace {keywords}",
            )
        )
    return commands


def device_commands(dock_area: BECDockArea, activate: Callable[[], None]) -> list[PaletteCommand]:
    """One command per device: positioners open a device box, others a waveform plot."""
    client = getattr(dock_area, "client", None)
    manager = getattr(client, "device_manager", None)
    devices = getattr(manager, "devices", None)
    if not devices:
        return []

    def open_positioner(name: str) -> None:
        activate()
        dock_area.new(widget="PositionerBox", device=name)

    def plot(name: str) -> None:
        activate()
        waveform = dock_area.new(widget="Waveform")
        waveform.plot(device_y=name)

    commands = []
    for name in sorted(devices.keys()):
        device = devices[name]
        positioner = isinstance(device, Positioner)
        device_class = str(_config_value(device, "deviceClass", "") or "")
        short_class = device_class.rsplit(".", 1)[-1]
        priority = str(_config_value(device, "readoutPriority", "") or "")
        enabled = bool(getattr(device, "enabled", True))
        tags = _config_value(device, "deviceTags", None) or ()
        description = str(_config_value(device, "description", "") or "")
        details = [short_class or ("Positioner" if positioner else "Device")]
        if priority:
            details.append(priority)
        if not enabled:
            details.append("disabled")
        commands.append(
            PaletteCommand(
                uid=f"device:{name}",
                title=name,
                subtitle=" · ".join(details),
                callback=(
                    (lambda n=name: open_positioner(n)) if positioner else (lambda n=name: plot(n))
                ),
                category="devices",
                icon="open_with" if positioner else "sensors",
                keywords=f"{device_class} {' '.join(map(str, tags))} {description}",
                hint="Move" if positioner else "Plot",
            )
        )
    return commands
