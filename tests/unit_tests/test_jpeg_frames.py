"""JPEG preview frames: decoding helpers, dispatcher hooks, Image widget and picture view."""

import threading
from unittest import mock

import numpy as np
import pytest
from qtpy.QtCore import QBuffer, QByteArray, QIODevice
from qtpy.QtGui import QImage

from bec_widgets.examples.jpeg_preview.jpeg_view import JpegView
from bec_widgets.tests.utils import create_widget
from bec_widgets.utils import jpeg_frames
from bec_widgets.utils.bec_dispatcher import QtThreadSafeCallback
from bec_widgets.utils.jpeg_frames import decode_jpeg, decode_jpeg_preview, qimage_preview
from bec_widgets.widgets.plots.image.image import Image


def _jpeg_bytes(image: np.ndarray, quality: int = 95) -> bytes:
    """Encode with Qt so the tests do not need simplejpeg."""
    image = np.ascontiguousarray(image)
    h, w = image.shape[:2]
    if image.ndim == 2:
        qimage = QImage(image.data, w, h, image.strides[0], QImage.Format.Format_Grayscale8)
    else:
        qimage = QImage(image.data, w, h, image.strides[0], QImage.Format.Format_RGB888)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    qimage.save(buffer, "JPG", quality)
    return bytes(data)


def _gradient(h=24, w=40):
    return np.tile(np.linspace(0, 255, w, dtype=np.uint8), (h, 1))


@pytest.fixture(params=["simplejpeg", "qt"])
def decoder(request, monkeypatch):
    if request.param == "qt":
        monkeypatch.setattr(jpeg_frames, "simplejpeg", None)
    elif jpeg_frames.simplejpeg is None:
        pytest.skip("simplejpeg not installed")
    return request.param


def test_decode_jpeg_gray_and_rgb(decoder):
    gray = _gradient()
    decoded = decode_jpeg(np.frombuffer(_jpeg_bytes(gray), np.uint8), channels=1)
    assert decoded.shape == gray.shape and decoded.dtype == np.uint8
    assert np.abs(decoded.astype(int) - gray).max() < 12

    rgb = np.stack([gray, gray[:, ::-1], np.full_like(gray, 128)], axis=-1)
    decoded = decode_jpeg(_jpeg_bytes(rgb), channels=3)
    assert decoded.shape == rgb.shape
    assert np.abs(decoded.astype(int) - rgb).mean() < 6


def test_decode_jpeg_preview_replaces_data_and_keeps_inputs(decoder):
    payload = np.frombuffer(_jpeg_bytes(_gradient()), np.uint8)
    content = {"data": payload, "device": "cam"}
    metadata = {"encoding": "jpeg", "channels": 1, "shape": [24, 40]}
    new_content, new_metadata = decode_jpeg_preview(content, metadata)
    assert new_content["data"].shape == (24, 40)
    assert new_metadata["transfer_nbytes"] == payload.size
    assert new_metadata["decode_ms"] >= 0
    assert content["data"] is payload and "decode_ms" not in metadata


def test_decode_jpeg_preview_passes_raw_frames_through():
    content, metadata = {"data": np.zeros((4, 4))}, {"encoding": "raw"}
    assert decode_jpeg_preview(content, metadata) == (content, metadata)


def test_qimage_preview_jpeg_and_raw():
    content = {"data": np.frombuffer(_jpeg_bytes(_gradient()), np.uint8)}
    new_content, _ = qimage_preview(content, {"encoding": "jpeg"})
    assert new_content["qimage"].size().width() == 40

    raw = {"data": (np.arange(64, dtype=np.uint16) * 100).reshape(8, 8)}
    new_content, _ = qimage_preview(raw, {})
    assert new_content["qimage"].format() == QImage.Format.Format_Grayscale8


def test_callback_preprocess_runs_before_emit(qtbot):
    received = []
    wrapper = QtThreadSafeCallback(
        lambda content, metadata: received.append((content, metadata)),
        preprocess=lambda content, metadata: ({**content, "x": 2}, {**metadata, "y": 3}),
    )
    wrapper({"x": 1}, {})
    qtbot.waitUntil(lambda: bool(received))
    assert received == [({"x": 2}, {"y": 3})]


