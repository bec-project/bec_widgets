from __future__ import annotations

from bec_lib.endpoints import MessageEndpoints
from bec_qthemes import material_icon
from qtpy.QtCore import Property, Qt, Signal, Slot
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.compact_popup import CompactPopupWidget
from bec_widgets.utils.toolbar import ModularToolBar, SeparatorAction, WidgetAction
from bec_widgets.widgets.control.buttons.button_abort.button_abort import AbortButton
from bec_widgets.widgets.control.buttons.button_reset.button_reset import ResetButton
from bec_widgets.widgets.control.buttons.button_resume.button_resume import ResumeButton
from bec_widgets.widgets.control.buttons.stop_button.stop_button import StopButton


class BECQueue(BECWidget, CompactPopupWidget):
    """
    Widget to display the BEC queue.
    """

    PLUGIN = True
    ICON_NAME = "edit_note"
    status_colors = {
        "STOPPED": "red",
        "PENDING": "orange",
        "IDLE": "gray",
        "PAUSED": "yellow",
        "DEFERRED_PAUSE": "lightyellow",
        "RUNNING": "green",
        "COMPLETED": "blue",
    }

    queue_busy = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        client=None,
        config: ConnectionConfig = None,
        gui_id: str = None,
        refresh_upon_start: bool = True,
        **kwargs,
    ):
        CompactPopupWidget.__init__(self, parent=parent, layout=QVBoxLayout)
        BECWidget.__init__(self, client=client, config=config, gui_id=gui_id, **kwargs)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Set up the toolbar
        self.set_toolbar()
        # Set up the table
        self.table = QTableWidget(self)
        # self.layout.addWidget(self.table)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Scan Number", "Type", "Status", "Cancel"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        self.addWidget(self.table)
        self.label = "BEC Queue"
        self.tooltip = "BEC Queue status"

        self.bec_dispatcher.connect_slot(self.update_queue, MessageEndpoints.scan_queue_status())
        self.reset_content()
        if refresh_upon_start:
            self.refresh_queue()

    def set_toolbar(self):
        """
        Set the toolbar.
        """
        widget_label = QLabel("Live Queue")
        widget_label.setStyleSheet("font-weight: bold;")
        self.toolbar = ModularToolBar(
            actions={
                "widget_label": WidgetAction(widget=widget_label),
                "separator_1": SeparatorAction(),
                "resume": WidgetAction(widget=ResumeButton(toolbar=False)),
                "stop": WidgetAction(widget=StopButton(toolbar=False)),
                "reset": WidgetAction(widget=ResetButton(toolbar=False)),
            },
            target_widget=self,
        )

        self.addWidget(self.toolbar)

    @Property(bool)
    def hide_toolbar(self):
        """Property to hide the BEC Queue toolbar."""
        return not self.toolbar.isVisible()

    @hide_toolbar.setter
    def hide_toolbar(self, hide: bool):
        """
        Setters for the hide_toolbar property.

        Args:
            hide(bool): Whether to hide the toolbar.
        """
        self._hide_toolbar(hide)

    def _hide_toolbar(self, hide: bool):
        """
        Hide the toolbar.

        Args:
            hide(bool): Whether to hide the toolbar.
        """
        self.toolbar.setVisible(not hide)

    def refresh_queue(self):
        """
        Refresh the queue.
        """
        msg = self.client.connector.get(MessageEndpoints.scan_queue_status())
        if msg is None:
            # msg is None if no scan has been run yet (fresh start)
            return
        self.update_queue(msg.content, msg.metadata)

    @Slot(dict, dict)
    def update_queue(self, content, _metadata):
        """
        Update the queue table with the latest queue information.

        Args:
            content (dict): The queue content.
            _metadata (dict): The metadata.
        """
        # only show the primary queue for now
        queue_info = content.get("queue", {}).get("primary", {}).get("info", [])
        self.table.setRowCount(len(queue_info))
        self.table.clearContents()

        if not queue_info:
            self.reset_content()
            return

        for index, item in enumerate(queue_info):
            blocks = item.get("request_blocks", [])
            scan_types = []
            scan_numbers = []
            scan_ids = []
            status = item.get("status", "")
            for request_block in blocks:
                scan_type = request_block.get("content", {}).get("scan_type", "")
                if scan_type:
                    scan_types.append(scan_type)
                scan_number = request_block.get("scan_number", "")
                if scan_number:
                    scan_numbers.append(str(scan_number))
                scan_id = request_block.get("scan_id", "")
                if scan_id:
                    scan_ids.append(scan_id)
            if scan_types:
                scan_types = ", ".join(scan_types)
            if scan_numbers:
                scan_numbers = ", ".join(scan_numbers)
            if scan_ids:
                scan_ids = ", ".join(scan_ids)
            self.set_row(index, scan_numbers, scan_types, status, scan_ids)
        busy = (
            False
            if all(item.get("status") in ("STOPPED", "COMPLETED", "IDLE") for item in queue_info)
            else True
        )
        self.set_global_state("warning" if busy else "default")
        self.queue_busy.emit(busy)

    def format_item(self, content: str, status=False) -> QTableWidgetItem:
        """
        Format the content of the table item.

        Args:
            content (str): The content to be formatted.

        Returns:
            QTableWidgetItem: The formatted item.
        """
        if not content or not isinstance(content, str):
            content = ""
        item = QTableWidgetItem(content)
        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        # item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        if status:
            try:
                color = self.status_colors.get(content, "black")  # Default to black if not found
                item.setForeground(QColor(color))
            except:
                return item
        return item

    def set_row(self, index: int, scan_number: str, scan_type: str, status: str, scan_id: str):
        """
        Set the row of the table.

        Args:
            index (int): The index of the row.
            scan_number (str): The scan number.
            scan_type (str): The scan type.
            status (str): The status.
        """
        abort_button = self._create_abort_button(scan_id)
        abort_button.button.clicked.connect(self.delete_selected_row)

        self.table.setItem(index, 0, self.format_item(scan_number))
        self.table.setItem(index, 1, self.format_item(scan_type))
        self.table.setItem(index, 2, self.format_item(status, status=True))
        self.table.setCellWidget(index, 3, abort_button)

    def _create_abort_button(self, scan_id: str) -> AbortButton:
        """
        Create an abort button with styling for BEC Queue widget for certain scan_id.

        Args:
            scan_id(str): The scan id to abort.

        Returns:
            AbortButton: The abort button.
        """
        abort_button = AbortButton(scan_id=scan_id)

        abort_button.button.setText("")
        abort_button.button.setIcon(
            material_icon("cancel", color="#cc181e", filled=True, convert_to_pixmap=False)
        )
        abort_button.button.setStyleSheet("background-color:  rgba(0,0,0,0) ")
        abort_button.button.setFlat(True)

        return abort_button

    def delete_selected_row(self):

        button = self.sender()
        row = self.table.indexAt(button.pos()).row()
        self.table.removeRow(row)

        button.deleteLater()

    def reset_content(self):
        """
        Reset the content of the table.
        """

        self.table.setRowCount(1)
        self.set_row(0, "", "", "", "")


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = BECQueue()
    widget.show()
    sys.exit(app.exec_())
