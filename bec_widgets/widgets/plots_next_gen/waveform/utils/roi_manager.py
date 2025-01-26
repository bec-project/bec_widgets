import pyqtgraph as pg
from qtpy.QtCore import QObject, Signal, Slot
from bec_widgets.utils.linear_region_selector import LinearRegionWrapper
from bec_widgets.utils.colors import get_accent_colors


class WaveformROIManager(QObject):
    """
    A reusable helper class that manages a single linear ROI region on a given plot item.
    It provides signals to notify about region changes and active state.
    """

    roi_changed = Signal(tuple)  # Emitted when the ROI (left, right) changes
    roi_active = Signal(bool)  # Emitted when ROI is enabled or disabled

    def __init__(self, plot_item: pg.PlotItem, parent=None):
        super().__init__(parent)
        self._plot_item = plot_item
        self._roi_wrapper: LinearRegionWrapper | None = None
        self._roi_region: tuple[float, float] | None = None
        self._accent_colors = get_accent_colors()

    @property
    def roi_region(self) -> tuple[float, float] | None:
        return self._roi_region

    @roi_region.setter
    def roi_region(self, value: tuple[float, float] | None):
        self._roi_region = value
        if self._roi_wrapper is not None and value is not None:
            self._roi_wrapper.linear_region_selector.setRegion(value)

    @Slot(bool)
    def toggle_roi(self, enabled: bool) -> None:
        if enabled:
            self._enable_roi()
        else:
            self._disable_roi()

    @Slot(tuple)
    def select_roi(self, region: tuple[float, float]):
        # If ROI not present, enabling it
        if self._roi_wrapper is None:
            self.toggle_roi(True)
        self.roi_region = region

    def _enable_roi(self):
        if self._roi_wrapper is not None:
            # Already enabled
            return
        color = self._accent_colors.default
        color.setAlpha(int(0.2 * 255))
        hover_color = self._accent_colors.default
        hover_color.setAlpha(int(0.35 * 255))

        self._roi_wrapper = LinearRegionWrapper(
            self._plot_item, color=color, hover_color=hover_color, parent=self
        )
        self._roi_wrapper.add_region_selector()
        self._roi_wrapper.region_changed.connect(self._on_region_changed)

        # If we already had a region, apply it
        if self._roi_region is not None:
            self._roi_wrapper.linear_region_selector.setRegion(self._roi_region)
        else:
            self._roi_region = self._roi_wrapper.linear_region_selector.getRegion()

        self.roi_active.emit(True)

    def _disable_roi(self):
        if self._roi_wrapper is not None:
            self._roi_wrapper.region_changed.disconnect(self._on_region_changed)
            self._roi_wrapper.cleanup()
            self._roi_wrapper.deleteLater()
            self._roi_wrapper = None

        self._roi_region = None
        self.roi_active.emit(False)

    @Slot(tuple)
    def _on_region_changed(self, region: tuple[float, float]):
        self._roi_region = region
        self.roi_changed.emit(region)
