from __future__ import annotations

from typing import TYPE_CHECKING

from bec_lib.callback_handler import EventType
from bec_lib.logger import bec_logger
from bec_lib.messages import ScanHistoryMessage
from qtpy import QtCore, QtGui, QtWidgets

from bec_widgets.utils.bec_widget import BECWidget, ConnectionConfig
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot

if TYPE_CHECKING:
    from bec_lib.client import BECClient


logger = bec_logger.logger


class BECHistoryManager(QtCore.QObject):
    """History manager for scan history operations. This class
    is responsible for emitting signals when the scan history is updated.
    """

    # ScanHistoryMessage.model_dump() (dict)
    scan_history_updated = QtCore.Signal(dict)

    def __init__(self, parent, client: BECClient):
        super().__init__(parent)
        self.client = client
        self._cb_id = self.client.callbacks.register(
            event_type=EventType.SCAN_HISTORY_UPDATE, callback=self._on_scan_history_update
        )

    def refresh_scan_history(self) -> None:
        """Refresh the scan history from the client."""
        for scan_id in self.client.history._scan_ids:  # pylint: disable=protected-access
            history_msg = self.client.history._scan_data.get(scan_id, None)
            if history_msg is None:
                logger.info(f"Scan history message for scan_id {scan_id} not found.")
                continue
            self.scan_history_updated.emit(history_msg.model_dump())

    def _on_scan_history_update(self, history_msg: ScanHistoryMessage) -> None:
        """Handle scan history updates from the client."""
        self.scan_history_updated.emit(history_msg.model_dump())

    def cleanup(self) -> None:
        """Clean up the manager by disconnecting callbacks."""
        self.client.callbacks.remove(self._cb_id)
        self.scan_history_updated.disconnect()


