"""The Image widget shows a detector preview that is published over ZMQ."""

import json

import numpy as np
import pytest

from bec_widgets.tests.fake_devices import FakeDevice
from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.plots.image.image import Image

zmq = pytest.importorskip("zmq")

# pylint: disable=protected-access


@pytest.fixture
def publisher():
    """A ZMQ publisher as an area detector IOC runs it (ADZMQ); yields it with its address."""
    socket = zmq.Context.instance().socket(zmq.PUB)
    port = socket.bind_to_random_port("tcp://127.0.0.1")
    yield socket, f"tcp://127.0.0.1:{port}"
    socket.close(linger=0)


def test_image_shows_preview_frames_of_a_zmq_publisher(qtbot, mocked_client, publisher):
    """
    A camera with no Redis preview: its preview signal only advertises the ZMQ stream of the
    IOC. The widget is used as for any preview signal; the Data API reads the stream.
    """
    socket, address = publisher
    camera = FakeDevice("cam")
    camera._info["signals"]["preview"] = {
        "obj_name": "cam_preview",
        "component_name": "preview",
        "signal_class": "PreviewSignal",
        "describe": {
            "signal_info": {
                "ndim": 2,
                "transports": [
                    {"transport": "zmq", "address": address, "encoder": "adzmq-array-1.0"}
                ],
            }
        },
    }
    mocked_client.device_manager.add_devices([camera])
    frame = np.arange(12, dtype=np.uint16).reshape(3, 4)
    header = {"htype": "array-1.0", "shape": [3, 4], "type": "uint16"}

    widget = create_widget(qtbot, Image, client=mocked_client)
    widget.image(device="cam", signal="preview")
    assert widget._data_bridge.routes == {("cam", "preview"): "zmq"}

    def frame_shown() -> bool:
        # A subscriber that is still connecting misses frames: publish until one is shown.
        socket.send_multipart([json.dumps(header).encode(), frame.tobytes()])
        return widget.main_image.raw_data is not None

    qtbot.waitUntil(frame_shown, timeout=5000)
    assert np.array_equal(widget.main_image.raw_data, frame)
