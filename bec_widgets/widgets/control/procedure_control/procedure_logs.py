from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_server.scan_server.procedures.helper import FrontendProcedureHelper
from PySide6.QtWidgets import QLabel
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QSizePolicy, QTextEdit, QVBoxLayout, QWidget

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot

logger = bec_logger.logger


class ProcedureLogs(BECWidget, QWidget):

    def __init__(self, parent=None, client=None, config=None, gui_id: str | None = None, **kwargs):
        config = config or ConnectionConfig()
        super().__init__(parent=parent, client=client, config=config, gui_id=gui_id, **kwargs)
        self._conn = self.bec_dispatcher.client.connector
        self._queue: str | None = None
        self._setup_ui()

    def _setup_ui(self):
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self.widget = QTextEdit(lineWrapMode=QTextEdit.LineWrapMode.NoWrap, readOnly=True)
        font = QFont("Courier New")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.widget.setFont(font)
        self.widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(self.widget)

    @SafeSlot(dict, dict)
    def _trigger_update(self, msg, _):
        self.widget.append(msg.get("data").strip())

    def _update(self):
        if self._queue is None:
            self.widget.setText("")
            return
        if msgs := self._conn.xread(MessageEndpoints.procedure_logs(self._queue)):
            self.widget.append("".join(msg.get("data").data.strip() for msg in msgs))

    @SafeSlot(None)
    @SafeSlot(str)
    def set_queue(self, queue: str | None):
        self.queue = queue

    @SafeProperty(str)
    def queue(self) -> str | None:
        return self._queue

    @queue.setter
    def queue(self, queue: str | None) -> None:
        if self._queue is not None:
            self.bec_dispatcher.disconnect_slot(
                self._trigger_update, MessageEndpoints.procedure_logs(self._queue)
            )
        self._queue = queue
        if self._queue is not None:
            self.bec_dispatcher.connect_slot(
                self._trigger_update, MessageEndpoints.procedure_logs(self._queue)
            )
        self._update()


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = ProcedureLogs()
    widget.queue = "primary"
    widget.show()
    sys.exit(app.exec())
