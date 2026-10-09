from unittest import mock

import pytest
from qtpy.QtCore import QPoint, Qt
from qtpy.QtWidgets import QMainWindow, QWidget

from bec_widgets.applications.main_app import BECMainApp
from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.widgets.utility.command_palette.command_palette import (
    CommandPalette,
    default_flavour,
)
from bec_widgets.widgets.utility.command_palette.palette_core import (
    CommandPaletteController,
    PaletteCommand,
    fuzzy_match,
    rich_title,
)


def _commands(calls: list | None = None):
    calls = calls if calls is not None else []

    def cmd(uid, title, category, **kwargs):
        return PaletteCommand(
            uid=uid, title=title, category=category, callback=lambda: calls.append(uid), **kwargs
        )

    return [
        cmd("view:docks", "Go to Dock Area", "navigate"),
        cmd("app:theme", "Switch to Light Theme", "actions", keywords="appearance"),
        cmd("widget:Waveform", "Waveform", "widgets"),
        cmd("widget:MultiWaveform", "Multi Waveform", "widgets"),
        cmd("widget:ScanControl", "Scan Control", "widgets"),
        cmd("device:samx", "samx", "devices", subtitle="SimPositioner"),
        cmd("device:bpm4i", "bpm4i", "devices", subtitle="SimMonitor"),
        cmd("workspace:alignment", "alignment", "workspaces"),
    ]


@pytest.fixture
def controller(qtbot):
    calls = []
    ctrl = CommandPaletteController([lambda: _commands(calls)])
    ctrl.calls = calls
    ctrl.refresh()
    yield ctrl
    ctrl.deleteLater()


# ---------------------------------------------------------------- matching


def test_fuzzy_match_prefers_substring_and_word_starts():
    exact = fuzzy_match("wave", "Waveform")
    inner = fuzzy_match("wave", "Multi Waveform")
    scattered = fuzzy_match("wf", "Waveform")
    assert exact[1] == [0, 1, 2, 3]
    assert inner[1] == [6, 7, 8, 9]
    assert exact[0] > inner[0] > scattered[0]
    assert fuzzy_match("sc", "Scan Control")[1] == [0, 1]
    assert fuzzy_match("scc", "Scan Control")[1] == [0, 1, 5]
    assert fuzzy_match("zz", "Waveform") is None
    assert fuzzy_match("", "anything") == (0.0, [])


def test_rich_title_highlights_and_escapes():
    text = rich_title("a<b", [0, 2], "#ff0000")
    assert text == (
        '<b><font color="#ff0000">a</font></b>&lt;<b><font color="#ff0000">b</font></b>'
    )
    assert rich_title("plain", [], "#000") == "plain"


# ---------------------------------------------------------------- controller


def test_empty_query_groups_by_category(controller):
    sections = [row["section"] for row in controller.model.items]
    assert sections[0] == "Go to"
    assert "Widgets" in sections and "Devices" in sections and "Workspaces" in sections
    assert controller.sectioned
    assert controller.currentIndex == 0


def test_query_ranks_best_match_first(controller):
    controller.set_query("wave")
    titles = [cmd.title for cmd in controller.results]
    assert titles[:2] == ["Waveform", "Multi Waveform"]
    assert not controller.sectioned
    assert controller.model.items[0]["positions"] == [0, 1, 2, 3]


def test_multi_token_and_keyword_search(controller):
    controller.set_query("multi wave")
    assert [cmd.uid for cmd in controller.results] == ["widget:MultiWaveform"]
    controller.set_query("appearance")
    assert [cmd.uid for cmd in controller.results] == ["app:theme"]


@pytest.mark.parametrize(
    "text, scope, uids",
    [
        ("@sam", "devices", ["device:samx"]),
        ("+scan", "widgets", ["widget:ScanControl"]),
        ("#", "workspaces", ["workspace:alignment"]),
        (">dock", "actions", ["view:docks"]),
    ],
)
def test_prefix_selects_scope(controller, text, scope, uids):
    controller.set_query(text)
    assert controller.scope == scope
    assert [cmd.uid for cmd in controller.results] == uids


