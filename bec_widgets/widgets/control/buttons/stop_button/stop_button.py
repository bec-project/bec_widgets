from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QToolButton, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot


class StopButton(BECWidget, QWidget):
    """A button that stops the current scan."""

    PLUGIN = True
    ICON_NAME = "dangerous"
    RPC = True

    def __init__(self, parent=None, client=None, config=None, gui_id=None, toolbar=False, **kwargs):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)

        self.get_bec_shortcuts()

        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if toolbar:
            icon = material_icon("stop", color="#cc181e", filled=True, convert_to_pixmap=False)
            self.button = QToolButton(icon=icon)
            self.button.setToolTip("Stop the scan queue")
        else:
            self.button = QPushButton()
            self.button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            self.button.setText("Stop")
            self.button.setStyleSheet(
                f"background-color:  #cc181e; color: white; font-weight: bold; font-size: 12px;"
            )
        self.button.clicked.connect(self.stop_scan)

        self.layout.addWidget(self.button)

    @SafeSlot()
    def stop_scan(
        self,
    ):  # , scan_id: str | None = None): #FIXME scan_id will be added when combining with Queue widget
        """
        Stop the scan.

        Args:
            scan_id(str|None): The scan id to stop. If None, the current scan will be stopped.
        """
        self.queue.request_scan_halt()


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
