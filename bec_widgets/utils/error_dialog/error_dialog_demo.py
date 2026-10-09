"""Interactive demo of the error dialog: raises realistic errors through ``SafeSlot``.

Run with ``python -m bec_widgets.utils.error_dialog.error_dialog_demo [qwidget|qml|legacy]``.
The errors go through the real ``SafeSlot(popup_error=True)`` path, so the dialog shows exactly
what a user would see.
"""

from __future__ import annotations

import json
import os
import sys

from pydantic import BaseModel, Field
from qtpy.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.error_popups import SafeSlot


class LimitError(ValueError):
    """Raised when a move target is outside the soft limits (demo stand-in)."""


class GridScanArgs(BaseModel):
    """Arguments of a grid scan (demo stand-in for the scan control form)."""

    motor_1: str
    start_1: float
    stop_1: float
    steps_1: int = Field(gt=1)
    motor_2: str
    steps_2: int = Field(gt=1)
    exp_time: float = Field(gt=0)


def check_limits(device: str, target: float, limits: tuple[float, float]) -> None:
    """Raise :class:`LimitError` if ``target`` is outside ``limits``."""
    low, high = limits
    if not low <= target <= high:
        raise LimitError(
            f"Target {target} is outside the soft limits [{low:g}, {high:g}] of {device}."
        )


def load_profile(text: str) -> dict:
    """Parse a saved dock profile."""
    return json.loads(text)


class ErrorDemo(QWidget):
    """Buttons that raise the kinds of errors BEC widgets report."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves = {"bpm3i": object()}
        layout = QVBoxLayout(self)
        for label, slot in (
            ("Move outside limits", self.on_setpoint_change),
            ("Invalid scan arguments", self.on_scan_clicked),
            ("Missing curve (chained)", self.on_curve_update),
            ("Broken profile ×7", self.burst),
            ("Toggle theme", self.toggle_theme),
        ):
            button = QPushButton(label, self)
            button.clicked.connect(slot)
            layout.addWidget(button)

    @SafeSlot(popup_error=True)
    def on_setpoint_change(self):
        """Move samx to an out-of-range setpoint."""
        self.move_device("samx", 12.5)

    def move_device(self, name: str, target: float) -> None:
        """Check the limits, then move."""
        check_limits(name, target, (-10, 10))

    @SafeSlot(popup_error=True)
    def on_scan_clicked(self):
        """Validate the grid scan form."""
        args = self.collect_scan_args()
        return GridScanArgs(**args)

    def collect_scan_args(self) -> dict:
        """Values as typed in the form."""
        return {
            "motor_1": "samx",
            "start_1": -5,
            "stop_1": "5 mm",
            "steps_1": 1,
            "motor_2": "samy",
            "steps_2": 21,
            "exp_time": 0,
        }

    @SafeSlot(popup_error=True)
    def on_curve_update(self):
        """Update a curve that was removed from the plot."""
        try:
            curve = self._curves["bpm4i"]
        except KeyError:
            # no "from": shows the "while handling" chain in the dialog
            message = "Curve 'bpm4i' is not on this waveform; was it removed?"
            raise RuntimeError(message)  # pylint: disable=raise-missing-from
        return curve

    @SafeSlot(popup_error=True)
    def on_profile_loaded(self):
        """Restore a dock profile from a truncated file."""
        return load_profile('{"docks": [{"name": "waveform", "geometry": [0, 0, 640')

    def burst(self):
        """Seven identical errors in a row, as a broken timer would produce."""
        for _ in range(7):
            self.on_profile_loaded()

    def toggle_theme(self):
        """Switch between light and dark."""
        theme = QApplication.instance().theme
        apply_theme("light" if theme.theme == "dark" else "dark")


if __name__ == "__main__":  # pragma: no cover
    ui = sys.argv[1] if len(sys.argv) > 1 else "qwidget"
    if ui != "legacy":
        os.environ["BEC_ERROR_DIALOG"] = ui
    app = QApplication(sys.argv)
    apply_theme("dark")
    demo = ErrorDemo()
    demo.setWindowTitle(f"Error dialog demo ({ui})")
    demo.show()
    sys.exit(app.exec_())
