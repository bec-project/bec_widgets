from __future__ import annotations

from typing import Literal

import pyqtgraph as pg
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QHBoxLayout, QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot


class ColorButton(QWidget):
    """
    A ColorButton that opens a dialog to select a color. Inherits from pyqtgraph.ColorButton.
    Patches event loop of the ColorDialog, if opened in another QDialog.
    """

    color_selected = Signal(str)

    ICON_NAME = "colors"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.button = pg.ColorButton()
        self.button.setFlat(True)
        self.button.clicked.connect(self.select_color)
        self.layout.addWidget(self.button)

    @SafeSlot()
    def select_color(self):
        self.origColor = self.button.color()
        self.button.colorDialog.setCurrentColor(self.button.color())
        self.button.colorDialog.open()
        self.button.colorDialog.exec()
        self.color_selected.emit(self.button.color().name())

    @SafeSlot(str)
    def set_color(self, color: tuple | str):
        """
        Set the color of the button.

        Args:
            color(tuple|str): The color to set.
        """
        self.button.setColor(color)

    def get_color(self, format: Literal["RGBA", "HEX"] = "RGBA") -> tuple | str:
        """
        Get the color of the button in the specified format.

        Args:
            format(Literal["RGBA", "HEX"]): The format of the returned color.

        Returns:
            tuple|str: The color in the specified format.
        """
        if format == "RGBA":
            return self.button.color().getRgb()
        if format == "HEX":
            return self.button.color().name()

    def cleanup(self):
        """
        Clean up the ColorButton.
        """
        self.button.colorDialog.close()
        self.button.colorDialog.deleteLater()
