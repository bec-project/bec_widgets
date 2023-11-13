import os
import sys

from qtpy import QtWidgets, uic


class UI(QtWidgets.QWidget):
    def __init__(self, uipath):
        super().__init__()

        self.ui = uic.loadUi(uipath, self)

        _, fname = os.path.split(uipath)
        self.setWindowTitle(fname)

        self.show()


def main():
    """A basic script to display UI file

    Run the script, passing UI file path as an argument, e.g.
    $ python bec_widgets/display_ui_file.py bec_widgets/line_plot.ui
    """
    app = QtWidgets.QApplication(sys.argv)

    UI(sys.argv[1])

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
