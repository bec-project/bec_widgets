"""Tests of the tour guide (short tours, progress, welcome, hints, What's this and both overlays)."""

# pylint: disable=redefined-outer-name,protected-access

import pytest
from qtpy.QtCore import QPoint, QRect, QSettings, QSize
from qtpy.QtWidgets import QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from bec_widgets.utils.tour_guide.geometry import interaction_region, place_card, target_rect
from bec_widgets.utils.tour_guide.guide import TourGuide, tour_ui_from_env
from bec_widgets.utils.tour_guide.model import Tour, TourProgress, TourStep


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "tours.ini"), QSettings.Format.IniFormat)


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        central = QWidget()
        layout = QVBoxLayout(central)
        self.first = QPushButton("First")
        self.second = QPushButton("Second")
        self.hidden = QPushButton("Hidden")
        self.help = QPushButton("Help")
        for widget in (self.first, self.second, self.hidden, QLabel("text"), self.help):
            layout.addWidget(widget)
        self.hidden.hide()
        self.setCentralWidget(central)
        self.view = "main"


@pytest.fixture(params=["qwidget", "qml"])
def guide(request, qtbot, settings):
    window = Window()
    qtbot.addWidget(window)
    window.resize(900, 600)
    window.show()
    qtbot.waitExposed(window)
    switched = []

    def switch(view):
        switched.append(view)
        window.view = view

    guide = TourGuide(
        window,
        ui=request.param,
        settings=settings,
        view_switcher=switch,
        current_view=lambda: window.view,
    )
    guide.switched = switched
    guide.register_tour(
        Tour(
            id="basics",
            title="Basics",
            summary="The buttons.",
            order=0,
            steps=[
                TourStep("First", "The first button.", target=window.first, hint="Click it."),
                TourStep("Hidden", "Never visible.", target=window.hidden),
                TourStep("Second", "The second button.", target=lambda: window.second),
                TourStep("Overview", "No target, centred card."),
            ],
        )
    )
    guide.register_tour(
        Tour(
            id="other",
            title="Other view",
            summary="Lives in another view.",
            view="other",
            order=1,
            steps=[TourStep("Help", "The help button.", target=window.help, view="other")],
        )
    )
    guide.register_tour(
        Tour(
            id="unavailable",
            title="Never",
            summary="No available step.",
            steps=[TourStep("x", "y", target=window.first, available=lambda: False)],
        )
    )
    guide.set_help_anchor(window.help)
    yield guide
    guide.close()
    guide.cleanup()


def test_progress_store_round_trip(settings):
    progress = TourProgress(settings)
    assert progress.completed() == []
    assert progress.position("a") is None
    progress.save_position("a", 3)
    assert progress.position("a") == 3
    progress.mark_completed("a")
    assert progress.is_completed("a")
    assert progress.position("a") is None
    progress.welcome_dismissed = True
    progress.mark_offered("b")
    again = TourProgress(settings)
    assert again.welcome_dismissed
    assert again.offered() == ["b"]
    again.reset()
    assert not again.welcome_dismissed and again.completed() == []


def test_tours_hide_tours_without_available_steps(guide):
    assert [tour.id for tour in guide.tours()] == ["basics", "other"]


def test_tour_skips_invisible_steps_and_counts_correctly(guide):
    assert guide.start_tour("basics")
    state = guide.state()
    assert state["mode"] == "step"
    assert state["title"] == "First"
    assert state["hint"] == "Click it."
    assert state["count"] == 4
    assert state["spot"].contains(guide._window.first.geometry().center())
    guide.next_step()
    state = guide.state()
    assert state["title"] == "Second"  # the hidden button is skipped ...
    assert state["count"] == 3  # ... and no longer counted
    assert state["index"] == 1
    guide.next_step()
    assert guide.state()["spot"] is None
    guide.prev_step()
    assert guide.state()["title"] == "Second"


def test_close_keeps_position_and_resume_continues(guide):
    guide.start_tour("basics")
    guide.next_step()
    guide.close()
    assert guide.mode == "hidden"
    status = guide.tour_status(guide.tour("basics"))
    assert status["status"] == "in_progress"
    assert status["label"].startswith("Step 2")
    guide.resume_tour("basics")
    assert guide.current_index == 1


def test_finish_marks_done_and_suggests_next(guide):
    guide.start_tour("basics", 3)
    guide.next_step()
    assert guide.mode == "done"
    state = guide.state()
    assert state["finished"] == "Basics"
    assert state["next"]["id"] == "other"
    assert guide.tour_status(guide.tour("basics"))["status"] == "done"


def test_step_in_other_view_switches_view(guide):
    guide.start_tour("other")
    assert guide.switched == ["other"]
    assert guide.state()["title"] == "Help"


def test_welcome_is_shown_until_dismissed(guide, settings):
    assert guide.maybe_show_welcome()
    state = guide.state()
    assert state["mode"] == "welcome"
    assert [tour["id"] for tour in state["tours"]] == ["basics", "other"]
    assert state["anchor"] is not None
    guide._on_overlay_action("never", "")
    assert guide.mode == "hidden"
    assert TourProgress(settings).welcome_dismissed
    assert not guide.maybe_show_welcome()


def test_view_hint_is_offered_once(guide):
    guide.notify_view_entered("other")
    assert guide.mode == "hint"
    assert guide.state()["tour"]["id"] == "other"
    guide.close()
    guide.notify_view_entered("other")
    assert guide.mode == "hidden"


