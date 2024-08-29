from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QToolButton, QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.utils.bec_widget import BECWidget


class AbortButton(BECWidget, QWidget):
    """A button that abort the scan."""

    ICON_NAME = "cancel"

    def __init__(self, parent=None, client=None, config=None, gui_id=None, toolbar=False):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QWidget.__init__(self, parent=parent)

        self.get_bec_shortcuts()

        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if toolbar:
            icon = material_icon("cancel", color="#666666", filled=True)
            self.button = QToolButton(icon=icon)
            self.button.triggered.connect(self.abort_scan)
        else:
            self.button = QPushButton()
            self.button.setText("Abort")
            self.button.setStyleSheet(
                "background-color:  #666666; color: white; font-weight: bold; font-size: 12px;"
            )
            self.button.clicked.connect(self.abort_scan)

        self.layout.addWidget(self.button)

    @SafeSlot()
    def abort_scan(
        self,
    ):  # , scan_id: str | None = None): #FIXME scan_id will be added when combining with Queue widget
        """
        Abort the scan.

        Args:
            scan_id(str|None): The scan id to abort. If None, the current scan will be aborted.
        """
        self.queue.request_scan_abortion()
