import pytest
from qtpy.QtCore import QParallelAnimationGroup
from qtpy.QtWidgets import QLabel

from bec_widgets.applications.navigation_centre.reveal_animator import RevealAnimator

ANIM_TEST_DURATION = 50  # ms


@pytest.fixture
def label(qtbot):
    w = QLabel("Reveal Label")
    qtbot.addWidget(w)
    qtbot.waitExposed(w)
    return w


def _run_group(group: QParallelAnimationGroup, qtbot, duration_ms: int):
    group.start()
    qtbot.wait(duration_ms + 100)


def test_immediate_collapsed_then_revealed(label):
    anim = RevealAnimator(label, duration=ANIM_TEST_DURATION, initially_revealed=False)

    # Initially collapsed
    assert anim.fx.opacity() == pytest.approx(0.0)
    assert label.maximumWidth() == 0
    assert label.maximumHeight() == 0

    # Snap to revealed
    anim.set_immediate(True)
    sh = label.sizeHint()
    assert anim.fx.opacity() == pytest.approx(1.0)
    assert label.maximumWidth() == max(sh.width(), 1)
    assert label.maximumHeight() == max(sh.height(), 1)


def test_reveal_then_collapse_with_animation(label, qtbot):
    anim = RevealAnimator(label, duration=ANIM_TEST_DURATION, initially_revealed=False)

    group = QParallelAnimationGroup()
    anim.setup(True)
    anim.add_to_group(group)
    _run_group(group, qtbot, ANIM_TEST_DURATION)

    sh = label.sizeHint()
    assert anim.fx.opacity() == pytest.approx(1.0)
    assert label.maximumWidth() == max(sh.width(), 1)
    assert label.maximumHeight() == max(sh.height(), 1)

    # Collapse using the SAME group; do not re-add animations to avoid deletion
    anim.setup(False)
    _run_group(group, qtbot, ANIM_TEST_DURATION)

    assert anim.fx.opacity() == pytest.approx(0.0)
    assert label.maximumWidth() == 0
    assert label.maximumHeight() == 0


@pytest.mark.parametrize(
    "flags",
    [
        dict(animate_opacity=False, animate_width=True, animate_height=True),
        dict(animate_opacity=True, animate_width=False, animate_height=True),
        dict(animate_opacity=True, animate_width=True, animate_height=False),
    ],
)
def test_partial_flags_respectively_disable_properties(label, qtbot, flags):
    # Establish initial state
    label.setMaximumWidth(123)
    label.setMaximumHeight(456)

    anim = RevealAnimator(label, duration=10, initially_revealed=False, **flags)

    # Record baseline values for disabled properties
    baseline_opacity = anim.fx.opacity()
    baseline_w = label.maximumWidth()
    baseline_h = label.maximumHeight()

    group = QParallelAnimationGroup()
    anim.setup(True)
    anim.add_to_group(group)
    _run_group(group, qtbot, ANIM_TEST_DURATION)

    sh = label.sizeHint()

    if flags.get("animate_opacity", True):
        assert anim.fx.opacity() == pytest.approx(1.0)
    else:
        # Opacity should remain unchanged
        assert anim.fx.opacity() == pytest.approx(baseline_opacity)

    if flags.get("animate_width", True):
        assert label.maximumWidth() == max(sh.width(), 1)
    else:
        assert label.maximumWidth() == baseline_w

    if flags.get("animate_height", True):
        assert label.maximumHeight() == max(sh.height(), 1)
    else:
        assert label.maximumHeight() == baseline_h


def test_animations_list_and_order(label):
    anim = RevealAnimator(label, duration=ANIM_TEST_DURATION)
    lst = anim.animations()
    # All should be present and in defined order: opacity, height, width
    names = [a.propertyName() for a in lst]
    assert names == [b"opacity", b"maximumHeight", b"maximumWidth"]


@pytest.mark.parametrize(
    "flags,expected",
    [
        (dict(animate_opacity=False), [b"maximumHeight", b"maximumWidth"]),
        (dict(animate_width=False), [b"opacity", b"maximumHeight"]),
        (dict(animate_height=False), [b"opacity", b"maximumWidth"]),
        (dict(animate_opacity=False, animate_width=False, animate_height=True), [b"maximumHeight"]),
        (dict(animate_opacity=False, animate_width=True, animate_height=False), [b"maximumWidth"]),
        (dict(animate_opacity=True, animate_width=False, animate_height=False), [b"opacity"]),
        (dict(animate_opacity=False, animate_width=False, animate_height=False), []),
    ],
)
def test_animations_respects_flags(label, flags, expected):
    anim = RevealAnimator(label, duration=ANIM_TEST_DURATION, **flags)
    names = [a.propertyName() for a in anim.animations()]
    assert names == expected
