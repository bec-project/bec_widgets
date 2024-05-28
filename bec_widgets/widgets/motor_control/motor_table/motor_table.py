# pylint: disable = no-name-in-module,missing-module-docstring
import os

from qtpy import uic
from qtpy.QtCore import Qt
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtGui import QDoubleValidator, QKeySequence
from qtpy.QtWidgets import (
    QCheckBox,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QShortcut,
    QTableWidget,
    QTableWidgetItem,
)

from bec_widgets.utils import UILoader
from bec_widgets.widgets.motor_control.motor_control import MotorControlWidget


class MotorCoordinateTable(MotorControlWidget):
    """
    Widget to save coordinates from motor, display them in the table and move back to them.
    There are two modes of operation:
        - Individual: Each row is a single coordinate.
        - Start/Stop: Each pair of rows is a start and end coordinate.
    Signals:
        plot_coordinates_signal (pyqtSignal(list, str, str)): Signal to plot the coordinates in the MotorMap.
    Slots:
        add_coordinate (pyqtSlot(tuple)): Slot to add a coordinate to the table.
        mode_switch (pyqtSlot): Slot to switch between individual and start/stop mode.
    """

    plot_coordinates_signal = pyqtSignal(list, str, str)

    def _load_ui(self):
        """Load the UI for the coordinate table."""
        current_path = os.path.dirname(__file__)
        self.ui = UILoader().load_ui(os.path.join(current_path, "motor_table.ui"), self)

    def _init_ui(self):
        """Initialize the UI"""
        # Setup table behaviour
        self._setup_table()
        self.ui.table.setSelectionBehavior(QTableWidget.SelectRows)

        # for tag columns default tag
        self.tag_counter = 1

        # Connect signals and slots
        self.ui.checkBox_resize_auto.stateChanged.connect(self.resize_table_auto)
        self.ui.comboBox_mode.currentIndexChanged.connect(self.mode_switch)

        # Keyboard shortcuts for deleting a row
        self.delete_shortcut = QShortcut(QKeySequence(Qt.Key_Delete), self.ui.table)
        self.delete_shortcut.activated.connect(self.delete_selected_row)
        self.backspace_shortcut = QShortcut(QKeySequence(Qt.Key_Backspace), self.ui.table)
        self.backspace_shortcut.activated.connect(self.delete_selected_row)

        # Warning message for mode switch enable/disable
        self.warning_message = True

    @pyqtSlot(dict)
    def on_config_update(self, config: dict) -> None:
        """
        Update config dict
        Args:
            config(dict): New config dict
        """
        self.config = config

        # Get motor names
        self.motor_x, self.motor_y = (
            self.config["motor_control"]["motor_x"],
            self.config["motor_control"]["motor_y"],
        )

        # Decimal precision of the table coordinates
        self.precision = self.config["motor_control"].get("precision", 3)

        # Mode switch default option
        self.mode = self.config["motor_control"].get("mode", "Individual")

        # Set combobox to default mode
        self.ui.comboBox_mode.setCurrentText(self.mode)

        self._init_ui()

    def _setup_table(self):
        """Setup the table with appropriate headers and configurations."""
        mode = self.ui.comboBox_mode.currentText()

        if mode == "Individual":
            self._setup_individual_mode()
        elif mode == "Start/Stop":
            self._setup_start_stop_mode()
            self.start_stop_counter = 0  # TODO: remove this??

        self.wipe_motor_map_coordinates()

    def _setup_individual_mode(self):
        """Setup the table for individual mode."""
        self.ui.table.setColumnCount(5)
        self.ui.table.setHorizontalHeaderLabels(["Show", "Move", "Tag", "X", "Y"])
        self.ui.table.verticalHeader().setVisible(False)

    def _setup_start_stop_mode(self):
        """Setup the table for start/stop mode."""
        self.ui.table.setColumnCount(8)
        self.ui.table.setHorizontalHeaderLabels(
            [
                "Show",
                "Move [start]",
                "Move [end]",
                "Tag",
                "X [start]",
                "Y [start]",
                "X [end]",
                "Y [end]",
            ]
        )
        self.ui.table.verticalHeader().setVisible(False)
        # Set flag to track if the coordinate is stat or the end of the entry
        self.is_next_entry_end = False

    def mode_switch(self):
        """Switch between individual and start/stop mode."""
        last_selected_index = self.ui.comboBox_mode.currentIndex()

        if self.ui.table.rowCount() > 0 and self.warning_message is True:
            msgBox = QMessageBox()
            msgBox.setIcon(QMessageBox.Critical)
            msgBox.setText(
                "Switching modes will delete all table entries. Do you want to continue?"
            )
            msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            returnValue = msgBox.exec()

            if returnValue is QMessageBox.Cancel:
                self.ui.comboBox_mode.blockSignals(True)  # Block signals
                self.ui.comboBox_mode.setCurrentIndex(last_selected_index)
                self.ui.comboBox_mode.blockSignals(False)  # Unblock signals
                return

        # Wipe table
        self.wipe_motor_map_coordinates()

        # Initiate new table with new mode
        self._setup_table()

    @pyqtSlot(tuple)
    def add_coordinate(self, coordinates: tuple):
        """
        Add a coordinate to the table.
        Args:
            coordinates(tuple): Coordinates (x,y) to add to the table.
        """
        tag = f"Pos {self.tag_counter}"
        self.tag_counter += 1
        x, y = coordinates
        self._add_row(tag, x, y)

    def _add_row(self, tag: str, x: float, y: float) -> None:
        """
        Add a row to the table.
        Args:
            tag(str): Tag of the coordinate.
            x(float): X coordinate.
            y(float): Y coordinate.
        """

        mode = self.ui.comboBox_mode.currentText()
        if mode == "Individual":
            checkbox_pos = 0
            button_pos = 1
            tag_pos = 2
            x_pos = 3
            y_pos = 4
            coordinate_reference = "Individual"
            color = "green"

            # Add new row -> new entry
            row_count = self.ui.table.rowCount()
            self.ui.table.insertRow(row_count)

            # Add Widgets
            self._add_widgets(
                tag,
                x,
                y,
                row_count,
                checkbox_pos,
                tag_pos,
                button_pos,
                x_pos,
                y_pos,
                coordinate_reference,
                color,
            )

        if mode == "Start/Stop":
            # These positions are always fixed
            checkbox_pos = 0
            tag_pos = 3

            if self.is_next_entry_end is False:  # It is the start position of the entry
                print("Start position")
                button_pos = 1
                x_pos = 4
                y_pos = 5
                coordinate_reference = "Start"
                color = "blue"

                # Add new row -> new entry
                row_count = self.ui.table.rowCount()
                self.ui.table.insertRow(row_count)

                # Add Widgets
                self._add_widgets(
                    tag,
                    x,
                    y,
                    row_count,
                    checkbox_pos,
                    tag_pos,
                    button_pos,
                    x_pos,
                    y_pos,
                    coordinate_reference,
                    color,
                )

                # Next entry will be the end of the current entry
                self.is_next_entry_end = True

            elif self.is_next_entry_end is True:  # It is the end position of the entry
                print("End position")
                row_count = self.ui.table.rowCount() - 1  # Current row
                button_pos = 2
                x_pos = 6
                y_pos = 7
                coordinate_reference = "Stop"
                color = "red"

                # Add Widgets
                self._add_widgets(
                    tag,
                    x,
                    y,
                    row_count,
                    checkbox_pos,
                    tag_pos,
                    button_pos,
                    x_pos,
                    y_pos,
                    coordinate_reference,
                    color,
                )
                self.is_next_entry_end = False  # Next entry will be the start of the new entry

        # Auto table resize
        self.resize_table_auto()

    def _add_widgets(
        self,
        tag: str,
        x: float,
        y: float,
        row: int,
        checkBox_pos: int,
        tag_pos: int,
        button_pos: int,
        x_pos: int,
        y_pos: int,
        coordinate_reference: str,
        color: str,
    ) -> None:
        """
        Add widgets to the table.
        Args:
            tag(str): Tag of the coordinate.
            x(float): X coordinate.
            y(float): Y coordinate.
            row(int): Row of the QTableWidget where to add the widgets.
            checkBox_pos(int): Column where to put CheckBox.
            tag_pos(int): Column where to put Tag.
            button_pos(int): Column where to put Move button.
            x_pos(int): Column where to link x coordinate.
            y_pos(int): Column where to link y coordinate.
            coordinate_reference(str): Reference to the coordinate for MotorMap.
            color(str): Color of the coordinate for MotorMap.
        """
        # Add widgets
        self._add_checkbox(row, checkBox_pos, x_pos, y_pos)
        self._add_move_button(row, button_pos, x_pos, y_pos)
        self.ui.table.setItem(row, tag_pos, QTableWidgetItem(tag))
        self._add_line_edit(x, row, x_pos, x_pos, y_pos, coordinate_reference, color)
        self._add_line_edit(y, row, y_pos, x_pos, y_pos, coordinate_reference, color)

        # # Emit the coordinates to be plotted
        self.emit_plot_coordinates(x_pos, y_pos, coordinate_reference, color)

        # Connect item edit to emit coordinates
        self.ui.table.itemChanged.connect(
            lambda: print(f"item changed from {coordinate_reference} slot \n {x}-{y}-{color}")
        )
        self.ui.table.itemChanged.connect(
            lambda: self.emit_plot_coordinates(x_pos, y_pos, coordinate_reference, color)
        )

    def _add_checkbox(self, row: int, checkBox_pos: int, x_pos: int, y_pos: int):
        """
        Add a checkbox to the table.
        Args:
            row(int): Row of QTableWidget where to add the checkbox.
            checkBox_pos(int): Column where to put CheckBox.
            x_pos(int): Column where to link x coordinate.
            y_pos(int): Column where to link y coordinate.
        """
        show_checkbox = QCheckBox()
        show_checkbox.setChecked(True)
        show_checkbox.stateChanged.connect(lambda: self.emit_plot_coordinates(x_pos, y_pos))
        self.ui.table.setCellWidget(row, checkBox_pos, show_checkbox)

    def _add_move_button(self, row: int, button_pos: int, x_pos: int, y_pos: int) -> None:
        """
        Add a move button to the table.
        Args:
            row(int): Row of QTableWidget where to add the move button.
            button_pos(int): Column where to put move button.
            x_pos(int): Column where to link x coordinate.
            y_pos(int): Column where to link y coordinate.
        """
        move_button = QPushButton("Move")
        move_button.clicked.connect(lambda: self.handle_move_button_click(x_pos, y_pos))
        self.ui.table.setCellWidget(row, button_pos, move_button)

    def _add_line_edit(
        self,
        value: float,
        row: int,
        line_pos: int,
        x_pos: int,
        y_pos: int,
        coordinate_reference: str,
        color: str,
    ) -> None:
        """
        Add a QLineEdit to the table.
        Args:
            value(float): Initial value of the QLineEdit.
            row(int): Row of QTableWidget where to add the QLineEdit.
            line_pos(int): Column where to put QLineEdit.
            x_pos(int): Column where to link x coordinate.
            y_pos(int): Column where to link y coordinate.
            coordinate_reference(str): Reference to the coordinate for MotorMap.
            color(str): Color of the coordinate for MotorMap.
        """
        # Adding validator
        validator = QDoubleValidator()
        validator.setDecimals(self.precision)

        # Create line edit
        edit = QLineEdit(str(f"{value:.{self.precision}f}"))
        edit.setValidator(validator)
        edit.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Add line edit to the table
        self.ui.table.setCellWidget(row, line_pos, edit)
        edit.textChanged.connect(
            lambda: self.emit_plot_coordinates(x_pos, y_pos, coordinate_reference, color)
        )

    def wipe_motor_map_coordinates(self):
        """Wipe the motor map coordinates."""
        try:
            self.ui.table.itemChanged.disconnect()  # Disconnect all previous connections
        except TypeError:
            print("No previous connections to disconnect")
        self.ui.table.setRowCount(0)
        reference_tags = ["Individual", "Start", "Stop"]
        for reference_tag in reference_tags:
            self.plot_coordinates_signal.emit([], reference_tag, "green")

    def handle_move_button_click(self, x_pos: int, y_pos: int) -> None:
        """
        Handle the move button click.
        Args:
            x_pos(int): X position of the coordinate.
            y_pos(int): Y position of the coordinate.
        """
        button = self.sender()
        row = self.ui.table.indexAt(button.pos()).row()

        x = self.get_coordinate(row, x_pos)
        y = self.get_coordinate(row, y_pos)
        self.move_motor(x, y)

    def emit_plot_coordinates(self, x_pos: float, y_pos: float, reference_tag: str, color: str):
        """
        Emit the coordinates to be plotted.
        Args:
            x_pos(float): X position of the coordinate.
            y_pos(float): Y position of the coordinate.
            reference_tag(str): Reference tag of the coordinate.
            color(str): Color of the coordinate.
        """
        print(
            f"Emitting plot coordinates: x_pos={x_pos}, y_pos={y_pos}, reference_tag={reference_tag}, color={color}"
        )
        coordinates = []
        for row in range(self.ui.table.rowCount()):
            show = self.ui.table.cellWidget(row, 0).isChecked()
            x = self.get_coordinate(row, x_pos)
            y = self.get_coordinate(row, y_pos)

            coordinates.append((x, y, show))  # (x, y, show_flag)
        self.plot_coordinates_signal.emit(coordinates, reference_tag, color)

    def get_coordinate(self, row: int, column: int) -> float:
        """
        Helper function to get the coordinate from the table QLineEdit cells.
        Args:
            row(int): Row of the table.
            column(int): Column of the table.
        Returns:
            float: Value of the coordinate.
        """
        edit = self.ui.table.cellWidget(row, column)
        value = float(edit.text()) if edit and edit.text() != "" else None
        if value:
            return value

    def delete_selected_row(self):
        """Delete the selected row from the table."""
        selected_rows = self.ui.table.selectionModel().selectedRows()
        for row in selected_rows:
            self.ui.table.removeRow(row.row())
        if self.ui.comboBox_mode.currentText() == "Start/Stop":
            self.emit_plot_coordinates(x_pos=4, y_pos=5, reference_tag="Start", color="blue")
            self.emit_plot_coordinates(x_pos=6, y_pos=7, reference_tag="Stop", color="red")
            self.is_next_entry_end = False
        elif self.ui.comboBox_mode.currentText() == "Individual":
            self.emit_plot_coordinates(x_pos=3, y_pos=4, reference_tag="Individual", color="green")

    def resize_table_auto(self):
        """Resize the table to fit the contents."""
        if self.ui.checkBox_resize_auto.isChecked():
            self.ui.table.resizeColumnsToContents()

    def move_motor(self, x: float, y: float) -> None:
        """
        Move the motor to the target coordinates.
        Args:
            x(float): Target x coordinate.
            y(float): Target y coordinate.
        """
        self.motor_thread.move_absolute(self.motor_x, self.motor_y, (x, y))

    @pyqtSlot(str, str)
    def change_motors(self, motor_x: str, motor_y: str) -> None:
        """
        Change the active motors and update config.
        Can be connected to the selected_motors_signal from MotorControlSelection.
        Args:
            motor_x(str): New motor X to be controlled.
            motor_y(str): New motor Y to be controlled.
        """
        self.motor_x = motor_x
        self.motor_y = motor_y
        self.config["motor_control"]["motor_x"] = motor_x
        self.config["motor_control"]["motor_y"] = motor_y

    @pyqtSlot(int)
    def set_precision(self, precision: int) -> None:
        """
        Set the precision of the coordinates.
        Args:
            precision(int): Precision of the coordinates.
        """
        self.precision = precision
        self.config["motor_control"]["precision"] = precision
