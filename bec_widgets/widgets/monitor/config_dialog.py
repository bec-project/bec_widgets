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

from bec_widgets.qt_utils.yaml_dialog import load_yaml, save_yaml

current_path = os.path.dirname(__file__)
Ui_Form, BaseClass = uic.loadUiType(os.path.join(current_path, "config_dialog.ui"))
Tab_Ui_Form, Tab_BaseClass = uic.loadUiType(os.path.join(current_path, "tab_template.ui"))
# test configs #TODO delete after loading works

config_default = {
    "plot_settings": {
        "background_color": "black",
        "num_columns": 1,
        "colormap": "plasma",
        "scan_types": False,
    },
    "plot_data": [
        {
            "plot_name": "BPM4i plots vs samx",
            "x": {
                "label": "Motor Y",
                "signals": [{"name": "samx", "entry": "samx"}],
            },
            "y": {
                "label": "bpm4i",
                "signals": [{"name": "bpm4i", "entry": "bpm4i"}],
            },
        },
        {
            "plot_name": "Gauss plots vs samx",
            "x": {
                "label": "Motor X",
                "signals": [{"name": "samx", "entry": "samx"}],
            },
            "y": {
                "label": "Gauss",
                "signals": [
                    {"name": "gauss_bpm", "entry": "gauss_bpm"},
                    {"name": "gauss_acd1", "entry": "gauss_adc1"},
                    {"name": "gauss_acd2", "entry": "gauss_adc2"},
                ],
            },
        },
    ],
}

