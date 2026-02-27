import datetime
import time
from types import SimpleNamespace
from unittest import mock

import jwt
import pytest
from bec_lib.messages import (
    DeploymentInfoMessage,
    ExperimentInfoMessage,
    MessagingConfig,
    MessagingServiceScopeConfig,
    SessionInfoMessage,
)
from qtpy.QtCore import QByteArray, QUrl
from qtpy.QtNetwork import QNetworkRequest

from bec_widgets.widgets.services.bec_atlas_admin_view.bec_atlas_admin_view import BECAtlasAdminView
from bec_widgets.widgets.services.bec_atlas_admin_view.bec_atlas_http_service import (
    ATLAS_ENPOINTS,
    AuthenticatedUserInfo,
    BECAtlasHTTPError,
    BECAtlasHTTPService,
    HTTPResponse,
)
from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.experiment_mat_card import (
    ExperimentMatCard,
)
from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.experiment_selection import (
    ExperimentSelection,
    is_match,
)
from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.utils import (
    format_datetime,
    format_name,
    format_schedule,
)


class _FakeQByteArray:
    def __init__(self, payload: bytes):
        self._payload = payload

    def data(self) -> bytes:
        return self._payload


class _FakeReply:
    def __init__(
        self,
        *,
        request_url: str,
        status: int = 200,
        payload: bytes = b"{}",
        headers: list[tuple[bytes, bytes]] | None = None,
    ):
        self._request_url = request_url
        self._status = status
        self._payload = payload
        self._headers = (
            headers
            if headers is not None
            else [(QByteArray(b"content-type"), QByteArray(b"application/json"))]
        )
        self.deleted = False

    def attribute(self, attr):
        assert attr == QNetworkRequest.Attribute.HttpStatusCodeAttribute
        return self._status

    def readAll(self):
        return _FakeQByteArray(self._payload)

    def url(self):
        return QUrl(self._request_url)

    def rawHeaderPairs(self):
        return self._headers

    def deleteLater(self):
        self.deleted = True


