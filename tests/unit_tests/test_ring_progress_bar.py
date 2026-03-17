# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import json

import pytest
from bec_lib.endpoints import MessageEndpoints
from pydantic import ValidationError
from qtpy.QtCore import QPoint, QPointF
from qtpy.QtGui import QColor

from bec_widgets.utils import Colors
from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_bar import (
    RingProgressBar,
    RingProgressContainerWidget,
)

from .client_mocks import mocked_client


@pytest.fixture
def ring_progress_bar(qtbot, mocked_client):
    widget = RingProgressBar(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_bar_init(ring_progress_bar):
    assert ring_progress_bar is not None
    assert ring_progress_bar.client is not None
    assert isinstance(ring_progress_bar, RingProgressBar)
    assert ring_progress_bar.config.widget_class == "RingProgressBar"
    assert ring_progress_bar.config.gui_id is not None
    assert ring_progress_bar.gui_id == ring_progress_bar.config.gui_id


def test_rpb_center_label(ring_progress_bar):
    test_text = "Center Label"
    ring_progress_bar.set_center_label(test_text)
    assert ring_progress_bar.center_label == test_text
    assert ring_progress_bar.ring_progress_bar.center_label.text() == test_text


def test_add_ring(qtbot, ring_progress_bar):
    ring_progress_bar.show()
    initial_num_bars = ring_progress_bar.ring_progress_bar.num_bars
    assert initial_num_bars == len(ring_progress_bar.rings)
    ring_progress_bar.add_ring()
    assert ring_progress_bar.ring_progress_bar.num_bars == initial_num_bars + 1
    assert len(ring_progress_bar.rings) == initial_num_bars + 1
    qtbot.wait(200)


def test_remove_ring(ring_progress_bar):
    ring_progress_bar.add_ring()
    initial_num_bars = ring_progress_bar.ring_progress_bar.num_bars
    assert initial_num_bars == len(ring_progress_bar.rings)
    ring_progress_bar.remove_ring()
    assert ring_progress_bar.ring_progress_bar.num_bars == initial_num_bars - 1
    assert len(ring_progress_bar.rings) == initial_num_bars - 1


def test_remove_ring_no_bars(ring_progress_bar):
    # Remove all rings first
    while ring_progress_bar.ring_progress_bar.num_bars > 0:
        ring_progress_bar.remove_ring()
    initial_num_bars = ring_progress_bar.ring_progress_bar.num_bars
    assert initial_num_bars == 0
    # Attempt to remove a ring when there are none
    ring_progress_bar.remove_ring()
    assert ring_progress_bar.ring_progress_bar.num_bars == initial_num_bars
    assert len(ring_progress_bar.rings) == initial_num_bars


def test_bar_set_value(ring_progress_bar):
    ring_progress_bar.add_ring()
    ring_progress_bar.add_ring()

    ring_progress_bar.rings[0].set_value(10)
    ring_progress_bar.rings[1].set_value(20)
    ring_values = [ring.config.value for ring in ring_progress_bar.rings]
    assert ring_values == [10, 20]


def test_bar_set_precision(ring_progress_bar):
    # Add 3 rings
    ring_progress_bar.add_ring()
    ring_progress_bar.add_ring()
    ring_progress_bar.add_ring()

    assert ring_progress_bar.ring_progress_bar.num_bars == 3
    assert len(ring_progress_bar.rings) == 3

    # Set precision for all rings
    for ring in ring_progress_bar.rings:
        ring.set_precision(2)
    ring_precision = [ring.config.precision for ring in ring_progress_bar.rings]
    assert ring_precision == [2, 2, 2]

    # Set values
    for i, ring in enumerate(ring_progress_bar.rings):
        ring.set_value([10.1234, 20.1234, 30.1234][i])
    ring_values = [ring.config.value for ring in ring_progress_bar.rings]
    assert ring_values == [10.12, 20.12, 30.12]

    # Set precision for ring at index 1
    ring_progress_bar.rings[1].set_precision(4)
    ring_precision = [ring.config.precision for ring in ring_progress_bar.rings]
    assert ring_precision == [2, 4, 2]

    # Set values again
    for i, ring in enumerate(ring_progress_bar.rings):
        ring.set_value([10.1234, 20.1234, 30.1234][i])
    ring_values = [ring.config.value for ring in ring_progress_bar.rings]
    assert ring_values == [10.12, 20.1234, 30.12]


def test_set_min_max_value(ring_progress_bar):
    # Add 2 rings
    ring_progress_bar.add_ring()
    ring_progress_bar.add_ring()

    # Set min/max values for all rings
    for ring in ring_progress_bar.rings:
        ring.set_min_max_values(0, 10)
    ring_min_values = [ring.config.min_value for ring in ring_progress_bar.rings]
    ring_max_values = [ring.config.max_value for ring in ring_progress_bar.rings]

    assert ring_min_values == [0, 0]
    assert ring_max_values == [10, 10]

    # Set values
    ring_progress_bar.rings[0].set_value(5)
    ring_progress_bar.rings[1].set_value(15)
    ring_values = [ring.config.value for ring in ring_progress_bar.rings]
    assert ring_values == [5, 10]


def test_setup_colors_from_colormap(ring_progress_bar):
    # Add 5 rings
    for _ in range(5):
        ring_progress_bar.add_ring()
    ring_progress_bar.ring_progress_bar.set_colors_from_map("viridis", "RGB")

    expected_colors = Colors.golden_angle_color("viridis", 5, "RGB")
    converted_colors = [ring.color.getRgb() for ring in ring_progress_bar.rings]
    ring_config_colors = [QColor(ring.config.color).getRgb() for ring in ring_progress_bar.rings]

    assert expected_colors == converted_colors
    assert ring_config_colors == expected_colors


def get_colors_from_rings(rings):
    converted_colors = [ring.color.getRgb() for ring in rings]
    ring_config_colors = [QColor(ring.config.color).getRgb() for ring in rings]
    return converted_colors, ring_config_colors


def test_set_colors_from_colormap_and_change_num_of_bars(ring_progress_bar):
    # Add 2 rings
    ring_progress_bar.add_ring()
    ring_progress_bar.add_ring()
    ring_progress_bar.ring_progress_bar.set_colors_from_map("viridis", "RGB")

    expected_colors = Colors.golden_angle_color("viridis", 2, "RGB")
    converted_colors, ring_config_colors = get_colors_from_rings(ring_progress_bar.rings)

    assert expected_colors == converted_colors
    assert ring_config_colors == expected_colors

    # increase the number of bars to 6
    for _ in range(4):
        ring_progress_bar.add_ring()
    ring_progress_bar.ring_progress_bar.set_colors_from_map("viridis", "RGB")
    expected_colors = Colors.golden_angle_color("viridis", 6, "RGB")
    converted_colors, ring_config_colors = get_colors_from_rings(ring_progress_bar.rings)

    assert expected_colors == converted_colors
    assert ring_config_colors == expected_colors

    # decrease the number of bars to 3
    for _ in range(3):
        ring_progress_bar.remove_ring()
    ring_progress_bar.ring_progress_bar.set_colors_from_map("viridis", "RGB")
    expected_colors = Colors.golden_angle_color("viridis", 3, "RGB")
    converted_colors, ring_config_colors = get_colors_from_rings(ring_progress_bar.rings)

    assert expected_colors == converted_colors
    assert ring_config_colors == expected_colors


def test_set_colors_directly(ring_progress_bar):
    # Add 3 rings
    for _ in range(3):
        ring_progress_bar.add_ring()

    # setting as a list of rgb tuples
    colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
    ring_progress_bar.ring_progress_bar.set_colors_directly(colors)
    converted_colors = get_colors_from_rings(ring_progress_bar.rings)[0]

    assert colors == converted_colors

    ring_progress_bar.ring_progress_bar.set_colors_directly((255, 0, 0, 255), 1)
    converted_colors = get_colors_from_rings(ring_progress_bar.rings)[0]

    assert converted_colors == [(255, 0, 0, 255), (255, 0, 0, 255), (0, 0, 255, 255)]


def test_set_line_width(ring_progress_bar):
    # Add 3 rings
    for _ in range(3):
        ring_progress_bar.add_ring()

    # Set line width for all rings
    for ring in ring_progress_bar.rings:
        ring.set_line_width(5)
    line_widths = [ring.config.line_width for ring in ring_progress_bar.rings]

    assert line_widths == [5, 5, 5]

    # Set individual line widths
    for i, ring in enumerate(ring_progress_bar.rings):
        ring.set_line_width([10, 20, 30][i])
    line_widths = [ring.config.line_width for ring in ring_progress_bar.rings]

    assert line_widths == [10, 20, 30]

    # Set line width for ring at index 1
    ring_progress_bar.rings[1].set_line_width(15)
    line_widths = [ring.config.line_width for ring in ring_progress_bar.rings]

    assert line_widths == [10, 15, 30]


def test_set_gap(ring_progress_bar):
    ring_progress_bar.add_ring()
    ring_progress_bar.set_gap(20)

    assert ring_progress_bar.ring_progress_bar.gap == 20 == ring_progress_bar.gap


def test_remove_ring_by_index(ring_progress_bar):
    # Add 5 rings
    for _ in range(5):
        ring_progress_bar.add_ring()

    assert ring_progress_bar.ring_progress_bar.num_bars == 5

    # Store the ring at index 2 before removal
    ring_at_3 = ring_progress_bar.rings[3]

    # Remove ring at index 2 (middle ring)
    ring_progress_bar.remove_ring(index=2)

    assert ring_progress_bar.ring_progress_bar.num_bars == 4
    # Ring that was at index 3 is now at index 2
    assert ring_progress_bar.rings[2] == ring_at_3


def test_remove_ring_updates_gaps(ring_progress_bar):
    # Add 3 rings with default gap
    for _ in range(3):
        ring_progress_bar.add_ring()

    initial_gap = ring_progress_bar.gap
    # Gaps should be: 0, gap, 2*gap
    expected_gaps = [0, initial_gap, 2 * initial_gap]
    actual_gaps = [ring.gap for ring in ring_progress_bar.rings]
    assert actual_gaps == expected_gaps

    # Remove middle ring
    ring_progress_bar.remove_ring(index=1)

    # Gaps should now be: 0, gap (for the remaining 2 rings)
    expected_gaps = [0, initial_gap]
    actual_gaps = [ring.gap for ring in ring_progress_bar.rings]
    assert actual_gaps == expected_gaps


def test_center_label_property(ring_progress_bar):
    test_text = "Test Label"
    ring_progress_bar.center_label = test_text

    assert ring_progress_bar.center_label == test_text
    assert ring_progress_bar.ring_progress_bar.center_label.text() == test_text


def test_color_map_property(ring_progress_bar):
    # Add some rings
    for _ in range(3):
        ring_progress_bar.add_ring()

    # Set colormap via property
    ring_progress_bar.color_map = "plasma"

    assert ring_progress_bar.color_map == "plasma"
    assert ring_progress_bar.ring_progress_bar.color_map == "plasma"

    # Verify colors were applied
    expected_colors = Colors.golden_angle_color("plasma", 3, "RGB")
    actual_colors = [ring.color.getRgb() for ring in ring_progress_bar.rings]
    assert actual_colors == expected_colors


def test_color_map_property_invalid_colormap(ring_progress_bar):
    # Make sure that invalid colormaps do not crash the application
    ring_progress_bar.color_map = "plasma"
    ring_progress_bar.color_map = "invalid_colormap_name"

    assert ring_progress_bar.color_map == "plasma"  # Should remain unchanged


def test_ring_json_serialization(ring_progress_bar):
    # Add rings with specific configurations
    ring_progress_bar.add_ring()
    ring_progress_bar.add_ring()
    ring_progress_bar.add_ring()

    # Configure rings
    ring_progress_bar.rings[0].set_value(25)
    ring_progress_bar.rings[0].set_color((255, 0, 0, 255))
    ring_progress_bar.rings[1].set_value(50)
    ring_progress_bar.rings[1].set_line_width(15)
    ring_progress_bar.rings[2].set_value(75)
    ring_progress_bar.rings[2].set_precision(4)

    # Get JSON
    json_str = ring_progress_bar.ring_json

    # Verify it's valid JSON
    ring_configs = json.loads(json_str)
    assert isinstance(ring_configs, list)
    assert len(ring_configs) == 3

    # Check some values
    assert ring_configs[0]["value"] == 25
    assert ring_configs[1]["value"] == 50
    assert ring_configs[1]["line_width"] == 15
    assert ring_configs[2]["precision"] == 4


def test_ring_json_deserialization(ring_progress_bar):
    # Create JSON config
    ring_configs = [
        {"value": 10, "color": (100, 150, 200, 255), "line_width": 8},
        {"value": 20, "precision": 2, "min_value": 0, "max_value": 50},
        {"value": 30, "direction": 1},
    ]
    json_str = json.dumps(ring_configs)

    # Load via property
    ring_progress_bar.ring_json = json_str

    # Verify rings were created
    assert len(ring_progress_bar.rings) == 3

    # Verify configurations
    assert ring_progress_bar.rings[0].config.value == 10
    assert ring_progress_bar.rings[0].config.line_width == 8
    assert ring_progress_bar.rings[1].config.precision == 2
    assert ring_progress_bar.rings[1].config.max_value == 50
    assert ring_progress_bar.rings[2].config.direction == 1


def test_ring_json_replaces_existing_rings(ring_progress_bar):
    # Add some initial rings
    for _ in range(5):
        ring_progress_bar.add_ring()

    assert len(ring_progress_bar.rings) == 5

    # Load new config with only 2 rings
    ring_configs = [{"value": 10}, {"value": 20}]
    ring_progress_bar.ring_json = json.dumps(ring_configs)

    # Should have replaced all rings
    assert len(ring_progress_bar.rings) == 2
    assert ring_progress_bar.rings[0].config.value == 10
    assert ring_progress_bar.rings[1].config.value == 20


def test_add_ring_with_config(ring_progress_bar):
    config = {
        "value": 42,
        "color": (128, 64, 192, 255),
        "line_width": 12,
        "precision": 1,
        "min_value": 0,
        "max_value": 100,
    }
    ring_progress_bar.color_map = ""
    ring_progress_bar.add_ring(config=config)

    assert len(ring_progress_bar.rings) == 1
    ring = ring_progress_bar.rings[0]

    assert ring.config.value == 42
    assert ring.config.line_width == 12
    assert ring.config.precision == 1
    assert ring.config.max_value == 100
    assert ring.config.color == "#8040c0"  # Hex representation of (128, 64, 192)


def test_set_colors_directly_single_color_extends_to_all(ring_progress_bar):
    # Add 4 rings
    for _ in range(4):
        ring_progress_bar.add_ring()

    # Set a single color, should extend to all rings
    single_color = (200, 100, 50, 255)
    ring_progress_bar.ring_progress_bar.set_colors_directly(single_color)

    colors = [ring.color.getRgb() for ring in ring_progress_bar.rings]
    assert all(color == single_color for color in colors)


def test_set_colors_directly_list_too_short(ring_progress_bar):
    # Add 5 rings
    for _ in range(5):
        ring_progress_bar.add_ring()

    # Provide only 2 colors
    colors = [(255, 0, 0, 255), (0, 255, 0, 255)]
    ring_progress_bar.ring_progress_bar.set_colors_directly(colors)

    # Last color should be extended to remaining rings
    actual_colors = [ring.color.getRgb() for ring in ring_progress_bar.rings]
    assert actual_colors[0] == (255, 0, 0, 255)
    assert actual_colors[1] == (0, 255, 0, 255)
    assert all(color == (0, 255, 0, 255) for color in actual_colors[2:])


def test_gap_affects_ring_positioning(ring_progress_bar):
    # Add 3 rings
    for _ in range(3):
        ring_progress_bar.add_ring()

    initial_gap = ring_progress_bar.gap

    # Change gap
    new_gap = 30
    ring_progress_bar.set_gap(new_gap)

    # Verify gaps are updated but update method is needed for visual changes
    assert ring_progress_bar.gap == new_gap


def test_clear_all_rings(ring_progress_bar):
    # Add multiple rings
    for _ in range(5):
        ring_progress_bar.add_ring()

    assert len(ring_progress_bar.rings) == 5

    # Clear all
    ring_progress_bar.ring_progress_bar.clear_all()

    assert len(ring_progress_bar.rings) == 0
    assert ring_progress_bar.ring_progress_bar.num_bars == 0


def test_rings_property_returns_correct_list(ring_progress_bar):
    # Add some rings
    for _ in range(3):
        ring_progress_bar.add_ring()

    rings_via_property = ring_progress_bar.rings
    rings_direct = ring_progress_bar.ring_progress_bar.rings

    # Should return the same list
    assert rings_via_property is rings_direct
    assert len(rings_via_property) == 3


###################################
# Hover behavior tests
###################################


@pytest.fixture
def container(qtbot):
    widget = RingProgressContainerWidget()
    qtbot.addWidget(widget)
    widget.resize(200, 200)
    yield widget


def _ring_center_pos(container):
    """Return (center_x, center_y, base_radius) for a square container."""
    size = min(container.width(), container.height())
    center_x = container.width() / 2
    center_y = container.height() / 2
    max_ring_size = container.get_max_ring_size()
    base_radius = (size - 2 * max_ring_size) / 2
    return center_x, center_y, base_radius


def test_ring_at_pos_no_rings(container):
    assert container._ring_at_pos(QPointF(100, 100)) is None


def test_ring_at_pos_center_is_inside_rings(container):
    """The center of the widget is inside all rings; _ring_at_pos should return None."""
    container.add_ring()
    assert container._ring_at_pos(QPointF(100, 100)) is None


def test_ring_at_pos_on_single_ring(container):
    """A point on the ring arc should resolve to that ring."""
    ring = container.add_ring()
    cx, cy, base_radius = _ring_center_pos(container)
    # Point exactly on the ring centreline
    pos = QPointF(cx + base_radius, cy)
    assert container._ring_at_pos(pos) is ring


def test_ring_at_pos_outside_all_rings(container):
    """A point well outside the outermost ring returns None."""
    container.add_ring()
    cx, cy, base_radius = _ring_center_pos(container)
    line_width = container.rings[0].config.line_width
    # Place point clearly beyond the outer edge
    pos = QPointF(cx + base_radius + line_width + 5, cy)
    assert container._ring_at_pos(pos) is None


def test_ring_at_pos_selects_correct_ring_from_multiple(qtbot):
    """With multiple rings, each position resolves to the right ring."""
    container = RingProgressContainerWidget()
    qtbot.addWidget(container)
    container.resize(300, 300)

    ring0 = container.add_ring()
    ring1 = container.add_ring()

    size = min(container.width(), container.height())
    cx = container.width() / 2
    cy = container.height() / 2
    max_ring_size = container.get_max_ring_size()
    base_radius = (size - 2 * max_ring_size) / 2

    radius0 = base_radius - ring0.gap
    radius1 = base_radius - ring1.gap

    assert container._ring_at_pos(QPointF(cx + radius0, cy)) is ring0
    assert container._ring_at_pos(QPointF(cx + radius1, cy)) is ring1


def test_set_hovered_ring_sets_flag(container):
    """_set_hovered_ring marks the ring as hovered and updates _hovered_ring."""
    ring = container.add_ring()
    assert container._hovered_ring is None
    container._set_hovered_ring(ring)
    assert container._hovered_ring is ring
    assert ring._hovered is True


def test_set_hovered_ring_to_none_clears_flag(container):
    """Calling _set_hovered_ring(None) un-hovers the current ring."""
    ring = container.add_ring()
    container._set_hovered_ring(ring)
    container._set_hovered_ring(None)
    assert container._hovered_ring is None
    assert ring._hovered is False


def test_set_hovered_ring_switches_between_rings(qtbot):
    """Switching hover from one ring to another correctly updates both flags."""
    container = RingProgressContainerWidget()
    qtbot.addWidget(container)
    ring0 = container.add_ring()
    ring1 = container.add_ring()

    container._set_hovered_ring(ring0)
    assert ring0._hovered is True
    assert ring1._hovered is False

    container._set_hovered_ring(ring1)
    assert ring0._hovered is False
    assert ring1._hovered is True
    assert container._hovered_ring is ring1


def test_build_tooltip_text_manual_mode(container):
    """Manual mode tooltip contains mode label, value, max and percentage."""
    ring = container.add_ring()
    ring.set_value(50)
    ring.set_min_max_values(0, 100)

    text = RingProgressContainerWidget._build_tooltip_text(ring)
    assert "Manual" in text
    assert "50.0%" in text
    assert "100" in text


def test_build_tooltip_text_scan_mode(container):
    """Scan mode tooltip labels the mode as 'Scan progress'."""
    ring = container.add_ring()
    ring.config.mode = "scan"
    ring.set_value(25)

    text = RingProgressContainerWidget._build_tooltip_text(ring)
    assert "Scan progress" in text


def test_build_tooltip_text_device_mode_with_signal(container):
    """Device mode tooltip shows device:signal when both are set."""
    ring = container.add_ring()
    ring.config.mode = "device"
    ring.config.device = "samx"
    ring.config.signal = "readback"
    ring.set_value(10)

    text = RingProgressContainerWidget._build_tooltip_text(ring)
    assert "Device" in text
    assert "samx:readback" in text


def test_build_tooltip_text_device_mode_without_signal(container):
    """Device mode tooltip shows only device name when signal is absent."""
    ring = container.add_ring()
    ring.config.mode = "device"
    ring.config.device = "samy"
    ring.config.signal = None
    ring.set_value(10)

    text = RingProgressContainerWidget._build_tooltip_text(ring)
    assert "samy" in text
    assert ":" not in text.split("Device:")[-1].split("\n")[0]


def test_build_tooltip_text_nonzero_min_shows_range(container):
    """Tooltip includes Range line when min_value is not 0."""
    ring = container.add_ring()
    ring.set_min_max_values(10, 90)
    ring.set_value(50)

    text = RingProgressContainerWidget._build_tooltip_text(ring)
    assert "Range" in text


def test_build_tooltip_text_zero_min_no_range(container):
    """Tooltip omits Range line when min_value is 0."""
    ring = container.add_ring()
    ring.set_min_max_values(0, 100)
    ring.set_value(50)

    text = RingProgressContainerWidget._build_tooltip_text(ring)
    assert "Range" not in text


def test_refresh_hover_tooltip_updates_label_on_value_change(container):
    """refresh_hover_tooltip updates the label text after the ring value changes."""
    ring = container.add_ring()
    ring.set_value(30)
    container._hovered_ring = ring
    container._last_hover_global_pos = QPoint(100, 100)

    container.refresh_hover_tooltip(ring)
    text_before = container._hover_tooltip_label.text()

    ring.set_value(70)
    container.refresh_hover_tooltip(ring)
    text_after = container._hover_tooltip_label.text()

    assert text_before != text_after
    assert "70" in text_after


def test_refresh_hover_tooltip_no_pos_does_not_crash(container):
    """refresh_hover_tooltip with no stored position should return without raising."""
    ring = container.add_ring()
    container._last_hover_global_pos = None
    # Should not raise
    container.refresh_hover_tooltip(ring)
