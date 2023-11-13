import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import QPointF

from bec_widgets.qt_utils import Crosshair


def test_mouse_moved_lines(qtbot):
    # Create a PlotWidget and add a PlotItem
    plot_widget = pg.PlotWidget(title="1D PlotWidget with multiple curves")
    plot_item = plot_widget.getPlotItem()
    plot_item.plot([1, 2, 3], [4, 5, 6])

    # Create a Crosshair instance
    crosshair = Crosshair(plot_item=plot_item, precision=2)

    # Connect the signals to slots that will store the emitted values
    emitted_values_1D = []
    crosshair.coordinatesChanged1D.connect(emitted_values_1D.append)

    # Simulate a mouse moved event at a specific position
    pos_in_view = QPointF(2, 5)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]

    # Call the mouse_moved method
    crosshair.mouse_moved(event_mock)

    # Assert the expected behavior
    assert crosshair.v_line.pos().x() == 2
    assert crosshair.h_line.pos().y() == 5


def test_mouse_moved_signals(qtbot):
    # Create a PlotWidget and add a PlotItem
    plot_widget = pg.PlotWidget(title="1D PlotWidget with multiple curves")
    plot_item = plot_widget.getPlotItem()
    plot_item.plot([1, 2, 3], [4, 5, 6])

    # Create a Crosshair instance
    crosshair = Crosshair(plot_item=plot_item, precision=2)

    # Create a slot that will store the emitted values as tuples
    emitted_values_1D = []

    def slot(x, y_values):
        emitted_values_1D.append((x, y_values))

    # Connect the signal to the custom slot
    crosshair.coordinatesChanged1D.connect(slot)

    # Simulate a mouse moved event at a specific position
    pos_in_view = QPointF(2, 5)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]

    # Call the mouse_moved method
    crosshair.mouse_moved(event_mock)

    # Assert the expected behavior
    assert emitted_values_1D == [(2.0, [5.0])]


def test_mouse_moved_signals_outside(qtbot):
    # Create a PlotWidget and add a PlotItem
    plot_widget = pg.PlotWidget(title="1D PlotWidget with multiple curves")
    plot_item = plot_widget.getPlotItem()
    plot_item.plot([1, 2, 3], [4, 5, 6])

    # Create a Crosshair instance
    crosshair = Crosshair(plot_item=plot_item, precision=2)

    # Create a slot that will store the emitted values as tuples
    emitted_values_1D = []

    def slot(x, y_values):
        emitted_values_1D.append((x, y_values))

    # Connect the signal to the custom slot
    crosshair.coordinatesChanged1D.connect(slot)

    # Simulate a mouse moved event at a specific position
    pos_in_view = QPointF(22, 55)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]

    # Call the mouse_moved method
    crosshair.mouse_moved(event_mock)

    # Assert the expected behavior
    assert emitted_values_1D == []


def test_mouse_moved_signals_2D(qtbot):
    # write similar test for 2D plot

    # Create a PlotWidget and add a PlotItem
    plot_widget = pg.PlotWidget(title="2D plot with crosshair and ROI square")
    data_2D = np.random.random((100, 200))
    plot_item = plot_widget.getPlotItem()
    image_item = pg.ImageItem(data_2D)
    plot_item.addItem(image_item)
    # Create a Crosshair instance
    crosshair = Crosshair(plot_item=plot_item)
    # Create a slot that will store the emitted values as tuples
    emitted_values_2D = []

    def slot(x, y):
        emitted_values_2D.append((x, y))

    # Connect the signal to the custom slot
    crosshair.coordinatesChanged2D.connect(slot)
    # Simulate a mouse moved event at a specific position
    pos_in_view = QPointF(22.0, 55.0)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]
    # Call the mouse_moved method
    crosshair.mouse_moved(event_mock)
    # Assert the expected behavior
    assert emitted_values_2D == [(22.0, 55.0)]


def test_mouse_moved_signals_2D_outside(qtbot):
    # write similar test for 2D plot

    # Create a PlotWidget and add a PlotItem
    plot_widget = pg.PlotWidget(title="2D plot with crosshair and ROI square")
    data_2D = np.random.random((100, 200))
    plot_item = plot_widget.getPlotItem()
    image_item = pg.ImageItem(data_2D)
    plot_item.addItem(image_item)
    # Create a Crosshair instance
    crosshair = Crosshair(plot_item=plot_item, precision=2)
    # Create a slot that will store the emitted values as tuples
    emitted_values_2D = []

    def slot(x, y):
        emitted_values_2D.append((x, y))

    # Connect the signal to the custom slot
    crosshair.coordinatesChanged2D.connect(slot)
    # Simulate a mouse moved event at a specific position
    pos_in_view = QPointF(220.0, 555.0)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]
    # Call the mouse_moved method
    crosshair.mouse_moved(event_mock)
    # Assert the expected behavior
    assert emitted_values_2D == []
