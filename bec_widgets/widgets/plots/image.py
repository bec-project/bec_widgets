from __future__ import annotations

import time
from typing import Literal, Optional

import numpy as np
import pyqtgraph as pg
from pydantic import Field, BaseModel
from qtpy.QtCore import QThread
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtWidgets import QWidget

from bec_lib import MessageEndpoints, RedisConnector
from bec_widgets.utils import ConnectionConfig, BECConnector, BECDispatcher
from bec_widgets.widgets.plots import BECPlotBase, WidgetConfig


class MonitorConfig(BaseModel):
    monitor: Optional[str] = Field(None, description="The name of the monitor.")
    fft: Optional[bool] = Field(False, description="Whether to perform FFT on the monitor data.")
    log: Optional[bool] = Field(False, description="Whether to perform log on the monitor data.")
    center_of_mass: Optional[bool] = Field(
        False, description="Whether to calculate the center of mass of the monitor data."
    )
    transpose: Optional[bool] = Field(
        False, description="Whether to transpose the monitor data before displaying."
    )
    rotation: Optional[int] = Field(
        None, description="The rotation angle of the monitor data before displaying."
    )

    # TODO Decide if usefully to include port and host
    host: Optional[str] = Field(None, description="The host of the monitor.")
    port: Optional[int] = Field(None, description="The port of the monitor.")


class ImageItemConfig(ConnectionConfig):
    # color_map: Optional[str] = Field("magma", description="The color map of the image.")
    source: Optional[str] = Field(None, description="The source of the curve.")
    signals: MonitorConfig = Field(
        default_factory=MonitorConfig, description="The configuration of the monitor."
    )


class ImageConfig(WidgetConfig):
    color_map: Optional[str] = Field("magma", description="The color map of the image.")
    color_bar: Optional[Literal["simple", "full"]] = Field(
        "simple", description="The type of the color bar."
    )
    vrange: Optional[tuple[int, int]] = Field(
        None, description="The range of the color bar. If None, the range is automatically set."
    )
    images: dict[str, ImageItemConfig] = Field(
        {},
        description="The configuration of the images. The key is the name of the image.",
    )
    # TODO Decide if implement or not
    # x_transpose_axis:
    # y_transpose_axis:


class BECImageItem(BECConnector, pg.ImageItem):  # TODO decide how complex it should be
    USER_ACCESS = []

    def __init__(
        self,
        config: Optional[ImageItemConfig] = None,
        gui_id: Optional[str] = None,
        **kwargs,
    ):
        if config is None:
            config = ImageItemConfig(widget_class=self.__class__.__name__)
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
        ...
        # self.set_color_map(self.config.color_map)

    def set(self, **kwargs):
        pass

    def set_color_map(self, cmap: str = "magma"):
        self.setColorMap(cmap)
        # self.config.color_map = cmap


