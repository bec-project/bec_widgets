import os
import sys
import webbrowser

from qtpy.QtWidgets import QApplication, QMainWindow

from bec_widgets.utils.ui_loader import UILoader


class BECWebLinksMixin:
    @staticmethod
    def open_bec_docs():
        webbrowser.open("https://beamline-experiment-control.readthedocs.io/en/latest/")

    @staticmethod
    def open_bec_widgets_docs():
        webbrowser.open("https://bec.readthedocs.io/projects/bec-widgets/en/latest/")

    @staticmethod
    def open_bec_bug_report():
        webbrowser.open("https://gitlab.psi.ch/groups/bec/-/issues/")


class BECGeneralApp(QMainWindow):
    def __init__(self, parent=None):
        super(BECGeneralApp, self).__init__(parent)
        ui_file_path = os.path.join(os.path.dirname(__file__), "general_app.ui")
        self.load_ui(ui_file_path)

        self.resize(1280, 720)

        self.ini_ui()

    def ini_ui(self):
        self._hook_menubar()

    def load_ui(self, ui_file):
        loader = UILoader(self)
        self.ui = loader.loader(ui_file)
        self.setCentralWidget(self.ui)

    def _hook_menubar(self):
        self.ui.action_BEC_docs.triggered.connect(BECWebLinksMixin.open_bec_docs)
        self.ui.action_BEC_widgets_docs.triggered.connect(BECWebLinksMixin.open_bec_widgets_docs)
        self.ui.action_bug_report.triggered.connect(BECWebLinksMixin.open_bec_bug_report)


def main():  # pragma: no cover
    from qtpy import PYSIDE6

    if not PYSIDE6:
        print(
            "PYSIDE6 is not available in the environment. UI files with BEC custom widgets are runnable only with PySide6."
        )
        return

    app = QApplication(sys.argv)
    main_window = BECGeneralApp()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    main()
