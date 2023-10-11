import os
from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QApplication, QVBoxLayout
from bec_widgets.widgets.device_monitor import BECDeviceMonitor


class ModularApp(QMainWindow):
    def __init__(self, client=None, parent=None):
        super(ModularApp, self).__init__(parent)

        # Client and device manager from BEC
        self.client = bec_dispatcher.client if client is None else client

        # Loading UI
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "modular.ui"), self)

        self._init_plots()

    def _init_plots(self):
        self.glw_1_layout = QVBoxLayout(self.glw_1)  # Create a new QVBoxLayout
        self.bec_device_monitor = BECDeviceMonitor(parent=self)
        self.glw_1_layout.addWidget(self.bec_device_monitor)  # Add BECDeviceMonitor to the layout


if __name__ == "__main__":
    from bec_widgets.bec_dispatcher import bec_dispatcher

    # BECclient global variables
    client = bec_dispatcher.client
    client.start()

    app = QApplication([])
    modularApp = ModularApp(client=client)

    window = modularApp
    window.show()
    app.exec_()
