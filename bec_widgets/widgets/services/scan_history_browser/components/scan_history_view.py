from __future__ import annotations

from typing import TYPE_CHECKING

from bec_lib.callback_handler import EventType
from bec_lib.logger import bec_logger
from bec_lib.messages import ScanHistoryMessage
from bec_qthemes import material_icon
from qtpy import QtCore, QtGui, QtWidgets

from bec_widgets.utils.bec_widget import BECWidget, ConnectionConfig
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.utility.spinner.spinner import SpinnerWidget

if TYPE_CHECKING:
    from bec_lib.client import BECClient


logger = bec_logger.logger


class BECHistoryManager(QtCore.QObject):
    """History manager for scan history operations. This class
    is responsible for emitting signals when the scan history is updated.
    """

    # ScanHistoryMessage.model_dump() (dict)
    scan_history_updated = QtCore.Signal(dict)
    scan_history_refreshed = QtCore.Signal(list)

    def __init__(self, parent, client: BECClient):
        super().__init__(parent)
        self._load_attempt = 0
        self.client = client
        self._cb_id: dict[str, int] = {}
        self._cb_id["update_scan_history"] = self.client.callbacks.register(
            EventType.SCAN_HISTORY_UPDATE, self._on_scan_history_update
        )
        self._cb_id["scan_history_loaded"] = self.client.callbacks.register(
            EventType.SCAN_HISTORY_LOADED, self._on_scan_history_reloaded
        )

    def refresh_scan_history(self) -> None:
        """Refresh the scan history from the client."""
        all_messages = []
        # pylint: disable=protected-access
        for scan_id in self.client.history._scan_ids:  # pylint: disable=protected-access
            history_msg = self.client.history._scan_data.get(scan_id, None)
            if history_msg is None:
                logger.info(f"Scan history message for scan_id {scan_id} not found.")
                continue
            all_messages.append(history_msg.model_dump())
        self.scan_history_refreshed.emit(all_messages)

    def _on_scan_history_reloaded(self, history_msgs: list[ScanHistoryMessage]) -> None:
        """Handle scan history reloaded event from the client."""
        if not history_msgs:
            logger.warning("Scan history reloaded with no messages.")
            return
        self.scan_history_refreshed.emit([msg.model_dump() for msg in history_msgs])

    def _on_scan_history_update(self, history_msg: ScanHistoryMessage) -> None:
        """Handle scan history updates from the client."""
        self.scan_history_updated.emit(history_msg.model_dump())

    def cleanup(self) -> None:
        """Clean up the manager by disconnecting callbacks."""
        for cb_id in self._cb_id.values():
            self.client.callbacks.remove(cb_id)
        self.scan_history_updated.disconnect()
        self.scan_history_refreshed.disconnect()


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
        self.status_icons = self._create_status_icons()
        self.column_header = ["Scan Nr", "Scan Name", "Status"]
        self.scan_history: list[ScanHistoryMessage] = []  # newest at index 0
        self.scan_history_ids: set[str] = set()  # scan IDs of the scan history
        self.max_length = max_length  # Maximum number of scan history entries to keep
        self.bec_scan_history_manager = BECHistoryManager(parent=self, client=self.client)
        self._set_policies()
        self.apply_theme()
        self.currentItemChanged.connect(self._current_item_changed)
        header = self.header()
        header.setToolTip(f"Last {self.max_length} scans in history.")
        self.bec_scan_history_manager.scan_history_updated.connect(self.update_history)
        self.bec_scan_history_manager.scan_history_refreshed.connect(self.update_full_history)
        self._container = QtWidgets.QStackedLayout()
        self._container.setStackingMode(QtWidgets.QStackedLayout.StackAll)
        self.setLayout(self._container)
        self._add_overlay()
        self._start_waiting_display()
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

    def _create_status_icons(self) -> dict[str, QtGui.QIcon]:
        """Create status icons for the scan history."""
        colors = get_accent_colors()
        return {
            "closed": material_icon(
                icon_name="fiber_manual_record", filled=True, color=colors.success
            ),
            "halted": material_icon(
                icon_name="fiber_manual_record", filled=True, color=colors.warning
            ),
            "aborted": material_icon(
                icon_name="fiber_manual_record", filled=True, color=colors.emergency
            ),
            "unknown": material_icon(
                icon_name="fiber_manual_record", filled=True, color=QtGui.QColor("#b0bec5")
            ),
        }

    def apply_theme(self, theme: str | None = None):
        """Apply the theme to the widget."""
        self.status_icons = self._create_status_icons()
        self.repaint()

    def _add_overlay(self):
        self._overlay_widget = QtWidgets.QWidget()
        self._overlay_widget.setStyleSheet("background-color: rgba(240, 240, 240, 180);")
        self._overlay_widget.setAutoFillBackground(True)
        self._overlay_layout = QtWidgets.QVBoxLayout()
        self._overlay_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._overlay_widget.setLayout(self._overlay_layout)

        self._spinner = SpinnerWidget(parent=self)
        self._spinner.setFixedSize(QtCore.QSize(32, 32))
        self._overlay_layout.addWidget(self._spinner)
        self._container.addWidget(self._overlay_widget)

    def _start_waiting_display(self):
        self._overlay_widget.setVisible(True)
        self._spinner.start()
        QtWidgets.QApplication.processEvents()

    def _stop_waiting_display(self):
        self._overlay_widget.setVisible(False)
        self._spinner.stop()
        QtWidgets.QApplication.processEvents()

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
        # pylint: disable=protected-access
        if self.client.history._scan_history_loaded_event.is_set():
            while len(self.scan_history) > 0:
                self.remove_scan(index=0)
            self.bec_scan_history_manager.refresh_scan_history()
            return
        else:
            logger.info("Scan history not loaded yet, waiting for it to be loaded.")

    @SafeSlot(dict)
    def update_history(self, msg_dump: dict):
        """Update the scan history with new scan data."""
        msg = ScanHistoryMessage(**msg_dump)
        self.add_scan(msg)
        self.ensure_history_max_length()

    @SafeSlot(list)
    def update_full_history(self, all_messages: list[dict]):
        """Update the scan history with a full list of scan data."""
        messages = []
        for msg_dump in all_messages:
            msg = ScanHistoryMessage(**msg_dump)
            messages.append(msg)
            if len(messages) >= self.max_length:
                messages.pop(0)
        messages.sort(key=lambda m: m.scan_number, reverse=False)
        self.add_scans(messages)
        self.ensure_history_max_length()
        self._stop_waiting_display()

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
        self._add_scan_to_scan_history(msg)
        tree_item = self._setup_tree_item(msg)
        self.insertTopLevelItem(0, tree_item)

    def _setup_tree_item(self, msg: ScanHistoryMessage) -> QtWidgets.QTreeWidgetItem:
        """Setup a tree item for the scan history message.

        Args:
            msg (ScanHistoryMessage): The scan history message containing scan details.

        Returns:
            QtWidgets.QTreeWidgetItem: The tree item representing the scan history message.
        """
        tree_item = QtWidgets.QTreeWidgetItem([str(msg.scan_number), msg.scan_name, ""])
        icon = self.status_icons.get(msg.exit_status, self.status_icons["unknown"])
        tree_item.setIcon(2, icon)
        tree_item.setExpanded(False)
        for col in range(tree_item.columnCount()):
            tree_item.setToolTip(col, f"Status: {msg.exit_status}")
        return tree_item

    def _add_scan_to_scan_history(self, msg: ScanHistoryMessage):
        """
        Add a scan message to the internal scan history list and update the tree widget.

        Args:
            msg (ScanHistoryMessage): The scan history message containing scan details.
        """
        if msg.stored_data_info is None:
            logger.info(
                f"Old scan history entry fo scan {msg.scan_id} without stored_data_info, skipping."
            )
            return
        if msg.scan_id in self.scan_history_ids:
            logger.info(f"Scan {msg.scan_id} already in history, skipping.")
            return
        self.scan_history.insert(0, msg)
        self.scan_history_ids.add(msg.scan_id)

    def add_scans(self, messages: list[ScanHistoryMessage]):
        """
        Add multiple scan entries to the tree widget.

        Args:
            messages (list[ScanHistoryMessage]): List of scan history messages containing scan details.
        """
        tree_items = []
        for msg in messages:
            self._add_scan_to_scan_history(msg)
            tree_items.append(self._setup_tree_item(msg))
        # Insert for insertTopLevelItems needs to reversed to keep order of scan_history list
        self.insertTopLevelItems(0, tree_items[::-1])

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
            self.scan_history_ids.remove(msg.scan_id)
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