def test_scope_cycling_and_clearing(controller):
    controller.cycle_scope(1)
    assert controller.scope == "actions"
    assert {cmd.category for cmd in controller.results} == {"navigate", "actions"}
    controller.cycle_scope(-1)
    controller.cycle_scope(-1)
    assert controller.scope == "workspaces"
    controller.clear_scope()
    assert controller.scope == "all"


def test_move_wraps_and_page_clamps(controller):
    controller.set_query("wave")
    assert controller.resultCount == 2
    controller.move(1)
    assert controller.currentIndex == 1
    controller.move(1)
    assert controller.currentIndex == 0
    controller.move(-1)
    assert controller.currentIndex == 1
    controller.move_page(-8)
    assert controller.currentIndex == 0


def test_empty_text(controller):
    controller.set_query("@xyzzy")
    assert controller.resultCount == 0
    assert controller.currentIndex == -1
    assert controller.empty_text() == "No matches for “xyzzy” in devices"


def test_execute_runs_command_and_remembers_it(qtbot, controller):
    accepted = []
    controller.accepted.connect(accepted.append)
    controller.set_query("bpm")
    controller.execute()
    assert accepted == ["device:bpm4i"]
    qtbot.waitUntil(lambda: controller.calls == ["device:bpm4i"], timeout=1000)

    controller.reset()
    controller.refresh()
    first = controller.model.items[0]
    assert (first["uid"], first["section"]) == ("device:bpm4i", "Recent")

    # recently used commands win ties
    controller.set_query("s")
    assert controller.results[0].uid != "device:bpm4i"
    controller.execute(-1)
    controller.set_query("b")
    assert controller.results[0].uid == "device:bpm4i"


def test_failing_source_is_skipped(qtbot):
    def broken():
        raise RuntimeError("boom")

    ctrl = CommandPaletteController([broken, lambda: _commands()])
    ctrl.refresh()
    assert len(ctrl.commands) == len(_commands())
    ctrl.deleteLater()


def test_default_flavour(monkeypatch):
    monkeypatch.delenv("BEC_COMMAND_PALETTE", raising=False)
    assert default_flavour() == "qwidget"
    monkeypatch.setenv("BEC_COMMAND_PALETTE", "QML")
    assert default_flavour() == "qml"


# ---------------------------------------------------------------- overlay, both renderers


@pytest.fixture(params=["qwidget", "qml"])
def palette_window(qtbot, request):
    window = QMainWindow()
    window.setCentralWidget(QWidget())
    window.resize(900, 640)
    calls = []
    palette = CommandPalette(window, sources=[lambda: _commands(calls)], flavour=request.param)
    palette.install_shortcuts()
    palette.calls = calls
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    yield window, palette
    palette.cleanup()


def _type(qtbot, palette, text):
    if palette.flavour == "qml":
        palette.card.view.setFocus()
        qtbot.keyClicks(palette.card.view, text)
    else:
        qtbot.keyClicks(palette.card.input, text)


def _key(qtbot, palette, key):
    target = palette.card.view if palette.flavour == "qml" else palette.card.input
    qtbot.keyClick(target, key)


def test_overlay_opens_with_shortcut_and_runs_command(qtbot, palette_window):
    window, palette = palette_window
    window.activateWindow()
    window.centralWidget().setFocus()
    palette.toggle()
    assert palette.is_open()
    assert palette.geometry() == window.rect()
    card = palette.card_geometry()
    assert card.width() == 640 and card.top() >= 24

    _type(qtbot, palette, "wave")
    qtbot.waitUntil(lambda: palette.controller.query == "wave", timeout=2000)
    _key(qtbot, palette, Qt.Key.Key_Down)
    assert palette.controller.currentIndex == 1
    _key(qtbot, palette, Qt.Key.Key_Return)
    assert not palette.is_open()
    qtbot.waitUntil(lambda: palette.calls == ["widget:MultiWaveform"], timeout=1000)


def test_overlay_tab_and_escape(qtbot, palette_window):
    _window, palette = palette_window
    palette.open_palette()
    _key(qtbot, palette, Qt.Key.Key_Tab)
    assert palette.controller.scope == "actions"
    _key(qtbot, palette, Qt.Key.Key_Backspace)
    assert palette.controller.scope == "all"
    _key(qtbot, palette, Qt.Key.Key_Escape)
    assert not palette.is_open()


