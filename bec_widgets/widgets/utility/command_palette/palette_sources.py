"""Command sources of the BEC main app's command palette.

A source is a callable returning :class:`PaletteCommand` objects. Sources run every time the
palette opens, so they always reflect the current menus, workspaces and devices. Views of the
main app contribute their own commands by implementing ``palette_commands()``.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, Iterable

from bec_lib import messages
from bec_lib.device import Positioner
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject
from qtpy.QtGui import QAction, QKeySequence
from qtpy.QtWidgets import QApplication, QMenu, QMenuBar

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.name_utils import pascal_to_title
from bec_widgets.widgets.utility.command_palette.palette_core import PaletteCommand
from bec_widgets.widgets.utility.command_palette.palette_intents import (
    DeviceIntent,
    parse_intent,
    resolve_device,
    units_match,
)

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.applications.main_app import BECMainApp
    from bec_widgets.utils.bec_widget import BECWidget
    from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea

logger = bec_logger.logger

# candidates listed when a typed device name matches several devices
MAX_CANDIDATES = 5


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
    current_index = app.stack.currentIndex()
    for view_id in app._view_index:  # pylint: disable=protected-access
        if app._view_index[view_id] == current_index:  # pylint: disable=protected-access
            continue  # going to the view on screen does nothing
        view = app.stack.widget(app._view_index[view_id])  # pylint: disable=protected-access
        item = app.sidebar.components.get(view_id)
        title = getattr(view, "view_title", None) or view_id
        commands.append(
            PaletteCommand(
                uid=f"view:{view_id}",
                title=f"Go to {title}",
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
                    callback=lambda t=widget_type: add_widget(t),
                    category="widgets",
                    icon=icon,
                    keywords=f"add new dock {group} {widget_type} {pascal_to_title(widget_type)}",
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
                subtitle="Current workspace" if name == current else "",
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
                keywords=f"{device_class} {priority} {' '.join(map(str, tags))} {description}",
                hint="Add box" if positioner else "Plot",
            )
        )
    return commands


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


class DeviceState:
    """What a typed command needs to know about one device, read from the BEC caches."""

    def __init__(self, name: str, device):
        self.name = name
        self.device = device
        self.positioner = isinstance(device, Positioner)
        self.enabled = bool(getattr(device, "enabled", True))
        self.precision = self._precision(device)
        self.egu = self._egu(device) if self.positioner else ""
        self.limits = self._limits(device) if self.positioner else None
        self.position = self.read_position()

    @staticmethod
    def _precision(device) -> int:
        try:
            return max(0, min(int(getattr(device, "precision", 3)), 6))
        except (TypeError, ValueError):
            return 3

    @staticmethod
    def _egu(device) -> str:
        try:
            return str(device.egu() or "")
        except Exception:  # pylint: disable=broad-except
            return ""

    @staticmethod
    def _limits(device) -> tuple[float, float] | None:
        try:
            low, high = (_number(v) for v in device.limits)
        except Exception:  # pylint: disable=broad-except
            return None
        # BEC reports [0, 0] for a device without limits
        if low is None or high is None or low == high:
            return None
        return min(low, high), max(low, high)

    def read_position(self, signals: dict | None = None) -> float | None:
        """Readback value from a cached read or from a readback message's ``signals``."""
        if signals is None:
            try:
                signals = self.device.read(cached=True) or {}
            except Exception:  # pylint: disable=broad-except
                return None
        hints = list(getattr(self.device, "_hints", None) or [])
        for key in [*hints[:1], self.name, f"{self.name}_user_readback"]:
            value = _number((signals.get(key) or {}).get("value"))
            if value is not None:
                return value
        return None

    def fmt(self, value: float, sign: bool = False) -> str:
        """``value`` at the device precision, with the unit; a typographic minus."""
        text = f"{value:+.{self.precision}f}" if sign else f"{value:.{self.precision}f}"
        text = text.replace("-", "\u2212")
        return f"{text} {self.egu}" if self.egu else text

    def limits_text(self) -> str:
        """``"limits −10 … 10"``, or an empty string without limits."""
        if self.limits is None:
            return ""
        low, high = (f"{v:.{self.precision}f}".replace("-", "\u2212") for v in self.limits)
        return f"limits {low} \u2026 {high}"


