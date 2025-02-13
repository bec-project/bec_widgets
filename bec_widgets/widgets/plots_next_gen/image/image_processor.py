from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, Field
from qtpy.QtCore import QObject, Signal


@dataclass
class ImageStats:
    """Container to store stats of an image."""

    maximum: float
    minimum: float
    mean: float
    std: float

    @classmethod
    def from_data(cls, data: np.ndarray) -> ImageStats:
        """
        Get the statistics of the image data.

        Args:
            data(np.ndarray): The image data.

        Returns:
            ImageStats: The statistics of the image data.
        """
        return cls(maximum=np.max(data), minimum=np.min(data), mean=np.mean(data), std=np.std(data))


# noinspection PyDataclass
class ProcessingConfig(BaseModel):
    fft: bool = Field(False, description="Whether to perform FFT on the monitor data.")
    log: bool = Field(False, description="Whether to perform log on the monitor data.")
    transpose: bool = Field(
        False, description="Whether to transpose the monitor data before displaying."
    )
    rotation: int = Field(
        0, description="The rotation angle of the monitor data before displaying."
    )
    stats: ImageStats = Field(
        ImageStats(maximum=0, minimum=0, mean=0, std=0),
        description="The statistics of the image data.",
    )

    model_config: dict = {"validate_assignment": True}


class ImageProcessor(QObject):
    """
    Class for processing the image data.
    """

    image_processed = Signal(np.ndarray)

    def __init__(self, parent=None, config: ProcessingConfig = None):
        super().__init__(parent=parent)
        if config is None:
            config = ProcessingConfig()
        self.config = config
        self._current_thread = None

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

    def update_image_stats(self, data: np.ndarray) -> None:
        """Get the statistics of the image data.

        Args:
            data(np.ndarray): The image data.

        """
        self.config.stats.maximum = np.max(data)
        self.config.stats.minimum = np.min(data)
        self.config.stats.mean = np.mean(data)
        self.config.stats.std = np.std(data)

    def process_image(self, data: np.ndarray) -> np.ndarray:
        """Core processing logic without threading overhead."""
        if self.config.fft:
            data = self.FFT(data)
        if self.config.rotation is not None:
            data = self.rotation(data, self.config.rotation)
        if self.config.transpose:
            data = self.transpose(data)
        if self.config.log:
            data = self.log(data)
        self.update_image_stats(data)
        return data
