"""This module contains the BECStatusBox widget, which displays the status of different BEC services.
The widget automatically updates the status of all running BEC services, and displays their status.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from bec_lib.logger import bec_logger
from bec_lib.utils.import_utils import lazy_import_from
from pydantic import BaseModel
from qtpy.QtCore import QObject, QTimer, Signal
from qtpy.QtWidgets import QHBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.compact_popup import CompactPopupWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.services.bec_status_box.status_box_widgets import StatusBoxWidgetView
from bec_widgets.widgets.services.bec_status_box.status_model import ServiceStatusModel, build_rows

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.client import BECClient
    from bec_lib.messages import BECStatus, ServiceMetricMessage, StatusMessage
else:
    # TODO : Put normal imports back when Pydantic gets faster
    BECStatus = lazy_import_from("bec_lib.messages", ("BECStatus",))

logger = bec_logger.logger

QML_FILE = Path(__file__).parent / "qml" / "StatusBox.qml"


@dataclass
class BECServiceInfoContainer:
    """Container to store information about the BEC services."""

    service_name: str
    status: str
    info: dict
    metrics: dict | None


class BECServiceStatusMixin(QObject):
    """Mixin to receive the latest service status from the BEC server and emit it via services_update signal.

    Args:
        client (BECClient): The client object to connect to the BEC server.
    """

    services_update = Signal(dict, dict)

    ICON_NAME = "dns"

    def __init__(self, parent, client: BECClient):
        super().__init__(parent)
        self.client = client
        self._service_update_timer = QTimer()
        self._service_update_timer.timeout.connect(self._get_service_status)
        self._service_update_timer.start(1000)

    def _get_service_status(self):
        """Get the latest service status from the BEC server."""
        # pylint: disable=protected-access
        self.client._update_existing_services()
        self.services_update.emit(self.client._services_info, self.client._services_metric)

    def cleanup(self):
        """Cleanup the BECServiceStatusMixin."""
        self._service_update_timer.stop()
        self._service_update_timer.deleteLater()


class BECStatusBox(BECWidget, CompactPopupWidget):
    """An autonomous widget to display the status of BEC services.

    The header shows the overall state of BEC, the list groups the core services and the other
    services (clients, data processing). Clicking a service shows its host, user, uptime, load and
    versions inline, with a button to copy them.

    Args:
        parent Optional : The parent widget for the BECStatusBox. Defaults to None.
        box_name Optional(str): The name of the top service label. Defaults to "BEC Server".
        client Optional(BECClient): The client object to connect to the BEC server. Defaults to None
        bec_service_status_mixin Optional(BECServiceStatusMixin): Source of the service updates.
        view Optional(str): "qml" or "widgets". Defaults to the BEC_STATUS_BOX_VIEW environment
            variable, or "qml".
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
        view: str | None = None,
        gui_id: str = None,
        **kwargs,
    ):
        super().__init__(parent=parent, layout=QHBoxLayout, client=client, gui_id=gui_id, **kwargs)

        self.box_name = box_name
        self.status_container: dict[str, BECServiceInfoContainer] = {}
        self.core_state = "IDLE"
        self.model = ServiceStatusModel(self)

        if not bec_service_status_mixin:
            bec_service_status_mixin = BECServiceStatusMixin(self, client=self.client)
        self.bec_service_status = bec_service_status_mixin

        self.label = box_name
        self.tooltip = "BEC servers health status"
        self.view_kind = (view or os.environ.get("BEC_STATUS_BOX_VIEW") or "qml").lower()
        self.view = self._create_view()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.addWidget(self.view)
        self.model.summaryChanged.connect(self._update_compact_state)
        self.bec_service_status.services_update.connect(self.update_service_status)
        self.bec_core_state.connect(self.update_top_item_status)
        self._update_compact_state()

    def _create_view(self) -> QWidget:
        """Create the QML or QWidget view on the shared model."""
        if self.view_kind == "qml":
            try:
                # pylint: disable=import-outside-toplevel
                from bec_widgets.utils.quick import create_quick_widget

                quick = create_quick_widget(
                    self, QML_FILE, context={"statusModel": self.model}, raise_on_error=True
                )
                quick.setMinimumSize(280, 220)
                return quick
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(f"QML status box unavailable, using the QWidget view: {exc}")
                self.view_kind = "widgets"
        view = StatusBoxWidgetView(self.model, self)
        view.setMinimumSize(280, 220)
        return view

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
        self, service_name: str, status: BECStatus | str, info: dict, metrics: dict = None
    ) -> None:
        """Store the newest status and metrics of a BEC service.

        Args:
            service_name (str): The name of the service.
            status (BECStatus | str): The status of the service.
            info (dict): The information about the service.
            metrics (dict): The metrics of the service.
        """
        status = status.name if isinstance(status, BECStatus) else status
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
        # FIXME: We simply replace the pydantic message with dict for now until we refactor the widget
        for val in services_info.values():
            val.info = val.info.model_dump() if isinstance(val.info, BaseModel) else val.info
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
            info = msg.info.model_dump() if isinstance(msg.info, BaseModel) else msg.info
            self._update_status_container(service_name, msg.status, info, metrics)
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

    def _update_compact_state(self) -> None:
        tone = self.model.tone
        self.set_global_state(
            {"success": "success", "warning": "warning", "emergency": "emergency"}.get(
                tone, "default"
            )
        )
        self.tooltip = f"{self.model.headline}\n{self.model.detail}".strip()

    def cleanup(self):
        """Cleanup the BECStatusBox widget."""
        self.bec_service_status.cleanup()
        if isinstance(self.view, StatusBoxWidgetView):
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
