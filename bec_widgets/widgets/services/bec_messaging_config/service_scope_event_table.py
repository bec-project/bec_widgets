"""Module for the service scope event subscription table widget."""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


class ServiceScopeEventTableWidget(QWidget):
    """Widget that manages per-scope event subscriptions for messaging services."""

    EVENT_NAMES = ("new_scan", "scan_finished", "alarm")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services: list[dict] = []
        self._subscriptions: dict[str, dict[str, bool]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._table = QTableWidget(len(self.EVENT_NAMES), 0, self)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table.setVerticalHeaderLabels(list(self.EVENT_NAMES))
        self._table.horizontalHeader().setStretchLastSection(True)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        root.addWidget(self._table, 1)

    def set_services(self, services: list[dict]) -> None:
        """Update the table rows to match the current services.

        Args:
            services (list[dict]): Service dictionaries collected from the service configuration panels.
        """
        self._services = [dict(service) for service in services]
        known_ids = {str(service.get("id", "")) for service in self._services if service.get("id")}
        self._subscriptions = {
            service_id: subscriptions
            for service_id, subscriptions in self._subscriptions.items()
            if service_id in known_ids
        }

        self._table.clearContents()
        self._table.setRowCount(len(self.EVENT_NAMES))
        self._table.setColumnCount(len(self._services))
        self._table.setHorizontalHeaderLabels(
            [self._format_service_label(service) for service in self._services]
        )

        for column, service in enumerate(self._services):
            service_id = str(service.get("id", ""))

            event_states = self._subscriptions.setdefault(
                service_id, {event_name: False for event_name in self.EVENT_NAMES}
            )
            for row, event_name in enumerate(self.EVENT_NAMES):
                self._table.setCellWidget(
                    row,
                    column,
                    self._make_checkbox_cell(
                        service_id, event_name, event_states.get(event_name, False)
                    ),
                )

    def get_data(self) -> list[dict]:
        """Return the event subscriptions for the current services."""
        results: list[dict] = []
        for service in self._services:
            service_id = str(service.get("id", ""))
            results.append(
                {
                    "id": service_id,
                    "source": service.get("source"),
                    "service_type": service.get("service_type"),
                    "scope": service.get("scope"),
                    "events": dict(
                        self._subscriptions.get(
                            service_id, {event_name: False for event_name in self.EVENT_NAMES}
                        )
                    ),
                }
            )
        return results

    def _format_service_label(self, service: dict) -> str:
        service_name = str(service.get("service_type", ""))
        scope_name = str(service.get("scope", ""))
        source_name = str(service.get("source", ""))
        return f"{service_name}\n{scope_name}\n({source_name})"

    def _make_checkbox_cell(self, service_id: str, event_name: str, checked: bool) -> QWidget:
        checkbox = QCheckBox()
        checkbox.setChecked(checked)
        checkbox.toggled.connect(
            lambda state, current_service_id=service_id, current_event_name=event_name: self._set_event_state(
                current_service_id, current_event_name, state
            )
        )

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(checkbox)
        return container

    def _set_event_state(self, service_id: str, event_name: str, checked: bool) -> None:
        self._subscriptions.setdefault(service_id, {})[event_name] = checked
