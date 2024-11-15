"""This module contains the BECStatusBox widget, which displays the status of different BEC services in a collapsible tree widget.
The widget automatically updates the status of all running BEC services, and displays their status.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bec_lib.utils.import_utils import lazy_import_from
from qtpy.QtCore import QObject, QTimer, Signal, Slot
from qtpy.QtWidgets import QHBoxLayout, QTreeWidget, QTreeWidgetItem

from bec_widgets.qt_utils.compact_popup import CompactPopupWidget
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.services.bec_status_box.status_item import StatusItem

if TYPE_CHECKING:
    from bec_lib.client import BECClient

# TODO : Put normal imports back when Pydantic gets faster
BECStatus = lazy_import_from("bec_lib.messages", ("BECStatus",))


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

    Args:
        parent Optional : The parent widget for the BECStatusBox. Defaults to None.
        box_name Optional(str): The name of the top service label. Defaults to "BEC Server".
        client Optional(BECClient): The client object to connect to the BEC server. Defaults to None
        config Optional(BECStatusBoxConfig | dict): The configuration for the status box. Defaults to None.
        gui_id Optional(str): The unique id for the widget. Defaults to None.
    """

    PLUGIN = True
    CORE_SERVICES = ["DeviceServer", "ScanServer", "SciHub", "ScanBundler", "FileWriterManager"]

    service_update = Signal(BECServiceInfoContainer)
    bec_core_state = Signal(str)

    def __init__(
        self,
        parent=None,
        box_name: str = "BEC Servers",
        client: BECClient = None,
        bec_service_status_mixin: BECServiceStatusMixin = None,
        gui_id: str = None,
    ):
        super().__init__(client=client, gui_id=gui_id)
        CompactPopupWidget.__init__(self, parent=parent, layout=QHBoxLayout)

        self.box_name = box_name
        self.status_container = defaultdict(lambda: {"info": None, "item": None, "widget": None})

        if not bec_service_status_mixin:
            bec_service_status_mixin = BECServiceStatusMixin(self, client=self.client)
        self.bec_service_status = bec_service_status_mixin

        self.label = box_name
        self.tooltip = "BEC servers health status"
        self.init_ui()
        self.bec_service_status.services_update.connect(self.update_service_status)
        self.bec_core_state.connect(self.update_top_item_status)
        self.tree.itemDoubleClicked.connect(self.on_tree_item_double_clicked)
        self.addWidget(self.tree)

    def init_ui(self) -> None:
        """Init the UI for the BECStatusBox widget, should only take place once."""
        self.init_ui_tree_widget()
        top_label = self._create_status_widget(self.box_name, status=BECStatus.IDLE)
        tree_item = QTreeWidgetItem()
        tree_item.setExpanded(True)
        tree_item.setDisabled(True)
        self.status_container[self.box_name].update({"item": tree_item, "widget": top_label})
        self.tree.addTopLevelItem(tree_item)
        self.tree.setItemWidget(tree_item, 0, top_label)
        self.service_update.connect(top_label.update_config)
        self._initialized = True

    def init_ui_tree_widget(self) -> None:
        """Initialise the tree widget for the status box."""
        self.tree = QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        # TODO probably here is a problem still with setting the stylesheet
        # self.tree.setStyleSheet(
        #     "QTreeWidget::item:!selected "
        #     "{ "
        #     "border: 1px solid gainsboro; "
        #     "border-left: none; "
        #     "border-top: none; "
        #     "}"
        #     "QTreeWidget::item:selected {}"
        # )
        self.tree.setStyleSheet(
            "QTreeWidget::item:!selected { "
            "border: 1px solid gainsboro; "
            "border-left: none; "
            "border-top: none; "
            "} "
            "QTreeWidget::item:selected {} "
            "QTreeView::branch { "
            "border-image: none; "
            "background: transparent; "
            "} "
            "QTreeView::branch:has-siblings:!adjoins-item { "
            "border-image: none; "
            "} "
            "QTreeView::branch:has-children:!has-siblings:closed, "
            "QTreeView::branch:closed:has-children:has-siblings { "
            "border-image: none; "
            "} "
            "QTreeView::branch:open:has-children:!has-siblings, "
            "QTreeView::branch:open:has-children:has-siblings { "
            "border-image: none; "
            "}"
        )

        # self.tree.setRootIsDecorated(False)

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
        item = StatusItem(parent=self, config=self.status_container[service_name]["info"])
        return item

    @Slot(str)
    def update_top_item_status(self, status: BECStatus) -> None:
        """Method to update the status of the top item in the tree widget.
        Gets the status from the Signal 'bec_core_state' and updates the StatusItem via the signal 'service_update'.

        Args:
            status (BECStatus): The state of the core services.
        """
        self.status_container[self.box_name]["info"].status = status
        self.set_global_state("emergency" if status == "NOTCONNECTED" else "success")
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
            service_name=service_name,
            status=status.name if isinstance(status, BECStatus) else status,
            info=info,
            metrics=metrics,
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
            if service_name in self.status_container:
                if not msg:
                    self.add_tree_item(service_name, "NOTCONNECTED", {}, metrics)
                    continue
                self._update_status_container(service_name, msg.status, msg.info, metrics)
                self.service_update.emit(self.status_container[service_name]["info"])
                continue

            self.add_tree_item(service_name, msg.status, msg.info, metrics)
        self.check_redundant_tree_items(checked)

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
            if service_name not in self.status_container:
                if not msg:
                    self.add_tree_item(service_name, "NOTCONNECTED", {}, metrics)
                    continue
                self.add_tree_item(service_name, msg.status, msg.info, metrics)
                continue
            if not msg:
                self.status_container[service_name]["info"].status = "NOTCONNECTED"
                core_state = None
            else:
                self._update_status_container(service_name, msg.status, msg.info, metrics)
                if core_state:
                    core_state = msg.status if msg.status.value < core_state.value else core_state

            self.service_update.emit(self.status_container[service_name]["info"])

        self.bec_core_state.emit(core_state.name if core_state else "NOTCONNECTED")
        return services_info

    def check_redundant_tree_items(self, checked: list) -> None:
        """Utility method to check and remove redundant objects from the BECStatusBox.

        Args:
            checked (list): A list of services that are currently running.
        """
        to_be_deleted = [key for key in self.status_container if key not in checked]

        for key in to_be_deleted:
            obj = self.status_container.pop(key)
            item = obj["item"]
            self.status_container[self.box_name]["item"].removeChild(item)

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
        item = QTreeWidgetItem()
        self.service_update.connect(item_widget.update_config)
        self.status_container[self.box_name]["item"].addChild(item)
        self.tree.setItemWidget(item, 0, item_widget)
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

    def cleanup(self):
        """Cleanup the BECStatusBox widget."""
        self.bec_service_status.cleanup()
        return super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import set_theme

    app = QApplication(sys.argv)
    set_theme("dark")
    main_window = BECStatusBox()
    main_window.show()
    sys.exit(app.exec())
