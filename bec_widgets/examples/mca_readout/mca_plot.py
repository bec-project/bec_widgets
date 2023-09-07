# import simulation_progress as SP
import numpy as np
import pyqtgraph as pg

from PyQt5.QtCore import pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QLabel,
    QWidget,
    QProgressBar,
    QPushButton,
)

from bec_lib.core import MessageEndpoints, RedisConnector, BECMessage


class StreamApp(QWidget):
    update_signal = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.init_ui()

        self.data = None
        # self.scanID = None
        self.stream_consumer = None

        self.update_signal.connect(self.plot_new)
        self.connect_stream_consumer("ScanID1", "mca")

    def init_ui(self):
        # Create layout and add widgets
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Create plot
        self.plot_widget = pg.PlotWidget(title="2D plot for mcs data")
        self.image_item = pg.ImageItem()
        self.label_id = pg.LabelItem(justify="left")
        self.plot_widget.addItem(self.label_id)
        self.plot_widget.addItem(self.image_item)

        # Add widgets to the layout
        self.layout.addWidget(self.plot_widget)

    def connect_stream_consumer(self, scanID, device):
        if self.stream_consumer is not None:
            self.stream_consumer.shutdown()

        self.stream_consumer = connector.stream_consumer(
            topics=MessageEndpoints.device_async_readback(scanID=scanID, device=device),
            cb=self._streamer_cb,
            parent=self,
        )

        self.stream_consumer.start()

    def plot_new(self):
        self.image_item.setImage(self.data)

    @staticmethod
    def _streamer_cb(msg, *, parent, **_kwargs) -> None:
        msgMCS = BECMessage.DeviceMessage.loads(msg.value)

        row = msgMCS.content["signals"]["mca1"]
        metadata = msgMCS.metadata

        if parent.data is None:
            parent.data = row
        else:
            parent.data = np.vstack((parent.data, row))

        # current_scanID = metadata.get("scanID", None)
        # if current_scanID is None:
        #     return

        # if current_scanID != parent.scanID:
        #     parent.scanID = current_scanID
        #     parent.data = row
        #     parent.image_item.clear()

        print(f"msg: {msg}")
        print(f"metadata: {metadata}")
        print(f"parent.data: {parent.data}")

        parent.update_signal.emit()


if __name__ == "__main__":
    from bec_lib.core import RedisConnector

    connector = RedisConnector("localhost:6379")

    app = QApplication([])
    streamApp = StreamApp()

    streamApp.show()
    app.exec_()
