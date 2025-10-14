from __future__ import annotations

import numpy as np
import pytest
from qtpy.QtCore import QPointF, Qt

from bec_widgets.widgets.plots.image.image import Image
from bec_widgets.widgets.plots.image.setting_widgets.image_roi_tree import ROIPropertyTree
from bec_widgets.widgets.plots.roi.image_roi import CircularROI, RectangularROI
from tests.unit_tests.client_mocks import mocked_client
from tests.unit_tests.conftest import create_widget


@pytest.fixture
def image_widget(qtbot, mocked_client):
    """Create an Image widget with some test data."""
    widget = create_widget(qtbot, Image, client=mocked_client)
    # Add a simple test image
    data = np.zeros((100, 100), dtype=float)
    data[20:40, 20:40] = 5  # A square region with value 5
    widget.main_image.set_data(data)
    yield widget


@pytest.fixture
def roi_tree(qtbot, image_widget):
    """Create an ROI property tree widget linked to the image widget."""
    tree = create_widget(qtbot, ROIPropertyTree, image_widget=image_widget)
    yield tree


@pytest.fixture
def compact_roi_tree(qtbot, image_widget):
    tree = create_widget(
        qtbot, ROIPropertyTree, image_widget=image_widget, compact=True, compact_color="#00BCD4"
    )
    yield tree


def test_initialization(roi_tree, image_widget):
    """Test that the widget initializes correctly with the right components."""
    # Check the widget has the right structure
    assert roi_tree.image_widget == image_widget
    assert roi_tree.plot == image_widget.plot_item
    assert roi_tree.controller == image_widget.roi_controller
    assert isinstance(roi_tree.roi_items, dict)
    assert len(roi_tree.tree.findItems("", Qt.MatchContains)) == 0  # Empty tree initially

    # Check toolbar actions
    assert roi_tree.toolbar.components.get_action("roi_rectangle")
    assert roi_tree.toolbar.components.get_action("roi_circle")
    assert roi_tree.toolbar.components.get_action("roi_ellipse")
    assert roi_tree.toolbar.components.get_action("expand_toggle")
    assert roi_tree.toolbar.components.get_action("lock_unlock_all")

    # Check tree view setup
    assert roi_tree.tree.columnCount() == 3
    assert roi_tree.tree.headerItem().text(roi_tree.COL_ACTION) == "Actions"
    assert roi_tree.tree.headerItem().text(roi_tree.COL_ROI) == "ROI"
    assert roi_tree.tree.headerItem().text(roi_tree.COL_PROPS) == "Properties"


def test_controller_connection(roi_tree, image_widget):
    """Test that controller signals/slots are properly connected."""
    roi = image_widget.add_roi(kind="rect", name="test_roi")

    # Verify that ROI was added to the tree
    assert roi in roi_tree.roi_items
    assert len(roi_tree.tree.findItems("test_roi", Qt.MatchExactly, roi_tree.COL_ROI)) == 1

    # Remove ROI via controller and check that it's removed from the tree
    image_widget.remove_roi(0)
    assert roi not in roi_tree.roi_items
    assert len(roi_tree.tree.findItems("test_roi", Qt.MatchExactly, roi_tree.COL_ROI)) == 0


def test_expand_collapse_tree(roi_tree, image_widget):
    """Test that triggering the expand action expands and collapses all ROI items in the tree."""
    roi1 = image_widget.add_roi(kind="rect", name="rect1")
    roi2 = image_widget.add_roi(kind="circle", name="circle1")
    item1 = roi_tree.roi_items[roi1]
    item2 = roi_tree.roi_items[roi2]

    # Initially, items should be collapsed
    assert not item1.isExpanded()
    assert not item2.isExpanded()

    # Trigger expand
    roi_tree.expand_toggle.action.trigger()
    assert item1.isExpanded()
    assert item2.isExpanded()

    # Trigger collapse
    roi_tree.expand_toggle.action.trigger()
    assert not item1.isExpanded()
    assert not item2.isExpanded()


