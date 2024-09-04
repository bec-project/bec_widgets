import sys

from qtpy.QtCore import Property, QEasingCurve, QPointF, QPropertyAnimation, Qt, Signal
from qtpy.QtGui import QColor, QPainter
from qtpy.QtWidgets import QApplication, QWidget


class ToggleSwitch(QWidget):
    """
    A simple toggle.
    """

    enabled = Signal(bool)
    ICON_NAME = "toggle_on"

    def __init__(self, parent=None, checked=True):
        super().__init__(parent)
        self.setFixedSize(40, 21)

        self._thumb_pos = QPointF(3, 2)  # Use QPointF for the thumb position
        self._active_track_color = QColor(33, 150, 243)
        self._active_thumb_color = QColor(255, 255, 255)
        self._inactive_track_color = QColor(200, 200, 200)
        self._inactive_thumb_color = QColor(255, 255, 255)

        self._checked = checked
        self._track_color = self.inactive_track_color
        self._thumb_color = self.inactive_thumb_color

        self._animation = QPropertyAnimation(self, b"thumb_pos")
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.OutBack)
        self.setProperty("checked", checked)

    @Property(bool)
    def checked(self):
        """
        The checked state of the toggle switch.
        """
        return self._checked

    @checked.setter
    def checked(self, state):
        self._checked = state
        self.update_colors()
        self.set_thumb_pos_to_state()
        self.enabled.emit(self._checked)

    @Property(QPointF)
    def thumb_pos(self):
        return self._thumb_pos

    @thumb_pos.setter
    def thumb_pos(self, pos):
        self._thumb_pos = pos
        self.update()

    @Property(QColor)
    def active_track_color(self):
        return self._active_track_color

    @active_track_color.setter
    def active_track_color(self, color):
        self._active_track_color = color
        self.update_colors()
        self.update()

    @Property(QColor)
    def active_thumb_color(self):
        return self._active_thumb_color

    @active_thumb_color.setter
    def active_thumb_color(self, color):
        self._active_thumb_color = color
        self.update_colors()
        self.update()

    @Property(QColor)
    def inactive_track_color(self):
        return self._inactive_track_color

    @inactive_track_color.setter
    def inactive_track_color(self, color):
        self._inactive_track_color = color
        self.update_colors()
        self.update()

    @Property(QColor)
    def inactive_thumb_color(self):
        return self._inactive_thumb_color

    @inactive_thumb_color.setter
    def inactive_thumb_color(self, color):
        self._inactive_thumb_color = color
        self.update_colors()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw track
        painter.setBrush(self._track_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(
            0, 0, self.width(), self.height(), self.height() / 2, self.height() / 2
        )

        # Draw thumb
        painter.setBrush(self._thumb_color)
        diameter = int(self.height() * 0.8)
        painter.drawEllipse(int(self._thumb_pos.x()), int(self._thumb_pos.y()), diameter, diameter)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.checked = not self.checked

    def update_colors(self):

        self._thumb_color = self.active_thumb_color if self._checked else self.inactive_thumb_color
        self._track_color = self.active_track_color if self._checked else self.inactive_track_color

    def get_thumb_pos(self, checked):
        return QPointF(self.width() - self.height() + 3, 2) if checked else QPointF(3, 2)

    def set_thumb_pos_to_state(self):
        # this is to avoid that linter complains about the thumb_pos setter
        self.setProperty("thumb_pos", self.get_thumb_pos(self._checked))
        self.update_colors()

    def animate_thumb(self):
        start_pos = self.thumb_pos
        end_pos = self.get_thumb_pos(self._checked)

        self._animation.stop()
        self._animation.setStartValue(start_pos)
        self._animation.setEndValue(end_pos)
        self._animation.start()

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        return self.size()


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)
    window = ToggleSwitch()
    window.show()
    sys.exit(app.exec())
