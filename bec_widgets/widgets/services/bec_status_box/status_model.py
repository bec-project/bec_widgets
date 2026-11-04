"""View-independent data layer of the BEC status box.

``ServiceStatusModel`` turns the raw service info of the BEC client into display rows and an overall
summary. The status box view and the status-bar pill read the same model.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from qtpy.QtCore import QObject, Signal
from qtpy.QtWidgets import QApplication

from bec_widgets.widgets.containers.main_window.addons.status_pill import ToolSeverity
from bec_widgets.widgets.progress.stage_bar import Tone

# status -> (label, tone, material icon)
STATUS_STYLE = {
    "RUNNING": ("Running", Tone.OK, "check_circle"),
    "BUSY": ("Busy", Tone.OK, "progress_activity"),
    "IDLE": ("Idle", Tone.WARN, "pause_circle"),
    "ERROR": ("Error", Tone.BAD, "error"),
    "NOTCONNECTED": ("Not connected", Tone.BAD, "cloud_off"),
}


# colour of the overall state in the header and its dot
SEVERITY_TONE = {
    ToolSeverity.OK: Tone.OK,
    ToolSeverity.INFO: Tone.NEUTRAL,
    ToolSeverity.WARNING: Tone.WARN,
    ToolSeverity.CRITICAL: Tone.BAD,
}


class RestartState(StrEnum):
    """Progress of a BEC server restart requested from the status box."""

    NONE = ""
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


FRIENDLY_NAMES = {
    "DeviceServer": "Device server",
    "ScanServer": "Scan server",
    "ScanBundler": "Scan bundler",
    "FileWriterManager": "File writer",
    "SciHub": "SciHub",
    "DAPServer": "Data processing",
    "CLIBECClient": "IPython client",
    "BECIPythonClient": "IPython client",
    "BECClient": "Client",
    "BECGuiClient": "GUI client",
}


def friendly_name(service_name: str) -> tuple[str, str]:
    """Return a readable name and a short instance id for a BEC service name.

    Args:
        service_name (str): The raw service name, e.g. "DeviceServer" or "CLIBECClient/<uuid>".

    Returns:
        tuple[str, str]: The display name and the short instance id ("" for unique services).
    """
    base, _, instance = service_name.partition("/")
    name = FRIENDLY_NAMES.get(base)
    if name is None:
        name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", base)
        name = name[:1].upper() + name[1:].lower() if name else service_name
    return name, instance[:6]


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as a short human readable string.

    Args:
        seconds (float): The duration.

    Returns:
        str: For example "45 s", "12 min", "3 h 5 min" or "2 d 4 h".
    """
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} h {minutes} min"
    days, hours = divmod(hours, 24)
    return f"{days} d {hours} h"


@dataclass
class ServiceRow:
    """One display row of the status box."""

    service_name: str
    display_name: str
    instance: str
    group: str
    status: str
    status_label: str
    tone: Tone
    icon: str
    host: str = ""
    user: str = ""
    version: str = ""
    version_mismatch: bool = False
    uptime: str = ""
    cpu: str = ""
    memory: str = ""
    details: list[tuple[str, str]] = field(default_factory=list)

    @property
    def subtitle(self) -> str:
        """The secondary line: who runs the service and where."""
        parts = []
        if self.user and self.host:
            parts.append(f"{self.user}@{self.host}")
        elif self.host:
            parts.append(self.host)
        if self.instance:
            parts.append(f"#{self.instance}")
        if not parts and self.status == "NOTCONNECTED":
            parts.append("No heartbeat from this service")
        return " · ".join(parts)

    def details_text(self) -> str:
        """Plain text version of the details, used for the copy button."""
        lines = [f"{self.service_name}: {self.status_label}"]
        lines += [f"{key}: {value}" for key, value in self.details]
        return "\n".join(lines)


CORE_GROUP = "Core services"
OTHER_GROUP = "Clients and other services"


