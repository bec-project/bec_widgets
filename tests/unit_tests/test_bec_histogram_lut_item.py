import numpy as np
import pyqtgraph as pg
import pytest
from qtpy.QtCore import QPoint, QPointF, Qt

from bec_widgets.widgets.plots.image.bec_histogram_lut_item import (
    BECColorBarItem,
    BECHistogramLUTItem,
    RangeDialog,
)


@pytest.fixture
def hist_item(qtbot):
    """A BECHistogramLUTItem living inside a real scene, cleaned up after the test."""
    glw = pg.GraphicsLayoutWidget()
    qtbot.addWidget(glw)
    qtbot.waitExposed(glw)
    item = BECHistogramLUTItem()
    glw.addItem(item, row=0, col=0)
    item.setImageItem(pg.ImageItem(np.arange(100, dtype=float).reshape(10, 10)))
    yield item
    item.cleanup()


def test_menu_actions_present(hist_item):
    labels = [a.text() for a in hist_item._bec_menu.actions() if a.text()]
    assert labels == [
        "Colormap",
        "Select colormap",
        "Image scaling (levels)",
        "Set levels…",
        "Autoscale levels",
        "Histogram display range",
        "Set histogram range…",
        "Reset histogram range",
    ]


def _menu_action(hist_item: BECHistogramLUTItem, text: str):
    return next(a for a in hist_item._bec_menu.actions() if a.text() == text)


def test_colormap_submenu_forwards_name(hist_item):
    """Picking a colormap in the submenu re-emits its name on the BEC signal."""
    assert hist_item._colormap_menu.actions()  # the pyqtgraph colormap menu is populated
    received = []
    hist_item.sigColorMapChangeRequested.connect(received.append)
    hist_item._colormap_menu.sigColorMapTriggered.emit(pg.colormap.get("viridis"))
    assert received == ["viridis"]


def test_default_viewbox_menu_bypassed(hist_item):
    """The histogram view shows the BEC menu, not pyqtgraph's default plot menu."""
    vb = hist_item.vb
    assert vb.getMenu(None) is hist_item._bec_menu
    assert vb.getContextMenus(None) == hist_item._bec_menu.actions()
    # The original ViewBoxMenu is kept alive (not replaced) so pyqtgraph internals
    # such as updateViewLists() keep working.
    assert vb.menu.__class__.__name__ == "ViewBoxMenu"
    vb.updateViewLists()  # would raise AttributeError if vb.menu were a plain QMenu


def test_raise_context_menu_pops_bec_menu(hist_item, monkeypatch):
    calls = []
    monkeypatch.setattr(hist_item._bec_menu, "popup", lambda pos: calls.append(pos))

    class _Pos:
        def toPoint(self):
            return QPoint(1, 2)

    class _Event:
        def screenPos(self):
            return _Pos()

    hist_item.vb.raiseContextMenu(_Event())
    assert calls == [QPoint(1, 2)]


def test_set_levels_action_emits_request(hist_item, monkeypatch):
    monkeypatch.setattr(RangeDialog, "get_new_range", staticmethod(lambda *a, **k: (3.0, 9.0)))
    received = []
    hist_item.sigColorLevelsChangeRequested.connect(received.append)
    _menu_action(hist_item, "Set levels…").trigger()
    assert received == [(3.0, 9.0)]


def test_set_levels_action_cancel_emits_nothing(hist_item, monkeypatch):
    monkeypatch.setattr(RangeDialog, "get_new_range", staticmethod(lambda *a, **k: None))
    received = []
    hist_item.sigColorLevelsChangeRequested.connect(received.append)
    _menu_action(hist_item, "Set levels…").trigger()
    assert received == []


def test_autoscale_levels_action_emits_request(hist_item):
    received = []
    hist_item.sigAutoLevelsRequested.connect(lambda: received.append(True))
    _menu_action(hist_item, "Autoscale levels").trigger()
    assert received == [True]


def test_set_histogram_range_action_applies_range(hist_item, monkeypatch):
    monkeypatch.setattr(RangeDialog, "get_new_range", staticmethod(lambda *a, **k: (5.0, 25.0)))
    recorded = []
    monkeypatch.setattr(hist_item, "setHistogramRange", lambda mn, mx: recorded.append((mn, mx)))
    _menu_action(hist_item, "Set histogram range…").trigger()
    assert recorded == [(5.0, 25.0)]


def test_reset_histogram_range_action_reenables_histogram_autorange(hist_item):
    hist_item.setHistogramRange(5.0, 25.0)
    assert hist_item.vb.autoRangeEnabled()[1] is False

    _menu_action(hist_item, "Reset histogram range").trigger()

    assert hist_item.vb.autoRangeEnabled()[1]


