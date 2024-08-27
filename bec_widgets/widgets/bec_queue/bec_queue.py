from __future__ import annotations

from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import Qt, Slot
from qtpy.QtWidgets import QHBoxLayout, QHeaderView, QTableWidget, QTableWidgetItem, QWidget

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget


class BECQueue(BECWidget, QWidget):
    """
    Widget to display the BEC queue.
    """

    ICON_NAME = "edit_note"

    def __init__(
        self,
        parent: QWidget | None = None,
        client=None,
        config: ConnectionConfig = None,
        gui_id: str = None,
    ):
        super().__init__(client, config, gui_id)
        QWidget.__init__(self, parent=parent)
        self.table = QTableWidget(self)
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.table)

        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Scan Number", "Type", "Status"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.bec_dispatcher.connect_slot(self.update_queue, MessageEndpoints.scan_queue_status())
        self.reset_content()

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
            status = item.get("status", "")
            for request_block in blocks:
                scan_type = request_block.get("content", {}).get("scan_type", "")
                if scan_type:
                    scan_types.append(scan_type)
                scan_number = request_block.get("scan_number", "")
                if scan_number:
                    scan_numbers.append(str(scan_number))
            if scan_types:
                scan_types = ", ".join(scan_types)
            if scan_numbers:
                scan_numbers = ", ".join(scan_numbers)
            self.set_row(index, scan_numbers, scan_types, status)

    def format_item(self, content: str) -> QTableWidgetItem:
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
        return item

    def set_row(self, index: int, scan_number: str, scan_type: str, status: str):
        """
        Set the row of the table.

        Args:
            index (int): The index of the row.
            scan_number (str): The scan number.
            scan_type (str): The scan type.
            status (str): The status.
        """

        self.table.setItem(index, 0, self.format_item(scan_number))
        self.table.setItem(index, 1, self.format_item(scan_type))
        self.table.setItem(index, 2, self.format_item(status))

    def reset_content(self):
        """
        Reset the content of the table.
        """

        self.table.setRowCount(1)
        self.set_row(0, "", "", "")


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = BECQueue()
    widget.show()
    sys.exit(app.exec_())
