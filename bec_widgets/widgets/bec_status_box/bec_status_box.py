"""This module contains the BECStatusBox widget, which displays the status of different BEC services in a collapsible tree widget.
The widget automatically updates the status of all running BEC services, and displays their status.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import qdarktheme
from bec_lib.utils.import_utils import lazy_import_from
from qtpy.QtCore import Signal, Slot
from qtpy.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from bec_widgets.utils.bec_connector import BECConnector
from bec_widgets.widgets.bec_status_box.status_item import StatusItem

if TYPE_CHECKING:
    from bec_lib.client import BECClient

# TODO : Put normal imports back when Pydantic gets faster
BECStatus = lazy_import_from("bec_lib.messages", ("BECStatus",))
StatusMessage = lazy_import_from("bec_lib.messages", ("StatusMessage",))


@dataclass
class BECServiceInfoContainer:
    """Container to store information about the BEC services."""

    service_name: str
    status: str
    info: dict
    metrics: dict | None


class BECStatusBox(QWidget):
    """An autonomous widget to display the status of BEC services.

    Args:
        parent Optional : The parent widget for the BECStatusBox. Defaults to None.
        box_name Optional(str): The name of the top service label. Defaults to "BEC Server".
        client Optional(BECClient): The client object to connect to the BEC server. Defaults to None
        config Optional(BECStatusBoxConfig | dict): The configuration for the status box. Defaults to None.
        gui_id Optional(str): The unique id for the widget. Defaults to None.
    """

    CORE_SERVICES = ["DeviceServer", "ScanServer", "SciHub", "ScanBundler", "FileWriterManager"]

    service_update = Signal(BECServiceInfoContainer)
    bec_core_state = Signal(str)

    def __init__(
        self,
        parent=None,
        box_name: str = "BEC Server",
        client: BECClient = None,
        gui_id: str = None,
    ):
        QWidget.__init__(self, parent=parent)
        self.setLayout(QVBoxLayout(self))
        self.tree = QTreeWidget(self)
        self.layout().addWidget(self.tree)
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet(
            "QTreeWidget::item:!selected "
            "{ "
            "border: 1px solid gainsboro; "
            "border-left: none; "
            "border-top: none; "
            "}"
            "QTreeWidget::item:selected {}"
        )
        self.box_name = box_name
        self.status_container = defaultdict(lambda: {"info": None, "item": None, "widget": None})

        self.connector = BECConnector(client=client, gui_id=gui_id)

        self.init_ui()

        self.bec_core_state.connect(self.update_top_item_status)
        self.tree.itemDoubleClicked.connect(self.on_tree_item_double_clicked)
        self.startTimer(
            1000
        )  # use qobject's own timer instead of creating one, which may be stopped from another thread(?)

    def timerEvent(self, event):
        """Get the latest service status from the BEC server."""
        # pylint: disable=protected-access
        self.connector.client._update_existing_services()
        self.update_service_status(
            self.connector.client._services_info, self.connector.client._services_metric
        )

    def init_ui(self) -> None:
        """Init the UI for the BECStatusBox widget"""
        top_label = self._create_status_widget(self.box_name, status=BECStatus.IDLE)
        tree_item = QTreeWidgetItem(self.tree)
        tree_item.setExpanded(True)
        tree_item.setDisabled(True)
        self.status_container[self.box_name].update({"item": tree_item, "widget": top_label})
        self.tree.setItemWidget(tree_item, 0, top_label)
        self.tree.addTopLevelItem(tree_item)
        self.service_update.connect(top_label.update_config)
        self._initialized = True

    def _create_status_widget(
        self, service_name: str, status=BECStatus, info: dict = None, metrics: dict = None
    ) -> StatusItem:
        """Creates a StatusItem (QWidget) for the given service, and stores all relevant
        information about the service in the status_container.

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
        self._update_status_container(service_name, status, info, metrics)
        item = StatusItem(parent=self.tree, config=self.status_container[service_name]["info"])
        return item

    @Slot(str)
    def update_top_item_status(self, status: BECStatus) -> None:
        """Method to update the status of the top item in the tree widget.
        Gets the status from the Signal 'bec_core_state' and updates the StatusItem via the signal 'service_update'.

        Args:
            status (BECStatus): The state of the core services.
        """
        self.status_container[self.box_name]["info"].status = status
        self.service_update.emit(self.status_container[self.box_name]["info"])

    def _update_status_container(
        self, service_name: str, status: BECStatus, info: dict, metrics: dict = None
    ) -> None:
        """Update the status_container with the newest status and metrics for the BEC service.
        If information about the service already exists, it will create a new entry.

        Args:
            service_name (str): The name of the service.
            status (BECStatus): The status of the service.
            info (dict): The information about the service.
            metrics (dict): The metrics of the service.
        """
        container = self.status_container[service_name].get("info", None)

        if container:
            container.status = status.name
            container.info = info
            container.metrics = metrics
            return
        service_info_item = BECServiceInfoContainer(
            service_name=service_name, status=status.name, info=info, metrics=metrics
        )
        self.status_container[service_name].update({"info": service_info_item})

    @Slot(dict, dict)
    def update_service_status(self, services_info: dict, services_metric: dict) -> None:
        """Callback function services_metric from BECServiceStatusMixin.
        It updates the status of all services.

        Args:
            services_info (dict): A dictionary containing the service status for all running BEC services.
            services_metric (dict): A dictionary containing the service metrics for all running BEC services.
        """
        checked = [self.box_name]
        services_info = self.update_core_services(services_info, services_metric)
        checked.extend(self.CORE_SERVICES)

        for service_name, msg in sorted(services_info.items()):
            checked.append(service_name)
            metric_msg = services_metric.get(service_name, None)
            metrics = metric_msg.metrics if metric_msg else None
            if service_name not in self.status_container:
                self.add_tree_item(service_name, msg.status, msg.info, metrics)
            self._update_status_container(service_name, msg.status, msg.info, metrics)
            self.service_update.emit(self.status_container[service_name]["info"])

    def update_core_services(self, services_info: dict, services_metric: dict) -> dict:
        """Update the core services of BEC, and emit the updated status to the BECStatusBox.

        Args:
            services_info (dict): A dictionary containing the service status of different services.
            services_metric (dict): A dictionary containing the service metrics of different services.

        Returns:
            dict: The services_info dictionary after removing the info updates related to the CORE_SERVICES
        """
        core_state = BECStatus.RUNNING
        for service_name in sorted(self.CORE_SERVICES):
            metric_msg = services_metric.get(service_name, None)
            metrics = metric_msg.metrics if metric_msg else None
            msg = services_info.pop(service_name, None)
            if msg is None:
                msg = StatusMessage(name=service_name, status=BECStatus.ERROR, info={})
            if service_name not in self.status_container:
                self.add_tree_item(service_name, msg.status, msg.info, metrics)

            self._update_status_container(service_name, msg.status, msg.info, metrics)
            core_state = msg.status if msg.status.value < core_state.value else core_state

            self.service_update.emit(self.status_container[service_name]["info"])

            # self.add_tree_item(service_name, msg.status, msg.info, metrics)

        self.bec_core_state.emit(core_state.name if core_state else "NOTCONNECTED")
        return services_info

    def add_tree_item(
        self, service_name: str, status: BECStatus, info: dict = None, metrics: dict = None
    ) -> None:
        """Method to add a new QTreeWidgetItem together with a StatusItem to the tree widget.

        Args:
            service_name (str): The name of the service.
            status (BECStatus): The status of the service.
            info (dict): The information about the service.
            metrics (dict): The metrics of the service.
        """
        item_widget = self._create_status_widget(service_name, status, info, metrics)
        toplevel_item = self.status_container[self.box_name]["item"]
        item = QTreeWidgetItem(toplevel_item)  # setDisabled=True
        toplevel_item.addChild(item)
        self.tree.setItemWidget(item, 0, item_widget)
        self.service_update.connect(item_widget.update_config)

        self.status_container[service_name].update({"item": item, "widget": item_widget})

    @Slot(QTreeWidgetItem, int)
    def on_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Callback function for double clicks on individual QTreeWidgetItems in the collapsed section.

        Args:
            item (QTreeWidgetItem): The item that was double clicked.
            column (int): The column that was double clicked.
        """
        for _, objects in self.status_container.items():
            if objects["item"] == item:
                objects["widget"].show_popup()

    def closeEvent(self, event):
        self.connector.cleanup()


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