config_scan = {
    "plot_settings": {
        "background_color": "white",
        "num_columns": 3,
        "colormap": "plasma",
        "scan_types": True,
    },
    "plot_data": {
        "grid_scan": [
            {
                "plot_name": "Grid plot 1",
                "x": {"label": "Motor X", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "BPM",
                    "signals": [
                        {"name": "gauss_bpm", "entry": "gauss_bpm"},
                        {"name": "gauss_adc1", "entry": "gauss_adc1"},
                    ],
                },
            },
            {
                "plot_name": "Grid plot 2",
                "x": {"label": "Motor X", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "BPM",
                    "signals": [
                        {"name": "gauss_bpm", "entry": "gauss_bpm"},
                        {"name": "gauss_adc1", "entry": "gauss_adc1"},
                    ],
                },
            },
            {
                "plot_name": "Grid plot 3",
                "x": {"label": "Motor Y", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "BPM",
                    "signals": [{"name": "gauss_bpm", "entry": "gauss_bpm"}],
                },
            },
            {
                "plot_name": "Grid plot 4",
                "x": {"label": "Motor Y", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "BPM",
                    "signals": [{"name": "gauss_adc3", "entry": "gauss_adc3"}],
                },
            },
        ],
        "line_scan": [
            {
                "plot_name": "BPM plot",
                "x": {"label": "Motor X", "signals": [{"name": "samx"}]},
                "y": {
                    "label": "BPM",
                    "signals": [
                        {"name": "gauss_bpm", "entry": "gauss_bpm"},
                        {"name": "gauss_adc1", "entry": "gauss_adc1"},
                        {"name": "gauss_adc2", "entry": "gauss_adc2"},
                    ],
                },
            },
            {
                "plot_name": "Multi",
                "x": {"label": "Motor X", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "Multi",
                    "signals": [
                        {"name": "gauss_bpm", "entry": "gauss_bpm"},
                        {"name": "samx", "entry": "samx"},
                    ],
                },
            },
            {
                "plot_name": "Multi",
                "x": {"label": "Motor X", "signals": [{"name": "samx", "entry": "samx"}]},
                "y": {
                    "label": "Multi",
                    "signals": [
                        {"name": "gauss_bpm", "entry": "gauss_bpm"},
                        {"name": "samx", "entry": "samx"},
                    ],
                },
            },
        ],
    },
}


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
            lambda: self.generate_empty_scan_tab(
                self.tabWidget_scan_types, self.lineEdit_scan_type.text()
            )
        )

        # Load/save yaml file buttons
        self.pushButton_import.clicked.connect(self.load_config_from_yaml)
        self.pushButton_export.clicked.connect(self.save_config_to_yaml)

        # Scan Types changed
        self.comboBox_scanTypes.currentIndexChanged.connect(self._init_default)

        # Make scan tabs closable
        self.tabWidget_scan_types.tabCloseRequested.connect(self.handle_tab_close_request)

        # Init functions to make a default dialog
        if default_config is None:
            self._init_default()
        else:
            self.load_config(default_config)

    def _init_default(self):
        """Init default dialog"""

        if self.comboBox_scanTypes.currentText() == "Disabled":  # Default mode
            self.add_new_scan(self.tabWidget_scan_types, "Default")
            self.add_new_plot(self.tabWidget_scan_types.widget(0))
            self.pushButton_new_scan_type.setEnabled(False)
            self.lineEdit_scan_type.setEnabled(False)
        else:  # Scan mode with clear tab
            self.pushButton_new_scan_type.setEnabled(True)
            self.lineEdit_scan_type.setEnabled(True)
            self.tabWidget_scan_types.clear()

    def add_new_scan(
        self, parent_tab: QTabWidget, scan_name: str, closable: bool = False
    ) -> QWidget:
        """
        Add a new scan tab to the parent tab widget

        Args:
            parent_tab(QTabWidget): Parent tab widget, where to add scan tab
            scan_name(str): Scan name
            closable(bool): If True, the scan tab will be closable

        Returns:
            scan_tab(QWidget): Scan tab widget
        """

        # Create a new scan tab
        scan_tab = QWidget()
        scan_tab_layout = QVBoxLayout(scan_tab)

        # Set a tab widget for plots
        tabWidget_plots = QTabWidget()
        tabWidget_plots.setObjectName("tabWidget_plots")  # TODO decide if needed to give a name
        tabWidget_plots.setTabsClosable(True)
        tabWidget_plots.tabCloseRequested.connect(self.handle_tab_close_request)
        scan_tab_layout.addWidget(tabWidget_plots)

        # Add scan tab
        parent_tab.addTab(scan_tab, scan_name)

        # Make tabs closable
        if closable:
            parent_tab.setTabsClosable(closable)

        return scan_tab

    def add_new_plot(self, scan_tab: QWidget) -> QWidget:
        """
        Add a new plot tab to the scan tab

        Args:
            scan_tab (QWidget): Scan tab widget

        Returns:
            plot_tab (QWidget): Plot tab
        """

        # Create a new plot tab from .ui template
        plot_tab = QWidget()
        plot_tab_ui = Tab_Ui_Form()
        plot_tab_ui.setupUi(plot_tab)
        plot_tab.ui = plot_tab_ui

        # Add plot to current scan tab
        tabWidget_plots = scan_tab.findChild(
            QTabWidget, "tabWidget_plots"
        )  # TODO decide if putting name is needed
        plot_name = f"Plot {tabWidget_plots.count() + 1}"
        tabWidget_plots.addTab(plot_tab, plot_name)

        # Hook signal
        self.hook_plot_tab_signals(scan_tab=scan_tab, plot_tab=plot_tab.ui)

        return plot_tab

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
        """
        Add a new signal to the table

        Args:
            table(QTableWidget): Table widget
        """

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
        if parent_tab.count() > 1:  # ensure there is at least one tab
            parent_tab.removeTab(index)

    def generate_empty_scan_tab(self, parent_tab: QTabWidget, scan_name: str):
        """
        Generate an empty scan tab

        Args:
            parent_tab (QTabWidget): Parent tab widget where to add the scan tab
            scan_name(str): name of the scan tab
        """

        scan_tab = self.add_new_scan(parent_tab, scan_name, closable=True)
        self.add_new_plot(scan_tab)

    def get_plot_config(self, plot_tab: QWidget) -> dict:
        """
        Get plot configuration from the plot tab adn send it as dict

        Args:
            plot_tab(QWidget): Plot tab widget

        Returns:
            dict: Plot configuration
        """

        ui = plot_tab.ui
        table = ui.tableWidget_y_signals
        signals = [
            {
                "name": self.safe_text(table.item(row, 0)),
                "entry": self.safe_text(table.item(row, 1)),
            }
            for row in range(table.rowCount())
        ]

        plot_data = {
            "plot_name": self.safe_text(ui.lineEdit_plot_title),
            "x": {
                "label": self.safe_text(ui.lineEdit_x_label),
                "signals": [
                    {
                        "name": self.safe_text(ui.lineEdit_x_name),
                        "entry": self.safe_text(ui.lineEdit_x_entry),
                    }
                ],
            },
            "y": {
                "label": self.safe_text(ui.lineEdit_y_label),
                "signals": signals,
            },
        }

        return plot_data

    def apply_config(self) -> dict:
        """
        Apply configuration from the whole configuration window

        Returns:
            dict: Current configuration

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
            plot_tab = self.tabWidget_scan_types.widget(0).findChild(QTabWidget)
            for index in range(plot_tab.count()):
                plot_data = self.get_plot_config(plot_tab.widget(index))
                config["plot_data"].append(plot_data)

        # Iterate through the scan tabs - Scan mode
        elif config["plot_settings"]["scan_types"] == True:
            # Iterate through the scan tabs
            for index in range(self.tabWidget_scan_types.count()):
                scan_tab = self.tabWidget_scan_types.widget(index)
                scan_name = self.tabWidget_scan_types.tabText(index)
                plot_tab = scan_tab.findChild(QTabWidget)
                config["plot_data"][scan_name] = []
                # Iterate through the plot tabs
                for index in range(plot_tab.count()):
                    plot_data = self.get_plot_config(plot_tab.widget(index))
                    config["plot_data"][scan_name].append(plot_data)

        return config

    def load_config(self, config: dict) -> None:
        """
        Load configuration to the configuration window

        Args:
            config(dict): Configuration to be loaded
        """

        # Plot setting General box
        plot_settings = config.get("plot_settings", {})

        self.comboBox_appearance.setCurrentText(plot_settings.get("background_color", "black"))
        self.spinBox_n_column.setValue(plot_settings.get("num_columns", 1))
        self.comboBox_colormap.setCurrentText(plot_settings.get("colormap", "magma"))
        self.comboBox_scanTypes.setCurrentText(
            "Enabled" if plot_settings.get("scan_types", False) else "Disabled"
        )

        # Clear exiting scan tabs
        self.tabWidget_scan_types.clear()

        # Get what mode is active - scan vs default device monitor
        scan_mode = plot_settings.get("scan_types", False)

        if scan_mode is False:  # default mode:
            plot_data = config.get("plot_data", [])
            self.add_new_scan(self.tabWidget_scan_types, "Default")
            for plot_config in plot_data:  # Create plot tab for each plot and populate GUI
                plot = self.add_new_plot(self.tabWidget_scan_types.widget(0))
                self.load_plot_setting(plot, plot_config)
        elif scan_mode is True:  # scan mode
            plot_data = config.get("plot_data", {})
            for scan_name, scan_config in plot_data.items():
                scan_tab = self.add_new_scan(self.tabWidget_scan_types, scan_name)
                for plot_config in scan_config:
                    plot = self.add_new_plot(scan_tab)
                    self.load_plot_setting(plot, plot_config)

    def load_plot_setting(self, plot: QWidget, plot_config: dict) -> None:
        """
        Load plot setting from config

        Args:
            plot (QWidget): plot tab widget
            plot_config (dict): config for single plot tab
        """
        x_config = plot_config.get("x", {})
        x_signals = x_config.get("signals", [{}])[0]  # Assuming at least one x signal
        y_config = plot_config.get("y", {})
        y_signals = y_config.get("signals", [])

        # LabelBox
        plot.ui.lineEdit_plot_title.setText(plot_config.get("plot_name", ""))
        plot.ui.lineEdit_x_label.setText(x_config.get("label", ""))
        plot.ui.lineEdit_y_label.setText(y_config.get("label", ""))

        # X axis
        plot.ui.lineEdit_x_name.setText(x_signals.get("name", ""))
        plot.ui.lineEdit_x_entry.setText(x_signals.get("entry", ""))

        # Y axis
        for y_signal in y_signals:
            row_position = plot.ui.tableWidget_y_signals.rowCount()
            plot.ui.tableWidget_y_signals.insertRow(row_position)
            plot.ui.tableWidget_y_signals.setItem(
                row_position, 0, QTableWidgetItem(y_signal.get("name", ""))
            )
            plot.ui.tableWidget_y_signals.setItem(
                row_position, 1, QTableWidgetItem(y_signal.get("entry", ""))
            )

    def load_config_from_yaml(self):
        """
        Load configuration from yaml file
        """
        config = load_yaml(self)
        self.load_config(config)

    def save_config_to_yaml(self):
        """
        Save configuration to yaml file
        """
        config = self.apply_config()
        save_yaml(self, config)

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
        new_config = self.apply_config()
        self.config_updated.emit(new_config)
        self.close()


if __name__ == "__main__":
    app = QApplication([])
    main_app = ConfigDialog()
    main_app.show()
    app.exec_()