def test_roi_properties_display(roi_tree, image_widget):
    """Test that ROI properties are displayed correctly in the tree."""
    # Add ROI with specific properties
    roi = image_widget.add_roi(kind="rect", name="prop_test", line_width=15)
    roi.line_color = "#FF0000"  # bright red

    # Find the tree item
    item = roi_tree.roi_items[roi]

    # Check property display
    assert item.text(roi_tree.COL_ROI) == "prop_test"

    # Find the type item (first child)
    type_item = item.child(0)
    assert type_item.text(roi_tree.COL_ROI) == "Type"
    assert type_item.text(roi_tree.COL_PROPS) == "RectangularROI"

    # Find the width item (second child)
    width_item = item.child(1)
    assert width_item.text(roi_tree.COL_ROI) == "Line width"
    width_spin = roi_tree.tree.itemWidget(width_item, roi_tree.COL_PROPS)
    assert width_spin.value() == 15


def test_roi_name_edit(roi_tree, image_widget, qtbot):
    """Test editing the ROI name in the tree."""
    roi = image_widget.add_roi(kind="rect", name="original_name")
    item = roi_tree.roi_items[roi]

    # Edit the name - simulate user editing the item
    item.setFlags(item.flags() | Qt.ItemIsEditable)
    roi_tree.tree.editItem(item, roi_tree.COL_ROI)
    qtbot.keyClicks(roi_tree.tree.viewport().focusWidget(), "new_name")
    qtbot.keyClick(roi_tree.tree.viewport().focusWidget(), Qt.Key_Return)
    # Check the ROI name was updated
    qtbot.waitUntil(
        lambda: all([roi.label == "new_name", item.text(roi_tree.COL_ROI) == "new_name"]),
        timeout=200,
    )


def test_roi_width_edit(roi_tree, image_widget, qtbot):
    """Test editing ROI line width via spin box."""
    roi = image_widget.add_roi(kind="rect", name="width_test", line_width=5)
    item = roi_tree.roi_items[roi]

    # Find the width spin box
    width_item = item.child(1)  # Second child item (index 1)
    width_spin = roi_tree.tree.itemWidget(width_item, roi_tree.COL_PROPS)

    # Change the width
    width_spin.setValue(25)
    # Check the ROI width was updated
    qtbot.waitUntil(lambda: roi.line_width == 25, timeout=200)


def test_delete_roi_button(roi_tree, image_widget, qtbot):
    """Test that the delete button correctly removes the ROI."""
    roi = image_widget.add_roi(kind="rect", name="to_delete")
    item = roi_tree.roi_items[roi]

    action_widget = roi_tree.tree.itemWidget(item, roi_tree.COL_ACTION)
    layout = action_widget.layout()

    del_btn = layout.itemAt(1).widget()
    del_btn.click()

    # Verify ROI was removed
    qtbot.waitUntil(
        lambda: all([roi not in roi_tree.roi_items, roi not in image_widget.roi_controller.rois]),
        timeout=200,
    )


def test_roi_color_change_from_roi(roi_tree, image_widget):
    """Test that changing the ROI color updates the tree display."""
    roi = image_widget.add_roi(kind="rect", name="color_test")
    item = roi_tree.roi_items[roi]

    # Change the ROI color directly
    roi.line_color = "#00FF00"  # bright green

    # Check that the color button was updated
    color_btn = roi_tree.tree.itemWidget(item, roi_tree.COL_PROPS)
    assert color_btn.color == "#00FF00"


def test_colormap_change(roi_tree, image_widget):
    """Test changing the colormap affects ROI colors."""
    # Add multiple ROIs
    roi1 = image_widget.add_roi(kind="rect", name="r1")
    roi2 = image_widget.add_roi(kind="circle", name="c1")

    # Store original colors
    orig_colors = [roi1.line_color, roi2.line_color]

    # Change colormap to "plasma" from the color map widget
    roi_tree.cmap.colormap = "plasma"

    # Colors should have changed
    new_colors = [roi1.line_color, roi2.line_color]
    assert new_colors != orig_colors


def test_coordinates_update(roi_tree, image_widget):
    """Test that coordinates update when ROI is moved."""
    # Add a rectangular ROI
    roi = image_widget.add_roi(kind="rect", name="moving_roi", pos=(10, 10), size=(20, 20))
    item = roi_tree.roi_items[roi]

    # Find coordinate items (type and width are 0 and 1, coordinates start at 2)
    coordinate_items = [item.child(i) for i in range(2, item.childCount())]

    # Store initial coordinates
    initial_coords = [item.text(roi_tree.COL_PROPS) for item in coordinate_items]

    # Move the ROI
    roi.setPos(50, 50)

    # Check that coordinates were updated
    new_coords = [item.text(roi_tree.COL_PROPS) for item in coordinate_items]
    assert new_coords != initial_coords


