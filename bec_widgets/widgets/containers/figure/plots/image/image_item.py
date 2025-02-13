from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional

import numpy as np
import pyqtgraph as pg
from bec_lib.logger import bec_logger
from pydantic import Field

from bec_widgets.utils import BECConnector, ConnectionConfig
from bec_widgets.widgets.containers.figure.plots.image.image_processor import (
    ImageStats,
    ProcessingConfig,
)

if TYPE_CHECKING:
    from bec_widgets.widgets.containers.figure.plots.image.image import BECImageShow

logger = bec_logger.logger


class ImageItemConfig(ConnectionConfig):
    parent_id: Optional[str] = Field(None, description="The parent plot of the image.")
    monitor: Optional[str] = Field(None, description="The name of the monitor.")
    source: Optional[str] = Field(None, description="The source of the curve.")
    color_map: Optional[str] = Field("magma", description="The color map of the image.")
    downsample: Optional[bool] = Field(True, description="Whether to downsample the image.")
    opacity: Optional[float] = Field(1.0, description="The opacity of the image.")
    vrange: Optional[tuple[float | int, float | int]] = Field(
        None, description="The range of the color bar. If None, the range is automatically set."
    )
    color_bar: Optional[Literal["simple", "full"]] = Field(
        "simple", description="The type of the color bar."
    )
    autorange: Optional[bool] = Field(True, description="Whether to autorange the color bar.")
    autorange_mode: Optional[Literal["max", "mean"]] = Field(
        "mean", description="Whether to use the mean of the image for autoscaling."
    )
    processing: ProcessingConfig = Field(
        default_factory=ProcessingConfig, description="The post processing of the image."
    )


# TODO old version will be deprecated
class BECImageItem(BECConnector, pg.ImageItem):
    USER_ACCESS = [
        "_rpc_id",
        "_config_dict",
        "set",
        "set_fft",
        "set_log",
        "set_rotation",
        "set_transpose",
        "set_opacity",
        "set_autorange",
        "set_autorange_mode",
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
        super().__init__(config=config, gui_id=gui_id, **kwargs)
        pg.ImageItem.__init__(self)

        self.parent_image = parent_image
        self.colorbar_bar = None
        self._raw_data = None

        self._add_color_bar(
            self.config.color_bar, self.config.vrange
        )  # TODO can also support None to not have any colorbar
        self.apply_config()
        if kwargs:
            self.set(**kwargs)
        self.connected = False

    @property
    def raw_data(self) -> np.ndarray:
        return self._raw_data

    @raw_data.setter
    def raw_data(self, data: np.ndarray):
        self._raw_data = data

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
            - autorange_mode
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
            "autorange_mode": self.set_autorange_mode,
        }
        for key, value in kwargs.items():
            if key in method_map:
                method_map[key](value)
            else:
                logger.warning(f"Warning: '{key}' is not a recognized property.")

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
        if self.color_bar and autorange:
            self.color_bar.autoHistogramRange()

    def set_autorange_mode(self, mode: Literal["max", "mean"] = "mean"):
        """
        Set the autorange mode to scale the vrange of the color bar. Choose between min/max or mean +/- std.

        Args:
            mode(Literal["max","mean"]): Max for min/max or mean for mean +/- std.
        """
        self.config.autorange_mode = mode

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

    def auto_update_vrange(self, stats: ImageStats) -> None:
        """Auto update of the vrange base on the stats of the image.

        Args:
            stats(ImageStats): The stats of the image.
        """
        fumble_factor = 2
        if self.config.autorange_mode == "mean":
            vmin = max(stats.mean - fumble_factor * stats.std, 0)
            vmax = stats.mean + fumble_factor * stats.std
            self.set_vrange(vmin, vmax, change_autorange=False)
            return
        if self.config.autorange_mode == "max":
            self.set_vrange(max(stats.minimum, 0), stats.maximum, change_autorange=False)
            return

    def set_vrange(
        self,
        vmin: float = None,
        vmax: float = None,
        vrange: tuple[float, float] = None,
        change_autorange: bool = True,
    ):
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
        if change_autorange:
            self.config.autorange = False
        if self.color_bar is not None:
            if self.config.color_bar == "simple":
                self.color_bar.setLevels(low=vmin, high=vmax)
            elif self.config.color_bar == "full":
                # pylint: disable=unexpected-keyword-arg
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
            self.parent_image.addItem(self.color_bar, row=1, col=1)
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
            self.parent_image.addItem(self.color_bar, row=1, col=1)

            # save settings
            self.config.color_bar = "full"
        else:
            raise ValueError("style should be 'simple' or 'full'")

    def remove(self):
        """Remove the curve from the plot."""
        self.parent_image.remove_image(self.config.monitor)
        self.rpc_register.remove_rpc(self)
