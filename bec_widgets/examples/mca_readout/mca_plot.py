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

    def __init__(self):
        super().__init__()

        self.init_ui()

        self.data = None
        self.scanID = None
        self.stream_consumer = None

        self.device_consumer("mca")

        self.new_scanID.connect(self.create_new_stream_consumer)
        self.update_signal.connect(self.plot_new)

    def init_ui(self):
        # Create layout and add widgets
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Create plot
        # self.glw = pg.GraphicsLayoutWidget()
        self.plot_widget = pg.PlotWidget(title="MCA readout")
        self.image_item = pg.ImageItem()
        self.plot_widget.addItem(self.image_item)

        # Add widgets to the layout
        self.layout.addWidget(self.plot_widget)

    @pyqtSlot(str)
    def create_new_stream_consumer(self, scanID: str):
        print(f"Creating new stream consumer for scanID: {scanID}")

        self.connect_stream_consumer(scanID, "mca")

    def connect_stream_consumer(self, scanID, device):
        if self.stream_consumer is not None:
            self.stream_consumer.shutdown()

        self.stream_consumer = connector.stream_consumer(
            topics=MessageEndpoints.device_async_readback(scanID=scanID, device=device),
            cb=self._streamer_cb,
            parent=self,
        )

        self.stream_consumer.start()

    def device_consumer(self, device):
        self.device_consumer = connector.consumer(
            topics=MessageEndpoints.device_status(device), cb=self._device_cv, parent=self
        )

        self.device_consumer.start()

    def plot_new(self):
        self.image_item.setImage(self.data.T)

    @staticmethod
    def _streamer_cb(msg, *, parent, **_kwargs) -> None:
        msgMCS = BECMessage.DeviceMessage.loads(msg.value)

        row = msgMCS.content["signals"]["mca1"]
        metadata = msgMCS.metadata

        if parent.data is None:
            parent.data = np.array([row])

        # Check if the current number of rows is odd
        # if parent.data is not None and parent.data.shape[0] % 2 == 0:
        #     row = np.flip(row)  # Flip the rowR
        else:
            parent.data = np.vstack((parent.data, row))

        parent.update_signal.emit()

    @staticmethod
    def _device_cv(msg, *, parent, **_kwargs) -> None:
        msgDEV = BECMessage.DeviceMessage.loads(msg.value)

        current_scanID = msgDEV.metadata["scanID"]

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

        # print(msgDEV)


if __name__ == "__main__":
    from bec_lib.core import RedisConnector

    connector = RedisConnector("localhost:6379")

    app = QApplication([])
    streamApp = StreamApp()

    streamApp.show()
    app.exec_()
