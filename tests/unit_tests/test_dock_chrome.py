# pylint: disable=missing-function-docstring, missing-module-docstring, redefined-outer-name, protected-access

import pytest
from qtpy.QtCore import Qt

import bec_widgets.widgets.containers.qt_ads as QtAds
from bec_widgets.widgets.containers.dock_area.chrome import DockChrome
from bec_widgets.widgets.containers.dock_area.chrome.catalog import (
    CORE_WIDGETS,
    STARTER_LAYOUTS,
    display_name,
    unique_title,
)
from bec_widgets.widgets.containers.dock_area.chrome.gallery_common import GalleryController
from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea


@pytest.fixture(autouse=True)
def isolate_profile_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("BECWIDGETS_PROFILE_DIR", str(tmp_path / "profiles"))


@pytest.fixture(params=["qwidget"])
def dock_area(request, qtbot, mocked_client, monkeypatch):
    monkeypatch.setenv("BEC_DOCK_CHROME", request.param)
    widget = BECDockArea(client=mocked_client, startup_profile=None)
    qtbot.addWidget(widget)
    widget.resize(1000, 700)
    widget.show()
    qtbot.waitExposed(widget)
    yield widget


def _dock_of(area, widget):
    return area._chrome.dock_of(widget)


# ---------------------------------------------------------------------- catalog


def test_catalog_names_and_titles():
    assert display_name("PositionerBox") == "Motor"
    assert display_name("BECQueue") == "Scan Queue"
    assert display_name("SomePluginWidget") == "Some Plugin Widget"
    assert unique_title("Waveform", set()) == "Waveform"
    assert unique_title("Waveform", {"Waveform"}) == "Waveform 2"
    assert unique_title("Waveform", {"Waveform", "Waveform 2"}) == "Waveform 3"
    assert len({entry.widget_class for entry in CORE_WIDGETS}) == len(CORE_WIDGETS)


def test_gallery_controller_filter_highlight_and_activate(qtbot):
    controller = GalleryController(entries=CORE_WIDGETS)
    assert controller.items.count == len(CORE_WIDGETS)
    controller.set_query("motor")
    names = [item["name"] for item in controller.items.items]
    assert "Motor" in names and "2D Motor" in names and "Scan Queue" not in names
    controller.set_query("device box")  # today's menu label still finds it
    assert [item["name"] for item in controller.items.items] == ["Motor", "2D Motor"]

    controller.set_query("")
    controller.move_highlight(-1)
    assert controller.highlight == controller.items.count - 1
    controller.move_highlight(1)
    assert controller.highlight == 0

    with qtbot.waitSignal(controller.widget_requested) as blocker:
        controller.activate()
    # no anchor yet: relative placements fall back to a new column
    assert blocker.args == ["Waveform", "column"]

    controller.set_anchor_title("Waveform")
    controller.set_placement("tab")
    assert controller.placement_summary() == "As a tab with Waveform"
    with qtbot.waitSignal(controller.widget_requested) as blocker:
        controller.activate(1)
    assert blocker.args == ["ScatterWaveform", "tab"]


# ---------------------------------------------------------------------- behaviour


def test_ads_flags_close_tabs_not_groups(dock_area):
    flag = QtAds.CDockManager.eConfigFlag
    assert not QtAds.CDockManager.testConfigFlag(flag.DockAreaHasCloseButton)
    assert not QtAds.CDockManager.testConfigFlag(flag.DoubleClickUndocksWidget)
    assert QtAds.CDockManager.testConfigFlag(flag.AllTabsHaveCloseButton)


def test_human_titles_numbered(dock_area):
    first = dock_area.new("Waveform")
    second = dock_area.new("Waveform")
    motor = dock_area.new("PositionerBox")
    assert _dock_of(dock_area, first).windowTitle() == "Waveform"
    assert _dock_of(dock_area, second).windowTitle() == "Waveform 2"
    assert _dock_of(dock_area, motor).windowTitle() == "Motor"
    # object names (the API) are unchanged
    assert motor.objectName().startswith("PositionerBox")


def test_close_hides_and_undo_restores(dock_area, qtbot):
    widget = dock_area.new("Waveform")
    dock = _dock_of(dock_area, widget)
    name = dock.objectName()

    dock.closeRequested.emit()
    qtbot.wait(10)
    assert dock.isClosed()
    assert name not in dock_area.dock_map()
    assert dock_area._chrome.undo_bar.isVisible()
    assert "Waveform" in dock_area._chrome.undo_bar.label.text()

    dock_area._chrome.undo_close()
    assert not dock.isClosed()
    assert name in dock_area.dock_map()
    assert not dock_area._chrome.undo_bar.isVisible()


def test_close_is_final_after_flush(dock_area, qtbot):
    widget = dock_area.new("Waveform")
    dock = _dock_of(dock_area, widget)
    dock.closeRequested.emit()
    dock_area._chrome.pending.flush()
    qtbot.waitUntil(lambda: dock_area.dock_manager.dockWidgetsMap() == {})


