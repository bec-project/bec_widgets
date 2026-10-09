"""
View-independent logic shared by the QML and QWidget beamline-state views.

:class:`BeamlineStatesController` owns every BEC subscription and backend call (available
states, per-state status, scan interlock) plus the filter state. It publishes the rows to show
through :class:`BeamlineStatesModel`, a flat list model with roles that both views read: QML
through role names, the QWidget view through :meth:`BeamlineStatesModel.row`.
"""

from __future__ import annotations

from typing import Any

from bec_lib import messages
from bec_lib.endpoints import MessageEndpoints
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

from bec_widgets.widgets.services.beamline_states.dialogs import BEAMLINE_STATE_STATUS_LABELS

STATUSES = ("invalid", "warning", "unknown", "valid")
DEFAULT_ACCEPTED = ["valid", "warning"]
NO_INFO_LABEL = "No state information available."

INTERLOCK_SECTION = "interlock"
OTHERS_SECTION = "others"
SECTION_TITLES = {
    INTERLOCK_SECTION: "Watched by scan interlock",
    OTHERS_SECTION: "Not watched by scan interlock",
}

ROLES = (
    "name",
    "status",
    "statusText",
    "label",
    "device",
    "stateType",
    "details",
    "watched",
    "accepted",
    "triggerOnWarning",
    "triggered",
    "section",
    "filteredOut",
)


class BeamlineStatesModel(QAbstractListModel):
    """Flat list of displayed beamline states, updated by key-based diffs."""

    _ROLE_IDS = {name: Qt.ItemDataRole.UserRole + 1 + i for i, name in enumerate(ROLES)}

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
        return {role: QByteArray(name.encode()) for name, role in self._ROLE_IDS.items()}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return row["name"]
        for name, role_id in self._ROLE_IDS.items():
            if role_id == role:
                return row[name]
        return None

    def row(self, i: int) -> dict[str, Any]:
        """Return the row dictionary at position ``i``."""
        return self._rows[i]

    def rows(self) -> list[dict[str, Any]]:
        """Return all rows in display order."""
        return list(self._rows)

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        """Replace the rows, emitting minimal remove/insert/move/change notifications."""
        new_names = [row["name"] for row in rows]
        new_set = set(new_names)
        for i in reversed(range(len(self._rows))):
            if self._rows[i]["name"] not in new_set:
                self.beginRemoveRows(QModelIndex(), i, i)
                self._rows.pop(i)
                self.endRemoveRows()
        for target, new_row in enumerate(rows):
            current = next(
                (i for i, row in enumerate(self._rows) if row["name"] == new_row["name"]), None
            )
            if current is None:
                self.beginInsertRows(QModelIndex(), target, target)
                self._rows.insert(target, new_row)
                self.endInsertRows()
                continue
            if current != target:
                self.beginMoveRows(QModelIndex(), current, current, QModelIndex(), target)
                self._rows.insert(target, self._rows.pop(current))
                self.endMoveRows()
            if self._rows[target] != new_row:
                changed = [
                    self._ROLE_IDS[key] for key in ROLES if self._rows[target][key] != new_row[key]
                ]
                self._rows[target] = new_row
                index = self.index(target, 0)
                self.dataChanged.emit(index, index, changed)


