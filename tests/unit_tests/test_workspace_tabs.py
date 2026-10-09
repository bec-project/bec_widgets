# pylint: disable=missing-function-docstring, missing-module-docstring, redefined-outer-name
import pytest
from qtpy.QtWidgets import QInputDialog, QMessageBox

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.widgets.containers.dock_area.profile_utils import (
    get_open_workspaces,
    list_profiles,
    set_open_workspaces,
)
from bec_widgets.widgets.containers.dock_area.workspace_tabs import (
    UNTITLED_WORKSPACE,
    WorkspaceTabs,
)

NAMESPACE = "tabs_test"


@pytest.fixture(autouse=True)
def isolate_profile_storage(tmp_path, monkeypatch):
    root = tmp_path / "profiles_root"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BECWIDGETS_PROFILE_DIR", str(root))
    yield


@pytest.fixture
def make_tabs(qtbot, mocked_client):
    created = []

    def _make(**kwargs):
        tabs = WorkspaceTabs(profile_namespace=NAMESPACE, client=mocked_client, **kwargs)
        qtbot.addWidget(tabs)
        tabs.show()
        qtbot.waitExposed(tabs)
        created.append(tabs)
        return tabs

    yield _make
    for tabs in created:
        tabs.cleanup()


def _save_profile(tabs, name):
    """Save the current tab under *name* without dialogs."""
    tabs.current_dock_area().save_profile(name, show_dialog=False)


def test_starts_with_one_untitled_workspace(make_tabs):
    tabs = make_tabs()
    assert tabs.count() == 1
    assert tabs.tabText(0) == UNTITLED_WORKSPACE
    assert tabs.current_dock_area() is not None
    assert tabs.workspace_names() == [None]


def test_new_workspace_adds_and_switches_tab(make_tabs):
    tabs = make_tabs()
    first = tabs.current_dock_area()
    tabs.new_workspace()
    assert tabs.count() == 2
    assert tabs.currentIndex() == 1
    second = tabs.current_dock_area()
    assert second is not first
    assert tabs.dock_areas() == [first, second]


def test_each_tab_keeps_its_own_layout(make_tabs):
    tabs = make_tabs()
    tabs.current_dock_area().new("RingProgressBar")
    tabs.new_workspace()
    assert tabs.current_dock_area().dock_list() == []
    tabs.setCurrentIndex(0)
    assert len(tabs.current_dock_area().dock_list()) == 1


def test_saving_names_the_tab_and_persists_open_tabs(make_tabs):
    tabs = make_tabs()
    _save_profile(tabs, "alignment")
    assert tabs.tabText(0) == "alignment"
    tabs.new_workspace()
    _save_profile(tabs, "scans")
    assert get_open_workspaces(NAMESPACE) == (["alignment", "scans"], "scans")

    tabs.setCurrentIndex(0)
    assert get_open_workspaces(NAMESPACE) == (["alignment", "scans"], "alignment")


def test_unsaved_tabs_are_not_persisted(make_tabs):
    tabs = make_tabs()
    _save_profile(tabs, "alignment")
    tabs.new_workspace()
    assert get_open_workspaces(NAMESPACE) == (["alignment"], None)


def test_restores_open_tabs_lazily(make_tabs):
    tabs = make_tabs()
    tabs.current_dock_area().new("RingProgressBar")
    _save_profile(tabs, "alignment")
    tabs.new_workspace()
    _save_profile(tabs, "scans")
    tabs.setCurrentIndex(0)
    tabs.cleanup()

    restored = make_tabs()
    assert [restored.tabText(i) for i in range(restored.count())] == ["alignment", "scans"]
    assert restored.currentIndex() == 0
    # Only the active tab builds its dock area at startup
    assert [page.is_materialized for page in restored.pages()] == [True, False]
    assert len(restored.current_dock_area().dock_list()) == 1

    restored.setCurrentIndex(1)
    assert restored.pages()[1].is_materialized
    assert restored.current_dock_area()._current_profile_name == "scans"


def test_restore_skips_missing_profiles(make_tabs):
    set_open_workspaces(["gone", "also_gone"], "gone", namespace=NAMESPACE)
    tabs = make_tabs()
    assert tabs.count() == 1
    assert tabs.workspace_names() == [None]


def test_restore_is_scoped_to_known_profiles(make_tabs):
    tabs = make_tabs()
    _save_profile(tabs, "alignment")
    tabs.cleanup()
    set_open_workspaces(["alignment", "gone"], "gone", namespace=NAMESPACE)

    restored = make_tabs()
    assert restored.workspace_names() == ["alignment"]


