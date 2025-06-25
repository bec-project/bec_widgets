from typing import Literal

import pytest
from qtpy.QtCore import QPoint, Qt
from qtpy.QtGui import QContextMenuEvent
from qtpy.QtWidgets import QComboBox, QLabel, QMenu, QStyle, QToolButton, QWidget

from bec_widgets.utils.toolbars.actions import (
    DeviceSelectionAction,
    ExpandableMenuAction,
    LongPressToolButton,
    MaterialIconAction,
    QtIconAction,
    SeparatorAction,
    SwitchableToolBarAction,
    WidgetAction,
)
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar


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
        orientation=orientation,
        background_color="rgba(255, 255, 255, 255)",  # White background for testing
    )
    qtbot.addWidget(toolbar)
    qtbot.waitExposed(toolbar)
    yield toolbar


@pytest.fixture
def separator_action():
    """Fixture to create a SeparatorAction."""
    return SeparatorAction()


@pytest.fixture
def material_icon_action():
    """Fixture to create a MaterialIconAction."""
    return MaterialIconAction(
        icon_name="home", tooltip="Test Material Icon Action", checkable=False
    )


@pytest.fixture
def material_icon_action_2():
    """Fixture to create another MaterialIconAction."""
    return MaterialIconAction(
        icon_name="home", tooltip="Test Material Icon Action 2", checkable=False
    )


@pytest.fixture
def qt_icon_action():
    """Fixture to create a QtIconAction."""
    return QtIconAction(standard_icon=QStyle.SP_FileIcon, tooltip="Qt File", checkable=True)


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


@pytest.fixture
def switchable_toolbar_action():
    """Fixture to create a switchable toolbar action with two MaterialIconActions."""
    action1 = MaterialIconAction(icon_name="counter_1", tooltip="Action 1", checkable=True)
    action2 = MaterialIconAction(icon_name="counter_2", tooltip="Action 2", checkable=True)
    switchable = SwitchableToolBarAction(
        actions={"action1": action1, "action2": action2},
        initial_action="action1",
        tooltip="Switchable Action",
        checkable=True,
    )
    return switchable


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
    assert len(toolbar.components._components) == 1  # only the separator
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


def test_add_action(toolbar_fixture, material_icon_action, qt_icon_action):
    """Test adding different types of actions to the toolbar components."""
    toolbar = toolbar_fixture

    # Add MaterialIconAction
    toolbar.add_action("material_icon_action", material_icon_action)
    assert toolbar.components.exists("material_icon_action")
    assert toolbar.components.get_action("material_icon_action") == material_icon_action

    # Add QtIconAction
    toolbar.add_action("qt_icon_action", qt_icon_action)
    assert toolbar.components.exists("qt_icon_action")
    assert toolbar.components.get_action("qt_icon_action") == qt_icon_action


def test_hide_show_action(toolbar_fixture, qt_icon_action, qtbot):
    """Test hiding and showing actions on the toolbar."""
    toolbar = toolbar_fixture

    # Add an action
    toolbar.add_action("icon_action", qt_icon_action)
    assert qt_icon_action.action.isVisible()

    # Hide the action
    toolbar.hide_action("icon_action")
    qtbot.wait(100)
    assert not qt_icon_action.action.isVisible()

    # Show the action
    toolbar.show_action("icon_action")
    qtbot.wait(100)
    assert qt_icon_action.action.isVisible()


def test_add_duplicate_action(toolbar_fixture, qt_icon_action):
    """Test that adding an action with a duplicate action_id raises a ValueError."""
    toolbar = toolbar_fixture

    # Add an action
    toolbar.add_action("qt_icon_action", qt_icon_action)
    assert toolbar.components.exists("qt_icon_action")

    # Attempt to add another action with the same ID
    with pytest.raises(ValueError) as excinfo:
        toolbar.add_action("qt_icon_action", qt_icon_action)
    assert "Bundle with name 'qt_icon_action' already exists." in str(excinfo.value)


def test_update_material_icon_colors(toolbar_fixture, material_icon_action):
    """Test updating the color of MaterialIconAction icons."""
    toolbar = toolbar_fixture

    # Add MaterialIconAction
    toolbar.add_action("material_icon_action", material_icon_action)
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


def test_device_selection_action(toolbar_fixture, device_selection_action):
    """Test adding a DeviceSelectionAction to the toolbar."""
    toolbar = toolbar_fixture
    toolbar.add_action("device_selection", device_selection_action)
    assert toolbar.components.exists("device_selection")
    toolbar.show_bundles(["device_selection"])
    # DeviceSelectionAction adds a QWidget, so it should be present in the toolbar's widgets
    # Check if the widget is added
    widget = device_selection_action.device_combobox.parentWidget()
    assert widget in toolbar.findChildren(QWidget)
    # Verify that the label is correct
    label = widget.findChild(QLabel)
    assert label.text() == "Select Device:"