class BeamlineStatesController(QObject):
    """
    BEC-facing logic of the beamline-state views.

    Args:
        client: BEC client, used for ``beamline_states`` and the scan-interlock actor.
        dispatcher: ``BECDispatcher`` of the hosting widget.
        parent: Owning QObject.
    """

    changed = Signal()
    error_occurred = Signal(str, str)
    add_requested = Signal()
    edit_requested = Signal(str)
    _interlock_enabled_streamed = Signal(bool)

    def __init__(self, client, dispatcher, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.client = client
        self._dispatcher = dispatcher
        self.model = BeamlineStatesModel(self)
        self._configs: dict[str, messages.BeamlineStateConfig] = {}
        self._order: list[str] = []
        self._status: dict[str, tuple[str, str]] = {}
        self._subscribed: set[str] = set()
        self._interlock = client.builtin_actors.scan_interlock
        self._interlock_enabled = False
        self._watched: dict[str, list[str]] = {}
        self._preferred_accepted: dict[str, list[str]] = {}
        self._status_filter: set[str] = set()
        self._search = ""
        self._show_filtered = False
        self._hidden_count = 0

        dispatcher.connect_slot(
            self.update_available_states, MessageEndpoints.available_beamline_states()
        )
        dispatcher.connect_slot(
            self.refresh_interlock,
            MessageEndpoints.builtin_actor_update_notif("ScanInterlockActor"),
        )
        self._interlock_enabled_streamed.connect(self._set_interlock_enabled)
        self._enabled_config = getattr(self._interlock, "_enabled", None)
        if self._enabled_config is not None and hasattr(self._enabled_config, "subscribe"):
            self._enabled_config.subscribe(self._on_enabled_stream)
        self.refresh_interlock()
        self.refresh_states()

    # ------------------------------------------------------------------ BEC input

    def refresh_states(self) -> None:
        """Load the cached list of available states."""
        msg = self.client.connector.get_last(
            MessageEndpoints.available_beamline_states(), key="data"
        )
        if msg is not None:
            self.update_available_states(msg.content, msg.metadata)

    def update_available_states(self, content: dict, _metadata: dict | None = None) -> None:
        """Apply ``AvailableBeamlineStatesMessage`` content."""
        configs: list[messages.BeamlineStateConfig] = content.get("states", [])
        self._configs = {state.name: state for state in configs}
        self._order = [state.name for state in configs]
        removed = self._subscribed - set(self._order)
        added = [name for name in self._order if name not in self._subscribed]
        if removed:
            self._dispatcher.disconnect_slot(
                self.update_state, [MessageEndpoints.beamline_state(name) for name in removed]
            )
            for name in removed:
                self._status.pop(name, None)
        for name in added:
            msg = self.client.connector.get_last(MessageEndpoints.beamline_state(name), key="data")
            if msg is not None:
                self._store_status(name, msg.content)
        if added:
            self._dispatcher.connect_slot(
                self.update_state, [MessageEndpoints.beamline_state(name) for name in added]
            )
        self._subscribed = set(self._order)
        self._rebuild()

    def update_state(self, content: dict, _metadata: dict | None = None) -> None:
        """Apply a ``BeamlineStateMessage`` for one of the displayed states."""
        name = content.get("name")
        if name not in self._configs:
            return
        if self._store_status(name, content):
            self._rebuild()

    def _store_status(self, name: str, content: dict) -> bool:
        status = str(content.get("status", "unknown")).lower()
        status = status if status in BEAMLINE_STATE_STATUS_LABELS else "unknown"
        value = (status, str(content.get("label", NO_INFO_LABEL)))
        if self._status.get(name) == value:
            return False
        self._status[name] = value
        return True

    def refresh_interlock(self, *_args) -> None:
        """Re-read the scan-interlock configuration from BEC."""
        try:
            self._interlock_enabled = bool(self._interlock.enabled)
            self._watched = {
                name: list(statuses) for name, statuses in self._interlock.states_watched.items()
            }
        except Exception as exc:  # pylint: disable=broad-except
            self.error_occurred.emit("Scan Interlock Unavailable", str(exc))
            return
        self._rebuild()

    def _on_enabled_stream(self, enabled: bool) -> None:
        # Called from the connector thread; hop to the Qt thread through a queued signal.
        self._interlock_enabled_streamed.emit(bool(enabled))

    def _set_interlock_enabled(self, enabled: bool) -> None:
        if enabled != self._interlock_enabled:
            self._interlock_enabled = enabled
            self._rebuild()

    # ------------------------------------------------------------------ derived state

    def status_of(self, name: str) -> tuple[str, str]:
        """Return ``(status, label)`` of a state."""
        return self._status.get(name, ("unknown", NO_INFO_LABEL))

    def _accepted(self, name: str) -> list[str]:
        return self._watched.get(name) or self._preferred_accepted.get(name, DEFAULT_ACCEPTED)

    def _is_triggered(self, name: str) -> bool:
        accepted = self._watched.get(name)
        if not self._interlock_enabled or not accepted:
            return False
        return self.status_of(name)[0] not in accepted

    def _passes_filters(self, name: str) -> bool:
        if self._status_filter and self.status_of(name)[0] not in self._status_filter:
            return False
        tokens = [token.strip().casefold() for token in self._search.split(",") if token.strip()]
        if not tokens:
            return True
        device = self._device(name) or ""
        haystack = f"{name} {device}".casefold()
        return any(token in haystack for token in tokens)

    def _device(self, name: str) -> str | None:
        config = self._configs.get(name)
        device = config.parameters.get("device") if config is not None else None
        return str(device) if device else None

    def _make_row(self, name: str, filtered_out: bool) -> dict[str, Any]:
        config = self._configs[name]
        status, label = self.status_of(name)
        accepted = self._accepted(name)
        details = [
            {"key": key, "value": str(value)}
            for key, value in config.parameters.items()
            if value is not None and value != ""
        ]
        return {
            "name": name,
            "status": status,
            "statusText": BEAMLINE_STATE_STATUS_LABELS[status],
            "label": label,
            "device": self._device(name) or "",
            "stateType": config.state_type,
            "details": details,
            "watched": name in self._watched,
            "accepted": ", ".join(s.upper() for s in accepted),
            "triggerOnWarning": "warning" not in accepted,
            "triggered": self._is_triggered(name),
            "section": INTERLOCK_SECTION if name in self._watched else OTHERS_SECTION,
            "filteredOut": filtered_out,
        }

    def _rebuild(self) -> None:
        rank = {status: i for i, status in enumerate(STATUSES)}
        position = {name: i for i, name in enumerate(self._order)}
        ordered = sorted(
            self._order,
            key=lambda name: (
                name not in self._watched,
                rank[self.status_of(name)[0]],
                position[name],
            ),
        )
        rows = []
        hidden = 0
        for name in ordered:
            # States watched by the interlock are always shown: they can block scans.
            passes = name in self._watched or self._passes_filters(name)
            if not passes:
                hidden += 1
                if not self._show_filtered:
                    continue
            rows.append(self._make_row(name, filtered_out=not passes))
        self._hidden_count = hidden
        self.model.set_rows(rows)
        self.changed.emit()

    # ------------------------------------------------------------------ properties for views

    @Property(bool, notify=changed)
    def interlockArmed(self) -> bool:  # noqa: N802
        """Whether the scan interlock is armed."""
        return self._interlock_enabled

    @Property(int, notify=changed)
    def watchedCount(self) -> int:  # noqa: N802
        """Number of states watched by the scan interlock."""
        return sum(1 for name in self._order if name in self._watched)

    @Property("QStringList", notify=changed)
    def blockingStates(self) -> list[str]:  # noqa: N802
        """Watched states currently tripping the armed interlock."""
        return [name for name in self._order if self._is_triggered(name)]

    @Property("QVariantMap", notify=changed)
    def counts(self) -> dict[str, int]:
        """Number of states per status."""
        counts = {status: 0 for status in STATUSES}
        for name in self._order:
            counts[self.status_of(name)[0]] += 1
        return counts

    @Property(int, notify=changed)
    def totalCount(self) -> int:  # noqa: N802
        """Number of configured states."""
        return len(self._order)

    @Property("QStringList", notify=changed)
    def statusFilter(self) -> list[str]:  # noqa: N802
        """Statuses selected in the summary chips; empty means all."""
        return sorted(self._status_filter, key=STATUSES.index)

    @Property(str, notify=changed)
    def searchText(self) -> str:  # noqa: N802
        """Name/device search text."""
        return self._search

    @Property(int, notify=changed)
    def hiddenCount(self) -> int:  # noqa: N802
        """Number of states hidden by the filters."""
        return self._hidden_count

    @Property(bool, notify=changed)
    def showFiltered(self) -> bool:  # noqa: N802
        """Whether states hidden by the filters are shown dimmed."""
        return self._show_filtered

    @Property(bool, notify=changed)
    def filtersActive(self) -> bool:  # noqa: N802
        """Whether any filter is set."""
        return bool(self._status_filter or self._search.strip())

    # ------------------------------------------------------------------ actions

    @Slot(str)
    def toggleStatusFilter(self, status: str) -> None:  # noqa: N802
        """Add or remove a status from the status filter."""
        self._status_filter ^= {status}
        self._rebuild()

    @Slot(str)
    def setSearchText(self, text: str) -> None:  # noqa: N802
        """Filter by state name or device (comma-separated tokens)."""
        if text != self._search:
            self._search = text
            self._rebuild()

    @Slot(bool)
    def setShowFiltered(self, show: bool) -> None:  # noqa: N802
        """Show or hide the states hidden by the filters."""
        self._show_filtered = bool(show)
        self._rebuild()

    @Slot()
    def clearFilters(self) -> None:  # noqa: N802
        """Reset all filters."""
        self._status_filter = set()
        self._search = ""
        self._show_filtered = False
        self._rebuild()

    @Slot(bool)
    def setInterlockArmed(self, armed: bool) -> None:  # noqa: N802
        """Arm or disarm the scan interlock."""
        try:
            self._interlock.enabled = bool(armed)
        except Exception as exc:  # pylint: disable=broad-except
            self.error_occurred.emit("Cannot Toggle Scan Interlock", str(exc))
            self.refresh_interlock()
            return
        self._interlock_enabled = bool(armed)
        self._rebuild()

    @Slot(str)
    def toggleWatched(self, name: str) -> None:  # noqa: N802
        """Add a state to, or remove it from, the scan interlock."""
        try:
            if name in self._watched:
                self._interlock.remove_state_from_interlock(name)
            else:
                self._interlock.add_state_to_interlock(name, self._accepted(name))
        except Exception as exc:  # pylint: disable=broad-except
            self.error_occurred.emit("Cannot Update Scan Interlock", str(exc))
            return
        self.refresh_interlock()

    @Slot(str, bool)
    def setTriggerOnWarning(self, name: str, trigger: bool) -> None:  # noqa: N802
        """Choose whether WARNING also trips the interlock for ``name``."""
        accepted = ["valid"] if trigger else list(DEFAULT_ACCEPTED)
        self._preferred_accepted[name] = accepted
        if name not in self._watched:
            self._rebuild()
            return
        try:
            self._interlock.add_state_to_interlock(name, accepted)
        except Exception as exc:  # pylint: disable=broad-except
            self.error_occurred.emit("Cannot Update Scan Interlock", str(exc))
            return
        self.refresh_interlock()

    def set_preferred_accepted(self, name: str, accepted: list[str]) -> None:
        """Remember the accepted statuses for a state not yet watched by the interlock."""
        self._preferred_accepted[name] = list(accepted)

    @Slot(str)
    def removeState(self, name: str) -> None:  # noqa: N802
        """Delete a beamline state from BEC (the view asks for confirmation first)."""
        try:
            self.client.beamline_states.delete(name)
        except Exception as exc:  # pylint: disable=broad-except
            self.error_occurred.emit("Cannot Remove State", str(exc))

    @Slot()
    def requestAdd(self) -> None:  # noqa: N802
        """Ask the hosting widget to open the add-state dialog."""
        self.add_requested.emit()

    @Slot(str)
    def requestEdit(self, name: str) -> None:  # noqa: N802
        """Ask the hosting widget to open the edit dialog for ``name``."""
        self.edit_requested.emit(name)

    def config(self, name: str) -> messages.BeamlineStateConfig | None:
        """Return the configuration of a state."""
        return self._configs.get(name)

    def state_summary(self) -> dict[str, dict[str, str]]:
        """Return every configured state with its ``status`` and ``label``."""
        return {
            name: {"status": status, "label": label}
            for name in self._order
            for status, label in [self.status_of(name)]
        }

    def cleanup(self) -> None:
        """Release all BEC subscriptions."""
        if self._enabled_config is not None:
            self._enabled_config.unsubscribe(self._on_enabled_stream)
            self._enabled_config = None
        self._dispatcher.disconnect_slot(
            self.update_available_states, MessageEndpoints.available_beamline_states()
        )
        self._dispatcher.disconnect_slot(
            self.refresh_interlock,
            MessageEndpoints.builtin_actor_update_notif("ScanInterlockActor"),
        )
        if self._subscribed:
            self._dispatcher.disconnect_slot(
                self.update_state,
                [MessageEndpoints.beamline_state(name) for name in self._subscribed],
            )
            self._subscribed = set()
