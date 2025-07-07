from qtpy import QtCore, QtWidgets

from bec_widgets.utils.bec_widget import BECWidget, ConnectionConfig
from bec_widgets.widgets.services.scan_history_browser.components import (
    ScanHistoryDeviceViewer,
    ScanHistoryMetadataViewer,
    ScanHistoryView,
)


class ScanHistoryBrowser(BECWidget, QtWidgets.QWidget):

    RPC = False
    PLUGIN = False

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        client=None,
        config: ConnectionConfig = None,
        gui_id: str | None = None,
        theme_update: bool = False,
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
        layout = QtWidgets.QHBoxLayout()

        self.setLayout(layout)
        self.scan_history_view = ScanHistoryView(
            parent=self, client=client, config=config, gui_id=gui_id, theme_update=theme_update
        )
        self.scan_history_metadata_viewer = ScanHistoryMetadataViewer(
            parent=self, client=client, config=config, gui_id=gui_id, theme_update=theme_update
        )
        self.scan_history_device_viewer = ScanHistoryDeviceViewer(
            parent=self, client=client, config=config, gui_id=gui_id, theme_update=theme_update
        )

        self.init_layout()
        self.connect_signals()
        QtCore.QTimer.singleShot(0, self.select_first_history_entry)

    def init_layout(self):
        """Initialize the layout of the widget."""
        # Add Scan history view
        layout: QtWidgets.QHBoxLayout = self.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.scan_history_view)
        # Add metadata and device viewers in a vertical layout
        widget = QtWidgets.QWidget(self)
        vertical_layout = QtWidgets.QVBoxLayout()
        vertical_layout.setContentsMargins(0, 0, 0, 0)
        vertical_layout.setSpacing(0)
        vertical_layout.addWidget(self.scan_history_metadata_viewer)
        vertical_layout.addWidget(self.scan_history_device_viewer)
        widget.setLayout(vertical_layout)
        # Add the vertical layout widget to the main layout
        layout.addWidget(widget)

    def connect_signals(self):
        """Connect signals to the appropriate slots."""
        self.scan_history_view.scan_selected.connect(self.scan_history_metadata_viewer.update_view)
        self.scan_history_view.scan_selected.connect(
            self.scan_history_device_viewer.update_devices_from_scan_history
        )
        self.scan_history_view.scan_removed.connect(self.scan_history_metadata_viewer.clear_view)
        self.scan_history_view.scan_removed.connect(self.scan_history_device_viewer.clear_view)

    def select_first_history_entry(self):
        """Select the first entry in the scan history view."""
        if self.scan_history_view.topLevelItemCount() > 0:
            self.scan_history_view.setCurrentItem(self.scan_history_view.topLevelItem(0))
            self.scan_history_view.itemActivated.emit(self.scan_history_view.topLevelItem(0), 0)


if __name__ == "__main__":  # pragma: no cover
    # pylint: disable=import-outside-toplevel

    from qtpy.QtWidgets import QApplication

    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    app = QApplication([])
    main_window = QtWidgets.QMainWindow()

    central_widget = QtWidgets.QWidget()
    button = DarkModeButton()
    layout = QtWidgets.QVBoxLayout(central_widget)
    main_window.setCentralWidget(central_widget)
    # Create a ScanHistoryBrowser instance
    browser = ScanHistoryBrowser()  # type: ignore
    layout.addWidget(button)
    layout.addWidget(browser)
    main_window.setWindowTitle("Scan History Browser")
    main_window.resize(800, 600)
    main_window.show()
    app.exec_()