def test_draw_mode_toggle(roi_tree, qtbot):
    """Test toggling draw modes."""
    # Initially no draw mode
    assert roi_tree._roi_draw_mode is None

    # Toggle rect mode on
    rect_action = roi_tree.toolbar.components.get_action("roi_rectangle").action
    circle_action = roi_tree.toolbar.components.get_action("roi_circle").action
    rect_action.toggle()
    assert roi_tree._roi_draw_mode == "rect"
    assert rect_action.isChecked()
    assert not circle_action.isChecked()

    # Toggle circle mode on (should turn off rect mode)
    circle_action.toggle()
    qtbot.wait(200)
    assert roi_tree._roi_draw_mode == "circle"
    assert not rect_action.isChecked()
    assert circle_action.isChecked()

    # Toggle circle mode off
    circle_action.toggle()
    assert roi_tree._roi_draw_mode is None
    assert not circle_action.isChecked()
    assert not rect_action.isChecked()


def test_add_roi_from_toolbar(qtbot, mocked_client):
    """Test creating ROIs using the toolbar and mouse interactions."""
    # Create Image widget with ROI tree
    widget = create_widget(qtbot, Image, client=mocked_client)
    data = np.zeros((100, 100), dtype=float)
    widget.main_image.set_data(data)
    qtbot.waitExposed(widget)

    roi_tree = create_widget(qtbot, ROIPropertyTree, image_widget=widget)

    # Get initial ROI count
    initial_roi_count = len(widget.roi_controller.rois)

    # Test rectangle ROI creation
    # 1. Activate rectangle drawing mode
    roi_tree.toolbar.components.get_action("roi_rectangle").action.setChecked(True)
    assert roi_tree._roi_draw_mode == "rect"

    # Get plot widget and view
    plot_item = widget.plot_item
    view = plot_item.vb.scene().views()[0]
    qtbot.waitExposed(view)

    # Define start and end points for the ROI (in view coordinates)
    start_pos = QPointF(20, 20)
    end_pos = QPointF(60, 60)

    # Map view coordinates to scene coordinates
    start_pos_scene = plot_item.vb.mapViewToScene(start_pos)
    end_pos_scene = plot_item.vb.mapViewToScene(end_pos)

    # Map scene coordinates to widget coordinates
    start_pos_widget = view.mapFromScene(start_pos_scene)
    end_pos_widget = view.mapFromScene(end_pos_scene)

    # Using qtbot to simulate mouse actions
    # First click to start drawing
    qtbot.mousePress(view.viewport(), Qt.LeftButton, pos=start_pos_widget)

    # Then move to end position
    qtbot.mouseMove(view.viewport(), pos=end_pos_widget)

    # Finally release to complete the ROI
    qtbot.mouseRelease(view.viewport(), Qt.LeftButton, pos=end_pos_widget)

    # Wait for signals to process
    qtbot.wait(200)

    # Check that a new ROI was created
    assert len(widget.roi_controller.rois) == initial_roi_count + 1

    # Get the newly created ROI
    new_roi = widget.roi_controller.rois[-1]

    # Verify it's a rectangular ROI
    assert isinstance(new_roi, RectangularROI)

    # Test circle ROI creation
    # Reset ROI draw mode
    roi_tree.toolbar.components.get_action("roi_rectangle").action.setChecked(False)
    roi_tree.toolbar.components.get_action("roi_circle").action.setChecked(True)
    assert roi_tree._roi_draw_mode == "circle"

    # Define new positions for circle ROI
    start_pos = QPointF(30, 30)
    end_pos = QPointF(50, 50)

    # Map view coordinates to scene coordinates
    start_pos_scene = plot_item.vb.mapViewToScene(start_pos)
    end_pos_scene = plot_item.vb.mapViewToScene(end_pos)

    # Map scene coordinates to widget coordinates
    start_pos_widget = view.mapFromScene(start_pos_scene)
    end_pos_widget = view.mapFromScene(end_pos_scene)

    # Using qtbot to simulate mouse actions
    # First click to start drawing
    qtbot.mousePress(view.viewport(), Qt.LeftButton, pos=start_pos_widget)

    # Then move to end position
    qtbot.mouseMove(view.viewport(), pos=end_pos_widget)

    # Finally release to complete the ROI
    qtbot.mouseRelease(view.viewport(), Qt.LeftButton, pos=end_pos_widget)

    # Wait for signals to process
    qtbot.wait(200)

    # Check that a new ROI was created
    assert len(widget.roi_controller.rois) == initial_roi_count + 2

    # Get the newly created ROI
    new_roi = widget.roi_controller.rois[-1]

    # Verify it's a circle ROI
    assert isinstance(new_roi, CircularROI)


