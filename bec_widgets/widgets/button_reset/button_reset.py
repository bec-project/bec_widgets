from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QToolButton, QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.utils.bec_widget import BECWidget


class ResetButton(BECWidget, QWidget):
    """A button that reset the scan queue."""

    ICON_NAME = "restart_alt"

    def __init__(self, parent=None, client=None, config=None, gui_id=None, toolbar=False):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QWidget.__init__(self, parent=parent)

        self.get_bec_shortcuts()

        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if toolbar:
            icon = material_icon("restart_alt", color="#F19E39", filled=True)
            self.button = QToolButton(icon=icon)
            self.button.triggered.connect(self.reset_queue)
        else:
            self.button = QPushButton()
            self.button.setText("Reset Queue")
            self.button.setStyleSheet(
                "background-color:  #F19E39; color: white; font-weight: bold; font-size: 12px;"
            )
            self.button.clicked.connect(self.reset_queue)

        self.layout.addWidget(self.button)

    @SafeSlot()
    def reset_queue(self):
        """Stop the scan."""
        self.queue.request_queue_reset()
