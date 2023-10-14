from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QPushButton,
    QDialog,
    QListView,
    QStandardItemModel,
    QStandardItem,
)
from bec_widgets.widgets.device_monitor import BECDeviceMonitor
from bec_widgets.bec_dispatcher import bec_dispatcher


class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self.layout = QVBoxLayout(self)
        self.listView = QListView(self)
        self.layout.addWidget(self.listView)
        self.okButton = QPushButton("OK", self)
        self.layout.addWidget(self.okButton)
        self.okButton.clicked.connect(self.accept)

    def populate_device_list(self, device_names):
        model = QStandardItemModel()
        for device_name in device_names:
            item = QStandardItem(device_name)
            item.setCheckable(True)
            model.appendRow(item)
        self.listView.setModel(model)


class PlotTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.addTabButton = QPushButton("Add Tab", self)
        self.addTabButton.clicked.connect(self.add_new_tab)
        self.setCornerWidget(self.addTabButton)

    def add_new_tab(self):
        config_dialog = ConfigDialog(self)
        config_dialog.populate_device_list(bec_dispatcher.client.device_manager.devices.keys())
        if config_dialog.exec_():
            selected_devices = [
                config_dialog.listView.model().item(i).text()
                for i in range(config_dialog.listView.model().rowCount())
                if config_dialog.listView.model().item(i).checkState()
            ]
            # Assuming device_config is a function that generates a config based on selected devices
            config = device_config(selected_devices)
            bec_device_monitor = BECDeviceMonitor(parent=self, config=config)
            self.addTab(bec_device_monitor, f"Tab {self.count() + 1}")


class ModularApp(QMainWindow):
    def __init__(self, client=None, parent=None):
        super(ModularApp, self).__init__(parent)
        self.client = bec_dispatcher.client if client is None else client
        self.init_ui()

    def init_ui(self):
        self.tabWidget = PlotTabWidget(self)
        self.setCentralWidget(self.tabWidget)


def device_config(selected_devices):
    # Generate a configuration based on the selected devices
    # This is a placeholder and should be replaced with your actual logic
    pass


if __name__ == "__main__":
    client = bec_dispatcher.client
    client.start()

    app = QApplication([])
    modularApp = ModularApp(client=client)

    window = modularApp
    window.show()
    app.exec_()