def build_rows(services, core_services: list[str], now: float | None = None) -> list[ServiceRow]:
    """Build display rows from the status box's service info containers.

    Args:
        services: Iterable of BECServiceInfoContainer-like objects (service_name, status, info,
            metrics).
        core_services (list[str]): Names of the core services, shown first in their own group.
        now (float | None): Current time, for uptime. Defaults to time.time().

    Returns:
        list[ServiceRow]: Core services in the given order, then all other services by name.
    """
    now = time.time() if now is None else now
    services = list(services)
    rows = []
    for svc in services:
        info = svc.info or {}
        metrics = svc.metrics or {}
        status = svc.status if svc.status in STATUS_STYLE else "NOTCONNECTED"
        label, tone, icon = STATUS_STYLE[status]
        name, instance = friendly_name(svc.service_name)
        versions = info.get("versions") or {}
        version = versions.get("bec_lib", "") or info.get("version", "")
        row = ServiceRow(
            service_name=svc.service_name,
            display_name=name,
            instance=instance,
            group=CORE_GROUP if svc.service_name in core_services else OTHER_GROUP,
            status=status,
            status_label=label,
            tone=tone,
            icon=icon,
            host=str(info.get("hostname") or metrics.get("hostname") or ""),
            user=str(info.get("user") or metrics.get("username") or ""),
            version=str(version),
        )
        if "create_time" in metrics:
            row.uptime = format_duration(now - metrics["create_time"])
        if "cpu_percent" in metrics:
            row.cpu = f"{metrics['cpu_percent']:.0f} %"
        if "memory_in_mb" in metrics:
            row.memory = f"{metrics['memory_in_mb']:.0f} MB"
        details = [("Service", svc.service_name)]
        for key, value in (
            ("Host", row.host),
            ("User", row.user),
            ("PID", metrics.get("pid", "")),
            ("Uptime", row.uptime),
            ("CPU", row.cpu),
            ("Memory", row.memory),
            ("Threads", metrics.get("num_threads", "")),
        ):
            if value not in ("", None):
                details.append((key, str(value)))
        if "create_time" in metrics:
            started = datetime.fromtimestamp(metrics["create_time"]).strftime("%Y-%m-%d %H:%M:%S")
            details.append(("Started", started))
        for package, pkg_version in versions.items():
            details.append((package, str(pkg_version)))
        row.details = details
        rows.append(row)

    # flag services whose bec_lib version differs from the one most services run
    versions = Counter(row.version for row in rows if row.version)
    if len(versions) > 1:
        common = versions.most_common(1)[0][0]
        for row in rows:
            row.version_mismatch = bool(row.version) and row.version != common

    core_order = {name: idx for idx, name in enumerate(core_services)}
    rows.sort(
        key=lambda r: (
            r.group != CORE_GROUP,
            core_order.get(r.service_name, 0),
            r.display_name,
            r.instance,
        )
    )
    return rows


def summarize(rows: list[ServiceRow], core_state: str) -> tuple[str, str, ToolSeverity]:
    """Summarize the overall state for the header and the status-bar pill.

    Args:
        rows (list[ServiceRow]): The display rows.
        core_state (str): The combined state of the core services.

    Returns:
        tuple[str, str, ToolSeverity]: (headline, detail line, severity).
    """
    core = [row for row in rows if row.group == CORE_GROUP]
    others = [row for row in rows if row.group != CORE_GROUP]
    down = [row for row in core if row.status in ("NOTCONNECTED", "ERROR")]
    idle = [row for row in core if row.status == "IDLE"]
    if down:
        if len(down) == 1:
            headline = f"{down[0].display_name}: {down[0].status_label.lower()}"
        else:
            headline = f"{len(down)} core services down"
        severity = ToolSeverity.CRITICAL
    elif idle:
        headline = (
            f"{idle[0].display_name} is idle" if len(idle) == 1 else f"{len(idle)} services idle"
        )
        severity = ToolSeverity.WARNING
    elif core and core_state in ("RUNNING", "BUSY"):
        headline = "All core services running"
        severity = ToolSeverity.OK
    else:
        headline = "Waiting for BEC services"
        severity = ToolSeverity.INFO
    ok = sum(1 for row in core if row.tone == Tone.OK)
    detail = f"{ok}/{len(core)} core services up"
    if others:
        detail += f" · {len(others)} other" if len(others) == 1 else f" · {len(others)} others"
    mismatched = [row for row in rows if row.version_mismatch]
    if mismatched:
        detail += f" · {len(mismatched)} version mismatch"
    return headline, detail, severity


