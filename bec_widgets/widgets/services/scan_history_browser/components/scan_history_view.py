from __future__ import annotations

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import ScanHistoryMessage
from qtpy import QtCore, QtGui, QtWidgets

from bec_widgets.utils.bec_widget import BECWidget, ConnectionConfig
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

logger = bec_logger.logger


class ScanHistoryView(BECWidget, QtWidgets.QTreeWidget):
    """ScanHistoryTree is a widget that displays the scan history in a tree format."""

    RPC = False
    PLUGIN = False

    scan_selected = QtCore.Signal(object)
    scan_removed = QtCore.Signal(object)

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
        self._set_policies()
        self.apply_theme()
        self._start_subscription()
        self.itemClicked.connect(self._on_item_clicked)
        self.currentItemChanged.connect(self._current_item_changed)

    def _set_policies(self):
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
        Emits a signal with the selected scan message when the current item changes.
        """
        if not current:
            return
        self._on_item_clicked(current, self.currentColumn())

    def _on_item_clicked(self, item: QtWidgets.QTreeWidgetItem, column: int):
        """
        Handle item click events in the tree widget.
        Emits a signal with the selected scan message when an item is clicked.
        """
        if not item:
            return
        index = self.indexOfTopLevelItem(item)
        self.scan_selected.emit(self.scan_history[index])

    def _start_subscription(self):
        """
        Subscribe to scan history updates.
        """
        self.bec_dispatcher.connect_slot(
            slot=self.update_history, topics=MessageEndpoints.scan_history(), from_start=True
        )

    @SafeSlot()
    def update_history(self, msg_content: dict, metdata: dict):
        """
        This method is called whenever a new scan history is available.
        """
        # TODO directly receive ScanHistoryMessage through dispatcher
        msg = ScanHistoryMessage(**msg_content)
        msg.metadata = metdata
        self.add_scan(msg)
        self.ensure_history_max_length()

    def ensure_history_max_length(self) -> None:
        """
        Clean up the scan history by clearing the list.
        This method can be called when the widget is closed or no longer needed.
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
        Remove a scan entry from the tree widget. We supoprt negative indexing where -1, -2, etc. refer to the last, second last, etc. entry.
        Args:
            index (int): The index of the scan entry to remove.
        """
        if index < 0:
            index = len(self.scan_history) + index
        try:
            msg = self.scan_history.pop(index)
            self.scan_removed.emit(msg)
        except IndexError:
            logger.warning(f"Invalid index {index} for removing scan entry from history.")
            return
        self.takeTopLevelItem(index)


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
    browser.scan_removed.connect(view.clear_view)
    browser.scan_removed.connect(device_viewer.clear_view)

    main_window.show()
    app.exec_()
