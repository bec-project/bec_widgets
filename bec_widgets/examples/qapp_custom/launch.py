import sys
import os

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout

# Set this early!
# os.environ["PYSIDE_DISABLE_INTERNAL_QT_WARNINGS"] = "1"

from qtpy.QtWidgets import QApplication
from bec_widget import BECWidget


class DemoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Demo Application")
        self.setGeometry(100, 100, 600, 400)

        # Create an instance of BECWidget
        self.main_widget = QWidget(self)

        self.setCentralWidget(self.main_widget)
        self.main_widget.layout = QVBoxLayout(self.main_widget)
        self.bec_widget_1 = BECWidget()
        self.bec_widget_2 = BECWidget()

        # Set up the UI for the BECWidget
        self.bec_widget_1.setup_ui()
        self.bec_widget_2.setup_ui()

        self.main_widget.layout.addWidget(self.bec_widget_1)
        self.main_widget.layout.addWidget(self.bec_widget_2)


def main():
    app = QApplication(sys.argv)
    widget = DemoApp()
    widget.resize(400, 200)
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
