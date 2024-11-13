import pytest
from pyqtgraph.widgets.ColorMapButton import ColorMapButton

from bec_widgets.widgets.utility.visual.colormap_widget.colormap_widget import BECColorMapWidget


@pytest.fixture
def color_map_widget(qtbot):
    widget = BECColorMapWidget()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_color_map_widget_init(color_map_widget):
    """Test that the widget initializes correctly."""
    assert color_map_widget is not None
    assert isinstance(color_map_widget, BECColorMapWidget)
    assert color_map_widget.colormap == "magma"
    assert isinstance(color_map_widget.button, ColorMapButton)
    # Check that the button has the correct initial colormap
    assert color_map_widget.button.colorMap().name == "magma"


def test_color_map_widget_set_valid_colormap(color_map_widget):
    """
    Test setting a valid colormap.
    """
    new_cmap = "viridis"
    color_map_widget.colormap = new_cmap
    assert color_map_widget.colormap == new_cmap
    assert color_map_widget.button.colorMap().name == new_cmap


def test_color_map_widget_set_invalid_colormap(color_map_widget):
    """Test setting an invalid colormap."""
    invalid_cmap = "invalid_colormap_name"
    old_cmap = color_map_widget.colormap
    color_map_widget.colormap = invalid_cmap
    # Since invalid, the colormap should not change
    assert color_map_widget.colormap == old_cmap
    assert color_map_widget.button.colorMap().name == old_cmap


def test_color_map_widget_signal_emitted(color_map_widget, qtbot):
    """Test that the signal is emitted when the colormap changes."""
    new_cmap = "plasma"
    with qtbot.waitSignal(color_map_widget.colormap_changed_signal, timeout=1000) as blocker:
        color_map_widget.colormap = new_cmap
    assert blocker.signal_triggered
    assert blocker.args == [new_cmap]
    assert color_map_widget.colormap == new_cmap


def test_color_map_widget_signal_not_emitted_for_invalid_colormap(color_map_widget, qtbot):
    """Test that the signal is not emitted when an invalid colormap is set."""
    invalid_cmap = "invalid_colormap_name"
    with qtbot.assertNotEmitted(color_map_widget.colormap_changed_signal):
        color_map_widget.colormap = invalid_cmap
    # The colormap should remain unchanged
    assert color_map_widget.colormap == "magma"


def test_color_map_widget_resize(color_map_widget):
    """Test that the widget resizes properly."""
    width, height = 200, 50
    color_map_widget.resize(width, height)
    assert color_map_widget.width() == width
    assert color_map_widget.height() == height
