import pytest
from qtpy.QtCore import QEasingCurve
from qtpy.QtWidgets import QPushButton, QVBoxLayout, QWidget

from bec_widgets.qt_utils.collapsible_panel_manager import (
    CollapsiblePanelManager,
    DimensionAnimator,
)
from bec_widgets.widgets.containers.layout_manager.layout_manager import LayoutManagerWidget


@pytest.fixture
def reference_widget(qtbot):
    widget = QWidget()
    layout = QVBoxLayout(widget)
    btn = QPushButton("Reference")
    layout.addWidget(btn)
    qtbot.addWidget(widget)
    widget.setVisible(True)
    qtbot.waitExposed(widget)
    return widget


@pytest.fixture
def layout_manager(qtbot, reference_widget):
    manager = LayoutManagerWidget()
    qtbot.addWidget(manager)
    manager.add_widget(reference_widget, row=0, col=0)
    manager.setVisible(True)
    qtbot.waitExposed(manager)
    return manager


@pytest.fixture
def panel_manager(layout_manager, reference_widget):
    manager = CollapsiblePanelManager(layout_manager, reference_widget)
    return manager


@pytest.fixture
def test_panel_widget(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    return widget


def test_dimension_animator_width_setting(qtbot, test_panel_widget):
    animator = DimensionAnimator(test_panel_widget, "left")
    animator.panel_width = 100
    assert animator.panel_width == 100
    assert test_panel_widget.width() == 100


def test_dimension_animator_height_setting(qtbot, test_panel_widget):
    animator = DimensionAnimator(test_panel_widget, "top")
    animator.panel_height = 150
    assert animator.panel_height == 150
    assert test_panel_widget.height() == 150


def test_add_panel(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    assert panel_manager.panels["left"]["widget"] == test_panel_widget
    # Initially hidden
    assert not test_panel_widget.isVisible()
    assert test_panel_widget.maximumWidth() == 0


def test_add_panel_no_target_size(panel_manager, test_panel_widget):
    panel_manager.add_panel("top", test_panel_widget)
    assert panel_manager.panels["top"]["target_size"] == 150
    assert not test_panel_widget.isVisible()


def test_add_panel_invalid_direction(panel_manager, test_panel_widget):
    with pytest.raises(ValueError) as exc_info:
        panel_manager.add_panel("invalid", test_panel_widget)
    assert "Direction must be one of 'left', 'right', 'top', 'bottom'." in str(exc_info.value)


def test_toggle_panel_show(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    assert not test_panel_widget.isVisible()

    panel_manager.toggle_panel("left", animation=False)
    assert test_panel_widget.isVisible()


def test_toggle_panel_hide(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("left", animation=False)
    assert test_panel_widget.isVisible()

    panel_manager.toggle_panel("left", animation=False)
    assert not test_panel_widget.isVisible()


def test_toggle_panel_scale(panel_manager, test_panel_widget, reference_widget):
    reference_widget.resize(800, 600)
    panel_manager.add_panel("right", test_panel_widget)
    panel_manager.toggle_panel("right", scale=0.25, animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumWidth() == 200


def test_toggle_panel_ensure_max(panel_manager, test_panel_widget):
    panel_manager.add_panel("bottom", test_panel_widget, target_size=150)
    panel_manager.toggle_panel("bottom", ensure_max=True, animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumHeight() == 150
    panel_manager.toggle_panel("bottom", ensure_max=True, animation=False)
    assert not test_panel_widget.isVisible()
    assert test_panel_widget.maximumHeight() == 16777215


def test_toggle_panel_easing_curve(panel_manager, test_panel_widget):
    panel_manager.add_panel("top", test_panel_widget, target_size=100, duration=500)
    panel_manager.toggle_panel("top", easing_curve=QEasingCurve.OutBounce, animation=True)
    assert panel_manager.animations.get(test_panel_widget) is not None


def test_toggle_nonexistent_panel(panel_manager):
    with pytest.raises(ValueError) as exc_info:
        panel_manager.toggle_panel("invalid")
    assert "No panel found in direction 'invalid'." in str(exc_info.value)


def test_toggle_panel_without_animation(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("left", animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumWidth() == 200
    panel_manager.toggle_panel("left", animation=False)
    assert not test_panel_widget.isVisible()


def test_after_hide_reset(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("left", ensure_max=True, animation=False)
    assert test_panel_widget.isVisible()
    panel_manager.toggle_panel("left", ensure_max=True, animation=False)
    assert not test_panel_widget.isVisible()
    assert test_panel_widget.minimumWidth() == 0
    assert test_panel_widget.maximumWidth() == 0


def test_toggle_panel_repeated(panel_manager, test_panel_widget):
    panel_manager.add_panel("right", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("right", animation=False)
    assert test_panel_widget.isVisible()
    panel_manager.toggle_panel("right", animation=False)
    assert not test_panel_widget.isVisible()
    panel_manager.toggle_panel("right", animation=False)
    assert test_panel_widget.isVisible()


def test_toggle_panel_with_custom_duration(panel_manager, test_panel_widget):
    panel_manager.add_panel("bottom", test_panel_widget, target_size=150, duration=1000)
    panel_manager.toggle_panel("bottom", duration=2000, animation=True)
    animation = panel_manager.animations.get(test_panel_widget)
    assert animation is not None
    assert animation.duration() == 2000


def test_toggle_panel_ensure_max_scale(panel_manager, test_panel_widget, reference_widget):
    reference_widget.resize(1000, 800)
    panel_manager.add_panel("top", test_panel_widget)
    panel_manager.toggle_panel("top", ensure_max=True, scale=0.5, animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumHeight() == 400


def test_no_animation_mode(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("left", animation=False)
    assert test_panel_widget.isVisible()
    panel_manager.toggle_panel("left", animation=False)
    assert not test_panel_widget.isVisible()


def test_toggle_panel_nondefault_easing(panel_manager, test_panel_widget):
    panel_manager.add_panel("right", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("right", easing_curve=QEasingCurve.InCurve, animation=True)
    animation = panel_manager.animations.get(test_panel_widget)
    assert animation is not None
    assert animation.easingCurve() == QEasingCurve.InCurve


def test_toggle_panel_ensure_max_no_animation(panel_manager, test_panel_widget):
    panel_manager.add_panel("bottom", test_panel_widget, target_size=150)
    panel_manager.toggle_panel("bottom", ensure_max=True, animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumHeight() == 150
    panel_manager.toggle_panel("bottom", ensure_max=True, animation=False)
    assert not test_panel_widget.isVisible()
    assert test_panel_widget.maximumHeight() == 16777215


def test_toggle_panel_new_target_size(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("left", target_size=300, animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumWidth() == 300
    panel_manager.toggle_panel("left", animation=False)
    assert not test_panel_widget.isVisible()


def test_toggle_panel_new_duration(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200, duration=300)
    panel_manager.toggle_panel("left", duration=1000, animation=True)
    animation = panel_manager.animations.get(test_panel_widget)
    assert animation.duration() == 1000


def test_toggle_panel_wrong_direction(panel_manager):
    with pytest.raises(ValueError) as exc:
        panel_manager.toggle_panel("unknown_direction")
    assert "No panel found in direction 'unknown_direction'." in str(exc.value)


def test_toggle_panel_no_panels(panel_manager):
    with pytest.raises(ValueError) as exc:
        panel_manager.toggle_panel("top")
    assert "No panel found in direction 'top'." in str(exc.value)


def test_multiple_panels_interaction(panel_manager):
    widget_left = QWidget()
    widget_right = QWidget()
    panel_manager.add_panel("left", widget_left, target_size=200)
    panel_manager.add_panel("right", widget_right, target_size=300)

    panel_manager.toggle_panel("left", animation=False)
    assert widget_left.isVisible()

    panel_manager.toggle_panel("right", animation=False)
    assert widget_right.isVisible()

    panel_manager.toggle_panel("left", animation=False)
    assert not widget_left.isVisible()
    assert widget_right.isVisible()

    panel_manager.toggle_panel("right", animation=False)
    assert not widget_right.isVisible()


def test_panel_manager_custom_easing(panel_manager, test_panel_widget):
    panel_manager.add_panel("top", test_panel_widget, target_size=150)
    panel_manager.toggle_panel("top", easing_curve=QEasingCurve.InQuad, animation=True)
    animation = panel_manager.animations.get(test_panel_widget)
    assert animation is not None
    assert animation.easingCurve() == QEasingCurve.InQuad


def test_toggle_panel_scale_no_animation(panel_manager, test_panel_widget, reference_widget):
    reference_widget.resize(400, 300)
    panel_manager.add_panel("bottom", test_panel_widget)
    panel_manager.toggle_panel("bottom", scale=0.5, animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumHeight() == 150
    panel_manager.toggle_panel("bottom", animation=False)
    assert not test_panel_widget.isVisible()


def test_after_hide_reset_properties(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("left", ensure_max=True, animation=False)
    panel_manager.toggle_panel("left", ensure_max=True, animation=False)
    assert not test_panel_widget.isVisible()
    assert test_panel_widget.minimumWidth() == 0
    assert test_panel_widget.maximumWidth() == 0


def test_toggle_panel_no_animation_show_only(panel_manager, test_panel_widget):
    panel_manager.add_panel("right", test_panel_widget, target_size=100)
    panel_manager.toggle_panel("right", animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumWidth() == 100


def test_toggle_panel_no_animation_hide_only(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=100)
    panel_manager.toggle_panel("left", animation=False)
    assert test_panel_widget.isVisible()
    panel_manager.toggle_panel("left", animation=False)
    assert not test_panel_widget.isVisible()


def test_toggle_panel_easing_inout(panel_manager, test_panel_widget):
    panel_manager.add_panel("top", test_panel_widget, target_size=120)
    panel_manager.toggle_panel("top", easing_curve=QEasingCurve.InOutQuad, animation=True)
    animation = panel_manager.animations.get(test_panel_widget)
    assert animation is not None
    assert animation.easingCurve() == QEasingCurve.InOutQuad


def test_toggle_panel_ensure_max_width(panel_manager, test_panel_widget):
    panel_manager.add_panel("right", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("right", ensure_max=True, animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumWidth() == 200


def test_toggle_panel_invalid_direction_twice(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    with pytest.raises(ValueError) as exc_info:
        panel_manager.toggle_panel("invalid_direction")
    assert "No panel found in direction 'invalid_direction'." in str(exc_info.value)
