import pyqtgraph as pg


class ColorButton(pg.ColorButton):
    """
    A ColorButton that opens a dialog to select a color. Inherits from pyqtgraph.ColorButton.
    Patches event loop of the ColorDialog, if opened in another QDialog.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def selectColor(self):
        self.origColor = self.color()
        self.colorDialog.setCurrentColor(self.color())
        self.colorDialog.open()
        self.colorDialog.exec()
