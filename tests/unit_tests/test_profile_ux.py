# pylint: disable=missing-function-docstring, missing-module-docstring, redefined-outer-name
# pylint: disable=protected-access
import shutil

import pytest
from qtpy.QtCore import QDateTime, Qt
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QDialog

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.widgets.containers.dock_area import profile_utils
from bec_widgets.widgets.containers.dock_area.profile_utils import (
    copy_profile,
    get_profile_info,
    is_quick_select,
    list_profiles,
    list_trashed_profiles,
    profile_origin,
    restore_trashed_profile,
    set_profile_notes,
    trash_profile,
)
from bec_widgets.widgets.containers.dock_area.profile_ux import (
    POLICY,
    ask_profile_name,
    create_profile_library,
    profile_qml,
    profile_qwidget,
    profile_ui_mode,
)
from bec_widgets.widgets.containers.dock_area.profile_ux.common import (
    SECTION_BUNDLED,
    SECTION_MINE,
    SECTION_TRASH,
    ProfileActions,
    ProfileLibraryController,
    check_profile_name,
    relative_time,
    unique_name,
)
from bec_widgets.widgets.containers.dock_area.workspace_tabs import WorkspaceTabs

NAMESPACE = "ux_test"
WIDGET = "Waveform"


@pytest.fixture(autouse=True)
def isolate_profile_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("BECWIDGETS_PROFILE_DIR", str(tmp_path / "profiles_root"))
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    monkeypatch.setattr(profile_utils, "module_profiles_dir", lambda: str(bundled))
    yield bundled


@pytest.fixture(autouse=True)
def default_policy():
    keeps, one_tab = POLICY.rename_keeps_old_profile, POLICY.one_tab_per_profile
    yield
    POLICY.rename_keeps_old_profile, POLICY.one_tab_per_profile = keeps, one_tab


@pytest.fixture
def make_tabs(qtbot, mocked_client, monkeypatch):
    created = []

    def _make(ui="qwidget"):
        monkeypatch.setenv("BEC_PROFILE_UI", ui)
        tabs = WorkspaceTabs(profile_namespace=NAMESPACE, client=mocked_client)
        qtbot.addWidget(tabs)
        tabs.show()
        qtbot.waitExposed(tabs)
        created.append(tabs)
        return tabs

    yield _make
    for tabs in created:
        tabs.cleanup()


def _save(tabs, name, **kwargs):
    tabs.current_dock_area().save_profile(name, show_dialog=False, **kwargs)


def _bundle(tabs, bundled, name):
    """Turn the current layout into a read-only bundled profile called *name*."""
    _save(tabs, "_src")
    (bundled / f"{name}.ini").write_bytes(
        open(profile_utils.runtime_profile_path("_src", NAMESPACE), "rb").read()
    )
    tabs.current_dock_area()._current_profile_name = None
    trash_profile("_src", NAMESPACE)
    shutil.rmtree(profile_utils._trash_root(NAMESPACE))
    list_profiles(NAMESPACE)


def _accept_with(monkeypatch, cls, name, extra=None):
    """Make *cls*.exec accept with *name* typed into the field."""

    def fake_exec(dialog):
        if hasattr(dialog, "name_edit"):
            dialog.name_edit.setText(name)
        else:
            dialog.backend.setName(name)
        if extra:
            extra(dialog)
        return QDialog.DialogCode.Accepted if dialog_ok(dialog) else QDialog.DialogCode.Rejected

    def dialog_ok(dialog):
        return dialog.check.ok if hasattr(dialog, "name_edit") else dialog.backend.check["ok"]

    monkeypatch.setattr(cls, "exec", fake_exec)


################################################################################
# Rules
################################################################################


def test_ui_mode_defaults_to_legacy(monkeypatch):
    monkeypatch.delenv("BEC_PROFILE_UI", raising=False)
    assert profile_ui_mode() == "legacy"
    monkeypatch.setenv("BEC_PROFILE_UI", "QML")
    assert profile_ui_mode() == "qml"
    monkeypatch.setenv("BEC_PROFILE_UI", "nonsense")
    assert profile_ui_mode() == "legacy"


def test_relative_time():
    now = QDateTime.fromString("2026-10-09T12:00:00Z", Qt.DateFormat.ISODate)
    assert relative_time("2026-10-09T11:59:30Z", now) == "just now"
    assert relative_time("2026-10-09T11:15:00Z", now) == "45 min ago"
    assert relative_time("2026-10-09T09:00:00Z", now) == "3 h ago"
    assert relative_time("2026-10-08T09:00:00Z", now) == "yesterday"
    assert relative_time("2026-10-04T12:00:00Z", now) == "5 days ago"
    assert relative_time("garbage", now) == ""


