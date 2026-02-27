"""
This module is a QWidget-based HTTP service, responsible for interacting with the
BEC Atlas API using a QNetworkAccessManager. It prov"""

import json
import time
from enum import StrEnum
from typing import Literal

import jwt
from bec_lib.logger import bec_logger
from bec_lib.messages import DeploymentInfoMessage
from pydantic import BaseModel
from qtpy.QtCore import QObject, QTimer, QUrl, QUrlQuery, Signal
from qtpy.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from qtpy.QtWidgets import QMessageBox, QWidget

from bec_widgets.utils.error_popups import SafeSlot

logger = bec_logger.logger


class ATLAS_ENPOINTS(StrEnum):
    """Constants for BEC Atlas API endpoints."""

    LOGIN = "/user/login"
    LOGOUT = "/user/logout"
    REALMS_EXPERIMENTS = "/realms/experiments"
    SET_EXPERIMENT = "/deployments/experiment"
    USER_INFO = "/user/me"
    DEPLOYMENT_INFO = "/deployments/id"


class BECAtlasHTTPError(Exception):
    """Custom exception for BEC Atlas HTTP errors."""


class HTTPResponse(BaseModel):
    """Model representing an HTTP response."""

    request_url: str
    headers: dict
    status: int
    data: dict | list | str  # Check with Klaus if str is deprecated


class AuthenticatedUserInfo(BaseModel):
    """Model representing authenticated user information."""

    email: str
    exp: float
    groups: set[str]
    deployment_id: str


class AuthenticatedTimer(QObject):
    """Timer to track authentication expiration and emit a signal when the token expires."""

    expired = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_expired)

    def start(self, duration_seconds: float):
        """Start the timer with the given duration in seconds."""
        self._timer.start(int(duration_seconds * 1000))

    def stop(self):
        """Stop the timer."""
        self._timer.stop()

    @SafeSlot()
    def _on_expired(self):
        """Handle the timer expiration by emitting the expired signal."""
        logger.info("Authentication token has expired.")
        self.expired.emit()


