from PyQt5 import uic
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
)

Ui_Form, BaseClass = uic.loadUiType("config_dialog.ui")
Tab_Ui_Form, Tab_BaseClass = uic.loadUiType("tab_template.ui")


class MainApp(QWidget, Ui_Form):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.signal_count = 1  # TODO decide if useful

        self.tab_ui_objects = []  # Create a list to hold the Tab_Ui_Form objects

        # Connect the buttons
        self.pushButton_add_new_plot.clicked.connect(self.add_new_plot)
        self.pushButton_ok.clicked.connect(self.get_configuration)

        self.add_new_plot()  # add initial first plot tab

    def add_new_plot(self):
        # Set tabs
        new_tab_widget = QWidget()
        new_tab = Tab_Ui_Form()
        new_tab.setupUi(new_tab_widget)

        # Tab Signals
        new_tab.pushButton_y_new.clicked.connect(
            lambda: self.add_new_signal(new_tab.tableWidget_y_signals)
        )
        new_tab_name = f"Plot {self.tabWidget_plots.count() + 1}"
        self.tabWidget_plots.addTab(
            new_tab_widget, new_tab_name
        )  # Add the new QWidget as a new tab
        self.tab_ui_objects.append(new_tab)  # Append the Tab_Ui_Form object to the list

    def add_new_signal(self, tableWidget_y_signals):
        row_position = tableWidget_y_signals.rowCount()
        tableWidget_y_signals.insertRow(row_position)
        tableWidget_y_signals.setItem(row_position, 0, QTableWidgetItem(""))
        tableWidget_y_signals.setItem(row_position, 1, QTableWidgetItem(""))

    def get_configuration(self):
        config = {
            "plot_settings": {
                "background_color": "black",
                "num_columns": self.spinBox.value(),
                "colormap": self.comboBox_2.currentText(),
                "scan_types": self.comboBox.currentText() == "Enabled",
            },
            "plot_data": [],
        }

        for index in range(self.tabWidget_plots.count()):
            tab = self.tabWidget_plots.widget(index)
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

    @staticmethod
    def safe_text(line_edit):
        return "" if line_edit is None else line_edit.text()


if __name__ == "__main__":
    app = QApplication([])
    main_app = MainApp()
    main_app.show()
    app.exec_()
