import pyqtgraph as pg
import pytest

from bec_widgets.widgets.color_map_selector.color_map_selector import ColormapSelector


@pytest.fixture
def color_map_selector(qtbot):
    widget = ColormapSelector()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


def test_color_map_selector_init(color_map_selector):
    assert color_map_selector is not None
    assert isinstance(color_map_selector, ColormapSelector)

    all_maps = pg.colormap.listMaps()
    loaded_maps = [
        color_map_selector.combo.itemText(i) for i in range(color_map_selector.combo.count())
    ]
    assert len(loaded_maps) > 0
    assert all_maps == loaded_maps


def test_color_map_selector_add_color_maps(color_map_selector):
    color_map_selector.add_color_maps(["cividis", "viridis"])
    assert color_map_selector.combo.count() == 2
    assert color_map_selector.combo.itemText(0) == "cividis"
    assert color_map_selector.combo.itemText(1) == "viridis"
    assert color_map_selector.combo.itemText(2) != "cividis"
    assert color_map_selector.combo.itemText(2) != "viridis"


def test_colormap_add_maps_by_property(color_map_selector):
    color_map_selector.colormaps = ["cividis", "viridis"]
    assert color_map_selector.combo.count() == 2
    assert color_map_selector.combo.itemText(0) == "cividis"
    assert color_map_selector.combo.itemText(1) == "viridis"
    assert color_map_selector.combo.itemText(2) != "cividis"
    assert color_map_selector.combo.itemText(2) != "viridis"