def test_widget_action(toolbar_fixture, widget_action):
    """Test adding a WidgetAction to the toolbar."""
    toolbar = toolbar_fixture
    toolbar.add_action("widget_action", widget_action)
    assert toolbar.components.exists("widget_action")
    toolbar.show_bundles(["widget_action"])
    # WidgetAction adds a QWidget to the toolbar
    container = widget_action.widget.parentWidget()
    assert container in toolbar.findChildren(QWidget)
    # Verify the label if present
    label = container.findChild(QLabel)
    assert label.text() == "Sample Label:"


def test_expandable_menu_action(toolbar_fixture, expandable_menu_action):
    """Test adding an ExpandableMenuAction to the toolbar."""
    toolbar = toolbar_fixture
    toolbar.add_action("expandable_menu", expandable_menu_action)
    assert toolbar.components.exists("expandable_menu")
    toolbar.show_bundles(["expandable_menu"])
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
    """Test hiding an action that does not exist raises a KeyError."""
    toolbar = toolbar_fixture
    with pytest.raises(KeyError) as excinfo:
        toolbar.hide_action("nonexistent_action")
    excinfo.match("Component with name 'nonexistent_action' does not exist.")


def test_show_action_nonexistent(toolbar_fixture):
    """Test showing an action that does not exist raises a KeyError."""
    toolbar = toolbar_fixture
    with pytest.raises(KeyError) as excinfo:
        toolbar.show_action("nonexistent_action")
    excinfo.match("Component with name 'nonexistent_action' does not exist.")


def test_add_bundle(toolbar_fixture, material_icon_action):
    """Test adding a bundle of actions to the toolbar."""
    toolbar = toolbar_fixture
    toolbar.add_action("material_icon_in_bundle", material_icon_action)
    bundle = ToolbarBundle("test_bundle", toolbar.components)
    bundle.add_action("material_icon_in_bundle")

    toolbar.add_bundle(bundle)

    assert toolbar.get_bundle("test_bundle")
    assert toolbar.components.exists("material_icon_in_bundle")

    toolbar.show_bundles(["test_bundle"])

    assert material_icon_action.action in toolbar.actions()


def test_invalid_orientation():
    """Test that an invalid orientation raises a ValueError."""
    try:
        toolbar = ModularToolBar(orientation="horizontal")
        with pytest.raises(ValueError):
            toolbar.set_orientation("diagonal")
    finally:
        toolbar.close()
        toolbar.deleteLater()


def test_widget_action_calculate_minimum_width(qtbot):
    """Test calculate_minimum_width with various combo box items."""
    combo = QComboBox()
    combo.addItems(["Short", "Longer Item", "The Longest Item In Combo"])
    widget_action = WidgetAction(label="Test", widget=combo)
    width = widget_action.calculate_minimum_width(combo)
    assert width > 0
    # Width should be large enough to accommodate the longest item plus additional space
    assert width > 100


def test_add_action_to_bundle(toolbar_fixture, dummy_widget, material_icon_action):
    # Create an initial bundle with one action
    toolbar_fixture.add_action("initial_action", material_icon_action)
    bundle = ToolbarBundle("test_bundle", toolbar_fixture.components)
    bundle.add_action("initial_action")
    toolbar_fixture.add_bundle(bundle)

    # Create a new action to add to the existing bundle
    new_action = MaterialIconAction(
        icon_name="counter_1", tooltip="New Action", checkable=True, parent=dummy_widget
    )
    toolbar_fixture.components.add_safe("new_action", new_action)
    toolbar_fixture.get_bundle("test_bundle").add_action("new_action")

    toolbar_fixture.show_bundles(["test_bundle"])

    # Verify the new action is registered in the toolbar's widgets
    assert toolbar_fixture.components.exists("new_action")
    assert toolbar_fixture.components.get_action("new_action") == new_action

    # Verify the new action is included in the bundle tracking
    assert toolbar_fixture.bundles["test_bundle"].bundle_actions["new_action"]() == new_action

    # Verify the new action's QAction is present in the toolbar's action list
    actions_list = toolbar_fixture.actions()
    assert new_action.action in actions_list

    # Verify that the new action is inserted immediately after the last action of the bundle
    last_bundle_action = material_icon_action.action
    index_last = actions_list.index(last_bundle_action)
    index_new = actions_list.index(new_action.action)
    assert index_new == index_last + 1


