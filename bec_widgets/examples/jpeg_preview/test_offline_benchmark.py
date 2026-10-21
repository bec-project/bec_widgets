"""
Offline benchmark of the JPEG preview path, without Redis or a running BEC.

Each frame goes through the same steps as in a live session, one view at a time: the simulated
camera makes and encodes it, BEC serialises and deserialises the message, the receiver-thread
hook decodes it, and the view updates and paints. Run it explicitly:

    QT_QPA_PLATFORM=offscreen python -m pytest -s -p no:randomly \
        bec_widgets/examples/jpeg_preview/test_offline_benchmark.py

Environment variables: BENCH_SIZES (default "512,1024,2048,4096"), BENCH_ENCODINGS
(default "raw,jpeg_gray,jpeg_rgb"), BENCH_FRAMES (default 10), BENCH_OUT (JSON file to write).
"""

from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path

import pytest
from bec_lib import messages
from bec_lib.serialization import MsgpackSerialization

from bec_widgets.examples.jpeg_preview.jpeg_view import JpegView
from bec_widgets.tests.fixtures import *  # noqa: F401,F403 pylint: disable=wildcard-import
from bec_widgets.tests.utils import create_widget
from bec_widgets.utils.jpeg_frames import decode_jpeg_preview, qimage_preview
from bec_widgets.widgets.plots.image.image import Image

sim_jpeg_camera = pytest.importorskip(
    "ophyd_devices.sim.sim_jpeg_camera", reason="needs the ophyd_devices SimJpegCamera"
)

SIZES = [int(s) for s in os.environ.get("BENCH_SIZES", "512,1024,2048,4096").split(",")]
ENCODINGS = os.environ.get("BENCH_ENCODINGS", "raw,jpeg_gray,jpeg_rgb").split(",")
FRAMES = int(os.environ.get("BENCH_FRAMES", "10"))


def _ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1e3


def test_offline_benchmark(qtbot, mocked_client):
    camera = sim_jpeg_camera.SimJpegCamera(name="jpeg_cam")
    image = create_widget(qtbot, Image, client=mocked_client, popups=False)
    image.enable_colorbar(enabled=True, style="full")
    view = create_widget(qtbot, JpegView, client=mocked_client)
    for widget in (image, view):
        widget.resize(900, 800)
        widget.show()
        qtbot.waitExposed(widget)

    rows = []
    for size in SIZES:
        for encoding in ENCODINGS:
            camera.configure_stream(width=size, height=size, encoding=encoding)
            camera.make_frame()  # builds the frame source for this size
            samples = {key: [] for key in ("make", "encode", "wire", "deser", "dec_img")}
            samples.update({"img_gui": [], "dec_pic": [], "pic_gui": []})
            for _ in range(FRAMES):
                t0 = time.perf_counter()
                data, metadata = camera.make_frame()
                samples["make"].append(_ms(t0))
                samples["encode"].append(metadata["encode_ms"])
                msg = messages.DevicePreviewMessage(
                    device="jpeg_cam", signal="preview", data=data, metadata=metadata
                )
                wire = MsgpackSerialization.dumps(msg)
                samples["wire"].append(len(wire) / 1e3)
                t0 = time.perf_counter()
                received = MsgpackSerialization.loads(wire)
                samples["deser"].append(_ms(t0))

                t0 = time.perf_counter()
                content, md = decode_jpeg_preview(received.content, received.metadata)
                samples["dec_img"].append(_ms(t0))
                t0 = time.perf_counter()
                image.on_image_update_2d(content, md)
                image.plot_widget.viewport().repaint()
                samples["img_gui"].append(_ms(t0))

                t0 = time.perf_counter()
                content, md = qimage_preview(received.content, received.metadata)
                samples["dec_pic"].append(_ms(t0))
                t0 = time.perf_counter()
                view.on_frame(content, md)
                view.view.viewport().repaint()
                samples["pic_gui"].append(_ms(t0))
            med = {key: round(statistics.median(values), 2) for key, values in samples.items()}
            raw_kb = size * size * 2 / 1e3
            row = {
                "size": f"{size}x{size}",
                "encoding": encoding,
                "wire KB": med["wire"],
                "vs raw": round(raw_kb / med["wire"], 1),
                "device make+encode ms": med["make"],
                "deserialise ms": med["deser"],
                "Image: decode ms (receiver)": med["dec_img"],
                "Image: GUI ms": med["img_gui"],
                "Picture: decode ms (receiver)": med["dec_pic"],
                "Picture: GUI ms": med["pic_gui"],
            }
            rows.append(row)
            print(row, flush=True)

    header = list(rows[0])
    lines = ["| " + " | ".join(header) + " |", "|" + " --- |" * len(header)]
    lines += ["| " + " | ".join(str(row[key]) for key in header) + " |" for row in rows]
    print("\n" + "\n".join(lines))
    out = os.environ.get("BENCH_OUT")
    if out:
        Path(out).write_text(json.dumps(rows, indent=1))
    camera.destroy()
