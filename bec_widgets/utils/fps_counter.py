"""
This module provides a utility class for counting and reporting frames per second (FPS) in a PyQtGraph application.

Classes:
    FPSCounter: A class that monitors the paint events of a `ViewBox` to calculate and emit FPS values.

Usage:
    The `FPSCounter` class can be used to monitor the rendering performance of a `ViewBox` in a PyQtGraph application.
    It connects to the `ViewBox`'s paint event and calculates the FPS over a specified interval, emitting the FPS value
    at regular intervals.

Example:
    from qtpy import QtWidgets, QtCore
    import pyqtgraph as pg
    from fps_counter import FPSCounter

    app = pg.mkQApp("FPS Counter Example")
    win = pg.GraphicsLayoutWidget()
    win.show()

    vb = pg.ViewBox()
    plot_item = pg.PlotItem(viewBox=vb)
    win.addItem(plot_item)

    fps_counter = FPSCounter(vb)
    fps_counter.sigFpsUpdate.connect(lambda fps: print(f"FPS: {fps:.2f}"))

    sys.exit(app.exec_())
"""

from time import perf_counter

import pyqtgraph as pg
from qtpy import QtCore


class FPSCounter(QtCore.QObject):
    """
    A utility class for counting and reporting frames per second (FPS).

    This class connects to a `ViewBox`'s paint event to count the number of
    frames rendered and calculates the FPS over a specified interval. It emits
    a signal with the FPS value at regular intervals.

    Attributes:
        sigFpsUpdate (QtCore.Signal): Signal emitted with the FPS value.
        view_box (pg.ViewBox): The `ViewBox` instance to monitor.
    """

    sigFpsUpdate = QtCore.Signal(float)

    def __init__(self, view_box):
        super().__init__()
        self.view_box = view_box
        self.view_box.sigPaint.connect(self.increment_count)
        self.count = 0
        self.last_update = perf_counter()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.calculate_fps)
        self.timer.start(1000)

    def increment_count(self):
        """
        Increment the frame count when the `ViewBox` is painted.
        """
        self.count += 1

    def calculate_fps(self):
        """
        Calculate the frames per second (FPS) based on the number of frames
        """
        now = perf_counter()
        elapsed = now - self.last_update
        fps = self.count / elapsed if elapsed > 0 else 0.0
        self.last_update = now
        self.count = 0
        self.sigFpsUpdate.emit(fps)

    def cleanup(self):
        """
        Clean up the FPS counter by stopping the timer and disconnecting the signal.
        """
        self.timer.stop()
        self.timer.timeout.disconnect(self.calculate_fps)
