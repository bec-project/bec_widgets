from __future__ import annotations

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QToolButton, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot

logger = bec_logger.logger


class AbortButton(BECWidget, QWidget):
    """A button that aborts the request."""

    PLUGIN = True
    ICON_NAME = "cancel"
    RPC = False

    def __init__(
        self,
        parent=None,
        client=None,
        config=None,
        gui_id=None,
        toolbar=False,
        request_id=None,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        self.get_bec_shortcuts()
        self.request_id = request_id

        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if toolbar:
            icon = material_icon("cancel", color="#666666", filled=True)
            self.button = QToolButton(icon=icon)
            self.button.setToolTip("Abort the request")
        else:
            self.button = QPushButton()
            self.button.setText("Abort")
        self.button.clicked.connect(self.abort_scan)

        self.layout.addWidget(self.button)

    @SafeSlot()
    def abort_scan(
        self,
    ):  # , scan_id: str | None = None): #FIXME scan_id will be added when combining with Queue widget
        """
        Abort the request.

        Args:
            request_id(str|None): The request id to abort. If None, the current request will be aborted.
        """
        if self.request_id is not None:
            logger.info(f"Aborting request with request_id: {self.request_id}")
            self.queue.request_scan_abortion(request_id=self.request_id)
        else:
            self.queue.request_scan_abortion()