def test_context_menu_contains_added_actions(
    toolbar_fixture, material_icon_action, material_icon_action_2, monkeypatch
):
    """
    Test that the toolbar's context menu lists all added toolbar actions.
    """
    toolbar = toolbar_fixture

    # Add two different actions
    toolbar.components.add_safe("material_icon_action", material_icon_action)
    toolbar.components.add_safe("material_icon_action_2", material_icon_action_2)
    bundle = toolbar.new_bundle("test_bundle")
    bundle.add_action("material_icon_action")
    bundle.add_action("material_icon_action_2")

    toolbar.show_bundles(["test_bundle"])
    # Mock the QMenu.exec_ method to prevent the context menu from being displayed and block CI pipeline
    monkeypatch.setattr(QMenu, "exec_", lambda self, pos=None: None)
    event = QContextMenuEvent(QContextMenuEvent.Mouse, QPoint(10, 10))
    toolbar.contextMenuEvent(event)
    menus = toolbar.findChildren(QMenu)

    assert len(menus) > 0
    menu = menus[-1]
    menu_action_texts = [action.text() for action in menu.actions()]
    tooltips = [
        action.action.tooltip
        for action in toolbar.components._components.values()
        if not isinstance(action.action, SeparatorAction)
    ]
    menu_actions_tooltips = [
        action.toolTip() for action in menu.actions() if action.toolTip() != ""
    ]
    assert menu_action_texts == tooltips


def test_context_menu_toggle_action_visibility(toolbar_fixture, material_icon_action, monkeypatch):
    """
    Test that toggling action visibility works correctly through the toolbar's context menu.
    """
    toolbar = toolbar_fixture
    # Add an action
    toolbar.add_action("material_icon_action", material_icon_action)
    toolbar.show_bundles(["material_icon_action"])
    assert material_icon_action.action.isVisible()

    # Manually trigger the context menu event
    monkeypatch.setattr(QMenu, "exec_", lambda self, pos=None: None)
    event = QContextMenuEvent(QContextMenuEvent.Mouse, QPoint(10, 10))
    toolbar.contextMenuEvent(event)

    # Grab the menu that was created
    menus = toolbar.findChildren(QMenu)
    assert len(menus) > 0
    menu = menus[-1]

    # Locate the QAction in the menu
    matching_actions = [m for m in menu.actions() if m.text() == material_icon_action.tooltip]
    assert len(matching_actions) == 1
    action_in_menu = matching_actions[0]

    # Toggle it off (uncheck)
    action_in_menu.setChecked(False)
    menu.triggered.emit(action_in_menu)
    # The action on the toolbar should now be hidden
    assert not material_icon_action.action.isVisible()

    # Toggle it on (check)
    action_in_menu.setChecked(True)
    menu.triggered.emit(action_in_menu)
    # The action on the toolbar should be visible again
    assert material_icon_action.action.isVisible()


def test_switchable_toolbar_action_add(toolbar_fixture, switchable_toolbar_action):
    """Test that a switchable toolbar action can be added to the toolbar correctly."""
    toolbar = toolbar_fixture
    toolbar.add_action("switch_action", switchable_toolbar_action)
    toolbar.show_bundles(["switch_action"])

    # Verify the action was added correctly
    assert toolbar.components.exists("switch_action")
    assert toolbar.components.get_action("switch_action") == switchable_toolbar_action

    # Verify the button is present and is the correct type
    button = switchable_toolbar_action.main_button
    assert isinstance(button, LongPressToolButton)

    # Verify initial state
    assert switchable_toolbar_action.current_key == "action1"
    assert button.toolTip() == "Action 1"


def test_switchable_toolbar_action_switching(toolbar_fixture, switchable_toolbar_action, qtbot):
    toolbar = toolbar_fixture
    toolbar.add_action("switch_action", switchable_toolbar_action)
    toolbar.show_bundles(["switch_action"])
    # Verify initial state is set to action1
    assert switchable_toolbar_action.current_key == "action1"
    assert switchable_toolbar_action.main_button.toolTip() == "Action 1"
    # Access the dropdown menu from the main button
    menu = switchable_toolbar_action.main_button.menu()
    assert menu is not None
    # Find the QAction corresponding to "Action 2"
    action_for_2 = None
    for act in menu.actions():
        if act.text() == "Action 2":
            action_for_2 = act
            break
    assert action_for_2 is not None, "Menu action for 'Action 2' not found."
    # Trigger the QAction to switch to action2
    action_for_2.trigger()
    qtbot.wait(100)
    # Verify that the switchable action has updated its state
    assert switchable_toolbar_action.current_key == "action2"
    assert switchable_toolbar_action.main_button.toolTip() == "Action 2"


