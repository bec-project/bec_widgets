from typing import Literal

import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from bec_widgets.qt_utils.side_panel import SidePanel


@pytest.fixture(params=["left", "right", "top", "bottom"])
def side_panel_fixture(qtbot, request):
    """
    Parametrized fixture to create SidePanel with different orientations.

    Yields:
        tuple: (SidePanel instance, orientation string)
    """
    orientation: Literal["left", "right", "top", "bottom"] = request.param
    panel = SidePanel(orientation=orientation)
    qtbot.addWidget(panel)
    qtbot.waitExposed(panel)
    yield panel, orientation


@pytest.fixture
def menu_widget(qtbot):
    """Fixture to create a simple widget to add to the SidePanel."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    label = QLabel("Test Widget")
    layout.addWidget(label)
    widget.setLayout(layout)
    return widget


def test_initialization(side_panel_fixture):
    """Test that SidePanel initializes correctly with different orientations."""
    panel, orientation = side_panel_fixture

    assert panel._orientation == orientation
    assert panel.panel_max_width == 200
    assert panel.animation_duration == 200
    assert panel.animations_enabled is True
    assert panel.panel_visible is False
    assert panel.current_action is None
    assert panel.current_index is None
    assert panel.switching_actions is False

    if orientation in ("left", "right"):
        assert panel.toolbar.orientation() == Qt.Vertical
        assert isinstance(panel.main_layout, QHBoxLayout)
    else:
        assert panel.toolbar.orientation() == Qt.Horizontal
        assert isinstance(panel.main_layout, QVBoxLayout)


def test_set_panel_max_width(side_panel_fixture, qtbot):
    """Test setting the panel_max_width property."""
    panel, orientation = side_panel_fixture
    new_max_width = 300
    panel.panel_max_width = new_max_width
    qtbot.wait(100)

    assert panel.panel_max_width == new_max_width
    if orientation in ("left", "right"):
        assert panel.stack_widget.maximumWidth() == new_max_width
    else:
        assert panel.stack_widget.maximumHeight() == new_max_width


def test_set_animation_duration(side_panel_fixture, qtbot):
    """Test setting the animationDuration property."""
    panel, _ = side_panel_fixture
    new_duration = 500
    panel.animation_duration = new_duration
    qtbot.wait(100)

    assert panel.animation_duration == new_duration
    assert panel.menu_anim.duration() == new_duration


def test_set_animations_enabled(side_panel_fixture, qtbot):
    """Test setting the animationsEnabled property."""
    panel, _ = side_panel_fixture
    panel.animationsEnabled = False
    qtbot.wait(100)

    assert panel.animationsEnabled is False

    panel.animationsEnabled = True
    qtbot.wait(100)

    assert panel.animationsEnabled is True


def test_show_hide_panel_with_animation(side_panel_fixture, qtbot):
    """Test showing and hiding the panel with animations enabled."""
    panel, orientation = side_panel_fixture
    panel.animationsEnabled = True

    # Show panel
    panel.show_panel(0)
    qtbot.wait(panel.animation_duration + 100)  # Wait for animation to complete

    final_size = panel.panel_max_width
    if orientation in ("left", "right"):
        assert panel.panel_width == final_size
    else:
        assert panel.panel_height == final_size
    assert panel.panel_visible is True

    # Hide panel
    panel.hide_panel()
    qtbot.wait(panel.animation_duration + 100)  # Wait for animation to complete

    if orientation in ("left", "right"):
        assert panel.panel_width == 0
    else:
        assert panel.panel_height == 0
    assert panel.panel_visible is False


def test_add_menu(side_panel_fixture, menu_widget, qtbot):
    """Test adding a menu to the SidePanel."""
    panel, _ = side_panel_fixture
    initial_count = panel.stack_widget.count()

    panel.add_menu(
        action_id="test_action",
        icon_name="counter_1",
        tooltip="Test Tooltip",
        widget=menu_widget,
        title="Test Panel",
    )
    qtbot.wait(100)

    assert panel.stack_widget.count() == initial_count + 1
    # Verify the action is added to the toolbar
    action = panel.toolbar.widgets.get("test_action")
    assert action is not None
    assert action.tooltip == "Test Tooltip"
    assert action.action in panel.toolbar.actions()


def test_toggle_action_show_panel(side_panel_fixture, menu_widget, qtbot):
    """Test that toggling an action shows the corresponding panel."""
    panel, _ = side_panel_fixture

    panel.add_menu(
        action_id="toggle_action",
        icon_name="counter_1",
        tooltip="Toggle Tooltip",
        widget=menu_widget,
        title="Toggle Panel",
    )
    qtbot.wait(100)

    action = panel.toolbar.widgets.get("toggle_action")
    assert action is not None

    # Initially, panel should be hidden
    assert panel.panel_visible is False

    # Toggle the action to show the panel
    action.action.trigger()
    qtbot.wait(panel.animation_duration + 100)

    assert panel.panel_visible is True
    assert panel.current_action == action.action
    assert panel.current_index == panel.stack_widget.count() - 1

    # Toggle the action again to hide the panel
    action.action.trigger()
    qtbot.wait(panel.animation_duration + 100)

    assert panel.panel_visible is False
    assert panel.current_action is None
    assert panel.current_index is None


def test_switch_actions(side_panel_fixture, menu_widget, qtbot):
    """Test switching between multiple actions and panels."""
    panel, _ = side_panel_fixture

    # Add two menus
    panel.add_menu(
        action_id="action1",
        icon_name="counter_1",
        tooltip="Tooltip1",
        widget=menu_widget,
        title="Panel 1",
    )
    panel.add_menu(
        action_id="action2",
        icon_name="counter_2",
        tooltip="Tooltip2",
        widget=menu_widget,
        title="Panel 2",
    )
    qtbot.wait(100)

    action1 = panel.toolbar.widgets.get("action1")
    action2 = panel.toolbar.widgets.get("action2")
    assert action1 is not None
    assert action2 is not None

    # Activate first action
    action1.action.trigger()
    qtbot.wait(panel.animation_duration + 100)
    assert panel.panel_visible is True
    assert panel.current_action == action1.action
    assert panel.current_index == 0

    # Activate second action
    action2.action.trigger()
    qtbot.wait(panel.animation_duration + 100)
    assert panel.panel_visible is True
    assert panel.current_action == action2.action
    assert panel.current_index == 1

    # Deactivate second action
    action2.action.trigger()
    qtbot.wait(panel.animation_duration + 100)
    assert panel.panel_visible is False
    assert panel.current_action is None
    assert panel.current_index is None


def test_multiple_add_menu(side_panel_fixture, menu_widget, qtbot):
    """Test adding multiple menus and ensure they are all added correctly."""
    panel, _ = side_panel_fixture
    initial_count = panel.stack_widget.count()

    for i in range(3):
        panel.add_menu(
            action_id=f"action{i}",
            icon_name=f"counter_{i}",
            tooltip=f"Tooltip{i}",
            widget=menu_widget,
            title=f"Panel {i}",
        )
        qtbot.wait(100)
        assert panel.stack_widget.count() == initial_count + i + 1
        action = panel.toolbar.widgets.get(f"action{i}")
        assert action is not None
        assert action.tooltip == f"Tooltip{i}"
        assert action.action in panel.toolbar.actions()


def test_switch_to_method(side_panel_fixture, menu_widget, qtbot):
    """Test the switch_to method to change panels without animation."""
    panel, _ = side_panel_fixture

    # Add two menus
    panel.add_menu(
        action_id="action1",
        icon_name="counter_1",
        tooltip="Tooltip1",
        widget=menu_widget,
        title="Panel 1",
    )
    panel.add_menu(
        action_id="action2",
        icon_name="counter_2",
        tooltip="Tooltip2",
        widget=menu_widget,
        title="Panel 2",
    )
    qtbot.wait(100)

    # Show first panel
    panel.show_panel(0)
    qtbot.wait(panel.animation_duration + 100)
    assert panel.current_index == 0

    # Switch to second panel
    panel.switch_to(1)
    qtbot.wait(100)
    assert panel.current_index == 1


def test_animation_enabled_parametrization(qtbot):
    """Test SidePanel with animations enabled and disabled."""
    for animations_enabled in [True, False]:
        panel = SidePanel(animations_enabled=animations_enabled)
        qtbot.addWidget(panel)
        qtbot.waitExposed(panel)

        assert panel.animations_enabled == animations_enabled

        panel.close()


def test_orientation_layouts(qtbot):
    """Test that the layouts are correctly set based on orientation."""
    orientations = {
        "left": ("horizontal", Qt.Vertical),
        "right": ("horizontal", Qt.Vertical),
        "top": ("vertical", Qt.Horizontal),
        "bottom": ("vertical", Qt.Horizontal),
    }

    for orientation, (main_layout_dir, toolbar_orientation) in orientations.items():
        panel = SidePanel(orientation=orientation)
        qtbot.addWidget(panel)
        qtbot.waitExposed(panel)

        # Verify main layout direction
        if main_layout_dir == "horizontal":
            assert isinstance(panel.main_layout, QHBoxLayout)
        else:
            assert isinstance(panel.main_layout, QVBoxLayout)

        # Verify toolbar orientation
        bar_orientation = panel.toolbar.orientation()
        assert bar_orientation == toolbar_orientation

        panel.close()


def test_panel_width_height_properties(side_panel_fixture, qtbot):
    """Test that setting panel_width and panel_height works correctly."""
    panel, orientation = side_panel_fixture

    if orientation in ("left", "right"):
        panel.panel_width = 150
        qtbot.wait(100)
        assert panel.panel_width == 150
        assert panel.stack_widget.width() == 150
    else:
        panel.panel_height = 150
        qtbot.wait(100)
        assert panel.panel_height == 150
        assert panel.stack_widget.height() == 150


def test_no_panel_initially(side_panel_fixture, qtbot):
    """Test that the panel is initially hidden."""
    panel, orientation = side_panel_fixture

    if orientation in ("left", "right"):
        assert panel.panel_width == 0
    else:
        assert panel.panel_height == 0
    assert panel.panel_visible is False


def test_add_multiple_menus(side_panel_fixture, menu_widget, qtbot):
    """Test adding multiple menus and ensure they are all added correctly."""
    panel, _ = side_panel_fixture
    initial_count = panel.stack_widget.count()

    for i in range(3):
        panel.add_menu(
            action_id=f"action{i}",
            icon_name=f"counter_{i}",
            tooltip=f"Tooltip{i}",
            widget=menu_widget,
            title=f"Panel {i}",
        )
        qtbot.wait(100)
        assert panel.stack_widget.count() == initial_count + i + 1
        action = panel.toolbar.widgets.get(f"action{i}")
        assert action is not None
        assert action.tooltip == f"Tooltip{i}"
        assert action.action in panel.toolbar.actions()
