import numpy as np
import pyqtgraph as pg
import pytest
from qtpy.QtOpenGLWidgets import QOpenGLWidget
from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

from bec_widgets.utils import gpu_acceleration
from bec_widgets.utils.gpu_acceleration import (
    ENV_VAR,
    grab_widget,
    opengl_available,
    set_view_opengl,
)


@pytest.fixture(autouse=True)
def _reset_opengl_probe(monkeypatch):
    """Keep the cached context probe and pyqtgraph's global config out of other tests."""
    # hold on to the real cached function: monkeypatch may swap the module
    # attribute for a stub, and it is only restored after this fixture resumes
    probe = gpu_acceleration.opengl_info
    probe.cache_clear()
    monkeypatch.delenv(ENV_VAR, raising=False)
    previous = pg.getConfigOption("useOpenGL")
    yield
    pg.setConfigOption("useOpenGL", previous)
    probe.cache_clear()


def _fake_renderer(monkeypatch, renderer: str | None):
    info = None if renderer is None else {"vendor": "v", "renderer": renderer, "version": "4.1"}
    monkeypatch.setattr(gpu_acceleration, "opengl_info", lambda: info)


def test_opengl_available_requires_opt_in(monkeypatch):
    _fake_renderer(monkeypatch, "NVIDIA GeForce RTX 3090")
    assert opengl_available(requested=True) is True
    assert opengl_available(requested=False) is False


def test_opengl_refused_without_context(monkeypatch):
    _fake_renderer(monkeypatch, None)
    assert opengl_available(requested=True) is False


@pytest.mark.parametrize("renderer", ["llvmpipe (LLVM 15.0.7, 256 bits)", "softpipe", "SWRast"])
def test_opengl_refused_on_software_renderer(monkeypatch, renderer):
    """A remote/X-forwarded session must stay on the raster viewport."""
    _fake_renderer(monkeypatch, renderer)
    assert opengl_available(requested=True) is False


def test_env_var_forces_opengl_on_software_renderer(monkeypatch):
    _fake_renderer(monkeypatch, "llvmpipe (LLVM 15.0.7, 256 bits)")
    monkeypatch.setenv(ENV_VAR, "1")
    assert opengl_available(requested=True) is True
    # forcing on also overrides a widget that did not ask for it
    assert opengl_available(requested=False) is True


def test_env_var_disables_opengl(monkeypatch):
    _fake_renderer(monkeypatch, "NVIDIA GeForce RTX 3090")
    monkeypatch.setenv(ENV_VAR, "0")
    assert opengl_available(requested=True) is False


def test_unrecognised_env_var_falls_back_to_auto(monkeypatch):
    _fake_renderer(monkeypatch, "NVIDIA GeForce RTX 3090")
    monkeypatch.setenv(ENV_VAR, "maybe")
    assert opengl_available(requested=True) is True


def _curve_view(qtbot, use_opengl: bool):
    pg.setConfigOption("useOpenGL", use_opengl)
    view = pg.GraphicsLayoutWidget()
    plot = view.addPlot()
    x = np.arange(5_000, dtype=np.float64)
    plot.addItem(pg.PlotDataItem(x, np.sin(x * 0.01), pen=pg.mkPen("r", width=2)))
    view.resize(400, 300)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitExposed(view)
    return view


def test_set_view_opengl_toggles_viewport(qtbot):
    view = _curve_view(qtbot, use_opengl=False)
    if not gpu_acceleration.opengl_available(True):
        pytest.skip("no hardware OpenGL available in this environment")

    assert set_view_opengl(view, True) is True
    assert isinstance(view.viewport(), QOpenGLWidget)
    assert set_view_opengl(view, False) is False
    assert not isinstance(view.viewport(), QOpenGLWidget)


def test_set_view_opengl_is_idempotent(qtbot):
    view = _curve_view(qtbot, use_opengl=False)
    viewport = view.viewport()
    assert set_view_opengl(view, False) is False
    # no needless swap: the same viewport object is kept
    assert view.viewport() is viewport


def test_toggling_back_to_opengl_does_not_strand_gl_state(qtbot):
    """Swapping the viewport deletes the item's OpenGLState on the C++ side.

    Without clearing the stale reference, the next paintGL raises
    'Signal source has been deleted'. PlotCurveItem.paint swallows that, so the
    curve silently stops rendering instead of crashing.
    """
    view = _curve_view(qtbot, use_opengl=True)
    if not isinstance(view.viewport(), QOpenGLWidget):
        pytest.skip("no OpenGL viewport available in this environment")

    curve = next(i for i in view.scene().items() if isinstance(i, pg.PlotCurveItem))
    view.viewport().repaint()
    assert curve.glstate is not None, "expected the GL path to have been taken"

    set_view_opengl(view, False)
    assert curve.glstate is None, "stale OpenGLState was not released on swap"

    set_view_opengl(view, True)
    view.viewport().repaint()
    # rebuilt against the new context rather than reusing the deleted object
    assert curve.glstate is not None


def _non_background_fraction(pixmap) -> float:
    """Fraction of pixels differing from the most common colour."""
    image = pixmap.toImage()
    buffer = np.frombuffer(image.constBits(), dtype=np.uint8)
    arr = buffer.reshape(image.height(), image.bytesPerLine() // 4, 4)
    flat = arr[:, : image.width(), :3].reshape(-1, 3)
    colours, counts = np.unique(flat, axis=0, return_counts=True)
    return float(np.any(flat != colours[counts.argmax()], axis=1).mean())


def _plot_host(qtbot, use_opengl: bool):
    pg.setConfigOption("useOpenGL", use_opengl)
    host = QWidget()
    layout = QVBoxLayout(host)
    layout.addWidget(QLabel("scan 42"))
    view = pg.GraphicsLayoutWidget()
    layout.addWidget(view)
    plot = view.addPlot()
    x = np.arange(5_000, dtype=np.float64)
    plot.addItem(pg.PlotDataItem(x, np.sin(x * 0.01), pen=pg.mkPen("r", width=2)))
    plot.enableAutoRange(False)
    plot.setXRange(0, 5_000)
    plot.setYRange(-1.5, 1.5)
    host.resize(640, 460)
    qtbot.addWidget(host)
    host.show()
    qtbot.waitExposed(host)
    return host, view


def test_grab_widget_matches_plain_grab_without_opengl(qtbot):
    host, view = _plot_host(qtbot, use_opengl=False)
    assert not isinstance(view.viewport(), QOpenGLWidget)
    assert _non_background_fraction(grab_widget(host)) == pytest.approx(
        _non_background_fraction(host.grab())
    )


def test_grab_widget_recovers_plot_on_opengl_viewport(qtbot):
    """QWidget.grab() alone returns a blank plot area over an OpenGL viewport."""
    host, view = _plot_host(qtbot, use_opengl=True)
    if not isinstance(view.viewport(), QOpenGLWidget):
        pytest.skip("no OpenGL viewport available in this environment")

    plain = _non_background_fraction(host.grab())
    composited = _non_background_fraction(grab_widget(host))
    assert composited > plain
    # the plot fills most of the host, so a correct capture is far from empty
    assert composited > 0.05