def test_unique_name():
    taken = {"a_copy", "a_copy_2"}
    assert unique_name("a", taken.__contains__) == "a_copy_3"
    assert unique_name("b", taken.__contains__, "custom") == "b_custom"


def test_name_check_basic_rules(make_tabs):
    tabs = make_tabs()
    _save(tabs, "alignment")
    check = lambda text, mode="save", **kw: check_profile_name(  # noqa: E731
        text, mode, namespace=NAMESPACE, **kw
    )
    assert not check("   ").ok
    bad = check("a/b")
    assert not bad.ok and bad.tone == "error" and "/" in bad.message
    assert not check(".hidden").ok
    assert not check("x" * 65).ok
    assert not check("alignment", "rename", original="alignment").ok
    update = check("alignment", current="alignment")
    assert update.ok and update.action == "Save" and not update.replaces
    replace = check("alignment", current="other")
    assert replace.ok and replace.replaces and replace.action == "Replace"
    fresh = check("brand_new")
    assert fresh.ok and fresh.tone == "neutral"


def test_name_check_read_only_suggests_free_name(make_tabs, isolate_profile_storage):
    tabs = make_tabs()
    _bundle(tabs, isolate_profile_storage, "overview")
    result = check_profile_name("overview", "save", namespace=NAMESPACE)
    assert not result.ok
    assert result.suggestion == "overview_custom"


def test_name_check_open_elsewhere_depends_on_policy(make_tabs):
    tabs = make_tabs()
    _save(tabs, "first")
    tabs.new_workspace()
    actions = ProfileActions(tabs.current_dock_area())
    blocked = actions.check("first", "save")
    assert not blocked.ok and "another tab" in blocked.message
    POLICY.one_tab_per_profile = False
    assert actions.check("first", "save").ok


def test_rename_hint_follows_policy(make_tabs):
    tabs = make_tabs()
    _save(tabs, "old")
    keep = check_profile_name("new", "rename", namespace=NAMESPACE, original="old")
    assert "stays in the library" in keep.message
    POLICY.rename_keeps_old_profile = False
    move = check_profile_name("new", "rename", namespace=NAMESPACE, original="old")
    assert "Recently deleted" in move.message


################################################################################
# Storage helpers
################################################################################


def test_trash_and_restore_round_trip(make_tabs):
    tabs = make_tabs()
    _save(tabs, "keep_me")
    tabs.current_dock_area()._current_profile_name = None
    entry = trash_profile("keep_me", NAMESPACE)
    assert entry is not None
    assert "keep_me" not in list_profiles(NAMESPACE)
    assert [t.name for t in list_trashed_profiles(NAMESPACE)] == ["keep_me"]
    assert restore_trashed_profile(entry.token, NAMESPACE) == "keep_me"
    assert "keep_me" in list_profiles(NAMESPACE)
    assert list_trashed_profiles(NAMESPACE) == []


def test_restore_refuses_when_name_is_taken_again(make_tabs):
    tabs = make_tabs()
    _save(tabs, "dup")
    entry = trash_profile("dup", NAMESPACE)
    _save(tabs, "dup")
    with pytest.raises(FileExistsError):
        restore_trashed_profile(entry.token, NAMESPACE)


def test_read_only_profiles_cannot_be_trashed(make_tabs, isolate_profile_storage):
    tabs = make_tabs()
    _bundle(tabs, isolate_profile_storage, "bundled")
    assert trash_profile("bundled", NAMESPACE) is None
    assert "bundled" in list_profiles(NAMESPACE)


def test_copy_profile_and_notes(make_tabs):
    tabs = make_tabs()
    _save(tabs, "src")
    set_profile_notes("src", "my notes", NAMESPACE)
    copy_profile("src", "dst", NAMESPACE)
    assert profile_origin("dst", NAMESPACE) == "settings"
    assert get_profile_info("dst", NAMESPACE).notes == "my notes"
    with pytest.raises(FileExistsError):
        copy_profile("src", "dst", NAMESPACE)
    set_profile_notes("src", "", NAMESPACE)
    assert get_profile_info("src", NAMESPACE).notes == ""


################################################################################
# Library controller
################################################################################


