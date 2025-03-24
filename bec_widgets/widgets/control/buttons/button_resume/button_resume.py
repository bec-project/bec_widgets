from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QToolButton, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot


class ResumeButton(BECWidget, QWidget):
    """A button that continue scan queue."""

    PLUGIN = True
    ICON_NAME = "resume"

    def __init__(self, parent=None, client=None, config=None, gui_id=None, toolbar=False, **kwargs):
        super().__init__(client=client, config=config, gui_id=gui_id, **kwargs)
        QWidget.__init__(self, parent=parent)

        self.get_bec_shortcuts()

        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if toolbar:
            icon = material_icon("resume", color="#2793e8", filled=True, convert_to_pixmap=False)
            self.button = QToolButton(icon=icon)
            self.button.setToolTip("Resume the scan queue")
        else:
            self.button = QPushButton()
            self.button.setText("Resume")
            self.button.setStyleSheet(
                "background-color:  #2793e8; color: white; font-weight: bold; font-size: 12px;"
            )
        self.button.clicked.connect(self.continue_scan)

        self.layout.addWidget(self.button)

    @SafeSlot()
    def continue_scan(self):
        """Stop the scan."""
        self.queue.request_scan_continuation()