def test_callback_preprocess_error_drops_message(qtbot):
    received = []

    def fail(content, metadata):
        raise ValueError("broken frame")

    wrapper = QtThreadSafeCallback(lambda *args: received.append(args), preprocess=fail)
    wrapper({"x": 1}, {})
    qtbot.wait(20)
    assert received == []


def test_callback_latest_only_delivers_newest(qtbot):
    received = []
    wrapper = QtThreadSafeCallback(
        lambda content, metadata: received.append(content["n"]), latest_only=True
    )
    # Messages arrive on the Redis thread; the GUI thread is busy until the event loop runs
    sender = threading.Thread(target=lambda: [wrapper({"n": n}, {}) for n in range(5)])
    sender.start()
    sender.join()
    qtbot.waitUntil(lambda: bool(received))
    qtbot.wait(20)
    assert received == [4]
    assert wrapper.dropped == 4
    sender = threading.Thread(target=lambda: wrapper({"n": 5}, {}))
    sender.start()
    sender.join()
    qtbot.waitUntil(lambda: received[-1] == 5)


def test_callbacks_with_different_hooks_are_different_wrappers():
    def slot(content, metadata):
        pass

    plain = QtThreadSafeCallback(slot)
    assert plain == QtThreadSafeCallback(slot)
    assert plain != QtThreadSafeCallback(slot, preprocess=decode_jpeg_preview)
    assert plain != QtThreadSafeCallback(slot, latest_only=True)


def _set_preview_signal(client, device="eiger", signal="preview"):
    client.device_manager.devices[device]._info["signals"][signal] = {
        "obj_name": f"{device}_{signal}",
        "signal_class": "PreviewSignal",
        "component_name": signal,
        "describe": {"signal_info": {"ndim": 2}},
    }


def test_image_preview_connects_with_jpeg_decoding(qtbot, mocked_client):
    view = create_widget(qtbot, Image, client=mocked_client)
    _set_preview_signal(mocked_client)
    with mock.patch.object(view.bec_dispatcher, "connect_slot") as connect_slot:
        view.image(device="eiger", signal="preview")
    kwargs = connect_slot.call_args.kwargs
    assert kwargs["preprocess"] is decode_jpeg_preview
    assert kwargs["latest_only"] is True


def test_image_shows_decoded_jpeg_frame(qtbot, mocked_client, decoder):
    view = create_widget(qtbot, Image, client=mocked_client)
    payload = np.frombuffer(_jpeg_bytes(_gradient()), np.uint8)
    content, metadata = decode_jpeg_preview(
        {"data": payload}, {"encoding": "jpeg", "channels": 1, "frame_id": 7}
    )
    view.on_image_update_2d(content, metadata)
    assert view.main_image.image.shape == (24, 40)
    assert view.last_frame_metadata["frame_id"] == 7


def test_image_autoranges_when_frame_size_changes(qtbot, mocked_client):
    view = create_widget(qtbot, Image, client=mocked_client)
    view.on_image_update_2d({"data": np.zeros((8, 8))}, {})
    view._autorange_on_next_update = False
    with mock.patch.object(view, "auto_range") as auto_range:
        view.on_image_update_2d({"data": np.ones((8, 8))}, {})
        auto_range.assert_not_called()
        view.on_image_update_2d({"data": np.ones((16, 32))}, {})
        auto_range.assert_called_once()


def test_jpeg_view_shows_frame_and_colormap(qtbot, mocked_client):
    view = create_widget(qtbot, JpegView, client=mocked_client)
    content, metadata = qimage_preview(
        {"data": np.frombuffer(_jpeg_bytes(_gradient()), np.uint8)}, {"encoding": "jpeg"}
    )
    with qtbot.waitSignal(view.frame_shown):
        view.on_frame(content, metadata)
    assert view._pixmap_item.pixmap().width() == 40
    view.set_colormap("magma")
    assert len(view._color_table) == 256
    view.on_frame(content, metadata)
    assert view._pixmap_item.pixmap().height() == 24
    view.set_colormap("gray")
    assert view._color_table is None
