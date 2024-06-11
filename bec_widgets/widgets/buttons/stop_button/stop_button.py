from qtpy.QtWidgets import QPushButton

from bec_widgets.utils import BECConnector


class StopButton(BECConnector, QPushButton):
    """A button that stops the current scan."""

    def __init__(self, parent=None, client=None, config=None, gui_id=None):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QPushButton.__init__(self, parent=parent)

        self.get_bec_shortcuts()
        self.setText("Stop")
        self.setStyleSheet("background-color:  #cc181e; color: white")
        self.clicked.connect(self.stop_scan)

    def stop_scan(self):
        """Stop the scan."""
        self.queue.request_scan_abortion()
        self.queue.request_queue_reset()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = StopButton()
    widget.show()
    sys.exit(app.exec_())
