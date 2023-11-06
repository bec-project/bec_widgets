import msgpack
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QComboBox,
    QPushButton,
    QVBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLayout,
    QGridLayout,
)

from bec_lib.core import MessageEndpoints


class ScanArgType:
    DEVICE = "device"
    FLOAT = "float"
    INT = "int"
    BOOL = "bool"


class ScanControl(QWidget):
    WIDGET_HANDLER = {
        ScanArgType.DEVICE: QLineEdit,
        ScanArgType.FLOAT: QDoubleSpinBox,
        ScanArgType.INT: QSpinBox,
        ScanArgType.BOOL: QCheckBox,
    }

    def __init__(self, parent=None, client=None, allowed_scans=None):
        super().__init__(parent)

        # Client from BEC + shortcuts to device manager and scans
        self.client = bec_dispatcher.client if client is None else client
        self.dev = self.client.device_manager.devices
        self.scans = self.client.scans

        # Scan list - allowed scans for the GUI
        self.allowed_scans = allowed_scans

        # Create and set main layout
        self._init_UI()

    def _init_UI(self):
        self.verticalLayout = QVBoxLayout(self)

        # Scan selection group box
        self.scan_selection_group = QGroupBox("Scan Selection", self)
        self.scan_selection_layout = QVBoxLayout(self.scan_selection_group)
        self.comboBox_scan_selection = QComboBox(self.scan_selection_group)
        self.scan_selection_layout.addWidget(self.comboBox_scan_selection)
        self.verticalLayout.addWidget(self.scan_selection_group)

        # Scan control group box
        self.scan_control_group = QGroupBox("Scan Control", self)
        self.scan_control_layout = QVBoxLayout(self.scan_control_group)
        self.verticalLayout.addWidget(self.scan_control_group)

        # Kwargs layout
        self.kwargs_layout = QGridLayout()
        self.scan_control_layout.addLayout(self.kwargs_layout)

        # 1st Separator
        self.add_horizontal_separator(self.scan_control_layout)

        # Buttons
        self.button_layout = QHBoxLayout()
        self.add_bundle_button = QPushButton("Add Bundle", self.scan_control_group)
        self.add_bundle_button.clicked.connect(self.add_bundle)
        self.remove_bundle_button = QPushButton("Remove Bundle", self.scan_control_group)
        self.remove_bundle_button.clicked.connect(self.remove_bundle)
        self.button_layout.addWidget(self.add_bundle_button)
        self.button_layout.addWidget(self.remove_bundle_button)
        self.scan_control_layout.addLayout(self.button_layout)

        # 2nd Separator
        self.add_horizontal_separator(self.scan_control_layout)

        # Args layout
        self.args_layout = QGridLayout()
        self.scan_control_layout.addLayout(self.args_layout)

        # Initialize scan selection
        self.populate_scans()
        self.comboBox_scan_selection.currentIndexChanged.connect(self.on_scan_selected)
        self.on_scan_selected()

    def add_horizontal_separator(self, layout) -> None:
        """
        Adds a horizontal separator to the given layout
        Args:
            layout: Layout to add the separator to
        """
        separator = QFrame(self.scan_control_group)
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

    def populate_scans(self):
        """Populates the scan selection combo box with available scans"""
        msg = self.client.producer.get(MessageEndpoints.available_scans())
        self.available_scans = msgpack.loads(msg)
        if self.allowed_scans is None:
            allowed_scans = self.available_scans.keys()
        else:
            allowed_scans = self.allowed_scans
        # TODO check parent class is ScanBase -> filter out the scans not relevant for GUI
        self.comboBox_scan_selection.addItems(allowed_scans)

    def on_scan_selected(self):
        selected_scan_name = self.comboBox_scan_selection.currentText()
        selected_scan_info = self.available_scans.get(selected_scan_name, {})

        # Clear the previous input fields
        self.clear_layout(self.args_layout)
        self.clear_layout(self.kwargs_layout)

        # Generate kwargs input
        self.generate_kwargs_input_fields(selected_scan_info)

        # Args section
        self.arg_input = selected_scan_info.get("arg_input", {})  # Get arg_input from selected scan
        self.add_labels(self.arg_input.keys(), self.args_layout)  # Add labels
        self.add_widgets_row_to_layout(
            self.args_layout, self.arg_input.items()
        )  # Add first row of widgets

    def add_labels(self, labels: list, grid_layout: QGridLayout) -> None:
        """
        Adds labels to the given grid layout as a separate row.
        Args:
            labels (list): List of label names to add.
            grid_layout (QGridLayout): The grid layout to which labels will be added.
        """
        row_index = grid_layout.rowCount()  # Get the next available row
        for column_index, label_name in enumerate(labels):
            label = QLabel(label_name.capitalize(), self.scan_control_group)
            # Add the label to the grid layout at the calculated row and current column
            grid_layout.addWidget(label, row_index, column_index)

    def generate_kwargs_input_fields(self, scan_info: dict) -> None:
        """
        Generates input fields for kwargs
        Args:
            scan_info(dict): Dictionary containing scan information
        """
        # Clear the previous input fields
        self.clear_layout(self.kwargs_layout)

        # Get signature
        signature = scan_info.get("signature", [])

        # Extract kwargs from the converted signature
        kwargs = [param["name"] for param in signature if param["kind"] == "KEYWORD_ONLY"]

        # Add labels
        self.add_labels(kwargs, self.kwargs_layout)

        # Add widgets
        self.add_widgets_row_to_layout(self.kwargs_layout, kwargs, signature)

    def add_widgets_row_to_layout(
        self, grid_layout: QGridLayout, items: list, signature: dict = None
    ) -> None:
        """
        Adds widgets to the given grid layout as a row.
        Args:
            grid_layout (QGridLayout): The grid layout to which widgets will be added.
            items (list): List of items to add, where each item is a tuple (item_name, item_type).
            signature (dict): Dictionary containing signature information for kwargs.
        """
        row_index = grid_layout.rowCount()  # Get the next available row
        for column_index, item in enumerate(items):
            if signature:
                # If a signature is provided, extract type and name from it
                kwarg_info = next((info for info in signature if info["name"] == item), None)
                if kwarg_info:
                    item_type = kwarg_info.get("annotation", "_empty")
                    item_name = item
            else:
                # If no signature is provided, assume the item is a tuple of (name, type)
                item_name, item_type = item

            widget_class = self.WIDGET_HANDLER.get(item_type, None)
            if widget_class is None:
                print(
                    f"Unsupported annotation '{item_type}' for parameter '{item_name}'"
                )  # TODO add type hinting!!!
                continue

            # Instantiate the widget and set some properties if necessary
            widget = widget_class(self.scan_control_group)
            if isinstance(widget, QLineEdit):
                widget.setMinimumWidth(100)  # Set a minimum width for QLineEdit if needed

            # Add the widget to the grid layout at the calculated row and current column
            grid_layout.addWidget(widget, row_index, column_index)

    def clear_layout(self, layout: QLayout) -> None:  # TODO like this probably
        """
        Clears completely the given layout, even if there are  sub-layouts
        Args:
            layout: Layout to clear
        """
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
            else:
                sub_layout = item.layout()
                if sub_layout:
                    self.clear_layout(sub_layout)
                    sub_layout.setParent(None)  # disown layout
                    sub_layout.deleteLater()  # schedule layout for deletion

    def remove_last_row_from_grid_layout(self, grid_layout: QGridLayout) -> None:
        """
        Removes the last row from the given grid layout.
        Args:
            grid_layout(QGridLayout): Layout to remove the last row from
        """
        row_index = grid_layout.rowCount() - 1
        # Find the actual last occupied row
        while row_index > 0:
            items_in_row = [
                grid_layout.itemAtPosition(row_index, col)
                for col in range(grid_layout.columnCount())
            ]
            if not any(items_in_row):  # If the row is empty, decrement the row index
                row_index -= 1
            else:
                break  # Found the last occupied row

        # Proceed if we have more than one occupied row
        if row_index > 2:
            for column_index in range(grid_layout.columnCount()):
                item = grid_layout.itemAtPosition(row_index, column_index)
                if item is not None:
                    widget = item.widget()
                    if widget:
                        grid_layout.removeWidget(widget)
                        widget.deleteLater()

            # Adjust the window size
            self.window().resize(self.window().sizeHint())

    def add_bundle(self) -> None:
        self.add_widgets_row_to_layout(self.args_layout, self.arg_input.items())

    def remove_bundle(self) -> None:
        self.remove_last_row_from_grid_layout(self.args_layout)


if __name__ == "__main__":
    from bec_widgets.bec_dispatcher import bec_dispatcher

    # BECclient global variables
    client = bec_dispatcher.client
    client.start()

    app = QApplication([])
    scan_control = ScanControl(client=client, allowed_scans=["line_scan", "grid_scan"])

    window = scan_control
    window.show()
    app.exec_()
