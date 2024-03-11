from __future__ import annotations

from collections import defaultdict
from typing import Literal, Optional, Any

import numpy as np
import pyqtgraph as pg
from pydantic import Field, BaseModel, ValidationError
from qtpy.QtCore import QThread, QObject
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtWidgets import QWidget

from bec_lib import MessageEndpoints
from bec_widgets.utils import ConnectionConfig, BECConnector
from bec_widgets.widgets.plots import BECPlotBase, WidgetConfig


class ProcessingConfig(BaseModel):
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


class ImageItemConfig(ConnectionConfig):
    monitor: Optional[str] = Field(None, description="The name of the monitor.")
    source: Optional[str] = Field(None, description="The source of the curve.")
    color_map: Optional[str] = Field("magma", description="The color map of the image.")
    downsample: Optional[bool] = Field(True, description="Whether to downsample the image.")
    opacity: Optional[float] = Field(1.0, description="The opacity of the image.")
    vrange: Optional[tuple[int, int]] = Field(
        None, description="The range of the color bar. If None, the range is automatically set."
    )
    color_bar: Optional[Literal["simple", "full"]] = Field(
        "simple", description="The type of the color bar."
    )
    processing: ProcessingConfig = Field(
        default_factory=ProcessingConfig, description="The post processing of the image."
    )


class ImageConfig(WidgetConfig):
    images: dict[str, ImageItemConfig] = Field(
        {},
        description="The configuration of the images. The key is the name of the image (source).",
    )


