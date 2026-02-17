"""Admin View panel for setting up account and messaging services in BEC."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import DeploymentInfoMessage, ExperimentInfoMessage
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.services.bec_atlas_admin_view.bec_atlas_http_service import (
    BECAtlasHTTPService,
    HTTPResponse,
)
from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.experiment_mat_card import (
    ExperimentMatCard,
)
from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.experiment_selection import (
    ExperimentSelection,
)

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.messages import ExperimentInfoMessage

logger = bec_logger.logger


class OverviewWidget(QWidget):
    """Overview Widget for the BEC Atlas Admin view"""

    login_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        layout = QHBoxLayout(self)
        self.setAutoFillBackground(True)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        self._experiment_info: ExperimentInfoMessage | None = None
        self._mat_card = ExperimentMatCard(
            parent=self,
            show_activate_button=True,
            button_text="Change Experiment",
            title="Current Experiment",
        )
        layout.addWidget(self._mat_card)
        self._mat_card.experiment_selected.connect(self._on_experiment_selected)

    def _on_experiment_selected(self, experiment_info: dict) -> None:
        """We reuse the experiment_selected signal from the mat card to trigger the login and experiment change process."""
        self.login_requested.emit()

    @SafeSlot(dict)
    def set_experiment_info(self, experiment_info: dict) -> None:
        self._experiment_info = ExperimentInfoMessage.model_validate(experiment_info)
        self._mat_card.set_experiment_info(self._experiment_info)


class BECAtlasAdminView(BECWidget, QWidget):

    authenticated = Signal(bool)
    account_changed = Signal(str)
    messaging_service_activated = Signal(str)

    def __init__(
        self, parent=None, atlas_url: str = "https://bec-atlas-dev.psi.ch/api/v1", client=None
    ):
        super().__init__(parent=parent, client=client)

        # State variables
        self._current_deployment_info: DeploymentInfoMessage | None = None
        self._current_deployment_info = None
        self._current_session_info = None
        self._current_experiment_info = None
        self._authenticated = False

        # Root layout
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # Toolbar for navigation between different views in the admin panel
        self.toolbar = ModularToolBar(self)
        self.init_toolbar()
        self.root_layout.insertWidget(0, self.toolbar)
        self.toolbar.show_bundles(["view", "auth"])

        # Stacked layout to switch between overview, experiment selection and messaging services
        # It is added below the toolbar
        self.stacked_layout = QStackedLayout()
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_layout.setSpacing(0)
        self.stacked_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        self.root_layout.addLayout(self.stacked_layout)

        # Overview widget
        self.overview_widget = OverviewWidget(parent=self)
        self.stacked_layout.addWidget(self.overview_widget)
        self.overview_widget.login_requested.connect(self.login)

        # Experiment Selection widget
        self.experiment_selection = ExperimentSelection(parent=self)
        self.stacked_layout.addWidget(self.experiment_selection)
        self.experiment_selection.experiment_selected.connect(self._on_experiment_selected)

        # BEC Atlas HTTP Service
        self.atlas_http_service = BECAtlasHTTPService(
            parent=self, base_url=atlas_url, headers={"accept": "application/json"}
        )

        # Connect signals
        self.atlas_http_service.http_response_received.connect(self._on_http_response_received)
        self.atlas_http_service.authenticated.connect(self._on_authenticated)

        self.bec_dispatcher.connect_slot(
            slot=self._update_deployment_info,
            topics=MessageEndpoints.deployment_info(),
            from_start=True,
        )

    @SafeSlot(dict)
    def _on_experiment_selected(self, experiment_info: dict) -> None:
        """Handle the experiment selected signal from the experiment selection widget"""
        experiment_info = ExperimentInfoMessage.model_validate(experiment_info)
        experiment_id = experiment_info.pgroup
        deployment_id = self._current_deployment_info.deployment_id
        self.set_experiment(experiment_id=experiment_id, deployment_id=deployment_id)

    @SafeSlot(dict, dict)
    def _update_deployment_info(self, msg: dict, metadata: dict) -> None:
        """Fetch current deployment info from the server."""
        deployment = DeploymentInfoMessage.model_validate(msg)
        self._current_deployment_info = deployment
        self._current_session_info = deployment.active_session
        if self._current_session_info is not None:
            self._current_experiment_info = self._current_session_info.experiment

        self.overview_widget.set_experiment_info(
            self._current_experiment_info.model_dump() if self._current_experiment_info else {}
        )

    def init_toolbar(self):
        """Initialize the toolbar for the admin view. This allows to switch between different views in the admin panel."""
        # Overview
        overview = MaterialIconAction(
            icon_name="home",
            tooltip="Show Overview Panel",
            label_text="Overview",
            text_position="under",
            parent=self,
            filled=True,
        )
        overview.action.triggered.connect(self._on_overview_selected)
        self.toolbar.components.add_safe("overview", overview)

        # Experiment Selection
        experiment_selection = MaterialIconAction(
            icon_name="experiment",
            tooltip="Show Experiment Selection Panel",
            label_text="Experiment Selection",
            text_position="under",
            parent=self,
            filled=True,
        )
        experiment_selection.action.triggered.connect(self._on_experiment_selection_selected)
        experiment_selection.action.setEnabled(False)  # Initially disabled until authenticated
        self.toolbar.components.add_safe("experiment_selection", experiment_selection)

        # Messaging Services
        messaging_services = MaterialIconAction(
            icon_name="chat",
            tooltip="Show Messaging Services Panel",
            label_text="Messaging Services",
            text_position="under",
            parent=self,
            filled=True,
        )
        messaging_services.action.triggered.connect(self._on_messaging_services_selected)
        messaging_services.action.setEnabled(False)  # Initially disabled until authenticated
        self.toolbar.components.add_safe("messaging_services", messaging_services)

        # Login
        login_action = MaterialIconAction(
            icon_name="login",
            tooltip="Login",
            label_text="Login",
            text_position="under",
            parent=self,
            filled=True,
        )
        login_action.action.triggered.connect(self.login)
        self.toolbar.components.add_safe("login", login_action)

        # Logout
        logout_action = MaterialIconAction(
            icon_name="logout",
            tooltip="Logout",
            label_text="Logout",
            text_position="under",
            parent=self,
            filled=True,
        )
        logout_action.action.triggered.connect(self.logout)
        logout_action.action.setEnabled(False)  # Initially disabled until authenticated
        self.toolbar.components.add_safe("logout", logout_action)

        # Add view_bundle to toolbar
        view_bundle = ToolbarBundle("view", self.toolbar.components)
        view_bundle.add_action("overview")
        view_bundle.add_action("experiment_selection")
        view_bundle.add_action("messaging_services")
        self.toolbar.add_bundle(view_bundle)

        # Add auth_bundle to toolbar
        auth_bundle = ToolbarBundle("auth", self.toolbar.components)
        auth_bundle.add_action("login")
        auth_bundle.add_action("logout")
        self.toolbar.add_bundle(auth_bundle)

    def _on_overview_selected(self):
        """Show the overview panel."""
        self.overview_widget.setVisible(True)
        self.experiment_selection.setVisible(False)
        self.stacked_layout.setCurrentWidget(self.overview_widget)

    def _on_experiment_selection_selected(self):
        """Show the experiment selection panel."""
        if not self._authenticated:
            logger.warning("Attempted to access experiment selection without authentication.")
            return
        self.overview_widget.setVisible(False)
        self.experiment_selection.setVisible(True)
        self.stacked_layout.setCurrentWidget(self.experiment_selection)

    def _on_messaging_services_selected(self):
        """Show the messaging services panel."""
        logger.info("Messaging services panel is not implemented yet.")
        # TODO
        return
        # if not self._authenticated:
        #     logger.warning("Attempted to access messaging services without authentication.")
        #     return
        # self.overview_widget.setVisible(False)
        # self.experiment_selection.setVisible(False)

    def _fetch_available_experiments(self):
        """Fetch the list of available experiments for the authenticated user."""
        # What if this is None, should this be an optional user input in the UI?
        if self._current_experiment_info is None:
            logger.error(
                "No current experiment info available, cannot fetch available experiments."
            )
            return
        current_realm_id = self._current_experiment_info.realm_id
        if current_realm_id is None:
            logger.error(
                "Current experiment does not have a realm_id, cannot fetch available experiments."
            )
            return
        self.atlas_http_service.get_experiments_for_realm(current_realm_id)

    def _on_http_response_received(self, response: dict) -> None:
        """Handle the HTTP response received from the BEC Atlas API."""
        response = HTTPResponse(**response)
        logger.info(f"HTTP Response received: {response.request_url} with status {response.status}")
        if "realms/experiments" in response.request_url and response.status == 200:
            experiments = response.data if isinstance(response.data, list) else []
            self.experiment_selection.set_experiment_infos(experiments)
            self._on_experiment_selection_selected()  # Switch to experiment selection once experiments are loaded

    def _on_authenticated(self, authenticated: bool) -> None:
        """Handle authentication state change."""
        self._authenticated = authenticated
        self.authenticated.emit(authenticated)
        if authenticated:
            self.toolbar.components.get_action("experiment_selection").action.setEnabled(True)
            self.toolbar.components.get_action("messaging_services").action.setEnabled(True)
            self.toolbar.components.get_action("login").action.setEnabled(False)
            self.toolbar.components.get_action("logout").action.setEnabled(True)
            self._fetch_available_experiments()  # Fetch experiments upon successful authentication
        else:
            self.toolbar.components.get_action("experiment_selection").action.setEnabled(False)
            self.toolbar.components.get_action("messaging_services").action.setEnabled(False)
            self.toolbar.components.get_action("login").action.setEnabled(True)
            self.toolbar.components.get_action("logout").action.setEnabled(False)
            # Delete data in experiment selection widget upon logout
            self.experiment_selection.set_experiment_infos([])
            self._on_overview_selected()  # Switch back to overview on logout

    @SafeSlot(dict)
    def set_experiment(self, experiment_id: str, deployment_id: str) -> None:
        """Set the experiment information for the current experiment."""
        self.atlas_http_service.set_experiment(experiment_id, deployment_id)

    def check_health(self) -> None:
        """Check the health of the BEC Atlas API."""
        self.atlas_http_service.check_health()

    def login(self) -> None:
        """Login to the BEC Atlas API."""
        self.atlas_http_service.login()

    def logout(self) -> None:
        """Logout from the BEC Atlas API."""
        self.atlas_http_service.logout()

    def cleanup(self):
        self.atlas_http_service.cleanup()
        return super().cleanup()


if __name__ == "__main__":
    import sys

    from bec_qthemes import apply_theme
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)

    apply_theme("light")
    window = BECAtlasAdminView()

    exp_info_dict = {
        "_id": "p22622",
        "owner_groups": ["admin"],
        "access_groups": ["unx-sls_xda_bs", "p22622"],
        "realm_id": "TestBeamline",
        "proposal": "12345967",
        "title": "Test Experiment for Mat Card Widget",
        "firstname": "John",
        "lastname": "Doe",
        "email": "john.doe@psi.ch",
        "account": "doe_j",
        "pi_firstname": "Jane",
        "pi_lastname": "Smith",
        "pi_email": "jane.smith@psi.ch",
        "pi_account": "smith_j",
        "eaccount": "e22622",
        "pgroup": "p22622",
        "abstract": "This is a test abstract for the experiment mat card widget. It should be long enough to test text wrapping and display in the card. The abstract provides a brief overview of the experiment, its goals, and its significance. This text is meant to simulate a real abstract that might be associated with an experiment in the BEC Atlas system. The card should be able to handle abstracts of varying lengths without any issues, ensuring that the user can read the full abstract even if it is quite long.",
        "schedule": [{"start": "01/01/2025 08:00:00", "end": "03/01/2025 18:00:00"}],
        "proposal_submitted": "15/12/2024",
        "proposal_expire": "31/12/2025",
        "proposal_status": "Scheduled",
        "delta_last_schedule": 30,
        "mainproposal": "",
    }
    from bec_lib.messages import ExperimentInfoMessage

    proposal_info = ExperimentInfoMessage(**exp_info_dict)
    window.set_experiment_info(proposal_info)
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())
