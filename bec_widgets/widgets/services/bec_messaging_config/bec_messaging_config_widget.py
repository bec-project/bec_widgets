"""Module for the BEC messaging configuration widget."""

from __future__ import annotations

import json

from qtpy.QtCore import Qt, QTimer, Signal  # type: ignore[attr-defined]
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.services.bec_messaging_config.service_cards import (
    CardType,
    ScopeListWidget,
    card_from_service,
    make_card,
)
from bec_widgets.widgets.services.bec_messaging_config.service_scope_event_table import (
    ServiceScopeEventTableWidget,
)


class ServiceConfigPanel(QWidget):
    """Panel that manages global and local service scopes for one service type.

    Args:
        card_type (CardType): The service type used when adding new scope cards.
        parent (QWidget | None): The parent widget.
    """

    config_changed = Signal()

    def __init__(self, card_type: CardType, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._card_type: CardType = card_type

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── Local settings box ────────────────────────────────────────────
        self._local_box = QGroupBox("Current Experiment")
        self._local_list = ScopeListWidget()
        self._local_list.cards_changed.connect(self.config_changed)
        self._local_add_btn = QPushButton("+ Add")
        self._local_add_btn.setFixedWidth(120)
        self._local_add_btn.clicked.connect(
            lambda: self._local_list.add_card(make_card(self._card_type))
        )
        local_layout = QVBoxLayout(self._local_box)
        local_layout.setContentsMargins(16, 16, 16, 16)
        local_layout.setSpacing(12)
        local_layout.addWidget(self._local_add_btn, 0, Qt.AlignmentFlag.AlignRight)
        local_layout.addWidget(self._local_list, 1)
        splitter.addWidget(self._local_box)

        # ── Global settings box ───────────────────────────────────────────
        self._global_box = QGroupBox("All Experiments")
        self._global_list = ScopeListWidget()
        self._global_list.cards_changed.connect(self.config_changed)
        self._global_add_btn = QPushButton("+ Add")
        self._global_add_btn.setFixedWidth(120)
        self._global_add_btn.clicked.connect(
            lambda: self._global_list.add_card(make_card(self._card_type))
        )
        global_layout = QVBoxLayout(self._global_box)
        global_layout.setContentsMargins(16, 16, 16, 16)
        global_layout.setSpacing(12)
        global_layout.addWidget(self._global_add_btn, 0, Qt.AlignmentFlag.AlignRight)
        global_layout.addWidget(self._global_list, 1)
        splitter.addWidget(self._global_box)

        splitter.setSizes([300, 300])
        root.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    def load_services(self, deployment_services: list, session_services: list) -> None:
        """Populate both lists with services matching the panel service type."""
        self._clear_list(self._global_list)
        self._clear_list(self._local_list)
        for info in deployment_services:
            if getattr(info, "service_type", None) == self._card_type:
                self._global_list.add_card(card_from_service(info))
        for info in session_services:
            if getattr(info, "service_type", None) == self._card_type:
                self._local_list.add_card(card_from_service(info))

    @staticmethod
    def _clear_list(list_widget: ScopeListWidget) -> None:
        """Remove all cards from *list_widget*."""
        list_widget.clear_cards()

    # ------------------------------------------------------------------
    def get_data(self) -> dict:
        """Collect all card data from both the deployment and session lists."""
        return {
            "deployment": self._collect(self._global_list),
            "session": self._collect(self._local_list),
        }

    @staticmethod
    def _collect(list_widget: ScopeListWidget) -> list[dict]:
        return [card.get_data() for card in list_widget.cards()]


class BECMessagingConfigWidget(QWidget):
    """Widget to configure SciLog, Signal, and MS Teams messaging services."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BEC Messaging Configuration")
        self.setMinimumSize(540, 500)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Tab widget ────────────────────────────────────────────────────
        self._tabs = QTabWidget()

        self._scilog_panel = ServiceConfigPanel("scilog")
        self._signal_panel = ServiceConfigPanel("signal")
        self._teams_panel = ServiceConfigPanel("teams")

        for panel in (self._scilog_panel, self._signal_panel, self._teams_panel):
            panel.config_changed.connect(self._refresh_scope_event_table)

        self._tabs.addTab(self._scilog_panel, "SciLog")
        self._tabs.addTab(self._signal_panel, "Signal")
        self._tabs.addTab(self._teams_panel, "MS Teams")

        content_splitter.addWidget(self._tabs)

        self._scope_event_table = ServiceScopeEventTableWidget(self)
        content_splitter.addWidget(self._scope_event_table)
        content_splitter.setStretchFactor(0, 3)
        content_splitter.setStretchFactor(1, 2)

        root.addWidget(content_splitter, 1)

        # ── Bottom action bar ─────────────────────────────────────────────
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self._status_label = QLabel("")
        self._status_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bottom_row.addWidget(self._status_label, 1)

        save_btn = QPushButton("Save && Apply")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._mock_save_to_atlas_api)
        bottom_row.addWidget(save_btn)

        root.addLayout(bottom_row)

    # ------------------------------------------------------------------
    # Initialisation from backend message
    # ------------------------------------------------------------------

    def populate_from_deployment(self, msg: DeploymentInfoMessage) -> None:
        """Populate all panels from a deployment info message.

        Args:
            msg (DeploymentInfoMessage): Deployment information containing deployment and session services.
        """
        deployment_services = list(msg.messaging_services)
        session_services = (
            list(msg.active_session.messaging_services) if msg.active_session is not None else []
        )
        self._scilog_panel.load_services(deployment_services, session_services)
        self._signal_panel.load_services(deployment_services, session_services)
        self._teams_panel.load_services(deployment_services, session_services)
        self._refresh_scope_event_table()

    # ------------------------------------------------------------------
    # Dummy REST methods (replace with real requests calls later)
    # ------------------------------------------------------------------

    def _build_payload(self) -> dict:
        """Collect the current UI state as a serializable dictionary."""
        return {
            "scilog": self._scilog_panel.get_data(),
            "signal": self._signal_panel.get_data(),
            "teams": self._teams_panel.get_data(),
            "event_subscriptions": self._scope_event_table.get_data(),
        }

    def _refresh_scope_event_table(self) -> None:
        """Refresh the event subscription table from the current service cards."""
        self._scope_event_table.set_services(self._collect_services_for_event_table())

    def _collect_services_for_event_table(self) -> list[dict]:
        """Collect all configured services for the event subscription table."""
        service_rows: list[dict] = []
        for panel in (self._scilog_panel, self._signal_panel, self._teams_panel):
            panel_data = panel.get_data()
            for source_name in ("deployment", "session"):
                for service in panel_data[source_name]:
                    service_rows.append({**service, "source": source_name})
        return service_rows

    def _mock_save_to_atlas_api(self) -> None:
        """Simulate saving the current configuration to Atlas."""
        payload = self._build_payload()
        print("─" * 60)
        print("[BECMessagingConfigWidget] _mock_save_to_atlas_api payload:")
        print(json.dumps(payload, indent=2))
        print("─" * 60)
        self._set_status("✅ Saved!", timeout_ms=4000)

    # ------------------------------------------------------------------
    # Status bar helper
    # ------------------------------------------------------------------

    def _set_status(self, message: str, *, timeout_ms: int = 0) -> None:
        """Show a status message and optionally clear it after a timeout.

        Args:
            message (str): The message to display in the status label.
            timeout_ms (int): Time in milliseconds before clearing the message.
        """
        self._status_label.setText(message)
        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, lambda: self._status_label.setText(""))


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_lib.messages import (
        DeploymentInfoMessage,
        MessagingConfig,
        MessagingServiceScopeConfig,
        SciLogServiceInfo,
        SessionInfoMessage,
        SignalServiceInfo,
        TeamsServiceInfo,
    )
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    apply_theme("dark")

    # ── Build a realistic mock DeploymentInfoMessage ──────────────────
    mock_deployment = DeploymentInfoMessage(
        deployment_id="dep-0001",
        name="mockup-beamline",
        messaging_config=MessagingConfig(
            signal=MessagingServiceScopeConfig(enabled=True),
            teams=MessagingServiceScopeConfig(enabled=True),
            scilog=MessagingServiceScopeConfig(enabled=True),
        ),
        messaging_services=[
            SciLogServiceInfo(
                id="sl-global-1",
                scope="beamline",
                enabled=True,
                name="Beamline Log",
                logbook_id="lb-99001",
            ),
            TeamsServiceInfo(
                id="teams-global-1",
                scope="beamline",
                enabled=True,
                name="BEC Channel",
                workflow_webhook_url="https://outlook.office.com/webhook/…",
            ),
            SignalServiceInfo(
                id="signal-global-1",
                scope="beamline",
                enabled=False,
                name=None,
                group_id=None,
                group_link=None,
            ),
        ],
        active_session=SessionInfoMessage(
            name="session-2026-03-07",
            messaging_services=[
                SciLogServiceInfo(
                    id="sl-local-1",
                    scope="experiment",
                    enabled=True,
                    name="My Notebook",
                    logbook_id="lb-12345",
                ),
                SignalServiceInfo(
                    id="signal-local-1",
                    scope="experiment",
                    enabled=True,
                    name="Lab Signal Group",
                    group_id="grp-8a3f291c",
                    group_link="https://signal.group/#grp-8a3f291c",
                ),
            ],
        ),
    )

    widget = BECMessagingConfigWidget()
    widget.populate_from_deployment(mock_deployment)
    widget.show()
    sys.exit(app.exec())