class BECImageItem(BECConnector, pg.ImageItem):
    USER_ACCESS = [
        "set",
        "set_color_map",
        "set_auto_downsample",
        "set_monitor",
        "set_vrange",
    ]

    def __init__(
        self,
        config: Optional[ImageItemConfig] = None,
        gui_id: Optional[str] = None,
        parent_image: Optional[BECImageItem] = None,
        **kwargs,
    ):
        if config is None:
            config = ImageItemConfig(widget_class=self.__class__.__name__)
            self.config = config
        else:
            self.config = config
        super().__init__(config=config, gui_id=gui_id)
        pg.ImageItem.__init__(self)

        self.parent_image = parent_image
        self.colorbar_bar = None

        self._add_color_bar(
            self.config.color_bar, self.config.vrange
        )  # TODO can also support None to not have any colorbar
        self.apply_config()
        if kwargs:
            self.set(**kwargs)

    def apply_config(self):
        self.set_color_map(self.config.color_map)
        self.set_auto_downsample(self.config.downsample)
        if self.config.vrange is not None:
            self.set_vrange(vrange=self.config.vrange)
        # self.set_color_bar(self.config.color_bar)

    def set(self, **kwargs):
        method_map = {
            "downsample": self.set_auto_downsample,
            "color_map": self.set_color_map,
            "monitor": self.set_monitor,
            "opacity": self.set_opacity,
            "vrange": self.set_vrange,
            "fft": self.set_fft,
            "log": self.set_log,
            "rot": self.set_rotation,
            "transpose": self.set_transpose,
        }
        for key, value in kwargs.items():
            if key in method_map:
                method_map[key](value)
            else:
                print(f"Warning: '{key}' is not a recognized property.")

    def set_fft(self, enable: bool = False):
        self.config.processing.fft = enable

    def set_log(self, enable: bool = False):
        self.config.processing.log = enable
        if enable and self.color_bar and self.config.color_bar == "full":
            self.color_bar.autoHistogramRange()

    def set_rotation(self, deg_90: int = 0):
        self.config.processing.rotation = deg_90

    def set_transpose(self, enable: bool = False):
        self.config.processing.transpose = enable

    def set_opacity(self, opacity: float = 1.0):
        self.setOpacity(opacity)
        self.config.opacity = opacity

    def set_color_map(self, cmap: str = "magma"):
        """
        Set the color map of the image.
        Args:
            cmap(str): The color map of the image.
        """
        self.setColorMap(cmap)
        if self.color_bar is not None:
            if self.config.color_bar == "simple":
                self.color_bar.setColorMap(cmap)
            elif self.config.color_bar == "full":
                self.color_bar.gradient.loadPreset(cmap)
        self.config.color_map = cmap

    def set_auto_downsample(self, auto: bool = True):
        """
        Set the auto downsample of the image.
        Args:
            auto(bool): Whether to downsample the image.
        """
        self.setAutoDownsample(auto)
        self.config.downsample = auto

    def set_monitor(self, monitor: str):
        """
        Set the monitor of the image.
        Args:
            monitor(str): The name of the monitor.
        """
        self.config.monitor = monitor

    def set_vrange(self, vmin: float = None, vmax: float = None, vrange: tuple[int, int] = None):
        """
        Set the range of the color bar.
        Args:
            vmin(float): Minimum value of the color bar.
            vmax(float): Maximum value of the color bar.
        """
        if vrange is not None:
            vmin, vmax = vrange
        self.setLevels([vmin, vmax])
        self.config.vrange = (vmin, vmax)
        if self.color_bar is not None:
            if self.config.color_bar == "simple":
                self.color_bar.setLevels(low=vmin, high=vmax)
            elif self.config.color_bar == "full":
                self.color_bar.setLevels(min=vmin, max=vmax)
                self.color_bar.setHistogramRange(vmin - 0.1 * vmin, vmax + 0.1 * vmax)

    def _add_color_bar(
        self, color_bar_style: str = "simple", vrange: Optional[tuple[int, int]] = None
    ):
        """
        Add color bar to the layout.
        Args:
            style(Literal["simple,full"]): The style of the color bar.
            vrange(tuple[int,int]): The range of the color bar.
        """
        if color_bar_style == "simple":
            self.color_bar = pg.ColorBarItem(colorMap=self.config.color_map)
            if vrange is not None:
                self.color_bar.setLevels(low=vrange[0], high=vrange[1])
            self.color_bar.setImageItem(self)
            self.parent_image.addItem(self.color_bar)  # , row=0, col=1)
            self.config.color_bar = "simple"
        elif color_bar_style == "full":
            # Setting histogram
            self.color_bar = pg.HistogramLUTItem()
            self.color_bar.setImageItem(self)
            self.color_bar.gradient.loadPreset(self.config.color_map)
            if vrange is not None:
                self.color_bar.setLevels(min=vrange[0], max=vrange[1])
                self.color_bar.setHistogramRange(
                    vrange[0] - 0.1 * vrange[0], vrange[1] + 0.1 * vrange[1]
                )

            # Adding histogram to the layout
            self.parent_image.addItem(self.color_bar)  # , row=0, col=1)

            # save settings
            self.config.color_bar = "full"
        else:
            raise ValueError("style should be 'simple' or 'full'")

    def _update_color_bar_for_log(self):
        """
        Update the color bar to reflect a logarithmic scale.
        """
        ...
        # if self.config.vrange:
        #     vmin, vmax = self.config.vrange
        #     offset = 1e-6
        #     vmin_log, vmax_log = np.log10(vmin + offset), np.log10(vmax + offset)
        #     if self.config.color_bar == "simple":
        #         self.color_bar.setLevels(low=vmin_log, high=vmax_log)
        #     elif self.config.color_bar == "full":
        #         self.color_bar.setImageItem(self)
        #         self.color_bar.setLevels(min=vmin_log, max=vmax_log)
        #         self.color_bar.setHistogramRange(
        #             vmin_log - 0.1 * vmin_log, vmax_log + 0.1 * vmax_log
        #         )


