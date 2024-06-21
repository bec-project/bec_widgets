"""This module contains the BECStatusBox widget, which displays the status of different BEC services in a collapsible tree widget.
The widget automatically updates the status of all running BEC services, and displays their status.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import qdarktheme
from bec_lib.utils.import_utils import lazy_import_from
from pydantic import BaseModel, Field, field_validator
from qtpy.QtCore import QObject, QTimer, Signal, Slot
from qtpy.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from bec_widgets.utils.bec_connector import BECConnector, ConnectionConfig
from bec_widgets.widgets.bec_status_box.status_item import StatusItem

if TYPE_CHECKING:
    from bec_lib.client import BECClient

# TODO : Put normal imports back when Pydantic gets faster
BECStatus = lazy_import_from("bec_lib.messages", ("BECStatus",))


class BECStatusBoxConfig(ConnectionConfig):
    pass


class BECServiceInfoContainer(BaseModel):
    """Container to store information about the BEC services."""

    service_name: str
    status: BECStatus | str = Field(
        default="NOTCONNECTED",
        description="The status of the service. Can be any of the BECStatus names, or NOTCONNECTED.",
    )
    info: dict
    metrics: dict | None
    model_config: dict = {"validate_assignment": True}

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        """Validate input for status. Accept BECStatus and NOTCONNECTED.

        Args:
            v (BECStatus | str): The input value.

        Returns:
            str: The validated status.
        """
        if v in list(BECStatus.__members__.values()):
            return v.name
        if v in list(BECStatus.__members__.keys()) or v == "NOTCONNECTED":
            return v
        raise ValueError(
            f"Status must be one of {BECStatus.__members__.values()} or 'NOTCONNECTED'. Input {v}"
        )


class BECServiceStatusMixin(QObject):
    """A mixin class to update the service status, and metrics.
    It emits a signal 'services_update' when the service status is updated.

    Args:
        client (BECClient): The client object to connect to the BEC server.
    """

    services_update = Signal(dict, dict)

    def __init__(self, client: BECClient):
        super().__init__()
        self.client = client
        self._service_update_timer = QTimer()
        self._service_update_timer.timeout.connect(self._get_service_status)
        self._service_update_timer.start(1000)

    def _get_service_status(self):
        """Pull latest service and metrics updates from REDIS for all services, and emit both via 'services_update' signal."""
        # pylint: disable=protected-access
        self.client._update_existing_services()
        self.services_update.emit(self.client._services_info, self.client._services_metric)


class BECStatusBox(BECConnector, QTreeWidget):
    """A widget to display the status of different BEC services.
    This widget automatically updates the status of all running BEC services, and displays their status.
    Information about the individual services is collapsible, and double clicking on
    the individual service will display the metrics about the service.

    Args:
        parent Optional : The parent widget for the BECStatusBox. Defaults to None.
        service_name Optional(str): The name of the top service label. Defaults to "BEC Server".
        client Optional(BECClient): The client object to connect to the BEC server. Defaults to None
        config Optional(BECStatusBoxConfig | dict): The configuration for the status box. Defaults to None.
        gui_id Optional(str): The unique id for the widget. Defaults to None.
    """

    CORE_SERVICES = ["DeviceServer", "ScanServer", "SciHub", "ScanBundler", "FileWriterManager"]

    service_update = Signal(dict)
    bec_core_state = Signal(str)

    def __init__(
        self,
        parent=None,
        service_name: str = "BEC Server",
        client: BECClient = None,
        config: BECStatusBoxConfig | dict = None,
        gui_id: str = None,
    ):
        if config is None:
            config = BECStatusBoxConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = BECStatusBoxConfig(**config)
        super().__init__(client=client, config=config, gui_id=gui_id)
        QTreeWidget.__init__(self, parent=parent)

        self.service_name = service_name
        self.config = config

        self.bec_service_info_container = {}
        self.tree_items = {}
        self.tree_top_item = None
        self.bec_service_status = BECServiceStatusMixin(client=self.client)

        self.init_ui()
        self.bec_service_status.services_update.connect(self.update_service_status)
        self.bec_core_state.connect(self.update_top_item_status)
        self.itemDoubleClicked.connect(self.on_tree_item_double_clicked)

    def init_ui(self) -> None:
        """Initialize the UI for the status box, and add QTreeWidget as the basis for the status box."""
        self.init_ui_tree_widget()
        top_label = self._create_status_widget(self.service_name, status=BECStatus.IDLE)
        self.tree_top_item = QTreeWidgetItem()
        self.tree_top_item.setExpanded(True)
        self.tree_top_item.setDisabled(True)
        self.addTopLevelItem(self.tree_top_item)
        self.setItemWidget(self.tree_top_item, 0, top_label)
        self.service_update.connect(top_label.update_config)

    def _create_status_widget(
        self, service_name: str, status=BECStatus, info: dict = None, metrics: dict = None
    ) -> StatusItem:
        """Creates a StatusItem (QWidget) for the given service, and stores all relevant
        information about the service in the bec_service_info_container.

        Args:
            service_name (str): The name of the service.
            status (BECStatus): The status of the service.
            info Optional(dict): The information about the service. Default is {}
            metric Optional(dict): Metrics for the respective service. Default is None

        Returns:
            StatusItem: The status item widget.
        """
        if info is None:
            info = {}
        self._update_bec_service_container(service_name, status, info, metrics)
        item = StatusItem(
            parent=self,
            config={
                "service_name": service_name,
                "status": status.name,
                "info": info,
                "metrics": metrics,
            },
        )
        return item

    @Slot(str)
    def update_top_item_status(self, status: BECStatus) -> None:
        """Method to update the status of the top item in the tree widget.
        Gets the status from the Signal 'bec_core_state' and updates the StatusItem via the signal 'service_update'.

        Args:
            status (BECStatus): The state of the core services.
        """
        self.bec_service_info_container[self.service_name].status = status
        self.service_update.emit(self.bec_service_info_container[self.service_name].model_dump())

    def _update_bec_service_container(
        self, service_name: str, status: BECStatus, info: dict, metrics: dict = None
    ) -> None:
        """Update the bec_service_info_container with the newest status and metrics for the BEC service.
        If information about the service already exists, it will create a new entry.

        Args:
            service_name (str): The name of the service.
            service_info (StatusMessage): A class containing the service status.
            service_metric (ServiceMetricMessage): A class containing the service metrics.
        """
        container = self.bec_service_info_container.get(service_name, None)
        if container:
            container.status = status
            container.info = info
            container.metrics = metrics
            return
        service_info_item = BECServiceInfoContainer(
            service_name=service_name, status=status, info=info, metrics=metrics
        )
        self.bec_service_info_container.update({service_name: service_info_item})

    @Slot(dict, dict)
    def update_service_status(self, services_info: dict, services_metric: dict) -> None:
        """Callback function services_metric from BECServiceStatusMixin.
        It updates the status of all services.

        Args:
            services_info (dict): A dictionary containing the service status for all running BEC services.
            services_metric (dict): A dictionary containing the service metrics for all running BEC services.
        """
        checked = []
        services_info = self.update_core_services(services_info, services_metric)
        checked.extend(self.CORE_SERVICES)

        for service_name, msg in sorted(services_info.items()):
            checked.append(service_name)
            metric_msg = services_metric.get(service_name, None)
            metrics = metric_msg.metrics if metric_msg else None
            if service_name in self.tree_items:
                self._update_bec_service_container(
                    service_name=service_name, status=msg.status, info=msg.info, metrics=metrics
                )
                self.service_update.emit(self.bec_service_info_container[service_name].model_dump())
                continue

            item_widget = self._create_status_widget(
                service_name=service_name, status=msg.status, info=msg.info, metrics=metrics
            )
            item = QTreeWidgetItem()
            item.setDisabled(True)
            self.service_update.connect(item_widget.update_config)
            self.tree_top_item.addChild(item)
            self.setItemWidget(item, 0, item_widget)
            self.tree_items.update({service_name: (item, item_widget)})

        self.check_redundant_tree_items(checked)

    def update_core_services(self, services_info: dict, services_metric: dict) -> dict:
        """Method to process status and metrics updates of core services (stored in CORE_SERVICES).
        If a core services is not connected, it should not be removed from the status widget

        Args:
            services_info (dict): A dictionary containing the service status of different services.
            services_metric (dict): A dictionary containing the service metrics of different services.

        Returns:
            dict: The services_info dictionary after removing the info updates related to the CORE_SERVICES
        """
        bec_core_state = "RUNNING"
        for service_name in sorted(self.CORE_SERVICES):
            metric_msg = services_metric.get(service_name, None)
            metrics = metric_msg.metrics if metric_msg else None
            if service_name not in services_info:
                self.bec_service_info_container[service_name].status = "NOTCONNECTED"
                bec_core_state = "ERROR"
            else:
                msg = services_info.pop(service_name)
                self._update_bec_service_container(
                    service_name=service_name, status=msg.status, info=msg.info, metrics=metrics
                )
                bec_core_state = (
                    "RUNNING" if (msg.status.value > 1 and bec_core_state == "RUNNING") else "ERROR"
                )

            if service_name in self.tree_items:
                self.service_update.emit(self.bec_service_info_container[service_name].model_dump())
                continue
            self.add_tree_item(service_name, msg.status, msg.info, metrics)

        self.bec_core_state.emit(bec_core_state)
        return services_info

    def check_redundant_tree_items(self, checked: list) -> None:
        """Utility method to check and remove redundant objects from the BECStatusBox.

        Args:
            checked (list): A list of services that are currently running.
        """
        to_be_deleted = [key for key in self.tree_items if key not in checked]

        for key in to_be_deleted:
            item, _ = self.tree_items.pop(key)
            self.tree_top_item.removeChild(item)

    def add_tree_item(
        self, service_name: str, status: BECStatus, info: dict = None, metrics: dict = None
    ) -> None:
        """Method to add a new QTreeWidgetItem together with a StatusItem to the tree widget.

        Args:
            service_name (str): The name of the service.
            service_status_msg (StatusMessage): The status of the service.
            metrics (dict): The metrics of the service.
        """
        item_widget = self._create_status_widget(
            service_name=service_name, status=status, info=info, metrics=metrics
        )
        item = QTreeWidgetItem()
        self.service_update.connect(item_widget.update_config)
        self.tree_top_item.addChild(item)
        self.setItemWidget(item, 0, item_widget)
        self.tree_items.update({service_name: (item, item_widget)})

    def init_ui_tree_widget(self) -> None:
        """Initialise the tree widget for the status box."""
        self.setHeaderHidden(True)
        self.setStyleSheet(
            "QTreeWidget::item:!selected "
            "{ "
            "border: 1px solid gainsboro; "
            "border-left: none; "
            "border-top: none; "
            "}"
            "QTreeWidget::item:selected {}"
        )

    @Slot(QTreeWidgetItem, int)
    def on_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Callback function for double clicks on individual QTreeWidgetItems in the collapsed section.

        Args:
            item (QTreeWidgetItem): The item that was double clicked.
            column (int): The column that was double clicked.
        """
        for _, (tree_item, status_widget) in self.tree_items.items():
            if tree_item == item:
                status_widget.show_popup()

    def closeEvent(self, event):
        super().cleanup()
        QTreeWidget().closeEvent(event)


def main():
    """Main method to run the BECStatusBox widget."""
    # pylint: disable=import-outside-toplevel
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    qdarktheme.setup_theme("auto")
    main_window = BECStatusBox()
    main_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