class BECImageShow(BECPlotBase):
    USER_ACCESS = [
        "set_vrange",
        "set_monitor",
        "set_color_map",
        "set_image",
        "set_processing",
        "enable_fft",
        "enable_log",
        "rotate",
        "transpose",
    ]

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        parent_figure=None,
        config: Optional[WidgetConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
        monitor: Optional[str] = None,
    ):
        if config is None:
            config = ImageConfig(widget_class=self.__class__.__name__)
        super().__init__(
            parent=parent, parent_figure=parent_figure, config=config, client=client, gui_id=gui_id
        )

        # Items to be added to the plot
        self.image = None
        self.color_bar = None

        # Args to pass
        self.monitor = monitor
        self.scanID = None

        # init image and image thread
        self._init_image()
        self._init_image_thread(monitor=self.monitor)

        # Dispatcher
        self.bec_dispatcher.connect_slot(self.on_scan_segment, MessageEndpoints.scan_segment())

    def find_widget_by_id(self, item_id: str):
        if self.image.gui_id == item_id:
            return self.image

    def apply_config(self):  # TODO implement
        ...

    def _init_image(self):
        self.image = BECImageItem()
        self.plot_item.addItem(self.image)
        self.config.images["device_monitor"] = self.image.config

        # customising ImageItem
        self._add_color_bar(style=self.config.color_bar, vrange=self.config.vrange)
        self.set_color_map(cmap=self.config.color_map)

    def _init_image_thread(self, monitor: str = None):
        self.monitor = monitor
        self.image.config.signals.monitor = monitor
        self.image_thread = ImageThread(client=self.client, monitor=monitor)
        self.image_thread.config = self.image.config.signals
        self.proxy_update_plot = pg.SignalProxy(
            self.image_thread.image_updated, rateLimit=25, slot=self.on_image_update
        )
        # self.image_thread.start()

    def _add_color_bar(
        self, style: Literal["simple,full"] = "simple", vrange: tuple[int, int] = (0, 100)
    ):
        if style == "simple":
            self.color_bar = pg.ColorBarItem(colorMap=self.config.color_map)
            if vrange is not None:
                self.color_bar.setLevels(low=vrange[0], high=vrange[1])
            self.color_bar.setImageItem(self.image)
            self.addItem(self.color_bar, row=0, col=1)
            self.config.color_bar = "simple"
        elif style == "full":
            # Setting histogram
            self.color_bar = pg.HistogramLUTItem()
            self.color_bar.setImageItem(self.image)
            self.color_bar.gradient.loadPreset(self.config.color_map)
            if vrange is not None:
                self.color_bar.setLevels(min=vrange[0], max=vrange[1])
                self.color_bar.setHistogramRange(
                    vrange[0] - 0.1 * vrange[0], vrange[1] + 0.1 * vrange[1]
                )

            # Adding histogram to the layout
            self.addItem(self.color_bar, row=0, col=1)

            # save settings
            self.config.color_bar = "full"
        else:
            raise ValueError("style should be 'simple' or 'full'")

    # def color_bar_switch(self, style: Literal["simple,full"] = "simple"): #TODO check if possible
    #     if style == "simple" and self.config.color_bar == "full":
    #         self.color_bar.remove()

    def set_vrange(self, vmin: float, vmax: float):
        self.image.setLevels([vmin, vmax])
        if self.color_bar is not None:
            if self.config.color_bar == "simple":
                self.color_bar.setLevels(low=vmin, high=vmax)
            elif self.config.color_bar == "full":
                self.color_bar.setLevels(min=vmin, max=vmax)
                self.color_bar.setHistogramRange(vmin - 0.1 * vmin, vmax + 0.1 * vmax)

    def set_monitor(self, monitor: str = None) -> None:
        """
        Set/update monitor device.
        Args:
            monitor(str): Name of the monitor.
        """
        self.image_thread.set_monitor(monitor)
        self.image.config.signals.monitor = monitor

    def set_color_map(self, cmap: str = "magma"):
        self.image.set_color_map(cmap)
        if self.color_bar is not None:
            if self.config.color_bar == "simple":
                self.color_bar.setColorMap(cmap)
            elif self.config.color_bar == "full":
                self.color_bar.gradient.loadPreset(cmap)

    # def set_zmq(self, address: str = None):  # TODO to be implemented
    #     ...

    def set_processing(
        self, fft: bool = False, log: bool = False, rotation: int = None, transpose: bool = False
    ):
        """
        Set the processing of the monitor data.
        Args:
            fft(bool): Whether to perform FFT on the monitor data.
            log(bool): Whether to perform log on the monitor data.
            rotation(int): The rotation angle of the monitor data before displaying.
            transpose(bool): Whether to transpose the monitor data before displaying.
        """
        self.image.config.signals.fft = fft
        self.image.config.signals.log = log
        self.image.config.signals.rotation = rotation
        self.image.config.signals.transpose = transpose
        self.image_thread.update_config(self.image.config.signals)

    def enable_fft(self, enable: bool = True):  # TODO enable processing of already taken images
        self.image.config.signals.fft = enable
        self.image_thread.update_config(self.image.config.signals)

    def enable_log(self, enable: bool = True):
        self.image.config.signals.log = enable
        self.image_thread.update_config(self.image.config.signals)

    def rotate(self, angle: int):  # TODO fine tune, can be byt any angle not just by 90deg?
        self.image.config.signals.rotation = angle
        self.image_thread.update_config(self.image.config.signals)

    def transpose(self):  # TODO do enable or not?
        self.image.config.signals.transpose = not self.image.config.signals.transpose
        self.image_thread.update_config(self.image.config.signals)

    # def enable_center_of_mass(self, enable: bool = True): #TODO check and enable
    #     self.image.config.signals.center_of_mass = enable
    #     self.image_thread.update_config(self.image.config.signals)

    @pyqtSlot(np.ndarray)
    def on_image_update(self, image):
        # print(f"Image updated: {image.shape}")
        print(f"Image updated")
        self.image.updateImage(image[0])

    @pyqtSlot(dict, dict)
    def on_scan_segment(self, msg, metadata):
        """
        Serves as a trigger to image acquisition.
        Update the scanID and start the image thread if the scanID is different from the current one.
        Args:
            msg(dict): The content of the message.
            metadata(dict): The metadata of the message.
        """
        current_scanID = msg.get("scanID", None)
        if current_scanID is None:
            return

        if current_scanID != self.scanID:
            self.scanID = current_scanID
            self.image_thread.start()

        max_points = metadata.get("num_points", None)
        current_point = msg.get("point_id") + 1

        print(f"Current point: {current_point} out of {max_points}")

        if current_point == max_points:
            if self.image_thread.isRunning():
                self.image_thread.stop()
                print("image thread done")

    def set_image(self, data: np.ndarray):
        """
        Set the image to be displayed.
        Args:
            data(np.ndarray): The image to be displayed.
        """
        self.imageItem.setImage(data)
        if self.image_thread.isRunning():
            self.image_thread.stop()

    def cleanup(self):  # TODO test
        self.image_thread.stop()
        self.image_thread.wait()
        print("ImageThread stopped")


