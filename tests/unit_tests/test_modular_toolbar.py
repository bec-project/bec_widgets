from typing import Literal

import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QComboBox, QLabel, QToolButton, QWidget

from bec_widgets.qt_utils.toolbar import (
    DeviceSelectionAction,
    ExpandableMenuAction,
    IconAction,
    MaterialIconAction,
    ModularToolBar,
    SeparatorAction,
    WidgetAction,
)


@pytest.fixture
def dummy_widget(qtbot):
    """Fixture to create a simple widget to be used as target widget."""
    widget = QWidget()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


@pytest.fixture(params=["horizontal", "vertical"])
def toolbar_fixture(qtbot, request, dummy_widget):
    """Parametrized fixture to create a ModularToolBar with different orientations."""
    orientation: Literal["horizontal", "vertical"] = request.param
    toolbar = ModularToolBar(
        target_widget=dummy_widget,
        orientation=orientation,
        background_color="rgba(255, 255, 255, 255)",  # White background for testing
    )
    qtbot.addWidget(toolbar)
    qtbot.waitExposed(toolbar)
    yield toolbar
    toolbar.close()


@pytest.fixture
def separator_action():
    """Fixture to create a SeparatorAction."""
    return SeparatorAction()


@pytest.fixture
def icon_action():
    """Fixture to create an IconAction."""
    return IconAction(icon_path="assets/BEC-Icon.png", tooltip="Test Icon Action", checkable=True)


@pytest.fixture
def material_icon_action():
    """Fixture to create a MaterialIconAction."""
    return MaterialIconAction(
        icon_name="home", tooltip="Test Material Icon Action", checkable=False
    )


@pytest.fixture
def device_selection_action():
    """Fixture to create a DeviceSelectionAction."""
    device_combobox = QComboBox()
    device_combobox.addItems(["Device 1", "Device 2", "Device 3"])
    device_combobox.setCurrentIndex(0)
    return DeviceSelectionAction(label="Select Device:", device_combobox=device_combobox)


@pytest.fixture
def widget_action():
    """Fixture to create a WidgetAction."""
    sample_widget = QLabel("Sample Widget")
    return WidgetAction(label="Sample Label:", widget=sample_widget)


@pytest.fixture
def expandable_menu_action():
    """Fixture to create an ExpandableMenuAction."""
    action1 = MaterialIconAction(icon_name="counter_1", tooltip="Menu Action 1", checkable=False)
    action2 = MaterialIconAction(icon_name="counter_2", tooltip="Menu Action 2", checkable=True)
    actions = {"action1": action1, "action2": action2}
    return ExpandableMenuAction(
        label="Expandable Menu", actions=actions, icon_path="assets/BEC-Icon.png"
    )


def test_initialization(toolbar_fixture):
    """Test that ModularToolBar initializes correctly with different orientations."""
    toolbar = toolbar_fixture
    if toolbar.orientation() == Qt.Horizontal:
        assert toolbar.orientation() == Qt.Horizontal
    elif toolbar.orientation() == Qt.Vertical:
        assert toolbar.orientation() == Qt.Vertical
    else:
        pytest.fail("Toolbar orientation is neither horizontal nor vertical.")
    assert toolbar.background_color == "rgba(255, 255, 255, 255)"
    assert toolbar.widgets == {}
    assert not toolbar.isMovable()
    assert not toolbar.isFloatable()


def test_set_background_color(toolbar_fixture):
    """Test setting the background color of the toolbar."""
    toolbar = toolbar_fixture
    new_color = "rgba(0, 0, 0, 255)"  # Black
    toolbar.set_background_color(new_color)
    assert toolbar.background_color == new_color
    # Verify stylesheet
    expected_style = f"QToolBar {{ background-color: {new_color}; border: none; }}"
    assert toolbar.styleSheet() == expected_style


def test_set_orientation(toolbar_fixture, qtbot, dummy_widget):
    """Test changing the orientation of the toolbar."""
    toolbar = toolbar_fixture
    if toolbar.orientation() == Qt.Horizontal:
        new_orientation = "vertical"
    else:
        new_orientation = "horizontal"
    toolbar.set_orientation(new_orientation)
    qtbot.wait(100)
    if new_orientation == "horizontal":
        assert toolbar.orientation() == Qt.Horizontal
    else:
        assert toolbar.orientation() == Qt.Vertical


def test_add_action(
    toolbar_fixture, icon_action, separator_action, material_icon_action, dummy_widget
):
    """Test adding different types of actions to the toolbar."""
    toolbar = toolbar_fixture

    # Add IconAction
    toolbar.add_action("icon_action", icon_action, dummy_widget)
    assert "icon_action" in toolbar.widgets
    assert toolbar.widgets["icon_action"] == icon_action
    assert icon_action.action in toolbar.actions()

    # Add SeparatorAction
    toolbar.add_action("separator_action", separator_action, dummy_widget)
    assert "separator_action" in toolbar.widgets
    assert toolbar.widgets["separator_action"] == separator_action

    # Add MaterialIconAction
    toolbar.add_action("material_icon_action", material_icon_action, dummy_widget)
    assert "material_icon_action" in toolbar.widgets
    assert toolbar.widgets["material_icon_action"] == material_icon_action
    assert material_icon_action.action in toolbar.actions()


