"""Benchmark the pyqtgraph 0.14 OpenGL viewport against the raster path.

Measures *render* cost only: the curve data is generated up front and cycled
frame to frame, so numpy work does not pollute the timing. vsync is disabled
via the swap interval so the OpenGL path is not pinned to the display refresh.

    python gpu_bench.py [n_points] [n_curves]
"""

import sys
import time

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore, QtGui, QtWidgets

N_POINTS = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
N_CURVES = int(sys.argv[2]) if len(sys.argv) > 2 else 3
FRAMES = 60
N_PRESET = 10


def _bench(use_opengl: bool, label: str, datasets, x) -> float:
    pg.setConfigOption("useOpenGL", use_opengl)
    pg.setConfigOption("enableExperimental", use_opengl)

    win = pg.GraphicsLayoutWidget()
    win.resize(1200, 800)
    plot = win.addPlot()
    curves = []
    for c in range(N_CURVES):
        curve = pg.PlotDataItem(pen=pg.mkPen(pg.intColor(c), width=1))
        plot.addItem(curve)
        curves.append(curve)
    plot.enableAutoRange(False)
    plot.setXRange(0, N_POINTS)
    plot.setYRange(-2, 2)
    win.show()

    deadline = time.perf_counter() + 1.0
    while time.perf_counter() < deadline:
        QtWidgets.QApplication.processEvents()

    viewport = win.viewport().__class__.__name__
    start = time.perf_counter()
    for i in range(FRAMES):
        for c, curve in enumerate(curves):
            curve.setData(x, datasets[(i + c) % N_PRESET])
        win.viewport().repaint()
        QtWidgets.QApplication.processEvents()
    elapsed = time.perf_counter() - start

    win.close()
    fps = FRAMES / elapsed
    print(f"  {label:<26} viewport={viewport:<22} {fps:7.1f} fps  ({1000 / fps:6.1f} ms/frame)")
    return fps


if __name__ == "__main__":
    # disable vsync before the QApplication so QOpenGLWidget is not capped at ~60 Hz
    fmt = QtGui.QSurfaceFormat.defaultFormat()
    fmt.setSwapInterval(0)
    QtGui.QSurfaceFormat.setDefaultFormat(fmt)

    app = QtWidgets.QApplication(sys.argv)
    print(f"pyqtgraph {pg.__version__}  |  Qt {QtCore.qVersion()}  |  swapInterval=0")
    print(f"{N_CURVES} curves x {N_POINTS:,} points, {FRAMES} frames (data pre-generated)\n")

    x = np.arange(N_POINTS, dtype=np.float64)
    rng = np.random.default_rng(0)
    datasets = [np.sin(x * 0.001 + k) + rng.normal(0, 0.1, N_POINTS) for k in range(N_PRESET)]

    raster = _bench(False, "raster (QPainter)", datasets, x)
    opengl = _bench(True, "opengl (QOpenGLWidget)", datasets, x)
    print(f"  -> speedup {opengl / raster:.2f}x")
