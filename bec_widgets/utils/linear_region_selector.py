""" Module for a thin wrapper (LinearRegionWrapper) around the LinearRegionItem in pyqtgraph.
The class is mainly designed for usage with the BECWaveform and 1D plots. """

from __future__ import annotations

import pyqtgraph as pg
from qtpy.QtCore import QObject, Signal, Slot
from qtpy.QtGui import QColor


class LinearRegionWrapper(QObject):
    """Wrapper class for the LinearRegionItem in pyqtgraph for 1D plots (BECWaveform)

    Args:
        plot_item (pg.PlotItem): The plot item to add the region selector to.
        parent (QObject): The parent object.
        color (QColor): The color of the region selector.
        hover_color (QColor): The color of the region selector when the mouse is over it.
    """

    # Signal with the region tuble (start, end)
    region_changed = Signal(tuple)

    def __init__(
        self, plot_item: pg.PlotItem, color: QColor = None, hover_color: QColor = None, parent=None
    ):
        super().__init__(parent)
        self.is_log_x = None
        self._edge_width = 2
        self.plot_item = plot_item
        self.linear_region_selector = pg.LinearRegionItem()
        self.proxy = None
        self.change_roi_color((color, hover_color))
        self.plot_item.ctrl.logXCheck.checkStateChanged.connect(self.check_log)
        self.plot_item.ctrl.logYCheck.checkStateChanged.connect(self.check_log)

    # Slot for changing the color of the region selector (edge and fill)
    @Slot(tuple)
    def change_roi_color(self, colors: tuple[QColor | str | tuple, QColor | str | tuple]):
        """Change the color and hover color of the region selector.
        Hover color means the color when the mouse is over the region.

        Args:
            colors (tuple): Tuple with the color and hover color
        """
        color, hover_color = colors
        if color is not None:
            self.linear_region_selector.setBrush(pg.mkBrush(color))
        if hover_color is not None:
            self.linear_region_selector.setHoverBrush(pg.mkBrush(hover_color))

    @Slot()
    def add_region_selector(self):
        """Add the region selector to the plot item"""
        self.plot_item.addItem(self.linear_region_selector)
        # Use proxy to limit the update rate of the region change signal to 10Hz
        self.proxy = pg.SignalProxy(
            self.linear_region_selector.sigRegionChanged,
            rateLimit=10,
            slot=self._region_change_proxy,
        )

    @Slot()
    def remove_region_selector(self):
        """Remove the region selector from the plot item"""
        self.proxy.disconnect()
        self.proxy = None
        self.plot_item.removeItem(self.linear_region_selector)

    def _region_change_proxy(self):
        """Emit the region change signal. If the plot is in log mode, convert the region to log."""
        x_low, x_high = self.linear_region_selector.getRegion()
        if self.is_log_x:
            x_low = 10**x_low
            x_high = 10**x_high
        self.region_changed.emit((x_low, x_high))

    @Slot()
    def check_log(self):
        """Check if the plot is in log mode."""
        self.is_log_x = self.plot_item.ctrl.logXCheck.isChecked()
        self.is_log_y = self.plot_item.ctrl.logYCheck.isChecked()

    def cleanup(self):
        """Cleanup the widget."""
        self.remove_region_selector()
