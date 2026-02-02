import json

from pydantic import BaseModel
from qtpy.QtCore import QUrl, Signal
from qtpy.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from qtpy.QtWidgets import QMessageBox, QWidget

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.services.bec_atlas_admin_view.login_dialog import LoginDialog


class HTTPResponse(BaseModel):
    request_url: str
    headers: dict
    status: int
    data: dict | list | str


class BECAtlasHTTPService(QWidget):
    """HTTP service using the QNetworkAccessManager to interact with the BEC Atlas API."""

    http_response_received = Signal(dict)
    authenticated = Signal(bool)

    def __init__(self, parent=None, base_url: str = "", headers: dict | None = None):
        super().__init__(parent)
        if headers is None:
            headers = {"accept": "application/json"}
        self._headers = headers
        self._base_url = base_url
        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.finished.connect(self._handle_response)
        self._authenticated = False

    def closeEvent(self, event):
        self.cleanup()
        return super().closeEvent(event)

    def cleanup(self):
        """Cleanup connection, destroy authenticate cookies."""

        # Disconnect signals to avoid handling responses after cleanup
        self.network_manager.finished.disconnect(self._handle_response)

        # Logout to invalidate session on server side
        self.logout()

        # Delete all cookies related to the base URL
        for cookie in self.network_manager.cookieJar().cookiesForUrl(QUrl(self._base_url)):
            self.network_manager.cookieJar().deleteCookie(cookie)

    def _handle_response(self, reply: QNetworkReply):
        """
        Handle the HTTP response from the server.

        Args:
            reply (QNetworkReply): The network reply object containing the response.
        """
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        raw_bytes = bytes(reply.readAll())
        request_url = reply.url().toString()
        headers = dict(reply.rawHeaderPairs())
        reply.deleteLater()

        if "login" in request_url and status == 200:
            self._authenticated = True
            self.authenticated.emit(True)
        elif "logout" in request_url and status == 200:
            self._authenticated = False
            self.authenticated.emit(False)

        # TODO, should we handle failures here or rather on more high levels?
        if status == 401:
            if "login" in request_url:
                # Failed login attempt
                self._show_warning(
                    title="Login Failed", text="Please check your login credentials."
                )
            else:
                self._show_warning(
                    title="Unauthorized",
                    text="You are not authorized to request this information. Please authenticate first.",
                )
            return
        self._handle_raw_response(raw_bytes, status, request_url, headers)

    def _handle_raw_response(self, raw_bytes: bytes, status: int, request_url: str, headers: dict):
        try:
            if len(raw_bytes) > 0:
                data = json.loads(raw_bytes.decode("utf-8"))
            else:
                data = {}

        except Exception:
            data = {}

        response = HTTPResponse(request_url=request_url, headers=headers, status=status, data=data)
        self.http_response_received.emit(response.model_dump())

    def _show_warning(self, title: str, text: str):
        """Show a warning message box for unauthorized access."""
        QMessageBox.warning(self, title, text, QMessageBox.StandardButton.Ok)

    def _show_login(self):
        """Show the login dialog to enter credentials."""
        dlg = LoginDialog(parent=self)
        dlg.credentials_entered.connect(self._set_credentials)
        dlg.exec_()  # blocking here is OK for login

    def _set_credentials(self, username: str, password: str):
        """Set the credentials and perform login."""
        self.post_request("/user/login", {"username": username, "password": password})

    ################
    # HTTP Methods
    ################

    def get_request(self, endpoint: str):
        """
        GET request to the API endpoint.

        Args:
            endpoint (str): The API endpoint to send the GET request to.
        """
        url = QUrl(self._base_url + endpoint)
        request = QNetworkRequest(url)
        for key, value in self._headers.items():
            request.setRawHeader(key.encode("utf-8"), value.encode("utf-8"))
        self.network_manager.get(request)

    def post_request(self, endpoint: str, payload: dict):
        """
        POST request to the API endpoint with a JSON payload.

        Args:
            endpoint (str): The API endpoint to send the POST request to.
            payload (dict): The JSON payload to include in the POST request.
        """
        url = QUrl(self._base_url + endpoint)
        request = QNetworkRequest(url)

        # Headers
        for key, value in self._headers.items():
            request.setRawHeader(key.encode("utf-8"), value.encode("utf-8"))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")

        payload_dump = json.dumps(payload).encode("utf-8")
        reply = self.network_manager.post(request, payload_dump)
        reply.finished.connect(lambda: self._handle_reply(reply))

    ################
    # API Methods
    ################

    @SafeSlot()
    def login(self):
        """Login to BEC Atlas with the provided username and password."""
        # TODO should we prompt here if already authenticated - and add option to skip login otherwise first destroy old token and re-authenticate?
        self._show_login()

    def logout(self):
        """Logout from BEC Atlas."""
        self.post_request("/user/logout", {})

    def check_health(self):
        """Check the health status of BEC Atlas."""
        self.get_request("/health")

    def get_realms(self, include_deployments: bool = True):
        """Get the list of realms from BEC Atlas. Requires authentication."""
        if not self._authenticated:
            self._show_login()

        # Requires authentication
        endpoint = "/realms"
        if include_deployments:
            endpoint += "?include_deployments=true"
        self.get_request(endpoint)
