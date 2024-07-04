from qtpy.QtCore import Qt, Slot
from qtpy.QtGui import QPainter, QPen
from qtpy.QtWidgets import QWidget


class PositionIndicator(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.position = 0.5
        self.min_value = 0
        self.max_value = 100
        self.scaling_factor = 0.5
        self.setMinimumHeight(10)

    def set_range(self, min_value, max_value):
        self.min_value = min_value
        self.max_value = max_value

    @Slot(float)
    def on_position_update(self, position: float):
        self.position = position
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()

        # Draw horizontal line
        painter.setPen(Qt.black)
        painter.drawLine(0, height // 2, width, height // 2)

        # Draw shorter vertical line at the current position
        x_pos = int(self.position * width)
        painter.setPen(QPen(Qt.red, 2))
        short_line_height = int(height * self.scaling_factor)
        painter.drawLine(
            x_pos,
            (height // 2) - (short_line_height // 2),
            x_pos,
            (height // 2) + (short_line_height // 2),
        )

        # Draw thicker vertical lines at the ends
        end_line_pen = QPen(Qt.blue, 5)
        painter.setPen(end_line_pen)
        painter.drawLine(0, 0, 0, height)
        painter.drawLine(width - 1, 0, width - 1, height)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication, QSlider, QVBoxLayout

    app = QApplication([])

    position_indicator = PositionIndicator()
    slider = QSlider(Qt.Horizontal)
    slider.valueChanged.connect(lambda value: position_indicator.on_position_update(value / 100))

    layout = QVBoxLayout()
    layout.addWidget(position_indicator)
    layout.addWidget(slider)

    widget = QWidget()
    widget.setLayout(layout)
    widget.show()

    app.exec_()
