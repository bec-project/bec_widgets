from dataclasses import dataclass
from threading import RLock

from bec_lib import BECClient
from bec_lib.core import BECMessage, MessageEndpoints
from bec_lib.core.redis_connector import RedisConsumerThreaded
from PyQt5.QtCore import QObject, pyqtSignal


@dataclass
class _BECDap:
    """Utility class to keep track of slots associated with a particular dap redis consumer"""

    consumer: RedisConsumerThreaded
    slots = set()


class _BECDispatcher(QObject):
    new_scan = pyqtSignal(dict, dict)
    scan_segment = pyqtSignal(dict, dict)
    new_dap_data = pyqtSignal(dict)

    new_projection_id = pyqtSignal(dict)
    new_projection_data = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.client = BECClient()
        self.client.start()

        self._slot_signal_map = {
            "on_scan_segment": self.scan_segment,
            "on_new_scan": self.new_scan,
        }
        self._daps = {}

        self._scan_id = None
        scan_lock = RLock()

        # self.new_projection_id.connect(self.new_projection_data)

        def _scan_segment_cb(scan_segment, metadata):
            with scan_lock:
                # TODO: use ScanStatusMessage instead?
                scan_id = metadata["scanID"]
                if self._scan_id != scan_id:
                    self._scan_id = scan_id
                    self.new_scan.emit(scan_segment, metadata)
            self.scan_segment.emit(scan_segment, metadata)

        self.client.callbacks.register("scan_segment", _scan_segment_cb, sync=False)

    def connect(self, widget):
        for slot_name, signal in self._slot_signal_map.items():
            slot = getattr(widget, slot_name, None)
            if callable(slot):
                signal.connect(slot)

    def connect_dap_slot(self, slot, dap_name):
        if dap_name not in self._daps:
            # create a new consumer and connect slot

            def _dap_cb(msg):
                msg = BECMessage.ProcessedDataMessage.loads(msg.value)
                self.new_dap_data.emit(msg.content["data"])

            dap_ep = MessageEndpoints.processed_data(dap_name)
            consumer = self.client.connector.consumer(topics=dap_ep, cb=_dap_cb)
            consumer.start()

            self.new_dap_data.connect(slot)

            self._daps[dap_name] = _BECDap(consumer)
            self._daps[dap_name].slots.add(slot)

        else:
            # connect slot if it's not yet connected
            if slot not in self._daps[dap_name].slots:
                self.new_dap_data.connect(slot)
                self._daps[dap_name].slots.add(slot)

    def disconnect_dap_slot(self, slot, dap_name):
        if dap_name not in self._daps:
            return

        if slot not in self._daps[dap_name].slots:
            return

        self.new_dap_data.disconnect(slot)
        self._daps[dap_name].slots.remove(slot)

        if not self._daps[dap_name].slots:
            # shutdown consumer if there are no more connected slots
            self._daps[dap_name].consumer.shutdown()
            del self._daps[dap_name]

    # def connect_proj_data(self, slot):
    #     keys = self.client.producer.keys("px_stream/projection_*")
    #     keys = keys or []
    #
    #     def _dap_cb(msg):
    #         msg = BECMessage.DeviceMessage.loads(msg.value)
    #         self.new_projection_data.emit(msg.content["data"])
    #
    #     proj_numbers = set(key.decode().split("px_stream/projection_")[1].split("/")[0] for key in keys)
    #     last_proj_id = sorted(proj_numbers)[-1]
    #     dap_ep = MessageEndpoints.processed_data(f"px_stream/projection_{last_proj_id}/")
    #
    #     consumer = self.client.connector.consumer(topics=dap_ep, cb=_dap_cb)
    #     consumer.start()
    #
    #     self.new_projection_data.connect(slot)

    def connect_proj_id(self, slot):
        def _dap_cb(msg):
            msg = BECMessage.DeviceMessage.loads(msg.value)
            self.new_projection_id.emit(msg.content["signals"])

        dap_ep = "px_stream/proj_nr"
        consumer = self.client.connector.consumer(topics=dap_ep, cb=_dap_cb)
        consumer.start()

        self.new_projection_id.connect(slot)

    def connect_proj_data(self, slot: object, data_ep: str) -> object:
        def _dap_cb(msg):
            msg = BECMessage.DeviceMessage.loads(msg.value)
            self.new_projection_data.emit(msg.content["signals"])

        consumer = self.client.connector.consumer(topics=data_ep, cb=_dap_cb)
        consumer.start()
        self._daps[data_ep] = _BECDap(consumer)
        self._daps[data_ep].slots.add(slot)

        self.new_projection_data.connect(slot)

    def disconnect_proj_data(self, slot, data_ep):
        if data_ep not in self._daps:
            return

        if slot not in self._daps[data_ep].slots:
            return

        self.new_projection_data.disconnect(slot)
        self._daps[data_ep].slots.remove(slot)

        if not self._daps[data_ep].slots:
            # shutdown consumer if there are no more connected slots
            self._daps[data_ep].consumer.shutdown()
            del self._daps[data_ep]


bec_dispatcher = _BECDispatcher()
