import sys

from PySide6.QtWidgets import QApplication

from bec_widget import BECWidget
from qtpy.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from bec_widgets.examples.qapp_custom.bec_qapp import BECQApplication
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow


class DemoApp(BECMainWindow):
    def __init__(self):
        super().__init__()
        # self.setWindowTitle("Demo Application")
        # self.setGeometry(100, 100, 600, 400)

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

        self.setWindowIcon(self.windowIcon())


def main():
    app = QApplication(sys.argv)
    # app = BECQApplication(sys.argv)
    widget = DemoApp()
    widget.resize(400, 200)
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
