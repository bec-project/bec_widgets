import pytest
from qtpy.QtCore import QEasingCurve
from qtpy.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from bec_widgets.qt_utils.collapsible_panel_manager import (
    CollapsiblePanelManager,
    DimensionAnimator,
)
from bec_widgets.widgets.containers.layout_manager.layout_manager import LayoutManagerWidget

# NOTE the following fixtures has to be done with using .show() method, otherwise qt .isVisible() check will not work!


@pytest.fixture
def reference_widget(qtbot):
    widget = QWidget()
    layout = QVBoxLayout(widget)
    btn = QPushButton("Reference")
    layout.addWidget(btn)
    qtbot.addWidget(widget)
    widget.show()
    return widget


@pytest.fixture
def layout_manager(qtbot, reference_widget):
    manager = LayoutManagerWidget()
    qtbot.addWidget(manager)
    manager.show()
    manager.add_widget(reference_widget, row=0, col=0)
    return manager


@pytest.fixture
def panel_manager(layout_manager, reference_widget):
    manager = CollapsiblePanelManager(layout_manager, reference_widget)
    return manager


@pytest.fixture
def test_panel_widget():
    widget = QWidget()
    return widget


def test_dimension_animator_width_setting(test_panel_widget):
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
    # After adding, panel should be hidden and have max width set to 0 (if left/right)
    assert panel_manager.panels["left"]["widget"] == test_panel_widget
    assert not test_panel_widget.isVisible()
    assert test_panel_widget.maximumWidth() == 0


def test_add_panel_no_target_size(panel_manager, test_panel_widget):
    # Using default target size for direction "top"
    panel_manager.add_panel("top", test_panel_widget)
    assert panel_manager.panels["top"]["target_size"] == 150
    assert not test_panel_widget.isVisible()


def test_add_panel_invalid_direction(panel_manager, test_panel_widget):
    with pytest.raises(ValueError) as exc_info:
        panel_manager.add_panel("invalid", test_panel_widget)
    assert "Direction must be one of 'left', 'right', 'top', 'bottom'." in str(exc_info.value)


