import pyqtgraph as pg
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QFrame, QHBoxLayout

from bec_widgets.widgets.plots.plot_base import BECViewBox


class ImageROIPlot(QFrame):
    """
    A widget for displaying an image with a region of interest (ROI) overlay.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setProperty("skip_settings", True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.content_widget = pg.GraphicsLayoutWidget(self)
        self.layout.addWidget(self.content_widget)
        self.plot_item = pg.PlotItem(viewBox=BECViewBox(enableMenu=True))
        self.content_widget.addItem(self.plot_item)
        self.curve_color = "w"

    def apply_theme(self, theme: str):
        """
        Recolor the live profile curves for the given theme.

        Args:
            theme(str): "dark" or "light".
        """
        if theme == "dark":
            self.curve_color = "w"
        else:
            self.curve_color = "k"
        for curve in self.plot_item.curves:
            if getattr(curve, "is_pinned_reference", False):
                # Frozen reference profiles keep their own (dashed) styling.
                continue
            curve.setPen(pg.mkPen(self.curve_color, width=3))

    def cleanup_pyqtgraph(self):
        """Cleanup pyqtgraph items."""
        self.plot_item.vb.menu.close()
        self.plot_item.vb.menu.deleteLater()
        self.plot_item.ctrlMenu.close()
        self.plot_item.ctrlMenu.deleteLater()
