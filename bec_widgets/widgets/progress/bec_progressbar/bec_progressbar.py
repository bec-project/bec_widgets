import sys
from enum import Enum
from string import Template

from qtpy.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer
from qtpy.QtGui import QColor, QPainter, QPainterPath


class ProgressState(Enum):
    NORMAL = "normal"
    PAUSED = "paused"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"

    @classmethod
    def from_bec_status(cls, status: str) -> "ProgressState":
        """
        Map a BEC status string (open, paused, aborted, halted, closed)
        to the corresponding ProgressState.
        Any unknown status falls back to NORMAL.
        """
        mapping = {
            "open": cls.NORMAL,
            "paused": cls.PAUSED,
            "aborted": cls.INTERRUPTED,
            "halted": cls.PAUSED,
            "closed": cls.COMPLETED,
        }
        return mapping.get(status.lower(), cls.NORMAL)


PROGRESS_STATE_COLORS = {
    ProgressState.NORMAL: QColor("#2979ff"),  # blue  – normal progress
    ProgressState.PAUSED: QColor("#ffca28"),  # orange/amber – paused
    ProgressState.INTERRUPTED: QColor("#ff5252"),  # red – interrupted
    ProgressState.COMPLETED: QColor("#00e676"),  # green – finished
}

from qtpy.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot


class BECProgressBar(BECWidget, QWidget):
    """
    A custom progress bar with smooth transitions. The displayed text can be customized using a template.
    """

    PLUGIN = True
    USER_ACCESS = [
        "set_value",
        "set_maximum",
        "set_minimum",
        "label_template",
        "label_template.setter",
        "state",
        "state.setter",
        "_get_label",
    ]
    ICON_NAME = "page_control"

    def __init__(self, parent=None, client=None, config=None, gui_id=None, **kwargs):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)

        accent_colors = get_accent_colors()

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
        # Corner‑rounding: base radius in pixels (auto‑reduced if bar is small)
        self._corner_radius = 10

        # Progress‑bar state handling
        self._state = ProgressState.NORMAL
        self._state_colors = dict(PROGRESS_STATE_COLORS)

        # layout settings
        self._padding_left_right = 10
        self._value_animation = QPropertyAnimation(self, b"_progressbar_value")
        self._value_animation.setDuration(200)
        self._value_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # label on top of the progress bar
        self.center_label = QLabel(self)
        self.center_label.setAlignment(Qt.AlignHCenter)
        self.center_label.setStyleSheet("color: white;")
        self.center_label.setMinimumSize(0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)
        layout.addWidget(self.center_label)
        layout.setAlignment(self.center_label, Qt.AlignCenter)
        self.setLayout(layout)

        self.update()
        self._adjust_label_width()

    @SafeProperty(
        str, doc="The template for the center label. Use $value, $maximum, and $percentage."
    )
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
        self._adjust_label_width()
        self.set_value(self._user_value)
        self.update()

    @SafeProperty(float, designable=False)
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

    def _adjust_label_width(self):
        """
        Reserve enough horizontal space for the center label so the widget
        doesn't resize as the text grows during progress.
        """
        template = Template(self._label_template)
        sample_text = template.safe_substitute(
            value=self._user_maximum, maximum=self._user_maximum, percentage=100
        )
        width = self.center_label.fontMetrics().horizontalAdvance(sample_text)
        self.center_label.setFixedWidth(width)

    @SafeSlot(float)
    @SafeSlot(int)
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
        # Update state automatically unless paused or interrupted
        if self._state not in (ProgressState.PAUSED, ProgressState.INTERRUPTED):
            self._state = (
                ProgressState.COMPLETED
                if self._user_value >= self._user_maximum
                else ProgressState.NORMAL
            )
        self.animate_progress()

    @SafeProperty(object, doc="Current visual state of the progress bar.")
    def state(self):
        return self._state

    @state.setter
    def state(self, state):
        """
        Set the visual state of the progress bar.

        Args:
            state(ProgressState | str): The state to set. Can be one of the
        """
        if isinstance(state, str):
            state = ProgressState(state.lower())
        if not isinstance(state, ProgressState):
            raise ValueError("state must be a ProgressState or its value")
        self._state = state
        self.update()

    @SafeProperty(float, doc="Base corner radius in pixels (auto‑scaled down on small bars).")
    def corner_radius(self) -> float:
        return self._corner_radius

    @corner_radius.setter
    def corner_radius(self, radius: float):
        self._corner_radius = max(0.0, radius)
        self.update()

    @SafeProperty(float)
    def padding_left_right(self) -> float:
        return self._padding_left_right

    @padding_left_right.setter
    def padding_left_right(self, padding: float):
        self._padding_left_right = padding
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(self._padding_left_right, 0, -self._padding_left_right, -1)

        # Corner radius adapts to widget height so it never exceeds half the bar’s thickness
        radius = min(self._corner_radius, rect.height() / 2)

        # Draw background
        painter.setBrush(self._background_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, radius, radius)  # Rounded corners

        # Draw border
        painter.setBrush(Qt.NoBrush)
        painter.setPen(self._border_color)
        painter.drawRoundedRect(rect, radius, radius)

        # Determine progress colour based on current state
        if self._state == ProgressState.PAUSED:
            current_color = self._state_colors[ProgressState.PAUSED]
        elif self._state == ProgressState.INTERRUPTED:
            current_color = self._state_colors[ProgressState.INTERRUPTED]
        elif self._state == ProgressState.COMPLETED or self._value >= self._maximum:
            current_color = self._state_colors[ProgressState.COMPLETED]
        else:
            current_color = self._state_colors[ProgressState.NORMAL]

        # Set clipping region to preserve the background's rounded corners
        progress_rect = rect.adjusted(
            0, 0, int(-rect.width() + (self._value / self._maximum) * rect.width()), 0
        )
        clip_path = QPainterPath()
        clip_path.addRoundedRect(
            QRectF(rect), radius, radius
        )  # Clip to the background's rounded corners
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

    @SafeProperty(float)
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

    @SafeProperty(float)
    def minimum(self):
        """
        The minimum value of the progress bar.
        """
        return self._user_minimum

    @minimum.setter
    def minimum(self, minimum: float):
        self.set_minimum(minimum)

    @SafeProperty(float)
    def initial_value(self):
        """
        The initial value of the progress bar.
        """
        return self._user_value

    @initial_value.setter
    def initial_value(self, value: float):
        self.set_value(value)

    @SafeSlot(float)
    def set_maximum(self, maximum: float):
        """
        Set the maximum value of the progress bar.

        Args:
            maximum (float): The maximum value.
        """
        self._user_maximum = maximum
        self._adjust_label_width()
        self.set_value(self._user_value)  # Update the value to fit the new range
        self.update()

    @SafeSlot(float)
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

    def _get_label(self) -> str:
        """Return the label text. mostly used for testing rpc."""
        return self.center_label.text()


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
