from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal, Optional

import numpy as np
from bec_lib.endpoints import MessageEndpoints
from pydantic import BaseModel, Field, ValidationError
from qtpy.QtCore import QThread
from qtpy.QtWidgets import QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot as Slot
from bec_widgets.utils import EntryValidator
from bec_widgets.widgets.figure.plots.image.image_item import BECImageItem, ImageItemConfig
from bec_widgets.widgets.figure.plots.image.image_processor import (
    ImageProcessor,
    ImageStats,
    ProcessorWorker,
)
from bec_widgets.widgets.figure.plots.plot_base import BECPlotBase, SubplotConfig


class ImageConfig(SubplotConfig):
    images: dict[str, ImageItemConfig] = Field(
        {},
        description="The configuration of the images. The key is the name of the image (source).",
    )


class BECImageShow(BECPlotBase):
    USER_ACCESS = [
        "_rpc_id",
        "_config_dict",
        "add_image_by_config",
        "image",
        "add_custom_image",
        "set_vrange",
        "set_color_map",
        "set_autorange",
        "set_autorange_mode",
        "set_monitor",
        "set_processing",
        "set_image_properties",
        "set_fft",
        "set_log",
        "set_rotation",
        "set_transpose",
        "set",
        "set_title",
        "set_x_label",
        "set_y_label",
        "set_x_scale",
        "set_y_scale",
        "set_x_lim",
        "set_y_lim",
        "set_grid",
        "lock_aspect_ratio",
        "export",
        "remove",
        "images",
    ]

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        parent_figure=None,
        config: Optional[ImageConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
        single_image: bool = True,
    ):
        if config is None:
            config = ImageConfig(widget_class=self.__class__.__name__)
        super().__init__(
            parent=parent, parent_figure=parent_figure, config=config, client=client, gui_id=gui_id
        )
        # Get bec shortcuts dev, scans, queue, scan_storage, dap
        self.single_image = single_image
        self.get_bec_shortcuts()
        self.entry_validator = EntryValidator(self.dev)
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
        worker.stats.connect(self.update_vrange)
        worker.finished.connect(thread.quit)
        worker.finished.connect(thread.wait)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        thread.start()

    def find_image_by_monitor(self, item_id: str) -> BECImageItem:
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
                    result = self.find_image_by_monitor(item_id)
                    if result is not None:
                        return result

    def apply_config(self, config: dict | SubplotConfig):
        """
        Apply the configuration to the 1D waveform widget.

        Args:
            config(dict|SubplotConfig): Configuration settings.
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

        for image_id, image_config in config.images.items():
            self.add_image_by_config(image_config)

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
            config.parent_id = self.gui_id
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

    @property
    def images(self) -> list[BECImageItem]:
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

    @images.setter
    def images(self, value: dict[str, dict[str, BECImageItem]]):
        """
        Set the images from a dictionary.

        Args:
            value (dict[str, dict[str, BECImageItem]]): The images to set, organized by source and id.
        """
        self._images = value

    def get_image_dict(self) -> dict[str, dict[str, BECImageItem]]:
        """
        Get all images.

        Returns:
            dict[str, dict[str, BECImageItem]]: The dictionary of images.
        """
        return self._images

    def image(
        self,
        monitor: str,
        color_map: Optional[str] = "magma",
        color_bar: Optional[Literal["simple", "full"]] = "full",
        downsample: Optional[bool] = True,
        opacity: Optional[float] = 1.0,
        vrange: Optional[tuple[int, int]] = None,
        # post_processing: Optional[PostProcessingConfig] = None,
        **kwargs,
    ) -> BECImageItem:
        """
        Add an image to the figure. Always access the first image widget in the figure.

        Args:
            monitor(str): The name of the monitor to display.
            color_bar(Literal["simple","full"]): The type of color bar to display.
            color_map(str): The color map to use for the image.
            data(np.ndarray): Custom data to display.
            vrange(tuple[float, float]): The range of values to display.

        Returns:
            BECImageItem: The image item.
        """
        image_source = "device_monitor_2d"

        image_exits = self._check_image_id(monitor, self._images)
        if image_exits:
            raise ValueError(
                f"Monitor with ID '{monitor}' already exists in widget '{self.gui_id}'."
            )

        # monitor = self.entry_validator.validate_monitor(monitor)

        image_config = ImageItemConfig(
            widget_class="BECImageItem",
            parent_id=self.gui_id,
            color_map=color_map,
            color_bar=color_bar,
            downsample=downsample,
            opacity=opacity,
            vrange=vrange,
            source=image_source,
            monitor=monitor,
            # post_processing=post_processing,
            **kwargs,
        )

        image = self._add_image_object(source=image_source, name=monitor, config=image_config)
        return image

    def add_custom_image(
        self,
        name: str,
        data: Optional[np.ndarray] = None,
        color_map: Optional[str] = "magma",
        color_bar: Optional[Literal["simple", "full"]] = "full",
        downsample: Optional[bool] = True,
        opacity: Optional[float] = 1.0,
        vrange: Optional[tuple[int, int]] = None,
        # post_processing: Optional[PostProcessingConfig] = None,
        **kwargs,
    ):
        image_source = "custom"
        # image_source = "device_monitor_2d"

        image_exits = self._check_image_id(name, self._images)
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

        image = self._add_image_object(
            source=image_source, name=name, config=image_config, data=data
        )
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
            image = self.find_image_by_monitor(image_id)
            if image:
                getattr(image, setting_method_name)(*args, **kwargs)
        else:
            for source, images in self._images.items():
                for _, image in images.items():
                    getattr(image, setting_method_name)(*args, **kwargs)
        self.refresh_image()

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

    def set_autorange(self, enable: bool = False, name: str = None):
        """
        Set the autoscale of the image.

        Args:
            enable(bool): Whether to autoscale the color bar.
            name(str): The name of the image. If None, apply to all images.
        """
        self.apply_setting_to_images("set_autorange", args=[enable], kwargs={}, image_id=name)

    def set_autorange_mode(self, mode: Literal["max", "mean"], name: str = None):
        """
        Set the autoscale mode of the image, that decides how the vrange of the color bar is scaled.
        Choose betwen 'max' -> min/max of the data, 'mean' -> mean +/- fudge_factor*std of the data (fudge_factor~2).

        Args:
            mode(str): The autoscale mode of the image.
            name(str): The name of the image. If None, apply to all images.
        """
        self.apply_setting_to_images("set_autorange_mode", args=[mode], kwargs={}, image_id=name)

    def set_monitor(self, monitor: str, name: str = None):
        """
        Set the monitor of the image.
        If name is not specified, then set monitor for all images.

        Args:
            monitor(str): The name of the monitor.
            name(str): The name of the image. If None, apply to all images.
        """
        self.apply_setting_to_images("set_monitor", args=[monitor], kwargs={}, image_id=name)

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

    def process_image(self, device: str, image: BECImageItem, data: np.ndarray):
        """
        Process the image data.

        Args:
            device(str): The name of the device - image_id of image.
            image(np.ndarray): The image data to be processed.
            data(np.ndarray): The image data to be processed.

        Returns:
            np.ndarray: The processed image data.
        """
        processing_config = image.config.processing
        self.processor.set_config(processing_config)
        if self.use_threading:
            self._create_thread_worker(device, data)
        else:
            data = self.processor.process_image(data)
            self.update_image(device, data)
            self.update_vrange(device, self.processor.config.stats)

    @Slot(dict)
    def on_image_update(self, msg: dict):
        """
        Update the image of the device monitor from bec.

        Args:
            msg(dict): The message from bec.
        """
        data = msg["data"]
        device = msg["device"]
        image = self._images["device_monitor_2d"][device]
        image.raw_data = data
        self.process_image(device, image, data)

    @Slot(str, np.ndarray)
    def update_image(self, device: str, data: np.ndarray):
        """
        Update the image of the device monitor.

        Args:
            device(str): The name of the device.
            data(np.ndarray): The data to be updated.
        """
        image_to_update = self._images["device_monitor_2d"][device]
        image_to_update.updateImage(data, autoLevels=image_to_update.config.autorange)

    @Slot(str, ImageStats)
    def update_vrange(self, device: str, stats: ImageStats):
        """
        Update the scaling of the image.

        Args:
            stats(ImageStats): The statistics of the image.
        """
        image_to_update = self._images["device_monitor_2d"][device]
        if image_to_update.config.autorange:
            image_to_update.auto_update_vrange(stats)

    def refresh_image(self):
        """
        Refresh the image.
        """
        for source, images in self._images.items():
            for image_id, image in images.items():
                data = image.raw_data
                self.process_image(image_id, image, data)

    def _connect_device_monitor_2d(self, monitor: str):
        """
        Connect to the device monitor.

        Args:
            monitor(str): The name of the monitor.
        """
        image_item = self.find_image_by_monitor(monitor)
        try:
            previous_monitor = image_item.config.monitor
        except AttributeError:
            previous_monitor = None
        if previous_monitor and image_item.connected is True:
            self.bec_dispatcher.disconnect_slot(
                self.on_image_update, MessageEndpoints.device_monitor_2d(previous_monitor)
            )
            image_item.connected = False
        if monitor and image_item.connected is False:
            self.entry_validator.validate_monitor(monitor)
            self.bec_dispatcher.connect_slot(
                self.on_image_update, MessageEndpoints.device_monitor_2d(monitor)
            )
            image_item.set_monitor(monitor)
            image_item.connected = True

    def _add_image_object(
        self, source: str, name: str, config: ImageItemConfig, data=None
    ) -> BECImageItem:  # TODO fix types
        config.parent_id = self.gui_id
        image = BECImageItem(config=config, parent_image=self)
        self.plot_item.addItem(image)
        if self.single_image is True and len(self.images) > 0:
            self.remove_image(0)
        self._images[source][name] = image
        if source == "device_monitor_2d":
            self._connect_device_monitor_2d(config.monitor)
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

    def remove_image(self, *identifiers):
        """
        Remove an image from the plot widget.

        Args:
            *identifiers: Identifier of the image to be removed. Can be either an integer (index) or a string (image_id).
        """
        for identifier in identifiers:
            if isinstance(identifier, int):
                self._remove_image_by_order(identifier)
            elif isinstance(identifier, str):
                self._remove_image_by_id(identifier)
            else:
                raise ValueError(
                    "Each identifier must be either an integer (index) or a string (image_id)."
                )

    def _remove_image_by_id(self, image_id):
        for source, images in self._images.items():
            if image_id in images:
                self._disconnect_monitor(image_id)
                image = images.pop(image_id)
                self.removeItem(image.color_bar)
                self.plot_item.removeItem(image)
                del self.config.images[image_id]
                if image in self.images:
                    self.images.remove(image)
                return
        raise KeyError(f"Image with ID '{image_id}' not found.")

    def _remove_image_by_order(self, N):
        """
        Remove an image by its order from the plot widget.

        Args:
            N(int): Order of the image to be removed.
        """
        if N < len(self.images):
            image = self.images[N]
            image_id = image.config.monitor
            self._disconnect_monitor(image_id)
            self.removeItem(image.color_bar)
            self.plot_item.removeItem(image)
            del self.config.images[image_id]
            for source, images in self._images.items():
                if image_id in images:
                    del images[image_id]
                    break
        else:
            raise IndexError(f"Image order {N} out of range.")

    def _disconnect_monitor(self, image_id):
        """
        Disconnect the monitor from the device.

        Args:
            image_id(str): The ID of the monitor.
        """
        image = self.find_image_by_monitor(image_id)
        if image:
            self.bec_dispatcher.disconnect_slot(
                self.on_image_update, MessageEndpoints.device_monitor_2d(image.config.monitor)
            )

    def cleanup(self):
        """
        Clean up the widget.
        """
        for monitor in self._images["device_monitor_2d"]:
            self.bec_dispatcher.disconnect_slot(
                self.on_image_update, MessageEndpoints.device_monitor_2d(monitor)
            )
        self.images.clear()
