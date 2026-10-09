from types import SimpleNamespace

import pytest
from bec_lib import messages
from qtpy.QtCore import QEvent, QPointF, QSettings, Qt
from qtpy.QtGui import QKeyEvent, QMouseEvent
from qtpy.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

from bec_widgets.applications.main_app import BECMainApp
from bec_widgets.applications.system_dock.system_dock import (
    MAX_PINNED,
    RailIndicator,
    SystemDock,
    SystemPanel,
)
from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.widgets.containers.main_window.addons.notification_center.notification_ux_common import (
    NotificationHub,
)


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "dock.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def window(qtbot, settings):
    """A plain window with a content area and the dock on its right edge."""
    win = QWidget()
    win.resize(1200, 700)
    layout = QHBoxLayout(win)
    layout.setContentsMargins(0, 0, 0, 0)
    win.content = QLabel("content", win)
    layout.addWidget(win.content, 1)
    win.dock = SystemDock(win, settings=settings)
    layout.addWidget(win.dock.pinned_column)
    layout.addWidget(win.dock)
    for name in ("alpha", "beta", "gamma"):
        win.dock.add_panel(
            SystemPanel(name, name.title(), "info", name.title(), QLabel(name)),
            shortcut="Ctrl+Shift+A" if name == "alpha" else None,
        )
    win.dock.add_separator()
    win.dock.add_panel(
        SystemPanel("small", "Small", "info", "Small", QLabel("small"), preferred_height=80)
    )
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    yield win
    win.dock.cleanup()


def _press(widget: QWidget):
    """Send a mouse press at the centre of ``widget`` through its window, like a real click."""
    handle = widget.window().windowHandle()
    local = QPointF(widget.mapTo(widget.window(), widget.rect().center()))
    global_pos = QPointF(widget.mapToGlobal(widget.rect().center()))
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        local,
        global_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(handle, event)


def test_rail_lists_panels_in_order(window):
    assert window.dock.panel_ids == ["alpha", "beta", "gamma", "small"]
    assert window.dock.peek_panel_id is None
    assert not window.dock.hover_open  # click to open is the default


def test_click_opens_flyout_and_click_again_closes(qtbot, window):
    dock = window.dock
    qtbot.mouseClick(dock.button("alpha"), Qt.MouseButton.LeftButton)
    assert dock.peek_panel_id == "alpha"
    assert dock.peek_sticky
    assert dock.peek.isVisible()
    assert dock.button("alpha").active
    qtbot.mouseClick(dock.button("beta"), Qt.MouseButton.LeftButton)
    assert dock.peek_panel_id == "beta"
    assert not dock.button("alpha").active
    qtbot.mouseClick(dock.button("beta"), Qt.MouseButton.LeftButton)
    assert dock.peek_panel_id is None
    assert not dock.peek.isVisible()


def test_click_outside_and_escape_close_the_flyout(qtbot, window):
    dock = window.dock
    dock.open_panel("alpha")
    _press(dock.frame("alpha").panel.content)
    assert dock.peek_panel_id == "alpha"  # clicks inside the flyout keep it open
    _press(window.content)
    assert dock.peek_panel_id is None
    dock.open_panel("alpha")
    # real key presses reach the window first, which is where the dock listens
    escape = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(window.windowHandle(), escape)
    assert dock.peek_panel_id is None


def test_flyout_is_left_of_the_rail_and_compact_panels_are_short(qtbot, window):
    dock = window.dock
    dock.open_panel("alpha")
    qtbot.wait(200)
    assert dock.peek.geometry().right() < dock.geometry().left()
    assert dock.peek.height() == dock.height()
    dock.open_panel("small")
    assert dock.peek.height() < dock.height()


def test_pin_moves_panel_into_the_column(qtbot, window, settings):
    dock = window.dock
    dock.open_panel("alpha")
    dock.set_pinned("alpha", True)
    assert dock.pinned == ["alpha"]
    assert dock.peek_panel_id is None
    assert dock.pinned_column.isVisible()
    assert dock.frame("alpha").parent() is dock.pinned_column
    assert dock.is_shown("alpha")
    assert dock.button("alpha").active
    assert settings.value("system_dock/pinned") in (["alpha"], "alpha")
    # a pinned panel's rail button does not open a flyout
    qtbot.mouseClick(dock.button("alpha"), Qt.MouseButton.LeftButton)
    assert dock.peek_panel_id is None
    dock.close_panel("alpha")
    assert dock.pinned == []
    assert not dock.pinned_column.isVisible()
    assert not dock.is_shown("alpha")


def test_at_most_two_panels_are_pinned(window):
    dock = window.dock
    for panel_id in ("alpha", "beta", "gamma"):
        dock.set_pinned(panel_id, True)
    assert len(dock.pinned) == MAX_PINNED
    assert dock.pinned == ["beta", "gamma"]


def test_pin_shortcut_pins_the_open_flyout_then_unpins(window):
    dock = window.dock
    dock.open_panel("beta")
    dock.toggle_pin_current()
    assert dock.pinned == ["beta"]
    dock.toggle_pin_current()
    assert dock.pinned == []


