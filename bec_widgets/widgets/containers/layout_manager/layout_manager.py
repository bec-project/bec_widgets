from __future__ import annotations

import math
import sys
from typing import Dict, Literal, Optional, Set, Tuple, Union

from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from typeguard import typechecked

from bec_widgets.cli.rpc.rpc_widget_handler import widget_handler


class LayoutManagerWidget(QWidget):
    """
    A robust layout manager that extends QGridLayout functionality, allowing
    users to add/remove widgets, access widgets by coordinates, shift widgets,
    and change the layout dynamically with automatic reindexing to keep the grid compact.

    Supports adding widgets via QWidget instances or string identifiers referencing the widget handler.
    """

    def __init__(self, parent=None, auto_reindex=True):
        super().__init__(parent)
        self.layout = QGridLayout(self)
        self.auto_reindex = auto_reindex

        # Mapping from widget to its position (row, col, rowspan, colspan)
        self.widget_positions: Dict[QWidget, Tuple[int, int, int, int]] = {}

        # Mapping from (row, col) to widget
        self.position_widgets: Dict[Tuple[int, int], QWidget] = {}

        # Keep track of the current position for automatic placement
        self.current_row = 0
        self.current_col = 0

    def add_widget(
        self,
        widget: QWidget | str,
        row: int | None = None,
        col: Optional[int] = None,
        rowspan: int = 1,
        colspan: int = 1,
        shift_existing: bool = True,
        shift_direction: Literal["down", "up", "left", "right"] = "right",
    ) -> QWidget:
        """
        Add a widget to the grid with enhanced shifting capabilities.

        Args:
            widget (QWidget | str): The widget to add. If str, it is used to create a widget via widget_handler.
            row (int, optional): The row to add the widget to. If None, the next available row is used.
            col (int, optional): The column to add the widget to. If None, the next available column is used.
            rowspan (int): Number of rows the widget spans. Default is 1.
            colspan (int): Number of columns the widget spans. Default is 1.
            shift_existing (bool): Whether to shift existing widgets if the target position is occupied. Default is True.
            shift_direction (Literal["down", "up", "left", "right"]): Direction to shift existing widgets. Default is "right".

        Returns:
            QWidget: The widget that was added.
        """
        # Handle widget creation if a BECWidget string identifier is provided
        if isinstance(widget, str):
            widget = widget_handler.create_widget(widget)

        if row is None:
            row = self.current_row
        if col is None:
            col = self.current_col

        if (row, col) in self.position_widgets:
            if shift_existing:
                # Attempt to shift the existing widget in the specified direction
                self.shift_widgets(direction=shift_direction, start_row=row, start_col=col)
            else:
                raise ValueError(f"Position ({row}, {col}) is already occupied.")

            # Add the widget to the layout
        self.layout.addWidget(widget, row, col, rowspan, colspan)
        self.widget_positions[widget] = (row, col, rowspan, colspan)
        self.position_widgets[(row, col)] = widget

        # Update current position for automatic placement
        self.current_col = col + colspan
        self.current_row = max(self.current_row, row)

        if self.auto_reindex:
            self.reindex_grid()

        return widget

    def add_widget_relative(
        self,
        widget: QWidget | str,
        reference_widget: QWidget,
        position: Literal["left", "right", "top", "bottom"],
        rowspan: int = 1,
        colspan: int = 1,
        shift_existing: bool = True,
        shift_direction: Literal["down", "up", "left", "right"] = "right",
    ) -> QWidget:
        """
        Add a widget relative to an existing widget.

        Args:
            widget (QWidget | str): The widget to add. If str, it is used to create a widget via widget_handler.
            reference_widget (QWidget): The widget relative to which the new widget will be placed.
            position (Literal["left", "right", "top", "bottom"]): Position relative to the reference widget.
            rowspan (int): Number of rows the widget spans. Default is 1.
            colspan (int): Number of columns the widget spans. Default is 1.
            shift_existing (bool): Whether to shift existing widgets if the target position is occupied.
            shift_direction (Literal["down", "up", "left", "right"]): Direction to shift existing widgets.

        Returns:
            QWidget: The widget that was added.

        Raises:
            ValueError: If the reference widget is not found.
        """
        if reference_widget not in self.widget_positions:
            raise ValueError("Reference widget not found in layout.")

        ref_row, ref_col, ref_rowspan, ref_colspan = self.widget_positions[reference_widget]

        # Determine new widget position based on the specified relative position
        if position == "left":
            new_row = ref_row
            new_col = ref_col - 1
        elif position == "right":
            new_row = ref_row
            new_col = ref_col + ref_colspan
        elif position == "top":
            new_row = ref_row - 1
            new_col = ref_col
        elif position == "bottom":
            new_row = ref_row + ref_rowspan
            new_col = ref_col
        else:
            raise ValueError("Invalid position. Choose from 'left', 'right', 'top', 'bottom'.")

        # Add the widget at the calculated position
        return self.add_widget(
            widget=widget,
            row=new_row,
            col=new_col,
            rowspan=rowspan,
            colspan=colspan,
            shift_existing=shift_existing,
            shift_direction=shift_direction,
        )

    def move_widget_by_coords(
        self,
        current_row: int,
        current_col: int,
        new_row: int,
        new_col: int,
        shift: bool = True,
        shift_direction: Literal["down", "up", "left", "right"] = "right",
    ) -> None:
        """
        Move a widget from (current_row, current_col) to (new_row, new_col).

        Args:
            current_row (int): Current row of the widget.
            current_col (int): Current column of the widget.
            new_row (int): Target row.
            new_col (int): Target column.
            shift (bool): Whether to shift existing widgets if the target position is occupied.
            shift_direction (Literal["down", "up", "left", "right"]): Direction to shift existing widgets.

        Raises:
            ValueError: If the widget is not found or target position is invalid.
        """
        self.move_widget(
            old_row=current_row,
            old_col=current_col,
            new_row=new_row,
            new_col=new_col,
            shift=shift,
            shift_direction=shift_direction,
        )

    @typechecked
    def move_widget_by_object(
        self,
        widget: QWidget,
        new_row: int,
        new_col: int,
        shift: bool = True,
        shift_direction: Literal["down", "up", "left", "right"] = "right",
    ) -> None:
        """
        Move a widget to a new position using the widget object.

        Args:
            widget (QWidget): The widget to move.
            new_row (int): Target row.
            new_col (int): Target column.
            shift (bool): Whether to shift existing widgets if the target position is occupied.
            shift_direction (Literal["down", "up", "left", "right"]): Direction to shift existing widgets.

        Raises:
            ValueError: If the widget is not found or target position is invalid.
        """
        if widget not in self.widget_positions:
            raise ValueError("Widget not found in layout.")

        old_position = self.widget_positions[widget]
        old_row, old_col = old_position[0], old_position[1]

        self.move_widget(
            old_row=old_row,
            old_col=old_col,
            new_row=new_row,
            new_col=new_col,
            shift=shift,
            shift_direction=shift_direction,
        )

    @typechecked
    def move_widget(
        self,
        old_row: int | None = None,
        old_col: int | None = None,
        new_row: int | None = None,
        new_col: int | None = None,
        shift: bool = True,
        shift_direction: Literal["down", "up", "left", "right"] = "right",
    ) -> None:
        """
        Move a widget to a new position. If the new position is occupied and shift is True,
        shift the existing widget to the specified direction.

        Args:
            old_row (int, optional): The current row of the widget.
            old_col (int, optional): The current column of the widget.
            new_row (int, optional): The target row to move the widget to.
            new_col (int, optional): The target column to move the widget to.
            shift (bool): Whether to shift existing widgets if the target position is occupied.
            shift_direction (Literal["down", "up", "left", "right"]): Direction to shift existing widgets.

        Raises:
            ValueError: If the widget is not found or target position is invalid.
        """
        if new_row is None or new_col is None:
            raise ValueError("Must provide both new_row and new_col to move a widget.")

        if old_row is None and old_col is None:
            raise ValueError(f"No widget found at position ({old_row}, {old_col}).")
        widget = self.get_widget(old_row, old_col)

        if (new_row, new_col) in self.position_widgets:
            if not shift:
                raise ValueError(f"Position ({new_row}, {new_col}) is already occupied.")
            # Shift the existing widget to make space
            self.shift_widgets(
                direction=shift_direction,
                start_row=new_row if shift_direction in ["down", "up"] else 0,
                start_col=new_col if shift_direction in ["left", "right"] else 0,
            )

        # Proceed to move the widget
        self.layout.removeWidget(widget)
        old_position = self.widget_positions.pop(widget)
        self.position_widgets.pop((old_position[0], old_position[1]))

        self.layout.addWidget(widget, new_row, new_col, old_position[2], old_position[3])
        self.widget_positions[widget] = (new_row, new_col, old_position[2], old_position[3])
        self.position_widgets[(new_row, new_col)] = widget

        # Update current_row and current_col for automatic placement if needed
        self.current_row = max(self.current_row, new_row)
        self.current_col = max(self.current_col, new_col + old_position[3])

        if self.auto_reindex:
            self.reindex_grid()

    @typechecked
    def shift_widgets(
        self,
        direction: Literal["down", "up", "left", "right"],
        start_row: int = 0,
        start_col: int = 0,
    ) -> None:
        """
        Shift widgets in the grid in the specified direction starting from the given position.

        Args:
            direction (Literal["down", "up", "left", "right"]): Direction to shift widgets.
            start_row (int): Starting row index.
            start_col (int): Starting column index.

        Raises:
            ValueError: If shifting causes widgets to go out of grid boundaries.
        """
        shifts = []
        positions_to_shift = [(start_row, start_col)]
        visited_positions = set()

        while positions_to_shift:
            row, col = positions_to_shift.pop(0)
            if (row, col) in visited_positions:
                continue
            visited_positions.add((row, col))

            widget = self.position_widgets.get((row, col))
            if widget is None:
                continue  # No widget at this position

            # Compute new position based on the direction
            if direction == "down":
                new_row = row + 1
                new_col = col
            elif direction == "up":
                new_row = row - 1
                new_col = col
            elif direction == "right":
                new_row = row
                new_col = col + 1
            elif direction == "left":
                new_row = row
                new_col = col - 1

            # Check for negative indices
            if new_row < 0 or new_col < 0:
                raise ValueError("Shifting widgets out of grid boundaries.")

            # If the new position is occupied, add it to the positions to shift
            if (new_row, new_col) in self.position_widgets:
                positions_to_shift.append((new_row, new_col))

            shifts.append(
                (widget, (row, col), (new_row, new_col), self.widget_positions[widget][2:])
            )

        # Remove all widgets from their old positions
        for widget, (old_row, old_col), _, _ in shifts:
            self.layout.removeWidget(widget)
            self.position_widgets.pop((old_row, old_col))

        # Add widgets to their new positions
        for widget, _, (new_row, new_col), (rowspan, colspan) in shifts:
            self.layout.addWidget(widget, new_row, new_col, rowspan, colspan)
            self.widget_positions[widget] = (new_row, new_col, rowspan, colspan)
            self.position_widgets[(new_row, new_col)] = widget

            # Update current_row and current_col if needed
            self.current_row = max(self.current_row, new_row)
            self.current_col = max(self.current_col, new_col + colspan)

    def shift_all_widgets(self, direction: Literal["down", "up", "left", "right"]) -> None:
        """
        Shift all widgets in the grid in the specified direction to make room and prevent negative indices.

        Args:
            direction (Literal["down", "up", "left", "right"]): Direction to shift all widgets.
        """
        # First, collect all the shifts to perform
        shifts = []
        for widget, (row, col, rowspan, colspan) in self.widget_positions.items():

            if direction == "down":
                new_row = row + 1
                new_col = col
            elif direction == "up":
                new_row = row - 1
                new_col = col
            elif direction == "right":
                new_row = row
                new_col = col + 1
            elif direction == "left":
                new_row = row
                new_col = col - 1

            # Check for negative indices
            if new_row < 0 or new_col < 0:
                raise ValueError("Shifting widgets out of grid boundaries.")

            shifts.append((widget, (row, col), (new_row, new_col), (rowspan, colspan)))

        # Now perform the shifts
        for widget, (old_row, old_col), (new_row, new_col), (rowspan, colspan) in shifts:
            self.layout.removeWidget(widget)
            self.position_widgets.pop((old_row, old_col))

        for widget, (old_row, old_col), (new_row, new_col), (rowspan, colspan) in shifts:
            self.layout.addWidget(widget, new_row, new_col, rowspan, colspan)
            self.widget_positions[widget] = (new_row, new_col, rowspan, colspan)
            self.position_widgets[(new_row, new_col)] = widget

        # Update current_row and current_col based on new widget positions
        self.current_row = max((pos[0] for pos in self.position_widgets.keys()), default=0)
        self.current_col = max((pos[1] for pos in self.position_widgets.keys()), default=0)

    def remove(
        self,
        row: int | None = None,
        col: int | None = None,
        coordinates: Tuple[int, int] | None = None,
    ) -> None:
        """
        Remove a widget from the layout. Can be removed by widget ID or by coordinates.

        Args:
            row (int, optional): The row coordinate of the widget to remove.
            col (int, optional): The column coordinate of the widget to remove.
            coordinates (tuple[int, int], optional): The (row, col) coordinates of the widget to remove.

        Raises:
            ValueError: If the widget to remove is not found.
        """
        if coordinates:
            row, col = coordinates
            widget = self.get_widget(row, col)
            if widget is None:
                raise ValueError(f"No widget found at coordinates {coordinates}.")
        elif row is not None and col is not None:
            widget = self.get_widget(row, col)
            if widget is None:
                raise ValueError(f"No widget found at position ({row}, {col}).")
        else:
            raise ValueError(
                "Must provide either widget_id, coordinates, or both row and col for removal."
            )

        self.remove_widget(widget)

    def remove_widget(self, widget: QWidget) -> None:
        """
        Remove a widget from the grid and reindex the grid to keep it compact.

        Args:
            widget (QWidget): The widget to remove.

        Raises:
            ValueError: If the widget is not found in the layout.
        """
        if widget not in self.widget_positions:
            raise ValueError("Widget not found in layout.")

        position = self.widget_positions.pop(widget)
        self.position_widgets.pop((position[0], position[1]))
        self.layout.removeWidget(widget)
        widget.setParent(None)  # Remove widget from the parent
        widget.deleteLater()

        # Reindex the grid to maintain compactness
        if self.auto_reindex:
            self.reindex_grid()

    def get_widget(self, row: int, col: int) -> QWidget | None:
        """
        Get the widget at the specified position.

        Args:
            row (int): The row coordinate.
            col (int): The column coordinate.

        Returns:
            QWidget | None: The widget at the specified position, or None if empty.
        """
        return self.position_widgets.get((row, col))

    def get_widget_position(self, widget: QWidget) -> Tuple[int, int, int, int] | None:
        """
        Get the position of the specified widget.

        Args:
            widget (QWidget): The widget to query.

        Returns:
            Tuple[int, int, int, int] | None: The (row, col, rowspan, colspan) tuple, or None if not found.
        """
        return self.widget_positions.get(widget)

    def change_layout(self, num_rows: int | None = None, num_cols: int | None = None) -> None:
        """
        Change the layout to have a certain number of rows and/or columns,
        rearranging the widgets accordingly.

        If only one of num_rows or num_cols is provided, the other is calculated automatically
        based on the number of widgets and the provided constraint.

        If both are provided, num_rows is calculated based on num_cols.

        Args:
            num_rows (int | None): The new maximum number of rows.
            num_cols (int | None): The new maximum number of columns.
        """
        if num_rows is None and num_cols is None:
            return  # Nothing to change

        total_widgets = len(self.widget_positions)

        if num_cols is not None:
            # Calculate num_rows based on num_cols
            num_rows = math.ceil(total_widgets / num_cols)
        elif num_rows is not None:
            # Calculate num_cols based on num_rows
            num_cols = math.ceil(total_widgets / num_rows)

        # Sort widgets by current position (row-major order)
        widgets_sorted = sorted(
            self.widget_positions.items(),
            key=lambda item: (item[1][0], item[1][1]),  # Sort by row, then column
        )

        # Clear the layout without deleting widgets
        for widget, _ in widgets_sorted:
            self.layout.removeWidget(widget)

        # Reset position mappings
        self.widget_positions.clear()
        self.position_widgets.clear()

        # Re-add widgets based on new layout constraints
        current_row, current_col = 0, 0
        for widget, _ in widgets_sorted:
            if current_col >= num_cols:
                current_col = 0
                current_row += 1
            self.layout.addWidget(widget, current_row, current_col, 1, 1)
            self.widget_positions[widget] = (current_row, current_col, 1, 1)
            self.position_widgets[(current_row, current_col)] = widget
            current_col += 1

        # Update current_row and current_col for automatic placement
        self.current_row = current_row
        self.current_col = current_col

        # Reindex the grid to ensure compactness
        self.reindex_grid()

    def clear_layout(self) -> None:
        """
        Remove all widgets from the layout without deleting them.
        """
        for widget in list(self.widget_positions):
            self.layout.removeWidget(widget)
            self.position_widgets.pop(
                (self.widget_positions[widget][0], self.widget_positions[widget][1])
            )
            self.widget_positions.pop(widget)
            widget.setParent(None)  # Optionally hide/remove the widget

        self.current_row = 0
        self.current_col = 0

    def reindex_grid(self) -> None:
        """
        Reindex the grid to remove empty rows and columns, ensuring that
        widget coordinates are contiguous and start from (0, 0).
        """
        # Step 1: Collect all occupied positions
        occupied_positions = sorted(self.position_widgets.keys())

        if not occupied_positions:
            # No widgets to reindex
            self.clear_layout()
            return

        # Step 2: Determine the new mapping by eliminating empty columns and rows
        # Find unique rows and columns
        unique_rows = sorted(set(pos[0] for pos in occupied_positions))
        unique_cols = sorted(set(pos[1] for pos in occupied_positions))

        # Create mappings from old to new indices
        row_mapping = {old_row: new_row for new_row, old_row in enumerate(unique_rows)}
        col_mapping = {old_col: new_col for new_col, old_col in enumerate(unique_cols)}

        # Step 3: Collect widgets with their new positions
        widgets_with_new_positions = []
        for widget, (row, col, rowspan, colspan) in self.widget_positions.items():
            new_row = row_mapping[row]
            new_col = col_mapping[col]
            widgets_with_new_positions.append((widget, new_row, new_col, rowspan, colspan))

        # Step 4: Clear the layout and reset mappings
        self.clear_layout()

        # Reset current_row and current_col
        self.current_row = 0
        self.current_col = 0

        # Step 5: Re-add widgets with new positions
        for widget, new_row, new_col, rowspan, colspan in widgets_with_new_positions:
            self.layout.addWidget(widget, new_row, new_col, rowspan, colspan)
            self.widget_positions[widget] = (new_row, new_col, rowspan, colspan)
            self.position_widgets[(new_row, new_col)] = widget

            # Update current position for automatic placement
            self.current_col = max(self.current_col, new_col + colspan)
            self.current_row = max(self.current_row, new_row)

    def get_widgets_positions(self) -> Dict[QWidget, Tuple[int, int, int, int]]:
        """
        Get the positions of all widgets in the layout.

        Returns:
            Dict[QWidget, Tuple[int, int, int, int]]: Mapping of widgets to their (row, col, rowspan, colspan).
        """
        return self.widget_positions.copy()

    def print_all_button_text(self):
        """Debug function to print the text of all QPushButton widgets."""
        print("Coordinates - Button Text")
        for coord, widget in self.position_widgets.items():
            if isinstance(widget, QPushButton):
                print(f"{coord} - {widget.text()}")


