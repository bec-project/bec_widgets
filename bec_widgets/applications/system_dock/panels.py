"""
The core panels of the main app's system dock.

Each panel wraps a widget from its own module (the QML or the QWidget version, picked with
``ui``) and turns that widget's model into the rail indicator. The widgets are created up front so
the indicators are live while the panels are closed.
"""

from __future__ import annotations

from qtpy.QtGui import QColor
from qtpy.QtWidgets import QFrame, QVBoxLayout, QWidget

from bec_widgets.applications.system_dock.system_dock import RailIndicator, SystemPanel
from bec_widgets.utils.quick.host import ThemeTokens

UI_KINDS = ("qml", "qwidget")
STATES_MIN_WIDTH = 660


def _ui(ui: str) -> str:
    ui = (ui or "qml").lower()
    return ui if ui in UI_KINDS else "qml"


class ScanProgressPanel(SystemPanel):
    """Progress of the running scan, in a compact flyout.

    The rail shows a live progress ring while a scan runs, amber while it is paused.
    """

    def __init__(self, parent: QWidget | None = None, ui: str = "qml", client=None):
        # pylint: disable=import-outside-toplevel
        if _ui(ui) == "qml":
            from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar_qml import (
                ScanProgressBarQml as Progress,
            )
        else:
            from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar_modern import (
                ScanProgressBarModern as Progress,
            )
        content = QFrame(parent)
        content.setObjectName("systemDockProgress")
        self.progress = Progress(parent=content, client=client, rpc_exposed=False)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(self.progress)
        layout.addStretch(1)
        super().__init__(
            "progress",
            "Scan progress",
            "play_arrow",
            "Progress",
            content,
            parent,
            preferred_height=self.progress.sizeHint().height() + 24,
        )
        self.progress.model.changed.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args) -> None:
        """Recompute the indicator from the progress model."""
        tokens = ThemeTokens()
        model = self.progress.model
        if model.active:
            summary = f"{model.title} · {int(round(model.fraction * 100))} %"
            if model.state == "paused":
                summary = f"Paused · {summary}"
        elif model.title == "No scan yet":
            summary = "No scan yet"
        else:
            summary = f"{model.stateLabel} · {model.title}"
        self.set_indicator(
            RailIndicator(
                progress=float(model.fraction) if model.active else None,
                progress_color=QColor(
                    tokens.warning if model.state == "paused" else tokens.primary
                ),
                tooltip=summary,
                summary=summary,
            )
        )


class QueuePanel(SystemPanel):
    """The scan queue.

    The rail shows the number of waiting scans: blue while the queue runs, amber when it is
    paused and red when it is locked. Without waiting scans a paused or locked queue shows a dot.
    """

    def __init__(self, parent: QWidget | None = None, ui: str = "qml", client=None):
        # pylint: disable=import-outside-toplevel
        if _ui(ui) == "qml":
            from bec_widgets.widgets.services.bec_queue.bec_queue import BECQueue as Queue
        else:
            from bec_widgets.widgets.services.bec_queue.bec_queue_qt import BECQueueQt as Queue
        self.queue = Queue(parent=parent, client=client, rpc_exposed=False)
        super().__init__("queue", "Scan queue", "format_list_numbered", "Queue", self.queue, parent)
        self.queue.controller.changed.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args) -> None:
        """Recompute the indicator from the queue controller."""
        tokens = ThemeTokens()
        queue = self.queue.controller
        waiting = int(queue.waitingCount)
        state = str(queue.state)
        color = {"paused": tokens.warning, "locked": tokens.danger}.get(state, tokens.primary)
        parts = {"paused": ["Paused"], "locked": ["Locked"], "running": ["Running"]}.get(
            state, ["Idle"]
        )
        if waiting:
            parts.append(f"{waiting} waiting")
        if state == "locked" and queue.lockReason:
            parts.append(str(queue.lockReason))
        summary = " · ".join(parts)
        self.set_indicator(
            RailIndicator(
                badge=str(waiting) if waiting else "",
                badge_color=QColor(color),
                dot_color=QColor(color) if state in ("paused", "locked") else None,
                tooltip=summary,
                summary=summary,
            )
        )


