import pyqtgraph as pg
import pytest
from bec_qthemes._main import AccentColors

from bec_widgets.utils.plot_indicator_items import BECArrowItem, BECTickItem


@pytest.fixture(scope="function")
def arrow_item():
    """Fixture for the BECArrowItem class"""
    item = BECArrowItem(plot_item=pg.PlotItem())
    yield item


def test_arrow_item_add_to_plot(arrow_item):
    """Test the add_to_plot method"""
    assert arrow_item.plot_item is not None
    assert arrow_item.plot_item.items == []
    arrow_item.accent_colors = AccentColors(theme="dark")
    arrow_item.add_to_plot()
    assert arrow_item.plot_item.items == [arrow_item.arrow_item]


def test_arrow_item_remove_to_plot(arrow_item):
    """Test the remove_from_plot method"""
    arrow_item.accent_colors = AccentColors(theme="dark")
    arrow_item.add_to_plot()
    assert arrow_item.plot_item.items == [arrow_item.arrow_item]
    arrow_item.remove_from_plot()
    assert arrow_item.plot_item.items == []


def test_arrow_item_set_position(arrow_item):
    """Test the set_position method"""
    container = []

    def signal_callback(tup: tuple):
        container.append(tup)

    arrow_item.accent_colors = AccentColors(theme="dark")
    arrow_item.add_to_plot()
    arrow_item.position_changed.connect(signal_callback)
    arrow_item.set_position(pos=(1, 1))
    assert arrow_item.arrow_item.pos().toTuple() == (1, 1)
    arrow_item.set_position(pos=(2, 2))
    assert arrow_item.arrow_item.pos().toTuple() == (2, 2)
    assert container == [(1, 1), (2, 2)]


@pytest.fixture(scope="function")
def tick_item():
    """Fixture for the BECArrowItem class"""
    item = BECTickItem(plot_item=pg.PlotItem())
    yield item


def test_tick_item_add_to_plot(tick_item):
    """Test the add_to_plot method"""
    assert tick_item.plot_item is not None
    assert tick_item.plot_item.items == []
    tick_item.accent_colors = AccentColors(theme="dark")
    tick_item.add_to_plot()
    assert tick_item.plot_item.layout.itemAt(4, 1) == tick_item.tick_item


def test_tick_item_remove_to_plot(tick_item):
    """Test the remove_from_plot method"""
    tick_item.accent_colors = AccentColors(theme="dark")
    tick_item.add_to_plot()
    assert tick_item.plot_item.layout.itemAt(4, 1) == tick_item.tick_item
    tick_item.remove_from_plot()
    assert tick_item.plot_item.layout.itemAt(4, 1) is None


def test_tick_item_set_position(tick_item):
    """Test the set_position method"""
    container = []

    def signal_callback(val: float):
        container.append(val)

    tick_item.accent_colors = AccentColors(theme="dark")
    tick_item.add_to_plot()
    tick_item.position_changed.connect(signal_callback)

    tick_item.set_position(pos=1)
    assert tick_item._tick_pos == 1
    tick_item.set_position(pos=2)
    assert tick_item._tick_pos == 2
    assert container == [1.0, 2.0]
