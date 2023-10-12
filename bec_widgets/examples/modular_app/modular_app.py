import os
from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QApplication, QVBoxLayout
from bec_widgets.widgets.device_monitor import BECDeviceMonitor

config_1 = {
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
                "signals": [{"name": "gauss_bpm", "entry": "gauss_bpm"}],
            },
        },
    ],
}

config_2 = {
    "plot_settings": {
        "background_color": "black",
        "num_columns": 2,
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
                "signals": [{"name": "samy", "entry": "samy"}],
            },
        },
        {
            "plot_name": "Gauss plots vs samx",
            "x": {
                "label": "Motor X",
                "signals": [{"name": "samx", "entry": "samx"}],
            },
            "y": {
                "label": "Gauss ADC",
                "signals": [{"name": "gauss_adc1", "entry": "gauss_adc1"}],
            },
        },
    ],
}


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
        self.bec_device_monitor_1 = BECDeviceMonitor(parent=self, config=config_1)
        self.glw_1_layout.addWidget(self.bec_device_monitor_1)  # Add BECDeviceMonitor to the layout

        self.glw_2_layout = QVBoxLayout(self.glw_2)  # Create a new QVBoxLayout
        self.bec_device_monitor_2 = BECDeviceMonitor(parent=self, config=config_2)
        self.glw_2_layout.addWidget(self.bec_device_monitor_2)  # Add BECDeviceMonitor to the layout


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
