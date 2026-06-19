import numpy as np
import pyqtgraph as pg
import pytest
from qtpy.QtCore import QPointF, Qt
from qtpy.QtGui import QTransform

from bec_widgets.utils.crosshair import Crosshair
from bec_widgets.widgets.plots.image.image_item import ImageItem
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from tests.unit_tests.client_mocks import mocked_client

from .conftest import create_widget

# pylint: disable = redefined-outer-name


@pytest.fixture
def plot_widget_with_crosshair(qtbot):
    widget = pg.PlotWidget()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)

    widget.plot(x=[1, 2, 3], y=[4, 5, 6], name="Curve 1")
    plot_item = widget.getPlotItem()
    crosshair = Crosshair(plot_item=plot_item, precision=3)

    yield crosshair, plot_item


@pytest.fixture
def image_widget_with_crosshair(qtbot):
    widget = pg.PlotWidget()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)

    image_item = ImageItem()
    image_item.setImage(np.random.rand(100, 100))

    widget.addItem(image_item)
    plot_item = widget.getPlotItem()
    crosshair = Crosshair(plot_item=plot_item, precision=3)

    yield crosshair, plot_item


def test_mouse_moved_lines(plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair

    pos_in_view = QPointF(2, 5)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]

    # Simulate mouse movement
    crosshair.mouse_moved(event_mock)

    # Check that the vertical line is indeed at x=2
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
    image_item = plot_item.items[0]

    emitted_values_2D = []

    def slot(coordinates):
        emitted_values_2D.append(coordinates)

    crosshair.coordinatesChanged2D.connect(slot)

    pos_in_view = QPointF(21.0, 55.0)
    pos_in_scene = plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]

    crosshair.mouse_moved(event_mock)

    assert emitted_values_2D == [("ImageItem", 21, 55)]


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


def test_update_coord_label_1D(plot_widget_with_crosshair):
    crosshair, _ = plot_widget_with_crosshair
    # Provide a test position
    pos = (10, 20)
    crosshair.update_coord_label(pos)
    expected_text = f"({10:.3f}, {20:.3f})"
    # Verify that the coordinate label shows only the 1D coordinates (no intensity line)
    assert crosshair.coord_label.toPlainText() == expected_text
    label_pos = crosshair.coord_label.pos()
    assert np.isclose(label_pos.x(), 10)
    assert np.isclose(label_pos.y(), 20)
    assert crosshair.coord_label.isVisible()


def test_update_coord_label_2D(image_widget_with_crosshair):
    crosshair, plot_item = image_widget_with_crosshair

    known_image = np.array([[10, 20], [30, 40]], dtype=float)

    for item in plot_item.items:
        if isinstance(item, pg.ImageItem):
            item.setImage(known_image)

    pos = (0.5, 1.2)
    crosshair.update_coord_label(pos)

    ix = int(np.clip(0.5, 0, known_image.shape[0] - 1))  # 0
    iy = int(np.clip(1.2, 0, known_image.shape[1] - 1))  # 1
    intensity = known_image[ix, iy]  # Expected: 20
    expected_text = f"({0.5:.3f}, {1.2:.3f})\nIntensity: {intensity:.3f}"

    assert crosshair.coord_label.toPlainText() == expected_text
    label_pos = crosshair.coord_label.pos()
    assert np.isclose(label_pos.x(), 0.5)
    assert np.isclose(label_pos.y(), 1.2)
    assert crosshair.coord_label.isVisible()


def test_crosshair_precision_properties(plot_widget_with_crosshair):
    """
    Ensure Crosshair.precision and Crosshair.min_precision behave correctly
    and that _current_precision() reflects changes immediately.
    """
    crosshair, plot_item = plot_widget_with_crosshair

    assert crosshair.precision == 3
    assert crosshair._current_precision() == 3

    crosshair.precision = None
    plot_item.vb.setXRange(0, 1_000, padding=0)
    plot_item.vb.setYRange(0, 1_000, padding=0)
    assert crosshair._current_precision() == crosshair.min_precision == 2  # default floor

    crosshair.min_precision = 5
    assert crosshair._current_precision() == 5

    crosshair.precision = 1
    assert crosshair._current_precision() == 1


