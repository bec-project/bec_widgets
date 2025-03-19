from bec_qapp import upgrade_to_becqapp
from qtpy.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


class BECWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Upgrade qApp if necessary
        app = QApplication.instance()
        if not getattr(app, "is_bec_app", False):
            print("[BECWidget]: Upgrading QApplication instance to BECQApplication.")
            app = upgrade_to_becqapp()
        else:
            print("[BECWidget]: BECQApplication already active.")

        app.inject_property("widget_initialized", True)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        label = QLabel("BECWidget is running with BECQApplication features.")
        layout.addWidget(label)
        self.setLayout(layout)
