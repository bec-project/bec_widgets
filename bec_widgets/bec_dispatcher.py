from collections import defaultdict
from threading import RLock

from bec_lib.core import BECMessage, MessageEndpoints, RedisConnector
from PyQt5.QtCore import QObject, pyqtSignal

bec_connector = RedisConnector("localhost:6379")


class _BECDispatcher(QObject):
    scan_segment = pyqtSignal("PyQt_PyObject")
    new_dap_data = pyqtSignal(dict)
    new_scan = pyqtSignal("PyQt_PyObject")

    def __init__(self):
        super().__init__()
        # TODO: dap might not be a good fit to predefined slots, fix this inconsistency
        self._slot_signal_map = {
            "on_scan_segment": self.scan_segment,
            "on_new_scan": self.new_scan,
        }
        self._daps = defaultdict(set)

        self._scan_id = None
        scan_lock = RLock()
        self._dap_threads = []

        def _scan_cb(msg):
            msg = BECMessage.ScanMessage.loads(msg.value)[0]
            with scan_lock:
                # TODO: use ScanStatusMessage instead?
                scan_id = msg.content["scanID"]
                if self._scan_id != scan_id:
                    self._scan_id = scan_id
                    self.new_scan.emit(msg)
            self.scan_segment.emit(msg)

        scan_readback = MessageEndpoints.scan_segment()
        self._scan_thread = bec_connector.consumer(
            topics=scan_readback,
            cb=_scan_cb,
        )
        self._scan_thread.start()

    def connect(self, widget):
        for slot_name, signal in self._slot_signal_map.items():
            slot = getattr(widget, slot_name, None)
            if callable(slot):
                signal.connect(slot)

    def connect_dap(self, slot, dap_name):
        if dap_name not in self._daps:

            def _dap_cb(msg):
                msg = BECMessage.ProcessedDataMessage.loads(msg.value)
                self.new_dap_data.emit(msg.content["data"])

            dap_ep = MessageEndpoints.processed_data(dap_name)
            dap_thread = bec_connector.consumer(topics=dap_ep, cb=_dap_cb)
            dap_thread.start()
            self._dap_threads.append(dap_thread)

            self.new_dap_data.connect(slot)
            self._daps[dap_name].add(slot)

        else:
            # connect slot if it's not yet connected
            if slot not in self._daps[dap_name]:
                self._daps[dap_name].add(slot)
                self.new_dap_data.connect(slot)


bec_dispatcher = _BECDispatcher()
