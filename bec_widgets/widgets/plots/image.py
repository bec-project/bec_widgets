from __future__ import annotations
import scipy as sp

from collections import defaultdict
from typing import Literal, Optional, Any

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QMainWindow
from qtpy.QtCore import QThread
from pydantic import Field, BaseModel, ValidationError
from pyqtgraph import mkBrush
from qtpy import QtCore
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtWidgets import QWidget

from bec_lib import MessageEndpoints, RedisConnector
from bec_lib.scan_data import ScanData
from bec_widgets.utils import Colors, ConnectionConfig, BECConnector, EntryValidator, BECDispatcher
from bec_widgets.widgets.plots import BECPlotBase, WidgetConfig


class ImageConfig(ConnectionConfig):
    pass


class BECImageShowConfig(WidgetConfig):
    pass


class BECImageItem(BECConnector, pg.ImageItem):
    USER_ACCESS = []

    def __init__(
        self,
        config: Optional[ImageConfig] = None,
        gui_id: Optional[str] = None,
        **kwargs,
    ):
        if config is None:
            config = ImageConfig(widget_class=self.__class__.__name__)
            self.config = config
        else:
            self.config = config
            # config.widget_class = self.__class__.__name__
        super().__init__(config=config, gui_id=gui_id)
        pg.ImageItem.__init__(self)

        self.apply_config()
        if kwargs:
            self.set(**kwargs)

    def apply_config(self):
        pass

    def set(self, **kwargs):
        pass


class BECImageShow(BECPlotBase):
    USER_ACCESS = ["show_image"]

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        parent_figure=None,
        config: Optional[WidgetConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
    ):
        if config is None:
            config = BECImageShowConfig(widget_class=self.__class__.__name__)
        super().__init__(
            parent=parent, parent_figure=parent_figure, config=config, client=client, gui_id=gui_id
        )

        self.image = BECImageItem()
        self.addItem(self.image)
        self.addColorBar(self.image, values=(0, 100))
        # self.add_histogram()

        # set mock data
        # self.image.setImage(np.random.rand(100, 100))
        # self.image.setOpts(axisOrder="row-major")

        self.debug_stream()

    def debug_stream(self):
        device = "eiger"
        self.image_thread = ImageThread(client=self.client, monitor=device)
        # self.image_thread.start()
        self.image_thread.image_updated.connect(self.on_image_update)

    def add_color_bar(self, vmap: tuple[int, int] = (0, 100)):
        self.addColorBar(self.image, values=vmap)

    def add_histogram(self):
        # Create HistogramLUTWidget
        self.histogram = pg.HistogramLUTWidget()

        # Link HistogramLUTWidget to ImageItem
        self.histogram.setImageItem(self.image)

    # def show_image(
    #     self,
    #     image: np.ndarray,
    #     scale: Optional[tuple] = None,
    #     pos: Optional[tuple] = None,
    #     auto_levels: Optional[bool] = True,
    #     auto_range: Optional[bool] = True,
    #     lut: Optional[list] = None,
    #     opacity: Optional[float] = 1.0,
    #     auto_downsample: Optional[bool] = True,
    # ):
    #     self.image.setImage(
    #         image,
    #         scale=scale,
    #         pos=pos,
    #         autoLevels=auto_levels,
    #         autoRange=auto_range,
    #         lut=lut,
    #         opacity=opacity,
    #         autoDownsample=auto_downsample,
    #     )
    #
    # def remove(self):
    #     self.image.clear()
    #     self.removeItem(self.image)
    #     self.image = None
    #     super().remove()

    def set_monitor(self, monitor: str = None): ...

    def set_zmq(self, address: str = None): ...

    @pyqtSlot(np.ndarray)  # TODO specify format
    def on_image_update(self, image):
        self.image.updateImage(image)


class ImageThread(QThread):
    image_updated = pyqtSignal(np.ndarray)  # TODO add type

    def __init__(self, parent=None, client=None, monitor: str = None, port: int = None):
        super().__init__()

        bec_dispatcher = BECDispatcher()
        self.client = bec_dispatcher.client if client is None else client
        self.dev = self.client.device_manager.devices
        self.scans = self.client.scans
        self.queue = self.client.queue

        # Monitor Device
        self.monitor = monitor

        # Connection
        self.port = port
        if self.port is None:
            self.port = self.client.connector.host
        # self.connector = RedisConnector(self.port)
        self.connector = RedisConnector("localhost:6379")
        self.stream_consumer = None

        if self.monitor is not None:
            self.connect_stream_consumer(self.monitor)

    def set_monitor(self, monitor: str = None) -> None:
        """
        Set/update monitor device.
        Args:
            monitor(str): Name of the monitor.
        """
        self.monitor = monitor

    def connect_stream_consumer(self, device):
        if self.stream_consumer is not None:
            self.stream_consumer.shutdown()

        self.stream_consumer = self.connector.stream_consumer(
            topics=MessageEndpoints.device_monitor(device=device),
            cb=self._streamer_cb,
            parent=self,
        )

        self.stream_consumer.start()

        print(f"Stream consumer started for device: {device}")

    def process_FFT(self, data: np.ndarray) -> np.ndarray:
        return np.fft.fft2(data)

    def center_of_mass(self, data: np.ndarray) -> tuple:
        return np.unravel_index(np.argmax(data), data.shape)

    @staticmethod
    def _streamer_cb(msg, *, parent, **_kwargs) -> None:
        msg_device = msg.value
        metadata = msg_device.metadata

        data = msg_device.content["data"]
        parent.image_updated.emit(data)


class BECImageShowWithHistogram(pg.GraphicsLayoutWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # Create ImageItem and HistogramLUTItem
        self.imageItem = pg.ImageItem()
        self.histogram = pg.HistogramLUTItem()

        # Link Histogram to ImageItem
        self.histogram.setImageItem(self.imageItem)

        # Create a layout within the GraphicsLayoutWidget
        self.layout = self

        # Add ViewBox and Histogram to the layout
        self.viewBox = self.addViewBox(row=0, col=0)
        self.viewBox.addItem(self.imageItem)
        self.viewBox.setAspectLocked(True)  # Lock the aspect ratio

        # Add Histogram to the layout in the same cell
        self.addItem(self.histogram, row=0, col=1)
        self.histogram.setMaximumWidth(200)  # Adjust the width of the histogram to fit

    def setImage(self, image):
        """Set the image to be displayed."""
        self.imageItem.setImage(image)


# if __name__ == "__main__":
#     import sys
#     from qtpy.QtWidgets import QApplication
#
#     bec_dispatcher = BECDispatcher()
#     client = bec_dispatcher.client
#     client.start()
#
#     app = QApplication(sys.argv)
#     win = QMainWindow()
#     img = BECImageShow(client=client)
#     win.setCentralWidget(img)
#     win.show()
#     sys.exit(app.exec_())
