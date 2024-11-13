from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field
from qtpy.QtCore import QObject, Signal, Slot


@dataclass
class ImageStats:
    """Container to store stats of an image."""

    maximum: float
    minimum: float
    mean: float
    std: float


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
    model_config: dict = {"validate_assignment": True}
    stats: ImageStats = Field(
        ImageStats(maximum=0, minimum=0, mean=0, std=0),
        description="The statistics of the image data.",
    )


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
        self.update_image_stats(data)
        return data


class ProcessorWorker(QObject):
    """
    Worker for processing the image data.
    """

    processed = Signal(str, np.ndarray)
    stats = Signal(str, ImageStats)
    stopRequested = Signal()
    finished = Signal()

    def __init__(self, processor):
        super().__init__()
        self.processor = processor
        self._isRunning = False
        self.stopRequested.connect(self.stop)

    @Slot(str, np.ndarray)
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
            self.stats.emit(self.processor.config.stats)
            self.finished.emit()

    def stop(self):
        self._isRunning = False