def test_library_sections_and_flags(make_tabs, isolate_profile_storage):
    tabs = make_tabs()
    _bundle(tabs, isolate_profile_storage, "shipped")
    _save(tabs, "mine")
    _save(tabs, "gone")
    tabs.current_dock_area()._current_profile_name = None
    trash_profile("gone", NAMESPACE)
    _save(tabs, "mine")
    controller = ProfileLibraryController(ProfileActions(tabs.current_dock_area()))
    sections = {row["name"]: row["section"] for row in controller.state.rows}
    assert sections == {"mine": SECTION_MINE, "shipped": SECTION_BUNDLED, "gone": SECTION_TRASH}
    selected = controller.state.selected
    assert selected["name"] == "mine" and selected["isCurrent"]
    assert not selected["canDelete"] and "Close the tab" in selected["deleteReason"]


def test_library_delete_and_undo(make_tabs):
    tabs = make_tabs()
    _save(tabs, "closed")
    tabs.new_workspace()
    _save(tabs, "open_one")
    tabs.close_workspace(0)
    controller = ProfileLibraryController(ProfileActions(tabs.current_dock_area()))
    controller.select("p:closed")
    controller.request_delete()
    assert controller.state.pending_delete == "closed"
    controller.confirm_delete()
    assert "closed" not in list_profiles(NAMESPACE)
    assert controller.state.banner.action == "Undo"
    assert any(row["kind"] == "trash" for row in controller.state.rows)
    controller.banner_action()
    assert "closed" in list_profiles(NAMESPACE)
    assert not any(row["kind"] == "trash" for row in controller.state.rows)


def test_library_search_and_pin(make_tabs):
    tabs = make_tabs()
    _save(tabs, "alpha")
    _save(tabs, "beta")
    set_profile_notes("beta", "tomography setup", NAMESPACE)
    controller = ProfileLibraryController(ProfileActions(tabs.current_dock_area()))
    controller.set_query("tomo")
    assert [row["name"] for row in controller.state.rows] == ["beta"]
    assert controller.state.selected["name"] == "beta"
    controller.set_query("zzz")
    assert controller.state.rows == [] and "zzz" in controller.state.empty_text
    controller.set_query("")
    assert is_quick_select("alpha", NAMESPACE)
    controller.toggle_pin("p:alpha")
    assert not is_quick_select("alpha", NAMESPACE)


def test_library_open_in_new_tab_and_here(make_tabs):
    tabs = make_tabs()
    _save(tabs, "one")
    tabs.new_workspace()
    _save(tabs, "two")
    tabs.close_workspace(1)
    controller = ProfileLibraryController(ProfileActions(tabs.current_dock_area()))
    controller.select("p:two")
    controller.open_selected(new_tab=True)
    assert tabs.workspace_names() == ["one", "two"]
    assert tabs.currentIndex() == 1
    tabs.close_workspace(1)
    controller.refresh()
    controller.select("p:two")
    controller.open_selected(new_tab=False)
    assert tabs.workspace_names() == ["two"]


def test_library_rename_keeps_or_moves_old_profile(make_tabs):
    tabs = make_tabs()
    _save(tabs, "first")
    controller = ProfileLibraryController(ProfileActions(tabs.current_dock_area()))
    assert controller.apply_name("rename", "first", "second")
    assert tabs.workspace_names() == ["second"]
    assert {"first", "second"} <= set(list_profiles(NAMESPACE))
    POLICY.rename_keeps_old_profile = False
    assert controller.apply_name("rename", "second", "third")
    assert tabs.workspace_names() == ["third"]
    assert "second" not in list_profiles(NAMESPACE)
    assert "second" in [t.name for t in list_trashed_profiles(NAMESPACE)]


def test_library_rename_closed_profile_copies_it(make_tabs):
    tabs = make_tabs()
    _save(tabs, "closed")
    tabs.current_dock_area()._current_profile_name = None
    controller = ProfileLibraryController(ProfileActions(tabs.current_dock_area()))
    assert controller.apply_name("rename", "closed", "renamed")
    assert "renamed" in list_profiles(NAMESPACE)


def test_library_duplicate_and_replace_goes_to_trash(make_tabs):
    tabs = make_tabs()
    _save(tabs, "base")
    _save(tabs, "target")
    _save(tabs, "base")
    actions = ProfileActions(tabs.current_dock_area())
    text = actions.duplicate("base", "target")
    assert "Recently deleted" in text
    assert [t.name for t in list_trashed_profiles(NAMESPACE)] == ["target"]
    assert "target" in list_profiles(NAMESPACE)


