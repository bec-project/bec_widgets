"""Admin View panel for setting up account and messaging services in BEC."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import DeploymentInfoMessage, ExperimentInfoMessage
from qtpy.QtCore import QSize, Qt, QTimer, Signal
from qtpy.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_login import BECLogin
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import (
    MaterialIconAction,
    WidgetAction,
    create_action_with_text,
)
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.services.bec_atlas_admin_view.bec_atlas_http_service import (
    AtlasEndpoints,
    AuthenticatedUserInfo,
    BECAtlasHTTPService,
    HTTPResponse,
)
from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.experiment_mat_card import (
    ExperimentMatCard,
)
from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.experiment_selection import (
    ExperimentSelection,
)
from bec_widgets.widgets.services.bec_messaging_config.bec_messaging_config_widget import (
    BECMessagingConfigWidget,
)

if TYPE_CHECKING:  # pragma: no cover
    from qtpy.QtWidgets import QToolBar

logger = bec_logger.logger


class OverviewWidget(QGroupBox):
    """Overview Widget for the BEC Atlas Admin view"""

    login_requested = Signal(str, str)
    change_experiment_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setContentsMargins(12, 0, 12, 6)
        self._authenticated = False
        # Root layout
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # Stacked Layout to switch between login form and overview content
        self.stacked_layout = QStackedLayout()
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_layout.setSpacing(0)
        self.stacked_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        self.root_layout.addLayout(self.stacked_layout)

        self._init_login_view()
        self._init_experiment_overview()
        self.stacked_layout.setCurrentWidget(self._login_widget)
        self._experiment_overview_widget.setVisible(False)

    def set_experiment_info(self, experiment_info: ExperimentInfoMessage):
        """Set the experiment information for the overview widget."""
        self._experiment_overview_widget.set_experiment_info(experiment_info)

    @SafeSlot(bool)
    def set_authenticated(self, authenticated: bool):
        """Set the authentication state of the overview widget."""
        self._authenticated = authenticated
        if authenticated:
            self.stacked_layout.setCurrentWidget(self._experiment_overview_widget)
            self._experiment_overview_widget.setVisible(True)
        else:
            self.stacked_layout.setCurrentWidget(self._login_widget)
            self._experiment_overview_widget.setVisible(False)

    def _init_login_view(self):
        """Initialize the login view."""
        self._login_widget = QWidget()
        layout = QHBoxLayout(self._login_widget)
        self._login_widget.setAutoFillBackground(True)
        self._login_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.setSpacing(16)

        content = QFrame()
        content_layout = QVBoxLayout(content)
        content.setFrameShape(QFrame.Shape.StyledPanel)
        content.setFrameShadow(QFrame.Shadow.Raised)
        content.setStyleSheet(
            """
            QFrame
                {
                    border: 1px solid #cccccc;
                }
            QLabel
                {
                    border: none;
                }
            """
        )
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content.setFixedSize(400, 280)

        self._login = BECLogin(parent=self)
        self._login.credentials_entered.connect(self.login_requested.emit)
        content_layout.addWidget(self._login)
        layout.addWidget(content)
        self.stacked_layout.addWidget(self._login_widget)

    def _init_experiment_overview(self):
        """Initialize the experiment overview content."""
        self._experiment_overview_widget = ExperimentMatCard(
            show_activate_button=True,
            parent=self,
            title="Current Experiment",
            button_text="Change Experiment",
        )
        self._experiment_overview_widget.experiment_selected.connect(self._on_experiment_selected)
        layout = QVBoxLayout(self._experiment_overview_widget)
        self._experiment_overview_widget.setAutoFillBackground(True)
        self._experiment_overview_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stacked_layout.addWidget(self._experiment_overview_widget)

    @SafeSlot(dict)
    def _on_experiment_selected(self, _):
        """Handle the change experiment button click."""
        self.change_experiment_requested.emit()


class CustomLogoutAction(MaterialIconAction):
    """Custom logout action that can be enabled/disabled based on authentication state."""

    def __init__(self, parent=None):
        super().__init__(
            icon_name="logout",
            tooltip="Logout",
            label_text="Logout",
            text_position="under",
            parent=parent,
            filled=True,
        )
        self.action.setEnabled(False)  # Initially disabled until authenticated
        self._tick_timer = QTimer(parent)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)
        self._login_remaining_s = 0

    def add_to_toolbar(self, toolbar: QToolBar, target: QWidget):
        """
        Adds the action to the toolbar.

        Args:
            toolbar(QToolBar): The toolbar to add the action to.
            target(QWidget): The target widget for the action.
        """
        create_action_with_text(toolbar_action=self, toolbar=toolbar, min_size=QSize(70, 40))

    def set_authenticated(self, auth_info: AuthenticatedUserInfo | None):
        """Enable or disable the logout action based on authentication state."""
        if not auth_info:
            self._tick_timer.stop()
            self._login_remaining_s = 0
            self.action.setEnabled(False)
            self.update_label()  # Reset Label text
            return  # No need to set the timer if we're not authenticated
        self._login_remaining_s = max(0, int(auth_info.exp - time.time())) if auth_info else 0
        self.action.setEnabled(True)
        if self._login_remaining_s > 0:
            self._tick_timer.start()

    def _on_tick(self) -> None:
        """Handle the timer countdown tick to update the remaining logout time."""
        self._login_remaining_s -= 1
        if self._login_remaining_s <= 0:
            self.set_authenticated(None)  # This will disable the action and stop the timer
            return

        self.update_label()  # Optionally update the label to show remaining time

    def update_label(self):
        """Update the label text of the logout action."""
        if self._login_remaining_s > 0:
            label_text = f"{self.label_text}\n({self._login_remaining_s}s)"
        else:
            label_text = self.label_text
        self.action.setText(label_text)

    def cleanup(self):
        """Cleanup the timer when the action is destroyed."""
        if self._tick_timer.isActive():
            self._tick_timer.stop()


class AtlasConnectionInfo(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.setContentsMargins(6, 6, 6, 12)
        layout.setSpacing(8)
        self._bl_info_label = QLabel(self)
        self._atlas_url_label = QLabel(self)
        layout.addWidget(self._bl_info_label)
        layout.addWidget(self._atlas_url_label)
        self._atlas_url_text = ""

    def set_info(self, realm_id: str, bl_name: str, atlas_url: str):
        """Set the connection information for the BEC Atlas API."""
        bl_info = f"{realm_id} @ {bl_name}"
        self._bl_info_label.setText(bl_info)
        self._atlas_url_label.setText(atlas_url)
        self._atlas_url_text = atlas_url

    def set_logged_in(self, email: str):
        """Show login status in the atlas info widget."""
        self._atlas_url_label.setText(f"{self._atlas_url_text}  |  {email}")

    def clear_login(self):
        """Clear login status from the atlas info widget."""
        self._atlas_url_label.setText(self._atlas_url_text)


class BECAtlasAdminView(BECWidget, QWidget):

    RPC = False

    authenticated = Signal(bool)

    def __init__(
        self,
        parent=None,
        atlas_url: str = "https://bec-atlas-dev.psi.ch/api/v1",
        client=None,
        **kwargs,
    ):

        super().__init__(parent=parent, client=client, **kwargs)

        # State variables
        self._current_deployment_info: DeploymentInfoMessage | None = None
        self._current_deployment_info = None
        self._current_session_info = None
        self._current_experiment_info = None
        self._authenticated = False
        self._atlas_url = atlas_url

        # Root layout
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # Toolbar for navigation between different views in the admin panel
        self.toolbar = ModularToolBar(self)
        self.init_toolbar()
        self.root_layout.insertWidget(0, self.toolbar)
        self.toolbar.show_bundles(["view", "atlas_info", "auth"])

        # Stacked layout to switch between overview, experiment selection and messaging services
        # It is added below the toolbar
        self.stacked_layout = QStackedLayout()
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_layout.setSpacing(0)
        self.stacked_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        self.root_layout.addLayout(self.stacked_layout)

        # BEC Atlas HTTP Service
        self.atlas_http_service = BECAtlasHTTPService(
            parent=self, base_url=atlas_url, headers={"accept": "application/json"}
        )

        # Overview widget
        self.overview_widget = OverviewWidget(parent=self)
        self.stacked_layout.addWidget(self.overview_widget)

        # Experiment Selection widget
        self.experiment_selection = ExperimentSelection(parent=self)
        self.experiment_selection.setVisible(False)
        self.stacked_layout.addWidget(self.experiment_selection)

        # Messaging Services widget
        self.messaging_config_widget = BECMessagingConfigWidget(parent=self)
        self.messaging_config_widget.setVisible(False)
        self.stacked_layout.addWidget(self.messaging_config_widget)

        # Connect signals
        self.overview_widget.login_requested.connect(self._on_login_requested)
        self.overview_widget.change_experiment_requested.connect(
            self._on_experiment_selection_selected
        )
        self.authenticated.connect(self.overview_widget.set_authenticated)
        self.experiment_selection.experiment_selected.connect(self._on_experiment_selected)
        self.atlas_http_service.http_response.connect(self._on_http_response_received)
        self.atlas_http_service.authenticated.connect(self._on_authenticated)
        self._connect_dispatcher()

    def _connect_dispatcher(self):
        self.bec_dispatcher.connect_slot(
            slot=self._update_deployment_info,
            topics=MessageEndpoints.deployment_info(),
            from_start=True,
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

        # Atlas Info
        self._atlas_info_widget = AtlasConnectionInfo(parent=self)
        atlas_info = WidgetAction(widget=self._atlas_info_widget, parent=self)
        self.toolbar.components.add_safe("atlas_info", atlas_info)

        logout_action = CustomLogoutAction(parent=self)
        logout_action.action.triggered.connect(self.logout)
        logout_action.action.setEnabled(False)  # Initially disabled until authenticated
        self.toolbar.components.add_safe("logout", logout_action)

        # Add view_bundle to toolbar
        view_bundle = ToolbarBundle("view", self.toolbar.components)
        view_bundle.add_action("overview")
        view_bundle.add_action("experiment_selection")
        view_bundle.add_action("messaging_services")
        self.toolbar.add_bundle(view_bundle)

        # Add atlas_info to toolbar
        atlas_info_bundle = ToolbarBundle("atlas_info", self.toolbar.components)
        atlas_info_bundle.add_action("atlas_info")
        self.toolbar.add_bundle(atlas_info_bundle)

        # Add auth_bundle to toolbar
        auth_bundle = ToolbarBundle("auth", self.toolbar.components)
        auth_bundle.add_action("logout")
        self.toolbar.add_bundle(auth_bundle)

    ########################
    ## Toolbar icon slots
    ########################

    def _on_overview_selected(self):
        """Show the overview panel."""
        self.overview_widget.setVisible(True)
        self.experiment_selection.setVisible(False)
        self.messaging_config_widget.setVisible(False)
        self.stacked_layout.setCurrentWidget(self.overview_widget)

    def _on_experiment_selection_selected(self):
        """Show the experiment selection panel."""
        if not self._authenticated:
            logger.warning("Attempted to access experiment selection without authentication.")
            return
        self.overview_widget.setVisible(False)
        self.experiment_selection.setVisible(True)
        self.messaging_config_widget.setVisible(False)
        self.stacked_layout.setCurrentWidget(self.experiment_selection)

    def _on_messaging_services_selected(self):
        """Show the messaging services panel."""
        if not self._authenticated:
            logger.warning("Attempted to access messaging services without authentication.")
            return
        self.overview_widget.setVisible(False)
        self.experiment_selection.setVisible(False)
        self.messaging_config_widget.setVisible(True)
        if self._current_deployment_info is not None:
            self.messaging_config_widget.populate_from_deployment(self._current_deployment_info)
        self.stacked_layout.setCurrentWidget(self.messaging_config_widget)

    ########################
    ## Internal slots
    ########################

    @SafeSlot(dict)
    def _on_experiment_selected(self, experiment_info: dict) -> None:
        """Handle the experiment selected signal from the experiment selection widget"""
        experiment_info = ExperimentInfoMessage.model_validate(experiment_info)
        experiment_id = experiment_info.pgroup
        deployment_id = self._current_deployment_info.deployment_id
        self.set_experiment(experiment_id=experiment_id, deployment_id=deployment_id)

    @SafeSlot(str, str, popup_error=True)
    def _on_login_requested(self, username: str, password: str):
        """Handle login requested signal from the overview widget."""
        # Logout first to clear any existing session and cookies before attempting a new login
        if self._authenticated:
            logger.info("Existing session detected, logging out before attempting new login.")
            self.logout()
        # Now login with new credentials
        self.login(username, password)

    @SafeSlot(dict, dict)
    def _update_deployment_info(self, msg: dict, _: dict) -> None:
        """Fetch current deployment info from the server."""
        deployment = DeploymentInfoMessage.model_validate(msg)
        self._current_deployment_info = deployment
        self._current_session_info = deployment.active_session
        if self._current_session_info is not None:
            self._current_experiment_info = self._current_session_info.experiment
            self.overview_widget.set_experiment_info(self._current_experiment_info)

        self._atlas_info_widget.set_info(
            realm_id=self._current_experiment_info.realm_id or "",
            bl_name=self._current_deployment_info.name or "",
            atlas_url=self._atlas_url,
        )
        self.atlas_http_service._set_current_deployment_info(deployment)
        self.messaging_config_widget.populate_from_deployment(deployment)

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

    ########################
    ## HTTP Service response handling
    ########################

    def _on_http_response_received(self, response: dict) -> None:
        """Handle the HTTP response received from the BEC Atlas API."""
        response = HTTPResponse(**response)
        logger.debug(
            f"HTTP Response received: {response.request_url} with status {response.status}"
        )
        if AtlasEndpoints.REALMS_EXPERIMENTS in response.request_url:
            experiments = response.data if isinstance(response.data, list) else []
            self.experiment_selection.set_experiment_infos(experiments)
        elif AtlasEndpoints.SET_EXPERIMENT in response.request_url:
            self._on_overview_selected()

    @SafeSlot(dict)
    def _on_authenticated(self, auth_info: dict) -> None:
        """Handle authentication state change."""
        authenticated = False
        # Only if the user has owner access to the deployment, we consider them to be fully authenticated
        # This means that although they may authenticate against atlas, they won't be able to see any
        # extra information here
        if auth_info:
            info = AuthenticatedUserInfo.model_validate(auth_info)
            if (
                self._current_deployment_info
                and info.deployment_id == self._current_deployment_info.deployment_id
            ):
                authenticated = True
            else:
                logger.warning(
                    f"Authenticated user {info.email} does not have access to the current deployment {self._current_deployment_info.name if self._current_deployment_info else '<no deployment>'}."
                )
        self._authenticated = authenticated

        if authenticated:
            self.toolbar.components.get_action("experiment_selection").action.setEnabled(True)
            self.toolbar.components.get_action("messaging_services").action.setEnabled(True)
            self.toolbar.components.get_action("logout").action.setEnabled(True)
            self._fetch_available_experiments()  # Fetch experiments upon successful authentication
            self._atlas_info_widget.set_logged_in(info.email)
            self.toolbar.components.get_action("logout").set_authenticated(info)
        else:
            self.toolbar.components.get_action("experiment_selection").action.setEnabled(False)
            self.toolbar.components.get_action("messaging_services").action.setEnabled(False)
            self.toolbar.components.get_action("logout").action.setEnabled(False)
            # Delete data in experiment selection widget upon logout
            self.experiment_selection.set_experiment_infos([])
            self._on_overview_selected()  # Switch back to overview on logout
            self._atlas_info_widget.clear_login()  # Clear login status in atlas info widget on logout
            self.toolbar.components.get_action("logout").set_authenticated(None)
        self.authenticated.emit(authenticated)

    ################
    ## API Methods
    ################

    @SafeSlot(str, str, popup_error=True)
    def set_experiment(self, experiment_id: str, deployment_id: str) -> None:
        """Set the experiment information for the current experiment."""
        self.atlas_http_service.set_experiment(experiment_id, deployment_id)

    @SafeSlot(str, str, popup_error=True)
    def login(self, username: str, password: str) -> None:
        """Login to the BEC Atlas API with the provided username and password."""
        self.atlas_http_service.login(username=username, password=password)

    @SafeSlot(popup_error=True)
    def logout(self) -> None:
        """Logout from the BEC Atlas API."""
        self.atlas_http_service.logout()

    def get_user_info(self):
        """Get the current user information from the BEC Atlas API."""
        self.atlas_http_service.get_user_info()

    ###############
    ## Cleanup
    ###############

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
    from bec_lib.messages import DeploymentInfoMessage, ExperimentInfoMessage, SessionInfoMessage

    # proposal_info = ExperimentInfoMessage(**exp_info_dict)
    # session_info = SessionInfoMessage(name="Test Session", experiment=proposal_info)
    # deployment_info = DeploymentInfoMessage(
    #     deployment_id="test_deployment_001", active_session=session_info
    # )
    # window.set_experiment_info(proposal_info)
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())
