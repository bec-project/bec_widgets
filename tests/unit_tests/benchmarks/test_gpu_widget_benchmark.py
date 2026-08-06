"""End-to-end render benchmark for Waveform and Image, with and without OpenGL.

Drives each widget through the *real* data-entry point of whichever branch it is
run on, so the numbers include the widget-side data handling, not just pyqtgraph:

- ``data_api`` branch: a ``SubscriptionUpdate`` is handed to ``_on_data_update``,
  which includes the columnar alignment work.
- ``main``: ``update_sync_curves`` pulls a prepared scan-data dict (the fetch from
  the scan item is stubbed, since that needs a live BEC), and the image widget is
  fed through ``on_image_update_2d``.

The network/Redis hop is outside the measured region on both branches -- what is
compared is "a data snapshot is available -> pixels on screen".

Run explicitly (it is excluded from the CI suite by ``--ignore``)::

    QT_QPA_PLATFORM=offscreen pytest tests/unit_tests/benchmarks/test_gpu_widget_benchmark.py -s

Environment knobs: ``BENCH_FRAMES`` (default 40), ``BENCH_POINTS`` (default 50000),
``BENCH_IMAGE`` (image edge length, default 2048).
"""

import os
import time

import numpy as np
import pyqtgraph as pg
import pytest

from bec_widgets.utils.gpu_acceleration import opengl_available, set_view_opengl
from bec_widgets.widgets.plots.image.image import Image
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from tests.unit_tests.client_mocks import mocked_client
from tests.unit_tests.conftest import create_widget

try:
    from bec_lib.data_api.models import SourceData, SubscriptionUpdate

    HAS_DATA_API = True
except ImportError:  # main branch
    HAS_DATA_API = False

FRAMES = int(os.environ.get("BENCH_FRAMES", 40))
POINTS = int(os.environ.get("BENCH_POINTS", 50_000))
IMAGE_EDGE = int(os.environ.get("BENCH_IMAGE", 2048))
N_PRESET = 8
DEVICE, ENTRY = "bpm4i", "bpm4i"

_results: list[tuple[str, str, float | None]] = []
_data_path: dict[str, list[float]] = {}


def _make_update(values: np.ndarray, ordinals: tuple[int, ...], kind: str = "monitored"):
    """Build a single-source SubscriptionUpdate carrying `values`."""
    source = SourceData(
        device=DEVICE,
        entry=ENTRY,
        kind=kind,
        ordinals=ordinals,
        values=tuple(values),
        timestamps=tuple(float(o) for o in ordinals),
        complete=True,
    )
    return SubscriptionUpdate(
        scan_id="bench-scan",
        reason="live",
        sources={(DEVICE, ENTRY): source},
        aligned_ordinals=ordinals,
        complete=True,
    )


def _time_frames(widget, inject, count_paint_on, qtbot) -> float | None:
    """Run FRAMES inject-and-render cycles; None if the frames never rendered.

    Each frame waits for the item to actually paint before starting the next.
    ``repaint()`` is not usable here: on a QOpenGLWidget it defers, so a
    synchronous count sees zero. An unexposed window also makes painting a no-op
    for the raster viewport while OpenGL still renders, which would silently
    flatter raster -- hence the explicit per-frame confirmation.
    """
    paints = 0
    original = count_paint_on.paint

    def counting_paint(self, *args, **kwargs):
        nonlocal paints
        paints += 1
        return original(self, *args, **kwargs)

    count_paint_on.paint = counting_paint
    rendered = 0
    try:
        # The first paint after the window appears needs a generous stretch of
        # event loop; 1 ms slices never get there. Warm up until one lands, then
        # the per-frame polling below keeps up on its own.
        warmup_deadline = time.perf_counter() + 10.0
        while paints == 0 and time.perf_counter() < warmup_deadline:
            inject(0)
            widget.plot_widget.viewport().update()
            try:
                qtbot.waitUntil(lambda: paints > 0, timeout=1000)
            except Exception:
                pass
        if paints == 0:
            return None

        start = time.perf_counter()
        for i in range(FRAMES):
            before = paints
            inject(i)
            widget.plot_widget.viewport().update()
            # waitUntil spins pytest-qt's own event loop; hand-rolled
            # processEvents()/wait() polling does not deliver these paint events.
            try:
                qtbot.waitUntil(lambda: paints > before, timeout=5000)
                rendered += 1
            except Exception:
                pass
        elapsed = time.perf_counter() - start
    finally:
        count_paint_on.paint = original

    if rendered < FRAMES:
        print(
            f"    [diag] rendered={rendered}/{FRAMES} paints={paints} "
            f"viewport={type(widget.plot_widget.viewport()).__name__} "
            f"visible={widget.isVisible()} items={len(widget.plot_widget.scene().items())}"
        )
        return None
    return FRAMES / elapsed


def _time_data_path(inject, iterations: int) -> float:
    """Time the widget-side data handling alone, in ms per update.

    This is the part that differs between branches (DataAPI columnar alignment
    vs. the scan-item dict walk) and it needs no window, so unlike the render
    timing it is reliable regardless of whether the session composites.
    """
    inject(0)  # warm caches
    start = time.perf_counter()
    for i in range(iterations):
        inject(i)
    return (time.perf_counter() - start) * 1000 / iterations


