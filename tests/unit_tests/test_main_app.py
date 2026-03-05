import pytest
from qtpy.QtCore import QRect
from qtpy.QtWidgets import QWidget

from bec_widgets.applications.main_app import BECMainApp
from bec_widgets.applications.views.view import ViewBase
from bec_widgets.utils.bec_widget import BECWidget

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
    # App must be shown properly to ensure visibility checks work
    # Call .show() and then waitExposed
    app.show()
    qtbot.waitExposed(app)

    app.add_section("Tests", id="tests")

    v1 = SpyView(view_id="v1", title="V1")
    v2 = SpyView(view_id="v2", title="V2")
    vv = SpyVetoView(view_id="vv", title="VV")

    app.add_view(icon="widgets", title="View 1", view_id="v1", widget=v1, mini_text="v1")
    app.add_view(icon="widgets", title="View 2", view_id="v2", widget=v2, mini_text="v2")
    app.add_view(icon="widgets", title="Veto View", view_id="vv", widget=vv, mini_text="vv")

    # Start from dock_area (default) to avoid extra enter/exit counts on spies
    assert app.stack.currentIndex() == app._view_index["Docks"]
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


def test_added_view_gets_short_object_name(app_with_spies):
    app, v1, _, _ = app_with_spies
    assert v1.object_name == "v1"
    assert app._view_index["v1"] >= 0


def test_view_switch_method_switches_to_target(app_with_spies, qtbot):
    app, v1, _, _ = app_with_spies
    app.set_current("dock_area")
    qtbot.wait(10)
    v1.activate()
    qtbot.wait(10)
    assert app.stack.currentIndex() == app._view_index["v1"]


def test_view_content_widget_is_hidden_from_namespace(app_with_spies):
    app, _, _, _ = app_with_spies
    assert app.dock_area.content is app.dock_area.dock_area


# def test_developer_plotting_area_parent_id_uses_view_namespace(app_with_spies): #TODO temp disabled due to disabled IDE view
#     app, _, _, _ = app_with_spies
#     plotting_area = app.developer_view.developer_widget.plotting_ads
#
#     assert plotting_area.parent_id == app.developer_view.gui_id


def test_parent_id_ignores_plain_qwidget_between_connectors(qtbot, mocked_client):
    class RootConnector(BECWidget, QWidget):
        RPC = True

    class ChildConnector(BECWidget, QWidget):
        RPC = True

    root = RootConnector(client=mocked_client)
    qtbot.addWidget(root)
    spacer = QWidget(root)
    child = ChildConnector(parent=spacer, client=mocked_client)

    assert child.parent_id == root.gui_id


def test_guided_tour_is_initialized(app_with_spies):
    """Test that the guided tour is initialized in the main app."""
    app, _, _, _ = app_with_spies

    # Check that guided_tour exists
    assert hasattr(app, "guided_tour")
    assert app.guided_tour is not None

    # Check that start_guided_tour method exists
    assert hasattr(app, "start_guided_tour")
    assert callable(app.start_guided_tour)


def test_guided_tour_has_registered_widgets(app_with_spies):
    """Test that the guided tour has registered widgets."""
    app, _, _, _ = app_with_spies

    # Get registered widgets
    registered = app.guided_tour.get_registered_widgets()

    # Should have at least some registered widgets
    assert len(registered) > 0

    # Check that tour steps were created
    assert len(app.guided_tour._tour_steps) > 0


def test_views_can_extend_guided_tour(app_with_spies):
    """Test that views can register their own tour steps."""
    app, _, _, _ = app_with_spies

    # Check that device manager has register_tour_steps method
    assert hasattr(app.device_manager, "register_tour_steps")
    assert callable(app.device_manager.register_tour_steps)

    # Check that developer view has register_tour_steps method #TODO temp disabled due to disabled IDE view
    # assert hasattr(app.developer_view, "register_tour_steps")
    # assert callable(app.developer_view.register_tour_steps)

    # Verify that calling register_tour_steps returns ViewTourSteps or None
    dm_tour = app.device_manager.register_tour_steps(app.guided_tour, app)
    if dm_tour is not None:
        assert hasattr(dm_tour, "view_title")
        assert hasattr(dm_tour, "step_ids")
        assert isinstance(dm_tour.step_ids, list)

    # ide_tour = app.developer_view.register_tour_steps(app.guided_tour, app)  #TODO temp disabled due to disabled IDE view
    # if ide_tour is not None:
    #     assert hasattr(ide_tour, "view_title")
    #     assert hasattr(ide_tour, "step_ids")
    #     assert isinstance(ide_tour.step_ids, list)

    # Get all registered widgets
    widgets = app.guided_tour.get_registered_widgets()

    # pylint: disable=protected-access
    # Test that ide_tour has valid steps and targets #TODO temp disabled due to disabled IDE view
    # for step_id in ide_tour.step_ids:
    #     assert step_id in widgets
    #     tour_step = widgets.get(step_id)
    #     target, text = app.guided_tour._resolve_step_target(tour_step)
    #     assert isinstance(text, str)
    #     assert text != ""
    #     if target is not None:  # If step should be skipped
    #         highlighted_rect = app.guided_tour._get_highlight_rect(app, target, tour_step["title"])
    #         if (
    #             highlighted_rect is not None
    #         ):  # If widget is not visible, it will be skipped and return None
    #             assert isinstance(highlighted_rect, QRect)

    # Test that dm_tour has valid steps and targets, test it once
    # with _initialized = True and False. This leads to different tour paths.
    for init in [False, True]:
        app.device_manager.device_manager_widget._initialized = init
        for step_id in dm_tour.step_ids:
            assert step_id in widgets
            tour_step = widgets.get(step_id)
            target, text = app.guided_tour._resolve_step_target(tour_step)
            assert isinstance(text, str)
            assert text != ""
            if target is not None:  # If step should be skipped
                highlighted_rect = app.guided_tour._get_highlight_rect(
                    app, target, tour_step["title"]
                )
                if (
                    highlighted_rect is not None
                ):  # If widget is not visible, it will be skipped and return None
                    assert isinstance(highlighted_rect, QRect)


def test_guided_tour_can_start_and_stop(app_with_spies, qtbot):
    """Test that the guided tour can be started and stopped."""
    app, _, _, _ = app_with_spies

    app: BECMainApp

    # Start the tour
    with qtbot.waitSignal(app.guided_tour.tour_started, timeout=2000) as blocker:
        app.start_guided_tour()
    assert blocker.signal_triggered

    # Check that tour is active
    assert app.guided_tour._active
    assert app.guided_tour.overlay is not None
    assert app.guided_tour.overlay.isVisible()

    # Stop the tour
    with qtbot.waitSignal(app.guided_tour.tour_finished, timeout=2000) as blocker:
        app.guided_tour.stop_tour()

    assert blocker.signal_triggered

    # Check that tour is stopped
    assert not app.guided_tour._active