def test_crosshair_precision_properties_image(image_widget_with_crosshair):
    """
    The same precision/min_precision behaviour must apply for crosshairs attached
    to ImageItem-based plots.
    """
    crosshair, plot_item = image_widget_with_crosshair

    assert crosshair.precision == 3
    assert crosshair._current_precision() == 3

    crosshair.precision = None
    plot_item.vb.setXRange(0, 1_000, padding=0)
    plot_item.vb.setYRange(0, 1_000, padding=0)
    assert crosshair._current_precision() == crosshair.min_precision == 2

    crosshair.min_precision = 6
    assert crosshair._current_precision() == 6

    crosshair.precision = 2
    assert crosshair._current_precision() == 2


def test_get_transformed_position(plot_widget_with_crosshair):
    """Test that _get_transformed_position correctly transforms coordinates."""
    crosshair, _ = plot_widget_with_crosshair

    # Create a simple transform
    transform = QTransform()
    transform.translate(10, 20)  # Origin is now at (10, 20)

    # Test coordinates
    x, y = 5, 8

    # Get the transformed position
    row, col = crosshair._get_transformed_position(x, y, transform)

    # Calculate expected values:
    # row should be the y-offset from origin after transform
    # col should be the x-offset from origin after transform
    expected_row = QPointF(0, 8)  # y direction offset
    expected_col = QPointF(5, 0)  # x direction offset

    # Check that the results match expectations
    assert row == expected_row
    assert col == expected_col


def test_get_transformed_position_with_scale(plot_widget_with_crosshair):
    """Test that _get_transformed_position correctly handles scaling transformations."""
    crosshair, _ = plot_widget_with_crosshair

    # Create a transform with scaling
    transform = QTransform()
    transform.translate(10, 20)  # Origin is now at (10, 20)
    transform.scale(2, 3)  # Scale x by 2 and y by 3

    # Test coordinates
    x, y = 5, 8

    # Get the transformed position
    row, col = crosshair._get_transformed_position(x, y, transform)

    # Calculate expected values with scaling applied:
    # For a scale transform, the offsets should be multiplied by the scale factors
    expected_row = QPointF(0, 8 * 3)  # y direction offset with scale factor 3
    expected_col = QPointF(5 * 2, 0)  # x direction offset with scale factor 2

    # Check that the results match expectations
    assert row == expected_row
    assert col == expected_col


def test_ignore_invisible_curves_on_move(qtbot, mocked_client):
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    c0 = wf.plot(x=[1, 2, 3], y=[1, 4, 9], name="Curve_0")
    c1 = wf.plot(x=[1, 2, 3], y=[2, 5, 10], name="Curve_1")
    wf.hook_crosshair()

    # # Simulate a mouse move at (2,5)
    pos_in_view = QPointF(2, 5)
    pos_in_scene = wf.plot_item.vb.mapViewToScene(pos_in_view)
    event_mock = [pos_in_scene]

    # 1) Both curves visible: expect markers for both
    wf.crosshair.clear_markers()
    wf.crosshair.mouse_moved(event_mock)
    assert set(wf.crosshair.marker_moved_1d.keys()) == {"Curve_0", "Curve_1"}

    # 2) Hide Curve B and repeat: only Curve_0 should remain
    c1.setVisible(False)
    wf.crosshair.clear_markers()
    wf.crosshair.mouse_moved(event_mock)
    qtbot.wait(200)
    assert set(wf.crosshair.marker_moved_1d.keys()) == {"Curve_0"}


###############################################
# Pinned marker (click to pin, remove gestures)
###############################################