class TestBECAtlasHTTPService:

    @pytest.fixture
    def http_service(self, qtbot):
        """Fixture to create a BECAtlasHTTPService instance."""
        service = BECAtlasHTTPService(base_url="http://localhost:8000")
        qtbot.addWidget(service)
        qtbot.waitExposed(service)
        return service

    def test_initialization(self, http_service):
        """Test that the BECAtlasHTTPService initializes correctly."""
        assert http_service._base_url == "http://localhost:8000"
        assert http_service._auth_timer._timer.isActive() == False
        assert http_service._headers == {"accept": "application/json"}

    def test_get_request_uses_network_manager_get(self, http_service):
        """Test that _get_request uses the network manager's get method with correct parameters."""

        with mock.patch.object(http_service.network_manager, "get") as mock_get:
            http_service._get_request(
                endpoint=ATLAS_ENPOINTS.REALMS_EXPERIMENTS.value,
                query_parameters={"realm_id": "realm-1"},
            )

            mock_get.assert_called_once()
            request = mock_get.call_args.args[0]
            assert request.url().toString() == (
                "http://localhost:8000/realms/experiments?realm_id=realm-1"
            )
            assert request.rawHeader("accept") == QByteArray(b"application/json")

    def test_post_request_uses_network_manager_post(self, http_service):
        """Test that _post_request uses the network manager's post method with correct parameters."""

        with mock.patch.object(http_service.network_manager, "post") as mock_post:
            http_service._post_request(
                endpoint=ATLAS_ENPOINTS.LOGIN.value, payload={"username": "alice", "password": "pw"}
            )

            mock_post.assert_called_once()
            request, payload = mock_post.call_args.args
            assert request.url().toString() == "http://localhost:8000/user/login"
            assert request.rawHeader("accept") == QByteArray(b"application/json")
            assert payload == b'{"username": "alice", "password": "pw"}'

    def test_public_api(self, http_service):
        """Test BEC ATLAS public API methods from the http service."""
        with mock.patch.object(http_service, "_get_request") as mock_get:
            # User info
            http_service.get_user_info()
            mock_get.assert_called_once_with(endpoint=ATLAS_ENPOINTS.USER_INFO.value)

            mock_get.reset_mock()
            # Deployment info
            http_service.get_deployment_info("dep-1")
            mock_get.assert_called_once_with(
                endpoint=ATLAS_ENPOINTS.DEPLOYMENT_INFO.value,
                query_parameters={"deployment_id": "dep-1"},
            )

            mock_get.reset_mock()
            # Realms experiments
            http_service.get_experiments_for_realm("realm-1")
            mock_get.assert_called_once_with(
                endpoint=ATLAS_ENPOINTS.REALMS_EXPERIMENTS.value,
                query_parameters={"realm_id": "realm-1"},
            )

        with mock.patch.object(http_service, "_post_request") as mock_post:
            # Logout
            http_service.logout()
            mock_post.assert_called_once_with(endpoint=ATLAS_ENPOINTS.LOGOUT.value)

            mock_post.reset_mock()
            # Login
            http_service.login("alice", "pw")
            mock_post.assert_called_once_with(
                endpoint=ATLAS_ENPOINTS.LOGIN.value, payload={"username": "alice", "password": "pw"}
            )

            mock_post.reset_mock()
            # Set experiment
            http_service.set_experiment("exp-1", "dep-1")
            mock_post.assert_called_once_with(
                endpoint=ATLAS_ENPOINTS.SET_EXPERIMENT.value,
                query_parameters={"experiment_id": "exp-1", "deployment_id": "dep-1"},
            )

    def test_handle_response_login(self, http_service, qtbot):
        """Test that handling a login response correctly decodes the token and starts the auth timer."""
        exp = time.time() + 300
        token = jwt.encode({"email": "alice@example.org", "exp": exp}, "secret", algorithm="HS256")
        payload = ("{" f'"access_token": "{token}"' "}").encode()
        reply = _FakeReply(
            request_url="http://localhost:8000/user/login", status=200, payload=payload
        )

        with mock.patch.object(http_service, "get_user_info") as mock_get_user_info:

            with qtbot.waitSignal(http_service.authentication_expires, timeout=1000) as blocker:
                http_service._handle_response(reply)

            assert blocker.args[0] == pytest.approx(exp)
            assert http_service.auth_user_info is not None
            assert http_service.auth_user_info.email == "alice@example.org"
            assert http_service.auth_user_info.groups == set()
            http_service.get_user_info.assert_called_once()

    def test_handle_response_logout(self, http_service, qtbot):
        """Test handle response for logout."""
        http_service._auth_user_info = AuthenticatedUserInfo(
            email="alice@example.org", exp=time.time() + 60, groups={"staff"}, deployment_id="dep-1"
        )
        reply = _FakeReply(
            request_url="http://localhost:8000/user/logout", status=200, payload=b"{}"
        )

        with qtbot.waitSignal(http_service.authenticated, timeout=1000) as blocker:
            http_service._handle_response(reply)

        assert blocker.args[0] == {}
        assert http_service.auth_user_info is None

    def test_handle_response_user_info(self, http_service):
        """Test handle response for user info endpoint correctly updates auth user info."""
        http_service._auth_user_info = AuthenticatedUserInfo(
            email="alice@example.org", exp=time.time() + 60, groups=set(), deployment_id="dep-1"
        )
        http_service._current_deployment_info = SimpleNamespace(deployment_id="dep-1")
        reply = _FakeReply(
            request_url="http://localhost:8000/user/me",
            status=200,
            payload=b'{"email": "alice@example.org", "groups": ["operators", "staff"]}',
        )

        with mock.patch.object(http_service, "get_deployment_info") as mock_get_deployment_info:
            http_service._handle_response(reply)

            assert http_service.auth_user_info is not None
            assert http_service.auth_user_info.groups == {"operators", "staff"}
            mock_get_deployment_info.assert_called_once_with(deployment_id="dep-1")

    def test_handle_response_deployment_info(self, http_service, qtbot):
        """Test handling deployment info response"""

        # Groups match: should emit authenticated signal with user info
        http_service._auth_user_info = AuthenticatedUserInfo(
            email="alice@example.org",
            exp=time.time() + 60,
            groups={"operators"},
            deployment_id="dep-1",
        )
        reply = _FakeReply(
            request_url="http://localhost:8000/deployments/id?deployment_id=dep-1",
            status=200,
            payload=b'{"owner_groups": ["operators"], "name": "Beamline Deployment"}',
        )

        with qtbot.waitSignal(http_service.authenticated, timeout=1000) as blocker:
            http_service._handle_response(reply)

        assert blocker.args[0]["email"] == "alice@example.org"
        assert set(blocker.args[0]["groups"]) == {"operators"}
        assert blocker.args[0]["deployment_id"] == "dep-1"

        # Groups do not match: should show warning and logout
        http_service._auth_user_info = AuthenticatedUserInfo(
            email="alice@example.org",
            exp=time.time() + 60,
            groups={"operators"},
            deployment_id="dep-1",
        )
        reply = _FakeReply(
            request_url="http://localhost:8000/deployments/id?deployment_id=dep-1",
            status=200,
            payload=b'{"owner_groups": ["no-operators"], "name": "Beamline Deployment"}',
        )
        with (
            mock.patch.object(http_service, "_show_warning") as mock_show_warning,
            mock.patch.object(http_service, "logout") as mock_logout,
        ):
            http_service._handle_response(reply)

            mock_show_warning.assert_called_once()
            mock_logout.assert_called_once()

    def test_handle_response_emits_http_response(self, http_service, qtbot):
        """Test that _handle_response emits the http_response signal with correct parameters for a generic response."""
        reply = _FakeReply(
            request_url="http://localhost:8000/realms/experiments?realm_id=realm-1",
            status=200,
            payload=b'{"items": []}',
        )

        with qtbot.waitSignal(http_service.http_response, timeout=1000) as blocker:
            http_service._handle_response(reply)

        assert blocker.args[0]["request_url"] == (
            "http://localhost:8000/realms/experiments?realm_id=realm-1"
        )
        assert blocker.args[0]["status"] == 200
        assert blocker.args[0]["headers"] == {"content-type": "application/json"}
        assert blocker.args[0]["data"] == {"items": []}

    def test_handle_response_raises_for_invalid_status(self, http_service):
        reply = _FakeReply(
            request_url="http://localhost:8000/user/me",
            status=401,
            payload=b'{"detail": "Unauthorized"}',
        )

        with pytest.raises(BECAtlasHTTPError):
            http_service._handle_response(reply, _override_slot_params={"raise_error": True})