class BECImageShow(BECPlotBase):
    USER_ACCESS = [
        "add_image_by_config",
        "get_image_config",
        "get_image_list",
        "get_image_dict",
        "add_monitor_image",
        "add_custom_image",
        "set_vrange",
        "set_color_map",
    ]

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        parent_figure=None,
        config: Optional[ImageConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
    ):
        if config is None:
            config = ImageConfig(widget_class=self.__class__.__name__)
        super().__init__(
            parent=parent, parent_figure=parent_figure, config=config, client=client, gui_id=gui_id
        )

        self._images = defaultdict(dict)
        self.apply_config(self.config)
        self.processor = ImageProcessor()
        self.use_threading = False  # TODO WILL be moved to the init method and to figure method

    def _create_thread_worker(self, device: str, image: np.ndarray):
        thread = QThread()
        worker = ProcessorWorker(self.processor)
        worker.moveToThread(thread)

        # Connect signals and slots
        thread.started.connect(lambda: worker.process_image(device, image))
        worker.processed.connect(self.update_image)
        worker.finished.connect(thread.quit)
        worker.finished.connect(thread.wait)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        thread.start()

    def find_widget_by_id(self, item_id: str) -> BECImageItem:
        """
        Find the widget by its gui_id.
        Args:
            item_id(str): The gui_id of the widget.

        Returns:
            BECImageItem: The widget with the given gui_id.
        """
        for source, images in self._images.items():
            for key, value in images.items():
                if key == item_id and isinstance(value, BECImageItem):
                    return value
                elif isinstance(value, dict):
                    result = self.find_widget_by_id(item_id)
                    if result is not None:
                        return result

    def apply_config(self, config: dict | WidgetConfig):
        """
        Apply the configuration to the 1D waveform widget.
        Args:
            config(dict|WidgetConfig): Configuration settings.
            replot_last_scan(bool, optional): If True, replot the last scan. Defaults to False.
        """
        if isinstance(config, dict):
            try:
                config = ImageConfig(**config)
            except ValidationError as e:
                print(f"Validation error when applying config to BECImageShow: {e}")
                return
        self.config = config
        self.plot_item.clear()

        self.apply_axis_config()
        self._images = defaultdict(dict)

        # TODO extend by adding image by config

    def change_gui_id(self, new_gui_id: str):
        """
        Change the GUI ID of the image widget and update the parent_id in all associated curves.

        Args:
            new_gui_id (str): The new GUI ID to be set for the image widget.
        """
        self.gui_id = new_gui_id
        self.config.gui_id = new_gui_id

        for source, images in self._images.items():
            for id, image_item in images.items():
                image_item.config.parent_id = new_gui_id

    def add_image_by_config(self, config: ImageItemConfig | dict) -> BECImageItem:
        """
        Add an image to the widget by configuration.
        Args:
            config(ImageItemConfig|dict): The configuration of the image.

        Returns:
            BECImageItem: The image object.
        """
        if isinstance(config, dict):
            config = ImageItemConfig(**config)
        name = config.monitor if config.monitor is not None else config.gui_id
        image = self._add_image_object(source=config.source, name=name, config=config)
        return image

    def get_image_config(self, image_id, dict_output: bool = True) -> ImageItemConfig | dict:
        """
        Get the configuration of the image.
        Args:
            image_id(str): The ID of the image.
            dict_output(bool): Whether to return the configuration as a dictionary. Defaults to True.

        Returns:
            ImageItemConfig|dict: The configuration of the image.
        """
        for source, images in self._images.items():
            for id, image in images.items():
                if id == image_id:
                    if dict_output:
                        return image.config.dict()
                    else:
                        return image.config  # TODO check if this works

    def get_image_list(self) -> list[BECImageItem]:
        """
        Get the list of images.
        Returns:
            list[BECImageItem]: The list of images.
        """
        images = []
        for source, images_dict in self._images.items():
            for id, image in images_dict.items():
                images.append(image)
        return images

    def get_image_dict(self) -> dict[str, dict[str, BECImageItem]]:
        """
        Get all images.
        Returns:
            dict[str, dict[str, BECImageItem]]: The dictionary of images.
        """
        return self._images

    def add_monitor_image(
        self,
        monitor: str,
        color_map: Optional[str] = "magma",
        color_bar: Optional[Literal["simple", "full"]] = "simple",
        downsample: Optional[bool] = True,
        opacity: Optional[float] = 1.0,
        vrange: Optional[tuple[int, int]] = None,
        # post_processing: Optional[PostProcessingConfig] = None,
        **kwargs,
    ) -> BECImageItem:
        image_source = "device_monitor"

        image_exits = self._check_image_id(monitor, self._images)
        if image_exits:
            raise ValueError(
                f"Monitor with ID '{monitor}' already exists in widget '{self.gui_id}'."
            )

        image_config = ImageItemConfig(
            widget_class="BECImageItem",
            parent_id=self.gui_id,
            color_map=color_map,
            color_bar=color_bar,
            downsample=downsample,
            opacity=opacity,
            vrange=vrange,
            # post_processing=post_processing,
            **kwargs,
        )

        image = self._add_image_object(source=image_source, name=monitor, config=image_config)
        self._connect_device_monitor(monitor)
        return image

    def add_custom_image(
        self,
        name: str,
        data: Optional[np.ndarray] = None,
        color_map: Optional[str] = "magma",
        color_bar: Optional[Literal["simple", "full"]] = "simple",
        downsample: Optional[bool] = True,
        opacity: Optional[float] = 1.0,
        vrange: Optional[tuple[int, int]] = None,
        # post_processing: Optional[PostProcessingConfig] = None,
        **kwargs,
    ):
        image_source = "device_monitor"

        image_exits = self._check_curve_id(name, self._images)
        if image_exits:
            raise ValueError(f"Monitor with ID '{name}' already exists in widget '{self.gui_id}'.")

        image_config = ImageItemConfig(
            widget_class="BECImageItem",
            parent_id=self.gui_id,
            monitor=name,
            color_map=color_map,
            color_bar=color_bar,
            downsample=downsample,
            opacity=opacity,
            vrange=vrange,
            # post_processing=post_processing,
            **kwargs,
        )

        image = self._add_image_object(source=image_source, config=image_config, data=data)
        return image

    def apply_setting_to_images(
        self, setting_method_name: str, args: list, kwargs: dict, image_id: str = None
    ):
        """
        Apply a setting to all images or a specific image by its ID.

        Args:
            setting_method_name (str): The name of the method to apply (e.g., 'set_color_map').
            args (list): Positional arguments for the setting method.
            kwargs (dict): Keyword arguments for the setting method.
            image_id (str, optional): The ID of the specific image to apply the setting to. If None, applies to all images.
        """
        if image_id:
            image = self.find_widget_by_id(image_id)
            if image:
                getattr(image, setting_method_name)(*args, **kwargs)
        else:
            for source, images in self._images.items():
                for _, image in images.items():
                    getattr(image, setting_method_name)(*args, **kwargs)

    def set_vrange(self, vmin: float, vmax: float, name: str = None):
        """
        Set the range of the color bar.
        If name is not specified, then set vrange for all images.
        Args:
            vmin(float): Minimum value of the color bar.
            vmax(float): Maximum value of the color bar.
            name(str): The name of the image. If None, apply to all images.
        """
        self.apply_setting_to_images("set_vrange", args=[vmin, vmax], kwargs={}, image_id=name)

    def set_color_map(self, cmap: str, name: str = None):
        """
        Set the color map of the image.
        If name is not specified, then set color map for all images.
        Args:
            cmap(str): The color map of the image.
            name(str): The name of the image. If None, apply to all images.
        """
        self.apply_setting_to_images("set_color_map", args=[cmap], kwargs={}, image_id=name)

    def set_processing(self, name: str = None, **kwargs):
        """
        Set the post processing of the image.
        If name is not specified, then set post processing for all images.
        Args:
            name(str): The name of the image. If None, apply to all images.
            **kwargs: Keyword arguments for the properties to be set.
        Possible properties:
            - fft: bool
            - log: bool
            - rot: int
            - transpose: bool
        """
        self.apply_setting_to_images("set", args=[], kwargs=kwargs, image_id=name)

    def set_image_properties(self, name: str = None, **kwargs):
        """
        Set the properties of the image.
        Args:
            name(str): The name of the image. If None, apply to all images.
            **kwargs: Keyword arguments for the properties to be set.
        Possible properties:
            - downsample: bool
            - color_map: str
            - monitor: str
            - opacity: float
            - vrange: tuple[int,int]
            - fft: bool
            - log: bool
            - rot: int
            - transpose: bool
        """
        self.apply_setting_to_images("set", args=[], kwargs=kwargs, image_id=name)

    def set_fft(self, enable: bool = False, name: str = None):
        """
        Set the FFT of the image.
        If name is not specified, then set FFT for all images.
        Args:
            enable(bool): Whether to perform FFT on the monitor data.
            name(str): The name of the image. If None, apply to all images.
        """
        self.apply_setting_to_images("set_fft", args=[enable], kwargs={}, image_id=name)

    def set_log(self, enable: bool = False, name: str = None):
        """
        Set the log of the image.
        If name is not specified, then set log for all images.
        Args:
            enable(bool): Whether to perform log on the monitor data.
            name(str): The name of the image. If None, apply to all images.
        """
        self.apply_setting_to_images("set_log", args=[enable], kwargs={}, image_id=name)

    def set_rotation(self, deg_90: int = 0, name: str = None):
        """
        Set the rotation of the image.
        If name is not specified, then set rotation for all images.
        Args:
            deg_90(int): The rotation angle of the monitor data before displaying.
            name(str): The name of the image. If None, apply to all images.
        """
        self.apply_setting_to_images("set_rotation", args=[deg_90], kwargs={}, image_id=name)

    def set_transpose(self, enable: bool = False, name: str = None):
        """
        Set the transpose of the image.
        If name is not specified, then set transpose for all images.
        Args:
            enable(bool): Whether to transpose the monitor data before displaying.
            name(str): The name of the image. If None, apply to all images.
        """
        self.apply_setting_to_images("set_transpose", args=[enable], kwargs={}, image_id=name)

    def toggle_threading(self, use_threading: bool):
        """
        Toggle threading for the widgets postprocessing and updating.
        Args:
            use_threading(bool): Whether to use threading.
        """
        self.use_threading = use_threading
        if self.use_threading is False and self.thread.isRunning():
            self.cleanup()

    @pyqtSlot(dict)
    def on_image_update(self, msg: dict):
        """
        Update the image of the device monitor from bec.
        Args:
            msg(dict): The message from bec.
        """
        data = msg["data"]
        device = msg["device"]
        image_to_update = self._images["device_monitor"][device]
        processing_config = image_to_update.config.processing
        self.processor.set_config(processing_config)
        if self.use_threading:
            print("using threaded version")
            self._create_thread_worker(device, data)
        else:
            print("using NON-threaded version")
            data = self.processor.process_image(data)
            self.update_image(device, data)

    @pyqtSlot(str, np.ndarray)
    def update_image(self, device: str, data: np.ndarray):
        """
        Update the image of the device monitor.
        Args:
            device(str): The name of the device.
            data(np.ndarray): The data to be updated.
        """
        image_to_update = self._images["device_monitor"][device]
        image_to_update.updateImage(data)

    def _connect_device_monitor(self, monitor: str):
        """
        Connect to the device monitor.
        Args:
            monitor(str): The name of the monitor.
        """
        image_item = self.find_widget_by_id(monitor)
        try:
            previous_monitor = image_item.config.monitor
        except AttributeError:
            previous_monitor = None
        if previous_monitor != monitor:
            if previous_monitor:
                self.bec_dispatcher.disconnect_slot(
                    self.on_image_update, MessageEndpoints.device_monitor(previous_monitor)
                )
            if monitor:
                self.bec_dispatcher.connect_slot(
                    self.on_image_update, MessageEndpoints.device_monitor(monitor)
                )
                image_item.set_monitor(monitor)

    def _add_image_object(
        self, source: str, name: str, config: ImageItemConfig, data=None
    ) -> BECImageItem:  # TODO fix types
        image = BECImageItem(config=config, parent_image=self)
        self.plot_item.addItem(image)
        self._images[source][name] = image
        self.config.images[name] = config
        if data is not None:
            image.setImage(data)
        return image

    def _check_image_id(self, val: Any, dict_to_check: dict) -> bool:
        """
        Check if val is in the values of the dict_to_check or in the values of the nested dictionaries.
        Args:
            val(Any): Value to check.
            dict_to_check(dict): Dictionary to check.

        Returns:
            bool: True if val is in the values of the dict_to_check or in the values of the nested dictionaries, False otherwise.
        """
        if val in dict_to_check.keys():
            return True
        for key in dict_to_check:
            if isinstance(dict_to_check[key], dict):
                if self._check_image_id(val, dict_to_check[key]):
                    return True
        return False

    def cleanup(self):
        """
        Clean up the widget.
        """
        print(f"Cleaning up {self.gui_id}")
        for monitor in self._images["device_monitor"]:
            self.bec_dispatcher.disconnect_slot(
                self.on_image_update, MessageEndpoints.device_monitor(monitor)
            )
        if self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()