class ServicesPanel(SystemPanel):
    """BEC services (status box). The rail shows a dot only when something is wrong."""

    def __init__(self, parent: QWidget | None = None, ui: str = "qml", client=None):
        # pylint: disable=import-outside-toplevel
        from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECStatusBox

        self.box = BECStatusBox(
            parent=parent,
            client=client,
            view="qml" if _ui(ui) == "qml" else "widgets",
            rpc_exposed=False,
        )
        super().__init__("services", "BEC status", "monitor_heart", "Status", self.box, parent)
        self.box.model.summaryChanged.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args) -> None:
        """Recompute the indicator from the status model."""
        tokens = ThemeTokens()
        model = self.box.model
        dot = {"warning": tokens.warning, "emergency": tokens.danger}.get(model.tone)
        summary = model.headline or "Waiting for services"
        self.set_indicator(
            RailIndicator(
                dot_color=QColor(dot) if dot is not None else None,
                tooltip=" · ".join(t for t in (model.headline, model.detail) if t),
                summary=summary,
            )
        )


class NotificationsPanel(SystemPanel):
    """The notification history, docked from the window's notification host.

    The host's history drawer moves into the panel; opening the panel opens the drawer (which
    marks everything read and holds back toasts) and the toast "Details" action opens the panel.
    The rail shows the unread count in the colour of the most serious unread entry, pulsing while
    a critical error waits to be acknowledged.
    """

    def __init__(self, host, parent: QWidget | None = None):
        # pylint: disable=import-outside-toplevel
        from bec_widgets.widgets.containers.main_window.addons.notification_center.notification_ux_common import (
            Severity,
            severity_color,
        )

        self._severity_color = severity_color
        self._critical = Severity.CRITICAL
        self.host = host
        content = QWidget(parent)
        content.setObjectName("systemDockNotifications")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        host.drawer_docked = True
        host.drawer.setParent(content)
        layout.addWidget(host.drawer)
        # the dock header already has the title and close button
        for name in ("title", "close_btn"):
            widget = getattr(host.drawer, name, None)
            if widget is not None:
                widget.hide()
        root = host.drawer.rootObject() if hasattr(host.drawer, "rootObject") else None
        if root is not None:
            root.setProperty("embedded", True)
        super().__init__(
            "notifications", "Notifications", "notifications", "Alerts", content, parent
        )
        self.dock = None
        host.hub.changed.connect(self.refresh)
        host.drawer_toggled.connect(self._on_drawer_toggled)
        self.refresh()

    def attach(self, dock) -> None:
        """Let the toast "Details" action open this panel in ``dock``."""
        self.dock = dock

    def set_shown(self, shown: bool) -> None:
        if self.host.drawer_open != shown:
            self.host.set_drawer_open(shown)

    def _on_drawer_toggled(self, open_: bool) -> None:
        if self.dock is None:
            return
        if open_ and not self.dock.is_shown(self.panel_id):
            self.dock.open_panel(self.panel_id, sticky=True)
        elif not open_ and self.dock.is_shown(self.panel_id):
            self.dock.close_panel(self.panel_id)

    def refresh(self, *_args) -> None:
        """Recompute the indicator from the notification hub."""
        tokens = ThemeTokens()
        hub = self.host.hub
        unread = hub.unread_count()
        top = hub.top_unread_severity()
        criticals = sum(1 for e in hub.entries if e.needs_ack)
        if criticals:
            summary = f"{criticals} critical error(s) need attention"
            color = self._severity_color(tokens, self._critical)
        elif unread:
            summary = f"{unread} unread"
            color = self._severity_color(tokens, top) if top is not None else tokens.primary
        else:
            summary = f"{len(hub.entries)} in history" if hub.entries else "All caught up"
            color = tokens.primary
        count = max(unread, criticals)
        self.set_indicator(
            RailIndicator(
                badge=("99+" if count > 99 else str(count)) if count else "",
                badge_color=QColor(color),
                pulse=bool(criticals),
                tooltip=summary,
                summary=summary,
            )
        )