def _report(label: str, mode: str, fps: float | None) -> None:
    _results.append((label, mode, fps))
    if fps is None:
        print(f"  {label:<26} {mode:<8} INVALID (frames did not render)")
    else:
        print(f"  {label:<26} {mode:<8} {fps:8.1f} fps  ({1000 / fps:7.2f} ms/frame)")


def _setup_waveform(qtbot, mocked_client, use_opengl: bool):
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    set_view_opengl(wf.plot_widget, use_opengl)
    wf.plot(arg1=DEVICE)
    wf.resize(1200, 800)
    wf.show()
    qtbot.waitExposed(wf)
    return wf


def _waveform_injector(wf, x, datasets):
    """Return a per-frame injector using this branch's real data path."""
    if HAS_DATA_API:
        ordinals = tuple(range(POINTS))
        updates = [_make_update(d, ordinals) for d in datasets]
        return lambda i: wf._on_data_update(updates[i % N_PRESET])

    # main: update_sync_curves() reads the scan data dict it fetches
    payloads = [{DEVICE: {ENTRY: {"val": d}}} for d in datasets]
    state = {"i": 0}

    def fetch():
        return payloads[state["i"] % N_PRESET], "val"

    wf._fetch_scan_data_and_access = fetch
    wf._get_x_data = lambda *a, **k: x

    def inject(i):
        state["i"] = i
        wf.update_sync_curves()

    return inject


def _setup_image(qtbot, mocked_client, use_opengl: bool):
    img = create_widget(qtbot, Image, client=mocked_client)
    set_view_opengl(img.plot_widget, use_opengl)
    img.image(DEVICE, ENTRY)
    img.resize(1200, 800)
    img.show()
    qtbot.waitExposed(img)
    return img


def _image_injector(img, frames):
    if HAS_DATA_API:
        img._source_key = (DEVICE, ENTRY)
        img.subscriptions["main"].monitor_type = "2d"
        # a plain list keeps each frame a float32 ndarray; np.array([f], dtype=object)
        # yields an object-dtype array and the downstream isnan() blows up
        updates = [_make_update([f], (0,), kind="async") for f in frames]
        return lambda i: img._on_data_update(updates[i % N_PRESET])

    img.async_update = False
    return lambda i: img.on_image_update_2d({"data": frames[i % N_PRESET]}, {})


@pytest.mark.parametrize("use_opengl", [False, True], ids=["raster", "opengl"])
def test_waveform_render_benchmark(qtbot, mocked_client, use_opengl):
    if use_opengl and not opengl_available(True):
        pytest.skip("no hardware OpenGL available")

    rng = np.random.default_rng(0)
    x = np.arange(POINTS, dtype=np.float64)
    datasets = [np.sin(x * 0.001 + k) + rng.normal(0, 0.1, POINTS) for k in range(N_PRESET)]

    wf = _setup_waveform(qtbot, mocked_client, use_opengl)
    inject = _waveform_injector(wf, x, datasets)
    inject(0)  # warm up the curve/GL state before timing
    qtbot.wait(200)

    ms = _time_data_path(inject, FRAMES)
    fps = _time_frames(wf, inject, pg.PlotCurveItem, qtbot)
    _report(f"Waveform {POINTS:,}pts", "opengl" if use_opengl else "raster", fps)
    _data_path.setdefault(f"Waveform {POINTS:,}pts", []).append(ms)


@pytest.mark.parametrize("use_opengl", [False, True], ids=["raster", "opengl"])
def test_image_render_benchmark(qtbot, mocked_client, use_opengl):
    if use_opengl and not opengl_available(True):
        pytest.skip("no hardware OpenGL available")

    rng = np.random.default_rng(0)
    frames = [rng.normal(size=(IMAGE_EDGE, IMAGE_EDGE)).astype(np.float32) for _ in range(N_PRESET)]

    img = _setup_image(qtbot, mocked_client, use_opengl)
    inject = _image_injector(img, frames)
    inject(0)
    qtbot.wait(200)

    ms = _time_data_path(inject, FRAMES)
    fps = _time_frames(img, inject, pg.ImageItem, qtbot)
    _report(f"Image {IMAGE_EDGE}x{IMAGE_EDGE}", "opengl" if use_opengl else "raster", fps)
    _data_path.setdefault(f"Image {IMAGE_EDGE}x{IMAGE_EDGE}", []).append(ms)


def teardown_module(module):
    branch = "data_api" if HAS_DATA_API else "main"
    print(f"\n==== summary ({branch} data path, {FRAMES} frames) ====")
    by_label: dict[str, dict[str, float | None]] = {}
    for label, mode, fps in _results:
        by_label.setdefault(label, {})[mode] = fps
    for label, modes in by_label.items():
        raster, opengl = modes.get("raster"), modes.get("opengl")
        if raster and opengl:
            print(f"  {label:<26} render speedup {opengl / raster:5.2f}x")
        else:
            print(f"  {label:<26} render speedup n/a (a run did not render)")
    print(f"---- widget-side data path ({branch}) ----")
    for label, samples in _data_path.items():
        best = min(samples)
        print(f"  {label:<26} {best:8.3f} ms/update  (best of {len(samples)})")
