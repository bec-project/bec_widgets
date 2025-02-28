"""Module to create an arrow item for a pyqtgraph plot"""

import numpy as np
import pyqtgraph as pg
from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject, QPointF, Signal, Slot

from bec_widgets.utils.colors import get_accent_colors

logger = bec_logger.logger


class BECIndicatorItem(QObject):

    def __init__(self, plot_item: pg.PlotItem = None, parent=None):
        super().__init__(parent=parent)
        self.accent_colors = get_accent_colors()
        self.plot_item = plot_item
        self._item_on_plot = False
        self._pos = None
        self.is_log_x = False
        self.is_log_y = False

    @property
    def item_on_plot(self) -> bool:
        """Returns if the item is on the plot"""
        return self._item_on_plot

    @item_on_plot.setter
    def item_on_plot(self, value: bool) -> None:
        self._item_on_plot = value

    def add_to_plot(self) -> None:
        """Add the item to the plot"""
        raise NotImplementedError("Method add_to_plot not implemented")

    def remove_from_plot(self) -> None:
        """Remove the item from the plot"""
        raise NotImplementedError("Method remove_from_plot not implemented")

    def set_position(self, pos) -> None:
        """This method should implement the logic to set the position of the
        item on the plot. Depending on the child class, the position can be
        a tuple (x,y) or a single value, i.e. x position where y position is fixed.
        """
        raise NotImplementedError("Method set_position not implemented")

    def check_log(self):
        """Checks if the x or y axis is in log scale and updates the internal state accordingly."""
        self.is_log_x = self.plot_item.ctrl.logXCheck.isChecked()
        self.is_log_y = self.plot_item.ctrl.logYCheck.isChecked()
        self.set_position(self._pos)


