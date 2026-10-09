"""Toolkit-independent core of the reworked notification and error UX.

The QML and QWidget versions of the notification UI share everything that is not drawing:

- :class:`NotificationHub` is the application-wide history of notifications. BEC alarms,
  errors caught by ``SafeSlot(popup_error=True)``, uncaught exceptions and calls to
  :meth:`NotificationHub.notify` all end up here. Repeated messages are folded into one entry
  with a counter instead of flooding the screen.
- :class:`ToastQueue` decides which entries are shown as short toasts: at most a few at a time,
  auto-dismissed after a severity dependent time (paused while hovered) except for critical
  errors, which stay until they are acknowledged.
- :class:`NotificationHostBase` attaches the UI to a window: a toast stack in the bottom right
  corner, a history drawer on the right edge and a bell button with an unread badge for the
  status bar. Subclasses only create and place their views and render :meth:`view_state`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

import shiboken6
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import ErrorInfo
from qtpy.QtCore import QEvent, QObject, QRect, Qt, QThread, QTimer, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication, QMainWindow, QStatusBar, QWidget

from bec_widgets.utils.quick.host import ThemeTokens, _blend

logger = bec_logger.logger


class Severity(str, Enum):
    """Severity of a notification, from least to most serious."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# label, Material icon, toast lifetime in ms (0 = until acknowledged) and rank for sorting
SEVERITY_META: dict[Severity, dict[str, Any]] = {
    Severity.INFO: {"label": "Info", "icon": "info", "lifetime": 4000, "rank": 0},
    Severity.SUCCESS: {"label": "Done", "icon": "check_circle", "lifetime": 4000, "rank": 1},
    Severity.WARNING: {"label": "Warning", "icon": "warning", "lifetime": 8000, "rank": 2},
    Severity.ERROR: {"label": "Error", "icon": "error", "lifetime": 12000, "rank": 3},
    Severity.CRITICAL: {"label": "Critical", "icon": "dangerous", "lifetime": 0, "rank": 4},
}

# legacy banner kinds and BEC alarm levels mapped onto the new severities
_LEGACY_KINDS = {
    "info": Severity.INFO,
    "warning": Severity.WARNING,
    "minor": Severity.ERROR,
    "major": Severity.CRITICAL,
}
_ALARM_LEVELS = {0: Severity.WARNING, 1: Severity.ERROR, 2: Severity.CRITICAL}

# history filters: key -> (label, severities)
FILTERS: dict[str, tuple[str, tuple[Severity, ...]]] = {
    "all": ("All", tuple(Severity)),
    "errors": ("Errors", (Severity.ERROR, Severity.CRITICAL)),
    "warnings": ("Warnings", (Severity.WARNING,)),
    "info": ("Info", (Severity.INFO, Severity.SUCCESS)),
}


def to_severity(value: Any) -> Severity:
    """Normalise a severity given as :class:`Severity`, legacy banner kind or alarm level.

    Args:
        value: ``Severity``, its value, a legacy kind (``info``/``warning``/``minor``/``major``)
            or an integer BEC alarm level (0, 1, 2).

    Returns:
        Severity: The matching severity; unknown values become ``WARNING``.
    """
    if isinstance(value, Severity):
        return value
    raw = getattr(value, "value", value)
    if isinstance(raw, str):
        raw = raw.lower()
        if raw in _LEGACY_KINDS:
            return _LEGACY_KINDS[raw]
        try:
            return Severity(raw)
        except ValueError:
            return Severity.WARNING
    if isinstance(raw, int) and not isinstance(raw, bool):
        return _ALARM_LEVELS.get(raw, Severity.WARNING)
    return Severity.WARNING


def severity_color(tokens: ThemeTokens, severity: Severity) -> QColor:
    """Theme colour used for a severity: icon, accent stripe and badge."""
    if severity == Severity.INFO:
        return QColor(tokens.accent)
    if severity == Severity.SUCCESS:
        return QColor(tokens.success)
    if severity == Severity.WARNING:
        return QColor(tokens.warning)
    if severity == Severity.ERROR:
        # orange: between warning and critical so the two error levels read differently
        return _blend(tokens.warning, tokens.danger, 0.55)
    return QColor(tokens.danger)


