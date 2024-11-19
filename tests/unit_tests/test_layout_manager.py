from typing import Optional
from unittest.mock import patch

import pytest
from qtpy.QtWidgets import QLabel, QPushButton, QWidget

from bec_widgets.widgets.containers.layout_manager.layout_manager import LayoutManagerWidget


class MockWidgetHandler:
    def create_widget(self, widget_type: str) -> Optional[QWidget]:
        if widget_type == "ButtonWidget":
            return QPushButton()
        elif widget_type == "LabelWidget":
            return QLabel()
        else:
            return None


@pytest.fixture
def mock_widget_handler():
    handler = MockWidgetHandler()
    with patch(
        "bec_widgets.widgets.containers.layout_manager.layout_manager.widget_handler", handler
    ):
        yield handler


@pytest.fixture
def layout_manager(qtbot, mock_widget_handler):
    widget = LayoutManagerWidget()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_add_widget_empty_position(layout_manager):
    """Test adding a widget to an empty position without shifting."""
    btn1 = QPushButton("Button 1")
    layout_manager.add_widget(btn1, row=0, col=0)

    assert layout_manager.get_widget(0, 0) == btn1
    assert layout_manager.widget_positions[btn1] == (0, 0, 1, 1)
    assert layout_manager.position_widgets[(0, 0)] == btn1


def test_add_widget_occupied_position(layout_manager):
    """Test adding a widget to an occupied position with shifting (default direction right)."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")
    layout_manager.add_widget(btn1, row=0, col=0)
    layout_manager.add_widget(btn2, row=0, col=0)  # This should shift btn1 to the right

    assert layout_manager.get_widget(0, 0) == btn2
    assert layout_manager.get_widget(0, 1) == btn1
    assert layout_manager.widget_positions[btn2] == (0, 0, 1, 1)
    assert layout_manager.widget_positions[btn1] == (0, 1, 1, 1)


def test_add_widget_directional_shift_down(layout_manager):
    """Test adding a widget to an occupied position but shifting down instead of right."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")
    btn3 = QPushButton("Button 3")
    layout_manager.add_widget(btn1, row=0, col=0)
    layout_manager.add_widget(btn2, row=0, col=0)  # Shifts btn1 to the right by default

    # Now add btn3 at (0,1) but shift direction is down, so it should push btn1 down.
    layout_manager.add_widget(btn3, row=0, col=1, shift_direction="down")

    assert layout_manager.get_widget(0, 0) == btn2
    assert layout_manager.get_widget(0, 1) == btn3
    assert layout_manager.get_widget(1, 1) == btn1


def test_remove_widget_by_position(layout_manager):
    """Test removing a widget by specifying its row and column."""
    btn1 = QPushButton("Button 1")
    layout_manager.add_widget(btn1, row=0, col=0)

    layout_manager.remove(row=0, col=0)

    assert layout_manager.get_widget(0, 0) is None
    assert btn1 not in layout_manager.widget_positions


def test_move_widget_with_shift(layout_manager):
    """Test moving a widget to an occupied position, triggering a shift."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")
    btn3 = QPushButton("Button 3")

    layout_manager.add_widget(btn1, row=0, col=0)
    layout_manager.add_widget(btn2, row=0, col=1)
    layout_manager.add_widget(btn3, row=1, col=0)

    layout_manager.move_widget(old_row=0, old_col=0, new_row=0, new_col=1, shift_direction="right")

    assert layout_manager.get_widget(0, 1) == btn1
    assert layout_manager.get_widget(0, 2) == btn2
    assert layout_manager.get_widget(1, 0) == btn3


def test_move_widget_without_shift(layout_manager):
    """Test moving a widget to an occupied position without shifting."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")

    layout_manager.add_widget(btn1, row=0, col=0)
    layout_manager.add_widget(btn2, row=0, col=1)

    with pytest.raises(ValueError) as exc_info:
        layout_manager.move_widget(old_row=0, old_col=0, new_row=0, new_col=1, shift=False)

    assert "Position (0, 1) is already occupied." in str(exc_info.value)


