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
        """
        Add a new scan tab to the parent tab widget

        Args:
            parent_tab(QTabWidget): Parent tab widget, where to add scan tab
            scan_name(str): Scan name
        """
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
        plot_tab.pushButton_remove_current_plot.clicked.connect(
            lambda: self.remove_current_plot(scan_tab.findChild(QTabWidget, "tabWidget_plots"))
        )
        plot_tab.pushButton_y_new.clicked.connect(
            lambda: self.add_new_signal(
                scan_tab.findChild(QTabWidget, "tabWidget_plots").table_y_signals
            )
        )

    def remove_current_plot(self, plot_tab: QTabWidget) -> None:
        current_index = plot_tab.currentIndex()
        total_tabs = plot_tab.count()
        # make sure that there is a tab to be removed
        if current_index != -1 and total_tabs > 1:
            plot_tab.removeTab(current_index)

    def add_new_signal(self, table: QTableWidget) -> None:
        row_position = table.rowCount()
        table.insertRow(row_position)
        table.setItem(row_position, 0, QTableWidgetItem(""))
        table.setItem(row_position, 1, QTableWidgetItem(""))

        ...

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
