import pytest

from bec_widgets.applications.views.welcome_view.welcome_data import demo_snapshot
from bec_widgets.applications.views.welcome_view.welcome_view import (
    DIRECTIONS,
    WelcomeView,
    welcome_view_requested,
)
from bec_widgets.tests.utils import create_widget


@pytest.mark.parametrize(
    "value, expected",
    [("", None), ("0", None), ("off", None), ("board", "board"), ("FEED", "feed"), ("1", "board")],
)
def test_welcome_view_requested(monkeypatch, value, expected):
    monkeypatch.setenv("BEC_WELCOME_VIEW", value)
    assert welcome_view_requested() == expected


@pytest.mark.parametrize("direction", [key for key, _ in DIRECTIONS])
def test_welcome_view_builds_every_direction(qtbot, mocked_client, direction):
    view = create_widget(qtbot, WelcomeView, client=mocked_client, direction=direction)
    assert view.direction == direction
    view.set_switcher_visible(False)
    view.set_direction("board")
    assert view.direction == "board"


def test_welcome_view_rejects_unknown_direction(qtbot, mocked_client):
    view = create_widget(qtbot, WelcomeView, client=mocked_client)
    with pytest.raises(ValueError):
        view.set_direction("nope")


def test_demo_snapshot_is_consistent():
    snap = demo_snapshot()
    assert snap.running is not None and 0 < snap.running.done < snap.running.total
    assert len(snap.glances) == 4
    assert all(
        ev.kind in {"scan", "problem", "interlock", "config", "note", "session"}
        for ev in snap.events
    )