def test_change_layout_num_cols(layout_manager):
    """Test changing the layout by specifying only the number of columns."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")
    btn3 = QPushButton("Button 3")
    btn4 = QPushButton("Button 4")

    layout_manager.add_widget(btn1)
    layout_manager.add_widget(btn2)
    layout_manager.add_widget(btn3)
    layout_manager.add_widget(btn4)

    layout_manager.change_layout(num_cols=2)

    assert layout_manager.get_widget(0, 0) == btn1
    assert layout_manager.get_widget(0, 1) == btn2
    assert layout_manager.get_widget(1, 0) == btn3
    assert layout_manager.get_widget(1, 1) == btn4


def test_change_layout_num_rows(layout_manager):
    """Test changing the layout by specifying only the number of rows."""
    btn_list = [QPushButton(f"Button {i}") for i in range(1, 7)]
    for btn in btn_list:
        layout_manager.add_widget(btn)

    layout_manager.change_layout(num_rows=3)

    assert layout_manager.get_widget(0, 0) == btn_list[0]
    assert layout_manager.get_widget(0, 1) == btn_list[1]
    assert layout_manager.get_widget(1, 0) == btn_list[2]
    assert layout_manager.get_widget(1, 1) == btn_list[3]
    assert layout_manager.get_widget(2, 0) == btn_list[4]
    assert layout_manager.get_widget(2, 1) == btn_list[5]


def test_shift_all_widgets(layout_manager):
    """Test shifting all widgets down and then up."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")

    layout_manager.add_widget(btn1, row=0, col=0)
    layout_manager.add_widget(btn2, row=0, col=1)

    # Shift all down
    layout_manager.shift_all_widgets(direction="down")

    assert layout_manager.get_widget(1, 0) == btn1
    assert layout_manager.get_widget(1, 1) == btn2

    # Shift all up
    layout_manager.shift_all_widgets(direction="up")

    assert layout_manager.get_widget(0, 0) == btn1
    assert layout_manager.get_widget(0, 1) == btn2


def test_add_widget_auto_position(layout_manager):
    """Test adding widgets without specifying row and column."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")

    layout_manager.add_widget(btn1)
    layout_manager.add_widget(btn2)

    assert layout_manager.get_widget(0, 0) == btn1
    assert layout_manager.get_widget(0, 1) == btn2


def test_clear_layout(layout_manager):
    """Test clearing the entire layout."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")
    layout_manager.add_widget(btn1)
    layout_manager.add_widget(btn2)

    layout_manager.clear_layout()

    assert layout_manager.get_widget(0, 0) is None
    assert layout_manager.get_widget(0, 1) is None
    assert len(layout_manager.widget_positions) == 0


def test_add_widget_with_span(layout_manager):
    """Test adding a widget with rowspan and colspan."""
    btn1 = QPushButton("Button 1")
    layout_manager.add_widget(btn1, row=0, col=0, rowspan=2, colspan=2)

    assert layout_manager.widget_positions[btn1] == (0, 0, 2, 2)


def test_add_widget_overlap_with_span(layout_manager):
    """
    Test adding a widget that overlaps with an existing widget's span.
    The code will attempt to shift widgets accordingly.
    """
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")

    layout_manager.add_widget(btn1, row=0, col=0, rowspan=2, colspan=1)

    layout_manager.add_widget(btn2, row=1, col=1, shift_direction="right")

    assert layout_manager.get_widget(0, 0) == btn1
    assert layout_manager.widget_positions[btn1] == (0, 0, 2, 1)
    assert layout_manager.get_widget(1, 1) == btn2
    assert layout_manager.widget_positions[btn2] == (1, 1, 1, 1)


@pytest.mark.parametrize(
    "position, btn3_coords",
    [("left", (1, 0)), ("right", (1, 2)), ("top", (0, 1)), ("bottom", (2, 1))],
)
def test_add_widget_relative(layout_manager, position, btn3_coords):
    """Test adding a widget relative to an existing widget using parameterized data."""
    expected_row, expected_col = btn3_coords

    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")
    btn3 = QPushButton("Button 3")

    layout_manager.add_widget(btn1, row=0, col=0)
    layout_manager.add_widget(btn2, row=1, col=1)

    layout_manager.add_widget_relative(btn3, reference_widget=btn2, position=position)

    assert layout_manager.get_widget(0, 0) == btn1
    assert layout_manager.get_widget(1, 1) == btn2
    assert layout_manager.get_widget(expected_row, expected_col) == btn3


