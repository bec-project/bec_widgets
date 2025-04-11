from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QToolButton, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot


class ResetButton(BECWidget, QWidget):
    """A button that resets the scan queue."""

    PLUGIN = True
    ICON_NAME = "restart_alt"
    RPC = True

    def __init__(self, parent=None, client=None, config=None, gui_id=None, toolbar=False, **kwargs):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        self.get_bec_shortcuts()

        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if toolbar:
            icon = material_icon(
                "restart_alt", color="#F19E39", filled=True, convert_to_pixmap=False
            )
            self.button = QToolButton(icon=icon)
            self.button.setToolTip("Reset the scan queue")
        else:
            self.button = QPushButton()
            self.button.setText("Reset Queue")
            self.button.setStyleSheet(
                "background-color:  #F19E39; color: white; font-weight: bold; font-size: 12px;"
            )
        self.button.clicked.connect(self.confirm_reset_queue)

        self.layout.addWidget(self.button)

    @SafeSlot()
    def confirm_reset_queue(self):
        """Prompt the user to confirm the queue reset."""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("Confirm Reset")
        msg_box.setText(
            "Are you sure you want to reset the scan queue? This action cannot be undone."
        )
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)

        if msg_box.exec_() == QMessageBox.Yes:
            self.reset_queue()

    @SafeSlot()
    def reset_queue(self):
        """Reset the scan queue."""
        self.queue.request_queue_reset()