def test_hub_lists_status_and_actions_route(guide):
    guide.open_hub()
    state = guide.state()
    assert state["mode"] == "hub"
    assert state["done"] == 0 and state["total"] == 2
    guide._on_overlay_action("start", "basics")
    assert guide.is_active
    guide._on_overlay_action("hub", "")
    assert guide.mode == "hub"


def test_whats_this_collects_visible_documented_controls(guide):
    guide._window.view = "main"
    guide.toggle_whats_this()
    state = guide.state()
    titles = [anchor["title"] for anchor in state["anchors"]]
    assert titles == ["First", "Second"]  # hidden, other-view and target-less steps are left out
    guide.select_anchor(1)
    state = guide.state()
    assert state["selected"] == 1
    assert state["spot"] is not None
    guide.toggle_whats_this()
    assert guide.mode == "hidden"


def test_palette_and_welcome_hooks(guide):
    commands = guide.palette_commands()
    uids = [command["uid"] for command in commands]
    assert uids == ["tour:hub", "tour:whatsthis", "tour:basics", "tour:other"]
    commands[2]["callback"]()
    assert guide.is_active
    items = guide.welcome_items()
    assert items[0]["id"] == "basics" and items[0]["steps"] == 4
    guide.close()
    items[1]["start"]()
    assert guide.current_tour.id == "other"


def test_overlay_masks_let_the_app_work(guide, qtbot):
    window = guide._window
    guide.maybe_show_welcome()
    qtbot.wait(100)
    overlay = guide.overlay
    center = window.rect().center()
    # the welcome card only takes clicks on itself
    assert not overlay.mask().contains(QPoint(center.x(), 5))
    guide.start_tour("basics")
    qtbot.wait(100)
    spot = guide.state()["spot"]
    # the highlighted control stays clickable during a step, the rest is blocked
    assert not overlay.mask().contains(spot.center())
    assert overlay.mask().contains(QPoint(window.width() - 5, window.height() - 5))


def test_keyboard_shortcuts_only_while_blocking(guide):
    assert not any(shortcut.isEnabled() for shortcut in guide._shortcuts)
    guide.start_tour("basics")
    assert all(shortcut.isEnabled() for shortcut in guide._shortcuts)
    guide.close()
    guide.maybe_show_welcome()
    assert not any(shortcut.isEnabled() for shortcut in guide._shortcuts)


def test_place_card_avoids_spot():
    bounds = QRect(0, 0, 1000, 700)
    spot = QRect(10, 10, 100, 40)
    position, side = place_card(spot, QSize(300, 200), bounds)
    assert side == "right"
    assert not QRect(position, QSize(300, 200)).intersects(spot)
    position, side = place_card(QRect(850, 300, 140, 40), QSize(300, 200), bounds)
    assert side == "left"
    position, side = place_card(None, QSize(300, 200), bounds)
    assert side == "center" and abs(position.x() - 350) <= 1 and abs(position.y() - 250) <= 1


def test_interaction_region_modes():
    bounds = QRect(0, 0, 400, 300)
    spot = QRect(10, 10, 50, 50)
    card = QRect(100, 100, 100, 100)
    step = interaction_region("step", bounds, spot, [card])
    assert not step.contains(QPoint(20, 20)) and step.contains(QPoint(300, 250))
    welcome = interaction_region("welcome", bounds, None, [card])
    assert welcome.contains(QPoint(150, 150)) and not welcome.contains(QPoint(300, 250))
    assert not interaction_region("hint", bounds, None, []).isEmpty()


def test_target_rect_handles_hidden_and_callables(qtbot):
    window = Window()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    assert target_rect(window.hidden, window) is None
    assert target_rect(lambda: (window.first, "text"), window) is not None
    assert target_rect(QRect(1, 1, 20, 20), window) == QRect(1, 1, 20, 20)


def test_tour_ui_from_env(monkeypatch):
    monkeypatch.delenv("BEC_TOUR_UI", raising=False)
    assert tour_ui_from_env() is None
    monkeypatch.setenv("BEC_TOUR_UI", "QML")
    assert tour_ui_from_env() == "qml"
    monkeypatch.setenv("BEC_TOUR_UI", "nope")
    assert tour_ui_from_env() is None


@pytest.mark.parametrize("ui", ["qwidget", "qml"])
def test_main_app_entry_points(qtbot, mocked_client, settings, ui):
    # pylint: disable=import-outside-toplevel
    from qtpy.QtWidgets import QMenu

    from bec_widgets.applications.main_app import BECMainApp

    app = BECMainApp(client=mocked_client, anim_duration=10)
    qtbot.addWidget(app)
    app._setup_tour_guide(ui, settings=settings, first_run=False)
    app.show()
    qtbot.waitExposed(app)
    guide = app.tour_guide
    assert {tour.id for tour in guide.tours()} >= {"first_steps", "workspace", "device_config"}
    assert "help" in app.sidebar.components
    help_menu = next(menu for menu in app.menuBar().findChildren(QMenu) if menu.title() == "Help")
    shortcuts = {action.text(): action.shortcut().toString() for action in help_menu.actions()}
    assert shortcuts["Tours…"] == "F1"
    assert shortcuts["What's This?"] == "Shift+F1"
    assert "Classic Guided Tour" in shortcuts
    app.sidebar.components["help"].activated.emit()
    assert guide.mode == "hub"
    assert guide.start_tour("workspace")
    assert guide.state()["spot"] is not None
    devices = next(tour for tour in guide.tours() if tour.id == "device_config")
    guide.start_tour(devices.id)
    assert app._current_view_id == devices.view
    guide.close()
