from __future__ import annotations

from qtpy.QtCore import Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QColorDialog, QPushButton

from bec_widgets import BECWidget, SafeProperty, SafeSlot


class ColorButtonNative(BECWidget, QPushButton):
    """A QPushButton subclass that displays a color.

    The background is set to the given color and the button text is the hex code.
    The text color is chosen automatically (black if the background is light, white if dark)
    to guarantee good readability.
    """

    color_changed = Signal(str)

    RPC = False
    PLUGIN = True
    ICON_NAME = "colors"

    def __init__(self, parent=None, color="#000000", **kwargs):
        """Initialize the color button.

        Args:
            parent: Optional QWidget parent.
            color (str): The initial color in hex format (e.g., '#000000').
        """
        super().__init__(parent=parent, **kwargs)
        self.set_color(color)
        self.clicked.connect(self._open_color_dialog)

    @SafeSlot()
    def set_color(self, color: str | QColor):
        """Set the button's color and update its appearance.

        Args:
            color (str or QColor): The new color to assign.
        """
        if isinstance(color, QColor):
            self._color = color.name()
        else:
            self._color = color
        self._update_appearance()
        self.color_changed.emit(self._color)

    @SafeProperty("QColor")
    def color(self):
        """Return the current color in hex."""
        return self._color

    @color.setter
    def color(self, value):
        """Set the button's color and update its appearance."""
        self.set_color(value)

    def _update_appearance(self):
        """Update the button style based on the background color's brightness."""
        c = QColor(self._color)
        brightness = c.lightnessF()
        text_color = "#000000" if brightness > 0.5 else "#FFFFFF"
        self.setStyleSheet(f"background-color: {self._color}; color: {text_color};")
        self.setText(self._color)

    @SafeSlot()
    def _open_color_dialog(self):
        """Open a QColorDialog and apply the selected color."""
        current_color = QColor(self._color)
        chosen_color = QColorDialog.getColor(current_color, self, "Select Curve Color")
        if chosen_color.isValid():
            self.set_color(chosen_color)