def test_long_pressbutton(toolbar_fixture, switchable_toolbar_action, qtbot):
    toolbar = toolbar_fixture
    toolbar.add_action("switch_action", switchable_toolbar_action)
    toolbar.show_bundles(["switch_action"])

    # Verify the button is a LongPressToolButton
    button = switchable_toolbar_action.main_button
    assert isinstance(button, LongPressToolButton)

    # Override showMenu() to record when it is called.
    call_flag = []

    # had to put some fake menu, we cannot call .isVisible at CI
    def fake_showMenu():
        call_flag.append(True)

    button.showMenu = fake_showMenu

    # Simulate a long press (exceeding the threshold, default 500ms).
    qtbot.mousePress(button, Qt.LeftButton)
    qtbot.wait(600)  # wait longer than long_press_threshold
    qtbot.mouseRelease(button, Qt.LeftButton)

    # Verify that fake_showMenu() was called.
    assert call_flag, "Long press did not trigger showMenu() as expected."


# Additional tests for action/bundle removal
def test_remove_standalone_action(toolbar_fixture, material_icon_action):
    """
    Ensure that a standalone action is fully removed and no longer accessible.
    """
    toolbar = toolbar_fixture
    # Add the action and check it is present
    toolbar.add_action("icon_action", material_icon_action)

    assert toolbar.components.exists("icon_action")

    toolbar.show_bundles(["icon_action"])
    assert material_icon_action.action in toolbar.actions()

    # Now remove it
    toolbar.components.remove_action("icon_action")

    # Action bookkeeping
    assert not toolbar.components.exists("icon_action")
    # QAction list
    assert material_icon_action.action not in toolbar.actions()
    # Attempting to hide / show it should raise
    with pytest.raises(KeyError):
        toolbar.hide_action("icon_action")
    with pytest.raises(KeyError):
        toolbar.show_action("icon_action")


def test_remove_action_from_bundle(toolbar_fixture, material_icon_action, material_icon_action_2):
    """
    Remove a single action that is part of a bundle. This should not remove the action
    from the toolbar's components, but only from the bundle tracking.
    """
    toolbar = toolbar_fixture
    bundle = toolbar.new_bundle("test_bundle")
    # Add two actions to the bundle
    toolbar.components.add_safe("material_action", material_icon_action)
    toolbar.components.add_safe("material_action_2", material_icon_action_2)
    bundle.add_action("material_action")
    bundle.add_action("material_action_2")

    toolbar.show_bundles(["test_bundle"])

    # Initial assertions
    assert "test_bundle" in toolbar.bundles
    assert toolbar.components.exists("material_action")
    assert toolbar.components.exists("material_action_2")

    # Remove one action from the bundle
    toolbar.get_bundle("test_bundle").remove_action("material_action")

    # The bundle should still exist
    assert "test_bundle" in toolbar.bundles
    # The removed action should still exist in the components
    assert toolbar.components.exists("material_action")

    # The removed action should not be in the bundle anymore
    assert "material_action" not in toolbar.bundles["test_bundle"].bundle_actions


def test_remove_entire_bundle(toolbar_fixture, material_icon_action, material_icon_action_2):
    toolbar = toolbar_fixture
    toolbar.components.add_safe("material_action", material_icon_action)
    toolbar.components.add_safe("material_action_2", material_icon_action_2)
    # Create a bundle with two actions
    bundle = toolbar.new_bundle("to_remove")
    bundle.add_action("material_action")
    bundle.add_action("material_action_2")

    # Confirm bundle presence
    assert "to_remove" in toolbar.bundles

    # Remove the whole bundle
    toolbar.remove_bundle("to_remove")

    # Bundle mapping gone
    assert "to_remove" not in toolbar.bundles


def test_remove_nonexistent_action(toolbar_fixture):
    """
    Attempting to remove an action that does not exist should raise KeyError.
    """
    toolbar = toolbar_fixture
    with pytest.raises(KeyError) as excinfo:
        toolbar.components.remove_action("nonexistent_action")
    assert "Action with ID 'nonexistent_action' does not exist." in str(excinfo.value)


def test_remove_nonexistent_bundle(toolbar_fixture):
    """
    Attempting to remove a bundle that does not exist should raise KeyError.
    """
    toolbar = toolbar_fixture
    with pytest.raises(KeyError) as excinfo:
        toolbar.remove_bundle("nonexistent_bundle")
    excinfo.match("Bundle with name 'nonexistent_bundle' does not exist.")
