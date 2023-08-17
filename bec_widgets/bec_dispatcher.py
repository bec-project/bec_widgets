import argparse
import itertools
import os
from dataclasses import dataclass
from threading import RLock
from typing import Callable

from bec_lib import BECClient
from bec_lib.core import BECMessage, MessageEndpoints, ServiceConfig
from bec_lib.core.redis_connector import RedisConsumerThreaded
from PyQt5.QtCore import QObject, pyqtSignal


@dataclass
class _BECDap:
    """Utility class to keep track of slots associated with a particular dap redis consumer"""

    consumer: RedisConsumerThreaded
    slots = set()


# Adding a new pyqt signal requres a class factory, as they must be part of the class definition
# and cannot be dynamically added as class attributes after the class has been defined.
_signal_class_factory = (
    type(f"Signal{i}", (QObject,), dict(signal=pyqtSignal(dict, dict))) for i in itertools.count()
)


@dataclass
class _Connection:
    """Utility class to keep track of slots connected to a particular redis consumer"""

    consumer: RedisConsumerThreaded
    slots = set()
    # keep a reference to a new signal class, so it is not gc'ed
    _signal_container = next(_signal_class_factory)()

    def __post_init__(self):
        self.signal = self._signal_container.signal


class _BECDispatcher(QObject):
    new_scan = pyqtSignal(dict, dict)
    scan_segment = pyqtSignal(dict, dict)
    new_dap_data = pyqtSignal(dict, dict)

    new_projection_id = pyqtSignal(dict)
    new_projection_data = pyqtSignal(dict)

    def __init__(self, bec_config=None):
        super().__init__()
        self.client = BECClient()

        # TODO: this is a workaround for now to provide service config within qtdesigner, but is
        # it possible to provide config via a cli arg?
        if bec_config is None and os.path.isfile("bec_config.yaml"):
            bec_config = "bec_config.yaml"

        self.client.initialize(config=ServiceConfig(config_path=bec_config))

        self._slot_signal_map = {"on_scan_segment": self.scan_segment, "on_new_scan": self.new_scan}
        self._daps = {}
        self._connections = {}

        self._scan_id = None
        scan_lock = RLock()

        # self.new_projection_id.connect(self.new_projection_data)

        def _scan_segment_cb(msg):
            msg = BECMessage.ScanMessage.loads(msg.value)[0]
            with scan_lock:
                # TODO: use ScanStatusMessage instead?
                scan_id = msg.content["scanID"]
                if self._scan_id != scan_id:
                    self._scan_id = scan_id
                    self.new_scan.emit(msg.content, msg.metadata)
            self.scan_segment.emit(msg.content, msg.metadata)

        scan_segment_topic = MessageEndpoints.scan_segment()
        self._scan_segment_thread = self.client.connector.consumer(
            topics=scan_segment_topic, cb=_scan_segment_cb
        )
        self._scan_segment_thread.start()

    def connect(self, widget):
        for slot_name, signal in self._slot_signal_map.items():
            slot = getattr(widget, slot_name, None)
            if callable(slot):
                signal.connect(slot)

    def connect_slot(self, slot: Callable, topic: str) -> None:
        """Connect widget's pyqt slot, so that it is called on new pub/sub topic message

        Args:
            slot (Callable): A slot method/function that accepts two inputs: content and metadata of
                the corresponding pub/sub message
            topic (str): A topic that can typically be acquired via bec_lib.core.MessageEndpoints
        """
        # create new connection for topic if it doesn't exist
        if topic not in self._connections:

            def cb(msg):
                msg = BECMessage.MessageReader.loads(msg.value)
                # TODO: this can could be replaced with a simple
                # self._connections[topic].signal.emit(msg.content, msg.metadata)
                # once all dispatcher.connect_slot calls are made with a single topic only
                if not isinstance(msg, list):
                    msg = [msg]
                for msg_i in msg:
                    self._connections[topic].signal.emit(msg_i.content, msg_i.metadata)

            consumer = self.client.connector.consumer(topics=topic, cb=cb)
            consumer.start()

            self._connections[topic] = _Connection(consumer)

        # connect slot if it's not connected
        if slot not in self._connections[topic].slots:
            self._connections[topic].signal.connect(slot)
            self._connections[topic].slots.add(slot)

    def disconnect_slot(self, slot: Callable, topic: str) -> None:
        """Disconnect widget's pyqt slot from pub/sub updates on a topic.

        Args:
            slot (Callable): A slot to be disconnected
            topic (str): A corresponding topic that can typically be acquired via
                bec_lib.core.MessageEndpoints
        """
        if topic not in self._connections:
            return

        if slot not in self._connections[topic].slots:
            return

        self._connections[topic].signal.disconnect(slot)
        self._connections[topic].slots.remove(slot)

        if not self._connections[topic].slots:
            # shutdown consumer if there are no more connected slots
            self._connections[topic].consumer.shutdown()
            del self._connections[topic]

    def connect_dap_slot(self, slot, dap_names):
        if not isinstance(dap_names, list):
            dap_names = [dap_names]

        for dap_name in dap_names:
            if dap_name not in self._daps:  # create a new consumer and connect slot
                self.add_new_dap_connection(slot, dap_name)

            else:
                # connect slot if it's not yet connected
                if slot not in self._daps[dap_name].slots:
                    self.new_dap_data.connect(slot)
                    self._daps[dap_name].slots.add(slot)

    def add_new_dap_connection(self, slot, dap_name):
        def _dap_cb(msg):
            msg = BECMessage.ProcessedDataMessage.loads(msg.value)
            if not isinstance(msg, list):
                msg = [msg]
            for i in msg:
                self.new_dap_data.emit(i.content["data"], i.metadata)

        dap_ep = MessageEndpoints.processed_data(dap_name)
        consumer = self.client.connector.consumer(topics=dap_ep, cb=_dap_cb)
        consumer.start()

        self.new_dap_data.connect(slot)

        self._daps[dap_name] = _BECDap(consumer)
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


parser = argparse.ArgumentParser()
parser.add_argument("--bec-config", default=None)
args, _ = parser.parse_known_args()

bec_dispatcher = _BECDispatcher(args.bec_config)