def test_roi_lock_button(roi_tree, image_widget, qtbot):
    """Verify the individual lock button toggles ROI.movable."""
    roi = image_widget.add_roi(kind="rect", name="lock_test")
    item = roi_tree.roi_items[roi]

    # Lock button is the first widget in the Actions layout
    action_widget = roi_tree.tree.itemWidget(item, roi_tree.COL_ACTION)
    lock_btn = action_widget.layout().itemAt(0).widget()

    # Initially unlocked
    assert roi.movable
    assert not lock_btn.isChecked()

    # Lock it
    lock_btn.click()
    qtbot.wait(200)
    assert not roi.movable
    assert lock_btn.isChecked()

    # Unlock again
    lock_btn.click()
    qtbot.wait(200)
    assert roi.movable
    assert not lock_btn.isChecked()


def test_global_lock_all_button(roi_tree, image_widget, qtbot):
    """Verify the toolbar lock-all action locks/unlocks every ROI."""
    roi1 = image_widget.add_roi(kind="rect", name="g1")
    roi2 = image_widget.add_roi(kind="circle", name="g2")

    lock_all = roi_tree.lock_all_action.action

    # Start unlocked
    assert roi1.movable and roi2.movable
    assert not lock_all.isChecked()

    # Toggle → lock everything
    lock_all.trigger()
    qtbot.wait(200)
    assert lock_all.isChecked()
    assert not roi1.movable and not roi2.movable

    # Toggle again → unlock everything
    lock_all.trigger()
    qtbot.wait(200)
    assert not lock_all.isChecked()
    assert roi1.movable and roi2.movable


def test_new_roi_respects_global_lock(roi_tree, image_widget, qtbot):
    """When the global lock-all toggle is active, newly added ROIs start locked."""
    # Enable global lock
    roi_tree.lock_all_action.action.setChecked(True)
    qtbot.wait(100)

    # Add ROI after lock enabled
    roi = image_widget.add_roi(kind="rect", name="new_locked")

    assert not roi.movable
    # Disable global lock again
    roi_tree.lock_all_action.action.setChecked(False)


def test_cleanup_disconnect_signals(roi_tree, image_widget):
    """Test that cleanup disconnects ROI signals so further changes do not update the tree."""
    # Add a rectangular ROI
    roi = image_widget.add_roi(kind="rect", name="cleanup_test", pos=(10, 10), size=(20, 20))
    item = roi_tree.roi_items[roi]

    # Test that signals are connected before cleanup
    pre_name = item.text(roi_tree.COL_ROI)
    pre_coord = item.child(2).text(roi_tree.COL_PROPS)
    # Change ROI properties to see updates
    roi.label = "connected_name"
    roi.setPos(30, 30)
    # Verify that the tree item updated
    assert item.text(roi_tree.COL_ROI) == "connected_name"
    assert item.child(2).text(roi_tree.COL_PROPS) != pre_coord

    # Perform cleanup to disconnect signals
    roi_tree.cleanup()

    # Store initial state
    initial_name = item.text(roi_tree.COL_ROI)
    initial_coord = item.child(2).text(roi_tree.COL_PROPS)

    # Change ROI properties after cleanup
    roi.label = "changed_name"
    roi.setPos(50, 50)

    # Verify that the tree item was not updated
    assert item.text(roi_tree.COL_ROI) == initial_name
    assert item.child(2).text(roi_tree.COL_PROPS) == initial_coord


def test_compact_initialization_minimal_toolbar(compact_roi_tree):
    assert compact_roi_tree.compact is True
    assert compact_roi_tree.tree is None

    # Draw actions exist
    assert compact_roi_tree.toolbar.components.get_action("roi_rectangle")
    assert compact_roi_tree.toolbar.components.get_action("roi_circle")
    assert compact_roi_tree.toolbar.components.get_action("roi_ellipse")

    # Full-mode actions are absent
    import pytest

    with pytest.raises(KeyError):
        compact_roi_tree.toolbar.components.get_action("expand_toggle")
    with pytest.raises(KeyError):
        compact_roi_tree.toolbar.components.get_action("lock_unlock_all")
    with pytest.raises(KeyError):
        compact_roi_tree.toolbar.components.get_action("roi_tree_cmap")

    assert not hasattr(compact_roi_tree, "lock_all_action")