class ImageProcessor:
    """
    Class for processing the image data.
    """

    def __init__(self, config: ProcessingConfig = None):
        if config is None:
            config = ProcessingConfig()
        self.config = config

    def set_config(self, config: ProcessingConfig):
        """
        Set the configuration of the processor.
        Args:
            config(ProcessingConfig): The configuration of the processor.
        """
        self.config = config

    def FFT(self, data: np.ndarray) -> np.ndarray:
        """
        Perform FFT on the data.
        Args:
            data(np.ndarray): The data to be processed.

        Returns:
            np.ndarray: The processed data.
        """
        return np.abs(np.fft.fftshift(np.fft.fft2(data)))

    def rotation(self, data: np.ndarray, rotate_90: int) -> np.ndarray:
        """
        Rotate the data by 90 degrees n times.
        Args:
            data(np.ndarray): The data to be processed.
            rotate_90(int): The number of 90 degree rotations.

        Returns:
            np.ndarray: The processed data.
        """
        return np.rot90(data, k=rotate_90, axes=(0, 1))

    def transpose(self, data: np.ndarray) -> np.ndarray:
        """
        Transpose the data.
        Args:
            data(np.ndarray): The data to be processed.

        Returns:
            np.ndarray: The processed data.
        """
        return np.transpose(data)

    def log(self, data: np.ndarray) -> np.ndarray:
        """
        Perform log on the data.
        Args:
            data(np.ndarray): The data to be processed.

        Returns:
            np.ndarray: The processed data.
        """
        # TODO this is not final solution -> data should stay as int16
        data = data.astype(np.float32)
        offset = 1e-6
        data_offset = data + offset
        return np.log10(data_offset)

    # def center_of_mass(self, data: np.ndarray) -> tuple:  # TODO check functionality
    #     return np.unravel_index(np.argmax(data), data.shape)

    def process_image(self, data: np.ndarray) -> np.ndarray:
        """
        Process the data according to the configuration.
        Args:
            data(np.ndarray): The data to be processed.

        Returns:
            np.ndarray: The processed data.
        """
        if self.config.fft:
            data = self.FFT(data)
        if self.config.rotation is not None:
            data = self.rotation(data, self.config.rotation)
        if self.config.transpose:
            data = self.transpose(data)
        if self.config.log:
            data = self.log(data)
        return data


class ProcessorWorker(QObject):
    """
    Worker for processing the image data.
    """

    processed = pyqtSignal(str, np.ndarray)
    stopRequested = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, processor):
        super().__init__()
        self.processor = processor
        self._isRunning = False
        self.stopRequested.connect(self.stop)

    @pyqtSlot(str, np.ndarray)
    def process_image(self, device: str, image: np.ndarray):
        """
        Process the image data.
        Args:
            device(str): The name of the device.
            image(np.ndarray): The image data.
        """
        self._isRunning = True
        processed_image = self.processor.process_image(image)
        self._isRunning = False
        if not self._isRunning:
            self.processed.emit(device, processed_image)
            self.finished.emit()

    def stop(self):
        self._isRunning = False