def test_overlay_click_outside_closes(qtbot, palette_window):
    _window, palette = palette_window
    palette.open_palette("@")
    assert palette.controller.scope == "devices"
    qtbot.mouseClick(palette, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
    assert not palette.is_open()
    # reopening starts fresh
    palette.open_palette()
    assert palette.controller.scope == "all" and palette.controller.query == ""


def test_qwidget_card_follows_controller(qtbot, palette_window):
    _window, palette = palette_window
    if palette.flavour != "qwidget":
        pytest.skip("QWidget card only")
    palette.open_palette()
    card = palette.card
    palette.controller.set_query(">")
    assert card.input.text() == ""
    assert [c.isChecked() for c in card.chips.buttons()][1]
    palette.controller.set_query("nothing-matches")
    assert card.stack.currentWidget() is card.empty
    assert "nothing-matches" in card.empty_title.text()
    assert card.count_label.text() == ""


def test_qml_card_loads(qtbot, palette_window):
    _window, palette = palette_window
    if palette.flavour != "qml":
        pytest.skip("QML card only")
    palette.open_palette()
    assert palette.card.view.errors() == []
    assert palette.card.view.rootObject() is not None


# ---------------------------------------------------------------- main app integration


@pytest.fixture
def main_app(qtbot, mocked_client):
    app = BECMainApp(client=mocked_client, anim_duration=1, show_examples=False)
    qtbot.addWidget(app)
    app.show()
    qtbot.waitExposed(app)
    yield app


def _by_uid(app):
    app.command_palette.controller.refresh()
    return {cmd.uid: cmd for cmd in app.command_palette.controller.commands}


def test_main_app_palette_menu_entry(main_app):
    action = main_app._command_palette_action
    assert [s.toString() for s in action.shortcuts()] == ["Ctrl+K", "Ctrl+Shift+P"]
    view_action = next(a for a in main_app.menuBar().actions() if a.text() == "View")
    assert action in view_action.menu().actions()
    action.trigger()
    assert main_app.command_palette.is_open()


def test_main_app_commands(main_app):
    commands = _by_uid(main_app)
    assert "view:DM" in commands
    assert "widget:Waveform" in commands and "widget:ScanControl" in commands
    assert "device:samx" in commands and commands["device:samx"].hint == "Move"
    assert commands["device:bpm4i"].hint == "Plot"
    assert "menu:View/Dark Theme" in commands
    assert "workspace_action:save" in commands
    # the palette does not list itself
    assert not any("Command Palette" in cmd.title for cmd in commands.values())


def test_main_app_navigation_command(qtbot, main_app):
    _by_uid(main_app)["view:DM"].callback()
    assert main_app.stack.currentIndex() == main_app._view_index["DM"]


def test_main_app_widget_and_device_commands(qtbot, main_app):
    dock_area = main_app.dock_area.dock_area
    main_app.set_current("DM")
    commands = _by_uid(main_app)
    commands["widget:RingProgressBar"].callback()
    assert main_app.stack.currentIndex() == main_app._view_index["Docks"]
    assert any(type(w).__name__ == "RingProgressBar" for w in dock_area.widget_list())

    commands["device:samx"].callback()
    boxes = [w for w in dock_area.widget_list() if type(w).__name__ == "PositionerBox"]
    assert boxes and boxes[0].device == "samx"

    with mock.patch("bec_widgets.widgets.plots.waveform.waveform.Waveform.plot") as plot:
        commands["device:bpm4i"].callback()
    plot.assert_called_once_with(device_y="bpm4i")


def test_main_app_workspace_commands(qtbot, main_app):
    dock_area = main_app.dock_area.dock_area
    with mock.patch.object(dock_area, "list_profiles", return_value=["alignment"]):
        commands = _by_uid(main_app)
    with mock.patch.object(dock_area, "load_profile") as load:
        commands["workspace:alignment"].callback()
    load.assert_called_once_with("alignment")
    locked = dock_area.workspace_is_locked
    commands["workspace_action:lock"].callback()
    assert dock_area.workspace_is_locked is (not locked)
