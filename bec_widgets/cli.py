import argparse
import os
from threading import RLock

from bec_lib.core import BECMessage, MessageEndpoints, RedisConnector
from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QApplication, QMainWindow
from scan2d_plot import BECScanPlot2D

from .scan_plot import BECScanPlot


class BEC_UI(QMainWindow):
    new_scan_data = pyqtSignal("PyQt_PyObject")
    new_dap_data = pyqtSignal(dict)  # signal per proc instance?
    new_scan = pyqtSignal("PyQt_PyObject")

    def __init__(self, uipath):
        super().__init__()
        self._scan_channels = set()
        self._dap_channels = set()

        self._scan_thread = None
        self._dap_threads = []

        ui = uic.loadUi(uipath, self)

        _, fname = os.path.split(uipath)
        self.setWindowTitle(fname)

        for sp in ui.findChildren(BECScanPlot):
            for chan in (sp.x_channel, *sp.y_channel_list):
                if chan.startswith("dap."):
                    chan = chan.partition("dap.")[-1]
                    self._dap_channels.add(chan)
                else:
                    self._scan_channels.add(chan)

            sp.initialize()  # TODO: move this elsewhere?

            self.new_scan_data.connect(sp.redraw_scan)  # TODO: merge
            self.new_dap_data.connect(sp.redraw_dap)
            self.new_scan.connect(sp.clearData)

        for sp in ui.findChildren(BECScanPlot2D):
            for chan in (sp.x_channel, sp.y_channel, sp.z_channel):
                self._scan_channels.add(chan)

            sp.initialize()

            self.new_scan_data.connect(sp.redraw_scan)
            self.new_scan.connect(sp.clearData)

        # Scan setup
        self._scan_id = None
        scan_lock = RLock()

        def _scan_cb(msg):
            msg = BECMessage.ScanMessage.loads(msg.value)[0]
            with scan_lock:
                scan_id = msg.content["scanID"]
                if self._scan_id != scan_id:
                    self._scan_id = scan_id
                    self.new_scan.emit(msg)
            self.new_scan_data.emit(msg)

        bec_connector = RedisConnector("localhost:6379")

        if self._scan_channels:
            scan_readback = MessageEndpoints.scan_segment()
            self._scan_thread = bec_connector.consumer(
                topics=scan_readback,
                cb=_scan_cb,
            )
            self._scan_thread.start()

        # DAP setup
        def _proc_cb(msg):
            msg = BECMessage.ProcessedDataMessage.loads(msg.value)
            self.new_dap_data.emit(msg.content["data"])

        if self._dap_channels:
            for chan in self._dap_channels:
                proc_ep = MessageEndpoints.processed_data(chan)
                dap_thread = bec_connector.consumer(topics=proc_ep, cb=_proc_cb)
                dap_thread.start()
                self._dap_threads.append(dap_thread)

        self.show()


def main():
    parser = argparse.ArgumentParser(
        prog="bec-pyqt", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("uipath", type=str, help="Path to a BEC ui file")

    args, rem = parser.parse_known_args()

    app = QApplication(rem)
    BEC_UI(args.uipath)
    app.exec_()


if __name__ == "__main__":
    main()
