from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.procedures.helper import FrontendProcedureHelper
from bec_qthemes import material_icon
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot

logger = bec_logger.logger


class ProcedureLogs(BECWidget, QWidget):

    RPC = False

    def __init__(self, parent=None, client=None, config=None, gui_id: str | None = None, **kwargs):
        config = config or ConnectionConfig()
        super().__init__(parent=parent, client=client, config=config, gui_id=gui_id, **kwargs)
        self._conn = self.bec_dispatcher.client.connector
        self._queue: str | None = None
        self._helper = FrontendProcedureHelper(self._conn)
        self._setup_ui()

    @SafeSlot()
    def _update_selection_box(self):
        self._selection_box.clear()
        self._available_streams = self._helper.get.log_queue_names()
        self._selection_box.addItems(self._available_streams)

    def _setup_ui(self):
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._setup_tools()
        self._setup_display()

    def _setup_tools(self):
        self.tools = QWidget(self)
        self._tools_layout = QHBoxLayout()
        self._tools_layout.setContentsMargins(0, 0, 0, 0)
        self.tools.setLayout(self._tools_layout)
        self._selection_box = QComboBox()
        self._update_selection_box()
        self._selection_box.setCurrentIndex(-1)
        self._selection_box.currentTextChanged.connect(self.set_queue)
        self._refresh_button = QToolButton()
        self._refresh_button.setIcon(material_icon("refresh", convert_to_pixmap=False))
        self._tools_layout.addWidget(QLabel("Select logs stream: "))
        self._tools_layout.addWidget(self._selection_box)
        self._tools_layout.addWidget(self._refresh_button)
        self._refresh_button.clicked.connect(self._update_selection_box)
        self._layout.addWidget(self.tools)

    def _setup_display(self):
        self.widget = QTextEdit(lineWrapMode=QTextEdit.LineWrapMode.NoWrap, readOnly=True)
        font = QFont("Courier New")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.widget.setFont(font)
        self.widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(self.widget)

    @SafeSlot(dict, dict)
    def _update(self, msg, _):
        self.widget.append(msg.get("data").strip())

    def _init_content(self):
        self.widget.setText("")
        if self._queue is None:
            return
        if msgs := self._conn.xread(MessageEndpoints.procedure_logs(self._queue), from_start=True):
            self.widget.append("\n".join(msg.get("data").data.strip() for msg in msgs))

    @SafeSlot()
    def clear_selection_box(self, *_, **__):
        self._selection_box.setCurrentIndex(-1)

    @SafeSlot(None)
    @SafeSlot(str)
    def set_queue(self, queue: str | None):
        if queue == "":
            return
        self.queue = queue
        self._selection_box.setCurrentIndex(-1)

    @SafeProperty(str)
    def queue(self) -> str | None:
        return self._queue

    @queue.setter
    def queue(self, queue: str | None) -> None:
        if self._queue == queue:
            return
        if self._queue is not None:
            self.bec_dispatcher.disconnect_slot(
                self._update, MessageEndpoints.procedure_logs(self._queue)
            )
        self._queue = queue or None
        if self._queue is not None:
            self.bec_dispatcher.connect_slot(
                self._update, MessageEndpoints.procedure_logs(self._queue)
            )
        self._init_content()


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = ProcedureLogs()
    widget.queue = "primary"
    widget.show()
    sys.exit(app.exec())
