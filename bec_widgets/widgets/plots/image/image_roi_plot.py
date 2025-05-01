import pyqtgraph as pg
import numpy as np

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

        self.plot_item.plot([0, 1], [0, 1])  # Dummy plot to initialize the plot item
        self.apply_plot_widget_style()

    def set_data(self, data: np.ndarray):
        """
        Set the roi data to be displayed.
        """
