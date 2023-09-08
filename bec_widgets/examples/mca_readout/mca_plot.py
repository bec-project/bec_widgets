# import simulation_progress as SP
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QWidget,
)

from bec_lib.core import MessageEndpoints, BECMessage


class StreamApp(QWidget):
    update_signal = pyqtSignal()
    new_scanID = pyqtSignal(str)

    def __init__(self, device, sub_device):
        super().__init__()
        pg.setConfigOptions(background="w", foreground="k")
        self.init_ui()

        self.setWindowTitle("MCA readout")

        self.data = None
        self.scanID = None
        self.stream_consumer = None

        self.device = device
        self.sub_device = sub_device

        self.start_device_consumer()

        # self.start_device_consumer(self.device)  # for simulation

        self.new_scanID.connect(self.create_new_stream_consumer)
        self.update_signal.connect(self.plot_new)

    def init_ui(self):
        # Create layout and add widgets
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Create plot
        self.glw = pg.GraphicsLayoutWidget()
        self.layout.addWidget(self.glw)

        # Create Plot and add ImageItem
        self.plot_item = pg.PlotItem()
        self.plot_item.setAspectLocked(True)
        self.imageItem = pg.ImageItem()
        self.plot_item.addItem(self.imageItem)

        # Setting up histogram
        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.imageItem)
        self.hist.gradient.loadPreset("magma")
        # self.update_hist()

        # Adding Items to Graphical Layout
        self.glw.addItem(self.plot_item)
        self.glw.addItem(self.hist)

    @pyqtSlot(str)
    def create_new_stream_consumer(self, scanID: str):
        print(f"Creating new stream consumer for scanID: {scanID}")

        self.connect_stream_consumer(scanID, self.device)

    def connect_stream_consumer(self, scanID, device):
        if self.stream_consumer is not None:
            self.stream_consumer.shutdown()

        self.stream_consumer = connector.stream_consumer(
            topics=MessageEndpoints.device_async_readback(scanID=scanID, device=device),
            cb=self._streamer_cb,
            parent=self,
        )

        self.stream_consumer.start()

    def start_device_consumer(self):
        self.device_consumer = connector.consumer(
            topics=MessageEndpoints.scan_status(), cb=self._device_cv, parent=self
        )

        self.device_consumer.start()

    # def start_device_consumer(self, device): #for simulation
    #     self.device_consumer = connector.consumer(
    #         topics=MessageEndpoints.device_status(device), cb=self._device_cv, parent=self
    #     )
    #
    #     self.device_consumer.start()

    def plot_new(self):
        self.imageItem.setImage(self.data, autoLevels=False)

    @staticmethod
    def _streamer_cb(msg, *, parent, **_kwargs) -> None:
        msgMCS = BECMessage.DeviceMessage.loads(msg.value)

        row = msgMCS.content["signals"][parent.sub_device]
        metadata = msgMCS.metadata

        # Check if the current number of rows is odd
        if parent.data is not None and parent.data.shape[0] % 2 == 1:
            row = np.flip(row)  # Flip the row

        if parent.data is None:
            parent.data = np.array([row])
        else:
            parent.data = np.vstack((parent.data, row))

        parent.update_signal.emit()

    @staticmethod
    def _device_cv(msg, *, parent, **_kwargs) -> None:
        print("Getting ScanID")

        msgDEV = BECMessage.ScanStatusMessage.loads(msg.value)

        current_scanID = msgDEV.content["scanID"]

        if parent.scanID is None:
            parent.scanID = current_scanID
            parent.new_scanID.emit(current_scanID)
            print(f"New scanID: {current_scanID}")

        if current_scanID != parent.scanID:
            parent.scanID = current_scanID
            parent.data = None
            parent.image_item.clear()
            parent.new_scanID.emit(current_scanID)

            print(f"New scanID: {current_scanID}")


if __name__ == "__main__":
    import argparse
    from bec_lib.core import RedisConnector

    parser = argparse.ArgumentParser(description="Stream App.")
    parser.add_argument(
        "--port", type=str, default="localhost:6379", help="Port for RedisConnector"
    )
    parser.add_argument("--device", type=str, default="mca", help="Device name")
    parser.add_argument("--sub_device", type=str, default="mca1", help="Sub-device name")

    args = parser.parse_args()

    connector = RedisConnector(args.port)

    app = QApplication([])
    streamApp = StreamApp(device=args.device, sub_device=args.sub_device)

    streamApp.show()
    app.exec_()