def test_add_widget_relative_invalid_position(layout_manager):
    """Test adding a widget relative to an existing widget with an invalid position."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")

    layout_manager.add_widget(btn1, row=1, col=1)
    with pytest.raises(ValueError) as exc_info:
        layout_manager.add_widget_relative(btn2, reference_widget=btn1, position="invalid_position")

    assert "Invalid position. Choose from 'left', 'right', 'top', 'bottom'." in str(exc_info.value)
    btn2.deleteLater()


def test_add_widget_relative_to_nonexistent_widget(layout_manager):
    """Test adding a widget relative to a widget that does not exist in the layout."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")

    with pytest.raises(ValueError) as exc_info:
        layout_manager.add_widget_relative(btn2, reference_widget=btn1, position="left")

    assert "Reference widget not found in layout." in str(exc_info.value)
    btn1.deleteLater()
    btn2.deleteLater()


def test_add_widget_relative_with_shift(layout_manager):
    """Test adding a widget relative to an existing widget with shifting."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")
    btn3 = QPushButton("Button 3")

    layout_manager.add_widget(btn1, row=1, col=1)
    layout_manager.add_widget(btn2, row=1, col=0)

    layout_manager.add_widget_relative(
        btn3, reference_widget=btn1, position="left", shift_direction="right"
    )

    assert layout_manager.get_widget(0, 0) == btn3
    assert layout_manager.get_widget(1, 1) == btn2
    assert layout_manager.get_widget(0, 1) == btn1


def test_move_widget_by_object(layout_manager):
    """Test moving a widget using the widget object."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")

    layout_manager.add_widget(btn1)
    layout_manager.add_widget(btn2, row=0, col=1)

    layout_manager.move_widget_by_object(btn1, new_row=1, new_col=1)

    # the grid is reindex after each move, so the new positions are (0,0) and (1,0), because visually there is only one column
    assert layout_manager.get_widget(1, 0) == btn1
    assert layout_manager.get_widget(0, 0) == btn2


def test_move_widget_by_coords(layout_manager):
    """Test moving a widget using its current coordinates."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")

    layout_manager.add_widget(btn1)
    layout_manager.add_widget(btn2, row=0, col=1)

    layout_manager.move_widget_by_coords(0, 0, 1, 0, shift_direction="down")

    assert layout_manager.get_widget(1, 0) == btn1
    assert layout_manager.get_widget(0, 1) == btn2


def test_change_layout_no_arguments(layout_manager):
    """Test changing the layout with no arguments (should do nothing)."""
    btn1 = QPushButton("Button 1")
    layout_manager.add_widget(btn1, row=0, col=0)

    layout_manager.change_layout()

    assert layout_manager.get_widget(0, 0) == btn1
    assert len(layout_manager.widget_positions) == 1


def test_remove_nonexistent_widget(layout_manager):
    """Test removing a widget that doesn't exist in the layout."""
    with pytest.raises(ValueError) as exc_info:
        layout_manager.remove(row=0, col=0)

    assert "No widget found at position (0, 0)." in str(exc_info.value)


def test_reindex_grid_after_removal(layout_manager):
    """Test reindexing the grid after removing a widget."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")
    layout_manager.add_widget(btn1)
    layout_manager.add_widget(btn2, row=0, col=1)

    layout_manager.remove_widget(btn1)
    layout_manager.reindex_grid()

    # After removal and reindex, btn2 should shift to (0,0)
    assert layout_manager.get_widget(0, 0) == btn2
    assert layout_manager.widget_positions[btn2] == (0, 0, 1, 1)


def test_shift_all_widgets_up_at_top_row(layout_manager):
    """Test shifting all widgets up when they are already at the top row."""
    btn1 = QPushButton("Button 1")
    btn2 = QPushButton("Button 2")

    layout_manager.add_widget(btn1, row=0, col=0)
    layout_manager.add_widget(btn2, row=0, col=1)

    # Shifting up should cause an error since widgets can't move above row 0
    with pytest.raises(ValueError) as exc_info:
        layout_manager.shift_all_widgets(direction="up")

    assert "Shifting widgets out of grid boundaries." in str(exc_info.value)
