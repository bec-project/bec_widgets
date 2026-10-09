"""Logic shared by the QML and QWidget ports of the beamline state manager.

The ports keep the public API of :class:`BeamlineStateManager` (``clear_filters``,
``collapse_all``, ``state_summary``, ``refresh_states``, ``update_available_states``, the add and
filter dialogs and ``scan_interlock_enabled_changed``) but render from one display-ready state
instead of one ``BeamlineStatePill`` widget per state. The manager subscribes to every state
endpoint itself, so a state costs one row of data rather than a widget with its own connector
subscription.

Differences in the UX compared to the original manager:

* status counts double as quick status filters, and a search field filters by name or device;
* the scan interlock is a labelled switch with a banner naming the states that trip it;
* an expanded row shows the state parameters read-only, with Edit (a form dialog) and Remove.
"""

from __future__ import annotations

from typing import Any

from bec_lib import bl_states, messages
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.forms_from_types.pydantic_widget_form import PydanticWidgetForm
from bec_widgets.utils.ux_kit import PortedPropertiesMixin
from bec_widgets.widgets.services.beamline_states.dialogs import (
    BEAMLINE_STATE_STATUS_LABELS,
    SUPPORTED_BEAMLINE_STATES,
    AddBeamlineStateDialog,
    DeviceFilterDialog,
    StatusFilterDialog,
)

STATUS_ORDER = ("invalid", "warning", "unknown", "valid")
STATUS_TONES = {"valid": "success", "invalid": "danger", "warning": "warning", "unknown": "muted"}
STATUS_ICONS = {
    "valid": "check_circle",
    "invalid": "cancel",
    "warning": "warning",
    "unknown": "help",
}
STATUS_WORDS = {"valid": "valid", "invalid": "invalid", "warning": "warning", "unknown": "unknown"}
DEFAULT_INTERLOCK_STATUSES = ["valid", "warning"]


def state_device(config: messages.BeamlineStateConfig | None) -> str | None:
    """Device a state watches, if its parameters name one."""
    device = config.parameters.get("device") if config is not None else None
    return str(device) if device else None


def format_parameter(value: Any) -> str:
    """Compact text for a state parameter value."""
    if isinstance(value, float):
        return f"{value:g}"
    if value is None:
        return "—"
    return str(value)


def config_class_for(state_type: str) -> type[bl_states.BeamlineStateConfig] | None:
    """Pydantic config class of a supported state type, or ``None``."""
    for state_class in SUPPORTED_BEAMLINE_STATES:
        if state_type in {state_class.__name__, state_class.CONFIG_CLASS.state_type}:
            return state_class.CONFIG_CLASS
    return None


class EditBeamlineStateDialog(QDialog):
    """Form dialog that edits the parameters of one beamline state.

    Args:
        config(BeamlineStateConfig): Current configuration of the state.
        parent(QWidget): Parent widget.
        client: BEC client handed to the form (device pickers).
    """

    def __init__(self, config: messages.BeamlineStateConfig, parent=None, client=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit {config.name}")
        self._config: bl_states.BeamlineStateConfig | None = None
        config_class = config_class_for(config.state_type)
        if config_class is None:
            raise ValueError(f"Unsupported beamline state type '{config.state_type}'.")
        self.form = PydanticWidgetForm(
            config_class, parent=self, client=client, read_only_fields={"name"}
        )
        data = {"name": config.name}
        data.update(
            {
                key: value
                for key, value in config.parameters.items()
                if key in config_class.model_fields
            }
        )
        self.form.set_partial_data(data)
        self.form.mark_clean()

        header = QFormLayout()
        header.addRow("Type", QLabel(config.state_type, self))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.form)
        layout.addWidget(buttons)

    def accept(self) -> None:
        try:
            self._config = self.form.model_instance()  # type: ignore[assignment]
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.warning(self, "Invalid Beamline State", str(exc))
            return
        super().accept()

    @property
    def config_result(self) -> bl_states.BeamlineStateConfig | None:
        """Validated configuration after the dialog was accepted."""
        return self._config

    def cleanup(self) -> None:
        """Release the form's device subscriptions."""
        self.form.cleanup()


