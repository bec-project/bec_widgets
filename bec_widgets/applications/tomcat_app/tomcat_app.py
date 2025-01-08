import os
import pyqtgraph as pg
import requests
import sys

from PySide6.QtCore import Signal, Slot
from qtpy.QtCore import QSize
from qtpy.QtGui import QActionGroup, QIcon
from qtpy.QtWidgets import QApplication, QMainWindow, QStyle

import bec_widgets
from bec_lib.client import BECClient
from bec_lib.service_config import ServiceConfig
from bec_widgets.examples.general_app.web_links import BECWebLinksMixin
from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.utils.bec_dispatcher import QtRedisConnector
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.ui_loader import UILoader

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class TomcatApp(QMainWindow, BECWidget):
    select_slice = Signal()

    def __init__(self, parent=None, client=None, gui_id=None):
        super(TomcatApp, self).__init__(parent)
        BECWidget.__init__(self, client=client, gui_id=gui_id)
        ui_file_path = os.path.join(os.path.dirname(__file__), "tomcat_app.ui")
        self.load_ui(ui_file_path)

        self.resize(1280, 720)
        self.get_bec_shortcuts()

        self.bec_dispatcher.connect_slot(self.test_connection, "GPU Fastapi message")
        self.bec_dispatcher.connect_slot(self.status_update, "GPU Fastapi message")

        self.ui.slider_select.valueChanged.connect(self.select_slice_from_slider)
        self.proxy_slider = pg.SignalProxy(self.select_slice, rateLimit=2, slot=self.send_slice)

    def load_ui(self, ui_file):
        loader = UILoader(self)
        self.ui = loader.loader(ui_file)
        self.setCentralWidget(self.ui)

    def status_update(self, msg):
        status = msg["data"]["GPU SVC Status"]

        if status == "Running":
            self.ui.radio_io.setChecked(True)
        else:
            self.ui.radio_io.setChecked(False)

    # @SafeSlot(dict, dict)
    def test_connection(self, msg):
        print("Test Connection")
        print(msg)
        # print(metadata)

    def select_slice_from_slider(self, value):
        print(value)
        self.select_slice.emit()

    @Slot()
    def send_slice(self):
        value = self.ui.slider_select.value()
        requests.post(
            "http://ra-gpu-006:8000/api/v1/reco/single_slice",
            json={"slice": value, "rot_center": 0},
        )
        print(f"Sending slice {value}")


def main():  # pragma: no cover

    app = QApplication(sys.argv)
    icon = QIcon()
    icon.addFile(
        os.path.join(MODULE_PATH, "assets", "app_icons", "BEC-General-App.png"), size=QSize(48, 48)
    )
    app.setWindowIcon(icon)

    config = ServiceConfig(redis={"host": "ra-gpu-006", "port": 6379})

    client = BECClient(config=config, connector_cls=QtRedisConnector)

    main_window = TomcatApp(client=client)
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    main()
