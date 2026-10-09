"""Human names, categories and descriptions of the widgets offered by the dock area.

The Python class names stay the API (RPC, profiles, object names). Everything the user reads in
the dock area, the dock titles and the Add widget gallery comes from this catalog instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CATEGORIES = ("Plots", "Device control", "Scans & status", "Tools", "Plugins")

Placement = Literal["beside", "below", "tab", "column", "floating"]

PLACEMENTS: tuple[tuple[str, str, str], ...] = (
    ("beside", "Beside", "Right of the selected widget"),
    ("below", "Below", "Under the selected widget"),
    ("tab", "As tab", "In the same group as the selected widget"),
    ("column", "New column", "A new column at the right edge"),
    ("floating", "Floating", "In its own window"),
)


@dataclass(frozen=True)
class WidgetEntry:
    """One widget the user can add to a dock area.

    Args:
        widget_class(str): Registered class name used with ``BECDockArea.new``.
        name(str): Human name shown in the gallery and used for dock titles.
        category(str): One of :data:`CATEGORIES`.
        description(str): One line saying what the widget is for.
        icon(str): Material icon name.
        keywords(tuple[str, ...]): Extra search words, e.g. today's or older names.
        new_kwargs(dict): Extra keyword arguments passed to ``new``.
    """

    widget_class: str
    name: str
    category: str
    description: str
    icon: str
    keywords: tuple[str, ...] = ()
    new_kwargs: dict = field(default_factory=dict, hash=False, compare=False)

    def matches(self, query: str) -> bool:
        """Return True when every word of ``query`` occurs in the name, description or keywords."""
        words = query.lower().split()
        if not words:
            return True
        haystack = " ".join(
            (self.name, self.description, self.widget_class, self.category, *self.keywords)
        ).lower()
        return all(word in haystack for word in words)


CORE_WIDGETS: tuple[WidgetEntry, ...] = (
    WidgetEntry(
        "Waveform",
        "Waveform",
        "Plots",
        "Signals against a motor or time, with fits",
        "show_chart",
        ("plot", "curve", "line", "1d"),
    ),
    WidgetEntry(
        "ScatterWaveform",
        "Scatter Plot",
        "Plots",
        "Points coloured by a third signal",
        "scatter_plot",
        ("scatter waveform", "2d"),
    ),
    WidgetEntry(
        "MultiWaveform",
        "Multi Waveform",
        "Plots",
        "Many traces of one monitor, newest on top",
        "ssid_chart",
        ("traces", "history"),
    ),
    WidgetEntry(
        "Image",
        "Image",
        "Plots",
        "Live camera or detector image",
        "image",
        ("camera", "detector", "2d"),
    ),
    WidgetEntry(
        "Heatmap",
        "Heatmap",
        "Plots",
        "Grid scans as a colour map",
        "dataset",
        ("grid", "map", "2d"),
    ),
    WidgetEntry(
        "MotorMap",
        "Motor Map",
        "Plots",
        "Trail of two motors' positions",
        "my_location",
        ("trajectory", "xy"),
    ),
    WidgetEntry(
        "ScanControl",
        "Scan Control",
        "Device control",
        "Set up, start and stop scans",
        "tune",
        ("start", "scan", "acquire"),
    ),
    WidgetEntry(
        "PositionerBox",
        "Motor",
        "Device control",
        "Move one motor and watch its position",
        "switch_right",
        ("device box", "positioner", "move"),
    ),
    WidgetEntry(
        "PositionerBox2D",
        "2D Motor",
        "Device control",
        "Move two motors with a joystick pad",
        "open_with",
        ("device 2d box", "positioner", "xy"),
    ),
    WidgetEntry(
        "BECQueue",
        "Scan Queue",
        "Scans & status",
        "Running and waiting scans",
        "edit_note",
        ("queue",),
    ),
    WidgetEntry(
        "ScanProgressBar",
        "Scan Progress",
        "Scans & status",
        "Progress and time left of the running scan",
        "timelapse",
        ("progress", "bar"),
    ),
    WidgetEntry(
        "RingProgressBar",
        "Ring Progress",
        "Scans & status",
        "Concentric rings for scan and device progress",
        "track_changes",
        ("circular progressbar", "ring"),
    ),
    WidgetEntry(
        "BECStatusBox",
        "Service Status",
        "Scans & status",
        "Health of the BEC services",
        "monitor_heart",
        ("bec status box", "services"),
    ),
    WidgetEntry(
        "BeamlineStateManager",
        "Beamline States",
        "Scans & status",
        "Beamline conditions and their interlocks",
        "format_list_bulleted",
        ("beamline state manager", "interlock"),
    ),
    WidgetEntry(
        "LogPanel",
        "Logs",
        "Tools",
        "Messages from the BEC services",
        "browse_activity",
        ("log panel", "messages"),
    ),
    WidgetEntry(
        "BECShell",
        "BEC Command Line",
        "Tools",
        "The bec client, connected to this window",
        "hub",
        ("bec shell", "ipython", "console"),
        {"show_settings_action": False},
    ),
    WidgetEntry(
        "BecConsole",
        "System Terminal",
        "Tools",
        "A shell on this computer",
        "terminal",
        ("terminal", "bash"),
        {"startup_cmd": None},
    ),
    WidgetEntry(
        "SBBMonitor",
        "Departures",
        "Tools",
        "Bus and train departures near PSI",
        "train",
        ("sbb monitor", "train", "bus"),
    ),
)

_BY_CLASS: dict[str, WidgetEntry] = {entry.widget_class: entry for entry in CORE_WIDGETS}


def _title_from_class(name: str) -> str:
    from bec_widgets.utils.name_utils import pascal_to_title

    return pascal_to_title(name)


def plugin_entries() -> tuple[WidgetEntry, ...]:
    """Return gallery entries for widgets provided by beamline plugins."""
    try:
        from bec_widgets.utils.bec_plugin_helper import (
            get_plugin_rpc_widget_registry,
            get_plugin_widget_icons,
        )
        from bec_widgets.utils.plugin_utils import get_rpc_widget_registry

        plugin_registry = get_plugin_rpc_widget_registry()
        internal_registry = get_rpc_widget_registry()
        icons = get_plugin_widget_icons()
    except Exception:  # pragma: no cover - plugin discovery must never break the dock area
        return ()
    return tuple(
        WidgetEntry(
            name,
            _title_from_class(name),
            "Plugins",
            "Provided by a beamline plugin",
            icons.get(name, "widgets"),
        )
        for name in sorted(plugin_registry)
        if name not in internal_registry and name not in _BY_CLASS
    )


def all_entries(include_plugins: bool = True) -> tuple[WidgetEntry, ...]:
    """All widgets offered by the gallery, core widgets first.

    Args:
        include_plugins(bool): Whether to add widgets from beamline plugins.
    """
    if not include_plugins:
        return CORE_WIDGETS
    return CORE_WIDGETS + plugin_entries()


def entry_for(widget_class: str) -> WidgetEntry | None:
    """Return the catalog entry of a core widget class, if there is one."""
    return _BY_CLASS.get(widget_class)


def display_name(widget_class: str) -> str:
    """Human name of a widget class, e.g. ``PositionerBox`` -> ``Motor``."""
    entry = _BY_CLASS.get(widget_class)
    if entry is not None:
        return entry.name
    return _title_from_class(widget_class)


def unique_title(base: str, taken: set[str]) -> str:
    """Return ``base``, or ``base 2``, ``base 3``... when that title is already taken."""
    if base not in taken:
        return base
    index = 2
    while f"{base} {index}" in taken:
        index += 1
    return f"{base} {index}"


@dataclass(frozen=True)
class StarterLayout:
    """A ready-made arrangement offered on an empty workspace.

    ``steps`` is a sequence of ``(widget_class, placement, anchor_index)`` tuples. The anchor is
    the index of an earlier step, or ``None`` for the first widget.
    """

    name: str
    description: str
    icon: str
    steps: tuple[tuple[str, Placement, int | None], ...]


STARTER_LAYOUTS: tuple[StarterLayout, ...] = (
    StarterLayout(
        "Scanning",
        "Scan Control, a live plot, the queue and scan progress",
        "show_chart",
        (
            ("ScanControl", "column", None),
            ("Waveform", "beside", 0),
            ("BECQueue", "below", 1),
            ("ScanProgressBar", "tab", 2),
        ),
    ),
    StarterLayout(
        "Alignment",
        "A camera image with two motors and their trail",
        "my_location",
        (("Image", "column", None), ("PositionerBox2D", "beside", 0), ("MotorMap", "below", 1)),
    ),
    StarterLayout(
        "Monitoring",
        "Beamline states, service health and logs",
        "monitor_heart",
        (
            ("BeamlineStateManager", "column", None),
            ("BECStatusBox", "below", 0),
            ("LogPanel", "beside", 0),
        ),
    ),
)
