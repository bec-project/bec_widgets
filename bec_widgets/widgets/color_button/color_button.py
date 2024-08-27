from __future__ import annotations

from typing import Literal

import pyqtgraph as pg


class ColorButton(pg.ColorButton):
    """
    A ColorButton that opens a dialog to select a color. Inherits from pyqtgraph.ColorButton.
    Patches event loop of the ColorDialog, if opened in another QDialog.
    """

    ICON_NAME = "colors"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def selectColor(self):
        self.origColor = self.color()
        self.colorDialog.setCurrentColor(self.color())
        self.colorDialog.open()
        self.colorDialog.exec()

    def get_color(self, format: Literal["RGBA", "HEX"] = "RGBA") -> tuple | str:
        """
        Get the color of the button in the specified format.

        Args:
            format(Literal["RGBA", "HEX"]): The format of the returned color.

        Returns:
            tuple|str: The color in the specified format.
        """
        if format == "RGBA":
            return self.color().getRgb()
        if format == "HEX":
            return self.color().name()

    def cleanup(self):
        """
        Clean up the ColorButton.
        """
        self.colorDialog.close()
        self.colorDialog.deleteLater()