class BeamlineStatesPanel(SystemPanel):
    """Beamline states with the scan interlock.

    The rail shows a red "!" when the armed interlock trips (scans are blocked) and an amber dot
    when any state is invalid or in warning.
    """

    def __init__(self, parent: QWidget | None = None, ui: str = "qml", client=None):
        # pylint: disable=import-outside-toplevel
        if _ui(ui) == "qml":
            from bec_widgets.widgets.services.beamline_states.modern.beamline_states_qml import (
                BeamlineStatesQML as States,
            )
        else:
            from bec_widgets.widgets.services.beamline_states.modern.beamline_states_widget import (
                BeamlineStatesWidget as States,
            )
        self.states = States(parent=parent, client=client, rpc_exposed=False)
        super().__init__(
            "beamline_states",
            "Beamline states",
            "verified_user",
            "States",
            self.states,
            parent,
            # the states view has no compact layout yet: its chip row needs this much
            min_width=STATES_MIN_WIDTH,
        )
        self.states.controller.changed.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args) -> None:
        """Recompute the indicator from the states controller."""
        tokens = ThemeTokens()
        controller = self.states.controller
        blocking = list(controller.blockingStates)
        counts = dict(controller.counts)
        total = int(controller.totalCount)
        invalid = int(counts.get("invalid", 0))
        warning = int(counts.get("warning", 0))
        interlock = "interlock armed" if controller.interlockArmed else "interlock off"
        badge, dot = "", None
        if blocking:
            badge = "!"
            summary = f"Scans blocked by {', '.join(blocking)}"
        elif invalid or warning:
            dot = tokens.warning
            issues = []
            if invalid:
                issues.append(f"{invalid} invalid")
            if warning:
                issues.append(f"{warning} warning")
            summary = f"{' · '.join(issues)} of {total} · {interlock}"
        elif total:
            summary = f"All {total} valid · {interlock}"
        else:
            summary = "No states configured"
        self.set_indicator(
            RailIndicator(
                badge=badge,
                badge_color=QColor(tokens.danger),
                dot_color=QColor(dot) if dot is not None else None,
                pulse=bool(blocking),
                tooltip=summary,
                summary=summary,
            )
        )


class DeviceBrowserPanel(SystemPanel):
    """The device browser (QWidget only: there is no QML version yet)."""

    def __init__(self, parent: QWidget | None = None, client=None):
        # pylint: disable=import-outside-toplevel
        from bec_widgets.widgets.services.device_browser.device_browser import DeviceBrowser

        self.browser = DeviceBrowser(parent=parent, client=client, rpc_exposed=False)
        super().__init__("devices", "Devices", "memory", "Devices", self.browser, parent)
        self.set_indicator(RailIndicator(tooltip="Browse and edit the devices of this session"))


def build_core_panels(dock, ui: str = "qml", notification_host=None, client=None) -> None:
    """Add the core panels to ``dock`` in rail order.

    Args:
        dock(SystemDock): The dock to fill.
        ui(str): ``qml`` or ``qwidget``: which version of each widget to use.
        notification_host: The window's reworked notification host; without one there is no
            notifications panel (the legacy notification centre stays in the status bar).
        client: BEC client passed to the widgets.
    """
    dock.add_panel(ScanProgressPanel(dock, ui=ui, client=client))
    dock.add_panel(QueuePanel(dock, ui=ui, client=client), shortcut="Ctrl+Shift+Q")
    dock.add_panel(ServicesPanel(dock, ui=ui, client=client), shortcut="Ctrl+Shift+S")
    dock.add_panel(BeamlineStatesPanel(dock, ui=ui, client=client), shortcut="Ctrl+Shift+B")
    if notification_host is not None:
        panel = NotificationsPanel(notification_host, dock)
        dock.add_panel(panel, shortcut="Ctrl+Shift+N")
        panel.attach(dock)
    dock.add_separator()
    dock.add_panel(DeviceBrowserPanel(dock, client=client))
