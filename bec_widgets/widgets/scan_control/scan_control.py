import qdarktheme
from bec_lib.endpoints import MessageEndpoints
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
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils import BECConnector
from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets import StopButton

# TODO GENERAL
# - extract


class ScanArgType:
    DEVICE = "device"
    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    STR = "str"
    DEVICEBASE = "DeviceBase"
    LITERALS = "dict"


class ArgLabel(QLabel):
    def __init__(self, text: str, parent=None, arg_name: str = None, *args, **kwargs):
        super().__init__(text, parent=parent, *args, **kwargs)
        self.arg_name = arg_name


class DeviceLineEdit(BECConnector, QLineEdit):
    def __init__(self, parent=None, client=None, gui_id: str | None = None):
        super().__init__(client=client, gui_id=gui_id)
        QLineEdit.__init__(self, parent=parent)

        self.get_bec_shortcuts()

    def get_device(self):
        return getattr(self.dev, self.text().lower())


class ScanControl(BECConnector, QWidget):
    WIDGET_HANDLER = {
        ScanArgType.DEVICE: DeviceLineEdit,
        ScanArgType.DEVICEBASE: DeviceLineEdit,
        ScanArgType.FLOAT: QDoubleSpinBox,
        ScanArgType.INT: QSpinBox,
        ScanArgType.BOOL: QCheckBox,
        ScanArgType.STR: QLineEdit,
        ScanArgType.LITERALS: QComboBox,  # TODO figure out combobox logic
    }

    def __init__(
        self, parent=None, client=None, gui_id: str | None = None, allowed_scans: list | None = None
    ):
        super().__init__(client=client, gui_id=gui_id)
        QWidget.__init__(self, parent=parent)

        # Client from BEC + shortcuts to device manager and scans
        self.get_bec_shortcuts()

        # Main layout
        self.layout = QVBoxLayout(self)
        self.arg_box = None
        self.kwarg_boxes = []
        self.expert_mode = False  # TODO implement in the future versions

        # Scan list - allowed scans for the GUI
        self.allowed_scans = allowed_scans

        # Create and set main layout
        self._init_UI()

    def _init_UI(self):
        """
        Initializes the UI of the scan control widget. Create the top box for scan selection and populate scans to main combobox.
        """

        # Scan selection group box
        self.scan_selection_group = self.create_scan_selection_group()
        self.scan_selection_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.layout.addWidget(self.scan_selection_group)

        # Connect signals
        self.comboBox_scan_selection.currentIndexChanged.connect(self.on_scan_selected)
        self.button_run_scan.clicked.connect(self.run_scan)
        self.button_add_bundle.clicked.connect(self.add_arg_bundle)
        self.button_remove_bundle.clicked.connect(self.remove_arg_bundle)

        # Initialize scan selection
        self.populate_scans()

    def create_scan_selection_group(self) -> QGroupBox:
        """
        Creates the scan selection group box with combobox to select the scan and start/stop button.

        Returns:
            QGroupBox: Group box containing the scan selection widgets.
        """

        scan_selection_group = QGroupBox("Scan Selection", self)
        self.scan_selection_layout = QGridLayout(scan_selection_group)
        self.comboBox_scan_selection = QComboBox(scan_selection_group)
        # Run button
        self.button_run_scan = QPushButton("Start", scan_selection_group)
        self.button_run_scan.setStyleSheet("background-color:  #559900; color: white")
        # Stop button
        self.button_stop_scan = StopButton(parent=scan_selection_group)
        # Add bundle button
        self.button_add_bundle = QPushButton("Add Bundle", scan_selection_group)
        # Remove bundle button
        self.button_remove_bundle = QPushButton("Remove Bundle", scan_selection_group)

        self.scan_selection_layout.addWidget(self.comboBox_scan_selection, 0, 0, 1, 2)
        self.scan_selection_layout.addWidget(self.button_run_scan, 1, 0)
        self.scan_selection_layout.addWidget(self.button_stop_scan, 1, 1)
        self.scan_selection_layout.addWidget(self.button_add_bundle, 2, 0)
        self.scan_selection_layout.addWidget(self.button_remove_bundle, 2, 1)

        return scan_selection_group

    def populate_scans(self):
        """Populates the scan selection combo box with available scans from BEC session."""
        self.available_scans = self.client.connector.get(
            MessageEndpoints.available_scans()
        ).resource
        if self.allowed_scans is None:
            supported_scans = ["ScanBase", "SyncFlyScanBase", "AsyncFlyScanBase"]
            allowed_scans = [
                scan_name
                for scan_name, scan_info in self.available_scans.items()
                if scan_info["base_class"] in supported_scans
            ]

        else:
            allowed_scans = self.allowed_scans
        self.comboBox_scan_selection.addItems(allowed_scans)

    def on_scan_selected(self):
        """Callback for scan selection combo box"""
        self.reset_layout()
        selected_scan_name = self.comboBox_scan_selection.currentText()
        selected_scan_info = self.available_scans.get(selected_scan_name, {})

        gui_config = selected_scan_info.get("gui_config", {})
        self.arg_group = gui_config.get("arg_group", None)
        self.kwarg_groups = gui_config.get("kwarg_groups", None)

        if len(self.arg_group["arg_inputs"]) > 0:
            self.add_arg_group(self.arg_group)
        if len(self.kwarg_groups) > 0:
            self.add_kwargs_boxes(self.kwarg_groups)

        self.update()
        self.adjustSize()

    def add_input_labels(self, group_inputs: dict, grid_layout: QGridLayout, row: int) -> None:
        """
        Adds the given arg_group from arg_bundle to the scan control layout. The input labels are always added to the first row.

        Args:
            group(dict): Dictionary containing the arg_group information.
            grid_layout(QGridLayout): The grid layout to which the arg_group will be added.
        """
        for column_index, item in enumerate(group_inputs):
            arg_name = item.get("name", None)
            display_name = item.get("display_name", arg_name)
            tooltip = item.get("tooltip", None)
            label = ArgLabel(text=display_name, arg_name=arg_name)
            if tooltip is not None:
                label.setToolTip(item["tooltip"])
            grid_layout.addWidget(label, row, column_index)

    def add_input_widgets(self, group_inputs: dict, grid_layout: QGridLayout, row) -> None:
        for column_index, item in enumerate(group_inputs):
            widget = self.WIDGET_HANDLER.get(item["type"], None)
            if widget is None:
                print(f"Unsupported annotation '{item['type']}' for parameter '{item['name']}'")
                continue
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setRange(-9999, 9999)
            # if item["default"] != "_empty":  # TODO fix for comboboxes and spinboxes
            #     WidgetIO.set_value(widget, item["default"])
            # widget.setValue(item["default"])
            grid_layout.addWidget(widget(), row, column_index)

    def add_input_box(self, group: dict, rows: int = 1):
        """
        Adds the given gui_group to the scan control layout.

        Args:
            group(dict): Dictionary containing the gui_group information.
            rows(int): Number of input rows to add to the layout.
        """
        input_box = QGroupBox(group["name"])
        group_layout = QGridLayout(input_box)
        self.add_input_labels(group["inputs"], group_layout, 0)
        for i in range(rows):
            self.add_input_widgets(group["inputs"], group_layout, i + 1)
        input_box.setLayout(group_layout)
        self.layout.addWidget(input_box)
        input_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        return input_box

    def add_kwargs_boxes(self, groups: list):
        """
        Adds the given gui_groups to the scan control layout.

        Args:
            groups(list): List of dictionaries containing the gui_group information.
        """
        for group in groups:
            box = self.add_input_box(group)
            self.layout.addWidget(box)
            self.kwarg_boxes.append(box)

    def add_arg_group(self, group: dict):
        """
        Adds the given gui_groups to the scan control layout.

        Args:
        """
        self.arg_box = self.add_input_box(group, rows=group["min"])
        self.real_arg_box_row_count = group["min"]
        self.layout.addWidget(self.arg_box)

    def add_arg_bundle(self):
        if self.arg_box is not None:
            current_row_count = self.arg_box.layout().rowCount()
            if self.arg_group["max"] is not None and current_row_count >= self.arg_group["max"]:
                return
            self.add_input_widgets(
                self.arg_group["inputs"], self.arg_box.layout(), self.arg_box.layout().rowCount()
            )

            self.real_arg_box_row_count += 1

            print(f"row count REAL: {self.real_arg_box_row_count}")
            print(f"row count QT: {self.arg_box.layout().rowCount()}")

    def remove_arg_bundle(self):
        if self.arg_box is not None:
            current_row_count = self.real_arg_box_row_count  # self.arg_box.layout().rowCount()
            layout = self.arg_box.layout()
            if current_row_count > self.arg_group["min"]:
                for i in range(layout.columnCount()):
                    widget = layout.itemAtPosition(current_row_count, i).widget()
                    layout.removeWidget(widget)
                    widget.deleteLater()
                self.real_arg_box_row_count -= 1
                print(f"row count REAL: {self.real_arg_box_row_count}")
                print(f"row count QT: {self.arg_box.layout().rowCount()}")
                # self.arg_box.layout().removeRow(current_row_count - 1)

    def reset_layout(self):
        """Clears the scan control layout from GuiGroups and ArgGroups boxes."""
        if self.arg_box is not None:
            self.layout.removeWidget(self.arg_box)
            self.arg_box = None
        if self.kwarg_boxes != []:
            self.remove_kwarg_boxes()

    def remove_kwarg_boxes(self):
        for box in self.kwarg_boxes:
            self.layout.removeWidget(box)
            box.deleteLater()
        self.kwarg_boxes = []

    def add_labels_to_table(
        self, labels: list, table: QTableWidget
    ) -> None:  # TODO could be moved to BECTable -> not needed
        """
        Adds labels to the given table widget as a header row.

        Args:
            labels(list): List of label names to add.
            table(QTableWidget): The table widget to which labels will be added.
        """
        table.setColumnCount(len(labels))
        table.setHorizontalHeaderLabels(labels)

    def generate_args_input_fields(
        self, scan_info: dict
    ) -> None:  # TODO decide how to deal with arg bundles
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

    def generate_kwargs_input_fields(
        self, scan_info: dict, inputs: dict = {}, hidden: list = []
    ) -> None:  # TODO can be removed
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
        parameters = [
            param
            for param in signature
            if param["annotation"] != "_empty" and param["name"] not in hidden
        ]

        # Add labels
        self.add_labels_to_layout(parameters, self.kwargs_layout)

        # Add widgets
        widgets = self.generate_widgets_from_signature(parameters)

        self.add_widgets_row_to_layout(self.kwargs_layout, widgets)

    def create_widget_group(self, title: str, widgets: list) -> QGroupBox:  # TODO to be removed
        """
        Creates a group box containing the given widgets.

        Args:
            title(str): Title of the group box.
            widgets(list): List of widgets to add to the group box.

        Returns:
            QGroupBox: Group box containing the given widgets.
        """
        group_box = QGroupBox(title)
        group_layout = QVBoxLayout(group_box)
        for widget in widgets:
            group_layout.addWidget(widget)
        group_box.setLayout(group_layout)
        return group_box

    def generate_widgets_from_signature(self, parameters: list) -> list:  # TODO to be removed
        """
        Generates widgets from the given list of items.

        Args:
            parameters(list): List of items to create widgets for.

        Returns:
            list: List of widgets created from the given items.
        """
        widgets = []  # Initialize an empty list to hold the widgets

        item_default = None
        item_type = "_empty"
        item_name = "name"
        for item in parameters:
            if isinstance(item, dict):
                item_type = item.get("annotation", "_empty")
                item_name = item
                item_default = item.get("default", 0)
                item_default = item_default if item_default is not None else 0
            elif isinstance(item, tuple):
                item_name, item_type = item
            else:
                raise ValueError(f"Unsupported item type '{type(item)}' for parameter '{item}'")

            widget_class = self.WIDGET_HANDLER.get(item_type, None)
            if widget_class is None:
                print(f"Unsupported annotation '{item_type}' for parameter '{item_name}'")
                continue

            # Instantiate the widget and set some properties if necessary
            widget = widget_class()

            # set high default range for spin boxes #TODO can be linked to motor/device limits from BEC
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setRange(-9999, 9999)
            # if item_default is not None:
            #     WidgetIO.set_value(widget, item_default)

            # Add the widget to the list
            widgets.append(widget)

        return widgets

    def set_args_table_limits(
        self, table: QTableWidget, scan_info: dict
    ) -> None:  # TODO can be removed
        # Get bundle info
        arg_bundle_size = scan_info.get("arg_bundle_size", {})
        self.arg_size_min = arg_bundle_size.get("min", 1)
        self.arg_size_max = arg_bundle_size.get("max", None)

        # Clear the previous input fields
        table.setRowCount(0)  # Wipe table

    def add_widgets_row_to_layout(
        self, grid_layout: QGridLayout, widgets: list, row_index: int = None
    ) -> None:  # TODO to be removed
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
    ) -> None:  # TODO to be removed
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

    def remove_last_row_from_table(self, table_widget: QTableWidget) -> None:  # TODO to be removed
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

    def create_new_grid_layout(self):  # TODO to be removed
        new_layout = QGridLayout()
        # TODO maybe setup other layouts properties here?
        return new_layout

    def clear_and_delete_layout(self, layout: QLayout):  # TODO can be removed
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

    def add_bundle(self) -> None:  # TODO can be removed
        """Adds a new bundle to the scan control layout"""
        # Get widgets used for particular scan and save them to be able to use for adding bundles
        args_widgets = self.generate_widgets_from_signature(
            self.arg_input.items()
        )  # TODO decide if make sense to put widget list into method parameters

        # Add first widgets row to the table
        self.add_widgets_row_to_table(self.args_table, args_widgets)

    def remove_bundle(self) -> None:  # TODO can be removed
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
                if not widget:
                    continue
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

    def extract_kwargs(self, box: QGroupBox) -> dict:
        """
        Extracts the parameters from the given group box.

        Args:
            box(QGroupBox): Group box from which to extract the parameters.

        Returns:
            dict: Dictionary containing the extracted parameters.
        """
        parameters = {}
        keys = [label.arg_name for label in box.findChildren(ArgLabel)]
        layout = box.layout()
        for i in range(layout.columnCount()):
            key = keys[i]
            widget = layout.itemAtPosition(1, i).widget()
            if isinstance(widget, DeviceLineEdit):
                value = widget.get_device()
            else:
                value = WidgetIO.get_value(widget)
            parameters[key] = value
        return parameters

    def extract_args(self, box):
        args = []
        layout = box.layout()
        for i in range(layout.columnCount()):
            widget = layout.itemAtPosition(1, i).widget()
            if isinstance(widget, DeviceLineEdit):
                value = widget.get_device()
            else:
                value = WidgetIO.get_value(widget)
            args.append(value)
        return args

    def run_scan(self):
        args = []
        kwargs = {}
        if self.arg_box is not None:
            args = self.extract_args(self.arg_box)
        for box in self.kwarg_boxes:
            box_kwargs = self.extract_kwargs(box)
            kwargs.update(box_kwargs)
        print(kwargs)
        scan_function = getattr(self.scans, self.comboBox_scan_selection.currentText())
        print(f"called with args: {args} and kwargs: {kwargs}")
        if callable(scan_function):
            scan_function(*args, **kwargs)

    def close(self):
        super().close()


# Application example
if __name__ == "__main__":  # pragma: no cover
    app = QApplication([])
    scan_control = ScanControl(allowed_scans=["fermat_scan", "round_scan", "line_scan"])

    qdarktheme.setup_theme("auto")
    window = scan_control
    window.show()
    app.exec()
