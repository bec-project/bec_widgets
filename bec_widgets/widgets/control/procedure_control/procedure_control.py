import operator
from functools import partial, reduce
from typing import Literal

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import (
    ProcedureExecutionMessage,
    ProcedureQNotifMessage,
    ProcedureRequestMessage,
)
from bec_lib.procedures.helper import FrontendProcedureHelper
from bec_qthemes._icon.material_icons import material_icon
from pydantic import BaseModel, ConfigDict
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot

logger = bec_logger.logger

_icon = partial(material_icon, size=(20, 20), convert_to_pixmap=False, filled=False)

_ActionTypes = Literal["abort", "delete", "resubmit"]


class _BaseConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    actions: set[_ActionTypes]
    child_actions: set[_ActionTypes]
    actions_column: int = 3
    params_column: int = 2
    helper: FrontendProcedureHelper
    tree: QTreeWidget
    active_queue: bool = False


class _QueueConfig(BaseModel):
    queue: str
    base: _BaseConfig
    msgs: list[ProcedureExecutionMessage]


class _ItemConfig(BaseModel):
    base: _BaseConfig
    msg: ProcedureExecutionMessage


class _ActionItem(QTreeWidgetItem):
    ABORT_BUTTON_COLOR = DELETE_BUTTON_COLOR = "#CC181E"
    RESUBMIT_BUTTON_COLOR = "#2266BB"
    ACTION_TYPE: Literal["parent", "child"] = "child"

    def __init__(self, parent, strings: list[str], config: _BaseConfig):
        super().__init__(parent, strings)
        self._tree = config.tree
        self._config = config
        self._init_actions()

    def _init_actions(self):
        """Create the actions widget in the given column."""
        self.actions_widget = QWidget()
        actions_layout = QHBoxLayout(self.actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(0)

        def button(icon, color, slot, tooltip):
            button = QToolButton(self.actions_widget)
            setattr(self, icon, button)
            icon = _icon(icon, color=color)
            button.setIcon(icon)
            button.clicked.connect(slot)
            actions_layout.addWidget(button)
            button.setToolTip(tooltip)

        actions = (
            self._config.actions if self.ACTION_TYPE == "parent" else self._config.child_actions
        )
        if "abort" in actions:
            button("cancel_presentation", self.ABORT_BUTTON_COLOR, self._abort_self, "abort")
        if "delete" in actions:
            button("delete", self.DELETE_BUTTON_COLOR, self._delete_self, "delete")
        if "resubmit" in actions:
            button("autorenew", self.RESUBMIT_BUTTON_COLOR, self._resubmit_self, "resubmit")

        self._tree.setItemWidget(self, self._config.actions_column, self.actions_widget)

    @SafeSlot()
    def _abort_self(self): ...
    @SafeSlot()
    def _delete_self(self): ...
    @SafeSlot()
    def _resubmit_self(self): ...


class JobItem(_ActionItem):
    def __init__(self, parent, strings: list[str], config: _ItemConfig):
        super().__init__(parent, strings, config.base)
        self._msg = config.msg
        self._init_params_display()

    def queue(self):
        return self._msg.queue

    def _init_params_display(self):
        self.setText(self._config.params_column, self._short_params_text())
        self.setToolTip(self._config.params_column, self._long_params_html())

    def _short_params_text(self):
        a, k = self._msg.args_kwargs
        args = f"{a}, " if a else ""
        kwargs = f"{k}".strip("{}") if k else ""
        return args + kwargs

    def _long_params_html(self):
        a, k = self._msg.args_kwargs
        args = "<b>Positional arguments:</b><br>" + ", ".join(str(arg) for arg in a) if a else ""
        kwargs = (
            reduce(
                operator.add,
                (f"    {k}: {v}<br>" for k, v in k.items()),
                "<b>Keyword arguments:</b><br>",
            )
            if k
            else ""
        )
        return args + kwargs

    @SafeSlot()
    def _abort_self(self):
        self._config.helper.request.abort_execution(self._msg.execution_id)

    @SafeSlot()
    def _delete_self(self):
        self._config.helper.request.clear_unhandled_execution(self._msg.execution_id)

    @SafeSlot()
    def _resubmit_self(self):
        self._config.helper.request.clear_unhandled_execution(self._msg.execution_id)
        self._config.helper.request.procedure(
            identifier=self._msg.identifier,
            queue=self._msg.queue,
            args_kwargs=self._msg.args_kwargs,
        )


class QueueItem(_ActionItem):
    ACTION_TYPE = "parent"

    def __init__(self, parent, strings: list[str], config: _QueueConfig):
        super().__init__(parent, strings, config.base)
        self._queue = config.queue
        self.update(config.msgs)

    def clear(self):
        for i in reversed(range(self.childCount())):
            self.removeChild(self.child(i))

    def update(self, msgs: list[ProcedureExecutionMessage]):
        if self._config.active_queue:
            active = self._config.helper.get.running_procedures()
            for msg in active:
                if msg.queue == self._queue:
                    JobItem(
                        self, [msg.identifier, "RUNNING"], _ItemConfig(base=self._config, msg=msg)
                    )
        for msg in msgs:
            JobItem(
                self,
                [msg.identifier, "PENDING" if self._config.active_queue else "ABORTED"],
                _ItemConfig(base=self._config, msg=msg),
            )

    def queue(self):
        return self._queue

    @SafeSlot()
    def _abort_self(self):
        self._config.helper.request.abort_queue(self._queue)

    @SafeSlot()
    def _delete_self(self):
        self._config.helper.request.clear_unhandled_queue(self._queue)


class CategoryItem(QTreeWidgetItem):
    def __init__(self, parent, strings: list[str], config: _BaseConfig):
        super().__init__(parent, strings)
        self._queues: dict[str, QueueItem] = {}
        self._tree: QTreeWidget = parent
        self._config = config

    def update(self, queue: str, msgs: list[ProcedureExecutionMessage]):
        if (queue_item := self._queues.get(queue)) is not None:
            queue_item.clear()
            queue_item.update(msgs)
            if queue_item.childCount() == 0:
                self.removeChild(queue_item)
                del self._queues[queue]
        elif msgs:
            self._queues[queue] = QueueItem(
                self, [queue], _QueueConfig(base=self._config, queue=queue, msgs=msgs)
            )
            self._queues[queue].setExpanded(True)


class ProcedureControl(BECWidget, QWidget):

    RPC = False

    queue_selected = Signal(str)

    def __init__(self, parent=None, client=None, config=None, gui_id: str | None = None, **kwargs):
        config = config or ConnectionConfig()
        super().__init__(parent=parent, client=client, config=config, gui_id=gui_id, **kwargs)
        self._conn = self.bec_dispatcher.client.connector
        self._helper = FrontendProcedureHelper(self._conn)
        self._setup_ui()
        self.bec_dispatcher.connect_slot(self._update, MessageEndpoints.procedure_queue_notif())
        self._init_queues()
        self._content.itemSelectionChanged.connect(self.on_selection_changed)

    def on_selection_changed(self):
        selected_items = self._content.selectedItems()
        if len(selected_items) != 1:
            self.queue_selected.emit("")
            return
        if isinstance((item := selected_items[0]), (QueueItem, JobItem)):
            self.queue_selected.emit(item.queue())
            return
        self.queue_selected.emit("")

    @SafeSlot(ProcedureQNotifMessage, dict)
    def _update(self, msg: dict | ProcedureQNotifMessage, _):
        msg = ProcedureQNotifMessage.model_validate(msg)
        if msg.queue_type == "execution":
            cat_to_update = self._active_queues
            read_queue = self._helper.get.exec_queue
        else:
            cat_to_update = self._unhandled_queues
            read_queue = self._helper.get.unhandled_queue
        cat_to_update.update(msg.queue_name, read_queue(msg.queue_name))

    def _setup_ui(self):
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._content = QTreeWidget()
        self._content.setAlternatingRowColors(True)
        self._content.setHeaderLabels(["name", "status", "params", "actions"])
        self._layout.addWidget(self._content)

        config = partial(_BaseConfig, helper=self._helper, tree=self._content, actions_column=3)

        self._active_queues = CategoryItem(
            self._content,
            ["active queues"],
            config(actions={"abort"}, child_actions={"abort"}, active_queue=True),
        )
        self._content.addTopLevelItem(self._active_queues)
        self._active_queues.setExpanded(True)

        self._unhandled_queues = CategoryItem(
            self._content,
            ["unhandled queues"],
            config(actions={"delete"}, child_actions={"delete", "resubmit"}),
        )
        self._content.addTopLevelItem(self._unhandled_queues)
        self._active_queues.setExpanded(True)

    def _init_queues(self):
        for queue in self._helper.get.active_and_pending_queue_names():
            self._active_queues.update(queue, self._helper.get.exec_queue(queue))
        for queue in self._helper.get.queue_names("unhandled"):
            self._unhandled_queues.update(queue, self._helper.get.unhandled_queue(queue))


class ProcedureSubmissionOptionsDialog(QDialog):
    """
    Dialog to customize procedure options
    """

    def __init__(self, parent=None, client=None):
        super().__init__(parent)
        self.setWindowTitle("Procedure execution options")

        self._setup_ui()

    def sizeHint(self) -> QSize:
        return QSize(600, 800)

    def _setup_ui(self):
        """Setup the dialog UI with ScanControl widget and buttons."""
        layout = QVBoxLayout(self)

        # Create the scan control widget

        # Create dialog buttons
        button_box = QDialogButtonBox(Qt.Orientation.Horizontal, self)

        # Create custom buttons with appropriate text
        insert_button = QPushButton("Insert")
        cancel_button = QPushButton("Cancel")

        button_box.addButton(insert_button, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)

        layout.addWidget(button_box)

        # Connect button signals
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def accept(self):
        """Override accept to generate code before closing."""
        super().accept()


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = ProcedureControl()
    widget.setFixedWidth(800)
    widget.setFixedHeight(800)
    widget.show()
    sys.exit(app.exec())