def split_traceback(text: str) -> tuple[str, str]:
    """Return ``(exception type, message)`` from the last line of a formatted traceback."""
    lines = [line.strip() for line in (text or "").strip().splitlines() if line.strip()]
    if not lines:
        return "Error", ""
    last = lines[-1]
    head, sep, tail = last.partition(":")
    if sep and head and " " not in head.strip():
        return head.strip().rsplit(".", 1)[-1], tail.strip()
    return "Error", last


def relative_time(timestamp: float, now: float | None = None) -> str:
    """Short human readable age of ``timestamp`` such as ``2 min ago`` or ``13:04``."""
    now = time.time() if now is None else now
    seconds = max(0, int(now - timestamp))
    if seconds < 30:
        return "just now"
    if seconds < 3600:
        return f"{max(1, seconds // 60)} min ago"
    stamp = datetime.fromtimestamp(timestamp)
    if stamp.date() == datetime.fromtimestamp(now).date():
        return stamp.strftime("%H:%M")
    return stamp.strftime("%b %d, %H:%M")


def absolute_time(timestamp: float) -> str:
    """Full local timestamp."""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class NotificationEntry:
    """One notification in the history."""

    id: str
    severity: Severity
    title: str
    body: str = ""
    details: str = ""
    source: str = ""
    scan_number: int | None = None
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    count: int = 1
    read: bool = False
    acknowledged: bool = False

    @property
    def needs_ack(self) -> bool:
        """A critical entry stays pinned and on screen until somebody acknowledges it."""
        return self.severity == Severity.CRITICAL and not self.acknowledged

    def copy_text(self) -> str:
        """Plain-text report used by the Copy action, ready to paste into a logbook or issue."""
        lines = [f"[{SEVERITY_META[self.severity]['label']}] {self.title}"]
        lines.append(f"Time: {absolute_time(self.updated)}")
        if self.count > 1:
            lines.append(f"Occurrences: {self.count} (first at {absolute_time(self.created)})")
        if self.source:
            lines.append(f"Source: {self.source}")
        if self.scan_number is not None:
            lines.append(f"Scan: #{self.scan_number}")
        if self.body:
            lines.extend(["", self.body])
        if self.details:
            lines.extend(["", self.details])
        return "\n".join(lines)


