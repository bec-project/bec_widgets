import pytest
from qtpy.QtCore import QPoint, Qt
from qtpy.QtWidgets import QHBoxLayout, QLabel, QWidget

from bec_widgets.applications.navigation_centre.nav_common import (
    NAV_PANEL_ENV,
    NavPanelBase,
    create_side_bar,
)
from bec_widgets.applications.navigation_centre.nav_panel_qml import NavPanelQml
from bec_widgets.applications.navigation_centre.nav_panel_qwidget import NavPanelQWidget
from bec_widgets.applications.navigation_centre.side_bar import SideBar
from bec_widgets.utils.colors import apply_theme

ANIM = 40  # ms


@pytest.fixture(params=["qwidget", "qml"])
def panel_window(qtbot, request):
    window = QWidget()
    layout = QHBoxLayout(window)
    layout.setContentsMargins(0, 0, 0, 0)
    cls = NavPanelQWidget if request.param == "qwidget" else NavPanelQml
    panel = cls(parent=window, anim_duration=ANIM, drawer_mode="float")
    content = QLabel("content", window)
    content.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    layout.addWidget(panel)
    layout.addWidget(content, 1)
    panel.add_section("Apps", "apps")
    panel.add_item("widgets", "Dock Area", "dock", mini_text="Docks", subtitle="Plots")
    panel.add_item("display_settings", "Device Manager", "dm", mini_text="Devices")
    panel.add_item("admin_panel_settings", "Admin", "admin", from_top=False)
    panel.add_dark_mode_item()
    panel.activate_item("dock")
    qtbot.addWidget(window)
    window.resize(900, 600)
    window.show()
    qtbot.waitExposed(window)
    yield window, panel, content
    panel.cleanup()


def _settle(qtbot):
    qtbot.wait(ANIM + 120)


def test_entries_order_and_shortcuts(panel_window):
    _, panel, _ = panel_window
    assert [e.id for e in panel.ordered_entries()] == ["apps", "dock", "dm", "admin", "dark_mode"]
    assert [e.id for e in panel.view_entries()] == ["dock", "dm", "admin"]
    assert panel.components["dock"].shortcut.endswith("1")
    assert panel.components["admin"].shortcut.endswith("3")
    assert panel.components["dark_mode"].shortcut == ""


def test_exclusive_and_non_exclusive_selection(panel_window, qtbot):
    _, panel, _ = panel_window
    panel.add_item("widgets", "Extra", "extra", exclusive=False)
    with qtbot.waitSignal(panel.view_selected) as blocker:
        panel.activate_item("dm")
    assert blocker.args == ["dm"]
    assert panel.active_id == "dm"
    assert not panel.components["dock"].active
    panel.activate_item("extra")
    assert panel.components["extra"].active
    assert panel.active_id == "dm"
    panel.activate_item("dock", emit_signal=False)
    assert panel.active_id == "dock"


def test_opening_floats_over_content_without_reflow(panel_window, qtbot):
    _, panel, content = panel_window
    content_width = content.width()
    with qtbot.waitSignal(panel.toggled) as blocker:
        panel.toggle.click()
    assert blocker.args == [True]
    _settle(qtbot)
    assert panel.is_expanded
    assert panel.progress == 1.0
    assert panel.surface.width() == panel.drawer_width
    assert panel.width() == panel.rail_width
    assert content.width() == content_width
    assert panel._scrim.isVisible()


