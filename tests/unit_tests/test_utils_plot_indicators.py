# TODO temporary disabled until migrate tick and arrow items to new system
# import pytest
# from qtpy.QtCore import QPointF
#
# from bec_widgets.widgets.containers.figure import BECFigure
#
# from .client_mocks import mocked_client
#
#
# @pytest.fixture
# def plot_widget_with_arrow_item(qtbot, mocked_client):
#     widget = BECFigure(client=mocked_client())
#     qtbot.addWidget(widget)
#     qtbot.waitExposed(widget)
#     waveform = widget.plot()
#
#     yield waveform.arrow_item, waveform.plot_item
#
#
# @pytest.fixture
# def plot_widget_with_tick_item(qtbot, mocked_client):
#     widget = BECFigure(client=mocked_client())
#     qtbot.addWidget(widget)
#     qtbot.waitExposed(widget)
#     waveform = widget.plot()
#
#     yield waveform.tick_item, waveform.plot_item
#
#
# def test_arrow_item_add_to_plot(plot_widget_with_arrow_item):
#     """Test the add_to_plot method"""
#     arrow_item, plot_item = plot_widget_with_arrow_item
#     assert arrow_item.plot_item is not None
#     assert arrow_item.plot_item.items == []
#     arrow_item.add_to_plot()
#     assert arrow_item.plot_item.items == [arrow_item.arrow_item]
#     arrow_item.remove_from_plot()
#
#
# def test_arrow_item_set_position(plot_widget_with_arrow_item):
#     """Test the set_position method"""
#     arrow_item, plot_item = plot_widget_with_arrow_item
#     container = []
#
#     def signal_callback(tup: tuple):
#         container.append(tup)
#
#     arrow_item.add_to_plot()
#     arrow_item.position_changed.connect(signal_callback)
#     arrow_item.set_position(pos=(1, 1))
#     point = QPointF(1.0, 1.0)
#     assert arrow_item.arrow_item.pos() == point
#     arrow_item.set_position(pos=(2, 2))
#     point = QPointF(2.0, 2.0)
#     assert arrow_item.arrow_item.pos() == point
#     assert container == [(1, 1), (2, 2)]
#     arrow_item.remove_from_plot()
#
#
# def test_arrow_item_cleanup(plot_widget_with_arrow_item):
#     """Test cleanup procedure"""
#     arrow_item, plot_item = plot_widget_with_arrow_item
#     arrow_item.add_to_plot()
#     assert arrow_item.item_on_plot is True
#     arrow_item.cleanup()
#     assert arrow_item.plot_item.items == []
#     assert arrow_item.item_on_plot is False
#     assert arrow_item.arrow_item is None
#
#
# def test_tick_item_add_to_plot(plot_widget_with_tick_item):
#     """Test the add_to_plot method"""
#     tick_item, plot_item = plot_widget_with_tick_item
#     assert tick_item.plot_item is not None
#     assert tick_item.plot_item.items == []
#     tick_item.add_to_plot()
#     assert tick_item.plot_item.layout.itemAt(2, 1) == tick_item.tick_item
#     assert tick_item.item_on_plot is True
#     new_pos = plot_item.vb.geometry().bottom()
#     pos = tick_item.tick.pos()
#     new_pos = tick_item.tick_item.mapFromParent(QPointF(pos.x(), new_pos))
#     assert new_pos.y() == pos.y()
#     tick_item.remove_from_plot()
#
#
# def test_tick_item_set_position(plot_widget_with_tick_item):
#     """Test the set_position method"""
#     tick_item, plot_item = plot_widget_with_tick_item
#     container = []
#
#     def signal_callback(val: float):
#         container.append(val)
#
#     tick_item.add_to_plot()
#     tick_item.position_changed.connect(signal_callback)
#
#     tick_item.set_position(pos=1)
#     assert tick_item._pos == 1
#     tick_item.set_position(pos=2)
#     assert tick_item._pos == 2
#     assert container == [1.0, 2.0]
#     tick_item.remove_from_plot()
#
#
# def test_tick_item_cleanup(plot_widget_with_tick_item):
#     """Test cleanup procedure"""
#     tick_item, plot_item = plot_widget_with_tick_item
#     tick_item.add_to_plot()
#     assert tick_item.item_on_plot is True
#     tick_item.cleanup()
#     ticks = getattr(tick_item.plot_item.layout.itemAt(3, 1), "ticks", None)
#     assert ticks == None
#     assert tick_item.item_on_plot is False
#     assert tick_item.tick_item is None