class BECTickItem(BECIndicatorItem):
    """Class to create a tick item which can be added to a pyqtgraph plot.
    The tick item will be added to the layout of the plot item and can be used to indicate
    a position"""

    position_changed = Signal(float)
    position_changed_str = Signal(str)

    def __init__(self, plot_item: pg.PlotItem = None, parent=None):
        super().__init__(plot_item=plot_item, parent=parent)
        self.tick_item = pg.TickSliderItem(
            parent=parent, allowAdd=False, allowRemove=False, orientation="bottom"
        )
        self.tick_item.skip_auto_range = True
        self.tick = None
        self._pos = 0.0
        self._range = [0, 1]

    @Slot(float)
    def set_position(self, pos: float) -> None:
        """Set the x position of the tick item

        Args:
            pos (float): The position of the tick item.
        """
        if self.is_log_x is True:
            pos = pos if pos > 0 else 1e-10
            pos = np.log10(pos)
        self._pos = pos
        view_box = self.plot_item.getViewBox()  # Ensure you're accessing the correct view box
        view_range = view_box.viewRange()[0]
        self.update_range(self.plot_item.vb, view_range)
        self.position_changed.emit(pos)
        self.position_changed_str.emit(str(pos))

    @Slot()
    def update_range(self, _, view_range: tuple[float, float]) -> None:
        """Update the range of the tick item

        Args:
            vb (pg.ViewBox): The view box.
            viewRange (tuple): The view range.
        """
        if self._pos < view_range[0] or self._pos > view_range[1]:
            self.tick_item.setVisible(False)
        else:
            self.tick_item.setVisible(True)

        if self.tick_item.isVisible():
            origin = self.tick_item.tickSize / 2.0
            length = self.tick_item.length

            length_with_padding = length + self.tick_item.tickSize + 2

            self._range = view_range
            tick_with_padding = (self._pos - view_range[0]) / (view_range[1] - view_range[0])
            tick_value = (tick_with_padding * length_with_padding - origin) / length
            self.tick_item.setTickValue(self.tick, tick_value)

    def add_to_plot(self):
        """Add the tick item to the view box or plot item."""
        if self.plot_item is None:
            return

        self.plot_item.layout.addItem(self.tick_item, 2, 1)
        self.tick_item.setOrientation("top")
        self.tick = self.tick_item.addTick(0, movable=False, color=self.accent_colors.highlight)
        self.update_tick_pos_y()
        self.plot_item.vb.sigXRangeChanged.connect(self.update_range)
        self.plot_item.ctrl.logXCheck.checkStateChanged.connect(self.check_log)
        self.plot_item.ctrl.logYCheck.checkStateChanged.connect(self.check_log)
        self.plot_item.vb.geometryChanged.connect(self.update_tick_pos_y)
        self.item_on_plot = True

    @Slot()
    def update_tick_pos_y(self):
        """Update tick position, while respecting the tick_item coordinates"""
        pos = self.tick.pos()
        pos = self.tick_item.mapToParent(pos)
        new_pos = self.plot_item.vb.geometry().bottom()
        new_pos = self.tick_item.mapFromParent(QPointF(pos.x(), new_pos))
        self.tick.setPos(new_pos)

    def remove_from_plot(self):
        """Remove the tick item from the view box or plot item."""
        if self.plot_item is not None and self.item_on_plot is True:
            self.plot_item.vb.sigXRangeChanged.disconnect(self.update_range)
            self.plot_item.ctrl.logXCheck.checkStateChanged.disconnect(self.check_log)
            self.plot_item.ctrl.logYCheck.checkStateChanged.disconnect(self.check_log)
            if self.plot_item.layout is not None:
                self.plot_item.layout.removeItem(self.tick_item)
        self.item_on_plot = False

    def cleanup(self) -> None:
        """Cleanup the item"""
        self.remove_from_plot()
        self.tick_item = None


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
        self.arrow_item = pg.ArrowItem(parent=parent)
        self.arrow_item.skip_auto_range = True
        self._pos = (0, 0)
        self.arrow_item.setVisible(False)

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
        self._pos = pos
        pos_x = pos[0]
        pos_y = pos[1]
        if self.is_log_x is True:
            pos_x = np.log10(pos_x) if pos_x > 0 else 1e-10
            view_box = self.plot_item.getViewBox()  # Ensure you're accessing the correct view box
            view_range = view_box.viewRange()[0]
            # Avoid values outside the view range in the negative direction. Otherwise, there is
            # a buggy behaviour of the arrow item and it appears at the wrong position.
            if pos_x < view_range[0]:
                pos_x = view_range[0]
        if self.is_log_y is True:
            pos_y = np.log10(pos_y) if pos_y > 0 else 1e-10

        self.arrow_item.setPos(pos_x, pos_y)
        self.position_changed.emit(self._pos)
        self.position_changed_str.emit((str(self._pos[0]), str(self._pos[1])))

    def add_to_plot(self):
        """Add the arrow item to the view box or plot item."""
        if not self.arrow_item:
            logger.warning(f"Arrow item was already destroyed, cannot be created")
            return

        self.arrow_item.setStyle(
            angle=-90,
            pen=pg.mkPen(self.accent_colors.emergency, width=1),
            brush=pg.mkBrush(self.accent_colors.highlight),
            headLen=20,
        )
        self.arrow_item.setVisible(True)
        if self.plot_item is not None:
            self.plot_item.addItem(self.arrow_item)
            self.plot_item.ctrl.logXCheck.checkStateChanged.connect(self.check_log)
            self.plot_item.ctrl.logYCheck.checkStateChanged.connect(self.check_log)
            self.item_on_plot = True

    def remove_from_plot(self):
        """Remove the arrow item from the view box or plot item."""
        if self.plot_item is not None and self.item_on_plot is True:
            self.plot_item.ctrl.logXCheck.checkStateChanged.disconnect(self.check_log)
            self.plot_item.ctrl.logYCheck.checkStateChanged.disconnect(self.check_log)
            self.plot_item.removeItem(self.arrow_item)
        self.item_on_plot = False

    def cleanup(self) -> None:
        """Cleanup the item"""
        self.remove_from_plot()
        self.arrow_item = None