def test_toggle_panel_show(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    # Initially hidden
    assert not test_panel_widget.isVisible()

    panel_manager.toggle_panel("left", animation=False)
    # After toggle, panel should become visible
    assert test_panel_widget.isVisible()


def test_toggle_panel_hide(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("left", animation=False)
    # Now panel is visible
    assert test_panel_widget.isVisible()

    # Toggle again to hide
    panel_manager.toggle_panel("left", animation=False)
    # Should be invisible after second toggle
    assert not test_panel_widget.isVisible()


def test_toggle_panel_scale(panel_manager, test_panel_widget, reference_widget):
    reference_widget.resize(800, 600)  # Set a known size
    panel_manager.add_panel("right", test_panel_widget)
    # Toggling with scale=0.25 on a right panel should set final width ~ 800 * 0.25 = 200
    panel_manager.toggle_panel("right", scale=0.25, animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumWidth() == 200


def test_toggle_panel_ensure_max(panel_manager, test_panel_widget):
    panel_manager.add_panel("bottom", test_panel_widget, target_size=150)
    # Ensure fixed height after show
    panel_manager.toggle_panel("bottom", ensure_max=True, animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumHeight() == 150
    # Hide again
    panel_manager.toggle_panel("bottom", ensure_max=True, animation=False)
    assert not test_panel_widget.isVisible()
    # After hide, reset to flexible height
    assert test_panel_widget.maximumHeight() == 16777215


def test_toggle_panel_easing_curve(panel_manager, test_panel_widget):
    panel_manager.add_panel("top", test_panel_widget, target_size=100, duration=500)
    # Just ensure no errors raised when using different easing curves
    panel_manager.toggle_panel("top", easing_curve=QEasingCurve.OutBounce, animation=True)
    # Hard to test animation directly, but we can check if animation object is stored
    assert panel_manager.animations.get(test_panel_widget) is not None


def test_toggle_nonexistent_panel(panel_manager):
    with pytest.raises(ValueError) as exc_info:
        panel_manager.toggle_panel("invalid")
    assert "No panel found in direction 'invalid'." in str(exc_info.value)


def test_toggle_panel_without_animation(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("left", animation=False)
    # Visible and max width set
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumWidth() == 200
    # Toggle again without animation to hide instantly
    panel_manager.toggle_panel("left", animation=False)
    assert not test_panel_widget.isVisible()


def test_after_hide_reset(panel_manager, test_panel_widget):
    # Test internal method by simulating scenario
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    # Show panel with ensure_max
    panel_manager.toggle_panel("left", ensure_max=True, animation=False)
    assert test_panel_widget.isVisible()
    # Hide panel with ensure_max
    panel_manager.toggle_panel("left", ensure_max=True, animation=False)
    assert not test_panel_widget.isVisible()
    # After hide reset should restore flexible sizing
    assert test_panel_widget.minimumWidth() == 0
    assert test_panel_widget.maximumWidth() == 0


def test_toggle_panel_repeated(panel_manager, test_panel_widget):
    # Repeated toggles should show/hide correctly
    panel_manager.add_panel("right", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("right", animation=False)
    assert test_panel_widget.isVisible()
    panel_manager.toggle_panel("right", animation=False)
    assert not test_panel_widget.isVisible()
    panel_manager.toggle_panel("right", animation=False)
    assert test_panel_widget.isVisible()


def test_toggle_panel_with_custom_duration(panel_manager, test_panel_widget):
    panel_manager.add_panel("bottom", test_panel_widget, target_size=150, duration=1000)
    # Toggle with overriding duration
    panel_manager.toggle_panel("bottom", duration=2000, animation=True)
    animation = panel_manager.animations.get(test_panel_widget)
    assert animation is not None
    assert animation.duration() == 2000


def test_toggle_panel_ensure_max_scale(panel_manager, test_panel_widget, reference_widget):
    reference_widget.resize(1000, 800)
    panel_manager.add_panel("top", test_panel_widget)
    # With scale=0.5 on top panel, target size = 800 * 0.5 = 400
    panel_manager.toggle_panel("top", ensure_max=True, scale=0.5, animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumHeight() == 400


def test_no_animation_mode(panel_manager, test_panel_widget):
    # When animation=False, panel should jump instantly to final state
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("left", animation=False)
    assert test_panel_widget.isVisible()
    # Check again for no animation hide
    panel_manager.toggle_panel("left", animation=False)
    assert not test_panel_widget.isVisible()


def test_toggle_panel_nondefault_easing(panel_manager, test_panel_widget):
    panel_manager.add_panel("right", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("right", easing_curve=QEasingCurve.InCurve, animation=True)
    animation = panel_manager.animations.get(test_panel_widget)
    assert animation is not None
    # Just ensuring no exceptions and property is set
    assert animation.easingCurve() == QEasingCurve.InCurve


def test_toggle_panel_ensure_max_no_animation(panel_manager, test_panel_widget):
    panel_manager.add_panel("bottom", test_panel_widget, target_size=150)
    # Ensure max with no animation
    panel_manager.toggle_panel("bottom", ensure_max=True, animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumHeight() == 150
    # Toggle off ensure max with no animation
    panel_manager.toggle_panel("bottom", ensure_max=True, animation=False)
    assert not test_panel_widget.isVisible()
    assert test_panel_widget.maximumHeight() == 16777215


def test_toggle_panel_new_target_size(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    # Toggle with different target_size on the fly
    panel_manager.toggle_panel("left", target_size=300, animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumWidth() == 300
    # Hide panel
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
    # Attempting to toggle a panel that was never added
    with pytest.raises(ValueError) as exc:
        panel_manager.toggle_panel("top")
    assert "No panel found in direction 'top'." in str(exc.value)


def test_multiple_panels_interaction(panel_manager):
    widget_left = QWidget()
    widget_right = QWidget()
    panel_manager.add_panel("left", widget_left, target_size=200)
    panel_manager.add_panel("right", widget_right, target_size=300)

    # Toggle left on
    panel_manager.toggle_panel("left", animation=False)
    assert widget_left.isVisible()
    # Toggle right on
    panel_manager.toggle_panel("right", animation=False)
    assert widget_right.isVisible()

    # Hide left
    panel_manager.toggle_panel("left", animation=False)
    assert not widget_left.isVisible()
    assert widget_right.isVisible()

    # Hide right
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
    # scale=0.5 for bottom means target_size=300*0.5=150
    panel_manager.toggle_panel("bottom", scale=0.5, animation=False)
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumHeight() == 150
    # Hide again
    panel_manager.toggle_panel("bottom", animation=False)
    assert not test_panel_widget.isVisible()


def test_after_hide_reset_properties(panel_manager, test_panel_widget):
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    panel_manager.toggle_panel("left", ensure_max=True, animation=False)
    panel_manager.toggle_panel("left", ensure_max=True, animation=False)
    # After hide reset, properties should revert to flexible sizing
    assert not test_panel_widget.isVisible()
    assert test_panel_widget.minimumWidth() == 0
    # If the direction is left, we also check maximumWidth after hiding
    assert test_panel_widget.maximumWidth() == 0


def test_toggle_panel_no_animation_show_only(panel_manager, test_panel_widget):
    # Show panel only, no animation
    panel_manager.add_panel("right", test_panel_widget, target_size=100)
    panel_manager.toggle_panel("right", animation=False)
    # Check visible and dimension
    assert test_panel_widget.isVisible()
    assert test_panel_widget.maximumWidth() == 100


def test_toggle_panel_no_animation_hide_only(panel_manager, test_panel_widget):
    # Show first
    panel_manager.add_panel("left", test_panel_widget, target_size=100)
    panel_manager.toggle_panel("left", animation=False)
    assert test_panel_widget.isVisible()
    # Now hide without animation
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
    # Add a valid panel
    panel_manager.add_panel("left", test_panel_widget, target_size=200)
    # Try toggling invalid direction again
    with pytest.raises(ValueError) as exc_info:
        panel_manager.toggle_panel("invalid_direction")
    assert "No panel found in direction 'invalid_direction'." in str(exc_info.value)


def test_ensure_max_hiding_animation(panel_manager, test_panel_widget):
    # Test that ensure_max mode sets a DimensionAnimator and uses it
    panel_manager.add_panel("top", test_panel_widget, target_size=150)
    panel_manager.toggle_panel("top", ensure_max=True, animation=True)
    assert test_panel_widget.isVisible()
    # Hide with animation
    panel_manager.toggle_panel("top", ensure_max=True, animation=True)
    anim = panel_manager.animations.get(test_panel_widget)
    assert anim is not None