def test_panel_shortcut_toggles_the_panel(qtbot, window):
    qtbot.keyClick(
        window,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    assert window.dock.peek_panel_id == "alpha"
    assert "Ctrl+Shift+A" in window.dock.button("alpha").toolTip()


def test_pinned_panels_are_restored(qtbot, window, settings):
    window.dock.set_pinned("gamma", True)
    other = QWidget()
    qtbot.addWidget(other)
    dock = SystemDock(other, settings=settings)
    dock.add_panel(SystemPanel("gamma", "Gamma", "info", "Gamma", QLabel("g")))
    dock.restore_state()
    assert dock.pinned == ["gamma"]
    dock.cleanup()


def test_hover_opens_only_when_enabled(qtbot, window):
    dock = window.dock
    dock._on_button_hovered("alpha", True)
    qtbot.wait(400)
    assert dock.peek_panel_id is None
    dock.set_hover_open(True)
    dock.open_panel("alpha", sticky=False)
    dock._on_button_hovered("beta", True)  # a hover flyout follows the pointer
    assert dock.peek_panel_id == "beta"
    assert not dock.peek_sticky


def test_indicator_updates_tooltip_and_pulse(window):
    dock = window.dock
    panel = dock.panel("beta")
    panel.set_indicator(RailIndicator(badge="2", tooltip="2 things", pulse=True))
    assert "2 things" in dock.button("beta").toolTip()
    assert dock._pulse.state() == dock._pulse.State.Running
    panel.set_indicator(RailIndicator())
    assert dock._pulse.state() != dock._pulse.State.Running


def test_hiding_the_dock_closes_the_flyout(window):
    dock = window.dock
    dock.open_panel("alpha")
    dock.set_pinned("beta", True)
    dock.set_dock_visible(False)
    assert dock.peek_panel_id is None
    assert not dock.isVisible()
    assert not dock.pinned_column.isVisible()
    dock.set_dock_visible(True)
    assert dock.pinned_column.isVisible()


@pytest.fixture
def main_app(qtbot, mocked_client, monkeypatch):
    monkeypatch.delenv("BEC_SYSTEM_DOCK", raising=False)
    monkeypatch.delenv("BEC_NOTIFICATION_UI", raising=False)
    app = BECMainApp(client=mocked_client, anim_duration=10, system_dock="qwidget")
    qtbot.addWidget(app)
    app.show()
    qtbot.waitExposed(app)
    yield app
    # the reworked notification hub is an app-wide singleton
    NotificationHub.reset_instance()


def test_main_app_builds_the_core_panels(main_app):
    dock = main_app.system_dock
    assert dock.panel_ids == [
        "progress",
        "queue",
        "services",
        "beamline_states",
        "notifications",
        "devices",
    ]
    assert main_app.content_splitter.widget(1) is dock.pinned_column
    # the rail replaces the status bar progress bar and bell
    assert not main_app._scan_progress_bar_with_separator.isVisible()
    assert not main_app.notifications.bell.isVisible()
    assert main_app.notification_indicator is dock.button("notifications")


def test_main_app_notifications_open_in_the_dock(qtbot, main_app):
    dock = main_app.system_dock
    host = main_app.notifications
    entry = host.hub.notify("Detector timeout", "eiger9m", "error")
    qtbot.waitUntil(lambda: host.hub.unread_count() == 1)
    qtbot.waitUntil(lambda: dock.panel("notifications").indicator.badge == "1")
    # the toast's Details action opens the dock panel at that entry
    host.open_details(entry)
    assert dock.peek_panel_id == "notifications"
    assert host.drawer_open
    assert host.drawer.parent() is not main_app
    qtbot.waitUntil(lambda: dock.panel("notifications").indicator.badge == "")
    dock.close_peek()
    assert not host.drawer_open


def test_main_app_badges_follow_the_widgets(main_app):
    dock = main_app.system_dock
    tokens = ThemeTokens()
    queue = dock.panel("queue")
    paused = messages.ScanQueueStatusMessage(
        metadata={}, queue={"primary": {"info": [], "status": "PAUSED", "locks": []}}
    )
    queue.queue.update_queue(paused.content, {})
    assert queue.indicator.badge == ""
    assert queue.indicator.dot_color == tokens.warning
    assert queue.indicator.summary.startswith("Paused")

    services = dock.panel("services")
    assert services.indicator.dot_color is None or services.box.model.tone in (
        "warning",
        "emergency",
    )

    states = dock.panel("beamline_states")
    real = states.states
    try:
        controller = SimpleNamespace(
            blockingStates=["shutter_open"],
            counts={"invalid": 1, "warning": 0, "unknown": 0, "valid": 3},
            totalCount=4,
            interlockArmed=True,
        )
        states.states = SimpleNamespace(controller=controller)
        states.refresh()
        assert states.indicator.badge == "!"
        assert states.indicator.pulse
        controller.blockingStates = []
        states.refresh()
        assert states.indicator.badge == ""
        assert states.indicator.dot_color == tokens.warning
        controller.counts = {"invalid": 0, "warning": 0, "unknown": 0, "valid": 4}
        states.refresh()
        assert states.indicator.dot_color is None
        assert states.indicator.summary == "All 4 valid · interlock armed"
    finally:
        states.states = real


def test_main_app_without_dock(qtbot, mocked_client, monkeypatch):
    monkeypatch.setenv("BEC_SYSTEM_DOCK", "off")
    monkeypatch.delenv("BEC_NOTIFICATION_UI", raising=False)
    app = BECMainApp(client=mocked_client, anim_duration=10)
    qtbot.addWidget(app)
    assert app.system_dock is None
    assert app.notifications is None
    assert app.stack.parent() is app.centralWidget()