def test_library_revert(make_tabs):
    tabs = make_tabs()
    dock_area = tabs.current_dock_area()
    dock_area.new(WIDGET)
    _save(tabs, "rev")
    dock_area.new(WIDGET)
    assert len(dock_area.dock_list()) == 2
    controller = ProfileLibraryController(ProfileActions(dock_area))
    assert controller.state.selected["canRevert"]
    controller.apply_revert("rev")
    assert len(tabs.current_dock_area().dock_list()) == 1


################################################################################
# Views and wiring
################################################################################


@pytest.mark.parametrize("ui", ["qwidget", "qml"])
def test_library_window_opens_from_toolbar(make_tabs, qtbot, ui):
    tabs = make_tabs(ui)
    _save(tabs, "shown")
    dock_area = tabs.current_dock_area()
    dock_area.show_workspace_manager()
    dialog = dock_area.manage_dialog
    assert dialog is not None and dialog.isVisible()
    assert dialog.controller.state.selected["name"] == "shown"
    if ui == "qml":
        view = dialog.view
        assert view.status() == QQuickWidget.Status.Ready, view.errors()
        assert dialog.backend.rows.rowCount() == 1
    else:
        assert dialog.library.name_label.text() == "shown"
    dialog.close()
    qtbot.waitUntil(lambda: dock_area.manage_dialog is None)


@pytest.mark.parametrize("ui", ["qwidget", "qml"])
def test_toolbar_save_uses_name_dialog(make_tabs, monkeypatch, ui):
    tabs = make_tabs(ui)
    cls = profile_qml.ProfileNameDialog if ui == "qml" else profile_qwidget.ProfileNameDialog
    _accept_with(monkeypatch, cls, "from_dialog")
    tabs.current_dock_area().save_profile_dialog()
    assert tabs.workspace_names() == ["from_dialog"]


@pytest.mark.parametrize("ui", ["qwidget", "qml"])
def test_name_dialog_blocks_read_only_names(make_tabs, isolate_profile_storage, monkeypatch, ui):
    tabs = make_tabs(ui)
    _bundle(tabs, isolate_profile_storage, "shipped")
    cls = profile_qml.ProfileNameDialog if ui == "qml" else profile_qwidget.ProfileNameDialog
    _accept_with(monkeypatch, cls, "shipped")
    assert ask_profile_name(tabs.current_dock_area(), "save") is None
    assert tabs.workspace_names() == [None]


def test_qwidget_name_dialog_states(make_tabs, qtbot):
    tabs = make_tabs()
    _save(tabs, "taken")
    tabs.current_dock_area()._current_profile_name = None
    dialog = profile_qwidget.ProfileNameDialog(ProfileActions(tabs.current_dock_area()), "save")
    qtbot.addWidget(dialog)
    assert not dialog.confirm_button.isEnabled()
    dialog.name_edit.setText("taken")
    assert dialog.confirm_button.isEnabled() and dialog.confirm_button.text() == "Replace"
    dialog.name_edit.setText("bad:name")
    assert not dialog.confirm_button.isEnabled()
    dialog.name_edit.setText("fresh")
    assert dialog.confirm_button.text() == "Save"


def test_tab_rename_uses_name_dialog(make_tabs, monkeypatch):
    tabs = make_tabs()
    _save(tabs, "tab_old")
    _accept_with(monkeypatch, profile_qwidget.ProfileNameDialog, "tab_new")
    assert tabs.rename_workspace(0)
    assert tabs.workspace_names() == ["tab_new"]


def test_revert_from_toolbar_asks_with_revert_dialog(make_tabs, monkeypatch):
    tabs = make_tabs()
    dock_area = tabs.current_dock_area()
    _save(tabs, "rev")
    dock_area.new(WIDGET)
    asked = []
    monkeypatch.setattr(
        profile_qwidget.RevertProfileDialog,
        "exec",
        lambda self: asked.append(True) or QDialog.DialogCode.Rejected,
    )
    dock_area.restore_baseline_profile(show_dialog=True)
    assert asked and len(dock_area.dock_list()) == 1


def test_one_tab_policy_can_be_relaxed(make_tabs):
    tabs = make_tabs()
    _save(tabs, "shared")
    tabs.new_workspace()
    page = tabs.widget(1)
    assert tabs._is_open_elsewhere("shared", page)
    POLICY.one_tab_per_profile = False
    assert not tabs._is_open_elsewhere("shared", page)


def test_library_created_directly(make_tabs, qtbot):
    tabs = make_tabs()
    dialog = create_profile_library(tabs.current_dock_area(), ui="qml")
    qtbot.addWidget(dialog)
    assert dialog.controller.state.empty_text
    dialog.close()
