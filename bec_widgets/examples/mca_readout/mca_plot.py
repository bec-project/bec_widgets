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
    update_plot = pyqtSignal()

    def __init__(self):
        super().__init__()

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

        self.stream_consumer = connector.stream_consumer(
            topics=MessageEndpoints.device_async_readback(scanID="ScanID1", device="mca"),
            cb=self._streamer_cb,
            parent=self,
        )

        self.stream_consumer.start()

        self.data = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

        self.scanID = None

        self.update_plot.connect(self.plot_new)

    def plot_new(self):
        self.image_item.setImage(self.data)

    @staticmethod
    def _streamer_cb(msg, *, parent, **_kwargs) -> None:
        msgMCS = BECMessage.DeviceMessage.loads(msg.value)

        row = msgMCS.content["signals"]["mca1"]
        metadata = msgMCS.metadata

        current_scanID = metadata.get("scanID", None)
        if current_scanID is None:
            return

        if current_scanID != parent.scanID:
            parent.scanID = current_scanID
            parent.data = row
            parent.image_item.clear()

        parent.data = np.vstack((parent.data, row))

        parent.update_plot.emit()


if __name__ == "__main__":
    connector = RedisConnector("localhost:6379")

    app = QApplication([])
    streamApp = StreamApp()

    streamApp.show()
    app.exec_()
