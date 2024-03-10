from __future__ import annotations

from collections import defaultdict
from typing import Literal, Optional, Any

import numpy as np
import pyqtgraph as pg
from pydantic import Field, BaseModel
from qtpy.QtCore import QThread, QObject
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtWidgets import QWidget

from bec_lib import MessageEndpoints
from bec_widgets.utils import ConnectionConfig, BECConnector
from bec_widgets.widgets.plots import BECPlotBase, WidgetConfig


class PostProcessingConfig(BaseModel):
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
    color_map: Optional[str] = Field("magma", description="The color map of the image.")
    downsample: Optional[bool] = Field(True, description="Whether to downsample the image.")
    opacity: Optional[float] = Field(1.0, description="The opacity of the image.")
    vrange: Optional[tuple[int, int]] = Field(
        None, description="The range of the color bar. If None, the range is automatically set."
    )
    color_bar: Optional[Literal["simple", "full"]] = Field(
        "simple", description="The type of the color bar."
    )
    post_processing: PostProcessingConfig = Field(
        default_factory=PostProcessingConfig, description="The post processing of the image."
    )


class ImageConfig(WidgetConfig):
    images: dict[str, ImageItemConfig] = Field(
        {},
        description="The configuration of the images. The key is the name of the image (source).",
    )


class BECImageItem(BECConnector, pg.ImageItem):
    USER_ACCESS = ["set", "set_color_map", "set_auto_downsample", "set_monitor", "set_vrange"]

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
            "vrange": self.set_vrange,
        }
        for key, value in kwargs.items():
            if key in method_map:
                method_map[key](value)
            else:
                print(f"Warning: '{key}' is not a recognized property.")

    def set_color_map(self, cmap: str = "magma"):
        """
        Set the color map of the image.
        Args:
            cmap(str): The color map of the image.
        """
        self.setColorMap(cmap)
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


class BECImageShow(BECPlotBase):
    USER_ACCESS = ["add_monitor_image", "add_custom_image", "set_vrange", "set_color_map"]

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

        self.images = defaultdict(dict)

    def find_widget_by_id(self, item_id: str) -> BECImageItem:
        """
        Find the widget by its gui_id.
        Args:
            item_id(str): The gui_id of the widget.

        Returns:
            BECImageItem: The widget with the given gui_id.
        """
        for source, images in self.images.items():
            for key, value in images.items():
                if key == item_id and isinstance(value, BECImageItem):
                    return value
                elif isinstance(value, dict):
                    result = self.find_widget_by_id(item_id)
                    if result is not None:
                        return result

    def change_gui_id(self, new_gui_id: str):
        """
        Change the GUI ID of the image widget and update the parent_id in all associated curves.

        Args:
            new_gui_id (str): The new GUI ID to be set for the image widget.
        """
        # Update the gui_id in the waveform widget itself
        self.gui_id = new_gui_id
        self.config.gui_id = new_gui_id

        for source, images in self.images.items():
            for id, image_item in images.items():
                image_item.config.parent_id = new_gui_id

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

        image_exits = self._check_image_id(monitor, self.images)
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

        image_exits = self._check_curve_id(name, self.images)
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

    def set_vrange(self, vmin: float, vmax: float, name: str = None):
        """
        Set the range of the color bar.
        If name is not specified, then set vrange for all images.
        Args:
            vmin(float): Minimum value of the color bar.
            vmax(float): Maximum value of the color bar.
            name(str): The name of the image.
        """
        if name is None:
            for source, images in self.images.items():
                for id, image in images.items():
                    image.set_vrange(vmin, vmax)
        else:
            image = self.find_widget_by_id(name)
            image.set_vrange(vmin, vmax)

    def set_color_map(self, cmap: str, name: str = None):
        """
        Set the color map of the image.
        If name is not specified, then set color map for all images.
        Args:
            cmap(str): The color map of the image.
            name(str): The name of the image.
        """
        if name is None:
            for source, images in self.images.items():
                for id, image in images.items():
                    image.set_color_map(cmap)
        else:
            image = self.find_widget_by_id(name)
            image.set_color_map(cmap)

    @pyqtSlot(dict)
    def on_image_update(self, msg: dict):
        data = msg["data"]
        device = msg["device"]
        # TODO postprocessing
        image_to_update = self.images["device_monitor"][device]
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
        self.images[source][name] = image
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
        for monitor in self.images["device_monitor"]:
            self.bec_dispatcher.disconnect_slot(
                self.on_image_update, MessageEndpoints.device_monitor(monitor)
            )
