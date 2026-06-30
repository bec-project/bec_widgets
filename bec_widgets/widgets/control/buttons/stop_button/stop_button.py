from bec_qthemes import material_icon
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QToolButton, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot


class StopButton(BECWidget, QWidget):
    """A button that stops the current scan."""

    PLUGIN = True
    ICON_NAME = "dangerous"
    RPC = False
    ABORT_LABEL = "Stop"
    EMERGENCY_STOP_LABEL = "Emergency Stop"
    EMERGENCY_STOP_TIMEOUT_MS = 2000

    def __init__(self, parent=None, client=None, config=None, gui_id=None, toolbar=False, **kwargs):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)

        self.get_bec_shortcuts()

        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._emergency_stop_active = False
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._deactivate_emergency_stop)

        if toolbar:
            icon = material_icon("stop", color="#cc181e", filled=True, convert_to_pixmap=False)
            self.button = QToolButton(icon=icon)
            self.button.setToolTip(self.ABORT_LABEL)
        else:
            self.button = QPushButton()
            self.button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            self.button.setText(self.ABORT_LABEL)
            self.button.setProperty("variant", "danger")
        self.button.clicked.connect(self.stop_scan)

        self.layout.addWidget(self.button)

    @SafeSlot()
    def stop_scan(
        self,
    ):  # , scan_id: str | None = None): #FIXME scan_id will be added when combining with Queue widget
        """
        Abort the scan by default, then temporarily offer an emergency stop.

        Args:
            scan_id(str|None): The scan id to stop. If None, the current scan will be targeted.
        """
        if self._emergency_stop_active:
            self.queue.request_scan_halt()
            self._activate_emergency_stop()
            return

        self.queue.request_scan_abortion()
        self._activate_emergency_stop()

    def _activate_emergency_stop(self) -> None:
        self._emergency_stop_active = True
        self._set_button_label(self.EMERGENCY_STOP_LABEL)
        self._reset_timer.start(self.EMERGENCY_STOP_TIMEOUT_MS)

    def _deactivate_emergency_stop(self) -> None:
        self._emergency_stop_active = False
        self._set_button_label(self.ABORT_LABEL)

    def _set_button_label(self, label: str) -> None:
        if hasattr(self.button, "setText"):
            self.button.setText(label)
        self.button.setToolTip(label)

    def cleanup(self):
        """Stop and dispose the emergency-stop reset timer before widget teardown."""
        self._reset_timer.stop()
        self._reset_timer.timeout.disconnect(self._deactivate_emergency_stop)
        self._reset_timer.deleteLater()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

    from bec_widgets.widgets.control.buttons.stop_button.stop_button import StopButton

    class MyGui(QWidget):
        def __init__(self):
            super().__init__()
            self.setLayout(QVBoxLayout())
            # Create and add the StopButton to the layout
            self.stop_button = StopButton()
            self.layout().addWidget(self.stop_button)

    # Example of how this custom GUI might be used:
    app = QApplication([])
    my_gui = MyGui()
    my_gui.show()
    sys.exit(app.exec_())
