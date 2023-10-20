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

        self.signal_count = 1  # TODO decide if useful

        self.tab_ui_objects = {}  # []  # Create a list to hold the Tab_Ui_Form objects

        # Connect the buttons inside the dialog
        # self.pushButton_add_new_plot.clicked.connect(self.add_new_plot)  # TODO move to tabs

        # Connect the Ok/Apply/Cancel buttons
        self.pushButton_ok.clicked.connect(self.apply_and_close)
        self.pushButton_apply.clicked.connect(self.apply_config)
        self.pushButton_cancel.clicked.connect(self.close)

        # Scan types
        self.pushButton_new_scan_type.clicked.connect(self.add_new_scan_type)

        self.add_new_plot()  # add initial first plot tab

        if default_config is not None:
            self.load_config(default_config)

    def add_new_scan_type(self):
        scan_type_name = self.lineEdit_scan_type.text()
        if not scan_type_name:
            return

        new_scan_tab = QWidget()
        new_scan_tab_layout = QVBoxLayout(new_scan_tab)
        new_tabWidget_plots = QTabWidget()
        new_tabWidget_plots.setObjectName("tabWidget_plots")

        new_scan_tab_layout.addWidget(new_tabWidget_plots)

        self.tabWidget_scan_types.addTab(new_scan_tab, scan_type_name)
        # self.tab_ui_objects[scan_type_name] = []

        # Store tab structure in the dict
        self.tab_ui_objects[scan_type_name] = {"tab_widget": new_scan_tab, "plots": []}

        # Set the newly created scan tab as the current tab
        self.tabWidget_scan_types.setCurrentWidget(new_scan_tab)

        # Generate the first plot tab
        self.add_new_plot()

    def add_new_plot(self):
        # Get the currently selected scan tab
        current_scan_type_index = self.tabWidget_scan_types.currentIndex()
        if current_scan_type_index == -1:
            return  # Exit if no scan tab is selected

        # Get the tab widget of the currently selected scan tab
        current_scan_tab_widget = self.tabWidget_scan_types.widget(current_scan_type_index)

        # Get the QTabWidget object from the current scan tab widget
        current_tabWidget_plots = current_scan_tab_widget.findChild(QTabWidget, "tabWidget_plots")
        if current_tabWidget_plots is None:
            return  # Exit if the QTabWidget object is not found

        # Create a new plot tab
        new_plot_tab = QWidget()
        new_plot_tab_ui = Tab_Ui_Form()
        new_plot_tab_ui.setupUi(new_plot_tab)

        # Hook the buttons in the new plot tab
        self.hook_tab_buttons(new_plot_tab_ui)

        # Add this new plot tab to the currently selected scan tab's tab widget
        current_tabWidget_plots.addTab(new_plot_tab, f"Plot {current_tabWidget_plots.count() + 1}")

        # Store tab structure in the dict
        scan_type_name = self.tabWidget_scan_types.tabText(current_scan_type_index)
        if scan_type_name not in self.tab_ui_objects:
            self.tab_ui_objects[scan_type_name] = {
                "tab_widget": current_scan_tab_widget,
                "plots": [],
            }
        self.tab_ui_objects[scan_type_name]["plots"].append(new_plot_tab_ui)

        # Connect tab buttons # TODO decide what has to be hooked
        # self.hook_tab_buttons(new_plot_tab_ui)

    def hook_tab_buttons(self, tab_ui_object):
        tab_ui_object.pushButton_y_new.clicked.connect(
            lambda: self.add_new_signal(tab_ui_object.tableWidget_y_signals)
        )
        tab_ui_object.pushButton_remove_current_plot.clicked.connect(
            lambda: self.remove_current_plot(tab_ui_object)
        )
        tab_ui_object.pushButton_add_new_plot.clicked.connect(self.add_new_plot)

    def remove_current_plot(self, tab_ui_object):
        current_scan_type_index = self.tabWidget_scan_types.currentIndex()
        if current_scan_type_index == -1:
            return  # Exit if no scan tab is selected

        # Get the tab widget of the currently selected scan tab
        current_scan_tab_widget = self.tab_ui_objects[
            self.tabWidget_scan_types.tabText(current_scan_type_index)
        ]["tab_widget"].findChild(QTabWidget, "tabWidget_plots")

        current_index = current_scan_tab_widget.currentIndex()
        if current_index != -1:  # Ensure there is a tab to remove
            current_scan_tab_widget.removeTab(current_index)
            del self.tab_ui_objects[self.tabWidget_scan_types.tabText(current_scan_type_index)][
                "plots"
            ][current_index]

    def add_new_signal(self, tableWidget_y_signals):
        row_position = tableWidget_y_signals.rowCount()
        tableWidget_y_signals.insertRow(row_position)
        tableWidget_y_signals.setItem(row_position, 0, QTableWidgetItem(""))
        tableWidget_y_signals.setItem(row_position, 1, QTableWidgetItem(""))

    def apply_configuration(self):
        config = {
            "plot_settings": {
                "background_color": self.comboBox_appearance.currentText(),
                "num_columns": self.spinBox_n_column.value(),
                "colormap": self.comboBox_colormap.currentText(),
                "scan_types": self.comboBox_scanTypes.currentText() == "Enabled",
            },
            "plot_data": [],
        }

        for index in range(self.tabWidget_plots.count()):
            # tab = self.tabWidget_plots.widget(index) #TODO can be removed
            ui_object = self.tab_ui_objects[index]
            table = ui_object.tableWidget_y_signals
            signals = [
                {
                    "name": self.safe_text(table.item(row, 0)),
                    "entry": self.safe_text(table.item(row, 1)),
                }
                for row in range(table.rowCount())
            ]

            plot_config = {
                "plot_name": self.safe_text(ui_object.lineEdit_plot_title),
                "x": {
                    "label": self.safe_text(ui_object.lineEdit_x_label),
                    "signals": [
                        {
                            "name": self.safe_text(ui_object.lineEdit_x_name),
                            "entry": self.safe_text(ui_object.lineEdit_x_entry),
                        }
                    ],
                },
                "y": {
                    "label": self.safe_text(ui_object.lineEdit_y_label),
                    "signals": signals,
                },
            }
            config["plot_data"].append(plot_config)

        print(config)
        return config

    def load_config(self, config):
        plot_settings = config.get("plot_settings", {})
        plot_data = config.get("plot_data", [])

        # Set plot settings in the dialog
        self.comboBox_appearance.setCurrentText(
            plot_settings.get("background_color", "")
        )  # TODO implement more robust logic
        self.spinBox_n_column.setValue(plot_settings.get("num_columns", 1))
        self.comboBox_colormap.setCurrentText(plot_settings.get("colormap", ""))
        self.comboBox_scanTypes.setCurrentText(
            "Enabled" if plot_settings.get("scan_types", False) else "Disabled"
        )

        # Clear existing tabs
        self.tabWidget_plots.clear()
        self.tab_ui_objects = []

        # Set plot data in the dialog
        for plot_config in plot_data:
            new_tab_widget = QWidget()
            new_tab = Tab_Ui_Form()
            new_tab.setupUi(new_tab_widget)

            # Set tab values
            new_tab.lineEdit_plot_title.setText(plot_config.get("plot_name", ""))
            x_config = plot_config.get("x", {})
            new_tab.lineEdit_x_label.setText(x_config.get("label", ""))
            x_signals = x_config.get("signals", [{}])[0]  # Assuming at least one x signal
            new_tab.lineEdit_x_name.setText(x_signals.get("name", ""))
            new_tab.lineEdit_x_entry.setText(x_signals.get("entry", ""))

            y_config = plot_config.get("y", {})
            new_tab.lineEdit_y_label.setText(y_config.get("label", ""))
            y_signals = y_config.get("signals", [])
            for y_signal in y_signals:
                row_position = new_tab.tableWidget_y_signals.rowCount()
                new_tab.tableWidget_y_signals.insertRow(row_position)
                new_tab.tableWidget_y_signals.setItem(
                    row_position, 0, QTableWidgetItem(y_signal.get("name", ""))
                )
                new_tab.tableWidget_y_signals.setItem(
                    row_position, 1, QTableWidgetItem(y_signal.get("entry", ""))
                )

            # Connect tab buttons
            self.hook_tab_buttons(new_tab)

            # Add tab to dialog
            new_tab_name = f"Plot {self.tabWidget_plots.count() + 1}"
            self.tabWidget_plots.addTab(new_tab_widget, new_tab_name)
            self.tab_ui_objects.append(new_tab)

    def apply_config(self):
        config_to_emit = self.apply_configuration()
        self.config_updated.emit(config_to_emit)

    def apply_and_close(self):
        self.apply_config()
        self.close()

    @staticmethod
    def safe_text(line_edit):
        return "" if line_edit is None else line_edit.text()


if __name__ == "__main__":
    app = QApplication([])
    main_app = ConfigDialog()
    main_app.show()
    app.exec_()
