import os

from bec_lib.device import Positioner
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QSizePolicy

from bec_widgets.widgets.control.device_control.positioner_box import PositionerBox


class PositionerControlLine(PositionerBox):
    """A widget that controls a single device."""

    ui_file = "positioner_control_line.ui"
    dimensions = (60, 600)  # height, width

    PLUGIN = True
    ICON_NAME = "switch_left"

    def __init__(self, parent=None, device: Positioner | str | None = None, *args, **kwargs):
        """Initialize the DeviceControlLine.

        Args:
            parent: The parent widget.
            device (Positioner): The device to control.
        """
        self.current_path = os.path.dirname(__file__)
        self._indicator_switch_width = 0
        self._horizontal_indicator_width = 0
        self._vertical_indicator_width = 15
        self._indicator_thickness = 10
        self._indicator_is_horizontal = False
        self._line_height = self.dimensions[0]
        super().__init__(parent=parent, device=device, *args, **kwargs)
        self._configure_line_layout()
        self._update_indicator_orientation()

    def _configure_line_layout(self):
        device_box = self.ui.device_box
        indicator = self.ui.position_indicator

        self.main_layout.setAlignment(Qt.AlignmentFlag(0))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ui.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        device_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._line_height = max(
            self.dimensions[0],
            self.ui.minimumSizeHint().height(),
            self.ui.sizeHint().height(),
            device_box.minimumSizeHint().height(),
            device_box.sizeHint().height(),
        )
        device_box.setFixedHeight(self._line_height)
        device_box.setMinimumWidth(self.dimensions[1])
        device_box.setMaximumWidth(16777215)
        self.setFixedHeight(self._line_height)
        self.setMinimumWidth(self.dimensions[1])

        self.ui.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.ui.verticalLayout.setSpacing(0)
        self.ui.readback.setMaximumWidth(16777215)
        self.ui.setpoint.setMaximumWidth(16777215)
        self.ui.step_size.setMaximumWidth(16777215)

        indicator_hint = indicator.minimumSizeHint()
        step_hint = self.ui.step_size.sizeHint()
        self._indicator_thickness = max(indicator_hint.height(), 10)
        self._vertical_indicator_width = max(indicator.minimumWidth(), 15)
        self._horizontal_indicator_width = max(90, step_hint.width())
        base_width = max(device_box.minimumSizeHint().width(), self.dimensions[1])
        self._indicator_switch_width = (
            base_width - self._vertical_indicator_width + self._horizontal_indicator_width
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_indicator_orientation()

    def _update_indicator_orientation(self):
        if not hasattr(self, "ui"):
            return

        indicator = self.ui.position_indicator
        available_width = self.ui.device_box.width() or self.width() or self.dimensions[1]
        should_use_horizontal = available_width >= self._indicator_switch_width
        if should_use_horizontal == self._indicator_is_horizontal:
            return

        self._indicator_is_horizontal = should_use_horizontal
        indicator.vertical = not should_use_horizontal

        if should_use_horizontal:
            indicator.setMinimumSize(self._horizontal_indicator_width, self._indicator_thickness)
            indicator.setMaximumHeight(self._indicator_thickness)
            indicator.setMaximumWidth(16777215)
            indicator.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        else:
            indicator.setMinimumSize(self._vertical_indicator_width, self._indicator_thickness)
            indicator.setMaximumSize(self._vertical_indicator_width, 16777215)
            indicator.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        indicator.updateGeometry()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = PositionerControlLine(device="samy")

    widget.show()
    sys.exit(app.exec_())