class _FakeClickEvent:
    """Minimal stand-in for a pyqtgraph MouseClickEvent for routing tests."""

    def __init__(self, scene_pos, button=Qt.LeftButton, double=False):
        self._scenePos = scene_pos
        self._button = button
        self._double = double
        self.accepted = False

    def button(self):
        return self._button

    def double(self):
        return self._double

    def accept(self):
        self.accepted = True


def test_set_pin_1d_creates_marker_and_emits(plot_widget_with_crosshair):
    crosshair, _ = plot_widget_with_crosshair
    pinned = []
    crosshair.coordinatesPinned1D.connect(pinned.append)

    assert crosshair.pinned_point is None
    crosshair.set_pin(2, 5)

    assert crosshair.pinned_point is not None
    assert crosshair.pinned_pos is not None
    assert len(pinned) == 1
    _, px, py = pinned[0]
    assert np.isclose(px, 2) and np.isclose(py, 5)


def test_pin_draws_dashed_crosshair_lines(plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair
    crosshair.set_pin(2, 5)

    # A frozen, dashed crosshair (two infinite lines) is drawn at the pin.
    assert crosshair.pinned_v_line is not None
    assert crosshair.pinned_h_line is not None
    assert np.isclose(crosshair.pinned_v_line.value(), 2)
    assert np.isclose(crosshair.pinned_h_line.value(), 5)
    assert crosshair.pinned_v_line.pen.style() == Qt.PenStyle.DashLine
    assert crosshair.pinned_v_line in plot_item.items
    assert crosshair.pinned_h_line in plot_item.items

    crosshair.clear_pin()
    assert crosshair.pinned_v_line is None
    assert crosshair.pinned_h_line is None


def test_clear_pin_emits_only_when_pinned(plot_widget_with_crosshair):
    crosshair, _ = plot_widget_with_crosshair
    cleared = []
    crosshair.pinCleared.connect(lambda: cleared.append(True))

    crosshair.set_pin(2, 5)
    crosshair.clear_pin()
    assert crosshair.pinned_point is None
    assert crosshair.pinned_v_line is None
    assert crosshair.pinned_h_line is None
    assert crosshair.pinned_pos is None
    assert cleared == [True]

    # Clearing again is a no-op and must not re-emit.
    crosshair.clear_pin()
    assert cleared == [True]


def test_single_click_pins(qtbot, plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair
    graphics_view = plot_item.vb.scene().views()[0]
    qtbot.waitExposed(graphics_view)
    pos = graphics_view.mapFromScene(plot_item.vb.mapViewToScene(QPointF(2, 5)))

    qtbot.mouseClick(graphics_view.viewport(), Qt.LeftButton, pos=pos)
    assert crosshair.pinned_point is not None
    assert crosshair.pinned_pos is not None


def test_reclick_on_pin_removes_it(plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair
    crosshair.set_pin(2, 5)
    assert crosshair.pinned_point is not None

    # A left click that lands on the existing pin toggles it off.
    scene_pos = plot_item.vb.mapViewToScene(QPointF(*crosshair.pinned_pos))
    crosshair.mouse_clicked(_FakeClickEvent(scene_pos, button=Qt.LeftButton))
    assert crosshair.pinned_point is None


def test_double_click_clears_pin(plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair
    crosshair.set_pin(2, 5)
    assert crosshair.pinned_point is not None

    scene_pos = plot_item.vb.mapViewToScene(QPointF(2, 5))
    crosshair.mouse_clicked(_FakeClickEvent(scene_pos, double=True))
    assert crosshair.pinned_point is None


def test_right_click_on_pin_removes_via_menu(monkeypatch, plot_widget_with_crosshair):
    """Right-clicks are handled by the pin item itself (accepting the event there
    is what keeps pyqtgraph's plot context menu from opening on top)."""
    from qtpy.QtWidgets import QMenu

    crosshair, _ = plot_widget_with_crosshair
    crosshair.set_pin(2, 5)
    assert crosshair.pinned_point is not None

    # Choose the (only) "Remove pinned marker" action without showing a real menu.
    monkeypatch.setattr(QMenu, "exec_", lambda self, *a, **k: self.actions()[0])
    event = _FakeClickEvent(None, button=Qt.RightButton)
    crosshair.pinned_point.mouseClickEvent(event)

    assert crosshair.pinned_point is None
    assert event.accepted is True


def test_right_click_on_pin_menu_cancelled_keeps_pin(monkeypatch, plot_widget_with_crosshair):
    from qtpy.QtWidgets import QMenu

    crosshair, _ = plot_widget_with_crosshair
    crosshair.set_pin(2, 5)

    monkeypatch.setattr(QMenu, "exec_", lambda self, *a, **k: None)  # menu dismissed
    event = _FakeClickEvent(None, button=Qt.RightButton)
    crosshair.pinned_point.mouseClickEvent(event)

    assert crosshair.pinned_point is not None
    assert event.accepted is True


def test_right_click_without_pin_is_ignored(plot_widget_with_crosshair):
    crosshair, plot_item = plot_widget_with_crosshair
    scene_pos = plot_item.vb.mapViewToScene(QPointF(2, 5))
    event = _FakeClickEvent(scene_pos, button=Qt.RightButton)
    crosshair.mouse_clicked(event)
    # No pin -> nothing handled at scene level, the event is left for
    # pyqtgraph's own context menu.
    assert event.accepted is False


def test_log_mode_change_clears_pin(plot_widget_with_crosshair):
    """The pin lives in view coordinates; toggling log mode must drop it instead
    of leaving it at a now-meaningless position."""
    crosshair, plot_item = plot_widget_with_crosshair
    crosshair.set_pin(2, 5)
    assert crosshair.pinned_point is not None

    plot_item.ctrl.logYCheck.setChecked(True)

    assert crosshair.pinned_point is None
    assert crosshair.pinned_pos is None


def test_adopted_pin_rebinds_removal_callback(monkeypatch, plot_widget_with_crosshair):
    """After release/adopt (crosshair toggled off/on) the pin's context-menu
    removal must act on the adopting crosshair, not the deleted one."""
    from qtpy.QtWidgets import QMenu

    crosshair, _ = plot_widget_with_crosshair
    crosshair.set_pin(2, 5)

    state = crosshair.release_pin()
    # While detached there is no owner: the menu is disabled.
    assert state["point"]._on_remove is None

    crosshair.adopt_pin(state)
    assert crosshair.pinned_point is not None

    monkeypatch.setattr(QMenu, "exec_", lambda self, *a, **k: self.actions()[0])
    event = _FakeClickEvent(None, button=Qt.RightButton)
    crosshair.pinned_point.mouseClickEvent(event)
    assert crosshair.pinned_point is None


def test_set_pin_2d_emits_pixel_coordinates(image_widget_with_crosshair):
    crosshair, _ = image_widget_with_crosshair
    pinned = []
    crosshair.coordinatesPinned2D.connect(pinned.append)

    crosshair.set_pin(40, 60)
    assert crosshair.pinned_point is not None
    assert len(pinned) == 1
    _, px, py = pinned[0]
    assert (px, py) == (40, 60)


def test_reset_preserves_pin_cleanup_removes_it(image_widget_with_crosshair):
    crosshair, _ = image_widget_with_crosshair
    crosshair.set_pin(40, 60)
    assert crosshair.pinned_point is not None

    # A data/scan reset keeps the pin (a persistent annotation).
    crosshair.reset()
    assert crosshair.pinned_point is not None
    assert crosshair.pinned_pos is not None

    # Full teardown removes it.
    crosshair.cleanup()
    assert crosshair.pinned_point is None
    assert crosshair.pinned_pos is None
