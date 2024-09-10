"""Module to create an arrow item for a pyqtgraph plot"""

import pyqtgraph as pg
from qtpy.QtCore import QObject, Qt, Signal, Slot

from bec_widgets.utils.colors import get_accent_colors


class BECIndicatorItem(QObject):

    def __init__(self, plot_item: pg.PlotItem = None, parent=None):
        super().__init__(parent=parent)
        self.accent_colors = get_accent_colors()
        self.plot_item = plot_item

    def add_to_plot(self) -> None:
        """Add the item to the plot"""
        raise NotImplementedError("Method add_to_plot not implemented")

    def remove_from_plot(self) -> None:
        """Remove the item from the plot"""
        raise NotImplementedError("Method remove_from_plot not implemented")

    def set_position(self, pos: tuple[float, float] | float) -> None:
        """Set the position of the item"""
        raise NotImplementedError("Method set_position not implemented")

    def cleanup(self) -> None:
        """Cleanup the item"""
        self.remove_from_plot()
        self.deleteLater()


class BECTickItem(BECIndicatorItem):
    """Class to create a tick item which can be added to a pyqtgraph plot.
    The tick item will be added to the layout of the plot item and can be used to indicate
    a position"""

    position_changed = Signal(float)
    position_changed_str = Signal(str)

    def __init__(self, plot_item: pg.PlotItem = None, parent=None):
        super().__init__(plot_item=plot_item, parent=parent)
        self.tick_item = pg.TickSliderItem(allowAdd=False, allowRemove=False)
        self.tick = None
        self._tick_pos = 0
        self._range = [0, 1]

    @Slot(float)
    def set_position(self, pos: float) -> None:
        """Set the position of the tick item

        Args:
            pos (float): The position of the tick item.
        """
        self._tick_pos = pos
        self.update_range(self.plot_item.vb, self._range)

    def update_range(self, vb, viewRange) -> None:
        """Update the range of the tick item

        Args:
            vb (pg.ViewBox): The view box.
            viewRange (tuple): The view range.
        """
        origin = self.tick_item.tickSize / 2.0
        length = self.tick_item.length

        lengthIncludingPadding = length + self.tick_item.tickSize + 2

        self._range = viewRange

        tickValueIncludingPadding = (self._tick_pos - viewRange[0]) / (viewRange[1] - viewRange[0])
        tickValue = (tickValueIncludingPadding * lengthIncludingPadding - origin) / length
        self.tick_item.setTickValue(self.tick, tickValue)
        self.position_changed.emit(self._tick_pos)
        self.position_changed_str.emit(str(self._tick_pos))

    def add_to_plot(self):
        """Add the tick item to the view box or plot item."""
        if self.plot_item is not None:
            self.plot_item.layout.addItem(self.tick_item, 4, 1)
            self.tick = self.tick_item.addTick(0, movable=False, color=self.accent_colors.highlight)
            self.plot_item.vb.sigXRangeChanged.connect(self.update_range)

    def remove_from_plot(self):
        """Remove the tick item from the view box or plot item."""
        if self.plot_item is not None:
            self.plot_item.layout.removeItem(self.tick_item)


class BECArrowItem(BECIndicatorItem):
    """Class to create an arrow item which can be added to a pyqtgraph plot.
    It can be either added directly to a view box or a plot item.
    To add the arrow item to a view box or plot item, use the add_to_plot method.

    Args:
        view_box (pg.ViewBox | pg.PlotItem): The view box or plot item to which the arrow item should be added.
        parent (QObject): The parent object.

    Signals:
        position_changed (tuple[float, float]): Signal emitted when the position of the arrow item has changed.
        position_changed_str (tuple[str, str]): Signal emitted when the position of the arrow item has changed.
    """

    # Signal to emit if the position of the arrow item has changed
    position_changed = Signal(tuple)
    position_changed_str = Signal(tuple)

    def __init__(self, plot_item: pg.PlotItem = None, parent=None):
        super().__init__(plot_item=plot_item, parent=parent)
        self.arrow_item = pg.ArrowItem()

    @Slot(dict)
    def set_style(self, style: dict) -> None:
        """Set the style of the arrow item

        Args:
            style (dict): The style of the arrow item. Dictionary with key,
                          value pairs which are accepted from the pg.ArrowItem.setStyle method.
        """
        self.arrow_item.setStyle(**style)

    @Slot(tuple)
    def set_position(self, pos: tuple[float, float]) -> None:
        """Set the position of the arrow item

        Args:
            pos (tuple): The position of the arrow item as a tuple (x, y).
        """
        pos_x = pos[0]
        pos_y = pos[1]
        self.arrow_item.setPos(pos_x, pos_y)
        self.position_changed.emit((pos_x, pos_y))
        self.position_changed_str.emit((str(pos_x), str(pos_y)))

    def add_to_plot(self):
        """Add the arrow item to the view box or plot item."""
        self.arrow_item.setStyle(
            angle=-90,
            pen=pg.mkPen(self.accent_colors.emergency, width=1),
            brush=pg.mkBrush(self.accent_colors.highlight),
            headLen=20,
        )
        if self.plot_item is not None:
            self.plot_item.addItem(self.arrow_item)

    def remove_from_plot(self):
        """Remove the arrow item from the view box or plot item."""
        if self.plot_item is not None:
            self.plot_item.removeItem(self.arrow_item)
