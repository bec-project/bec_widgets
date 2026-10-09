# pylint: disable=missing-function-docstring, missing-module-docstring, redefined-outer-name
from unittest import mock

import pytest
from qtpy.QtWidgets import QApplication

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea
from bec_widgets.widgets.containers.dock_area.profile_loading import loader as loader_module
from bec_widgets.widgets.containers.dock_area.profile_loading.common import (
    LOADING_MODE_ENV,
    LOADING_UI_ENV,
    skeleton_kind,
)
from bec_widgets.widgets.containers.dock_area.profile_loading.placeholder import (
    DockPlaceholder,
    SkeletonPlaceholder,
)
from bec_widgets.widgets.containers.dock_area.profile_utils import (
    open_runtime_settings,
    read_manifest,
)
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_bar import RingProgressBar


@pytest.fixture(autouse=True)
def isolate_profile_storage(tmp_path, monkeypatch):
    root = tmp_path / "profiles_root"
    root.mkdir()
    monkeypatch.setenv("BECWIDGETS_PROFILE_DIR", str(root))
    monkeypatch.delenv(LOADING_MODE_ENV, raising=False)
    monkeypatch.delenv(LOADING_UI_ENV, raising=False)


@pytest.fixture
def dock_area(qtbot, mocked_client):
    area = create_widget(qtbot, BECDockArea, client=mocked_client, startup_profile=None)
    area.resize(1000, 700)
    yield area


def _build_profile(area: BECDockArea, name: str) -> dict[str, str]:
    """Save a profile with a titled waveform and two ring progress bars; return name -> class."""
    waveform = area.new("Waveform", object_name="plot")
    waveform.title = "Saved title"
    area.new("RingProgressBar", object_name="ring_a", where="bottom")
    area.new("RingProgressBar", object_name="ring_b", relative_to="ring_a", where="right")
    QApplication.processEvents()
    area.save_profile(name, show_dialog=False)
    return {"plot": "Waveform", "ring_a": "RingProgressBar", "ring_b": "RingProgressBar"}


def _switch_away(area: BECDockArea, qtbot) -> None:
    area.delete_all()
    area.new("RingProgressBar", object_name="other_ring")
    area.save_profile("other", show_dialog=False)
    area.load_profile("other")
    qtbot.wait(10)


def _placeholders(area: BECDockArea) -> list[DockPlaceholder]:
    return [d.widget() for d in area.dock_list() if isinstance(d.widget(), DockPlaceholder)]


def test_load_profile_builds_every_widget_before_returning(dock_area, qtbot):
    expected = _build_profile(dock_area, "bench")
    _switch_away(dock_area, qtbot)

    with qtbot.waitSignal(dock_area.profile_load_finished, timeout=1000) as blocker:
        dock_area.load_profile("bench")

    assert blocker.args == ["bench"]
    widgets = dock_area.widget_map()
    assert {name: type(w).__name__ for name, w in widgets.items()} == expected
    assert not _placeholders(dock_area)
    assert widgets["plot"].title == "Saved title"
    assert not dock_area.profile_load_in_progress


def test_progressive_load_shows_skeleton_then_fills(dock_area, qtbot):
    expected = _build_profile(dock_area, "bench")
    _switch_away(dock_area, qtbot)

    dock_area.load_profile_progressive("bench")

    # The layout exists right away, held by placeholders that know what they stand for
    placeholders = _placeholders(dock_area)
    assert {p.profile_object_name: p.profile_widget_class for p in placeholders} == expected
    assert dock_area.profile_load_in_progress
    assert dock_area._current_profile_name == "bench"

    qtbot.waitUntil(lambda: not dock_area.profile_load_in_progress, timeout=5000)
    assert not _placeholders(dock_area)
    widgets = dock_area.widget_map()
    assert isinstance(widgets["plot"], Waveform)
    assert widgets["plot"].title == "Saved title"
    assert isinstance(widgets["ring_b"], RingProgressBar)


def test_progressive_load_reports_progress(dock_area, qtbot):
    _build_profile(dock_area, "bench")
    _switch_away(dock_area, qtbot)
    reports = []

    dock_area.load_profile_progressive("bench")
    dock_area._profile_load_job.progress.connect(lambda *args: reports.append(args))
    qtbot.waitUntil(lambda: not dock_area.profile_load_in_progress, timeout=5000)

    assert [done for done, _total, _next in reports] == [1, 2, 3, 3]
    assert all(total == 3 for _done, total, _next in reports)
    assert not dock_area._profile_load_progress._show_timer.isActive()


def test_cancel_leaves_load_now_placeholders(dock_area, qtbot):
    _build_profile(dock_area, "bench")
    _switch_away(dock_area, qtbot)

    with mock.patch.object(loader_module.ProfileLoadJob, "_step"):
        dock_area.load_profile_progressive("bench")
    dock_area.cancel_profile_load()

    placeholders = _placeholders(dock_area)
    assert len(placeholders) == 3
    assert {p.state for p in placeholders} == {"paused"}
    assert not dock_area.profile_load_in_progress

    placeholders[0].load_requested.emit(placeholders[0].profile_object_name)
    assert len(_placeholders(dock_area)) == 2


