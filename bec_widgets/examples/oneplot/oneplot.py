from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget
from bec_lib.core import MessageEndpoints, BECMessage
from pyqtgraph.Qt import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal, Qt

from threading import RLock

import os

import numpy as np
from enum import Enum
import pyqtgraph as pg
from PyQt5 import QtGui
from PyQt5.QtCore import QThread, pyqtSlot
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QApplication, QWidget


class PlotApp(QWidget):
    def __init__(self):
        super().__init__()
        self.motor_data = None
        self.monitor_data = None
        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "oneplot.ui"), self)

        self.init_ui()

    def init_ui(self):
        self.plot = pg.PlotItem()
        self.glw.addItem(self.plot)
        self.plot.setLabel("bottom", "Motor")
        self.plot.setLabel("left", "Monitor")

    def on_dap_update(self, msg, metadata):
        ...
        # print("on_dap_update")
        # print(f'msg "on_dap_update" = {msg}')
        # self.dap_x = msg["gaussian_fit_worker_3"]["x"]
        # print(f"self.dap_x = {self.dap_x}")
        # print(metadata)

    def on_scan_segment(self, msg, metadata):
        # TODO x -> motor
        # TODO y -> monitor._hints :list
        print("on_scan_segment")
        # scanMSG = BECMessage.ScanMessage.loads(msg.value)
        self.motor_data = msg["samx"]["samx"]["value"]
        self.monitor_data = msg["gauss_bpm"]["gauss_bpm"][
            "value"
        ]  # gaussbpm._hints -> implement logic with list

        # self.scan_x =
        # scanMSG = msg.content["data"]

        # self.data_x = BECMessage.ScanMessage.loads(msg)

        # self.data_y = BECMessage.ScanMessage.loads(msg)

        # print(msg)
        print(f'msg "on_scan_segment" = {msg}')

    def on_new_scan(self, msg, metadata):
        ...
        # print("on_new_scan")
        # print(f'msg "on_new_scan" = {msg}')
        # print(metadata)


# class Controller(QThread):
#     new_scan = pyqtSignal(dict, dict)
#     scan_segment = pyqtSignal(dict, dict)
#     new_dap_data = pyqtSignal(dict, dict)
#
#     def __init__(self):
#         super().__init__()
#         self.scan_lock = RLock()
#
#     def _scan_segment_cb(msg, parent, **_kwargs):
#         msg = BECMessage.ScanMessage.loads(msg.value)
#         for i in msg:
#             with parent.scan_lock:
#                 # TODO: use ScanStatusMessage instead?
#                 scan_id = msg.content["scanID"]
#                 if parent._scan_id != scan_id:
#                     parent._scan_id = scan_id
#                     parent.new_scan.emit(msg.content, msg.metadata)
#             parent.scan_segment.emit(msg.content, msg.metadata)
#
#         scan_segment_topic = MessageEndpoints.scan_segment()
#         parent._scan_segment_thread = parent.client.connector.consumer(
#             topics=scan_segment_topic,
#             cb=_scan_segment_cb,
#         )
#         parent._scan_segment_thread.start()
#
#     @staticmethod
#     def _scan_segment_callback(msg, *, parent, **_kwargs) -> None:
#         scanMSG = BECMessage.ScanMessage.loads(msg.value)
#         self.data_x

if __name__ == "__main__":
    # from bec_lib import BECClient
    from bec_widgets import ctrl_c
    from bec_widgets.bec_dispatcher import bec_dispatcher

    client = bec_dispatcher.client
    client.start()

    dev = client.device_manager.devices
    scans = client.scans
    queue = client.queue

    app = QApplication([])

    plotApp = PlotApp()

    bec_dispatcher.connect_dap_slot(plotApp.on_dap_update, "gaussian_fit_worker_3")
    bec_dispatcher.connect_slot(plotApp.on_scan_segment, MessageEndpoints.scan_segment())
    bec_dispatcher.new_scan.connect(plotApp.on_new_scan)  # TODO check if works!
    # bec_dispatcher.connect_slot(plotApp.on_new_scan,)
    ctrl_c.setup(app)

    window = plotApp
    window.show()
    app.exec_()