class ImageThread(QThread):
    image_updated = pyqtSignal(np.ndarray)

    def __init__(
        self,
        parent=None,
        client=None,
        monitor: str = None,
        monitor_config: MonitorConfig = None,
        host: str = None,
        port: int | str = None,
    ):
        super().__init__(parent=parent)

        bec_dispatcher = BECDispatcher()
        self.client = bec_dispatcher.client if client is None else client
        self.dev = self.client.device_manager.devices
        self.scans = self.client.scans
        self.queue = self.client.queue

        # Monitor Device
        self.monitor = monitor
        self.config = monitor_config

        # Connection
        self.host = host
        self.port = str(port)
        if self.host is None:
            self.host = self.client.connector.host
            self.port = self.client.connector.port
        self.connector = RedisConnector(f"{self.host}:{self.port}")

        self.running = False
        if self.monitor is not None:
            self.set_monitor(self.monitor)

    def update_config(self, config: MonitorConfig | dict):  # TODO include monitor update in config?
        """
        Update the monitor configuration.
        Args:
            config(MonitorConfig|dict): The new monitor configuration.
        """
        if isinstance(config, dict):
            config = MonitorConfig(**config)
        self.config = config

    def set_monitor(self, monitor: str = None) -> None:  # TODO check monitor update with the config
        """
        Set/update monitor device.
        Args:
            monitor(str): Name of the monitor.
        """
        self.monitor = monitor
        print(f"Stream consumer started for device: {monitor}")

    def process_FFT(self, data: np.ndarray) -> np.ndarray:  # TODO check functionality
        return np.abs(np.fft.fftshift(np.fft.fft2(data)))

    def rotation(self, data: np.ndarray, angle: int) -> np.ndarray:
        return np.rot90(data, k=angle, axes=(0, 1))

    def transpose(self, data: np.ndarray) -> np.ndarray:
        return np.transpose(data)

    def log(self, data: np.ndarray) -> np.ndarray:
        return np.log10(np.abs(data))

    # def center_of_mass(self, data: np.ndarray) -> tuple:  # TODO check functionality
    #     return np.unravel_index(np.argmax(data), data.shape)

    def post_processing(self, data: np.ndarray) -> np.ndarray:
        if self.config.fft:
            data = self.process_FFT(data)
        if self.config.rotation is not None:
            data = self.rotation(data, self.config.rotation)
        if self.config.transpose:
            data = self.transpose(data)
        if self.config.log:
            data = self.log(data)
        return data

    def run(self):
        self.running = True
        self.get_image()

    def get_image(self):
        if self.monitor is None:
            return
        while self.running:
            data = self.connector.get_last(
                topic=MessageEndpoints.device_monitor(device=self.monitor)
            )
            if data is not None:
                data = data.content["data"]

                data = self.post_processing(data)

                self.image_updated.emit(data)
                print("ImageThread is running")

            time.sleep(0.01)

    def stop(self):
        self.running = False
