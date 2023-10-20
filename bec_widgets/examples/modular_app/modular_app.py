import os

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QApplication, QVBoxLayout

from bec_widgets.widgets.monitor import BECDeviceMonitor

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
        {
            "plot_name": "Plot 3",
            "x": {
                "label": "Motor X",
                "signals": [{"name": "samx", "entry": "samx"}],
            },
            "y": {
                "label": "Gauss ADC",
                "signals": [{"name": "gauss_adc3", "entry": "gauss_adc3"}],
            },
        },
    ],
}

config_scan_mode = config = {
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
                        {"name": "samx", "entry": ["samx", "samx_setpoint"]},
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
                        {"name": "samx", "entry": ["samx", "samx_setpoint"]},
                    ],
                },
            },
        ],
    },
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
        self.pushButton_setting_1.clicked.connect(
            lambda: self.bec_device_monitor_1.show_config_dialog()
        )

        self.glw_2_layout = QVBoxLayout(self.glw_2)  # Create a new QVBoxLayout
        self.bec_device_monitor_2 = BECDeviceMonitor(parent=self, config=config_2)
        self.glw_2_layout.addWidget(self.bec_device_monitor_2)  # Add BECDeviceMonitor to the layout
        self.pushButton_setting_2.clicked.connect(
            lambda: self.bec_device_monitor_2.show_config_dialog()
        )

        self.glw_3_layout = QVBoxLayout(self.glw_3)  # Create a new QVBoxLayout
        self.bec_device_monitor_3 = BECDeviceMonitor(parent=self, config=config_scan_mode)
        self.glw_3_layout.addWidget(self.bec_device_monitor_3)  # Add BECDeviceMonitor to the layout
        self.pushButton_setting_3.clicked.connect(
            lambda: self.bec_device_monitor_3.show_config_dialog()
        )

    def show_config_dialog(self, monitor):
        monitor.show_config_dialog()


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
