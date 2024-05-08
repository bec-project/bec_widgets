from qtpy import QtCore, QtGui
from qtpy.QtWidgets import QWidget

from bec_widgets.utils import BECConnector, Colors, ConnectionConfig


class SpiralProgressBar(BECConnector, QWidget):
    USER_ACCESS = [
        "set_number_of_bars",
        "set_value",
        "set_colors_from_map",
        "set_colors_directly",
        "set_line_widths",
    ]

    def __init__(
        self,
        parent=None,
        config: ConnectionConfig | None = None,
        client=None,
        gui_id: str | None = None,
        num_bars=3,
    ):
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = ConnectionConfig(**config, widget_class=self.__class__.__name__)
            self.config = config
        super().__init__(client=client, config=config, gui_id=gui_id)
        QWidget.__init__(self, parent=None)

        self.min_bars = 2
        self.max_values = 6
        self.num_bars = max(2, min(num_bars, 6))
        self.initialize_bars(self.num_bars)

    def initialize_bars(self, num_bars):
        self.values = [0] * num_bars
        self.min_values = [0] * num_bars
        self.max_values = [100] * num_bars
        self.start_positions = [90 * 16] * num_bars
        self.directions = [-1] * num_bars
        self.colors = [QtGui.QColor(0, 159, 227)] * num_bars
        self.lineWidths = [5] * num_bars
        self.backgroundColors = [QtGui.QColor(200, 200, 200, 50)] * num_bars
        self.gap = 10
        self.update()

    def set_number_of_bars(self, num_bars):
        num_bars = max(2, min(num_bars, 6))
        if num_bars != self.num_bars:
            self.num_bars = num_bars
            self.initialize_bars(num_bars)

    def set_value(self, values):
        if len(values) != self.num_bars:
            raise ValueError("Value length must match the number of progress bars.")
        self.values = [
            max(min_val, min(max_val, val))
            for val, min_val, max_val in zip(values, self.min_values, self.max_values)
        ]
        self.update()

    def set_colors_from_map(self, colormap, format="QColor"):
        self.colors = Colors.golden_angle_color(colormap, self.num_bars, format)
        self.update()

    def set_colors_directly(self, colors):
        if len(colors) != self.num_bars:
            raise ValueError("Colors length must match the number of progress bars.")
        self.colors = []
        for color in colors:
            if isinstance(color, QtGui.QColor):
                self.colors.append(color)
            elif isinstance(color, str):
                self.colors.append(QtGui.QColor(color))
            elif isinstance(color, tuple):
                self.colors.append(QtGui.QColor(*color))
        self.update()

    def set_line_widths(self, widths):
        if len(widths) != self.num_bars:
            raise ValueError("Widths length must match the number of progress bars.")
        self.lineWidths = widths
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        size = min(self.width(), self.height())
        rect = QtCore.QRect(0, 0, size, size)
        rect.adjust(
            max(self.lineWidths), max(self.lineWidths), -max(self.lineWidths), -max(self.lineWidths)
        )

        for i in range(self.num_bars):
            # Background arc
            painter.setPen(
                QtGui.QPen(self.backgroundColors[i], self.lineWidths[i], QtCore.Qt.SolidLine)
            )
            offset = self.gap * i
            adjusted_rect = QtCore.QRect(
                rect.left() + offset,
                rect.top() + offset,
                rect.width() - 2 * offset,
                rect.height() - 2 * offset,
            )
            painter.drawArc(adjusted_rect, self.start_positions[i], 360 * 16)

            # Foreground arc
            pen = QtGui.QPen(self.colors[i], self.lineWidths[i], QtCore.Qt.SolidLine)
            pen.setCapStyle(QtCore.Qt.RoundCap)
            painter.setPen(pen)
            angle = int(self.values[i] / 100 * 360 * 16 * self.directions[i])
            painter.drawArc(adjusted_rect, self.start_positions[i], angle)

    def sizeHint(self):
        return QtCore.QSize(200, 200)
