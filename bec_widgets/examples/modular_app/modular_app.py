import os

from qtpy import uic
from qtpy.QtWidgets import QMainWindow, QApplication

from bec_widgets.widgets import BECMonitor

# some default configs for demonstration purposes
CONFIG_SIMPLE = {
    "plot_settings": {
        "background_color": "black",
        "num_columns": 2,
        "colormap": "plasma",
        "scan_types": False,
    },
    "plot_data": [
        {
            "plot_name": "BPM4i plots vs samx",
            "x_label": "Motor X",
            "y_label": "bpm4i",
            "sources": [
                {
                    "type": "scan_segment",
                    "signals": {
                        "x": [{"name": "samx"}],
                        "y": [{"name": "bpm4i", "entry": "bpm4i"}],
                    },
                },
                # {
                #     "type": "history",
                #     "signals": {
                #         "x": [{"name": "samx"}],
                #         "y": [{"name": "bpm4i", "entry": "bpm4i"}],
                #     },
                # },
                # {
                #     "type": "dap",
                #     'worker':'some_worker',
                #     "signals": {
                #         "x": [{"name": "samx"}],
                #         "y": [{"name": "bpm4i", "entry": "bpm4i"}],
                #     },
                # },
            ],
        },
        {
            "plot_name": "Gauss plots vs samx",
            "x_label": "Motor X",
            "y_label": "Gauss",
            "sources": [
                {
                    "type": "scan_segment",
                    "signals": {
                        "x": [{"name": "samx", "entry": "samx"}],
                        "y": [{"name": "gauss_bpm"}, {"name": "gauss_adc1"}],
                    },
                }
            ],
        },
    ],
}


CONFIG_SCAN_MODE = {
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
                "x_label": "Motor X",
                "y_label": "BPM",
                "sources": [
                    {
                        "type": "scan_segment",
                        "signals": {
                            "x": [{"name": "samx", "entry": "samx"}],
                            "y": [{"name": "gauss_bpm"}],
                        },
                    }
                ],
            },
            {
                "plot_name": "Grid plot 2",
                "x_label": "Motor X",
                "y_label": "BPM",
                "sources": [
                    {
                        "type": "scan_segment",
                        "signals": {
                            "x": [{"name": "samx", "entry": "samx"}],
                            "y": [{"name": "gauss_adc1"}],
                        },
                    }
                ],
            },
            {
                "plot_name": "Grid plot 3",
                "x_label": "Motor X",
                "y_label": "BPM",
                "sources": [
                    {
                        "type": "scan_segment",
                        "signals": {
                            "x": [{"name": "samy"}],
                            "y": [{"name": "gauss_adc2"}],
                        },
                    }
                ],
            },
            {
                "plot_name": "Grid plot 4",
                "x_label": "Motor X",
                "y_label": "BPM",
                "sources": [
                    {
                        "type": "scan_segment",
                        "signals": {
                            "x": [{"name": "samy", "entry": "samy"}],
                            "y": [{"name": "gauss_adc3"}],
                        },
                    }
                ],
            },
        ],
        "line_scan": [
            {
                "plot_name": "BPM plots vs samx",
                "x_label": "Motor X",
                "y_label": "Gauss",
                "sources": [
                    {
                        "type": "scan_segment",
                        "signals": {
                            "x": [{"name": "samx", "entry": "samx"}],
                            "y": [{"name": "bpm4i"}],
                        },
                    }
                ],
            },
            {
                "plot_name": "Gauss plots vs samx",
                "x_label": "Motor X",
                "y_label": "Gauss",
                "sources": [
                    {
                        "type": "scan_segment",
                        "signals": {
                            "x": [{"name": "samx", "entry": "samx"}],
                            "y": [{"name": "gauss_bpm"}, {"name": "gauss_adc1"}],
                        },
                    }
                ],
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
        """Initialize plots and connect the buttons to the config dialogs"""
        plots = [self.plot_1, self.plot_2, self.plot_3]
        configs = [CONFIG_SIMPLE, CONFIG_SCAN_MODE, CONFIG_SCAN_MODE]
        buttons = [self.pushButton_setting_1, self.pushButton_setting_2, self.pushButton_setting_3]

        # hook plots, configs and buttons together
        for plot, config, button in zip(plots, configs, buttons):
            plot.on_config_update(config)
            button.clicked.connect(plot.show_config_dialog)


if __name__ == "__main__":
    from bec_widgets.utils.bec_dispatcher import bec_dispatcher

    # BECclient global variables
    client = bec_dispatcher.client
    client.start()

    app = QApplication([])
    modularApp = ModularApp(client=client)

    window = modularApp
    window.show()
    app.exec()