class DeviceCommandSource(QObject):
    """Turns typed device commands (``samx 10``, ``samx?``, ``stop samx``) into palette rows.

    Each row previews exactly what Enter does. A move outside the limits, on a disabled device,
    on a device that is not a motor or with a unit the device does not use is listed with the
    reason and does nothing on Enter. Moves and stops are sent from a worker thread with the
    same calls the Device Box uses.

    Args:
        widget(BECWidget): Widget whose BEC client and worker pool the commands use.
        parent(QObject | None): Parent object.
    """

    def __init__(self, widget: BECWidget, parent: QObject | None = None):
        super().__init__(parent)
        self.widget = widget

    def _devices(self) -> dict:
        client = getattr(self.widget, "client", None)
        manager = getattr(client, "device_manager", None)
        return getattr(manager, "devices", None) or {}

    def __call__(self, query: str, scope: str) -> list[PaletteCommand]:
        if scope not in ("all", "devices"):
            return []
        intent = parse_intent(query)
        if intent is None:
            return []
        devices = self._devices()
        # with "@", partial names such as "sax" are matched; searching everything, a word only
        # counts as a device when it is a device name or starts the name of a motor
        names = resolve_device(intent.device, devices.keys(), fuzzy=scope == "devices")
        if scope != "devices" and names != [intent.device]:
            names = [n for n in names if isinstance(devices[n], Positioner)]
        if not names:
            return []
        if len(names) == 1:
            return [self._command(intent, DeviceState(names[0], devices[names[0]]))]
        shown = names[:MAX_CANDIDATES]
        more = f", showing the best {len(shown)}" if len(names) > len(shown) else ""
        header = PaletteCommand(
            uid="intent:ambiguous",
            title=f"\u201c{intent.device}\u201d matches {len(names)} devices",
            subtitle=f"Choose one with \u2191\u2193{more}",
            callback=lambda: None,
            category="devices",
            icon="help",
            hint="",
            enabled=False,
        )
        return [header] + [
            self._command(intent, DeviceState(name, devices[name])) for name in shown
        ]

    # ------------------------------------------------------------------ rows
    def _command(self, intent: DeviceIntent, state: DeviceState) -> PaletteCommand:
        if intent.kind == "where":
            return self._where_command(state)
        if intent.kind == "stop":
            return self._stop_command(state)
        return self._move_command(intent, state)

    def _move_command(self, intent: DeviceIntent, state: DeviceState) -> PaletteCommand:
        name, value = state.name, float(intent.value)
        target = value
        if intent.relative:
            target = state.position + value if state.position is not None else None
            title = f"Move {name} by {state.fmt(value, sign=True)}"
        else:
            title = f"Move {name} to {state.fmt(value)}"

        if state.position is None:
            now = "position unknown"
        elif intent.relative and target is not None:
            now = f"now {state.fmt(state.position)} \u2192 {state.fmt(target)}"
        else:
            now = f"now {state.fmt(state.position)}"
        details = [now, state.limits_text()]
        reason = self._refusal(intent, state, target)
        return PaletteCommand(
            uid=f"intent:move:{name}",
            title=title,
            subtitle=reason or " \u00b7 ".join(part for part in details if part),
            callback=lambda: self._move(name, value, intent.relative),
            category="devices",
            icon="block" if reason else "open_with",
            hint="Move",
            enabled=not reason,
            tone="danger" if reason else "",
        )

    @staticmethod
    def _refusal(  # pylint: disable=too-many-return-statements
        intent: DeviceIntent, state: DeviceState, target: float | None
    ) -> str:
        """Why the move is not offered, or an empty string."""
        name = state.name
        if not state.positioner:
            return f"{name} is not a motor"
        if not state.enabled:
            return f"{name} is disabled"
        if intent.unit:
            if not state.egu:
                return f"{name} reports no unit, leave out \u201c{intent.unit}\u201d"
            if not units_match(intent.unit, state.egu):
                return f"{name} is in {state.egu}, not {intent.unit}"
        if state.limits is not None:
            if target is None:
                return f"{name} has no position to move from"
            low, high = state.limits
            if not low <= target <= high:
                return f"{state.fmt(target)} is outside the {state.limits_text()}"
        return ""

    def _where_command(self, state: DeviceState) -> PaletteCommand:
        name = state.name
        if state.position is None:
            title, enabled = f"{name}: no position", False
        else:
            title, enabled = f"{name} is at {state.fmt(state.position)}", True
        text = "" if state.position is None else f"{state.position:.{state.precision}f}"
        return PaletteCommand(
            uid=f"intent:where:{name}",
            title=title,
            subtitle=state.limits_text(),
            callback=lambda: QApplication.clipboard().setText(text),
            category="devices",
            icon="my_location",
            hint="Copy",
            enabled=enabled,
        )

    def _stop_command(self, state: DeviceState) -> PaletteCommand:
        name = state.name
        return PaletteCommand(
            uid=f"intent:stop:{name}",
            title=f"Stop {name}",
            subtitle=f"now {state.fmt(state.position)}" if state.position is not None else "",
            callback=lambda: self._stop(name),
            category="devices",
            icon="stop_circle",
            hint="Stop",
        )

    # ------------------------------------------------------------------ actions
    def _move(self, name: str, value: float, relative: bool) -> None:
        self.widget.submit_task(self._send_move, name, value, relative, on_failed=self._on_failed)

    def _send_move(self, name: str, value: float, relative: bool) -> None:
        client = self.widget.client
        client.scans.mv(client.device_manager.devices[name], value, relative=relative)

    def _stop(self, name: str) -> None:
        self.widget.submit_task(self._send_stop, name, on_failed=self._on_failed)

    def _send_stop(self, name: str) -> None:
        msg = messages.VariableMessage(value=[name])
        self.widget.client.connector.send(MessageEndpoints.stop_devices(), msg)

    @SafeSlot(str)
    def _on_failed(self, error: str) -> None:
        logger.error(f"Command palette device command failed: {error}")