def core_services_down(rows: list[ServiceRow]) -> int:
    """Number of core services that are not connected or in error."""
    return sum(
        1 for row in rows if row.group == CORE_GROUP and row.status in ("NOTCONNECTED", "ERROR")
    )


class ServiceStatusModel(QObject):
    """The rows, the overall summary and the restart progress of the BEC services.

    Signals:
        rows_changed(): The rows were replaced.
        summary_changed(): The headline, the detail line or the severity changed.
        restart_changed(): The restart progress or whether a restart is possible changed.
        restart_requested(): The view asks for a restart; the owner confirms and requests it.
    """

    rows_changed = Signal()
    summary_changed = Signal()
    restart_changed = Signal()
    restart_requested = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._rows: list[ServiceRow] = []
        self._headline = "Waiting for BEC services"
        self._detail = ""
        self._severity = ToolSeverity.INFO
        self._restart_state = RestartState.NONE
        self._restart_text = ""
        self._can_restart = False

    @property
    def rows(self) -> list[ServiceRow]:
        """The current display rows."""
        return list(self._rows)

    def set_rows(self, rows: list[ServiceRow], core_state: str) -> None:
        """Replace the rows and update the summary.

        Args:
            rows (list[ServiceRow]): The new rows, already sorted.
            core_state (str): The combined state of the core services.
        """
        self._rows = list(rows)
        summary = summarize(self._rows, core_state)
        if summary != (self._headline, self._detail, self._severity):
            self._headline, self._detail, self._severity = summary
            self.summary_changed.emit()
        self.rows_changed.emit()

    @property
    def headline(self) -> str:
        """The one-line overall state, e.g. "All core services running"."""
        return self._headline

    @property
    def detail(self) -> str:
        """The secondary summary line with counts."""
        return self._detail

    @property
    def severity(self) -> ToolSeverity:
        """The overall severity: ok, info, warning or critical."""
        return self._severity

    @property
    def services_down(self) -> int:
        """Number of core services that are not connected or in error."""
        return core_services_down(self._rows)

    def set_restart(self, state: RestartState | str, text: str = "") -> None:
        """Set the restart progress shown in the header and the pill.

        Args:
            state (RestartState | str): none, running, done or failed.
            text (str): The line shown while the state is set.
        """
        state = RestartState(state)
        if (state, text) != (self._restart_state, self._restart_text):
            self._restart_state, self._restart_text = state, text
            self.restart_changed.emit()

    def set_can_restart(self, can_restart: bool) -> None:
        """Enable or disable the restart action."""
        if can_restart != self._can_restart:
            self._can_restart = can_restart
            self.restart_changed.emit()

    @property
    def restart_state(self) -> RestartState:
        """The restart progress."""
        return self._restart_state

    @property
    def restart_text(self) -> str:
        """The restart progress line."""
        return self._restart_text

    @property
    def can_restart(self) -> bool:
        """Whether a restart can be requested now (SciHub is up and no restart is running)."""
        return self._can_restart and self._restart_state != RestartState.RUNNING

    def request_restart(self) -> None:
        """Ask the owner widget to confirm and request a BEC server restart."""
        if self.can_restart:
            self.restart_requested.emit()

    def copy_details(self, service_name: str) -> None:
        """Copy the details of a service to the clipboard.

        Args:
            service_name (str): The raw service name.
        """
        for row in self._rows:
            if row.service_name == service_name:
                QApplication.clipboard().setText(row.details_text())
                return