class ScanHistoryView(BECWidget, QtWidgets.QTreeWidget):
    """ScanHistoryTree is a widget that displays the scan history in a tree format."""

    RPC = False
    PLUGIN = False

    # ScanHistoryMessage.content, ScanHistoryMessage.metadata
    scan_selected = QtCore.Signal(dict, dict)
    no_scan_selected = QtCore.Signal()

    def __init__(
        self,
        parent: QtWidgets.QWidget = None,
        client=None,
        config: ConnectionConfig = None,
        gui_id: str = None,
        max_length: int = 100,
        theme_update: bool = True,
        **kwargs,
    ):
        super().__init__(
            parent=parent,
            client=client,
            config=config,
            gui_id=gui_id,
            theme_update=theme_update,
            **kwargs,
        )
        colors = get_accent_colors()
        self.status_colors = {
            "closed": colors.success,
            "halted": colors.warning,
            "aborted": colors.emergency,
        }
        # self.status_colors = {"closed": "#00e676", "halted": "#ffca28", "aborted": "#ff5252"}
        self.column_header = ["Scan Nr", "Scan Name", "Status"]
        self.scan_history: list[ScanHistoryMessage] = []  # newest at index 0
        self.max_length = max_length  # Maximum number of scan history entries to keep
        self.bec_scan_history_manager = BECHistoryManager(parent=self, client=self.client)
        self._set_policies()
        self.apply_theme()
        self.currentItemChanged.connect(self._current_item_changed)
        header = self.header()
        header.setToolTip(f"Last {self.max_length} scans in history.")
        self.bec_scan_history_manager.scan_history_updated.connect(self.update_history)
        self.refresh()

    def _set_policies(self):
        """Set the policies for the tree widget."""
        self.setColumnCount(len(self.column_header))
        self.setHeaderLabels(self.column_header)
        self.setRootIsDecorated(False)  # allow expand arrow for per‑scan details
        self.setUniformRowHeights(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setIndentation(12)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setAnimated(True)

        header = self.header()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        for column in range(1, self.columnCount()):
            header.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.Stretch)

    def apply_theme(self, theme: str | None = None):
        """Apply the theme to the widget."""
        colors = get_accent_colors()
        self.status_colors = {
            "closed": colors.success,
            "halted": colors.warning,
            "aborted": colors.emergency,
        }
        self.repaint()

    def _current_item_changed(
        self, current: QtWidgets.QTreeWidgetItem, previous: QtWidgets.QTreeWidgetItem
    ):
        """
        Handle current item change events in the tree widget.

        Args:
            current (QtWidgets.QTreeWidgetItem): The currently selected item.
            previous (QtWidgets.QTreeWidgetItem): The previously selected item.
        """
        if not current:
            return
        index = self.indexOfTopLevelItem(current)
        self.scan_selected.emit(self.scan_history[index].content, self.scan_history[index].metadata)

    @SafeSlot()
    def refresh(self):
        """Refresh the scan history view."""
        while len(self.scan_history) > 0:
            self.remove_scan(index=0)
        self.bec_scan_history_manager.refresh_scan_history()

    @SafeSlot(dict)
    def update_history(self, msg_dump: dict):
        """Update the scan history with new scan data."""
        msg = ScanHistoryMessage(**msg_dump)
        self.add_scan(msg)
        self.ensure_history_max_length()

    def ensure_history_max_length(self) -> None:
        """
        Method to ensure the scan history does not exceed the maximum length.
        If the length exceeds the maximum, it removes the oldest entry.
        This is called after adding a new scan to the history.
        """
        while len(self.scan_history) > self.max_length:
            logger.warning(
                f"Removing oldest scan history entry to maintain max length of {self.max_length}."
            )
            self.remove_scan(index=-1)

    def add_scan(self, msg: ScanHistoryMessage):
        """
        Add a scan entry to the tree widget.

        Args:
            msg (ScanHistoryMessage): The scan history message containing scan details.
        """
        if msg.stored_data_info is None:
            logger.info(
                f"Old scan history entry fo scan {msg.scan_id} without stored_data_info, skipping."
            )
            return
        if msg in self.scan_history:
            logger.info(f"Scan {msg.scan_id} already in history, skipping.")
            return
        self.scan_history.insert(0, msg)
        tree_item = QtWidgets.QTreeWidgetItem([str(msg.scan_number), msg.scan_name, ""])
        color = QtGui.QColor(self.status_colors.get(msg.exit_status, "#b0bec5"))
        pix = QtGui.QPixmap(10, 10)
        pix.fill(QtCore.Qt.transparent)
        with QtGui.QPainter(pix) as p:
            p.setRenderHint(QtGui.QPainter.Antialiasing)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(color)
            p.drawEllipse(0, 0, 10, 10)
        tree_item.setIcon(2, QtGui.QIcon(pix))
        tree_item.setForeground(2, QtGui.QBrush(color))
        for col in range(tree_item.columnCount()):
            tree_item.setToolTip(col, f"Status: {msg.exit_status}")
        self.insertTopLevelItem(0, tree_item)
        tree_item.setExpanded(False)

    def remove_scan(self, index: int):
        """
        Remove a scan entry from the tree widget.
        We supoprt negative indexing where -1, -2, etc.

        Args:
            index (int): The index of the scan entry to remove.
        """
        if index < 0:
            index = len(self.scan_history) + index
        try:
            msg = self.scan_history.pop(index)
            self.no_scan_selected.emit()
        except IndexError:
            logger.warning(f"Invalid index {index} for removing scan entry from history.")
            return
        self.takeTopLevelItem(index)

    def cleanup(self):
        """Cleanup the widget"""
        self.bec_scan_history_manager.cleanup()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    # pylint: disable=import-outside-toplevel

    from bec_widgets.widgets.services.scan_history_browser.components import (
        ScanHistoryDeviceViewer,
        ScanHistoryMetadataViewer,
    )
    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    app = QtWidgets.QApplication([])

    main_window = QtWidgets.QMainWindow()
    central_widget = QtWidgets.QWidget()
    button = DarkModeButton()
    layout = QtWidgets.QVBoxLayout(central_widget)
    main_window.setCentralWidget(central_widget)

    # Create a ScanHistoryBrowser instance
    browser = ScanHistoryView()

    # Create a ScanHistoryView instance
    view = ScanHistoryMetadataViewer()
    device_viewer = ScanHistoryDeviceViewer()

    layout.addWidget(button)
    layout.addWidget(browser)
    layout.addWidget(view)
    layout.addWidget(device_viewer)
    browser.scan_selected.connect(view.update_view)
    browser.scan_selected.connect(device_viewer.update_devices_from_scan_history)
    browser.no_scan_selected.connect(view.clear_view)
    browser.no_scan_selected.connect(device_viewer.clear_view)

    main_window.show()
    app.exec_()