def test_hide_show_action(toolbar_fixture, icon_action, qtbot, dummy_widget):
    """Test hiding and showing actions on the toolbar."""
    toolbar = toolbar_fixture

    # Add an action
    toolbar.add_action("icon_action", icon_action, dummy_widget)
    assert icon_action.action.isVisible()

    # Hide the action
    toolbar.hide_action("icon_action")
    qtbot.wait(100)
    assert not icon_action.action.isVisible()

    # Show the action
    toolbar.show_action("icon_action")
    qtbot.wait(100)
    assert icon_action.action.isVisible()


def test_add_duplicate_action(toolbar_fixture, icon_action, dummy_widget):
    """Test that adding an action with a duplicate action_id raises a ValueError."""
    toolbar = toolbar_fixture

    # Add an action
    toolbar.add_action("icon_action", icon_action, dummy_widget)
    assert "icon_action" in toolbar.widgets

    # Attempt to add another action with the same ID
    with pytest.raises(ValueError) as excinfo:
        toolbar.add_action("icon_action", icon_action, dummy_widget)
    assert "Action with ID 'icon_action' already exists." in str(excinfo.value)


def test_update_material_icon_colors(toolbar_fixture, material_icon_action, dummy_widget):
    """Test updating the color of MaterialIconAction icons."""
    toolbar = toolbar_fixture

    # Add MaterialIconAction
    toolbar.add_action("material_icon_action", material_icon_action, dummy_widget)
    assert material_icon_action.action is not None

    # Initial icon
    initial_icon = material_icon_action.action.icon()

    # Update color
    new_color = "#ff0000"  # Red
    toolbar.update_material_icon_colors(new_color)

    # Updated icon
    updated_icon = material_icon_action.action.icon()

    # Assuming that the icon changes when color is updated
    assert initial_icon != updated_icon


def test_device_selection_action(toolbar_fixture, device_selection_action, dummy_widget):
    """Test adding a DeviceSelectionAction to the toolbar."""
    toolbar = toolbar_fixture
    toolbar.add_action("device_selection", device_selection_action, dummy_widget)
    assert "device_selection" in toolbar.widgets
    # DeviceSelectionAction adds a QWidget, so it should be present in the toolbar's widgets
    # Check if the widget is added
    widget = device_selection_action.device_combobox.parentWidget()
    assert widget in toolbar.findChildren(QWidget)
    # Verify that the label is correct
    label = widget.findChild(QLabel)
    assert label.text() == "Select Device:"


def test_widget_action(toolbar_fixture, widget_action, dummy_widget):
    """Test adding a WidgetAction to the toolbar."""
    toolbar = toolbar_fixture
    toolbar.add_action("widget_action", widget_action, dummy_widget)
    assert "widget_action" in toolbar.widgets
    # WidgetAction adds a QWidget to the toolbar
    container = widget_action.widget.parentWidget()
    assert container in toolbar.findChildren(QWidget)
    # Verify the label if present
    label = container.findChild(QLabel)
    assert label.text() == "Sample Label:"


def test_expandable_menu_action(toolbar_fixture, expandable_menu_action, dummy_widget):
    """Test adding an ExpandableMenuAction to the toolbar."""
    toolbar = toolbar_fixture
    toolbar.add_action("expandable_menu", expandable_menu_action, dummy_widget)
    assert "expandable_menu" in toolbar.widgets
    # ExpandableMenuAction adds a QToolButton with a QMenu
    # Find the QToolButton
    tool_buttons = toolbar.findChildren(QToolButton)
    assert len(tool_buttons) > 0
    button = tool_buttons[-1]  # Assuming it's the last one added
    menu = button.menu()
    assert menu is not None
    # Check that menu has the correct actions
    for action_id, sub_action in expandable_menu_action.actions.items():
        # Check if a sub-action with the correct tooltip exists
        matched = False
        for menu_action in menu.actions():
            if menu_action.toolTip() == sub_action.tooltip:
                matched = True
                break
        assert matched, f"Sub-action with tooltip '{sub_action.tooltip}' not found in menu."


def test_update_material_icon_colors_no_material_actions(toolbar_fixture, dummy_widget):
    """Test updating material icon colors when there are no MaterialIconActions."""
    toolbar = toolbar_fixture
    # Ensure there are no MaterialIconActions
    toolbar.update_material_icon_colors("#00ff00")


def test_hide_action_nonexistent(toolbar_fixture):
    """Test hiding an action that does not exist raises a ValueError."""
    toolbar = toolbar_fixture
    with pytest.raises(ValueError) as excinfo:
        toolbar.hide_action("nonexistent_action")
    assert "Action with ID 'nonexistent_action' does not exist." in str(excinfo.value)


def test_show_action_nonexistent(toolbar_fixture):
    """Test showing an action that does not exist raises a ValueError."""
    toolbar = toolbar_fixture
    with pytest.raises(ValueError) as excinfo:
        toolbar.show_action("nonexistent_action")
    assert "Action with ID 'nonexistent_action' does not exist." in str(excinfo.value)
