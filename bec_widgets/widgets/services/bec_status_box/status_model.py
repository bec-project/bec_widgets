"""View-independent data layer for the BEC status box.

``ServiceStatusModel`` turns the raw service info of the BEC client into display rows. The QML view
binds to it as a list model, and the QWidget view reads the same rows, so both views show exactly
the same content.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from qtpy.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    Qt,
    Signal,
    Slot,
)
from qtpy.QtWidgets import QApplication

# status -> (label, tone, material icon)
STATUS_STYLE = {
    "RUNNING": ("Running", "success", "check_circle"),
    "BUSY": ("Busy", "success", "progress_activity"),
    "IDLE": ("Idle", "warning", "pause_circle"),
    "ERROR": ("Error", "emergency", "error"),
    "NOTCONNECTED": ("Not connected", "emergency", "cloud_off"),
}

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
    tone: str
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


def summarize(rows: list[ServiceRow], core_state: str) -> tuple[str, str, str]:
    """Summarize the overall state for the header.

    Args:
        rows (list[ServiceRow]): The display rows.
        core_state (str): The combined state of the core services.

    Returns:
        tuple[str, str, str]: (headline, detail line, tone).
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
        tone = "emergency"
    elif idle:
        headline = (
            f"{idle[0].display_name} is idle" if len(idle) == 1 else f"{len(idle)} services idle"
        )
        tone = "warning"
    elif core and core_state in ("RUNNING", "BUSY"):
        headline = "All core services running"
        tone = "success"
    else:
        headline = "Waiting for BEC services"
        tone = "neutral"
    ok = sum(1 for row in core if row.tone == "success")
    detail = f"{ok}/{len(core)} core services up"
    if others:
        detail += f" · {len(others)} other" if len(others) == 1 else f" · {len(others)} others"
    mismatched = [row for row in rows if row.version_mismatch]
    if mismatched:
        detail += f" · {len(mismatched)} version mismatch"
    return headline, detail, tone


class ServiceStatusModel(QAbstractListModel):
    """List model of BEC services with a summary, shared by the QML and QWidget views."""

    summaryChanged = Signal()
    rowsChanged = Signal()

    ROLE_NAMES = (
        "serviceName",
        "displayName",
        "subtitle",
        "group",
        "status",
        "statusLabel",
        "tone",
        "icon",
        "version",
        "versionMismatch",
        "uptime",
        "cpu",
        "memory",
        "details",
    )

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._rows: list[ServiceRow] = []
        self._headline = "Waiting for BEC services"
        self._detail = ""
        self._tone = "neutral"
        self._roles = {Qt.ItemDataRole.UserRole + i: n for i, n in enumerate(self.ROLE_NAMES)}
        self._role_ids = {name: role for role, name in self._roles.items()}

    # ---- QAbstractListModel -------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        return len(self._rows)

    def roleNames(self) -> dict[int, QByteArray]:
        return {role: QByteArray(name.encode()) for role, name in self._roles.items()}

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return row.display_name
        name = self._roles.get(role)
        if name is None:
            return None
        return self._value(row, name)

    @staticmethod
    def _value(row: ServiceRow, name: str):
        match name:
            case "serviceName":
                return row.service_name
            case "displayName":
                return row.display_name
            case "subtitle":
                return row.subtitle
            case "group":
                return row.group
            case "status":
                return row.status
            case "statusLabel":
                return row.status_label
            case "tone":
                return row.tone
            case "icon":
                return row.icon
            case "version":
                return row.version
            case "versionMismatch":
                return row.version_mismatch
            case "uptime":
                return row.uptime
            case "cpu":
                return row.cpu
            case "memory":
                return row.memory
            case "details":
                return [{"key": key, "value": value} for key, value in row.details]
        return None

    # ---- public API ---------------------------------------------------------------------------

    @property
    def rows(self) -> list[ServiceRow]:
        """The current display rows."""
        return list(self._rows)

    def set_rows(self, rows: list[ServiceRow], core_state: str) -> None:
        """Replace the rows, emitting fine-grained model signals instead of a reset.

        Args:
            rows (list[ServiceRow]): The new rows, already sorted.
            core_state (str): The combined state of the core services.
        """
        new_keys = [row.service_name for row in rows]
        # remove rows that disappeared
        for idx in reversed(range(len(self._rows))):
            if self._rows[idx].service_name not in new_keys:
                self.beginRemoveRows(QModelIndex(), idx, idx)
                del self._rows[idx]
                self.endRemoveRows()
        # insert or move rows into place, update changed ones
        for target, row in enumerate(rows):
            current = [r.service_name for r in self._rows]
            if row.service_name not in current:
                self.beginInsertRows(QModelIndex(), target, target)
                self._rows.insert(target, row)
                self.endInsertRows()
                continue
            source = current.index(row.service_name)
            if source != target:
                self.beginMoveRows(QModelIndex(), source, source, QModelIndex(), target)
                self._rows.insert(target, self._rows.pop(source))
                self.endMoveRows()
            if self._rows[target] != row:
                changed = [
                    self._role_ids[name]
                    for name in self.ROLE_NAMES
                    if self._value(self._rows[target], name) != self._value(row, name)
                ]
                self._rows[target] = row
                index = self.index(target)
                self.dataChanged.emit(index, index, changed)

        headline, detail, tone = summarize(self._rows, core_state)
        if (headline, detail, tone) != (self._headline, self._detail, self._tone):
            self._headline, self._detail, self._tone = headline, detail, tone
            self.summaryChanged.emit()
        self.rowsChanged.emit()

    @Property(str, notify=summaryChanged)
    def headline(self) -> str:
        """The one-line overall state, e.g. "All core services running"."""
        return self._headline

    @Property(str, notify=summaryChanged)
    def detail(self) -> str:
        """The secondary summary line with counts."""
        return self._detail

    @Property(str, notify=summaryChanged)
    def tone(self) -> str:
        """The overall tone: success, warning, emergency or neutral."""
        return self._tone

    @Slot(str)
    def copyDetails(self, service_name: str) -> None:
        """Copy the details of a service to the clipboard.

        Args:
            service_name (str): The raw service name.
        """
        for row in self._rows:
            if row.service_name == service_name:
                QApplication.clipboard().setText(row.details_text())
                return
