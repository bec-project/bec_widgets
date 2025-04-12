import numpy as np
from qtpy.QtCore import Property, QSize, Qt, Slot
from qtpy.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors, get_theme_palette


class PositionIndicator(BECWidget, QWidget):
    """
    Display a position within a defined range, e.g. motor limits.
    """

    USER_ACCESS = ["set_value", "set_range", "vertical", "indicator_width", "rounded_corners"]
    PLUGIN = True
    ICON_NAME = "horizontal_distribute"

    def __init__(self, parent=None, client=None, config=None, gui_id=None, **kwargs):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)

        self.position = 50
        self.min_value = 0
        self.max_value = 100
        self.scaling_factor = 0.5
        self.is_vertical = False
        self._current_indicator_position = 0
        self._draw_position = 0
        self._rounded_corners = 10
        self._indicator_width = 2
        self._indicator_color = get_accent_colors().success
        self._background_color = get_theme_palette().mid().color()
        self._use_color_palette = True

    def set_range(self, min_value: float, max_value: float):
        """
        Set the range of the position indicator

        Args:
            min_value(float): Minimum value of the range
            max_value(float): Maximum value of the range
        """
        self.minimum = min_value
        self.maximum = max_value

    @Property(float)
    def minimum(self):
        """
        Property to get the minimum value of the position indicator
        """
        return self.min_value

    @minimum.setter
    def minimum(self, min_value: float):
        """
        Setter for the minimum property

        Args:
            min_value: The minimum value of the position indicator
        """
        self.min_value = min_value
        self.update()

    @Property(float)
    def maximum(self):
        """
        Property to get the maximum value of the position indicator
        """
        return self.max_value

    @maximum.setter
    def maximum(self, max_value: float):
        """
        Setter for the maximum property

        Args:
            max_value: The maximum value of the position indicator
        """
        self.max_value = max_value
        self.update()

    @Property(bool)
    def vertical(self):
        """
        Property to determine the orientation of the position indicator
        """
        return self.is_vertical

    @vertical.setter
    def vertical(self, is_vertical: bool):
        """
        Setter for the vertical property

        Args:
            is_vertical: True if the indicator should be vertical, False if horizontal
        """

        self.is_vertical = is_vertical
        self.update()

    @Property(float)
    def value(self):
        """
        Property to get the current value of the position indicator
        """
        return self.position

    @value.setter
    def value(self, position: float):
        """
        Setter for the value property

        Args:
            position: The new position of the indicator
        """
        self.set_value(position)

    @Property(int)
    def indicator_width(self):
        """
        Property to get the width of the indicator
        """
        return self._indicator_width

    @indicator_width.setter
    def indicator_width(self, width: int):
        """
        Setter for the indicator width property

        Args:
            width: The new width of the indicator
        """
        self._indicator_width = width
        self.update()

    @Property(int)
    def rounded_corners(self):
        """
        Property to get the rounded corners of the position indicator
        """
        return self._rounded_corners

    @rounded_corners.setter
    def rounded_corners(self, value: int):
        """
        Setter for the rounded corners property

        Args:
            value: The new value for the rounded corners
        """
        self._rounded_corners = value
        self.update()

    @Property(QColor)
    def indicator_color(self):
        """
        Property to get the color of the indicator
        """
        return self._indicator_color

    @indicator_color.setter
    def indicator_color(self, color: QColor):
        """
        Setter for the indicator color property

        Args:
            color: The new color for the indicator
        """
        self._indicator_color = color
        self.update()

    @Property(QColor)
    def background_color(self):
        """
        Property to get the background color of the position indicator
        """
        return self._background_color

    @background_color.setter
    def background_color(self, color: QColor):
        """
        Setter for the background color property

        Args:
            color: The new background color
        """
        self._background_color = color
        self.update()

    @Property(bool)
    def use_color_palette(self):
        """
        Property to determine if the indicator should use the color palette or the custom color.
        """
        return self._use_color_palette

    @use_color_palette.setter
    def use_color_palette(self, use_palette: bool):
        """
        Setter for the use color palette property

        Args:
            use_palette: True if the indicator should use the color palette, False if custom color
        """
        self._use_color_palette = use_palette
        self.update()

    # @Property(float)
    @Slot(int)
    @Slot(float)
    def set_value(self, position: float):
        self.position = position
        self.update()

    def _get_indicator_color(self):
        if self._use_color_palette:
            return get_accent_colors().success
        return self._indicator_color

    def _get_background_brush(self):
        if self._use_color_palette:
            return get_theme_palette().mid()
        return QBrush(self._background_color)

    def paintEvent(self, event):
        painter = QPainter(self)
        width = self.width()
        height = self.height()

        # Set up the brush for the background
        painter.setBrush(self._get_background_brush())

        # Create a QPainterPath with a rounded rectangle for clipping
        path = QPainterPath()
        path.addRoundedRect(0, 0, width, height, self._rounded_corners, self._rounded_corners)

        # Set clipping to the rounded rectangle
        painter.setClipPath(path)

        # Draw the rounded rectangle background first
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, width, height, self._rounded_corners, self._rounded_corners)

        # get the position scaled to the defined min and max values
        self._current_indicator_position = position = np.interp(
            self.position, [self.min_value, self.max_value], [0, 100]
        )

        if self.is_vertical:
            # If vertical, rotate the coordinate system by -90 degrees
            painter.translate(width // 2, height // 2)  # Move origin to center
            painter.rotate(-90)  # Rotate by -90 degrees for vertical drawing
            painter.translate(-height // 2, -width // 2)  # Restore the origin for drawing

            # Switch width and height for the vertical orientation
            width, height = height, width

        # Draw the moving vertical indicator, respecting the clip path
        self._draw_position = x_pos = round(
            position * width / 100
        )  # Position for the vertical line

        indicator_pen = QPen(self._get_indicator_color(), self._indicator_width)
        painter.setPen(indicator_pen)
        painter.drawLine(x_pos, 0, x_pos, height)

        painter.end()

    def minimumSizeHint(self):
        # Set the smallest possible size
        return QSize(10, 10)


if __name__ == "__main__":  # pragma: no cover
    from bec_qthemes import setup_theme
    from qtpy.QtWidgets import QApplication, QSlider, QVBoxLayout

    app = QApplication([])
    setup_theme("dark")
    # Create position indicator and slider
    position_indicator = PositionIndicator()
    # position_indicator.set_range(0, 1)
    slider = QSlider(Qt.Horizontal)
    slider.valueChanged.connect(lambda value: position_indicator.set_value(value))
    position_indicator.is_vertical = False
    # position_indicator.set_value(100)
    layout = QVBoxLayout()
    layout.addWidget(position_indicator)
    layout.addWidget(slider)

    widget = QWidget()
    widget.setLayout(layout)
    widget.show()

    app.exec_()
