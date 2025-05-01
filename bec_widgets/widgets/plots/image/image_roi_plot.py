import pyqtgraph as pg

from bec_widgets.utils.round_frame import RoundedFrame
from bec_widgets.widgets.plots.plot_base import BECViewBox


class ImageROIPlot(RoundedFrame):
    """
    A widget for displaying an image with a region of interest (ROI) overlay.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.content_widget = pg.GraphicsLayoutWidget(self)
        self.layout.addWidget(self.content_widget)
        self.plot_item = pg.PlotItem(viewBox=BECViewBox(enableMenu=True))
        self.content_widget.addItem(self.plot_item)
        self.curve_color = "w"

        self.apply_plot_widget_style()

    def apply_theme(self, theme: str):
        if theme == "dark":
            self.curve_color = "w"
        else:
            self.curve_color = "k"
        for curve in self.plot_item.curves:
            curve.setPen(pg.mkPen(self.curve_color, width=3))
        super().apply_theme(theme)

    def cleanup_pyqtgraph(self):
        """Cleanup pyqtgraph items."""
        self.plot_item.vb.menu.close()
        self.plot_item.vb.menu.deleteLater()
        self.plot_item.ctrlMenu.close()
        self.plot_item.ctrlMenu.deleteLater()
