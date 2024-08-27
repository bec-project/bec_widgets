from qtpy.QtWidgets import QPushButton

from bec_widgets.qt_utils.error_popups import SafeSlot as Slot
from bec_widgets.utils.bec_widget import BECWidget


class StopButton(BECWidget, QPushButton):
    """A button that stops the current scan."""

    ICON_NAME = "dangerous"

    def __init__(self, parent=None, client=None, config=None, gui_id=None):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QPushButton.__init__(self, parent=parent)

        self.get_bec_shortcuts()
        self.setText("Stop")
        self.setStyleSheet(
            "background-color:  #cc181e; color: white; font-weight: bold; font-size: 12px;"
        )
        self.clicked.connect(self.stop_scan)

    @Slot()
    def stop_scan(self):
        """Stop the scan."""
        self.queue.request_scan_abortion()
        self.queue.request_queue_reset()
