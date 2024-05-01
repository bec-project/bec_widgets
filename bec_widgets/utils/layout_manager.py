from collections import OrderedDict
from typing import Literal

from qtpy.QtWidgets import QGridLayout, QWidget


class GridLayoutManager:
    """
    GridLayoutManager class is used to manage widgets in a QGridLayout and extend its functionality.

    The GridLayoutManager class provides methods to add, move, and check the position of widgets in a QGridLayout.
    It also provides a method to get the positions of all widgets in the layout.

    Args:
        layout(QGridLayout): The layout to manage.
    """

    def __init__(self, layout: QGridLayout):
        self.layout = layout

    def is_position_occupied(self, row: int, col: int) -> bool:
        """
        Check if the position in the layout is occupied by a widget.
        Args:
            row(int): The row to check.
            col(int): The column to check.

        Returns:
            bool: True if the position is occupied, False otherwise.
        """
        for i in range(self.layout.count()):
            widget_row, widget_col, _, _ = self.layout.getItemPosition(i)
            if widget_row == row and widget_col == col:
                return True
        return False

    def shift_widgets(
        self,
        direction: Literal["down", "up", "left", "right"] = "down",
        start_row: int = 0,
        start_col: int = 0,
    ):
        """
        Shift widgets in the layout in the specified direction starting from the specified position.
        Args:
            direction(str): The direction to shift the widgets. Can be "down", "up", "left", or "right".
            start_row(int): The row to start shifting from. Default is 0.
            start_col(int): The column to start shifting from. Default is 0.
        """
        for i in reversed(range(self.layout.count())):
            widget_item = self.layout.itemAt(i)
            widget = widget_item.widget()
            row, col, rowspan, colspan = self.layout.getItemPosition(i)
            if direction == "down" and row >= start_row:
                self.layout.addWidget(widget, row + 1, col, rowspan, colspan)
            elif direction == "up" and row > start_row:
                self.layout.addWidget(widget, row - 1, col, rowspan, colspan)
            elif direction == "right" and col >= start_col:
                self.layout.addWidget(widget, row, col + 1, rowspan, colspan)
            elif direction == "left" and col > start_col:
                self.layout.addWidget(widget, row, col - 1, rowspan, colspan)

    def move_widget(self, widget: QWidget, new_row: int, new_col: int):
        """
        Move a widget to a new position in the layout.
        Args:
            widget(QWidget): The widget to move.
            new_row(int): The new row to move the widget to.
            new_col(int): The new column to move the widget to.
        """
        self.layout.removeWidget(widget)
        self.layout.addWidget(widget, new_row, new_col)

    def add_widget(
        self,
        widget: QWidget,
        row=None,
        col=0,
        rowspan=1,
        colspan=1,
        shift: Literal["down", "up", "left", "right"] = "down",
    ):
        """
        Add a widget to the layout at the specified position.
        Args:
            widget(QWidget): The widget to add.
            row(int): The row to add the widget to. If None, the widget will be added to the next available row.
            col(int): The column to add the widget to. Default is 0.
            rowspan(int): The number of rows the widget will span. Default is 1.
            colspan(int): The number of columns the widget will span. Default is 1.
            shift(str): The direction to shift the widgets if the position is occupied. Can be "down", "up", "left", or "right".
        """
        if row is None:
            row = self.layout.rowCount()
        if self.is_position_occupied(row, col):
            self.shift_widgets(shift, start_row=row)
        self.layout.addWidget(widget, row, col, rowspan, colspan)

    def get_widgets_positions(self) -> dict:
        """
        Get the positions of all widgets in the layout.
        Returns:
            dict: A dictionary with the positions of the widgets in the layout.

        """
        positions = []
        for i in range(self.layout.count()):
            widget_item = self.layout.itemAt(i)
            widget = widget_item.widget()
            if widget:
                position = self.layout.getItemPosition(i)
                positions.append((position, widget))
        positions.sort(key=lambda x: (x[0][0], x[0][1], x[0][2], x[0][3]))
        ordered_positions = OrderedDict()
        for pos, widget in positions:
            ordered_positions[pos] = widget
        return ordered_positions
