import sys

import numpy as np
from qtpy.QtCore import QRect, Qt, QTimer
from qtpy.QtGui import QColor, QPainter, QPen
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget

from bec_widgets.utils.colors import get_theme_palette


def ease_in_out_sine(t):
    return 1 - np.sin(np.pi * t)


class SpinnerWidget(QWidget):
    ICON_NAME = "progress_activity"
    PLUGIN = True

    def __init__(self, parent=None):
        super().__init__(parent)

        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.time = 0
        self.duration = 50
        self.speed = 50
        self._started = False

    def start(self):
        if self._started:
            return
        self.timer.start(self.speed)
        self._started = True

    def stop(self):
        if not self._started:
            return
        self.timer.stop()
        self._started = False
        self.update()

    def rotate(self):
        self.time = (self.time + 1) % self.duration
        t = self.time / self.duration
        easing_value = ease_in_out_sine(t)
        self.angle -= (20 * easing_value) % 360 + 10
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        size = min(self.width(), self.height())
        rect = QRect(0, 0, size, size)

        background_color = QColor(200, 200, 200, 50)
        line_width = 5

        color_palette = get_theme_palette()

        color = QColor(color_palette.accent().color())

        rect.adjust(line_width, line_width, -line_width, -line_width)

        # Background arc
        painter.setPen(QPen(background_color, line_width, Qt.SolidLine))
        adjusted_rect = QRect(rect.left(), rect.top(), rect.width(), rect.height())
        painter.drawArc(adjusted_rect, 0, 360 * 16)

        if self._started:
            # Foreground arc
            pen = QPen(color, line_width, Qt.SolidLine)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            proportion = 1 / 4
            angle_span = int(proportion * 360 * 16)
            angle_span += angle_span * ease_in_out_sine(self.time / self.duration)
            painter.drawArc(adjusted_rect, int(self.angle * 16), int(angle_span))
        painter.end()

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)
    window = QMainWindow()
    widget = SpinnerWidget()
    widget.start()
    window.setCentralWidget(widget)
    window.show()
    sys.exit(app.exec())