class BeamlineStatesPortBase(PortedPropertiesMixin, BECWidget, QWidget):
    """Shared implementation of the beamline state manager ports.

    Subclasses build the renderer in :meth:`_init_view` and redraw it from :meth:`view_state` in
    :meth:`_sync_view`.
    """

    PLUGIN = False
    RPC = False
    rpc_widget_class = "BeamlineStateManager"
    ICON_NAME = "format_list_bulleted"
    USER_ACCESS = [
        "clear_filters",
        "collapse_all",
        "state_summary",
        "remove",
        "attach",
        "detach",
        "screenshot",
    ]

    scan_interlock_enabled_changed = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        client=None,
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(parent=parent, client=client, config=config, gui_id=gui_id, **kwargs)
        self._configs: dict[str, messages.BeamlineStateConfig] = {}
        self._order: list[str] = []
        self._states: dict[str, tuple[str, str]] = {}
        self._subscribed: set[str] = set()
        self._expanded: set[str] = set()
        self._selected_statuses: set[str] | None = None
        self._selected_devices: set[str] | None = None
        self._filter_text = ""
        self._show_hidden = False
        self._scan_interlock = self.client.builtin_actors.scan_interlock
        self._interlock_enabled = False
        self._interlock_states: dict[str, list[str]] = {}
        self._preferred_statuses: dict[str, list[str]] = {}
        self._enabled_config = None

        self._init_view()

        self.bec_dispatcher.connect_slot(
            self.update_available_states, MessageEndpoints.available_beamline_states()
        )
        self.bec_dispatcher.connect_slot(
            self._refresh_scan_interlock,
            MessageEndpoints.builtin_actor_update_notif("ScanInterlockActor"),
        )
        self.scan_interlock_enabled_changed.connect(self._on_interlock_enabled_changed)
        self._enabled_config = getattr(self._scan_interlock, "_enabled", None)
        if self._enabled_config is not None and hasattr(self._enabled_config, "subscribe"):
            self._enabled_config.subscribe(self._on_interlock_enabled_stream)
        self._refresh_scan_interlock()
        self.refresh_states()
        self._refresh()

    # ---- renderer hooks ------------------------------------------------------------------

    def _init_view(self) -> None:
        """Build the renderer."""

    def _sync_view(self) -> None:
        """Redraw the renderer from :meth:`view_state`."""

    def _refresh(self) -> None:
        self._sync_view()

    # ---- original public API -------------------------------------------------------------

    @SafeSlot()
    def clear_filters(self) -> None:
        """Remove every status, device and text filter."""
        self._selected_statuses = None
        self._selected_devices = None
        self._filter_text = ""
        self._show_hidden = False
        self._refresh()

    @SafeSlot()
    def collapse_all(self) -> None:
        """Collapse the details of all states."""
        self._expanded.clear()
        self._refresh()

    def state_summary(self) -> dict[str, dict[str, str]]:
        """
        Return all beamline states (including filtered ones) with their current status and label.

        Returns:
            dict: Mapping of state name to a dictionary with ``status`` and ``label`` keys.
        """
        return {
            name: {"status": self._status(name), "label": self._label(name)} for name in self._order
        }

    @SafeSlot()
    def refresh_states(self) -> None:
        """Fetch the latest cached available beamline states and update the list immediately."""
        msg = self.client.connector.get_last(
            MessageEndpoints.available_beamline_states(), key="data"
        )
        if msg is not None:
            self.update_available_states(msg.content, msg.metadata)

    @SafeSlot(dict, dict)
    def update_available_states(
        self, content: dict[str, Any], _metadata: dict[str, Any] | None = None
    ) -> None:
        """Update the displayed states from ``AvailableBeamlineStatesMessage`` content."""
        state_configs: list[messages.BeamlineStateConfig] = content.get("states", [])
        self._configs = {state.name: state for state in state_configs}
        self._order = [state.name for state in state_configs]
        names = set(self._order)
        for name in sorted(self._subscribed - names):
            self.bec_dispatcher.disconnect_slot(
                self.update_state, MessageEndpoints.beamline_state(name)
            )
            self._subscribed.discard(name)
            self._states.pop(name, None)
            self._expanded.discard(name)
        for name in self._order:
            if name in self._subscribed:
                continue
            self._subscribed.add(name)
            msg = self.client.connector.get_last(MessageEndpoints.beamline_state(name), key="data")
            if msg is not None:
                self._store_state(msg.content)
            self.bec_dispatcher.connect_slot(
                self.update_state, MessageEndpoints.beamline_state(name)
            )
        self._refresh()

    @SafeSlot(dict, dict)
    def update_state(
        self, content: dict[str, Any], _metadata: dict[str, Any] | None = None
    ) -> None:
        """Update one state from a ``BeamlineStateMessage`` content dictionary."""
        if self._store_state(content):
            self._refresh()

    @SafeSlot()
    def open_add_state_dialog(self) -> None:
        """Ask for a new state and add it, optionally to the scan interlock."""
        dialog = AddBeamlineStateDialog(self, client=self.client)
        config = None
        add_to_interlock = False
        statuses = list(DEFAULT_INTERLOCK_STATUSES)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                config = dialog.config_result
                add_to_interlock = dialog.add_to_interlock()
                statuses = dialog.interlock_statuses()
        finally:
            dialog.cleanup()
            dialog.deleteLater()
        if config is None:
            return
        try:
            self.client.beamline_states.add(config)
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.warning(self, "Cannot Add State", str(exc))
            return
        self._preferred_statuses[config.name] = statuses
        if add_to_interlock:
            self._call_interlock(self._scan_interlock.add_state_to_interlock, config.name, statuses)

    @SafeSlot()
    def open_status_filter_dialog(self) -> None:
        """Choose the shown statuses in a dialog (the chips do the same inline)."""
        dialog = StatusFilterDialog(self._selected_statuses, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._selected_statuses = dialog.selected_statuses()
        self._refresh()

    @SafeSlot()
    def open_device_filter_dialog(self) -> None:
        """Choose the shown devices in a dialog (the search field does the same inline)."""
        devices = sorted(
            {device for config in self._configs.values() if (device := state_device(config))}
        )
        dialog = DeviceFilterDialog(devices, self._selected_devices, self._filter_text, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._selected_devices = dialog.selected_devices()
        self._filter_text = dialog.filter_text()
        self._refresh()

    # ---- UX actions ----------------------------------------------------------------------

    def toggle_status_filter(self, status: str) -> None:
        """Show only states of the clicked status; click more chips to add statuses.

        Clicking the last selected chip again shows all statuses.
        """
        selected = set(self._selected_statuses or ())
        if status in selected:
            selected.discard(status)
        else:
            selected.add(status)
        self._selected_statuses = selected or None
        self._refresh()

    def set_filter_text(self, text: str) -> None:
        """Filter by state name or device; commas separate alternatives."""
        if text == self._filter_text:
            return
        self._filter_text = text
        self._refresh()

    def set_expanded(self, name: str, expanded: bool) -> None:
        """Expand or collapse the details of one state."""
        if expanded:
            self._expanded.add(name)
        else:
            self._expanded.discard(name)
        self._refresh()

    def toggle_expanded(self, name: str) -> None:
        """Toggle the details of one state."""
        self.set_expanded(name, name not in self._expanded)

    def set_show_hidden(self, show: bool) -> None:
        """Show or hide the states removed by the filters."""
        self._show_hidden = bool(show)
        self._refresh()

    def set_interlock_enabled(self, enabled: bool) -> None:
        """Arm or disarm the scan interlock."""
        enabled = bool(enabled)
        if enabled == self._interlock_enabled:
            return
        try:
            self._scan_interlock.enabled = enabled
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.warning(self, "Cannot Toggle Scan Interlock", str(exc))
            self._refresh_scan_interlock()
            return
        self._interlock_enabled = enabled
        self._refresh()

    def toggle_interlock_for(self, name: str) -> None:
        """Add a state to the scan interlock or remove it."""
        if name in self._interlock_states:
            self._call_interlock(self._scan_interlock.remove_state_from_interlock, name)
        else:
            self._call_interlock(
                self._scan_interlock.add_state_to_interlock, name, self._accepted_statuses(name)
            )

    def set_trip_on_warning(self, name: str, trip: bool) -> None:
        """Whether a WARNING status of the state trips the scan interlock."""
        statuses = ["valid"] if trip else list(DEFAULT_INTERLOCK_STATUSES)
        if statuses == self._accepted_statuses(name):
            return
        self._preferred_statuses[name] = statuses
        if name in self._interlock_states:
            self._call_interlock(self._scan_interlock.add_state_to_interlock, name, statuses)
        else:
            self._refresh()

    def edit_state(self, name: str) -> None:
        """Edit the parameters of a state in a form dialog."""
        config = self._configs.get(name)
        if config is None:
            return
        try:
            dialog = EditBeamlineStateDialog(config, self, client=self.client)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot Edit State", str(exc))
            return
        new_config = None
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_config = dialog.config_result
        finally:
            dialog.cleanup()
            dialog.deleteLater()
        if new_config is not None:
            self.update_state_parameters(name, new_config)

    def update_state_parameters(self, name: str, config: bl_states.BeamlineStateConfig) -> bool:
        """Send new parameters of a state to BEC.

        Returns:
            bool: Whether BEC accepted the update.
        """
        state_client = getattr(self.client.beamline_states, name, None)
        if state_client is None:
            QMessageBox.warning(
                self, "Cannot Update State", f"Beamline state '{name}' is not available."
            )
            return False
        try:
            state_client.update_parameters(**config.model_dump(exclude={"name"}))
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.warning(self, "Cannot Update State", str(exc))
            return False
        return True

    def remove_state(self, name: str) -> None:
        """Delete a state after confirmation."""
        reply = QMessageBox.question(
            self,
            "Remove Beamline State",
            f"Remove beamline state '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.client.beamline_states.delete(name)
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.warning(self, "Cannot Remove State", str(exc))

    # ---- scan interlock ------------------------------------------------------------------

    @SafeSlot(dict, dict)
    def _refresh_scan_interlock(
        self, _content: dict[str, Any] | None = None, _metadata: dict[str, Any] | None = None
    ) -> None:
        """Re-read the scan-interlock state from BEC."""
        try:
            self._interlock_enabled = bool(self._scan_interlock.enabled)
            self._interlock_states = {
                name: list(statuses)
                for name, statuses in dict(self._scan_interlock.states_watched).items()
            }
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.warning(self, "Scan Interlock Unavailable", str(exc))
            return
        self._refresh()

    def _on_interlock_enabled_stream(self, enabled: bool) -> None:
        """Connector-thread callback; hands the value to the Qt thread through a signal."""
        self.scan_interlock_enabled_changed.emit(bool(enabled))

    @SafeSlot(bool)
    def _on_interlock_enabled_changed(self, enabled: bool) -> None:
        self._interlock_enabled = bool(enabled)
        self._refresh()

    def _call_interlock(self, method, *args) -> None:
        try:
            method(*args)
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.warning(self, "Cannot Update Scan Interlock", str(exc))
            return
        self._refresh_scan_interlock()

    def _accepted_statuses(self, name: str) -> list[str]:
        if name in self._interlock_states:
            return list(self._interlock_states[name])
        return list(self._preferred_statuses.get(name, DEFAULT_INTERLOCK_STATUSES))

    def _is_tripped(self, name: str) -> bool:
        accepted = self._interlock_states.get(name)
        if not accepted or not self._interlock_enabled:
            return False
        return self._status(name) not in accepted

    # ---- state bookkeeping ---------------------------------------------------------------

    def _store_state(self, content: dict[str, Any]) -> bool:
        name = content.get("name")
        if not name or name not in self._configs:
            return False
        status = str(content.get("status", "unknown")).lower()
        if status not in BEAMLINE_STATE_STATUS_LABELS:
            status = "unknown"
        label = str(content.get("label", "No state information available."))
        if self._states.get(name) == (status, label):
            return False
        self._states[name] = (status, label)
        return True

    def _status(self, name: str) -> str:
        return self._states.get(name, ("unknown", ""))[0]

    def _label(self, name: str) -> str:
        return self._states.get(name, ("unknown", "No state information available."))[1]

    def _matches_filters(self, name: str) -> bool:
        if (
            self._selected_statuses is not None
            and self._status(name) not in self._selected_statuses
        ):
            return False
        device = state_device(self._configs.get(name))
        if self._selected_devices is not None and device not in self._selected_devices:
            return False
        tokens = [token.strip().casefold() for token in self._filter_text.split(",")]
        tokens = [token for token in tokens if token]
        if tokens:
            haystack = f"{name} {device or ''}".casefold()
            if not any(token in haystack for token in tokens):
                return False
        return True

    def _filters_active(self) -> bool:
        return (
            self._selected_statuses is not None
            or self._selected_devices is not None
            or bool(self._filter_text.strip())
        )

    # ---- view state ----------------------------------------------------------------------

    def _row(self, name: str) -> dict:
        config = self._configs[name]
        status = self._status(name)
        watched = name in self._interlock_states
        accepted = self._accepted_statuses(name)
        params = [
            {"key": key, "value": format_parameter(value)}
            for key, value in config.parameters.items()
        ]
        return {
            "kind": "state",
            "key": f"state:{name}",
            "name": name,
            "label": self._label(name),
            "status": status,
            "statusText": BEAMLINE_STATE_STATUS_LABELS[status].capitalize(),
            "tone": STATUS_TONES[status],
            "icon": STATUS_ICONS[status],
            "device": state_device(config) or "",
            "stateType": config.state_type,
            "params": params,
            "watched": watched,
            "tripped": self._is_tripped(name),
            "armed": watched and self._interlock_enabled,
            "acceptedText": " or ".join(s.upper() for s in accepted),
            "tripOnWarning": "warning" not in accepted,
            "expanded": name in self._expanded,
            "title": "",
            "count": 0,
        }

    def view_state(self) -> dict:
        """Display-ready state shared by both renderers."""
        rank = {status: index for index, status in enumerate(STATUS_ORDER)}
        ordered = sorted(self._order, key=lambda name: rank[self._status(name)])
        visible, hidden = [], []
        for name in ordered:
            # States watched by the scan interlock are never filtered away.
            if name in self._interlock_states or self._matches_filters(name):
                visible.append(name)
            else:
                hidden.append(name)
        shown = set(visible) | (set(hidden) if self._show_hidden else set())

        rows: list[dict] = []
        sections = (
            ("interlock", "Scan interlock", [n for n in ordered if n in self._interlock_states]),
            (
                "others",
                "Not in scan interlock",
                [n for n in ordered if n not in self._interlock_states],
            ),
        )
        # Like the original manager, headers only appear once some state is in the interlock.
        with_headers = any(name in shown for name in sections[0][2])
        for key, title, names in sections:
            names = [name for name in names if name in shown]
            if not names:
                continue
            if not with_headers:
                rows.extend(self._row(name) for name in names)
                continue
            rows.append(
                {
                    "kind": "header",
                    "key": f"header:{key}",
                    "name": key,
                    "title": title,
                    "count": len(names),
                    "armed": key == "interlock" and self._interlock_enabled,
                    "expanded": False,
                    "params": [],
                }
            )
            rows.extend(self._row(name) for name in names)

        counts = {status: 0 for status in STATUS_ORDER}
        for name in self._order:
            counts[self._status(name)] += 1
        chips = [
            {
                "status": status,
                "text": f"{counts[status]} {STATUS_WORDS[status]}",
                "tone": STATUS_TONES[status],
                "active": self._selected_statuses is not None and status in self._selected_statuses,
            }
            for status in STATUS_ORDER
            if counts[status] or (self._selected_statuses and status in self._selected_statuses)
        ]
        tripped = [name for name in ordered if self._is_tripped(name)]
        if tripped:
            banner = (
                "Scans are blocked: "
                + ", ".join(tripped)
                + (" is" if len(tripped) == 1 else " are")
                + " outside the accepted status."
            )
        else:
            banner = ""
        if self._interlock_enabled:
            interlock_text = "Armed" if not tripped else "Tripped"
        else:
            interlock_text = "Off"
        hidden_count = len(hidden)
        noun = "state" if hidden_count == 1 else "states"
        return {
            "empty": not self._order,
            "rows": rows,
            "chips": chips,
            "total": len(self._order),
            "filterText": self._filter_text,
            "filtersActive": self._filters_active(),
            "noMatches": bool(self._order) and not shown,
            "hiddenCount": hidden_count,
            "hiddenText": (f"{hidden_count} {noun} hidden by filters" if hidden_count else ""),
            "showHidden": self._show_hidden,
            "interlockEnabled": self._interlock_enabled,
            "interlockText": interlock_text,
            "interlockTone": (
                ("danger" if tripped else "success") if self._interlock_enabled else "muted"
            ),
            "interlockCount": len(self._interlock_states),
            "banner": banner,
        }

    # ---- teardown ------------------------------------------------------------------------

    def cleanup(self) -> None:
        if self._enabled_config is not None:
            self._enabled_config.unsubscribe(self._on_interlock_enabled_stream)
            self._enabled_config = None
        self.bec_dispatcher.disconnect_slot(
            self.update_available_states, MessageEndpoints.available_beamline_states()
        )
        self.bec_dispatcher.disconnect_slot(
            self._refresh_scan_interlock,
            MessageEndpoints.builtin_actor_update_notif("ScanInterlockActor"),
        )
        for name in sorted(self._subscribed):
            self.bec_dispatcher.disconnect_slot(
                self.update_state, MessageEndpoints.beamline_state(name)
            )
        self._subscribed.clear()
        super().cleanup()


BeamlineStatesPortBase.PORTED_FROM = BeamlineStatesPortBase
