import pyqtgraph as pg
import pytest

from bec_widgets.widgets.waveform.waveform_widget import BECWaveformWidget

from .client_mocks import mocked_client


@pytest.fixture
def plot_widget_with_arrow_item(qtbot, mocked_client):
    widget = BECWaveformWidget(client=mocked_client())
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)

    yield widget.waveform.arrow_item, widget.waveform.plot_item


@pytest.fixture
def plot_widget_with_tick_item(qtbot, mocked_client):
    widget = BECWaveformWidget(client=mocked_client())
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)

    yield widget.waveform.motor_pos_tick, widget.waveform.plot_item


def test_arrow_item_add_to_plot(plot_widget_with_arrow_item):
    """Test the add_to_plot method"""
    arrow_item, plot_item = plot_widget_with_arrow_item
    assert arrow_item.plot_item is not None
    assert arrow_item.plot_item.items == []
    arrow_item.add_to_plot()
    assert arrow_item.plot_item.items == [arrow_item.arrow_item]


def test_arrow_item_remove_to_plot(plot_widget_with_arrow_item):
    """Test the remove_from_plot method"""
    arrow_item, plot_item = plot_widget_with_arrow_item
    arrow_item.add_to_plot()
    assert arrow_item.plot_item.items == [arrow_item.arrow_item]
    arrow_item.remove_from_plot()
    assert arrow_item.plot_item.items == []


def test_arrow_item_set_position(plot_widget_with_arrow_item):
    """Test the set_position method"""
    arrow_item, plot_item = plot_widget_with_arrow_item
    container = []

    def signal_callback(tup: tuple):
        container.append(tup)

    arrow_item.add_to_plot()
    arrow_item.position_changed.connect(signal_callback)
    arrow_item.set_position(pos=(1, 1))
    assert arrow_item.arrow_item.pos().toTuple() == (1, 1)
    arrow_item.set_position(pos=(2, 2))
    assert arrow_item.arrow_item.pos().toTuple() == (2, 2)
    assert container == [(1, 1), (2, 2)]


def test_tick_item_add_to_plot(plot_widget_with_tick_item):
    """Test the add_to_plot method"""
    tick_item, plot_item = plot_widget_with_tick_item
    assert tick_item.plot_item is not None
    assert tick_item.plot_item.items == []
    tick_item.add_to_plot()
    assert tick_item.plot_item.layout.itemAt(4, 1) == tick_item.tick_item


def test_tick_item_remove_to_plot(plot_widget_with_tick_item):
    """Test the remove_from_plot method"""
    tick_item, plot_item = plot_widget_with_tick_item
    tick_item.add_to_plot()
    assert tick_item.plot_item.layout.itemAt(4, 1) == tick_item.tick_item
    tick_item.remove_from_plot()
    assert tick_item.plot_item.layout.itemAt(4, 1) is None


def test_tick_item_set_position(plot_widget_with_tick_item):
    """Test the set_position method"""
    tick_item, plot_item = plot_widget_with_tick_item
    container = []

    def signal_callback(val: float):
        container.append(val)

    tick_item.add_to_plot()
    tick_item.position_changed.connect(signal_callback)

    tick_item.set_position(pos=1)
    assert tick_item._pos == 1
    tick_item.set_position(pos=2)
    assert tick_item._pos == 2
    assert container == [1.0, 2.0]