@pytest.fixture
def experiment_info_message() -> ExperimentInfoMessage:
    data = {
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
    return ExperimentInfoMessage.model_validate(data)


@pytest.fixture
def experiment_info_list(experiment_info_message: ExperimentInfoMessage) -> list[dict]:
    """Fixture to provide a list of experiment info dictionaries."""
    another_experiment_info = {
        "_id": "p22623",
        "owner_groups": ["admin"],
        "access_groups": ["unx-sls_xda_bs", "p22623"],
        "realm_id": "TestBeamline",
        "proposal": "",
        "title": "Experiment without Proposal",
        "firstname": "Alice",
        "lastname": "Johnson",
        "email": "alice.johnson@psi.ch",
        "account": "johnson_a",
        "pi_firstname": "Bob",
        "pi_lastname": "Brown",
        "pi_email": "bob.brown@psi.ch",
        "pi_account": "brown_b",
        "eaccount": "e22623",
        "pgroup": "p22623",
        "abstract": "",
        "schedule": [],
        "proposal_submitted": "",
        "proposal_expire": "",
        "proposal_status": "",
        "delta_last_schedule": None,
        "mainproposal": "",
    }
    return [
        experiment_info_message.model_dump(),
        ExperimentInfoMessage.model_validate(another_experiment_info).model_dump(),
    ]


class TestBECAtlasExperimentSelection:

    def test_format_name(self, experiment_info_message: ExperimentInfoMessage):
        """Test utils format name"""
        assert format_name(experiment_info_message) == "John Doe"

    def test_format_schedule(self, experiment_info_message: ExperimentInfoMessage):
        """Test utils format schedule"""
        assert format_schedule(experiment_info_message.schedule) == (
            "2025-01-01 08:00",
            "2025-01-03 18:00",
        )
        assert format_schedule(experiment_info_message.schedule, as_datetime=True) == (
            datetime.datetime.strptime(
                experiment_info_message.schedule[0]["start"], "%d/%m/%Y %H:%M:%S"
            ),
            datetime.datetime.strptime(
                experiment_info_message.schedule[0]["end"], "%d/%m/%Y %H:%M:%S"
            ),
        )
        assert format_schedule([]) == ("", "")

    def test_format_datetime(self):
        """Test utils format datetime"""
        dt = datetime.datetime(2025, 1, 1, 8, 0)
        assert format_datetime(dt) == "2025-01-01 08:00"
        assert format_datetime(None) == ""

    @pytest.fixture
    def mat_card(self, qtbot):
        """Fixture to create an ExperimentMatCard instance."""
        card = ExperimentMatCard()
        qtbot.addWidget(card)
        qtbot.waitExposed(card)
        return card

    def test_set_experiment_info(
        self, mat_card: ExperimentMatCard, experiment_info_message: ExperimentInfoMessage, qtbot
    ):
        """Test that set_experiment_info correctly updates the card's display based on the provided experiment info, whether it's a dictionary or an ExperimentInfoMessage instance."""
        # Test with ExperimentInfoMessage instance
        mat_card.set_experiment_info(experiment_info_message)
        assert mat_card._card_pgroup.text() == "p22622"
        assert mat_card._card_title.text() == "Next Experiment"
        assert mat_card._abstract_label.text() == experiment_info_message.abstract.strip()
        assert mat_card.experiment_info == experiment_info_message.model_dump()
        assert mat_card._activate_button.isEnabled()
        assert mat_card._activate_button.text() == "Activate"

        # Test with dictionary input
        mat_card.set_experiment_info(experiment_info_message.model_dump())
        mat_card.set_title("Experiment Details")
        assert mat_card._card_pgroup.text() == "p22622"
        assert mat_card._card_title.text() == "Experiment Details"
        assert mat_card._abstract_label.text() == experiment_info_message.abstract.strip()
        assert mat_card.experiment_info == experiment_info_message.model_dump()
        assert mat_card._activate_button.isEnabled()
        assert mat_card._activate_button.text() == "Activate"

        with qtbot.waitSignal(mat_card.experiment_selected, timeout=1000) as blocker:
            mat_card._activate_button.click()
        assert blocker.args[0] == experiment_info_message.model_dump()

    def test_is_match(self):
        """Test is_match utility function for search functionality."""
        data = {"name": "Test Experiment", "description": "This is a test."}
        relevant_keys = ["name", "description"]

        # Test exact match
        assert is_match("Test Experiment", data, relevant_keys, enable_fuzzy=False)
        assert not is_match("Nonexistent", data, relevant_keys, enable_fuzzy=False)

        # Test fuzzy match
        assert not is_match("Nonexistent", data, relevant_keys, enable_fuzzy=True)
        assert is_match("Test Experimnt", data, relevant_keys, enable_fuzzy=True)
        # Typo should still match with fuzzy enabled
        assert is_match("Test Experiement", data, relevant_keys, enable_fuzzy=True)

    @pytest.fixture
    def experiment_selection(self, qtbot):
        """Fixture to create an ExperimentSelection instance with sample experiment info."""
        selection = ExperimentSelection()
        qtbot.addWidget(selection)
        qtbot.waitExposed(selection)
        return selection

    def test_set_experiments(
        self, experiment_selection: ExperimentSelection, experiment_info_list: list[dict]
    ):
        """Test that set_experiment_infos correctly populates the experiment selection with provided experiment info."""
        with mock.patch.object(
            experiment_selection._card_tab, "set_experiment_info"
        ) as mock_set_experiment_info:
            experiment_selection.set_experiment_infos(experiment_info_list)
            assert len(experiment_selection._experiment_infos) == 2

            # Next experiment should be the first one as the second one has no schedule
            mock_set_experiment_info.assert_called_once_with(experiment_info_list[0])

            # Should be on card tab
            assert experiment_selection._tabs.currentWidget() == experiment_selection._card_tab

    def test_filter_functionality(
        self, experiment_selection: ExperimentSelection, experiment_info_list: list[dict], qtbot
    ):
        """Test that the search functionality correctly filters experiments based on the search query."""
        wid = experiment_selection
        wid.set_experiment_infos(experiment_info_list)

        # First move to the table tab
        wid._tabs.setCurrentWidget(wid._table_tab)
        assert wid._side_card.experiment_info == wid._next_experiment

        # Initially, both experiments should be in the table
        assert wid._table.rowCount() == 2
        with qtbot.waitSignal(wid._with_proposals.toggled, timeout=1000):
            wid._with_proposals.setChecked(False)  # Should hide one experiment
        assert wid._table.rowCount() == 1
        with qtbot.waitSignal(wid._without_proposals.toggled, timeout=1000):
            wid._without_proposals.setChecked(False)  # Should hide the other experiment
        assert wid._table.rowCount() == 0
        with qtbot.waitSignals(
            [wid._without_proposals.toggled, wid._with_proposals.toggled], timeout=1000
        ):
            wid._without_proposals.setChecked(True)
            wid._with_proposals.setChecked(True)  # Should show both experiments again
        assert wid._table.rowCount() == 2

        # Click on first experiment and check if side card updates
        with qtbot.waitSignal(wid._table.itemSelectionChanged, timeout=1000):
            wid._table.selectRow(0)  # Select the first experiment
        pgroup = wid._table.item(0, 0).text()  # pgroup
        exp = [exp for exp in experiment_info_list if exp["pgroup"] == pgroup][0]
        assert wid._side_card.experiment_info == exp

        # Click on second experiment and check if side card updates
        with qtbot.waitSignal(wid._table.itemSelectionChanged, timeout=1000):
            wid._table.selectRow(1)  # Select the second experiment

        pgroup = wid._table.item(1, 0).text()  # pgroup
        exp = [exp for exp in experiment_info_list if exp["pgroup"] == pgroup][0]
        assert wid._side_card.experiment_info == exp

        wid.search_input.setText("Experiment without Proposal")
        with mock.patch.object(wid, "_apply_row_filter") as mock_apply_row_filter:
            with qtbot.waitSignal(wid.fuzzy_is_disabled.stateChanged, timeout=1000):
                wid.fuzzy_is_disabled.setChecked(True)  # Disable fuzzy search
            mock_apply_row_filter.assert_called_once_with("Experiment without Proposal")

        assert wid._enable_fuzzy_search is False

    def test_emit_selected_experiment(
        self, experiment_selection: ExperimentSelection, experiment_info_list: list[dict], qtbot
    ):
        """Test that clicking the activate button on the side card emits the experiment_selected signal with the correct experiment info."""
        wid = experiment_selection
        wid.set_experiment_infos(experiment_info_list)

        wid._tabs.setCurrentWidget(wid._table_tab)
        with qtbot.waitSignal(wid._table.itemSelectionChanged, timeout=1000):
            wid._table.selectRow(1)  # Select the second experiment
        pgroup = wid._table.item(1, 0).text()  # pgroup
        exp = [exp for exp in experiment_info_list if exp["pgroup"] == pgroup][0]

        with qtbot.waitSignal(wid.experiment_selected, timeout=1000) as blocker:
            wid._side_card._activate_button.click()
        assert blocker.args == [exp]


class TestBECAtlasAdminView:

    @pytest.fixture
    def admin_view(self, qtbot):
        """Fixture to create a BECAtlasAdminView instance."""
        with mock.patch(
            "bec_widgets.widgets.services.bec_atlas_admin_view.bec_atlas_admin_view.BECAtlasAdminView._connect_dispatcher"
        ):
            view = BECAtlasAdminView()
            qtbot.addWidget(view)
            qtbot.waitExposed(view)
            return view

    def test_init_and_login(self, admin_view: BECAtlasAdminView, qtbot):
        """Test that the BECAtlasAdminView initializes correctly."""
        # Check that the atlas URL is set correctly
        assert admin_view._atlas_url == "https://bec-atlas-dev.psi.ch/api/v1"

        # Test that clicking the login button emits the credentials_entered signal with the correct username and password
        with mock.patch.object(admin_view.atlas_http_service, "login") as mock_login:
            with qtbot.waitSignal(admin_view.overview_widget.login_requested, timeout=1000):
                admin_view.overview_widget._login.username.setText("alice")
                admin_view.overview_widget._login.password.setText("password")
                admin_view.overview_widget._login._emit_credentials()

            mock_login.assert_called_once_with(username="alice", password="password")
            mock_login.reset_mock()
            admin_view._authenticated = True
            with mock.patch.object(admin_view, "logout") as mock_logout:
                with qtbot.waitSignal(admin_view.overview_widget.login_requested, timeout=1000):
                    admin_view.overview_widget._login.password.setText("password")
                    admin_view.overview_widget._login._emit_credentials()
                mock_logout.assert_called_once()
                mock_login.assert_called_once_with(username="alice", password="password")

    def test_on_experiment_selected(
        self, admin_view: BECAtlasAdminView, deployment_info: DeploymentInfoMessage, qtbot
    ):
        """Test that selecting an experiment in the overview widget correctly calls the HTTP service to set the experiment and updates the current experiment view."""
        # First we need to simulate that we are authenticated and have deployment info
        admin_view._update_deployment_info(deployment_info.model_dump(), {})
        with mock.patch.object(
            admin_view.atlas_http_service, "set_experiment"
        ) as mock_set_experiment:
            with qtbot.waitSignal(
                admin_view.experiment_selection.experiment_selected, timeout=1000
            ):
                admin_view.experiment_selection.experiment_selected.emit(
                    deployment_info.active_session.experiment.model_dump()
                )
            mock_set_experiment.assert_called_once_with(
                deployment_info.active_session.experiment.pgroup, deployment_info.deployment_id
            )

    @pytest.fixture
    def deployment_info(
        self, experiment_info_message: ExperimentInfoMessage
    ) -> DeploymentInfoMessage:
        """Fixture to provide a DeploymentInfoMessage instance."""
        return DeploymentInfoMessage(
            deployment_id="dep-1",
            name="Test Deployment",
            messaging_config=MessagingConfig(
                signal=MessagingServiceScopeConfig(enabled=False),
                teams=MessagingServiceScopeConfig(enabled=False),
                scilog=MessagingServiceScopeConfig(enabled=False),
            ),
            active_session=SessionInfoMessage(
                experiment=experiment_info_message, name="Test Session"
            ),
        )

    def test_on_authenticated(
        self, admin_view: BECAtlasAdminView, deployment_info: DeploymentInfoMessage, qtbot
    ):
        """Test that the on_authenticated method correctly updates the UI based on authentication state."""
        # Simulate successful authentication
        auth_info = AuthenticatedUserInfo(
            email="alice@example.com",
            exp=time.time() + 300,
            groups={"operators"},
            deployment_id="dep-1",
        )

        # First check that deployment info updates all fields correctly
        admin_view._update_deployment_info(deployment_info.model_dump(), {})

        assert admin_view.atlas_http_service._current_deployment_info == deployment_info
        assert (
            admin_view._atlas_info_widget._bl_info_label.text()
            == f"{deployment_info.active_session.experiment.realm_id} @ {deployment_info.name}"
        )
        assert admin_view._atlas_info_widget._atlas_url_label.text() == admin_view._atlas_url

        # Now run on_authenticated, this enables all toolbar buttons
        # and calls fetch experiments. It also switches the overview widget
        # to the current experiment view.
        # Default should be on the overview widget
        assert admin_view.stacked_layout.currentWidget() == admin_view.overview_widget
        with mock.patch.object(
            admin_view, "_fetch_available_experiments"
        ) as mock_fetch_experiments:
            with qtbot.waitSignal(admin_view.authenticated, timeout=1000) as blocker:
                admin_view._on_authenticated(auth_info.model_dump())
            # Fetch experiments should be called
            mock_fetch_experiments.assert_called_once()
            assert blocker.args[0] is True
            assert (
                admin_view._atlas_info_widget._atlas_url_label.text()
                == f"{admin_view._atlas_info_widget._atlas_url_text}  |  {auth_info.email}"
            )
            assert (
                admin_view.toolbar.components.get_action("messaging_services").action.isEnabled()
                is False
            )

            # Logout timer is running
            logout_action = admin_view.toolbar.components.get_action("logout")
            assert logout_action.action.isEnabled() is True
            assert logout_action._tick_timer.isActive() is True

            # Current Experiment widget should be visible in the overview
            assert (
                admin_view.overview_widget.stacked_layout.currentWidget()
                == admin_view.overview_widget._experiment_overview_widget
            )

            # Click toolbar to switch to experiment selection
            exp_select = admin_view.toolbar.components.get_action("experiment_selection")
            assert exp_select.action.isEnabled() is True
            with qtbot.waitSignal(exp_select.action.triggered, timeout=1000):
                exp_select.action.trigger()

            assert admin_view.stacked_layout.currentWidget() == admin_view.experiment_selection

            # Now we simulate that the authentication expires
            # This deactivates buttons, resets the overview widget
            # and emits authenticated signal with False
            with qtbot.waitSignal(admin_view.authenticated, timeout=1000) as blocker:
                admin_view._on_authenticated({})  # Simulate not authenticated anymore
            assert blocker.args[0] is False
            assert logout_action._tick_timer.isActive() is False
            assert admin_view._atlas_info_widget._atlas_url_label.text() == admin_view._atlas_url
            assert (
                admin_view.overview_widget.stacked_layout.currentWidget()
                == admin_view.overview_widget._login_widget
            )
            # View should switch back to overview
            assert admin_view.stacked_layout.currentWidget() == admin_view.overview_widget

    def test_fetch_experiments(
        self, admin_view: BECAtlasAdminView, deployment_info: DeploymentInfoMessage, qtbot
    ):
        """Test that _fetch_available_experiments correctly calls the HTTP service and updates the experiment selection widget."""
        admin_view._update_deployment_info(deployment_info.model_dump(), {})
        with mock.patch.object(
            admin_view.atlas_http_service, "get_experiments_for_realm"
        ) as mock_get_experiments:
            admin_view._fetch_available_experiments()
            mock_get_experiments.assert_called_once_with(
                deployment_info.active_session.experiment.realm_id
            )

    def test_on_http_response_received(
        self, experiment_info_list: list[dict], admin_view: BECAtlasAdminView, qtbot
    ):
        """Test that _on_http_response_received correctly handles HTTP responses and updates the UI accordingly."""
        realms = HTTPResponse(
            request_url=f"{admin_view._atlas_url}/{ATLAS_ENPOINTS.REALMS_EXPERIMENTS}/experiments?realm_id=TestBeamline",
            status=200,
            headers={"content-type": "application/json"},
            data=experiment_info_list,
        )
        with mock.patch.object(
            admin_view.experiment_selection, "set_experiment_infos"
        ) as mock_set_experiment_infos:
            admin_view._on_http_response_received(realms.model_dump())
            mock_set_experiment_infos.assert_called_once_with(experiment_info_list)

        set_experiment = HTTPResponse(
            request_url=f"{admin_view._atlas_url}/{ATLAS_ENPOINTS.SET_EXPERIMENT}",
            status=200,
            headers={"content-type": "application/json"},
            data={},
        )
        with mock.patch.object(admin_view, "_on_overview_selected") as mock_on_overview_selected:
            admin_view._on_http_response_received(set_experiment.model_dump())
            mock_on_overview_selected.assert_called_once()
