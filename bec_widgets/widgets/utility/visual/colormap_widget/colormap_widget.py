from pyqtgraph.widgets.ColorMapButton import ColorMapButton
from qtpy.QtCore import Property, Signal, Slot
from qtpy.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from bec_widgets.utils import Colors
from bec_widgets.utils.bec_widget import BECWidget


class BECColorMapWidget(BECWidget, QWidget):
    colormap_changed_signal = Signal(str)
    ICON_NAME = "palette"
    PLUGIN = True
    RPC = False

    def __init__(self, parent=None, cmap: str = "magma", **kwargs):
        super().__init__(parent=parent, **kwargs)
        # Create the ColorMapButton
        self.button = ColorMapButton()

        # Set the size policy and minimum width
        size_policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.button.setSizePolicy(size_policy)
        self.button.setMinimumWidth(100)
        self.button.setMinimumHeight(30)

        # Create the layout
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.button)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Set the initial colormap
        self.button.setColorMap(cmap)
        self._cmap = cmap

        # Connect the signal
        self.button.sigColorMapChanged.connect(self.colormap_changed)

    @Property(str)
    def colormap(self):
        """Get the current colormap name."""
        return self._cmap

    @colormap.setter
    def colormap(self, name):
        """Set the colormap by name."""
        if self._cmap != name:
            if Colors.validate_color_map(name, return_error=False) is False:
                return
            self.button.setColorMap(name)
            self._cmap = name
            self.colormap_changed_signal.emit(name)

    @Slot()
    def colormap_changed(self):
        """
        Emit the colormap changed signal with the current colormap selected in the button.
        """
        cmap = self.button.colorMap().name
        self._cmap = cmap
        self.colormap_changed_signal.emit(cmap)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = BECColorMapWidget()
    window.show()
    sys.exit(app.exec())
