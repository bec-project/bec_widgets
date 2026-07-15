import sys
from enum import Enum
from string import Template

from qtpy.QtCore import QTimer
from qtpy.QtGui import QPalette
from qtpy.QtWidgets import QApplication, QProgressBar, QSizePolicy, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot


class ProgressState(Enum):
    NORMAL = "normal"
    PAUSED = "paused"
    WARNING = "warning"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"


class BECProgressBar(BECWidget, QWidget):
    """
    A BEC progress bar backed by Qt's native QProgressBar.

    The displayed text can be customized using a template with $value, $maximum,
    and $percentage placeholders.

    Args:
        parent: Parent Qt widget.
        client: Optional BEC client instance.
        config: Optional widget configuration.
        gui_id: Optional GUI identifier used by the BEC widget infrastructure.
        enable_dynamic_stylesheet: If True, adjust the chunk border radius while the
            filled chunk is still too narrow for the target radius. This avoids Qt
            stylesheet over-rounding artifacts on small progress values. Once the
            target radius is usable, normal value updates no longer rebuild the
            stylesheet.
        **kwargs: Additional keyword arguments forwarded to BECWidget.
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

    def __init__(
        self,
        parent=None,
        client=None,
        config=None,
        gui_id=None,
        enable_dynamic_stylesheet: bool = True,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)

        accent_colors = get_accent_colors()

        # internal values
        self._oversampling_factor = 50
        self._value = 0
        self._maximum = 100 * self._oversampling_factor

        # User values
        self._user_value = 0
        self._user_minimum = 0
        self._user_maximum = 100
        self._label_template = "$value / $maximum - $percentage %"

        self._corner_radius = 8

        # Progress‑bar state handling
        self._state = ProgressState.NORMAL

        self._state_colors = {
            ProgressState.NORMAL: accent_colors.default,
            ProgressState.PAUSED: accent_colors.highlight,
            ProgressState.WARNING: accent_colors.warning,
            ProgressState.INTERRUPTED: accent_colors.emergency,
            ProgressState.COMPLETED: accent_colors.success,
        }

        # layout settings
        self._padding_left_right = 10
        self._chunk_radius = None
        self._enable_dynamic_stylesheet = enable_dynamic_stylesheet

        self.progressbar = QProgressBar(self)
        self.progressbar.setTextVisible(True)
        self.progressbar.setRange(0, self._maximum)
        self.progressbar.setMinimumHeight(0)
        self.progressbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(self._padding_left_right, 0, self._padding_left_right, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(self.progressbar)
        self.setLayout(self._layout)

        self._sync_progressbar()
        self._apply_state_style()

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

    def apply_theme(self, theme=None):
        """Apply the current theme to the progress bar."""
        accent_colors = get_accent_colors()
        self._state_colors = {
            ProgressState.NORMAL: accent_colors.default,
            ProgressState.PAUSED: accent_colors.highlight,
            ProgressState.WARNING: accent_colors.warning,
            ProgressState.INTERRUPTED: accent_colors.emergency,
            ProgressState.COMPLETED: accent_colors.success,
        }
        self._chunk_radius = None
        self._apply_state_style()

    @label_template.setter
    def label_template(self, template):
        self._label_template = template
        self._sync_progressbar()

    @SafeProperty(float, designable=False)
    def _progressbar_value(self):
        """
        The current value of the progress bar.
        """
        return self._value

    @_progressbar_value.setter
    def _progressbar_value(self, val):
        self._value = val
        self.progressbar.setValue(int(round(val)))

    def _update_template(self):
        template = Template(self._label_template)
        return template.safe_substitute(
            value=self._user_value,
            maximum=self._user_maximum,
            percentage=int(self._percentage(self._user_value)),
        )

    @SafeSlot(float)
    @SafeSlot(int)
    def set_value(self, value):
        """
        Set the value of the progress bar.

        Args:
            value (float): The value to set.
        """
        previous_visual_state = self._current_visual_state()
        previous_value = self._value
        self._user_value = self._clamp_value(value)
        self._value = self.map_value(self._user_value)
        if self._enable_dynamic_stylesheet and self._value < previous_value:
            self._chunk_radius = None
        # Update state automatically unless paused or interrupted
        if self._state not in (
            ProgressState.PAUSED,
            ProgressState.WARNING,
            ProgressState.INTERRUPTED,
        ):
            self._state = (
                ProgressState.COMPLETED
                if self._user_value >= self._user_maximum
                else ProgressState.NORMAL
            )
        self._sync_progressbar()
        visual_state_changed = self._current_visual_state() is not previous_visual_state
        if visual_state_changed:
            self._chunk_radius = None
        if (
            self._enable_dynamic_stylesheet
            and not visual_state_changed
            and (self._chunk_radius is None or self._chunk_radius != self._target_chunk_radius())
        ):
            self._update_chunk_radius()
        if visual_state_changed:
            self._apply_state_style()

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
        self._chunk_radius = None
        self._apply_state_style()

    @SafeProperty(float, doc="Base corner radius in pixels (auto‑scaled down on small bars).")
    def corner_radius(self) -> float:
        return self._corner_radius

    @corner_radius.setter
    def corner_radius(self, radius: float):
        self._corner_radius = max(0.0, radius)
        self._chunk_radius = None
        self._apply_state_style()

    @SafeProperty(bool)
    def enable_dynamic_stylesheet(self) -> bool:
        return self._enable_dynamic_stylesheet

    @enable_dynamic_stylesheet.setter
    def enable_dynamic_stylesheet(self, enabled: bool):
        self._enable_dynamic_stylesheet = bool(enabled)
        self._chunk_radius = None
        self._apply_state_style()

    @SafeProperty(float)
    def padding_left_right(self) -> float:
        return self._padding_left_right

    @padding_left_right.setter
    def padding_left_right(self, padding: float):
        self._padding_left_right = padding
        self._layout.setContentsMargins(int(round(padding)), 0, int(round(padding)), 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._chunk_radius = None
        self._update_chunk_radius()

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
        previous_maximum = self._user_maximum
        self._user_maximum = maximum
        if self._enable_dynamic_stylesheet and maximum != previous_maximum:
            self._chunk_radius = None
        self.set_value(self._user_value)  # Update the value to fit the new range

    @SafeSlot(float)
    def set_minimum(self, minimum: float):
        """
        Set the minimum value of the progress bar.

        Args:
            minimum (float): The minimum value.
        """
        previous_minimum = self._user_minimum
        self._user_minimum = minimum
        if self._enable_dynamic_stylesheet and minimum != previous_minimum:
            self._chunk_radius = None
        self.set_value(self._user_value)  # Update the value to fit the new range

    def map_value(self, value: float):
        """
        Map the user value to the range [0, 100*self._oversampling_factor] for the progress
        """
        span = self._user_maximum - self._user_minimum
        if span <= 0:
            return float(self._maximum if value >= self._user_maximum else 0)
        mapped_value = (value - self._user_minimum) / span * self._maximum
        return min(float(self._maximum), max(0.0, mapped_value))

    def _percentage(self, value: float) -> float:
        return (self.map_value(value) / self._maximum) * 100 if self._maximum else 0.0

    def _clamp_value(self, value: float) -> float:
        if self._user_maximum <= self._user_minimum:
            return self._user_maximum
        return min(self._user_maximum, max(self._user_minimum, value))

    def _sync_progressbar(self) -> None:
        self.progressbar.setRange(0, int(self._maximum))
        self.progressbar.setValue(int(round(self._value)))
        self.progressbar.setFormat(self._update_template())

    def _setup_style_sheet(self, *, chunk_radius: int) -> None:
        radius = int(round(self._corner_radius))
        chunk_color = self._state_colors[self._current_visual_state()].name()
        self.progressbar.setStyleSheet(f"""
            QProgressBar {{
                background-color: palette(mid);
                border: none;
                border-radius: {radius}px;
                color: palette(text);
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {chunk_color};
                border-radius: {chunk_radius}px;
            }}
            """)

    def _update_chunk_radius(self) -> None:
        chunk_radius = self._current_chunk_radius()
        if chunk_radius != self._chunk_radius:
            self._chunk_radius = chunk_radius
            self._setup_style_sheet(chunk_radius=chunk_radius)
            self._apply_state_palette()

    def _apply_state_style(self) -> None:
        if self._chunk_radius is None:
            self._chunk_radius = self._current_chunk_radius()
        self._setup_style_sheet(chunk_radius=self._chunk_radius)
        self._apply_state_palette()

    def _apply_state_palette(self) -> None:
        color = self._state_colors[self._current_visual_state()]
        palette = self.progressbar.palette()
        palette.setColor(QPalette.ColorRole.Highlight, color)
        palette.setColor(QPalette.ColorRole.HighlightedText, palette.color(QPalette.ColorRole.Text))
        self.progressbar.setPalette(palette)

    def _current_chunk_radius(self) -> int:
        target_radius = self._target_chunk_radius()
        if not self._enable_dynamic_stylesheet:
            return target_radius
        return self._calculate_chunk_radius(target_radius)

    def _target_chunk_radius(self) -> int:
        radius = int(round(self._corner_radius))
        return max(0, radius - 1)

    def _calculate_chunk_radius(self, target_radius: int) -> int:
        """
        Scale the chunk radius down while the filled part is narrower than the target radius.
        Qt stylesheets otherwise over-round very small chunks.
        """
        if target_radius <= 0 or self._maximum <= 0:
            return 0
        fill_width = self.progressbar.width() * min(1.0, max(0.0, self._value / self._maximum))
        if fill_width <= 0:
            return 0
        return min(target_radius, max(1, int(fill_width / 2)))

    def _current_visual_state(self) -> ProgressState:
        if self._state in (ProgressState.PAUSED, ProgressState.WARNING, ProgressState.INTERRUPTED):
            return self._state
        if self._state == ProgressState.COMPLETED or self._value >= self._maximum:
            return ProgressState.COMPLETED
        return ProgressState.NORMAL

    def _get_label(self) -> str:
        """Return the label text. mostly used for testing rpc."""
        return self.progressbar.text()


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)

    progress_bar = BECProgressBar()
    progress_bar.setWindowTitle("BEC Progress Bar")
    progress_bar.resize(360, 48)
    progress_bar.set_minimum(-100)
    progress_bar.set_maximum(0)
    progress_bar.set_value(-100)
    progress_bar.show()

    # Example of setting values
    def update_progress():
        value = progress_bar._user_value + 2.5
        if value > progress_bar._user_maximum:
            value = progress_bar._user_minimum
        progress_bar.set_value(value)

    timer = QTimer(progress_bar)
    timer.timeout.connect(update_progress)
    timer.start(200)

    sys.exit(app.exec())
