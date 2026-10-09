"""Staff sign-in for *Device Config*, through the same BEC Atlas login as Admin View.

:class:`StaffAccess` is toolkit-free state shared by the QWidget and QML lock screens: it signs in
against BEC Atlas, and only unlocks when the account owns the running deployment.
"""

from __future__ import annotations

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import DeploymentInfoMessage
from qtpy.QtCore import QObject, QTimer, Signal
from qtpy.QtWidgets import QWidget

from bec_widgets.widgets.services.bec_atlas_admin_view.bec_atlas_http_service import (
    BECAtlasHTTPError,
    BECAtlasHTTPService,
)

logger = bec_logger.logger

ATLAS_URL = "https://bec-atlas-prod.psi.ch/api/v1"
SIGN_IN_TIMEOUT_MS = 20_000


class _GateAtlasService(BECAtlasHTTPService):
    """Atlas service that reports failures as a signal instead of message boxes."""

    failed = Signal(str)

    def _handle_response(self, reply):  # pylint: disable=invalid-name
        try:
            super()._handle_response(reply)
        except BECAtlasHTTPError as exc:
            text = str(exc)
            if "status code 401" in text or "status code 403" in text:
                self.failed.emit("User name or password is not correct.")
            else:
                self.failed.emit("BEC Atlas did not accept the request. Try again.")
            logger.warning(f"Device Config sign-in failed: {text}")

    def _show_warning(self, text: str):
        self.failed.emit(text)


class StaffAccess(QObject):
    """Sign-in state of the staff-only *Device Config* view.

    Args:
        dispatcher: The BEC dispatcher, for the deployment-info subscription.
        parent: Parent, normally the gate widget.
        atlas_url: BEC Atlas API base URL.
    """

    changed = Signal()

    def __init__(self, dispatcher=None, parent: QObject | None = None, atlas_url: str = ATLAS_URL):
        super().__init__(parent)
        self.dispatcher = dispatcher
        self.user = ""
        self.error = ""
        self.busy = False
        self.deployment = ""
        # The Atlas service is a QWidget; keep it a hidden child of the gate widget.
        self.service = _GateAtlasService(
            parent=parent if isinstance(parent, QWidget) else None, base_url=atlas_url
        )
        self.service.hide()
        self.service.authenticated.connect(self._on_authenticated)
        self.service.failed.connect(self._on_failed)
        self._timeout = QTimer(self, singleShot=True, interval=SIGN_IN_TIMEOUT_MS)
        self._timeout.timeout.connect(
            lambda: self._on_failed("BEC Atlas did not answer. Check the network and try again.")
        )
        if dispatcher is not None:
            dispatcher.connect_slot(
                self.on_deployment, MessageEndpoints.deployment_info(), from_start=True
            )

    @property
    def unlocked(self) -> bool:
        """True while a staff account of this deployment is signed in."""
        return bool(self.user)

    def on_deployment(self, msg: dict, _meta: dict | None = None) -> None:
        """Track the running deployment; sign-in checks ownership against it."""
        try:
            info = DeploymentInfoMessage.model_validate(msg)
        except Exception:  # pylint: disable=broad-except
            return
        self.service._set_current_deployment_info(info)  # pylint: disable=protected-access
        self.deployment = str(info.name or "")
        self.changed.emit()

    def sign_in(self, username: str, password: str) -> None:
        """Ask BEC Atlas to sign in; the view unlocks once ownership is confirmed."""
        if self.busy:
            return
        if not username.strip() or not password:
            self.error = "Enter your user name and password."
            self.changed.emit()
            return
        if not self.deployment:
            self.error = "This BEC session has no deployment registered with BEC Atlas."
            self.changed.emit()
            return
        self.busy = True
        self.error = ""
        self._timeout.start()
        self.changed.emit()
        self.service.login(username=username.strip(), password=password)

    def sign_out(self) -> None:
        """Lock the view again and end the Atlas session."""
        was_signed_in = self.unlocked
        self.user = ""
        self.busy = False
        self._timeout.stop()
        self.changed.emit()
        if was_signed_in:
            self.service.logout()

    def _on_authenticated(self, info: dict) -> None:
        self._timeout.stop()
        self.busy = False
        self.user = str((info or {}).get("email", "")) if info else ""
        if info:
            self.error = ""
        self.changed.emit()

    def _on_failed(self, text: str) -> None:
        self._timeout.stop()
        self.busy = False
        self.user = ""
        self.error = text
        self.changed.emit()

    def cleanup(self) -> None:
        """Drop the subscription and end the Atlas session."""
        self._timeout.stop()
        if self.dispatcher is not None:
            self.dispatcher.disconnect_slot(self.on_deployment, MessageEndpoints.deployment_info())
        if self.unlocked:
            self.service.cleanup()  # also ends the session on the Atlas server
        else:
            self.service._auth_timer.stop()  # pylint: disable=protected-access
        self.service.deleteLater()
