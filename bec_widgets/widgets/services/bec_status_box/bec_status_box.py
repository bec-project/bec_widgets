"""This module contains the BECStatusBox widget, which displays the status of different BEC services.
The widget automatically updates the status of all running BEC services, and displays their status.
"""

from __future__ import annotations

import time
import weakref
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.utils.import_utils import lazy_import_from
from pydantic import BaseModel
from qtpy.QtCore import QObject, QThreadPool, QTimer, Signal
from qtpy.QtWidgets import QHBoxLayout, QMessageBox, QWidget

from bec_widgets.utils.bec_connector import Worker
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.services.bec_status_box.status_box_widgets import StatusBoxWidgetView
from bec_widgets.widgets.services.bec_status_box.status_model import (
    RestartState,
    ServiceStatusModel,
    build_rows,
    friendly_name,
)

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.client import BECClient
    from bec_lib.messages import (
        BECStatus,
        ServiceMetricMessage,
        ServiceRequestMessage,
        StatusMessage,
    )
else:
    # TODO : Put normal imports back when Pydantic gets faster
    BECStatus, ServiceRequestMessage = lazy_import_from(
        "bec_lib.messages", ("BECStatus", "ServiceRequestMessage")
    )

logger = bec_logger.logger

RESTART_TIMEOUT_S = 120


@dataclass
class BECServiceInfoContainer:
    """Container to store information about the BEC services."""

    service_name: str
    status: str
    info: dict
    metrics: dict | None


class BECServiceStatusMixin(QObject):
    """Polls the service status of the BEC server and emits it via the services_update signal.

    The status boxes and server pills of one client share one poller (``shared``): it reads only
    while at least one of them is shown (``add_viewer`` / ``remove_viewer``), every
    POLL_INTERVAL_MS, and hands each new viewer the last result at once. A poller made directly
    starts polling right away and is cleaned up by its owner.

    Args:
        client (BECClient): The client object to connect to the BEC server.
        start (bool): Start polling right away. The shared poller waits for its first viewer.
    """

    services_update = Signal(dict, dict)

    ICON_NAME = "dns"
    # the services publish their status every 3 s; polling faster would show nothing new
    POLL_INTERVAL_MS = 3000

    _shared: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

    def __init__(self, parent, client: BECClient, start: bool = True):
        super().__init__(parent)
        self.client = client
        # the Redis reads run on the thread pool, one at a time, so a slow Redis never blocks the GUI
        self._worker: Worker | None = None
        self._viewers: set[int] = set()
        self.last_update: tuple[dict, dict] | None = None
        self._service_update_timer = QTimer()
        self._service_update_timer.setInterval(self.POLL_INTERVAL_MS)
        self._service_update_timer.timeout.connect(self._get_service_status)
        if start:
            self._service_update_timer.start()

    @classmethod
    def shared(cls, client: BECClient) -> BECServiceStatusMixin:
        """The poller shared by all status boxes and pills of a client."""
        poller = cls._shared.get(client)
        if poller is None:
            poller = cls(None, client, start=False)
            cls._shared[client] = poller
        return poller

    @classmethod
    def reset_shared(cls) -> None:
        """Stop and drop all shared pollers, e.g. between tests."""
        for poller in list(cls._shared.values()):
            poller.cleanup()
        cls._shared.clear()

    def add_viewer(self, viewer: QObject) -> None:
        """Poll while this widget shows the status; the first viewer starts with a read."""
        self._viewers.add(id(viewer))
        if not self._service_update_timer.isActive():
            self._service_update_timer.start()
            self._get_service_status()

    def remove_viewer(self, viewer: QObject) -> None:
        """Stop polling once no widget shows the status any more."""
        self._viewers.discard(id(viewer))
        if not self._viewers:
            self._service_update_timer.stop()

    @property
    def polling(self) -> bool:
        """Whether the poller reads the service status periodically."""
        return self._service_update_timer.isActive()

    def _get_service_status(self):
        """Read the latest service status from the BEC server off the GUI thread."""
        if self._worker is not None:
            return
        # pylint: disable=protected-access
        self._worker = Worker(self.client._update_existing_services)
        self._worker.signals.completed.connect(self._on_service_status)
        self._worker.signals.failed.connect(self._on_read_failed)
        QThreadPool.globalInstance().start(self._worker)

    @SafeSlot()
    def _on_service_status(self):
        self._worker = None
        # pylint: disable=protected-access
        self.last_update = (self.client._services_info, self.client._services_metric)
        self.services_update.emit(*self.last_update)

    @SafeSlot(str)
    def _on_read_failed(self, _error: str):
        self._worker = None

    def cleanup(self):
        """Cleanup the BECServiceStatusMixin."""
        self._viewers.clear()
        self._service_update_timer.stop()
        self._service_update_timer.deleteLater()
        if self._worker is not None:
            for signal in (self._worker.signals.completed, self._worker.signals.failed):
                try:
                    signal.disconnect()
                except (TypeError, RuntimeError):
                    pass


