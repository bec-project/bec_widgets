import pyqtgraph as pg
from qtpy.QtCore import Property, Signal, Slot
from qtpy.QtGui import QColor, QFontMetrics, QImage
from qtpy.QtWidgets import QApplication, QComboBox, QStyledItemDelegate, QVBoxLayout, QWidget


class ColormapDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super(ColormapDelegate, self).__init__(parent)
        self.image_width = 25
        self.image_height = 10
        self.gap = 10

    def paint(self, painter, option, index):
        text = index.data()
        colormap = pg.colormap.get(text)
        colors = colormap.getLookupTable(start=0.0, stop=1.0, alpha=False)

        font_metrics = QFontMetrics(painter.font())
        text_width = font_metrics.width(text)
        text_height = font_metrics.height()

        total_height = max(text_height, self.image_height)

        image = QImage(self.image_width, self.image_height, QImage.Format_RGB32)
        for i in range(self.image_width):
            color = QColor(*colors[int(i * (len(colors) - 1) / (self.image_width - 1))])
            for j in range(self.image_height):
                image.setPixel(i, j, color.rgb())

        painter.drawImage(
            option.rect.x(), option.rect.y() + (total_height - self.image_height) // 2, image
        )
        painter.drawText(
            option.rect.x() + self.image_width + self.gap,
            option.rect.y() + (total_height - text_height) // 2 + font_metrics.ascent(),
            text,
        )


class ColormapSelector(QWidget):
    """
    Simple colormap combobox widget. By  default it loads all the available colormaps in pyqtgraph.
    """

    colormap_changed_signal = Signal(str)

    def __init__(self, parent=None, default_colormaps=None):
        super().__init__(parent)
        self._colormaps = []
        self.initUI(default_colormaps)

    def initUI(self, default_colormaps=None):
        self.layout = QVBoxLayout(self)
        self.combo = QComboBox()
        self.combo.setItemDelegate(ColormapDelegate())
        self.combo.currentTextChanged.connect(self.colormap_changed)
        self.available_colormaps = pg.colormap.listMaps()
        if default_colormaps is None:
            default_colormaps = self.available_colormaps
        self.add_color_maps(default_colormaps)
        self.layout.addWidget(self.combo)

    @Slot()
    def colormap_changed(self):
        """
        Emit the colormap changed signal with the current colormap selected in the combobox.
        """
        self.colormap_changed_signal.emit(self.combo.currentText())

    def add_color_maps(self, colormaps=None):
        """
        Add colormaps to the combobox.

        Args:
            colormaps(list): List of colormaps to add to the combobox. If None, all available colormaps are added.
        """
        self.combo.clear()
        if colormaps is not None:
            for name in colormaps:
                if name in self.available_colormaps:
                    self.combo.addItem(name)
        else:
            for name in self.available_colormaps:
                self.combo.addItem(name)
        self._colormaps = colormaps if colormaps is not None else self.available_colormaps

    @Property("QStringList")
    def colormaps(self):
        """
        Property to get and set the colormaps in the combobox.
        """
        return self._colormaps

    @colormaps.setter
    def colormaps(self, value):
        """
        Set the colormaps in the combobox.
        """
        if self._colormaps != value:
            self._colormaps = value
            self.add_color_maps(value)


if __name__ == "__main__":  # pragma: no cover
    import sys

    app = QApplication(sys.argv)
    ex = ColormapSelector()
    ex.show()
    sys.exit(app.exec_())
