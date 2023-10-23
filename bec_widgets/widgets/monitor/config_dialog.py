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
    QLineEdit,
)

current_path = os.path.dirname(__file__)
Ui_Form, BaseClass = uic.loadUiType(os.path.join(current_path, "config_dialog.ui"))
Tab_Ui_Form, Tab_BaseClass = uic.loadUiType(os.path.join(current_path, "tab_template.ui"))


class ConfigDialog(QWidget, Ui_Form):
    config_updated = pyqtSignal(dict)

    def __init__(self, default_config=None):
        super(ConfigDialog, self).__init__()
        self.setupUi(self)

        # Connect the Ok/Apply/Cancel buttons
        self.pushButton_ok.clicked.connect(self.apply_and_close)
        self.pushButton_apply.clicked.connect(self.apply_config)
        self.pushButton_cancel.clicked.connect(self.close)

        # Hook signals top level
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
        plot_tab.ui = plot_tab_ui

        # Add plot to current scan tab
        tabWidget_plots = scan_tab.findChild(QTabWidget, "tabWidget_plots")
        plot_name = f"Plot {tabWidget_plots.count() + 1}"
        tabWidget_plots.addTab(plot_tab, plot_name)

        # Hook signal
        self.hook_plot_tab_signals(scan_tab=scan_tab, plot_tab=plot_tab.ui)

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
            lambda: self.add_new_signal(plot_tab.tableWidget_y_signals)
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
        parent_tab = self.sender()
        parent_tab.removeTab(index)

    def get_plot_config(self, plot_tab: Tab_Ui_Form) -> dict:
        """
        Get plot configuration from the plot tab adn send it as dict

        Args:
            plot_tab(Tab_Ui_Form): Plot tab widget

        Returns:
            dict: Plot configuration
        """

        table = plot_tab.tableWidget_y_signals
        signals = [
            {
                "name": self.safe_text(table.item(row, 0)),
                "entry": self.safe_text(table.item(row, 1)),
            }
            for row in range(table.rowCount())
        ]

        plot_data = {
            "plot_name": self.safe_text(plot_tab.lineEdit_plot_title),
            "x": {
                "label": self.safe_text(plot_tab.lineEdit_x_label),
                "signals": [
                    {
                        "name": self.safe_text(plot_tab.lineEdit_x_name),
                        "entry": self.safe_text(plot_tab.lineEdit_x_entry),
                    }
                ],
            },
            "y": {
                "label": self.safe_text(plot_tab.lineEdit_y_label),
                "signals": signals,
            },
        }
        return plot_data

    def apply_config(self) -> dict:
        """
        Apply configuration from the whole configuration window

        Returns:
            dict: Configuration

        """
        # General settings
        config = {
            "plot_settings": {
                "background_color": self.comboBox_appearance.currentText(),
                "num_columns": self.spinBox_n_column.value(),
                "colormap": self.comboBox_colormap.currentText(),
                "scan_types": True if self.comboBox_scanTypes.currentText() == "Enabled" else False,
            },
            "plot_data": {} if self.comboBox_scanTypes.currentText() == "Enabled" else [],
        }

        # Iterate through the plot tabs - Device monitor mode
        if config["plot_settings"]["scan_types"] == False:
            plot_tab = self.tabWidget_scan_types.findChild(QTabWidget, "tabWidget_plots")
            for index in range(plot_tab.count()):
                plot_data = self.get_plot_config(plot_tab.widget(index).ui)
                config["plot_data"].append(plot_data)

        # Iterate through the scan tabs - Scan mode
        elif config["plot_settings"]["scan_types"] == True:
            # Iterate through the scan tabs
            for index in range(self.tabWidget_scan_types.count()):
                scan_tab = self.tabWidget_scan_types.widget(index)
                scan_name = self.tabWidget_scan_types.tabText(index)
                plot_tab = scan_tab.findChild(QTabWidget, "tabWidget_plots")
                plot_data = {}
                for index in range(plot_tab.count()):
                    plot_data = self.get_plot_config(plot_tab.widget(index).ui)
                config["plot_data"][scan_name] = plot_data

        print(config)
        return config

    @staticmethod
    def safe_text(line_edit: QLineEdit) -> str:
        """
        Get text from a line edit, if it is None, return empty string
        Args:
            line_edit(QLineEdit): Line edit widget

        Returns:
            str: Text from the line edit
        """
        return "" if line_edit is None else line_edit.text()

    def apply_and_close(self):
        self.apply_config()
        self.close()

    def load_config(self):
        ...


if __name__ == "__main__":
    app = QApplication([])
    main_app = ConfigDialog()
    main_app.show()
    app.exec_()