def test_open_workspace_switches_to_existing_tab(make_tabs):
    tabs = make_tabs()
    _save_profile(tabs, "alignment")
    tabs.new_workspace()
    tabs.open_workspace("alignment")
    assert tabs.count() == 2
    assert tabs.currentIndex() == 0


def test_open_workspace_opens_saved_profile_in_new_tab(make_tabs):
    tabs = make_tabs()
    tabs.current_dock_area().new("RingProgressBar")
    _save_profile(tabs, "alignment")
    tabs.new_workspace()
    _save_profile(tabs, "scans")
    tabs.close_workspace(0)
    assert tabs.workspace_names() == ["scans"]

    tabs.open_workspace("alignment")
    assert tabs.workspace_names() == ["scans", "alignment"]
    assert len(tabs.current_dock_area().dock_list()) == 1


def test_loading_profile_open_in_other_tab_switches_instead(make_tabs):
    tabs = make_tabs()
    _save_profile(tabs, "alignment")
    tabs.new_workspace()
    _save_profile(tabs, "scans")

    tabs.current_dock_area().load_profile("alignment")

    assert tabs.currentIndex() == 0
    assert tabs.workspace_names() == ["alignment", "scans"]


def test_saving_under_name_open_in_other_tab_is_refused(make_tabs):
    tabs = make_tabs()
    _save_profile(tabs, "alignment")
    tabs.new_workspace()
    _save_profile(tabs, "alignment")
    assert tabs.workspace_names() == ["alignment", None]


def test_close_workspace_keeps_profile_on_disk(make_tabs):
    tabs = make_tabs()
    _save_profile(tabs, "alignment")
    tabs.new_workspace()
    _save_profile(tabs, "scans")
    assert tabs.close_workspace(0)
    assert tabs.workspace_names() == ["scans"]
    assert "alignment" in list_profiles(NAMESPACE)
    assert get_open_workspaces(NAMESPACE) == (["scans"], "scans")


def test_closing_last_tab_leaves_empty_workspace(make_tabs):
    tabs = make_tabs()
    _save_profile(tabs, "alignment")
    tabs.close_workspace(0)
    assert tabs.count() == 1
    assert tabs.workspace_names() == [None]
    assert "alignment" in list_profiles(NAMESPACE)


def test_close_unsaved_workspace_with_widgets_asks_first(make_tabs, monkeypatch):
    tabs = make_tabs()
    tabs.current_dock_area().new("RingProgressBar")
    tabs.new_workspace()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.No
    )
    assert not tabs.close_workspace(0)
    assert tabs.count() == 2

    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )
    assert tabs.close_workspace(0)
    assert tabs.count() == 1


def test_rename_saves_under_new_name_and_keeps_old_profile(make_tabs):
    tabs = make_tabs()
    _save_profile(tabs, "alignment")
    assert tabs.rename_workspace(0, "alignment_v2")
    assert tabs.tabText(0) == "alignment_v2"
    profiles = list_profiles(NAMESPACE)
    assert "alignment" in profiles and "alignment_v2" in profiles
    assert get_open_workspaces(NAMESPACE) == (["alignment_v2"], "alignment_v2")


def test_rename_untitled_workspace_saves_it(make_tabs, monkeypatch):
    tabs = make_tabs()
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("beamtime", True))
    assert tabs.rename_workspace()
    assert tabs.tabText(0) == "beamtime"
    assert "beamtime" in list_profiles(NAMESPACE)


def test_rename_to_name_open_in_other_tab_is_refused(make_tabs, monkeypatch):
    tabs = make_tabs()
    _save_profile(tabs, "alignment")
    tabs.new_workspace()
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: infos.append(args))
    assert not tabs.rename_workspace(1, "alignment")
    assert infos
    assert tabs.workspace_names() == ["alignment", None]


def test_rename_over_existing_saved_profile_asks_first(make_tabs, monkeypatch):
    tabs = make_tabs()
    _save_profile(tabs, "alignment")
    tabs.close_workspace(0)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.No
    )
    assert not tabs.rename_workspace(0, "alignment")
    assert tabs.workspace_names() == [None]


def test_moving_tabs_updates_persisted_order(make_tabs):
    tabs = make_tabs()
    _save_profile(tabs, "alignment")
    tabs.new_workspace()
    _save_profile(tabs, "scans")
    tabs.tabBar().moveTab(1, 0)
    assert get_open_workspaces(NAMESPACE)[0] == ["scans", "alignment"]


def test_open_menu_lists_saved_profiles(make_tabs):
    tabs = make_tabs()
    _save_profile(tabs, "alignment")
    tabs._populate_open_menu()
    texts = [action.text() for action in tabs._open_menu.actions()]
    assert "New Workspace" in texts
    assert "alignment" in texts
