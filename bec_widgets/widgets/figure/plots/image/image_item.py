from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional

import numpy as np
import pyqtgraph as pg
from pydantic import Field

from bec_widgets.utils import BECConnector, ConnectionConfig
from bec_widgets.widgets.figure.plots.image.image_processor import ProcessingConfig

if TYPE_CHECKING:
    from bec_widgets.widgets.figure.plots.image.image import BECImageShow


class ImageItemConfig(ConnectionConfig):
    parent_id: Optional[str] = Field(None, description="The parent plot of the image.")
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
    autorange: Optional[bool] = Field(True, description="Whether to autorange the color bar.")
    processing: ProcessingConfig = Field(
        default_factory=ProcessingConfig, description="The post processing of the image."
    )


class BECImageItem(BECConnector, pg.ImageItem):
    USER_ACCESS = [
        "rpc_id",
        "config_dict",
        "set",
        "set_fft",
        "set_log",
        "set_rotation",
        "set_transpose",
        "set_opacity",
        "set_autorange",
        "set_color_map",
        "set_auto_downsample",
        "set_monitor",
        "set_vrange",
        "get_data",
    ]

    def __init__(
        self,
        config: Optional[ImageItemConfig] = None,
        gui_id: Optional[str] = None,
        parent_image: Optional[BECImageShow] = None,
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
        """
        Apply current configuration.
        """
        self.set_color_map(self.config.color_map)
        self.set_auto_downsample(self.config.downsample)
        if self.config.vrange is not None:
            self.set_vrange(vrange=self.config.vrange)

    def set(self, **kwargs):
        """
        Set the properties of the image.

        Args:
            **kwargs: Keyword arguments for the properties to be set.

        Possible properties:
            - downsample
            - color_map
            - monitor
            - opacity
            - vrange
            - fft
            - log
            - rot
            - transpose
        """
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
        """
        Set the FFT of the image.

        Args:
            enable(bool): Whether to perform FFT on the monitor data.
        """
        self.config.processing.fft = enable

    def set_log(self, enable: bool = False):
        """
        Set the log of the image.

        Args:
            enable(bool): Whether to perform log on the monitor data.
        """
        self.config.processing.log = enable
        if enable and self.color_bar and self.config.color_bar == "full":
            self.color_bar.autoHistogramRange()

    def set_rotation(self, deg_90: int = 0):
        """
        Set the rotation of the image.

        Args:
            deg_90(int): The rotation angle of the monitor data before displaying.
        """
        self.config.processing.rotation = deg_90

    def set_transpose(self, enable: bool = False):
        """
        Set the transpose of the image.

        Args:
            enable(bool): Whether to transpose the image.
        """
        self.config.processing.transpose = enable

    def set_opacity(self, opacity: float = 1.0):
        """
        Set the opacity of the image.

        Args:
            opacity(float): The opacity of the image.
        """
        self.setOpacity(opacity)
        self.config.opacity = opacity

    def set_autorange(self, autorange: bool = False):
        """
        Set the autorange of the color bar.

        Args:
            autorange(bool): Whether to autorange the color bar.
        """
        self.config.autorange = autorange
        if self.color_bar is not None:
            self.color_bar.autoHistogramRange()

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
        self.config.autorange = False
        if self.color_bar is not None:
            if self.config.color_bar == "simple":
                self.color_bar.setLevels(low=vmin, high=vmax)
            elif self.config.color_bar == "full":
                self.color_bar.setLevels(min=vmin, max=vmax)
                self.color_bar.setHistogramRange(vmin - 0.1 * vmin, vmax + 0.1 * vmax)

    def get_data(self) -> np.ndarray:
        """
        Get the data of the image.
        Returns:
            np.ndarray: The data of the image.
        """
        return self.image

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