@pytest.mark.parametrize("cls", [NavPanelQWidget, NavPanelQml])
def test_push_mode_reflows_once_and_stays_open(qtbot, cls):
    window = QWidget()
    layout = QHBoxLayout(window)
    layout.setContentsMargins(0, 0, 0, 0)
    panel = cls(parent=window, anim_duration=ANIM, drawer_mode="push")
    content = QLabel("content", window)
    layout.addWidget(panel)
    layout.addWidget(content, 1)
    panel.add_item("widgets", "Dock Area", "dock")
    panel.add_item("display_settings", "Device Manager", "dm")
    qtbot.addWidget(window)
    window.resize(900, 600)
    window.show()
    qtbot.waitExposed(window)
    widths = []
    panel.toggle_expanded()
    for _ in range(4):
        qtbot.wait(ANIM // 4)
        widths.append(panel.width())
    _settle(qtbot)
    # the slot in the layout keeps the rail width while the drawer opens, then makes room once
    assert widths[0] == panel.rail_width
    assert panel.width() == panel.drawer_width and panel.pinned
    assert not panel._scrim.isVisible()
    panel.activate_from_user("dm")
    assert panel.is_expanded
    panel.toggle_expanded()
    assert panel.width() == panel.rail_width
    _settle(qtbot)
    assert not panel.is_expanded and panel.surface.width() == panel.rail_width
    panel.cleanup()


def test_click_on_scrim_closes(panel_window, qtbot):
    _, panel, _ = panel_window
    panel.set_expanded(True)
    _settle(qtbot)
    qtbot.mouseClick(panel._scrim, Qt.MouseButton.LeftButton, pos=QPoint(600, 300))
    _settle(qtbot)
    assert not panel.is_expanded
    assert panel.surface.width() == panel.rail_width
    assert not panel._scrim.isVisible()


def test_choosing_a_view_closes_floating_drawer_but_not_pinned(panel_window, qtbot):
    _, panel, _ = panel_window
    panel.set_expanded(True)
    panel.activate_from_user("dm")
    assert not panel.is_expanded
    panel.set_pinned(True)
    _settle(qtbot)
    assert panel.is_expanded and panel.width() == panel.drawer_width
    assert not panel._scrim.isVisible()
    panel.activate_from_user("dock")
    assert panel.is_expanded
    panel.set_pinned(False)
    _settle(qtbot)
    assert not panel.is_expanded and panel.width() == panel.rail_width


def test_rapid_toggling_ends_in_the_last_state(panel_window, qtbot):
    _, panel, _ = panel_window
    for _ in range(5):
        panel.toggle_expanded()
        qtbot.wait(5)
    _settle(qtbot)
    assert panel.is_expanded
    assert panel.surface.width() == panel.drawer_width
    panel.toggle_expanded()
    _settle(qtbot)
    assert panel.surface.width() == panel.rail_width


def test_keyboard_shortcuts(panel_window, qtbot):
    window, panel, content = panel_window
    window.activateWindow()
    content.setFocus()
    with qtbot.waitSignal(panel.view_selected):
        qtbot.keyClick(window, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
    assert panel.active_id == "dm"
    qtbot.keyClick(window, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
    _settle(qtbot)
    assert panel.is_expanded
    assert panel._surface_has_focus()
    panel.handle_escape()
    _settle(qtbot)
    assert not panel.is_expanded


def test_move_focus_wraps_to_ends(panel_window):
    _, panel, _ = panel_window
    assert panel.move_focus(None, 1) == "dock"
    assert panel.move_focus("dock", 1) == "dm"
    assert panel.move_focus("dm", 1) == "admin"
    assert panel.move_focus("dock", -1) == "dock"
    assert panel.move_focus("dock", 10**6) == "dark_mode"


def test_theme_entry_follows_theme(panel_window, qtbot):
    _, panel, _ = panel_window
    apply_theme("dark")
    qtbot.wait(20)
    assert panel.components["dark_mode"].title == "Light theme"
    apply_theme("light")
    qtbot.wait(20)
    assert panel.components["dark_mode"].title == "Dark theme"
    apply_theme("dark")


def test_qwidget_rows_have_tooltips_and_accessible_names(qtbot):
    panel = NavPanelQWidget(anim_duration=0)
    qtbot.addWidget(panel)
    panel.add_item("widgets", "Dock Area", "dock", subtitle="Plots")
    panel.activate_item("dock")
    row = panel.row_widget("dock")
    assert row.accessibleName() == "Dock Area (current view)"
    assert "Dock Area" in panel.tooltip_for(panel.components["dock"])
    assert "Plots" in panel.tooltip_for(panel.components["dock"])
    panel.cleanup()


@pytest.mark.parametrize(
    "flavour, cls", [("qwidget", NavPanelQWidget), ("qml", NavPanelQml), ("legacy", SideBar)]
)
def test_factory_follows_env(monkeypatch, qtbot, flavour, cls):
    monkeypatch.setenv(NAV_PANEL_ENV, flavour)
    panel = create_side_bar(anim_duration=0, remember_state=True)
    qtbot.addWidget(panel)
    assert isinstance(panel, cls)
    if isinstance(panel, NavPanelBase):
        panel.cleanup()


def test_legacy_section_is_added_above_bottom_items(qtbot):
    sidebar = SideBar(anim_duration=0)
    qtbot.addWidget(sidebar)
    bottom = sidebar.add_item(icon="widgets", title="Bottom", id="bottom", from_top=False)
    section = sidebar.add_section("Late section", id="late")
    spacer = sidebar.content_layout.indexOf(sidebar._bottom_spacer)
    assert sidebar.content_layout.indexOf(section) < spacer
    assert sidebar.content_layout.indexOf(bottom) > spacer
