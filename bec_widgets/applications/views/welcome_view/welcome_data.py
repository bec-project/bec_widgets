"""Data shown on the welcome view.

The view only renders a :class:`WelcomeSnapshot`. :func:`demo_snapshot` returns a fixed, realistic
shift so the three design directions can be compared on the same content. A live provider would
fill the same dataclasses from BEC:

* account: ``MessageEndpoints.account()``
* queue and running scan: ``MessageEndpoints.scan_queue_status()`` and ``scan_progress()``
* recent scans: ``MessageEndpoints.scan_history()``
* services: ``MessageEndpoints.service_status(...)`` (as ``BECStatusBox`` does)
* interlock: ``MessageEndpoints.available_beamline_states()`` and ``beamline_state(name)``
* problems: ``MessageEndpoints.alarm()`` and the notification centre
* workspaces: the dock area profile store (``profile_utils``)

Experiment title, beamtime dates and the machine status are not BEC endpoints today; they are
open questions for the design discussion.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass
class Experiment:
    """Who is measuring and on what."""

    beamline: str
    account: str
    title: str
    beamtime: str
    day: str


@dataclass
class Glance:
    """One-line state of a subsystem, shown as a tile or a chip."""

    key: str
    icon: str
    label: str
    value: str
    detail: str
    tone: str


@dataclass
class RunningScan:
    """The scan that is running right now."""

    number: int
    scan_type: str
    summary: str
    sample: str
    done: int
    total: int
    elapsed: str
    remaining: str
    paused: bool = False


@dataclass
class QueuedScan:
    """A scan waiting in the queue."""

    scan_type: str
    summary: str
    sample: str = ""
    estimate: str = ""


@dataclass
class RecentScan:
    """A finished scan with what is needed to jump back to it."""

    number: int
    scan_type: str
    summary: str
    sample: str
    status: str
    tone: str
    duration: str
    finished: str


@dataclass
class Problem:
    """Something that needs a person: an error, a warning, a tripped state."""

    tone: str
    title: str
    text: str
    when: str
    action: str = ""


@dataclass
class Workspace:
    """A saved dock area profile the user can reopen."""

    name: str
    opened: str
    docks: list[str]
    current: bool = False


@dataclass
class QuickAction:
    """A shortcut into another part of the app."""

    icon: str
    title: str
    text: str
    shortcut: str = ""


@dataclass
class Event:
    """One line of the activity feed."""

    time: str
    kind: str  # scan, problem, interlock, config, note, session
    icon: str
    tone: str
    title: str
    text: str = ""
    action: str = ""


@dataclass
class WelcomeSnapshot:
    """Everything the welcome view shows at one moment."""

    experiment: Experiment
    greeting: str
    glances: list[Glance]
    running: RunningScan | None
    queued: list[QueuedScan]
    recent: list[RecentScan]
    problems: list[Problem]
    workspaces: list[Workspace]
    actions: list[QuickAction]
    events: list[Event] = field(default_factory=list)
    away_since: str = ""
    away_summary: list[tuple[str, str, str]] = field(default_factory=list)
    tip: tuple[str, str] = ("", "")


def demo_snapshot() -> WelcomeSnapshot:
    """A realistic evening shift on day three of a beamtime, used for the mockups."""
    return WelcomeSnapshot(
        experiment=Experiment(
            beamline="X12SA · cSAXS",
            account="p20631",
            title="Operando SAXS of battery cathodes",
            beamtime="7 – 10 Oct",
            day="Day 3 of 4",
        ),
        greeting="Good evening",
        glances=[
            Glance("machine", "bolt", "Machine", "401 mA", "Top-up · light available", "success"),
            Glance(
                "interlock", "verified_user", "Scan interlock", "Armed", "2 of 2 valid", "success"
            ),
            Glance(
                "services",
                "monitor_heart",
                "BEC services",
                "All running",
                "1 version mismatch",
                "warning",
            ),
            Glance("queue", "playlist_play", "Queue", "Running", "2 waiting · ~14 min", "info"),
        ],
        running=RunningScan(
            number=1291,
            scan_type="line_scan",
            summary="samx −2 → 2 · 41 pts · 0.5 s",
            sample="LaB6",
            done=25,
            total=41,
            elapsed="0:52",
            remaining="0:33",
        ),
        queued=[
            QueuedScan("grid_scan", "samx −5 → 5 (41) · samy −2 → 2 (11)", "LaB6", "~11 min"),
            QueuedScan("line_scan", "mono_energy 12.3 → 12.5 keV · 101 pts", "", "~3 min"),
        ],
        recent=[
            RecentScan(
                1290,
                "line_scan",
                "samy −1 → 1 · 21 pts",
                "LaB6",
                "Aborted",
                "warning",
                "0:24",
                "21:31",
            ),
            RecentScan(
                1289,
                "fermat_scan",
                "samx, samy ±3 · step 0.5",
                "LaB6",
                "Done",
                "success",
                "6:12",
                "21:24",
            ),
            RecentScan(
                1288, "acquire", "eiger9m · 1 s", "LaB6", "Done", "success", "0:01", "21:17"
            ),
            RecentScan(
                1287,
                "grid_scan",
                "samx ±5 (41) · samy ±2 (11)",
                "cathode_A3",
                "Done",
                "success",
                "11:40",
                "21:05",
            ),
            RecentScan(
                1286,
                "line_scan",
                "mono_energy 12.3 → 12.5 keV",
                "cathode_A3",
                "Failed",
                "danger",
                "1:02",
                "20:41",
            ),
            RecentScan(
                1285,
                "line_scan",
                "samx −2 → 2 · 41 pts",
                "cathode_A3",
                "Done",
                "success",
                "0:58",
                "20:33",
            ),
        ],
        problems=[
            Problem(
                "warning",
                "sample_temp is close to its upper limit",
                "bpm4i reads 9.6, limit 10. Not part of the scan interlock.",
                "2 min ago",
                "Beamline states",
            ),
            Problem(
                "danger",
                "Scan 1286 failed: mono_energy readback timed out",
                "DeviceServer · mono_energy did not reach 12.41 keV within 10 s.",
                "20:41",
                "Details",
            ),
            Problem(
                "info",
                "IPython client on x12sa-console-2 runs v3.38.1",
                "The servers run v3.39.0. Restart that client to update.",
                "18:02",
                "",
            ),
        ],
        workspaces=[
            Workspace("Alignment", "open now", ["Waveform", "Image", "PositionerBox"], True),
            Workspace("Scan monitor", "today 19:12", ["Waveform", "Waveform", "Queue", "Ring"]),
            Workspace("Detector QA", "yesterday", ["Image", "Image", "Heatmap"]),
            Workspace("Energy calibration", "7 Oct", ["Waveform", "ScanControl"]),
        ],
        actions=[
            QuickAction(
                "play_circle", "Run a scan", "Scan control with your last settings", "Ctrl+R"
            ),
            QuickAction(
                "search", "Find anything", "Devices, scans, widgets and commands", "Ctrl+K"
            ),
            QuickAction("display_settings", "Device manager", "Enable, disable or edit devices"),
            QuickAction(
                "dashboard_customize", "New workspace", "Start from an empty dock area", "Ctrl+T"
            ),
        ],
        events=[
            Event(
                "21:52",
                "scan",
                "play_arrow",
                "info",
                "Scan 1291 started",
                "line_scan · samx −2 → 2 · LaB6",
                "Live plot",
            ),
            Event(
                "21:31",
                "scan",
                "stop_circle",
                "warning",
                "Scan 1290 aborted by e20631",
                "line_scan · samy −1 → 1 · 12 of 21 points",
                "Plot",
            ),
            Event(
                "21:24",
                "scan",
                "check_circle",
                "success",
                "Scan 1289 finished",
                "fermat_scan · 6 min 12 s · LaB6",
                "Plot",
            ),
            Event(
                "21:10",
                "config",
                "tune",
                "neutral",
                "Sample changed to LaB6",
                "sample_name metadata updated by e20631",
            ),
            Event(
                "21:05",
                "scan",
                "check_circle",
                "success",
                "Scan 1287 finished",
                "grid_scan · 11 min 40 s · cathode_A3",
                "Plot",
            ),
            Event(
                "20:58",
                "interlock",
                "lock_open",
                "success",
                "Scan interlock re-armed",
                "shutter_open is valid again after 4 min",
            ),
            Event(
                "20:54",
                "interlock",
                "lock",
                "danger",
                "Scan interlock tripped",
                "shutter_open outside [0, 10] · queue paused",
                "Beamline states",
            ),
            Event(
                "20:41",
                "problem",
                "error",
                "danger",
                "Scan 1286 failed",
                "mono_energy readback timed out",
                "Details",
            ),
            Event(
                "20:33",
                "scan",
                "done_all",
                "success",
                "6 more scans finished",
                "1281 – 1285 and 1288 · cathode_A3, LaB6",
                "Show",
            ),
            Event(
                "19:30",
                "note",
                "sticky_note_2",
                "info",
                "Note from beamline staff",
                "Mono recalibrated at 19:00. Expect a 2 eV offset on old energy scans.",
            ),
            Event("19:12", "config", "dashboard", "neutral", "Workspace 'Scan monitor' saved"),
            Event(
                "18:02",
                "session",
                "login",
                "neutral",
                "e20631 started bec on x12sa-console-2",
                "client v3.38.1, servers v3.39.0",
            ),
        ],
        away_since="17:45",
        away_summary=[
            ("check_circle", "success", "8 scans finished"),
            ("stop_circle", "warning", "1 aborted"),
            ("error", "danger", "1 failed"),
            ("lock", "danger", "Interlock tripped once"),
            ("sticky_note_2", "info", "1 staff note"),
        ],
        tip=(
            "Re-run any scan from its history",
            "Right-click a scan in the history and choose Re-run to open it in scan control "
            "with the same arguments.",
        ),
    )


def trouble_snapshot() -> WelcomeSnapshot:
    """The same shift a few minutes later, when the interlock trips and a service goes down."""
    snap = demo_snapshot()
    snap.glances = [
        snap.glances[0],
        Glance(
            "interlock",
            "gpp_bad",
            "Scan interlock",
            "Tripped",
            "shutter_open outside [0, 10]",
            "danger",
        ),
        Glance(
            "services",
            "monitor_heart",
            "BEC services",
            "1 down",
            "File writer not responding",
            "danger",
        ),
        Glance(
            "queue", "pause_circle", "Queue", "Paused", "by the interlock · 2 waiting", "warning"
        ),
    ]
    snap.running = replace(snap.running, paused=True)
    snap.problems = [
        Problem(
            "danger",
            "Scans are blocked: the scan interlock tripped",
            "shutter_open reads 12.3, accepted range [0, 10]. The queue resumes when it is "
            "valid again.",
            "22:03",
            "Beamline states",
        ),
        Problem(
            "danger",
            "File writer is not responding",
            "Last heartbeat 40 s ago on x12sa-bec-01. Data of scan 1291 may be incomplete.",
            "22:02",
            "Service status",
        ),
    ] + snap.problems[:1]
    snap.events = [
        Event(
            "22:03",
            "interlock",
            "lock",
            "danger",
            "Scan interlock tripped",
            "shutter_open outside [0, 10] · scan 1291 paused at point 25",
            "Beamline states",
        ),
        Event(
            "22:02",
            "problem",
            "error",
            "danger",
            "File writer is not responding",
            "last heartbeat 40 s ago on x12sa-bec-01",
            "Service status",
        ),
    ] + snap.events
    snap.away_summary = snap.away_summary[:3] + [
        ("lock", "danger", "Interlock tripped twice"),
        ("error", "danger", "File writer down"),
    ]
    return snap
