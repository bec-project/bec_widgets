import os

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTabWidget,
    QTableWidgetItem,
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

        # Hook signals
        self.pushButton_new_scan_type.clicked.connect(
            lambda: self.add_new_scan(
                self.tabWidget_scan_types, self.lineEdit_scan_type.text(), True
            )
        )
        # Scan Types changed
        self.comboBox_scanTypes.currentIndexChanged.connect(self._init_default)
        # Make scan tabs closable
        self.tabWidget_scan_types.tabCloseRequested.connect(self.handle_tab_close_request)

        # Default configuration
        # Init functions to make a default dialog #TODO this is useful, but has to be made better
        if default_config is None:
            self._init_default()
        # self.load_config()

    def _init_default(self):
        if self.comboBox_scanTypes.currentText() == "Disabled":
            self.add_new_scan(self.tabWidget_scan_types, "Default")
            self.pushButton_new_scan_type.setEnabled(False)
            self.lineEdit_scan_type.setEnabled(False)
        else:
            self.pushButton_new_scan_type.setEnabled(True)
            self.lineEdit_scan_type.setEnabled(True)
            self.tabWidget_scan_types.clear()

    def add_new_scan(self, parent_tab: QTabWidget, scan_name: str, closable: bool = False) -> None:
        """
        Add a new scan tab to the parent tab widget

        Args:
            closable:
            parent_tab(QTabWidget): Parent tab widget, where to add scan tab
            scan_name(str): Scan name
            closable(bool): If True, the scan tab will be closable
        """
        # Create a new scan tab
        scan_tab = QWidget()
        scan_tab_layout = QVBoxLayout(scan_tab)

        # Set a tab widget for plots
        tabWidget_plots = QTabWidget()
        tabWidget_plots.setObjectName("tabWidget_plots")
        tabWidget_plots.setTabsClosable(True)
        tabWidget_plots.tabCloseRequested.connect(self.handle_tab_close_request)
        scan_tab_layout.addWidget(tabWidget_plots)

        # Add scan tab
        parent_tab.addTab(scan_tab, scan_name)

        # Optionally, connect the tabCloseRequested signal to a slot to handle the tab close request
        if closable:
            parent_tab.setTabsClosable(closable)
        # Add first plot
        self.add_new_plot(scan_tab)

    def add_new_plot(self, scan_tab: QWidget) -> None:
        """
        Add a new plot tab to the scan tab
        Args:
            scan_tab (QWidget): Scan tab widget

        """
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

    def hook_plot_tab_signals(self, scan_tab: QTabWidget, plot_tab: Tab_Ui_Form) -> None:
        """
        Hook signals of the plot tab
        Args:
            scan_tab(QTabWidget): Scan tab widget
            plot_tab(Tab_Ui_Form): Plot tab widget
        """
        plot_tab.pushButton_add_new_plot.clicked.connect(
            lambda: self.add_new_plot(scan_tab=scan_tab)
        )
        plot_tab.pushButton_y_new.clicked.connect(
            lambda: self.add_new_signal(
                scan_tab.findChild(QTabWidget, "tabWidget_plots").table_y_signals
            )
        )

    def add_new_signal(self, table: QTableWidget) -> None:
        row_position = table.rowCount()
        table.insertRow(row_position)
        table.setItem(row_position, 0, QTableWidgetItem(""))
        table.setItem(row_position, 1, QTableWidgetItem(""))

    def handle_tab_close_request(self, index: int) -> None:
        """
        Handle tab close request

        Args:
            index(int): Index of the tab to be closed
        """
        print(index)
        parent_tab = self.sender()
        parent_tab.removeTab(index)

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