class NotificationHub(QObject):
    """Application-wide notification history shared by every window and both UI versions.

    Signals:
        posted(str): A notification was added, or a repeated one was folded into an entry.
        changed(): Anything in the history changed.
        scan_started(): A new scan opened; hosts hide the non-critical toasts.
    """

    MAX_ENTRIES = 500
    DEDUP_WINDOW_S = 120.0

    posted = Signal(str)
    changed = Signal()
    scan_started = Signal()
    _post_requested = Signal(dict)

    _instance: NotificationHub | None = None

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._entries: list[NotificationEntry] = []
        self._hosts = 0
        self._dispatcher = None
        self._post_requested.connect(self._post, Qt.ConnectionType.QueuedConnection)

    @classmethod
    def instance(cls) -> NotificationHub:
        """Return the hub of this application, creating it on first use."""
        inst = cls._instance
        if inst is None or not shiboken6.isValid(inst):
            inst = cls(QApplication.instance())
            cls._instance = inst
        return inst

    @classmethod
    def reset_instance(cls) -> None:
        """Drop the hub, e.g. between tests. Its BEC subscriptions are disconnected."""
        inst = cls._instance
        cls._instance = None
        if inst is not None and shiboken6.isValid(inst):
            inst.disconnect_bec()
            shiboken6.delete(inst)

    # ------------------------------------------------------------------ public API
    def notify(
        self,
        title: str,
        body: str = "",
        severity: Severity | str | int = Severity.INFO,
        *,
        details: str = "",
        source: str = "",
        scan_number: int | None = None,
        entry_id: str | None = None,
    ) -> str:
        """Post a notification. Safe to call from any thread.

        Args:
            title(str): Short headline, e.g. ``Motor samx not reachable``.
            body(str): One or two sentences for the toast and the history row.
            severity(Severity | str | int): Severity, legacy kind or alarm level.
            details(str): Optional long text such as a traceback, shown in the details view.
            source(str): Where it came from, e.g. ``Scan server`` or a widget name.
            scan_number(int | None): Scan the notification refers to.
            entry_id(str | None): Stable id; a second post with the same id is ignored.

        Returns:
            str: The id of the (possibly folded) entry.
        """
        payload = {
            "title": str(title or "Notification"),
            "body": str(body or ""),
            "severity": to_severity(severity),
            "details": str(details or ""),
            "source": str(source or ""),
            "scan_number": scan_number,
            "entry_id": entry_id or uuid4().hex,
        }
        if QThread.currentThread() is not self.thread():
            self._post_requested.emit(payload)
            return payload["entry_id"]
        return self._post(payload)

    def report_exception(self, title: str, traceback_text: str, source: str = "") -> str:
        """Post an error from a formatted traceback; used instead of a modal error dialog."""
        exc_type, message = split_traceback(traceback_text)
        return self.notify(
            exc_type,
            message or "An unexpected error occurred.",
            Severity.ERROR,
            details=traceback_text.strip(),
            source=source or title,
        )

    def post_alarm(self, msg: dict, meta: dict | None = None) -> str | None:
        """Translate a BEC alarm message into a notification.

        Args:
            msg(dict): Alarm content with ``severity``, ``alarm_type``, ``msg`` and ``info``.
            meta(dict | None): Message metadata, may hold ``scan_id`` and ``scan_number``.

        Returns:
            str | None: Id of the entry, or None if the alarm was already posted.
        """
        msg = msg or {}
        meta = meta or {}
        info = msg.get("info")
        alarm_id = info.get("id") if isinstance(info, dict) else getattr(info, "id", None)
        if isinstance(info, dict):
            try:
                info = ErrorInfo(**info)
            except Exception:  # pylint: disable=broad-except
                # incomplete payload: keep what is there
                info = type("PartialInfo", (), dict(info))()
        if alarm_id and self.get(alarm_id) is not None:
            return None
        trace = getattr(info, "error_message", None) or msg.get("msg") or ""
        compact = getattr(info, "compact_error_message", None)
        exc_type, last_line = split_traceback(trace)
        title = msg.get("alarm_type") or getattr(info, "exception_type", None) or exc_type
        body = compact or last_line or str(msg.get("msg") or "")
        details = trace if trace.strip() and trace.strip() != body.strip() else ""
        if meta.get("scan_id") and details:
            details = f"Scan id: {meta['scan_id']}\n\n{details}"
        device = getattr(info, "device", None)
        source = f"Device {device}" if device else "BEC server"
        return self.notify(
            title,
            body,
            msg.get("severity", 0),
            details=details,
            source=source,
            scan_number=meta.get("scan_number"),
            entry_id=alarm_id,
        )

    @property
    def entries(self) -> list[NotificationEntry]:
        """History, newest first."""
        return list(self._entries)

    def get(self, entry_id: str) -> NotificationEntry | None:
        """Return the entry with ``entry_id`` or None."""
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        return None

    def acknowledge(self, entry_id: str) -> None:
        """Acknowledge a (critical) entry; it is unpinned and its toast closes."""
        entry = self.get(entry_id)
        if entry is None or entry.acknowledged:
            return
        entry.acknowledged = True
        entry.read = True
        self.changed.emit()

    def remove(self, entry_id: str) -> None:
        """Remove one entry from the history."""
        entry = self.get(entry_id)
        if entry is not None:
            self._entries.remove(entry)
            self.changed.emit()

    def clear(self) -> None:
        """Clear the history but keep critical errors nobody has acknowledged yet."""
        kept = [entry for entry in self._entries if entry.needs_ack]
        if len(kept) != len(self._entries):
            self._entries = kept
            self.changed.emit()

    def mark_read(self, entry_ids: list[str] | None = None) -> None:
        """Mark the given entries, or all of them, as read."""
        touched = False
        for entry in self._entries:
            if not entry.read and (entry_ids is None or entry.id in entry_ids):
                entry.read = True
                touched = True
        if touched:
            self.changed.emit()

    def unread_count(self) -> int:
        """Number of unread entries."""
        return sum(1 for entry in self._entries if not entry.read)

    def top_unread_severity(self) -> Severity | None:
        """Most serious severity among unread or unacknowledged entries."""
        open_entries = [e for e in self._entries if not e.read or e.needs_ack]
        if not open_entries:
            return None
        return max(open_entries, key=lambda e: SEVERITY_META[e.severity]["rank"]).severity

    # ------------------------------------------------------------------ hosts and BEC feed
    def register_host(self) -> None:
        """Called by a host when it attaches; errors are then routed here, not to dialogs."""
        self._hosts += 1

    def unregister_host(self) -> None:
        """Called by a host when it detaches."""
        self._hosts = max(0, self._hosts - 1)

    @property
    def has_hosts(self) -> bool:
        """Whether any window currently shows notifications."""
        return self._hosts > 0

    def connect_bec(self, dispatcher) -> None:
        """Subscribe to BEC alarms and scan status once per application."""
        if self._dispatcher is not None or dispatcher is None:
            return
        self._dispatcher = dispatcher
        dispatcher.connect_slot(self._on_alarm, MessageEndpoints.alarm())
        dispatcher.connect_slot(self._on_scan_status, MessageEndpoints.scan_status())

    def disconnect_bec(self) -> None:
        """Undo :meth:`connect_bec`."""
        dispatcher, self._dispatcher = self._dispatcher, None
        if dispatcher is None:
            return
        try:
            dispatcher.disconnect_slot(self._on_alarm, MessageEndpoints.alarm())
            dispatcher.disconnect_slot(self._on_scan_status, MessageEndpoints.scan_status())
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(f"NotificationHub could not disconnect from BEC: {exc}")

    def _on_alarm(self, msg: dict, meta: dict) -> None:
        try:
            self.post_alarm(msg, meta)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(f"Could not turn alarm into a notification: {exc}")

    def _on_scan_status(self, msg: dict, _meta: dict) -> None:
        if (msg or {}).get("status") == "open":
            self.scan_started.emit()

    # ------------------------------------------------------------------ internals
    def _post(self, payload: dict) -> str:
        entry_id = payload["entry_id"]
        if self.get(entry_id) is not None:
            return entry_id
        now = time.time()
        for entry in self._entries:
            if now - entry.updated > self.DEDUP_WINDOW_S:
                break
            if (
                entry.severity == payload["severity"]
                and entry.title == payload["title"]
                and entry.body == payload["body"]
                and entry.source == payload["source"]
            ):
                entry.count += 1
                entry.updated = now
                entry.read = False
                entry.acknowledged = False
                entry.details = payload["details"] or entry.details
                self._entries.remove(entry)
                self._entries.insert(0, entry)
                self.changed.emit()
                self.posted.emit(entry.id)
                return entry.id
        entry = NotificationEntry(
            id=entry_id,
            severity=payload["severity"],
            title=payload["title"],
            body=payload["body"],
            details=payload["details"],
            source=payload["source"],
            scan_number=payload["scan_number"],
            created=now,
            updated=now,
        )
        self._entries.insert(0, entry)
        self._trim()
        self.changed.emit()
        self.posted.emit(entry.id)
        return entry.id

    def _trim(self) -> None:
        excess = len(self._entries) - self.MAX_ENTRIES
        if excess <= 0:
            return
        for entry in reversed(list(self._entries)):
            if excess <= 0:
                break
            if not entry.needs_ack:
                self._entries.remove(entry)
                excess -= 1