def test_closing_several_at_once_undoes_together(dock_area, qtbot):
    a = _dock_of(dock_area, dock_area.new("Waveform"))
    b = _dock_of(dock_area, dock_area.new("Image"))
    a.closeRequested.emit()
    b.closeRequested.emit()
    assert "2 widgets" in dock_area._chrome.undo_bar.label.text()
    dock_area._chrome.undo_close()
    assert not a.isClosed() and not b.isClosed()


def test_delete_all_flushes_pending(dock_area, qtbot):
    dock = _dock_of(dock_area, dock_area.new("Waveform"))
    dock.closeRequested.emit()
    dock_area.delete_all()
    assert len(dock_area._chrome.pending) == 0
    qtbot.waitUntil(lambda: dock_area.dock_manager.dockWidgetsMap() == {})


def test_rename_is_saved_with_the_profile(dock_area, qtbot):
    widget = dock_area.new("Waveform")
    dock = _dock_of(dock_area, widget)
    dock_area._chrome.rename_dock(dock, "Beam profile")
    assert dock.windowTitle() == "Beam profile"

    dock_area.save_profile("titles", show_dialog=False)
    dock_area.delete_all()
    dock_area.load_profile("titles")
    restored = list(dock_area.dock_map().values())
    assert [d.windowTitle() for d in restored] == ["Beam profile"]
    assert restored[0]._custom_title


def test_inline_rename_editor(dock_area, qtbot):
    dock = _dock_of(dock_area, dock_area.new("Waveform"))
    editor = dock_area._chrome.renamer.start_rename(dock)
    assert editor is not None
    editor.setText("  Diode scan ")
    editor.commit()
    assert dock.windowTitle() == "Diode scan"


def test_rename_blocked_when_locked(dock_area):
    dock = _dock_of(dock_area, dock_area.new("Waveform"))
    dock_area.lock_button.setChecked(True)
    assert dock_area.workspace_is_locked
    assert not dock_area.add_widget_button.isEnabled()
    assert dock_area.lock_button.text() == "Layout locked"
    assert dock_area._chrome.renamer.start_rename(dock) is None
    dock_area.lock_button.setChecked(False)
    assert not dock_area.workspace_is_locked


@pytest.mark.parametrize("placement", ["beside", "below", "tab", "floating", "column"])
def test_add_widget_placement(dock_area, placement):
    anchor = _dock_of(dock_area, dock_area.new("Waveform"))
    dock_area.dock_manager.setDockWidgetFocused(anchor)
    widget = dock_area._chrome.add_widget("Image", placement)
    dock = _dock_of(dock_area, widget)
    assert dock is not None
    same_area = dock.dockAreaWidget() is anchor.dockAreaWidget()
    if placement == "tab":
        assert same_area
    elif placement == "floating":
        assert dock.isFloating()
    else:
        assert not same_area and not dock.isFloating()


def test_empty_state_and_starter_layout(dock_area, qtbot):
    chrome: DockChrome = dock_area._chrome
    qtbot.waitUntil(chrome.empty_state.isVisible)
    chrome.controller.activate_layout("Monitoring")
    layout = next(item for item in STARTER_LAYOUTS if item.name == "Monitoring")
    assert len(dock_area.dock_list()) == len(layout.steps)
    assert not chrome.empty_state.isVisible()
    dock_area.delete_all()
    qtbot.waitUntil(chrome.empty_state.isVisible)


def test_toolbar_has_one_add_button(dock_area):
    shown = dock_area.toolbar.shown_bundles
    assert shown[0] == "add_widget"
    assert "menu_plots" not in shown and "menu_utils" not in shown


def test_qwidget_gallery_keyboard(dock_area, qtbot):
    dock_area.open_widget_gallery()
    gallery = dock_area._chrome.gallery
    qtbot.waitUntil(gallery.isVisible)
    gallery.search.setText("queue")
    qtbot.keyClick(gallery.search, Qt.Key.Key_Return)
    assert [d.windowTitle() for d in dock_area.dock_list()] == ["Scan Queue"]
    assert not gallery.isVisible()


def test_qml_chrome_loads(qtbot, mocked_client, monkeypatch):
    monkeypatch.setenv("BEC_DOCK_CHROME", "qml")
    area = BECDockArea(client=mocked_client, startup_profile=None)
    qtbot.addWidget(area)
    area.show()
    qtbot.waitExposed(area)
    chrome = area._chrome
    assert chrome.empty_state.view.rootObject() is not None
    assert not chrome.empty_state.view.errors()
    area.open_widget_gallery()
    assert chrome.gallery.view.rootObject() is not None
    assert not chrome.gallery.view.errors()
    chrome.controller.set_query("heat")
    chrome.controller.activate()
    assert [d.windowTitle() for d in area.dock_list()] == ["Heatmap"]


def test_legacy_mode_keeps_old_chrome(qtbot, mocked_client, monkeypatch):
    monkeypatch.setenv("BEC_DOCK_CHROME", "legacy")
    area = BECDockArea(client=mocked_client, startup_profile=None)
    qtbot.addWidget(area)
    assert area._chrome is None
    assert "menu_plots" in area.toolbar.shown_bundles
    flag = QtAds.CDockManager.eConfigFlag
    assert QtAds.CDockManager.testConfigFlag(flag.DockAreaHasCloseButton)
    widget = area.new("Waveform")
    assert area.dock_list()[0].windowTitle() == widget.objectName()
