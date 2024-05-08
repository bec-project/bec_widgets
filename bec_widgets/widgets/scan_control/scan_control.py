import msgpack
from bec_lib import MessageEndpoints
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_dispatcher import BECDispatcher
from bec_widgets.utils.widget_io import WidgetIO


class ScanArgType:
    DEVICE = "device"
    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    STR = "str"


class ScanControl(QWidget):
    WIDGET_HANDLER = {
        ScanArgType.DEVICE: QLineEdit,
        ScanArgType.FLOAT: QDoubleSpinBox,
        ScanArgType.INT: QSpinBox,
        ScanArgType.BOOL: QCheckBox,
        ScanArgType.STR: QLineEdit,
    }

    def __init__(self, parent=None, client=None, allowed_scans=None):
        super().__init__(parent)

        # Client from BEC + shortcuts to device manager and scans
        self.client = BECDispatcher().client if client is None else client
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
        self.button_run_scan = QPushButton("Run Scan", self.scan_selection_group)
        self.scan_selection_layout.addWidget(self.comboBox_scan_selection)
        self.scan_selection_layout.addWidget(self.button_run_scan)
        self.verticalLayout.addWidget(self.scan_selection_group)

        # Scan control group box
        self.scan_control_group = QGroupBox("Scan Control", self)
        self.scan_control_layout = QVBoxLayout(self.scan_control_group)
        self.verticalLayout.addWidget(self.scan_control_group)

        # Kwargs layout - just placeholder
        self.kwargs_layout = QGridLayout()
        self.scan_control_layout.addLayout(self.kwargs_layout)

        # 1st Separator
        self.add_horizontal_separator(self.scan_control_layout)

        # Buttons
        self.button_layout = QHBoxLayout()
        self.pushButton_add_bundle = QPushButton("Add Bundle", self.scan_control_group)
        self.pushButton_add_bundle.clicked.connect(self.add_bundle)
        self.pushButton_remove_bundle = QPushButton("Remove Bundle", self.scan_control_group)
        self.pushButton_remove_bundle.clicked.connect(self.remove_bundle)
        self.button_layout.addWidget(self.pushButton_add_bundle)
        self.button_layout.addWidget(self.pushButton_remove_bundle)
        self.scan_control_layout.addLayout(self.button_layout)

        # 2nd Separator
        self.add_horizontal_separator(self.scan_control_layout)

        # Initialize the QTableWidget for args
        self.args_table = QTableWidget()
        self.args_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

        self.scan_control_layout.addWidget(self.args_table)

        # Connect signals
        self.comboBox_scan_selection.currentIndexChanged.connect(self.on_scan_selected)
        self.button_run_scan.clicked.connect(self.run_scan)

        # Initialize scan selection
        self.populate_scans()

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
        self.available_scans = self.client.producer.get(MessageEndpoints.available_scans()).resource
        if self.allowed_scans is None:
            allowed_scans = self.available_scans.keys()
        else:
            allowed_scans = self.allowed_scans
        # TODO check parent class is ScanBase -> filter out the scans not relevant for GUI
        self.comboBox_scan_selection.addItems(allowed_scans)

    def on_scan_selected(self):
        """Callback for scan selection combo box"""
        selected_scan_name = self.comboBox_scan_selection.currentText()
        selected_scan_info = self.available_scans.get(selected_scan_name, {})

        print(selected_scan_info)  # TODO remove when widget will be more mature
        # Generate kwargs input
        self.generate_kwargs_input_fields(selected_scan_info)

        # Args section
        self.generate_args_input_fields(selected_scan_info)

    def add_labels_to_layout(self, labels: list, grid_layout: QGridLayout) -> None:
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

    def add_labels_to_table(
        self, labels: list, table: QTableWidget
    ) -> None:  # TODO could be moved to BECTable
        """
        Adds labels to the given table widget as a header row.

        Args:
            labels(list): List of label names to add.
            table(QTableWidget): The table widget to which labels will be added.
        """
        table.setColumnCount(len(labels))
        table.setHorizontalHeaderLabels(labels)

    def generate_args_input_fields(self, scan_info: dict) -> None:
        """
        Generates input fields for args.

        Args:
            scan_info(dict): Scan signature dictionary from BEC.
        """

        # Setup args table limits
        self.set_args_table_limits(self.args_table, scan_info)

        # Get arg_input from selected scan
        self.arg_input = scan_info.get("arg_input", {})

        # Generate labels for table
        self.add_labels_to_table(list(self.arg_input.keys()), self.args_table)

        # add minimum number of args rows
        if self.arg_size_min is not None:
            for i in range(self.arg_size_min):
                self.add_bundle()

    def generate_kwargs_input_fields(self, scan_info: dict) -> None:
        """
        Generates input fields for kwargs

        Args:
            scan_info(dict): Scan signature dictionary from BEC.
        """
        # Create a new kwarg layout to replace the old one - this is necessary because otherwise row count is not reseted
        self.clear_and_delete_layout(self.kwargs_layout)
        self.kwargs_layout = self.create_new_grid_layout()  # Create new grid layout
        self.scan_control_layout.insertLayout(0, self.kwargs_layout)

        # Get signature
        signature = scan_info.get("signature", [])

        # Extract kwargs from the converted signature
        kwargs = [param["name"] for param in signature if param["kind"] == "KEYWORD_ONLY"]

        # Add labels
        self.add_labels_to_layout(kwargs, self.kwargs_layout)

        # Add widgets
        widgets = self.generate_widgets_from_signature(kwargs, signature)

        self.add_widgets_row_to_layout(self.kwargs_layout, widgets)

    def generate_widgets_from_signature(self, items: list, signature: dict = None) -> list:
        """
        Generates widgets from the given list of items.

        Args:
            items(list): List of items to create widgets for.
            signature(dict, optional): Scan signature dictionary from BEC.

        Returns:
            list: List of widgets created from the given items.
        """
        widgets = []  # Initialize an empty list to hold the widgets

        for item in items:
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
                print(f"Unsupported annotation '{item_type}' for parameter '{item_name}'")
                continue

            # Instantiate the widget and set some properties if necessary
            widget = widget_class()

            # set high default range for spin boxes #TODO can be linked to motor/device limits from BEC
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setRange(-9999, 9999)
                widget.setValue(0)
            # Add the widget to the list
            widgets.append(widget)

        return widgets

    def set_args_table_limits(self, table: QTableWidget, scan_info: dict) -> None:
        # Get bundle info
        arg_bundle_size = scan_info.get("arg_bundle_size", {})
        self.arg_size_min = arg_bundle_size.get("min", 1)
        self.arg_size_max = arg_bundle_size.get("max", None)

        # Clear the previous input fields
        table.setRowCount(0)  # Wipe table

    def add_widgets_row_to_layout(
        self, grid_layout: QGridLayout, widgets: list, row_index: int = None
    ) -> None:
        """
        Adds a row of widgets to the given grid layout.

        Args:
            grid_layout (QGridLayout): The grid layout to which widgets will be added.
            items (list): List of parameter names to create widgets for.
            row_index (int): The row index where the widgets should be added.
        """
        # If row_index is not specified, add to the next available row
        if row_index is None:
            row_index = grid_layout.rowCount()

        for column_index, widget in enumerate(widgets):
            # Add the widget to the grid layout at the specified row and column
            grid_layout.addWidget(widget, row_index, column_index)

    def add_widgets_row_to_table(
        self, table_widget: QTableWidget, widgets: list, row_index: int = None
    ) -> None:
        """
        Adds a row of widgets to the given QTableWidget.

        Args:
            table_widget (QTableWidget): The table widget to which widgets will be added.
            widgets (list): List of widgets to add to the table.
            row_index (int): The row index where the widgets should be added. If None, add to the end.
        """
        # If row_index is not specified, add to the end of the table
        if row_index is None or row_index > table_widget.rowCount():
            row_index = table_widget.rowCount()
            if self.arg_size_max is not None:  # ensure the max args size is not exceeded
                if row_index >= self.arg_size_max:
                    return
            table_widget.insertRow(row_index)

        for column_index, widget in enumerate(widgets):
            # If the widget is a subclass of QWidget, use setCellWidget
            if issubclass(type(widget), QWidget):
                table_widget.setCellWidget(row_index, column_index, widget)
            else:
                # Otherwise, assume it's a string or some other value that should be displayed as text
                item = QTableWidgetItem(str(widget))
                table_widget.setItem(row_index, column_index, item)

        # Optionally, adjust the row height based on the content #TODO decide if needed
        table_widget.setRowHeight(
            row_index,
            max(widget.sizeHint().height() for widget in widgets if isinstance(widget, QWidget)),
        )

    def remove_last_row_from_table(self, table_widget: QTableWidget) -> None:
        """
        Removes the last row from the given QTableWidget until only one row is left.

        Args:
            table_widget (QTableWidget): The table widget from which the last row will be removed.
        """
        row_count = table_widget.rowCount()
        if (
            row_count > self.arg_size_min
        ):  # Check to ensure there is a minimum number of rows remaining
            table_widget.removeRow(row_count - 1)

    def create_new_grid_layout(self):
        new_layout = QGridLayout()
        # TODO maybe setup other layouts properties here?
        return new_layout

    def clear_and_delete_layout(self, layout: QLayout):
        """
        Clears and deletes the given layout and all its child widgets.

        Args:
            layout(QLayout): Layout to clear and delete
        """
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
                else:
                    sub_layout = item.layout()
                    if sub_layout:
                        self.clear_and_delete_layout(sub_layout)
            layout.deleteLater()

    def add_bundle(self) -> None:
        """Adds a new bundle to the scan control layout"""
        # Get widgets used for particular scan and save them to be able to use for adding bundles
        args_widgets = self.generate_widgets_from_signature(
            self.arg_input.items()
        )  # TODO decide if make sense to put widget list into method parameters

        # Add first widgets row to the table
        self.add_widgets_row_to_table(self.args_table, args_widgets)

    def remove_bundle(self) -> None:
        """Removes the last bundle from the scan control layout"""
        self.remove_last_row_from_table(self.args_table)

    def extract_kwargs_from_grid_row(self, grid_layout: QGridLayout, row: int) -> dict:
        kwargs = {}
        for column in range(grid_layout.columnCount()):
            label_item = grid_layout.itemAtPosition(row, column)
            if label_item is not None:
                label_widget = label_item.widget()
                if isinstance(label_widget, QLabel):
                    key = label_widget.text()

                    # The corresponding value widget is in the next row
                    value_item = grid_layout.itemAtPosition(row + 1, column)
                    if value_item is not None:
                        value_widget = value_item.widget()
                        # Use WidgetIO.get_value to extract the value
                        value = WidgetIO.get_value(value_widget)
                        kwargs[key] = value
        return kwargs

    def extract_args_from_table(self, table: QTableWidget) -> list:
        """
        Extracts the arguments from the given table widget.

        Args:
            table(QTableWidget): Table widget from which to extract the arguments
        """
        args = []
        for row in range(table.rowCount()):
            row_args = []
            for column in range(table.columnCount()):
                widget = table.cellWidget(row, column)
                if widget:
                    if isinstance(widget, QLineEdit):  # special case for QLineEdit for Devices
                        value = widget.text().lower()
                        if value in self.dev:
                            value = getattr(self.dev, value)
                        else:
                            raise ValueError(f"The device '{value}' is not recognized.")
                    else:
                        value = WidgetIO.get_value(widget)
                    row_args.append(value)
            args.extend(row_args)
        return args

    def run_scan(self):
        # Extract kwargs for the scan
        kwargs = {
            k.lower(): v
            for k, v in self.extract_kwargs_from_grid_row(self.kwargs_layout, 1).items()
        }

        # Extract args from the table
        args = self.extract_args_from_table(self.args_table)

        # Convert args to lowercase if they are strings
        args = [arg.lower() if isinstance(arg, str) else arg for arg in args]

        # Execute the scan
        scan_function = getattr(self.scans, self.comboBox_scan_selection.currentText())
        if callable(scan_function):
            scan_function(*args, **kwargs)


# Application example
if __name__ == "__main__":  # pragma: no cover
    # BECclient global variables
    client = BECDispatcher().client
    client.start()

    app = QApplication([])
    scan_control = ScanControl(
        client=client,
    )  # allowed_scans=["line_scan", "grid_scan"])

    window = scan_control
    window.show()
    app.exec()
