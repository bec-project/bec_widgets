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
            cb=self._stremer_cb,
            parent=self,
        )

        self.stream_consumer.start()

        self.data = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

        self.scanID = None

        self.update_plot.connect(self.plot_new)

    def plot_new(self):
        self.image_item.setImage(self.data)

    @pyqtSlot(dict, dict)
    def get_stream(self, msg, metadata):
        print(msg)
        print(metadata)

    # def connect_stream_slot(self, slot, topic):

    @staticmethod
    def _stremer_cb(msg, *, parent, **_kwargs) -> None:
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

        # print(f"metadata: {metadata}")

        # add row vertically to data
        parent.data = np.vstack((parent.data, row))

        parent.update_plot.emit()

        # print(f"msg: {msgMCS}")
        # print(f"row: {row}")


if __name__ == "__main__":
    from bec_widgets.bec_dispatcher import bec_dispatcher

    # BECclient global variables
    # client = bec_dispatcher.client
    # client.start()
    #
    # dev = client.device_manager.devices
    # scans = client.scans
    # queue = client.queue

    connector = RedisConnector("localhost:6379")

    app = QApplication([])
    progressApp = StreamApp()

    # bec_dispatcher.connect_slot(
    #     slot=progressApp.get_stream,
    #     topic=MessageEndpoints.device_async_readback(scanID="ScanID1", device="mca"),
    # )

    # window = ProgressApp()
    # window.show()
    progressApp.show()
    app.exec_()
