import os

from bec_widgets.qt_utils import BECTable
from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QLabel,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QTableWidgetItem,
    QTableWidget,
    QTabWidget,
)


current_path = os.path.dirname(__file__)
Ui_Form, BaseClass = uic.loadUiType(os.path.join(current_path, "config_dialog.ui"))
Tab_Ui_Form, Tab_BaseClass = uic.loadUiType(os.path.join(current_path, "tab_template.ui"))


class ConfigDialog(QWidget, Ui_Form):
    config_updated = pyqtSignal(dict)

    def __init__(self, default_config=None):
        super(ConfigDialog, self).__init__()
        self.setupUi(self)

        # Connect the Ok/Apply/Cancel buttons #TODO this is useful
        self.pushButton_ok.clicked.connect(self.apply_and_close)
        self.pushButton_apply.clicked.connect(self.apply_config)
        self.pushButton_cancel.clicked.connect(self.close)

        # #TODO hook Scan types buttons
        self.pushButton_new_scan_type.clicked.connect(
            lambda: self.add_new_scan(self.tabWidget_scan_types, "New Scan Type")
        )

        # Default configuration
        self._init_default()
        # Init functions to make a default dialog #TODO this is useful, but has to be made better
        # if default_config is not None:
        # self.load_config()

    def _init_default(self):
        self.add_new_scan(self.tabWidget_scan_types, "Default")

    def add_new_scan(self, parent_tab: QTabWidget, scan_name: str) -> None:
        # Create a new scan tab
        scan_tab = QWidget()
        scan_tab_layout = QVBoxLayout(scan_tab)

        # Set a tab widget for plots
        tabWidget_plots = QTabWidget()
        tabWidget_plots.setObjectName("tabWidget_plots")
        scan_tab_layout.addWidget(tabWidget_plots)

        # Add scan tab
        parent_tab.addTab(scan_tab, scan_name)

        # Add first plot
        self.add_new_plot(scan_tab)

    def add_new_plot(self, scan_tab: QTabWidget) -> None:
        # Create a new plot tab from .ui template
        plot_tab = QWidget()
        plot_tab_ui = Tab_Ui_Form()
        plot_tab_ui.setupUi(plot_tab)

        # Add plot to current scan tab
        tabWidget_plots = scan_tab.findChild(QTabWidget, "tabWidget_plots")
        plot_name = f"Plot {tabWidget_plots.count() + 1}"
        tabWidget_plots.addTab(plot_tab, plot_name)

        # Hook signal
        self.hook_plot_tab_signals(scan_tab=scan_tab, plot_tab=plot_tab_ui)

    def hook_plot_tab_signals(self, scan_tab: QTabWidget, plot_tab: QTabWidget) -> None:
        plot_tab.pushButton_add_new_plot.clicked.connect(
            lambda: self.add_new_plot(scan_tab=scan_tab)
        )

    def apply_config(self):
        ...
        # config_to_emit = self.apply_configuration()
        # self.config_updated.emit(config_to_emit)

    def apply_and_close(self):
        ...
        # self.apply_config()
        # self.close()

    def load_config(self):
        ...

    @staticmethod
    def safe_text(line_edit):
        return "" if line_edit is None else line_edit.text()


if __name__ == "__main__":
    app = QApplication([])
    main_app = ConfigDialog()
    main_app.show()
    app.exec_()
