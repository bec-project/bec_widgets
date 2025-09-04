import pytest
from qtpy.QtWidgets import QWidget

from bec_widgets.applications.main_app import BECMainApp
from bec_widgets.applications.views.view import ViewBase

from .client_mocks import mocked_client

ANIM_TEST_DURATION = 60  # ms


@pytest.fixture
def viewbase(qtbot):
    v = ViewBase(content=QWidget())
    qtbot.addWidget(v)
    qtbot.waitExposed(v)
    yield v


# Spy views for testing enter/exit hooks and veto logic
class SpyView(ViewBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enter_calls = 0
        self.exit_calls = 0

    def on_enter(self) -> None:
        self.enter_calls += 1

    def on_exit(self) -> bool:
        self.exit_calls += 1
        return True


class SpyVetoView(SpyView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_exit = False

    def on_exit(self) -> bool:
        self.exit_calls += 1
        return bool(self.allow_exit)


@pytest.fixture
def app_with_spies(qtbot, mocked_client):
    app = BECMainApp(client=mocked_client, anim_duration=ANIM_TEST_DURATION, show_examples=False)
    qtbot.addWidget(app)
    qtbot.waitExposed(app)

    app.add_section("Tests", id="tests")

    v1 = SpyView(id="v1", title="V1")
    v2 = SpyView(id="v2", title="V2")
    vv = SpyVetoView(id="vv", title="VV")

    app.add_view(icon="widgets", title="View 1", id="v1", widget=v1, mini_text="v1")
    app.add_view(icon="widgets", title="View 2", id="v2", widget=v2, mini_text="v2")
    app.add_view(icon="widgets", title="Veto View", id="vv", widget=vv, mini_text="vv")

    # Start from dock_area (default) to avoid extra enter/exit counts on spies
    assert app.stack.currentIndex() == app._view_index["dock_area"]
    return app, v1, v2, vv


def test_viewbase_initializes(viewbase):
    assert viewbase.on_enter() is None
    assert viewbase.on_exit() is True


def test_on_enter_and_on_exit_are_called_on_switch(app_with_spies, qtbot):
    app, v1, v2, _ = app_with_spies

    app.set_current("v1")
    qtbot.wait(10)
    assert v1.enter_calls == 1

    app.set_current("v2")
    qtbot.wait(10)
    assert v1.exit_calls == 1
    assert v2.enter_calls == 1

    app.set_current("v1")
    qtbot.wait(10)
    assert v2.exit_calls == 1
    assert v1.enter_calls == 2


def test_on_exit_veto_prevents_switch_until_allowed(app_with_spies, qtbot):
    app, v1, v2, vv = app_with_spies

    # Move to veto view first
    app.set_current("vv")
    qtbot.wait(10)
    assert vv.enter_calls == 1

    # Attempt to leave veto view -> should veto
    app.set_current("v1")
    qtbot.wait(10)
    assert vv.exit_calls == 1
    # Still on veto view because veto returned False
    assert app.stack.currentIndex() == app._view_index["vv"]

    # Allow exit and try again
    vv.allow_exit = True
    app.set_current("v1")
    qtbot.wait(10)

    # Now the switch should have happened, and v1 received on_enter
    assert app.stack.currentIndex() == app._view_index["v1"]
    assert v1.enter_calls >= 1