class BECStatusBox(BECWidget, QWidget):
    """An autonomous widget to display the status of BEC services.

    The header shows the overall state of BEC, the list groups the core services and the other
    services (clients, data processing). Clicking a service shows its host, user, uptime, load and
    versions inline, with a button to copy them.

    Args:
        parent Optional : The parent widget for the BECStatusBox. Defaults to None.
        box_name Optional(str): The name of the top service label. Defaults to "BEC Server".
        client Optional(BECClient): The client object to connect to the BEC server. Defaults to None
        bec_service_status_mixin Optional(BECServiceStatusMixin): Source of the service updates.
            Defaults to the poller shared by all status boxes of the client.
        gui_id Optional(str): The unique id for the widget. Defaults to None.
    """

    PLUGIN = True
    CORE_SERVICES = ["DeviceServer", "ScanServer", "SciHub", "ScanBundler", "FileWriterManager"]
    USER_ACCESS = ["get_server_state", "remove", "attach", "detach", "screenshot"]

    service_update = Signal(BECServiceInfoContainer)
    bec_core_state = Signal(str)

    def __init__(
        self,
        parent=None,
        box_name: str = "BEC Servers",
        client: BECClient = None,
        bec_service_status_mixin: BECServiceStatusMixin = None,
        gui_id: str = None,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, gui_id=gui_id, **kwargs)
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.box_name = box_name
        self.status_container: dict[str, BECServiceInfoContainer] = {}
        self.core_state = "IDLE"
        self.model = ServiceStatusModel(self)

        # a poller handed in belongs to this box; the shared one only counts it as a viewer
        self._owns_poller = bool(bec_service_status_mixin)
        if not bec_service_status_mixin:
            bec_service_status_mixin = BECServiceStatusMixin.shared(self.client)
        self.bec_service_status = bec_service_status_mixin

        self.view = StatusBoxWidgetView(self.model, self)
        self.view.setMinimumSize(280, 220)
        self.main_layout.addWidget(self.view)
        self.model.restart_requested.connect(self.confirm_restart)
        self._restart_requested_at: float | None = None
        self._restart_timeout = QTimer(self)
        self._restart_timeout.setSingleShot(True)
        self._restart_timeout.timeout.connect(self._restart_timed_out)
        self._restart_clear = QTimer(self)
        self._restart_clear.setSingleShot(True)
        self._restart_clear.timeout.connect(lambda: self.model.set_restart(RestartState.NONE))
        self.bec_service_status.services_update.connect(self.update_service_status)
        self._poller_connected = True
        self.bec_core_state.connect(self.update_top_item_status)
        last_update = getattr(self.bec_service_status, "last_update", None)
        if isinstance(last_update, tuple):
            self.update_service_status(*last_update)  # what another box already read

    def showEvent(self, event):  # pylint: disable=invalid-name
        super().showEvent(event)
        self.bec_service_status.add_viewer(self)

    def hideEvent(self, event):  # pylint: disable=invalid-name
        super().hideEvent(event)
        self.bec_service_status.remove_viewer(self)

    def get_server_state(self) -> str:
        """Get the state ("RUNNING", "BUSY", "IDLE", "ERROR", "NOTCONNECTED") of the BEC server"""
        return self.core_state

    @SafeSlot(str)
    def update_top_item_status(self, status: str) -> None:
        """Update the combined state of the core services.

        Args:
            status (str): The state of the core services.
        """
        if status == self.core_state:
            return
        self.core_state = status
        self._refresh_model()

    def _update_status_container(
        self,
        service_name: str,
        status: BECStatus | str,
        info: BaseModel | dict,
        metrics: dict = None,
    ) -> None:
        """Store the newest status and metrics of a BEC service.

        Args:
            service_name (str): The name of the service.
            status (BECStatus | str): The status of the service.
            info (BaseModel | dict): The information about the service. The container keeps a dict.
            metrics (dict): The metrics of the service.
        """
        status = status.name if isinstance(status, BECStatus) else status
        info = info.model_dump() if isinstance(info, BaseModel) else info
        container = self.status_container.get(service_name)
        if container:
            container.status = status
            container.info = info
            container.metrics = metrics
        else:
            container = BECServiceInfoContainer(
                service_name=service_name, status=status, info=info, metrics=metrics
            )
            self.status_container[service_name] = container
        self.service_update.emit(container)

    @SafeSlot(dict, dict)
    def update_service_status(
        self,
        services_info: dict[str, StatusMessage],
        services_metric: dict[str, ServiceMetricMessage],
    ) -> None:
        """Callback for BECServiceStatusMixin.services_update. Updates the status of all services.

        Args:
            services_info (dict): The service status for all running BEC services.
            services_metric (dict): The service metrics for all running BEC services.
        """
        services_info = dict(services_info)
        checked = list(self.CORE_SERVICES)
        services_info = self.update_core_services(services_info, services_metric, refresh=False)

        for service_name, msg in sorted(services_info.items()):
            checked.append(service_name)
            metric_msg = services_metric.get(service_name, None)
            metrics = metric_msg.metrics if metric_msg else None
            if not msg:
                self._update_status_container(service_name, "NOTCONNECTED", {}, metrics)
                continue
            self._update_status_container(service_name, msg.status, msg.info, metrics)
        self.remove_stale_services(checked)
        self._refresh_model()

    def update_core_services(
        self, services_info: dict, services_metric: dict, refresh: bool = True
    ) -> dict:
        """Update the core services of BEC and emit their combined state.

        Args:
            services_info (dict): The service status of different services.
            services_metric (dict): The service metrics of different services.
            refresh (bool): Whether to refresh the view right away.

        Returns:
            dict: The services_info dictionary without the CORE_SERVICES entries.
        """
        core_state = BECStatus.RUNNING
        for service_name in self.CORE_SERVICES:
            metric_msg = services_metric.get(service_name, None)
            metrics = metric_msg.metrics if metric_msg else None
            msg = services_info.pop(service_name, None)
            if not msg:
                self._update_status_container(service_name, "NOTCONNECTED", {}, metrics)
                core_state = None
                continue
            self._update_status_container(service_name, msg.status, msg.info, metrics)
            if core_state and msg.status.value < core_state.value:
                core_state = msg.status

        self.core_state = core_state.name if core_state else "NOTCONNECTED"
        self.bec_core_state.emit(self.core_state)
        if refresh:
            self._refresh_model()
        return services_info

    def remove_stale_services(self, checked: list) -> None:
        """Remove services that are no longer reported by BEC.

        Args:
            checked (list): The services that are currently known.
        """
        for key in [key for key in self.status_container if key not in checked]:
            self.status_container.pop(key)

    def _refresh_model(self) -> None:
        rows = build_rows(self.status_container.values(), self.CORE_SERVICES)
        self.model.set_rows(rows, self.core_state)
        scihub = self.status_container.get("SciHub")
        self.model.set_can_restart(scihub is not None and scihub.status != "NOTCONNECTED")
        self._check_restart_progress()

    # ---- server restart -----------------------------------------------------------------------

    @SafeSlot()
    def confirm_restart(self) -> None:
        """Ask the user to confirm, then request a restart of the BEC server."""
        answer = QMessageBox.warning(
            self,
            "Restart BEC server",
            "Restart all BEC server services?\n\n"
            "A running scan is aborted, and devices are reloaded. "
            "Clients stay connected and continue after the restart.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.request_restart()

    def request_restart(self) -> None:
        """Request a restart of all BEC server services through SciHub.

        The progress is shown in the header: a service counts as restarted once it reports
        RUNNING with a process start time after the request.
        """
        if not self.model.can_restart:
            return
        self._restart_requested_at = time.time()
        self.client.connector.send(
            MessageEndpoints.service_request(), ServiceRequestMessage(action="restart")
        )
        logger.info("BEC server restart requested from the status box")
        self._restart_clear.stop()
        self._restart_timeout.start(int(RESTART_TIMEOUT_S * 1000))
        self.model.set_restart(
            RestartState.RUNNING, f"Restarting BEC server · 0/{len(self.CORE_SERVICES)}"
        )

    def _restarted_services(self) -> list[str]:
        restarted = []
        for name in self.CORE_SERVICES:
            container = self.status_container.get(name)
            if container is None or container.status not in ("RUNNING", "BUSY"):
                continue
            started = (container.metrics or {}).get("create_time")
            if started is not None and started >= self._restart_requested_at:
                restarted.append(name)
        return restarted

    def _check_restart_progress(self) -> None:
        if self._restart_requested_at is None:
            return
        done = len(self._restarted_services())
        total = len(self.CORE_SERVICES)
        if done < total:
            self.model.set_restart(RestartState.RUNNING, f"Restarting BEC server · {done}/{total}")
            return
        self._restart_requested_at = None
        self._restart_timeout.stop()
        self.model.set_restart(RestartState.DONE, "BEC server restarted")
        self._restart_clear.start(6000)
        self.submit_task(self._reload_client)

    def _reload_client(self) -> None:
        """Reload scans and devices in this client after a restart (runs off the GUI thread)."""
        # pylint: disable=protected-access
        try:
            self.client._load_scans()
            self.client.device_manager._reload_action()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(f"Reloading the client after the server restart failed: {exc}")

    def _restart_timed_out(self) -> None:
        if self._restart_requested_at is None:
            return
        missing = [n for n in self.CORE_SERVICES if n not in self._restarted_services()]
        self._restart_requested_at = None
        names = ", ".join(friendly_name(n)[0] for n in missing)
        self.model.set_restart(
            RestartState.FAILED, f"Restart not finished: {names} did not come back"
        )
        self._restart_clear.start(15000)

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        """Restyle the view after a theme change.

        Args:
            theme (str): The name of the new theme.
        """
        self.view.apply_theme()

    def cleanup(self):
        """Cleanup the BECStatusBox widget."""
        self.bec_service_status.remove_viewer(self)
        if self._poller_connected:
            self._poller_connected = False
            self.bec_service_status.services_update.disconnect(self.update_service_status)
        if self._owns_poller:
            self.bec_service_status.cleanup()
        self._restart_timeout.stop()
        self._restart_clear.stop()
        self.view.cleanup()
        return super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    main_window = BECStatusBox()
    main_window.show()
    sys.exit(app.exec())
