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

        self.tab_ui_objects = []  # Create a list to hold the Tab_Ui_Form objects

        # Connect the buttons inside the dialog
        self.pushButton_add_new_plot.clicked.connect(self.add_new_plot)

        # Connect the Ok/Apply/Cancel buttons
        self.pushButton_ok.clicked.connect(self.apply_and_close)
        self.pushButton_apply.clicked.connect(self.apply_config)
        self.pushButton_cancel.clicked.connect(self.close)

        self.add_new_plot()  # add initial first plot tab

        if default_config is not None:
            self.load_config(default_config)

    def add_new_plot(self):
        # Set tabs
        new_tab_widget = QWidget()
        new_tab = Tab_Ui_Form()
        new_tab.setupUi(new_tab_widget)

        # Connect tab buttons
        self.hook_tab_buttons(new_tab)

        # Tab header name
        new_tab_name = f"Plot {self.tabWidget_plots.count() + 1}"

        # Add new tab
        self.tabWidget_plots.addTab(
            new_tab_widget, new_tab_name
        )  # Add the new QWidget as a new tab
        self.tab_ui_objects.append(new_tab)  # Append the Tab_Ui_Form object to the list

    def hook_tab_buttons(self, tab_ui_object):
        tab_ui_object.pushButton_y_new.clicked.connect(
            lambda: self.add_new_signal(tab_ui_object.tableWidget_y_signals)
        )
        tab_ui_object.pushButton_remove_current_plot.clicked.connect(self.remove_current_plot)

    def remove_current_plot(self):
        current_index = self.tabWidget_plots.currentIndex()
        if current_index != -1:  # Ensure there is a tab to remove
            self.tabWidget_plots.removeTab(current_index)
            del self.tab_ui_objects[current_index]

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