def test_cleanup_restores_viewbox_and_clears_menu(hist_item):
    vb = hist_item.vb
    assert {"getMenu", "getContextMenus", "raiseContextMenu"} <= set(vb.__dict__)
    hist_item.cleanup()
    assert not ({"getMenu", "getContextMenus", "raiseContextMenu"} & set(vb.__dict__))
    assert hist_item._bec_menu is None
    assert hist_item._colormap_menu is None
    # idempotent: cleaning up again (as the fixture teardown will) must not raise
    hist_item.cleanup()


def test_range_dialog_orders_values(qtbot):
    dialog = RangeDialog(None, title="t", label="l", vmin=1.0, vmax=4.0)
    qtbot.addWidget(dialog)
    qtbot.waitExposed(dialog)
    dialog.min_spinbox.setValue(8.0)
    dialog.max_spinbox.setValue(2.0)
    assert dialog.get_range() == (2.0, 8.0)


def test_range_dialog_returns_fractional_values(qtbot):
    """The dialog hands fractional values through unchanged (regression context:
    they used to be truncated later by the QPoint-based tuple conversion)."""
    dialog = RangeDialog(None, title="t", label="l", vmin=0.25, vmax=10.5)
    qtbot.addWidget(dialog)
    qtbot.waitExposed(dialog)
    assert dialog.get_range() == (0.25, 10.5)


def test_colormap_menu_hides_none_entry(hist_item):
    none_actions = [a for a in hist_item._colormap_menu.actions() if a.text() == "None"]
    assert none_actions and not none_actions[0].isVisible()


################################################################################
# BECColorBarItem (simple colorbar)


@pytest.fixture
def color_bar_item(qtbot):
    """A BECColorBarItem attached to an image inside a real scene."""
    glw = pg.GraphicsLayoutWidget()
    qtbot.addWidget(glw)
    qtbot.waitExposed(glw)
    image_item = pg.ImageItem(np.arange(100, dtype=float).reshape(10, 10))
    item = BECColorBarItem()
    item.setImageItem(image_item)
    glw.addItem(item, row=0, col=0)
    yield item
    item.cleanup()


class _FakeRightClick:
    def __init__(self):
        self.accepted = False

    def button(self):
        return Qt.MouseButton.RightButton

    def accept(self):
        self.accepted = True

    def screenPos(self):
        return QPointF(3.0, 4.0)


def test_simple_colorbar_menu_actions_present(color_bar_item):
    labels = [a.text() for a in color_bar_item._bec_menu.actions() if a.text()]
    assert labels == [
        "Colormap",
        "Select colormap",
        "Image scaling (levels)",
        "Set levels…",
        "Autoscale levels",
    ]


def test_simple_colorbar_native_menu_disabled(color_bar_item):
    """pyqtgraph's built-in colormap menu is off; the BEC menu replaces it."""
    assert color_bar_item.colorMapMenu is False


def test_simple_colorbar_right_click_pops_bec_menu(color_bar_item, monkeypatch):
    calls = []
    monkeypatch.setattr(color_bar_item._bec_menu, "popup", lambda pos: calls.append(pos))
    ev = _FakeRightClick()
    color_bar_item.mouseClickEvent(ev)
    assert ev.accepted
    assert calls == [QPoint(3, 4)]


def test_simple_colorbar_set_levels_action_emits_request(color_bar_item, monkeypatch):
    monkeypatch.setattr(RangeDialog, "get_new_range", staticmethod(lambda *a, **k: (3.0, 9.0)))
    received = []
    color_bar_item.sigColorLevelsChangeRequested.connect(received.append)
    action = next(a for a in color_bar_item._bec_menu.actions() if a.text() == "Set levels…")
    action.trigger()
    assert received == [(3.0, 9.0)]


def test_simple_colorbar_autoscale_action_emits_request(color_bar_item):
    received = []
    color_bar_item.sigAutoLevelsRequested.connect(lambda: received.append(True))
    action = next(a for a in color_bar_item._bec_menu.actions() if a.text() == "Autoscale levels")
    action.trigger()
    assert received == [True]


def test_simple_colorbar_colormap_submenu_forwards_name(color_bar_item):
    received = []
    color_bar_item.sigColorMapChangeRequested.connect(received.append)
    color_bar_item._colormap_menu.sigColorMapTriggered.emit(pg.colormap.get("viridis"))
    assert received == ["viridis"]


def test_simple_colorbar_cleanup_idempotent(color_bar_item):
    color_bar_item.cleanup()
    assert color_bar_item._bec_menu is None
    assert color_bar_item._colormap_menu is None
    # idempotent: cleaning up again (as the fixture teardown will) must not raise
    color_bar_item.cleanup()
