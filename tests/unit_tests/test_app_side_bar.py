import pytest
from qtpy.QtCore import QParallelAnimationGroup, QSize

from bec_widgets.applications.navigation_centre.side_bar import SideBar
from bec_widgets.applications.navigation_centre.side_bar_components import (
    NavigationItem,
    SectionHeader,
)

ANIM_TEST_DURATION = 60  # ms


def _run(group: QParallelAnimationGroup, qtbot, duration=ANIM_TEST_DURATION):
    group.start()
    qtbot.wait(duration + 100)


@pytest.fixture
def header(qtbot):
    w = SectionHeader(text="Group", anim_duration=ANIM_TEST_DURATION)
    qtbot.addWidget(w)
    qtbot.waitExposed(w)
    return w


def test_section_header_initial_state_collapsed(header):
    # RevealAnimator is initially collapsed for the label
    assert header.lbl.maximumWidth() == 0
    assert header.lbl.maximumHeight() == 0


def test_section_header_animates_reveal_and_hide(header, qtbot):
    group = QParallelAnimationGroup()
    for anim in header.build_animations():
        group.addAnimation(anim)

    # Expand
    header.setup_animations(True)
    _run(group, qtbot)
    sh = header.lbl.sizeHint()
    assert header.lbl.maximumWidth() >= sh.width()
    assert header.lbl.maximumHeight() >= sh.height()

    # Collapse
    header.setup_animations(False)
    _run(group, qtbot)
    assert header.lbl.maximumWidth() == 0
    assert header.lbl.maximumHeight() == 0


@pytest.fixture
def nav(qtbot):
    w = NavigationItem(
        title="Counter", icon_name="widgets", mini_text="cnt", anim_duration=ANIM_TEST_DURATION
    )
    qtbot.addWidget(w)
    qtbot.waitExposed(w)
    return w


def test_build_animations_contains(nav):
    lst = nav.build_animations()
    assert len(lst) == 5


def test_setup_animations_changes_targets(nav, qtbot):
    group = QParallelAnimationGroup()
    for a in nav.build_animations():
        group.addAnimation(a)

    # collapsed -> expanded
    nav.setup_animations(True)
    _run(group, qtbot)

    sh_title = nav.title_lbl.sizeHint()
    assert nav.title_lbl.maximumWidth() >= sh_title.width()
    assert nav.mini_lbl.maximumHeight() == 0
    assert nav.icon_btn.iconSize() == QSize(26, 26)

    # expanded -> collapsed
    nav.setup_animations(False)
    _run(group, qtbot)
    assert nav.title_lbl.maximumWidth() == 0
    sh_mini = nav.mini_lbl.sizeHint()
    assert nav.mini_lbl.maximumHeight() >= sh_mini.height()
    assert nav.icon_btn.iconSize() == QSize(20, 20)


def test_activation_signal_emits(nav, qtbot):
    with qtbot.waitSignal(nav.activated, timeout=1000):
        nav.icon_btn.click()


@pytest.fixture
def sidebar(qtbot):
    sb = SideBar(title="Controls", anim_duration=ANIM_TEST_DURATION)
    qtbot.addWidget(sb)
    qtbot.waitExposed(sb)
    return sb


def test_add_section_and_separator(sidebar):
    sec = sidebar.add_section("Group A", id="group_a")
    assert sec is not None
    sep = sidebar.add_separator()
    assert sep is not None
    assert sidebar.content_layout.indexOf(sep) != -1


def test_add_item_top_and_bottom_positions(sidebar):
    top_item = sidebar.add_item(icon="widgets", title="Top", id="top")
    bottom_item = sidebar.add_item(icon="widgets", title="Bottom", id="bottom", from_top=False)

    i_spacer = sidebar.content_layout.indexOf(sidebar._bottom_spacer)
    i_top = sidebar.content_layout.indexOf(top_item)
    i_bottom = sidebar.content_layout.indexOf(bottom_item)

    assert i_top != -1 and i_bottom != -1
    assert i_bottom > i_spacer  # bottom items go after the spacer


def test_selection_exclusive_and_nonexclusive(sidebar, qtbot):
    a = sidebar.add_item(icon="widgets", title="A", id="a", exclusive=True)
    b = sidebar.add_item(icon="widgets", title="B", id="b", exclusive=True)
    c = sidebar.add_item(icon="widgets", title="C", id="c", exclusive=False)

    c._emit_activated()
    qtbot.wait(10)
    assert c.is_active() is True

    a._emit_activated()
    qtbot.wait(10)
    assert a.is_active() is True
    assert b.is_active() is False
    assert c.is_active() is True

    b._emit_activated()
    qtbot.wait(200)
    assert a.is_active() is False
    assert b.is_active() is True
    assert c.is_active() is True


def test_on_expand_configures_targets_and_shows_title(sidebar, qtbot):
    # Start collapsed
    assert sidebar._is_expanded is False
    start_w = sidebar.width()

    sidebar.on_expand()

    assert sidebar.width_anim.startValue() == start_w
    assert sidebar.width_anim.endValue() == sidebar._expanded_width
    assert sidebar.title_anim.endValue() == 1.0


def test__on_anim_finished_hides_on_collapse_and_resets_alignment(sidebar, qtbot):
    # Add one item so set_visible is called on components too
    item = sidebar.add_item(icon="widgets", title="Item", id="item")

    # Expand first
    sidebar.on_expand()
    qtbot.wait(ANIM_TEST_DURATION + 150)
    assert sidebar._is_expanded is True

    # Now collapse
    sidebar.on_expand()
    # Wait for animation group to finish and _on_anim_finished to run
    with qtbot.waitSignal(sidebar.group.finished, timeout=2000):
        pass

    # Collapsed state
    assert sidebar._is_expanded is False


def test_dark_mode_item_is_action(sidebar, qtbot, monkeypatch):
    dm = sidebar.add_dark_mode_item()

    called = {"toggled": False}

    def fake_apply(theme):
        called["toggled"] = True

    monkeypatch.setattr("bec_widgets.utils.colors.apply_theme", fake_apply, raising=False)

    before = dm.is_active()
    dm._emit_activated()
    qtbot.wait(200)
    assert called["toggled"] is True
    assert dm.is_active() == before