class BECAtlasHTTPService(QWidget):
    """HTTP service using the QNetworkAccessManager to interact with the BEC Atlas API."""

    http_response = Signal(dict)  # HTTPResponse.model_dump() dict
    authenticated = Signal(dict)  # AuthenticatedUserInfo.model_dump() dict or {}
    authentication_expires = Signal(float)

    def __init__(self, parent=None, base_url: str = "", headers: dict | None = None):
        super().__init__(parent)
        if headers is None:
            headers = {"accept": "application/json"}
        self._headers = headers
        self._base_url = base_url
        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.finished.connect(self._handle_response)
        self._auth_user_info: AuthenticatedUserInfo | None = None
        self._auth_timer = self._create_auth_timer()
        self._current_deployment_info = None

    def _create_auth_timer(self) -> AuthenticatedTimer:
        """Create and connect the authenticated timer to handle token expiration."""
        timer = AuthenticatedTimer(self)
        timer.expired.connect(self.__clear_login_info)
        return timer

    @property
    def auth_user_info(self) -> AuthenticatedUserInfo | None:
        """Get the authenticated user information, including email and token expiration time."""
        return self._auth_user_info

    def __set_auth_info(self, login_info: dict[Literal["email", "exp"], str | float]):
        """Set the authenticated user information after a successful login."""
        login_info.update({"groups": []})  # Initialize groups as empty until we fetch user info
        login_info.update(
            {
                "deployment_id": (
                    self._current_deployment_info.deployment_id
                    if self._current_deployment_info
                    else ""
                )
            }
        )
        self._auth_user_info = AuthenticatedUserInfo(**login_info)
        # Start timer to clear auth info once token expires
        exp_time = login_info.get("exp", 0)
        current_time = time.time()  # TODO should we use server time to avoid clock skew issues?
        duration = max(0, exp_time - current_time)
        self._auth_timer.start(duration)

    def __set_auth_groups(self, groups: list[str]):
        """Set the authenticated user's groups after fetching user info."""
        if self._auth_user_info is not None:
            self._auth_user_info.groups = set(groups)

    def __clear_login_info(self, skip_logout: bool = False):
        """Clear the authenticated user information after logout."""
        self._auth_user_info = None
        if not skip_logout:
            self.logout()  # Ensure we also logout on the server side and invalidate the session

    def closeEvent(self, event):
        self.cleanup()
        return super().closeEvent(event)

    def cleanup(self):
        """Cleanup connection, destroy authenticate cookies."""
        logger.info("Cleaning up BECAtlasHTTPService: disconnecting signals and clearing cookies.")
        # Disconnect signals to avoid handling responses after cleanup
        self.network_manager.finished.disconnect(self._handle_response)

        # Logout to invalidate session on server side
        self.logout()

        # Stop the authentication timer
        self._auth_timer.stop()

        # Delete all cookies related to the base URL
        for cookie in self.network_manager.cookieJar().cookiesForUrl(QUrl(self._base_url)):
            self.network_manager.cookieJar().deleteCookie(cookie)

    @SafeSlot(QNetworkReply, popup_error=True)
    def _handle_response(self, reply: QNetworkReply):
        """
        Handle the HTTP response from the server.

        Args:
            reply (QNetworkReply): The network reply object containing the response.
        """
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        raw_bytes = reply.readAll().data()
        request_url = reply.url().toString()
        headers = dict([(i.data().decode(), j.data().decode()) for i, j in reply.rawHeaderPairs()])
        reply.deleteLater()

        # Any unsuccessful status code should raise here
        if status != 200:
            raise BECAtlasHTTPError(
                f"HTTP request for {request_url} failed with status code {status} and response: {raw_bytes.decode('utf-8')}"
            )

        if len(raw_bytes) > 0:
            data = json.loads(raw_bytes.decode())
        else:
            data = {}

        if data is None:
            data = {}
            logger.warning(f"Received empty response for {request_url} with status code {status}.")

        if not isinstance(data, dict):
            raise BECAtlasHTTPError(
                f"Expected response data to be a dict for {request_url}, but got {type(data)}. Response content: {data}"
            )

        if ATLAS_ENPOINTS.LOGIN.value in request_url:
            # If it's a login response, don't forward the token
            # but extract the expiration time and emit it
            token = data.get("access_token")
            data = jwt.decode(token, options={"verify_signature": False})
            self.authentication_expires.emit(data.get("exp", 0))
            # Now we set the auth info, and then fetch the user info to get the groups
            self.__set_auth_info(data)
            # Fetch information about the deployment info
            self.get_user_info()  # Fetch groups, then emit authenticated once groups are set on auth_user
        elif ATLAS_ENPOINTS.LOGOUT.value in request_url:
            self._auth_timer.stop()  # Stop the timer if it was running
            self.__clear_login_info(skip_logout=True)  # Skip calling logout again
            self.authenticated.emit({})
        elif ATLAS_ENPOINTS.USER_INFO.value in request_url:
            groups = data.get("groups", [])
            email = data.get("email", "")
            # Second step of authentication: We also have all groups now
            if self.auth_user_info is not None and self.auth_user_info.email == email:
                self.__set_auth_groups(groups)
                if self._current_deployment_info is not None:
                    # Now we need to fetch the deployment info to get the owner groups and check access rights,
                    # Then we can emit the authenticated signal with the full user info including groups if access is
                    # granted. Otherwise, we emit nothing and show a warning that the user does not have the access
                    # rights for the current deployment.
                    self.get_deployment_info(
                        deployment_id=self._current_deployment_info.deployment_id
                    )
        elif ATLAS_ENPOINTS.DEPLOYMENT_INFO.value in request_url:
            owner_groups = data.get("owner_groups", [])
            if self.auth_user_info is not None and not self.auth_user_info.groups.isdisjoint(
                owner_groups
            ):
                self.authenticated.emit(self.auth_user_info.model_dump())
            else:
                self._show_warning(
                    text=f"User {self.auth_user_info.email} does not have access to the active deployment {data.get('name', '<unknown>')}."
                )
                self.logout()  # Logout to clear auth info and stop timer since user does not have access

        response = HTTPResponse(request_url=request_url, headers=headers, status=status, data=data)
        self.http_response.emit(response.model_dump())

    def _show_warning(self, text: str):
        """Show a warning message to the user."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(text)
        msg.setWindowTitle("Authentication Warning")
        msg.exec_()

    #######################
    # GET/POST Request Methods
    #######################

    def _get_request(self, endpoint: str, query_parameters: dict | None = None):
        """
        GET request to the API endpoint.

        Args:
            endpoint (str): The API endpoint to send the GET request to.
            query_parameters (dict | None): Optional query parameters to include in the URL.
        """
        logger.info(f"Sending GET request to {endpoint}.")
        url = QUrl(self._base_url + endpoint)
        if query_parameters:
            query = QUrlQuery()
            for key, value in query_parameters.items():
                query.addQueryItem(key, value)
            url.setQuery(query)
        request = QNetworkRequest(url)
        for key, value in self._headers.items():
            request.setRawHeader(key.encode(), value.encode())
        self.network_manager.get(request)

    def _post_request(
        self, endpoint: str, payload: dict | None = None, query_parameters: dict | None = None
    ):
        """
        POST request to the API endpoint with a JSON payload.

        Args:
            endpoint (str): The API endpoint to send the POST request to.
            payload (dict): The JSON payload to include in the POST request.
            query_parameters (dict | None): Optional query parameters to include in the URL.
        """
        logger.info(f"Sending GET request to {endpoint}.")
        if payload is None:
            payload = {}
        url = QUrl(self._base_url + endpoint)
        if query_parameters:
            query = QUrlQuery()
            for key, value in query_parameters.items():
                query.addQueryItem(key, value)
            url.setQuery(query)
        request = QNetworkRequest(url)

        # Headers
        for key, value in self._headers.items():
            request.setRawHeader(key.encode(), value.encode())
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")

        payload_dump = json.dumps(payload).encode()
        self.network_manager.post(request, payload_dump)

    def _set_current_deployment_info(self, deployment_info: dict | DeploymentInfoMessage):
        """
        Set the current deployment information for the service.

        Args:
            deployment_info (dict | DeploymentInfoMessage): The deployment information to set.
        """
        if isinstance(deployment_info, dict):
            deployment_info = DeploymentInfoMessage.model_validate(deployment_info)
        self._current_deployment_info = deployment_info

    ################
    # API Methods
    ################

    @SafeSlot(str, str, popup_error=True)
    def login(self, username: str, password: str):
        """
        Login to BEC Atlas with the provided username and password.

        Args:
            username (str): The username for authentication.
            password (str): The password for authentication.
        """
        self._post_request(
            endpoint=ATLAS_ENPOINTS.LOGIN.value,
            payload={"username": username, "password": password},
        )

    @SafeSlot(popup_error=True)
    def logout(self):
        """Logout from BEC Atlas."""
        self._post_request(endpoint=ATLAS_ENPOINTS.LOGOUT.value)

    @SafeSlot(str, popup_error=True)
    def get_experiments_for_realm(self, realm_id: str):
        """
        Get the list of realms from BEC Atlas. Requires authentication.

        Args:
            realm_id (str): The ID of the realm to retrieve experiments for.
        """
        self._get_request(
            endpoint=ATLAS_ENPOINTS.REALMS_EXPERIMENTS.value,
            query_parameters={"realm_id": realm_id},
        )

    @SafeSlot(str, str)
    def set_experiment(self, experiment_id: str, deployment_id: str) -> None:
        """
        Set the current experiment information for the service.

        Args:
            experiment_id (str): The ID of the experiment to set.
            deployment_id (str): The ID of the deployment associated with the experiment.
        """
        self._post_request(
            endpoint=ATLAS_ENPOINTS.SET_EXPERIMENT.value,
            query_parameters={"experiment_id": experiment_id, "deployment_id": deployment_id},
        )

    @SafeSlot(popup_error=True)
    def get_user_info(self):
        """Get the current user information from BEC Atlas. Requires authentication."""
        self._get_request(endpoint=ATLAS_ENPOINTS.USER_INFO.value)

    @SafeSlot(str, popup_error=True)
    def get_deployment_info(self, deployment_id: str):
        """
        Get the deployment information for a given deployment ID. Requires authentication.

        Args:
            deployment_id (str): The ID of the deployment to retrieve information for.
        """
        self._get_request(
            endpoint=ATLAS_ENPOINTS.DEPLOYMENT_INFO.value,
            query_parameters={"deployment_id": deployment_id},
        )
