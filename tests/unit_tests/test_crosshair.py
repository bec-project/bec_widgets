# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import numpy as np
import pytest
from qtpy.QtCore import QPointF

from bec_widgets.widgets.image.image_widget import BECImageWidget
from bec_widgets.widgets.waveform.waveform_widget import BECWaveformWidget

from .client_mocks import mocked_client

# pylint: disable = redefined-outer-name


@pytest.fixture
def plot_widget_with_crosshair(qtbot, mocked_client):
    widget = BECWaveformWidget(client=mocked_client())
    widget.plot(x=[1, 2, 3], y=[4, 5, 6])
    widget.waveform.hook_crosshair()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)

    yield widget.waveform.crosshair, widget.waveform.plot_item


@pytest.fixture
def image_widget_with_crosshair(qtbot, mocked_client):
    widget = BECImageWidget(client=mocked_client())
    widget._image.add_custom_image(name="test", data=np.random.random((100, 200)))
    widget._image.hook_crosshair()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)

    yield widget._image.crosshair, widget._image.plot_item


def test_mouse_moved_lines(plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair

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
    assert np.isclose(crosshair.v_line.pos().x(), 2)
    assert np.isclose(crosshair.h_line.pos().y(), 5)


def test_mouse_moved_signals(plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair

    # Create a slot that will store the emitted values as tuples
    emitted_values_1D = []

    def slot(coordinates):
        emitted_values_1D.append(coordinates)

    # Connect the signal to the custom slot
    crosshair.coordinatesChanged1D.connect(slot)

    # Simulate a mouse moved event at a specific position
    pos_in_view = QPointF(2, 5)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]

    # Call the mouse_moved method
    crosshair.mouse_moved(event_mock)

    # Assert the expected behavior
    assert emitted_values_1D == [("Curve 1", 2, 5)]


def test_mouse_moved_signals_outside(plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair

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


def test_mouse_moved_signals_2D(image_widget_with_crosshair):
    crosshair, plot_item = image_widget_with_crosshair

    # Create a slot that will store the emitted values as tuples
    emitted_values_2D = []

    def slot(coordinates):
        emitted_values_2D.append(coordinates)

    # Connect the signal to the custom slot
    crosshair.coordinatesChanged2D.connect(slot)
    # Simulate a mouse moved event at a specific position
    pos_in_view = QPointF(22.0, 55.0)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]
    # Call the mouse_moved method
    crosshair.mouse_moved(event_mock)
    # Assert the expected behavior
    assert emitted_values_2D == [("test", 22.0, 55.0)]


def test_mouse_moved_signals_2D_outside(image_widget_with_crosshair):
    crosshair, plot_item = image_widget_with_crosshair

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
