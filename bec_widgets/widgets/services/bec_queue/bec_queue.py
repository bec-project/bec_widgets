from __future__ import annotations

import threading
from pathlib import Path

from bec_lib import messages
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from qtpy.QtCore import Property, QUrl, Signal
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.compact_popup import CompactPopupWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.services.bec_queue.qml_host import create_quick_widget
from bec_widgets.widgets.services.bec_queue.queue_model import IDLE_STATUSES, QueueController

logger = bec_logger.logger

QML_FILE = Path(__file__).parent / "qml" / "BECQueue.qml"


class BECQueue(BECWidget, CompactPopupWidget):
    """
    Widget to display the BEC queue.

    Shows the running scan with its progress, the waiting scans (reorder, remove) and the most
    recent finished scans, together with the queue state and Pause / Resume / Abort controls.
    The view is written in QML and hosted in a ``QQuickWidget``; this class is the QWidget shell
    that keeps the RPC, Designer and docking interface.
    """

    PLUGIN = True
    ICON_NAME = "edit_note"

    queue_busy = Signal(bool)
    _history_ready = Signal(list)

    def __init__(
        self,
        parent: QWidget | None = None,
        client=None,
        config: ConnectionConfig = None,
        gui_id: str = None,
        refresh_upon_start: bool = True,
        **kwargs,
    ):
        super().__init__(
            parent=parent, layout=QVBoxLayout, client=client, gui_id=gui_id, config=config, **kwargs
        )
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.get_bec_shortcuts()
        self._toolbar_hidden = False
        self._known_queue_ids: set[str] = set()
        self._history_thread: threading.Thread | None = None

        self.controller = QueueController(self)
        self.controller.pause_requested.connect(self.pause_queue)
        self.controller.resume_requested.connect(self.resume_queue)
        self.controller.abort_requested.connect(self.abort_request)
        self.controller.halt_requested.connect(self.halt_scan)
        self.controller.remove_requested.connect(self.abort_request)
        self.controller.move_requested.connect(self.move_request)
        self.controller.clear_requested.connect(self.clear_queue)
        self._history_ready.connect(self.controller.set_history)

        self.view = self._create_view()
        self.view.setMinimumSize(320, 160)
        self.addWidget(self.view)
        self.label = "BEC Queue"
        self.tooltip = "BEC Queue status"

        self.bec_dispatcher.connect_slot(self.update_queue, MessageEndpoints.scan_queue_status())
        self.bec_dispatcher.connect_slot(self.on_scan_progress, MessageEndpoints.scan_progress())
        if refresh_upon_start:
            self.refresh_queue()

    def _create_view(self) -> QWidget:
        """Create the widget that renders the queue: here the QML view."""
        return create_quick_widget(self, QML_FILE, {"queue": self.controller})

    def _release_view(self):
        """Unload the QML tree before the controller it binds to is deleted."""
        self.view.setSource(QUrl())

    @Property(bool)
    def hide_toolbar(self):
        """Property to hide the BEC Queue toolbar."""
        return self._toolbar_hidden

    @hide_toolbar.setter
    def hide_toolbar(self, hide: bool):
        """
        Setters for the hide_toolbar property.

        Args:
            hide(bool): Whether to hide the toolbar.
        """
        self._hide_toolbar(hide)

    def _hide_toolbar(self, hide: bool):
        """
        Hide the toolbar.

        Args:
            hide(bool): Whether to hide the toolbar.
        """
        self._toolbar_hidden = hide
        self.controller.set_toolbar_visible(not hide)

    def refresh_queue(self):
        """
        Refresh the queue and the recent history.
        """
        msg = self.client.connector.get(MessageEndpoints.scan_queue_status())
        self._fetch_history()
        if msg is None:
            # msg is None if no scan has been run yet (fresh start)
            return
        self.update_queue(msg.content, msg.metadata)

    @SafeSlot(dict, dict)
    def update_queue(self, content, _metadata):
        """
        Update the view with the latest queue information.

        Args:
            content (dict): The queue content.
            _metadata (dict): The metadata.
        """
        # only show the primary queue for now
        primary_queue: messages.ScanQueueStatus | None = content.get("queue", {}).get("primary")
        self.controller.set_queue(primary_queue)
        queue_info = primary_queue.info if primary_queue else []

        queue_ids = {item.queue_id for item in queue_info}
        if self._known_queue_ids - queue_ids:
            # something left the queue: it is now in the history
            self._fetch_history()
        self._known_queue_ids = queue_ids

        busy = not all(item.status in IDLE_STATUSES for item in queue_info)
        self.set_global_state("warning" if busy else "default")
        self.queue_busy.emit(busy)

    @SafeSlot(dict, dict)
    def on_scan_progress(self, content: dict, metadata: dict):
        """
        Show the progress of the running scan.

        Args:
            content (dict): ProgressMessage content.
            metadata (dict): ProgressMessage metadata.
        """
        self.controller.set_progress(
            metadata.get("scan_id"),
            content.get("value", 0),
            content.get("max_value", 0),
            content.get("done", False),
        )

    def _fetch_history(self):
        """Read the queue history from Redis off the GUI thread."""
        if self._history_thread is not None and self._history_thread.is_alive():
            return

        def worker():
            try:
                history = self.client.connector.lrange(MessageEndpoints.scan_queue_history(), 0, 9)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(f"Could not read the queue history: {exc}")
                return
            if isinstance(history, list):
                self._history_ready.emit(
                    [m for m in history if isinstance(m, messages.ScanQueueHistoryMessage)]
                )

        self._history_thread = threading.Thread(target=worker, daemon=True)
        self._history_thread.start()

    ################################################################################
    # Requests to BEC
    ################################################################################

    @SafeSlot()
    def pause_queue(self):
        """Pause the queue: the running scan pauses at its next checkpoint, nothing new starts."""
        self.client.connector.send(
            MessageEndpoints.scan_queue_modification_request(),
            messages.ScanQueueModificationMessage(
                scan_id=None, action="deferred_pause", parameter={}
            ),
        )

    @SafeSlot()
    def resume_queue(self):
        """Resume the queue."""
        self.queue.request_scan_continuation()

    @SafeSlot(str)
    def abort_request(self, request_id: str):
        """
        Abort a request: the running scan is aborted, a waiting one is removed from the queue.

        Args:
            request_id(str): The request to abort; empty aborts the current request.
        """
        self.queue.request_scan_abortion(request_id=request_id or None)

    @SafeSlot()
    def halt_scan(self):
        """Halt the running scan without its cleanup routines."""
        self.queue.request_scan_halt()

    @SafeSlot(str, str)
    def move_request(self, scan_id: str, action: str):
        """
        Move a waiting scan within the queue.

        Args:
            scan_id(str): Scan id of the queue item.
            action(str): "move_up", "move_down", "move_top" or "move_bottom".
        """
        self.queue.request_queue_order_modification(scan_id=scan_id, action=action)

    @SafeSlot()
    def clear_queue(self):
        """Stop the running scan and remove every waiting scan."""
        self.queue.request_queue_reset()

    def cleanup(self):
        """Wait for a pending history read and release the view."""
        if self._history_thread is not None:
            self._history_thread.join(timeout=1)
        self._release_view()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = BECQueue()
    widget.show()
    sys.exit(app.exec_())