####################################################################################################
# The following code is for the GUI control panel to interact with the LayoutManagerWidget.
# It is not covered by any tests as it serves only as an example for the LayoutManagerWidget class.
####################################################################################################


class ControlPanel(QWidget):  # pragma: no cover
    def __init__(self, layout_manager: LayoutManagerWidget):
        super().__init__()
        self.layout_manager = layout_manager
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # Add Widget by Coordinates
        add_coord_group = QGroupBox("Add Widget by Coordinates")
        add_coord_layout = QGridLayout()

        add_coord_layout.addWidget(QLabel("Text:"), 0, 0)
        self.text_input = QLineEdit()
        add_coord_layout.addWidget(self.text_input, 0, 1)

        add_coord_layout.addWidget(QLabel("Row:"), 1, 0)
        self.row_input = QSpinBox()
        self.row_input.setMinimum(0)
        add_coord_layout.addWidget(self.row_input, 1, 1)

        add_coord_layout.addWidget(QLabel("Column:"), 2, 0)
        self.col_input = QSpinBox()
        self.col_input.setMinimum(0)
        add_coord_layout.addWidget(self.col_input, 2, 1)

        self.add_button = QPushButton("Add at Coordinates")
        self.add_button.clicked.connect(self.add_at_coordinates)
        add_coord_layout.addWidget(self.add_button, 3, 0, 1, 2)

        add_coord_group.setLayout(add_coord_layout)
        main_layout.addWidget(add_coord_group)

        # Add Widget Relative
        add_rel_group = QGroupBox("Add Widget Relative to Existing")
        add_rel_layout = QGridLayout()

        add_rel_layout.addWidget(QLabel("Text:"), 0, 0)
        self.rel_text_input = QLineEdit()
        add_rel_layout.addWidget(self.rel_text_input, 0, 1)

        add_rel_layout.addWidget(QLabel("Reference Widget:"), 1, 0)
        self.ref_widget_combo = QComboBox()
        add_rel_layout.addWidget(self.ref_widget_combo, 1, 1)

        add_rel_layout.addWidget(QLabel("Position:"), 2, 0)
        self.position_combo = QComboBox()
        self.position_combo.addItems(["left", "right", "top", "bottom"])
        add_rel_layout.addWidget(self.position_combo, 2, 1)

        self.add_rel_button = QPushButton("Add Relative")
        self.add_rel_button.clicked.connect(self.add_relative)
        add_rel_layout.addWidget(self.add_rel_button, 3, 0, 1, 2)

        add_rel_group.setLayout(add_rel_layout)
        main_layout.addWidget(add_rel_group)

        # Remove Widget
        remove_group = QGroupBox("Remove Widget")
        remove_layout = QGridLayout()

        remove_layout.addWidget(QLabel("Row:"), 0, 0)
        self.remove_row_input = QSpinBox()
        self.remove_row_input.setMinimum(0)
        remove_layout.addWidget(self.remove_row_input, 0, 1)

        remove_layout.addWidget(QLabel("Column:"), 1, 0)
        self.remove_col_input = QSpinBox()
        self.remove_col_input.setMinimum(0)
        remove_layout.addWidget(self.remove_col_input, 1, 1)

        self.remove_button = QPushButton("Remove at Coordinates")
        self.remove_button.clicked.connect(self.remove_widget)
        remove_layout.addWidget(self.remove_button, 2, 0, 1, 2)

        remove_group.setLayout(remove_layout)
        main_layout.addWidget(remove_group)

        # Change Layout
        change_layout_group = QGroupBox("Change Layout")
        change_layout_layout = QGridLayout()

        change_layout_layout.addWidget(QLabel("Number of Rows:"), 0, 0)
        self.change_rows_input = QSpinBox()
        self.change_rows_input.setMinimum(1)
        self.change_rows_input.setValue(1)  # Default value
        change_layout_layout.addWidget(self.change_rows_input, 0, 1)

        change_layout_layout.addWidget(QLabel("Number of Columns:"), 1, 0)
        self.change_cols_input = QSpinBox()
        self.change_cols_input.setMinimum(1)
        self.change_cols_input.setValue(1)  # Default value
        change_layout_layout.addWidget(self.change_cols_input, 1, 1)

        self.change_layout_button = QPushButton("Apply Layout Change")
        self.change_layout_button.clicked.connect(self.change_layout)
        change_layout_layout.addWidget(self.change_layout_button, 2, 0, 1, 2)

        change_layout_group.setLayout(change_layout_layout)
        main_layout.addWidget(change_layout_group)

        # Remove All Widgets
        self.clear_all_button = QPushButton("Clear All Widgets")
        self.clear_all_button.clicked.connect(self.clear_all_widgets)
        main_layout.addWidget(self.clear_all_button)

        # Refresh Reference Widgets and Print Button
        self.refresh_button = QPushButton("Refresh Reference Widgets")
        self.refresh_button.clicked.connect(self.refresh_references)
        self.print_button = QPushButton("Print All Button Text")
        self.print_button.clicked.connect(self.layout_manager.print_all_button_text)
        main_layout.addWidget(self.refresh_button)
        main_layout.addWidget(self.print_button)

        main_layout.addStretch()
        self.setLayout(main_layout)
        self.refresh_references()

    def refresh_references(self):
        self.ref_widget_combo.clear()
        widgets = self.layout_manager.get_widgets_positions()
        for widget in widgets:
            if isinstance(widget, QPushButton):
                self.ref_widget_combo.addItem(widget.text(), widget)

    def add_at_coordinates(self):
        text = self.text_input.text()
        row = self.row_input.value()
        col = self.col_input.value()

        if not text:
            QMessageBox.warning(self, "Input Error", "Please enter text for the button.")
            return

        button = QPushButton(text)
        try:
            self.layout_manager.add_widget(widget=button, row=row, col=col)
            self.refresh_references()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def add_relative(self):
        text = self.rel_text_input.text()
        ref_index = self.ref_widget_combo.currentIndex()
        ref_widget = self.ref_widget_combo.itemData(ref_index)
        position = self.position_combo.currentText()

        if not text:
            QMessageBox.warning(self, "Input Error", "Please enter text for the button.")
            return

        if ref_widget is None:
            QMessageBox.warning(self, "Input Error", "Please select a reference widget.")
            return

        button = QPushButton(text)
        try:
            self.layout_manager.add_widget_relative(
                widget=button, reference_widget=ref_widget, position=position
            )
            self.refresh_references()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def remove_widget(self):
        row = self.remove_row_input.value()
        col = self.remove_col_input.value()

        try:
            widget = self.layout_manager.get_widget(row, col)
            if widget is None:
                QMessageBox.warning(self, "Not Found", f"No widget found at ({row}, {col}).")
                return
            self.layout_manager.remove_widget(widget)
            self.refresh_references()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def change_layout(self):
        num_rows = self.change_rows_input.value()
        num_cols = self.change_cols_input.value()

        try:
            self.layout_manager.change_layout(num_rows=num_rows, num_cols=num_cols)
            self.refresh_references()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def clear_all_widgets(self):
        reply = QMessageBox.question(
            self,
            "Confirm Clear",
            "Are you sure you want to remove all widgets?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                self.layout_manager.clear_layout()
                self.refresh_references()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))


class MainWindow(QMainWindow):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Layout Manager Demo")
        self.resize(800, 600)
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QHBoxLayout()

        # Layout Area GroupBox
        layout_group = QGroupBox("Layout Area")
        layout_group.setMinimumSize(400, 400)
        layout_layout = QVBoxLayout()

        self.layout_manager = LayoutManagerWidget()
        layout_layout.addWidget(self.layout_manager)

        layout_group.setLayout(layout_layout)

        # Splitter
        splitter = QSplitter()
        splitter.addWidget(layout_group)

        # Control Panel
        control_panel = ControlPanel(self.layout_manager)
        control_group = QGroupBox("Control Panel")
        control_layout = QVBoxLayout()
        control_layout.addWidget(control_panel)
        control_layout.addStretch()
        control_group.setLayout(control_layout)
        splitter.addWidget(control_group)

        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