def test_compact_single_roi_enforced_programmatic(compact_roi_tree, image_widget):
    # Add first ROI
    roi1 = image_widget.add_roi(kind="rect", name="r1")
    assert len(image_widget.roi_controller.rois) == 1
    assert roi1.line_color == "#00BCD4"

    # Add second ROI; the first should be removed automatically
    roi2 = image_widget.add_roi(kind="circle", name="c1")
    rois = image_widget.roi_controller.rois
    assert len(rois) == 1
    assert rois[0] is roi2

    from bec_widgets.widgets.plots.roi.image_roi import CircularROI

    assert isinstance(rois[0], CircularROI)
    assert rois[0].line_color == "#00BCD4"


def test_compact_add_roi_from_toolbar_single_enforced(qtbot, compact_roi_tree, image_widget):
    # Ensure view is ready
    plot_item = image_widget.plot_item
    view = plot_item.vb.scene().views()[0]
    qtbot.waitExposed(view)

    # Activate rectangle drawing
    rect_action = compact_roi_tree.toolbar.components.get_action("roi_rectangle").action
    rect_action.setChecked(True)

    # Draw rectangle
    start_pos = QPointF(10, 10)
    end_pos = QPointF(50, 40)
    start_scene = plot_item.vb.mapViewToScene(start_pos)
    end_scene = plot_item.vb.mapViewToScene(end_pos)
    start_widget = view.mapFromScene(start_scene)
    end_widget = view.mapFromScene(end_scene)
    qtbot.mousePress(view.viewport(), Qt.LeftButton, pos=start_widget)
    qtbot.mouseMove(view.viewport(), pos=end_widget)
    qtbot.mouseRelease(view.viewport(), Qt.LeftButton, pos=end_widget)
    qtbot.wait(100)

    rois = image_widget.roi_controller.rois
    from bec_widgets.widgets.plots.roi.image_roi import CircularROI, RectangularROI

    assert len(rois) == 1
    assert isinstance(rois[0], RectangularROI)
    assert rois[0].line_color == "#00BCD4"

    # Now draw a circle; rectangle should be removed automatically
    rect_action.setChecked(False)
    circle_action = compact_roi_tree.toolbar.components.get_action("roi_circle").action
    circle_action.setChecked(True)

    start_pos = QPointF(20, 20)
    end_pos = QPointF(40, 40)
    start_scene = plot_item.vb.mapViewToScene(start_pos)
    end_scene = plot_item.vb.mapViewToScene(end_pos)
    start_widget = view.mapFromScene(start_scene)
    end_widget = view.mapFromScene(end_scene)
    qtbot.mousePress(view.viewport(), Qt.LeftButton, pos=start_widget)
    qtbot.mouseMove(view.viewport(), pos=end_widget)
    qtbot.mouseRelease(view.viewport(), Qt.LeftButton, pos=end_widget)
    qtbot.wait(100)

    rois = image_widget.roi_controller.rois
    assert len(rois) == 1
    assert isinstance(rois[0], CircularROI)
    assert rois[0].line_color == "#00BCD4"


def test_compact_draw_mode_toggle(compact_roi_tree):
    # Initially no draw mode
    assert compact_roi_tree._roi_draw_mode is None

    rect_action = compact_roi_tree.toolbar.components.get_action("roi_rectangle").action
    circle_action = compact_roi_tree.toolbar.components.get_action("roi_circle").action

    # Toggle rect on
    rect_action.toggle()
    assert compact_roi_tree._roi_draw_mode == "rect"
    assert rect_action.isChecked()
    assert not circle_action.isChecked()

    # Toggle circle on; rect should toggle off
    circle_action.toggle()
    assert compact_roi_tree._roi_draw_mode == "circle"
    assert circle_action.isChecked()
    assert not rect_action.isChecked()

    # Toggle circle off → none
    circle_action.toggle()
    assert compact_roi_tree._roi_draw_mode is None
    assert not rect_action.isChecked()
    assert not circle_action.isChecked()
