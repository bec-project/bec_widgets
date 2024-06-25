import sys

from qtpy import PYSIDE6
from qtpy.QtCore import QFile
from qtpy.QtUiTools import QUiLoader
from qtpy.QtWidgets import QApplication, QMainWindow

from bec_widgets.examples.plugin_example_pyside.tictactoe import TicTacToe
from bec_widgets.widgets.bec_status_box.bec_status_box import BECStatusBox
from bec_widgets.widgets.device_inputs import DeviceComboBox, DeviceLineEdit
from bec_widgets.widgets.vscode.vscode import VSCodeEditor


class CustomUiLoader(QUiLoader):
    def __init__(self, baseinstance):
        super(CustomUiLoader, self).__init__(baseinstance)
        self.custom_widgets = {
            "TicTacToe": TicTacToe,
            "VSCodeEditor": VSCodeEditor,
            "BECStatusBox": BECStatusBox,
            "DeviceLineEdit": DeviceLineEdit,
            "DeviceComboBox": DeviceComboBox,
        }

        self.baseinstance = baseinstance

    def createWidget(self, class_name, parent=None, name=""):
        if class_name in self.custom_widgets:
            widget = self.custom_widgets[class_name](parent)
            widget.setObjectName(name)
            return widget
        return super(CustomUiLoader, self).createWidget(class_name, parent, name)


class CustomMainWindow(QMainWindow):
    def __init__(self, ui_file, parent=None):
        super(CustomMainWindow, self).__init__(parent)
        self.load_ui(ui_file)

    def load_ui(self, ui_file):
        loader = CustomUiLoader(self)
        ui_file = QFile(ui_file)
        ui_file.open(QFile.ReadOnly)
        self.ui = loader.load(ui_file)
        ui_file.close()
        self.setCentralWidget(self.ui)


def main():  # pragma: no cover
    from qtpy import PYSIDE6

    if not PYSIDE6:
        print(
            "PYSIDE6 is not available in the environment. UI files with BEC custom widgets are runnable only with PySide6."
        )
        return

    app = QApplication(sys.argv)
    main_window = CustomMainWindow("general_app.ui")
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    main()
