import sys
from string import Template

from qtpy.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, Slot
from qtpy.QtGui import QColor, QPainter, QPainterPath
from qtpy.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget


class BECProgressBar(BECWidget, QWidget):
    """
    A custom progress bar with smooth transitions. The displayed text can be customized using a template.
    """

    USER_ACCESS = [
        "set_value",
        "set_maximum",
        "set_minimum",
        "label_template",
        "label_template.setter",
    ]
    ICON_NAME = "page_control"

    def __init__(self, parent=None, client=None, config=None, gui_id=None):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QWidget.__init__(self, parent=parent)

        accent_colors = QApplication.instance().theme.accent_colors

        # internal values
        self._oversampling_factor = 50
        self._value = 0
        self._target_value = 0
        self._maximum = 100 * self._oversampling_factor

        # User values
        self._user_value = 0
        self._user_minimum = 0
        self._user_maximum = 100
        self._label_template = "$value / $maximum - $percentage %"

        # Color settings
        self._background_color = QColor(30, 30, 30)
        self._progress_color = accent_colors.highlight  # QColor(210, 55, 130)

        self._completed_color = accent_colors.success
        self._border_color = QColor(50, 50, 50)

        # layout settings
        self._value_animation = QPropertyAnimation(self, b"_progressbar_value")
        self._value_animation.setDuration(200)
        self._value_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # label on top of the progress bar
        self.center_label = QLabel(self)
        self.center_label.setAlignment(Qt.AlignCenter)
        self.center_label.setStyleSheet("color: white;")
        self.center_label.setMinimumSize(0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.center_label)
        self.setLayout(layout)

        self.update()

    @Property(str, doc="The template for the center label. Use $value, $maximum, and $percentage.")
    def label_template(self):
        """
        The template for the center label. Use $value, $maximum, and $percentage to insert the values.

        Examples:
        >>> progressbar.label_template = "$value / $maximum - $percentage %"
        >>> progressbar.label_template = "$value / $percentage %"

        """
        return self._label_template

    @label_template.setter
    def label_template(self, template):
        self._label_template = template
        self.set_value(self._user_value)
        self.update()

    @Property(float, designable=False)
    def _progressbar_value(self):
        """
        The current value of the progress bar.
        """
        return self._value

    @_progressbar_value.setter
    def _progressbar_value(self, val):
        self._value = val
        self.update()

    def _update_template(self):
        template = Template(self._label_template)
        return template.safe_substitute(
            value=self._user_value,
            maximum=self._user_maximum,
            percentage=int((self.map_value(self._user_value) / self._maximum) * 100),
        )

    @Slot(float)
    @Slot(int)
    def set_value(self, value):
        """
        Set the value of the progress bar.

        Args:
            value (float): The value to set.
        """
        if value > self._user_maximum:
            value = self._user_maximum
        elif value < self._user_minimum:
            value = self._user_minimum
        self._target_value = self.map_value(value)
        self._user_value = value
        self.center_label.setText(self._update_template())
        self.animate_progress()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(10, 0, -10, -1)

        # Draw background
        painter.setBrush(self._background_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 10, 10)  # Rounded corners

        # Draw border
        painter.setBrush(Qt.NoBrush)
        painter.setPen(self._border_color)
        painter.drawRoundedRect(rect, 10, 10)

        # Determine progress color based on completion
        if self._value >= self._maximum:
            current_color = self._completed_color
        else:
            current_color = self._progress_color

        # Set clipping region to preserve the background's rounded corners
        progress_rect = rect.adjusted(
            0, 0, int(-rect.width() + (self._value / self._maximum) * rect.width()), 0
        )
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(rect), 10, 10)  # Clip to the background's rounded corners
        painter.setClipPath(clip_path)

        # Draw progress bar
        painter.setBrush(current_color)
        painter.drawRect(progress_rect)  # Less rounded, no additional rounding

        painter.end()

    def animate_progress(self):
        """
        Animate the progress bar from the current value to the target value.
        """
        self._value_animation.stop()
        self._value_animation.setStartValue(self._value)
        self._value_animation.setEndValue(self._target_value)
        self._value_animation.start()

    @Property(float)
    def maximum(self):
        """
        The maximum value of the progress bar.
        """
        return self._user_maximum

    @maximum.setter
    def maximum(self, maximum: float):
        """
        Set the maximum value of the progress bar.
        """
        self.set_maximum(maximum)

    @Property(float)
    def minimum(self):
        """
        The minimum value of the progress bar.
        """
        return self._user_minimum

    @minimum.setter
    def minimum(self, minimum: float):
        self.set_minimum(minimum)

    @Property(float)
    def initial_value(self):
        """
        The initial value of the progress bar.
        """
        return self._user_value

    @initial_value.setter
    def initial_value(self, value: float):
        self.set_value(value)

    @Slot(float)
    def set_maximum(self, maximum: float):
        """
        Set the maximum value of the progress bar.

        Args:
            maximum (float): The maximum value.
        """
        self._user_maximum = maximum
        self.set_value(self._user_value)  # Update the value to fit the new range
        self.update()

    @Slot(float)
    def set_minimum(self, minimum: float):
        """
        Set the minimum value of the progress bar.

        Args:
            minimum (float): The minimum value.
        """
        self._user_minimum = minimum
        self.set_value(self._user_value)  # Update the value to fit the new range
        self.update()

    def map_value(self, value: float):
        """
        Map the user value to the range [0, 100*self._oversampling_factor] for the progress
        """
        return (
            (value - self._user_minimum) / (self._user_maximum - self._user_minimum) * self._maximum
        )


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)

    progressBar = BECProgressBar()
    progressBar.show()
    progressBar.set_minimum(-100)
    progressBar.set_maximum(0)

    # Example of setting values
    def update_progress():
        value = progressBar._user_value + 2.5
        if value > progressBar._user_maximum:
            value = -100  # progressBar._maximum / progressBar._upsampling_factor
        progressBar.set_value(value)

    timer = QTimer()
    timer.timeout.connect(update_progress)
    timer.start(200)  # Update every half second

    sys.exit(app.exec())
