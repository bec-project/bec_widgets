import numpy as np
import pytest
from qtpy.QtCore import QPointF, Qt

from bec_widgets.widgets.plots.image.image_widget import BECImageWidget
from bec_widgets.widgets.plots.waveform.waveform_widget import BECWaveformWidget

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

    emitted_values_1D = []

    def slot(coordinates):
        emitted_values_1D.append(coordinates)

    crosshair.coordinatesChanged1D.connect(slot)

    pos_in_view = QPointF(2, 5)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]

    crosshair.mouse_moved(event_mock)

    # Assert the expected behavior
    assert emitted_values_1D == [("Curve 1", 2, 5)]


def test_mouse_moved_signals_outside(plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair

    # Create a slot that will store the emitted values as tuples
    emitted_values_1D = []

    def slot(coordinates):
        emitted_values_1D.append(coordinates)

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

    emitted_values_2D = []

    def slot(coordinates):
        emitted_values_2D.append(coordinates)

    crosshair.coordinatesChanged2D.connect(slot)

    pos_in_view = QPointF(22.0, 55.0)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]

    crosshair.mouse_moved(event_mock)

    assert emitted_values_2D == [("test", 22.0, 55.0)]


def test_mouse_moved_signals_2D_outside(image_widget_with_crosshair):
    crosshair, plot_item = image_widget_with_crosshair

    emitted_values_2D = []

    def slot(coordinates):
        emitted_values_2D.append(coordinates)

    crosshair.coordinatesChanged2D.connect(slot)

    pos_in_view = QPointF(220.0, 555.0)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]

    crosshair.mouse_moved(event_mock)

    assert emitted_values_2D == []


def test_marker_positions_after_mouse_move(plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair

    pos_in_view = QPointF(2, 5)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]

    crosshair.mouse_moved(event_mock)

    marker = crosshair.marker_moved_1d["Curve 1"]
    marker_x, marker_y = marker.getData()
    assert marker_x == [2]
    assert marker_y == [5]


def test_scale_emitted_coordinates(plot_widget_with_crosshair):
    crosshair, _ = plot_widget_with_crosshair

    x, y = crosshair.scale_emitted_coordinates(2, 5)
    assert x == 2
    assert y == 5

    crosshair.is_log_x = True
    crosshair.is_log_y = True

    x, y = crosshair.scale_emitted_coordinates(np.log10(2), np.log10(5))
    assert np.isclose(x, 2)
    assert np.isclose(y, 5)


def test_crosshair_changed_signal(plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair

    emitted_positions = []

    def slot(position):
        emitted_positions.append(position)

    crosshair.crosshairChanged.connect(slot)

    pos_in_view = QPointF(2, 5)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]

    crosshair.mouse_moved(event_mock)

    x, y = emitted_positions[0]

    assert np.isclose(x, 2)
    assert np.isclose(y, 5)


def test_marker_positions_after_mouse_move(plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair

    pos_in_view = QPointF(2, 5)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]

    crosshair.mouse_moved(event_mock)

    marker = crosshair.marker_moved_1d["Curve 1"]
    marker_x, marker_y = marker.getData()
    assert marker_x == [2]
    assert marker_y == [5]


def test_crosshair_clicked_signal(qtbot, plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair

    emitted_positions = []

    def slot(position):
        emitted_positions.append(position)

    crosshair.crosshairClicked.connect(slot)

    x_data = 2
    y_data = 5

    # Map data coordinates to scene coordinates
    pos_in_scene = plot_item.vb.mapViewToScene(QPointF(x_data, y_data))
    # Map scene coordinates to widget coordinates
    graphics_view = plot_item.vb.scene().views()[0]
    qtbot.waitExposed(graphics_view)
    pos_in_widget = graphics_view.mapFromScene(pos_in_scene)

    # Simulate mouse click
    qtbot.mouseClick(graphics_view.viewport(), Qt.LeftButton, pos=pos_in_widget)

    x, y = emitted_positions[0]

    assert np.isclose(round(x, 1), 2)
    assert np.isclose(round(y, 1), 5)