def test_snapshot_mid_load_keeps_unbuilt_widgets(dock_area, qtbot):
    _build_profile(dock_area, "bench")
    _switch_away(dock_area, qtbot)

    with mock.patch.object(loader_module.ProfileLoadJob, "_step"):
        dock_area.load_profile_progressive("bench")
    dock_area.cancel_profile_load()
    dock_area.save_profile("bench_copy", show_dialog=False)

    settings = open_runtime_settings("bench_copy", namespace=dock_area.profile_namespace)
    classes = {item["object_name"]: item["widget_class"] for item in read_manifest(settings)}
    assert classes == {"plot": "Waveform", "ring_a": "RingProgressBar", "ring_b": "RingProgressBar"}
    # The unbuilt waveform's saved state was carried over into the new profile
    assert any(key.endswith("plot/title") for key in settings.allKeys())


def test_switching_mid_load_discards_the_running_load(dock_area, qtbot):
    _build_profile(dock_area, "bench")
    _switch_away(dock_area, qtbot)

    with mock.patch.object(loader_module.ProfileLoadJob, "_step"):
        dock_area.load_profile_progressive("bench")
    first_job = dock_area._profile_load_job
    dock_area.load_profile("other")

    assert dock_area._profile_load_job is not first_job
    assert set(dock_area.widget_map()) == {"other_ring"}
    # Leaving "bench" mid-load saved it with all of its docks
    settings = open_runtime_settings("bench", namespace=dock_area.profile_namespace)
    assert {item["object_name"] for item in read_manifest(settings)} == {"plot", "ring_a", "ring_b"}


def test_failing_widget_does_not_abort_the_profile(dock_area, qtbot, monkeypatch):
    _build_profile(dock_area, "bench")
    _switch_away(dock_area, qtbot)
    original = loader_module.widget_handler.create_widget

    def create(widget_type, **kwargs):
        if widget_type == "Waveform":
            raise RuntimeError("device missing")
        return original(widget_type=widget_type, **kwargs)

    monkeypatch.setattr(loader_module.widget_handler, "create_widget", create)
    dock_area.load_profile("bench")

    failed = _placeholders(dock_area)
    assert [(p.profile_object_name, p.state, p.message) for p in failed] == [
        ("plot", "failed", "device missing")
    ]
    assert set(dock_area.widget_map()) == {"ring_a", "ring_b"}


def test_toolbar_combo_switches_progressively(dock_area, qtbot):
    _build_profile(dock_area, "bench")
    _switch_away(dock_area, qtbot)
    combo = dock_area.toolbar.components.get_action("workspace_combo").widget

    with mock.patch.object(dock_area, "load_profile_progressive") as load:
        combo.currentTextChanged.emit("bench")

    load.assert_called_once_with("bench")


def test_legacy_pipeline_still_available(dock_area, qtbot, monkeypatch):
    expected = _build_profile(dock_area, "bench")
    _switch_away(dock_area, qtbot)
    monkeypatch.setenv(LOADING_MODE_ENV, "legacy")

    with mock.patch.object(loader_module.ProfileLoadJob, "build_skeleton") as skeleton:
        dock_area.load_profile_progressive("bench")

    skeleton.assert_not_called()
    assert {n: type(w).__name__ for n, w in dock_area.widget_map().items()} == expected


def test_qml_variant(dock_area, qtbot, monkeypatch):
    from bec_widgets.widgets.containers.dock_area.profile_loading.qml_variant import (
        QmlProfileLoadProgress,
        QmlSkeletonPlaceholder,
    )

    _build_profile(dock_area, "bench")
    _switch_away(dock_area, qtbot)
    monkeypatch.setenv(LOADING_UI_ENV, "qml")
    dock_area._profile_load_progress = None

    with mock.patch.object(loader_module.ProfileLoadJob, "_step"):
        dock_area.load_profile_progressive("bench")
    placeholders = _placeholders(dock_area)
    assert placeholders and all(isinstance(p, QmlSkeletonPlaceholder) for p in placeholders)
    assert isinstance(dock_area._profile_load_progress, QmlProfileLoadProgress)

    placeholders[0].set_state("failed", "boom")
    root = placeholders[0]._view.rootObject()
    assert root.property("loadState") == "failed"
    assert root.property("message") == "boom"

    dock_area._profile_load_job.run_to_completion()
    assert not _placeholders(dock_area)


def test_placeholder_states_and_kinds(qtbot):
    placeholder = SkeletonPlaceholder("BECQueue", "queue", "edit_note")
    qtbot.addWidget(placeholder)
    assert placeholder.property("skip_settings") is True
    assert placeholder.ICON_NAME == "edit_note"
    assert placeholder.state == "queued"
    placeholder.set_state("paused")
    assert placeholder._action.isVisibleTo(placeholder)
    with qtbot.waitSignal(placeholder.load_requested) as blocker:
        placeholder._action.click()
    assert blocker.args == ["queue"]
    assert skeleton_kind("Waveform") == "plot"
    assert skeleton_kind("BECQueue") == "list"
    assert skeleton_kind("ScanControl") == "form"


def test_delete_all_closes_every_widget(dock_area, qtbot):
    _build_profile(dock_area, "bench")
    widgets = list(dock_area.widget_list())

    dock_area.delete_all()

    assert dock_area.dock_list() == []
    assert all(w._destroyed for w in widgets)