class ToastQueue(QObject):
    """Decides which notifications are on screen as toasts and for how long.

    At most :attr:`MAX_VISIBLE` toasts are shown; newer ones replace the oldest non-critical
    toast and the rest are counted as overflow ("+3 more"), which stays reachable in the
    history. Hovering the stack pauses every countdown.

    Signals:
        changed(): The visible toasts or the overflow count changed.
    """

    MAX_VISIBLE = 3

    changed = Signal()

    def __init__(self, hub: NotificationHub, parent: QObject | None = None):
        super().__init__(parent)
        self._hub = hub
        self._visible: list[str] = []  # oldest first
        self._timers: dict[str, QTimer] = {}
        self._remaining: dict[str, int] = {}
        self._started: dict[str, float] = {}
        self._paused = False
        self._suspended = False
        self.overflow = 0
        hub.posted.connect(self._on_posted)
        hub.changed.connect(self._on_hub_changed)
        hub.scan_started.connect(self.dismiss_transient)

    @property
    def visible_ids(self) -> list[str]:
        """Ids of the toasts on screen, oldest first."""
        return list(self._visible)

    def set_suspended(self, suspended: bool) -> None:
        """Hide all toasts while the history drawer is open; they stay in the history."""
        self._suspended = suspended
        if suspended:
            self.dismiss_all(keep_critical=False)

    def set_paused(self, paused: bool) -> None:
        """Pause or resume all countdowns, e.g. while the pointer is over the stack."""
        if paused == self._paused:
            return
        self._paused = paused
        now = time.monotonic()
        for entry_id, timer in self._timers.items():
            if paused:
                elapsed = int((now - self._started[entry_id]) * 1000)
                self._remaining[entry_id] = max(500, self._remaining[entry_id] - elapsed)
                timer.stop()
            else:
                self._started[entry_id] = now
                timer.start(self._remaining[entry_id])

    def dismiss(self, entry_id: str) -> None:
        """Close one toast; the entry stays in the history."""
        if entry_id not in self._visible:
            return
        self._visible.remove(entry_id)
        self._stop_timer(entry_id)
        self.changed.emit()

    def dismiss_transient(self) -> None:
        """Close all toasts except unacknowledged critical errors (used when a scan starts)."""
        self.dismiss_all(keep_critical=True)

    def dismiss_all(self, keep_critical: bool = True) -> None:
        """Close all toasts, optionally keeping the critical ones."""
        keep = []
        for entry_id in self._visible:
            entry = self._hub.get(entry_id)
            if keep_critical and entry is not None and entry.needs_ack:
                keep.append(entry_id)
            else:
                self._stop_timer(entry_id)
        changed = keep != self._visible or self.overflow
        self._visible = keep
        self.overflow = 0
        if changed:
            self.changed.emit()

    def cleanup(self) -> None:
        """Stop all timers and disconnect from the hub."""
        for entry_id in list(self._timers):
            self._stop_timer(entry_id)
        for signal, slot in (
            (self._hub.posted, self._on_posted),
            (self._hub.changed, self._on_hub_changed),
            (self._hub.scan_started, self.dismiss_transient),
        ):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    # ------------------------------------------------------------------ internals
    def _on_posted(self, entry_id: str) -> None:
        if self._suspended:
            return
        entry = self._hub.get(entry_id)
        if entry is None:
            return
        if entry_id in self._visible:
            # a repeat: move it to the newest position and restart its countdown
            self._visible.remove(entry_id)
            self._visible.append(entry_id)
            self._start_timer(entry)
            self.changed.emit()
            return
        if len(self._visible) >= self.MAX_VISIBLE:
            victim = next(
                (i for i in self._visible if not getattr(self._hub.get(i), "needs_ack", False)),
                None,
            )
            if victim is None and not entry.needs_ack:
                self.overflow += 1
                self.changed.emit()
                return
            victim = victim or self._visible[0]
            self._visible.remove(victim)
            self._stop_timer(victim)
            self.overflow += 1
        self._visible.append(entry_id)
        self._start_timer(entry)
        self.changed.emit()

    def _on_hub_changed(self) -> None:
        gone = [
            i
            for i in self._visible
            if (entry := self._hub.get(i)) is None
            or (entry.severity == Severity.CRITICAL and entry.acknowledged)
        ]
        for entry_id in gone:
            self._visible.remove(entry_id)
            self._stop_timer(entry_id)
        if gone:
            self.changed.emit()

    def _start_timer(self, entry: NotificationEntry) -> None:
        self._stop_timer(entry.id)
        lifetime = SEVERITY_META[entry.severity]["lifetime"]
        if lifetime <= 0:
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda entry_id=entry.id: self.dismiss(entry_id))
        self._timers[entry.id] = timer
        self._remaining[entry.id] = lifetime
        self._started[entry.id] = time.monotonic()
        if not self._paused:
            timer.start(lifetime)

    def _stop_timer(self, entry_id: str) -> None:
        timer = self._timers.pop(entry_id, None)
        self._remaining.pop(entry_id, None)
        self._started.pop(entry_id, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()


def entry_row(entry: NotificationEntry, tokens: ThemeTokens, now: float | None = None) -> dict:
    """Flat dictionary describing one entry, consumed by both views."""
    meta = SEVERITY_META[entry.severity]
    color = severity_color(tokens, entry.severity)
    subtitle = [part for part in (entry.source, relative_time(entry.updated, now)) if part]
    if entry.scan_number is not None:
        subtitle.insert(1 if entry.source else 0, f"Scan #{entry.scan_number}")
    return {
        "id": entry.id,
        "entryId": entry.id,
        "severity": entry.severity.value,
        "severityLabel": meta["label"],
        "icon": meta["icon"],
        "color": color.name(),
        "tint": tokens.soft(color, 0.14).name(),
        "title": entry.title,
        "body": entry.body,
        "details": entry.details,
        "hasDetails": bool(entry.details),
        "source": entry.source,
        "meta": " · ".join(subtitle),
        "time": relative_time(entry.updated, now),
        "timeAbs": absolute_time(entry.updated),
        "firstAbs": absolute_time(entry.created),
        "scan": "" if entry.scan_number is None else f"#{entry.scan_number}",
        "count": entry.count,
        "unread": not entry.read,
        "needsAck": entry.needs_ack,
        "critical": entry.severity == Severity.CRITICAL,
    }


class NotificationHostBase(QObject):
    """Attach the notification UI (toasts, history drawer, bell) to a window.

    Subclasses implement :meth:`_create_views`, :meth:`_sync_views` and :meth:`_place_views`.

    Args:
        window(QWidget): Window to overlay, usually a ``QMainWindow``.
        status_bar(QStatusBar | None): Where to put the bell; defaults to the window's status
            bar if it is a ``QMainWindow``. Pass ``None`` on a plain widget to skip the bell.
        dispatcher: ``BECDispatcher`` used to receive BEC alarms; optional.
    """

    TOAST_WIDTH = 380
    DRAWER_WIDTH = 400
    MARGIN = 16

    drawer_toggled = Signal(bool)

    def __init__(self, window: QWidget, status_bar: QStatusBar | None = None, dispatcher=None):
        super().__init__(window)
        self.window = window
        self.hub = NotificationHub.instance()
        self.hub.register_host()
        self.hub.connect_bec(dispatcher)
        self.queue = ToastQueue(self.hub, self)
        self.drawer_open = False
        self.filter_key = "all"
        self.search = ""
        self.selected_id: str | None = None
        self._sync_pending = False
        # set by a container that hosts the drawer itself (the main app's system dock): the
        # drawer is then laid out by that container, and toasts keep clear of ``right_inset``
        self.drawer_docked = False
        self.right_inset = 0
        if status_bar is None and isinstance(window, QMainWindow):
            status_bar = window.statusBar()
        self.status_bar = status_bar
        self._create_views()
        self.hub.changed.connect(self.sync)
        self.queue.changed.connect(self.sync)
        self._tick = QTimer(self)
        self._tick.setInterval(30_000)
        self._tick.timeout.connect(self.sync)
        self._tick.start()
        app = QApplication.instance()
        theme = getattr(app, "theme", None)
        if theme is not None:
            theme.theme_changed.connect(self._on_theme_changed)
        window.installEventFilter(self)
        self._cleaned = False
        self.sync_now()

    # ------------------------------------------------------------------ actions
    def toggle_drawer(self) -> None:
        """Open or close the history drawer."""
        self.set_drawer_open(not self.drawer_open)

    def set_drawer_open(self, open_: bool) -> None:
        """Open or close the history drawer. Opening marks everything as read."""
        changed = bool(open_) != self.drawer_open
        self.drawer_open = bool(open_)
        self.queue.set_suspended(self.drawer_open)
        if self.drawer_open:
            self.hub.mark_read()
        else:
            self.selected_id = None
        self.sync()
        if changed:
            self.drawer_toggled.emit(self.drawer_open)

    def open_details(self, entry_id: str) -> None:
        """Open the drawer on the details of one entry (the toast's Details action)."""
        self.selected_id = entry_id
        self.set_drawer_open(True)

    def select(self, entry_id: str | None) -> None:
        """Show the details of ``entry_id``; None goes back to the list."""
        self.selected_id = entry_id or None
        self.sync()

    def set_filter(self, key: str) -> None:
        """Filter the history by one of :data:`FILTERS`."""
        self.filter_key = key if key in FILTERS else "all"
        self.sync()

    def set_search(self, text: str) -> None:
        """Filter the history by text in title, message, source or details."""
        self.search = text or ""
        self.sync()

    def acknowledge(self, entry_id: str) -> None:
        """Acknowledge a critical error."""
        self.hub.acknowledge(entry_id)

    def remove(self, entry_id: str) -> None:
        """Remove an entry from the history."""
        if self.selected_id == entry_id:
            self.selected_id = None
        self.queue.dismiss(entry_id)
        self.hub.remove(entry_id)

    def dismiss_toast(self, entry_id: str) -> None:
        """Close a toast without touching the history."""
        entry = self.hub.get(entry_id)
        if entry is not None and entry.needs_ack:
            self.hub.acknowledge(entry_id)
        self.queue.dismiss(entry_id)
        if entry is not None:
            self.hub.mark_read([entry_id])

    def copy_details(self, entry_id: str) -> bool:
        """Copy a plain-text report of the entry to the clipboard."""
        entry = self.hub.get(entry_id)
        if entry is None:
            return False
        QApplication.clipboard().setText(entry.copy_text())
        return True

    def mark_all_read(self) -> None:
        """Mark the whole history as read."""
        self.hub.mark_read()

    def clear_history(self) -> None:
        """Clear the history; unacknowledged critical errors stay."""
        self.selected_id = None
        self.hub.clear()

    def set_toasts_hovered(self, hovered: bool) -> None:
        """Pause the toast countdowns while the pointer is over them."""
        self.queue.set_paused(hovered)

    # ------------------------------------------------------------------ state
    def filtered_entries(self) -> list[NotificationEntry]:
        """History entries matching the filter and search, critical ones pinned on top."""
        severities = FILTERS[self.filter_key][1]
        needle = self.search.strip().lower()
        rows = []
        for entry in self.hub.entries:
            if entry.severity not in severities:
                continue
            if needle and not any(
                needle in text.lower()
                for text in (entry.title, entry.body, entry.source, entry.details)
            ):
                continue
            rows.append(entry)
        rows.sort(key=lambda e: not e.needs_ack)  # stable: keeps newest first otherwise
        return rows

    def view_state(self) -> dict:
        """Everything the views need to render, as plain Python data."""
        tokens = ThemeTokens()
        now = time.time()
        entries = self.hub.entries
        counts = {
            key: sum(1 for e in entries if e.severity in severities)
            for key, (_label, severities) in FILTERS.items()
        }
        toasts = []
        if not self.drawer_open:
            for entry_id in self.queue.visible_ids:
                entry = self.hub.get(entry_id)
                if entry is not None:
                    toasts.append(entry_row(entry, tokens, now))
        selected = self.hub.get(self.selected_id) if self.selected_id else None
        top = self.hub.top_unread_severity()
        unread = self.hub.unread_count()
        open_criticals = sum(1 for e in entries if e.needs_ack)
        if open_criticals:
            bell_tip = f"{open_criticals} critical error(s) need attention"
        elif unread:
            bell_tip = f"{unread} unread notification(s)"
        else:
            bell_tip = "Notifications"
        return {
            "drawerOpen": self.drawer_open,
            "toasts": toasts,
            "overflow": self.queue.overflow if toasts else 0,
            # the list is only built while the drawer is visible
            "rows": (
                [entry_row(e, tokens, now) for e in self.filtered_entries()]
                if self.drawer_open
                else []
            ),
            "filters": [
                {"key": key, "label": label, "count": counts[key], "active": key == self.filter_key}
                for key, (label, _sev) in FILTERS.items()
            ],
            "filterKey": self.filter_key,
            "search": self.search,
            "total": len(entries),
            "selected": entry_row(selected, tokens, now) if selected is not None else None,
            "unread": unread,
            "openCriticals": open_criticals,
            "bellColor": (
                severity_color(tokens, top).name() if top is not None else tokens.fg_muted.name()
            ),
            "bellIcon": "notifications_active" if unread or open_criticals else "notifications",
            "bellTip": bell_tip,
        }

    def sync(self, *_args) -> None:
        """Schedule a view update; bursts of changes are folded into one update."""
        if self._cleaned or self._sync_pending:
            return
        self._sync_pending = True
        QTimer.singleShot(0, self.sync_now)

    def sync_now(self) -> None:
        """Push the current state into the views and re-place them right away."""
        self._sync_pending = False
        if self._cleaned:
            return
        state = self.view_state()
        self._sync_views(state)
        self._place_views()

    def content_rect(self) -> QRect:
        """Area of the window the overlays may cover: below menu and tool bars, above status."""
        rect = self.window.rect()
        top = 0
        bottom = rect.bottom()
        if isinstance(self.window, QMainWindow):
            menu = self.window.menuWidget()
            if menu is not None and menu.isVisible():
                top = menu.geometry().bottom() + 1
            central = self.window.centralWidget()
            if central is not None:
                top = max(top, central.geometry().top())
            status = self.window.statusBar() if self.window.statusBar() else None
            if status is not None and status.isVisible():
                bottom = status.geometry().top() - 1
        width = max(0, rect.width() - self.right_inset)
        return QRect(rect.left(), top, width, max(0, bottom - top + 1))

    def toast_geometry(self, content_height: int) -> QRect:
        """Bottom-right rectangle for a toast stack of ``content_height`` pixels."""
        area = self.content_rect()
        width = min(self.TOAST_WIDTH, max(200, area.width() - 2 * self.MARGIN))
        height = min(content_height, max(0, area.height() - 2 * self.MARGIN))
        return QRect(
            area.right() - self.MARGIN - width + 1,
            area.bottom() - self.MARGIN - height + 1,
            width,
            height,
        )

    def drawer_geometry(self) -> QRect:
        """Right-edge rectangle of the history drawer."""
        area = self.content_rect()
        width = min(self.DRAWER_WIDTH, area.width())
        return QRect(area.right() - width + 1, area.top(), width, area.height())

    # ------------------------------------------------------------------ plumbing
    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        if watched is self.window and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self._place_views()
        return False

    def _on_theme_changed(self, *_args) -> None:
        self._apply_theme()
        self.sync()

    def cleanup(self) -> None:
        """Detach from the window and the hub."""
        if self._cleaned:
            return
        self._cleaned = True
        self._tick.stop()
        self.queue.cleanup()
        for signal, slot in ((self.hub.changed, self.sync), (self.queue.changed, self.sync)):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        app = QApplication.instance()
        theme = getattr(app, "theme", None)
        if theme is not None:
            try:
                theme.theme_changed.disconnect(self._on_theme_changed)
            except (RuntimeError, TypeError):
                pass
        if shiboken6.isValid(self.window):
            self.window.removeEventFilter(self)
        self.hub.unregister_host()
        self._destroy_views()

    # ------------------------------------------------------------------ for subclasses
    def _create_views(self) -> None:
        raise NotImplementedError

    def _sync_views(self, state: dict) -> None:
        raise NotImplementedError

    def _place_views(self) -> None:
        raise NotImplementedError

    def _apply_theme(self) -> None:
        """Re-style the views after a theme change; QML follows the theme by itself."""

    def _destroy_views(self) -> None:
        """Release the views."""
