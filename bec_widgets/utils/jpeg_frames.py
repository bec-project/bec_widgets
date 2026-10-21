"""
Helpers for preview frames that arrive JPEG-compressed.

A JPEG preview frame is a ``DevicePreviewMessage`` whose ``data`` is a flat uint8 array holding
the JPEG bytes, with message metadata ``{"encoding": "jpeg", "shape": [h, w], "channels": 1 | 3}``.
Frames without that metadata are passed through untouched.

The ``*_preview`` functions match the ``preprocess`` hook of ``BECDispatcher.connect_slot``:
they run on the thread that receives Redis messages, so decoding never blocks the GUI thread.
"""

from __future__ import annotations

import time

import numpy as np
from qtpy.QtCore import QByteArray
from qtpy.QtGui import QImage

try:  # libjpeg-turbo bindings; much faster than Qt's own JPEG plugin
    import simplejpeg
except ImportError:  # pragma: no cover - depends on the environment
    simplejpeg = None


def is_jpeg_frame(metadata: dict | None) -> bool:
    """Whether a preview message carries a JPEG-compressed frame."""
    return bool(metadata) and metadata.get("encoding") == "jpeg"


def _as_bytes(data: bytes | np.ndarray) -> bytes:
    if isinstance(data, np.ndarray):
        return data.tobytes()
    return bytes(data)


def qimage_to_array(image: QImage) -> np.ndarray:
    """
    Copy an 8-bit grayscale or RGB QImage into a numpy array.

    Args:
        image (QImage): The image; other formats are converted to RGB888 first.

    Returns:
        np.ndarray: (h, w) uint8 for grayscale, (h, w, 3) uint8 otherwise.
    """
    if image.format() not in (QImage.Format.Format_Grayscale8, QImage.Format.Format_RGB888):
        image = image.convertToFormat(QImage.Format.Format_RGB888)
    channels = 1 if image.format() == QImage.Format.Format_Grayscale8 else 3
    h, w, bpl = image.height(), image.width(), image.bytesPerLine()
    buffer = np.frombuffer(image.constBits(), dtype=np.uint8, count=h * bpl).reshape(h, bpl)
    array = buffer[:, : w * channels].reshape(h, w, channels) if channels == 3 else buffer[:, :w]
    return array.copy()


def decode_jpeg(data: bytes | np.ndarray, channels: int | None = None) -> np.ndarray:
    """
    Decode JPEG bytes into a numpy array.

    Args:
        data (bytes | np.ndarray): The JPEG bytes, or a uint8 array holding them.
        channels (int | None): 1 for grayscale, 3 for RGB, None to keep what the file has.

    Returns:
        np.ndarray: (h, w) uint8 for grayscale, (h, w, 3) uint8 for RGB.
    """
    raw = _as_bytes(data)
    if simplejpeg is not None:
        if channels is None:
            channels = 1 if simplejpeg.decode_jpeg_header(raw)[2] == "Gray" else 3
        colorspace = "GRAY" if channels == 1 else "RGB"
        image = simplejpeg.decode_jpeg(raw, colorspace=colorspace)
        return image[..., 0] if channels == 1 else image
    qimage = QImage.fromData(QByteArray(raw), "JPG")
    if qimage.isNull():
        raise ValueError("Could not decode JPEG frame")
    if channels == 1:
        qimage = qimage.convertToFormat(QImage.Format.Format_Grayscale8)
    return qimage_to_array(qimage)


def decode_jpeg_preview(msg_content: dict, metadata: dict) -> tuple[dict, dict]:
    """
    Dispatcher preprocess hook: replace JPEG bytes in a preview message by the decoded array.

    Args:
        msg_content (dict): Content of the DevicePreviewMessage.
        metadata (dict): Metadata of the message.

    Returns:
        tuple[dict, dict]: New content and metadata; the inputs are not modified.
    """
    if not is_jpeg_frame(metadata):
        return msg_content, metadata
    data = msg_content.get("data")
    t0 = time.perf_counter()
    image = decode_jpeg(data, metadata.get("channels"))
    decode_ms = (time.perf_counter() - t0) * 1e3
    metadata = {**metadata, "decode_ms": decode_ms, "transfer_nbytes": int(np.size(data))}
    return {**msg_content, "data": image}, metadata


def qimage_preview(msg_content: dict, metadata: dict) -> tuple[dict, dict]:
    """
    Dispatcher preprocess hook for picture-only views: decode the frame into a QImage with Qt.

    JPEG frames are decoded by Qt's JPEG plugin; raw frames are scaled to 8 bit (0 to the
    99.9th percentile). The QImage is put under ``msg_content["qimage"]``.

    Args:
        msg_content (dict): Content of the DevicePreviewMessage.
        metadata (dict): Metadata of the message.

    Returns:
        tuple[dict, dict]: New content and metadata; the inputs are not modified.
    """
    data = msg_content.get("data")
    t0 = time.perf_counter()
    if is_jpeg_frame(metadata):
        qimage = QImage.fromData(QByteArray(_as_bytes(data)), "JPG")
    else:
        frame = np.asarray(data)
        if frame.ndim != 2:
            return msg_content, metadata
        top = float(np.percentile(frame[::8, ::8], 99.9)) or 1.0
        frame8 = np.ascontiguousarray(np.clip(frame * (255.0 / top), 0, 255).astype(np.uint8))
        h, w = frame8.shape
        qimage = QImage(frame8.data, w, h, frame8.strides[0], QImage.Format.Format_Grayscale8)
        qimage = qimage.copy()  # detach from the numpy buffer
    decode_ms = (time.perf_counter() - t0) * 1e3
    metadata = {**metadata, "decode_ms": decode_ms, "transfer_nbytes": int(np.asarray(data).nbytes)}
    return {**msg_content, "qimage": qimage}, metadata
