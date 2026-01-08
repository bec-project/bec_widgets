"""
Module for a TableWidget for the device manager view. Row data is encapsulated
in DeviceTableRow entries.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Iterable, Tuple

from bec_lib.atlas_models import Device as DeviceModel
from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy import QtCore, QtGui, QtWidgets
from thefuzz import fuzz

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.device_manager.components.device_table.device_table_row import (
    DeviceTableRow,
)
from bec_widgets.widgets.control.device_manager.components.ophyd_validation import (
    ConfigStatus,
    ConnectionStatus,
    get_validation_icons,
)

logger = bec_logger.logger

_DeviceCfgIter = Iterable[dict[str, Any]]
# DeviceValidationResult: device_config, config_status, connection_status, error_message
_ValidationResultIter = Iterable[Tuple[dict[str, Any], ConfigStatus, ConnectionStatus, str]]

FUZZY_SEARCH_THRESHOLD = 80


def is_match(
    text: str, row_data: dict[str, Any], relevant_keys: list[str], enable_fuzzy: bool
) -> bool:
    """
    Check if the text matches any of the relevant keys in the row data.

    Args:
        text (str): The text to search for.
        row_data (dict[str, Any]): The row data to search in.
        relevant_keys (list[str]): The keys to consider for searching.
        enable_fuzzy (bool): Whether to use fuzzy matching.
    Returns:
        bool: True if a match is found, False otherwise.
    """
    for key in relevant_keys:
        data = str(row_data.get(key, "") or "")
        if enable_fuzzy:
            match_ratio = fuzz.partial_ratio(text.lower(), data.lower())
            if match_ratio >= FUZZY_SEARCH_THRESHOLD:
                return True
        else:
            if text.lower() in data.lower():
                return True
    return False


class TableSortOnHold:
    """Context manager for putting table sorting on hold. Works with nested calls."""

    def __init__(self, table: QtWidgets.QTableWidget) -> None:
        self.table = table
        self._call_depth = 0
        self._registered_methods = []

    def register_on_hold_method(
        self, method: Callable[[QtWidgets.QTableWidget, bool], None]
    ) -> None:
        """
        Register a method to be called when sorting is put on hold.

        Args:
            method (Callable[[QtWidgets.QTableWidget, bool], None]): The method to register.
                            The method should accept the QTableWidget and a bool indicating
                            whether sorting is being enabled (True) or disabled (False).
        """
        self._registered_methods.append(method)

    def __enter__(self):
        """Enter the context manager"""
        self._call_depth += 1  # Needed for nested calls
        self.table.setSortingEnabled(False)
        for method in self._registered_methods:
            method(self.table, False)

    def __exit__(self, *exc):
        """Exit the context manager"""
        self._call_depth -= 1  # Remove nested calls
        if self._call_depth == 0:  # Only re-enable sorting on outermost exit
            self.table.setSortingEnabled(True)
            for method in self._registered_methods:
                method(self.table, True)


class CenterIconDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate to center icons in table cells."""

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ):
        # First draw the default cell (without icon)
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.icon = QtGui.QIcon()  # Create empty icon to avoid default to be drawn at given position
        option.widget.style().drawControl(
            QtWidgets.QStyle.ControlElement.CE_ItemViewItem, opt, painter, option.widget
        )
        # Check if there is an icon to draw
        icon = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        if not icon:
            return
        # Draw the icon centered in the cell
        icon_size = option.decorationSize
        if icon_size.isValid():
            size = icon_size
        else:
            size = icon.actualSize(option.rect.size())

        x = option.rect.x() + (option.rect.width() - size.width()) // 2
        y = option.rect.y() + (option.rect.height() - size.height()) // 2

        icon.paint(painter, QtCore.QRect(QtCore.QPoint(x, y), size))


class CheckBoxDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate to handle checkbox interactions in the table."""

    # Signal to indicate a checkbox was clicked
    checkbox_clicked = QtCore.Signal(int, int, bool)  # row, column, checked

    def editorEvent(
        self,
        event: QtCore.QEvent,
        model: QtCore.QAbstractItemModel,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ):
        if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
            if model and (model.flags(index) & QtCore.Qt.ItemFlag.ItemIsUserCheckable):
                old_state = QtCore.Qt.CheckState(
                    model.data(index, QtCore.Qt.ItemDataRole.CheckStateRole)
                )
                new_state = (
                    QtCore.Qt.CheckState.Unchecked
                    if old_state == QtCore.Qt.CheckState.Checked
                    else QtCore.Qt.CheckState.Checked
                )
                model.setData(index, new_state, QtCore.Qt.ItemDataRole.CheckStateRole)
                model.setData(
                    index,
                    new_state == QtCore.Qt.CheckState.Checked,
                    QtCore.Qt.ItemDataRole.UserRole,
                )
                self.checkbox_clicked.emit(
                    index.row(), index.column(), new_state == QtCore.Qt.CheckState.Checked
                )
            return True
        return super().editorEvent(event, model, option, index)


class SortTableItem(QtWidgets.QTableWidgetItem):
    """Custom TableWidgetItem with hidden __column_data attribute for sorting."""

    def __lt__(self, other: QtWidgets.QTableWidgetItem) -> bool:
        """Override less-than operator for sorting."""
        if not isinstance(other, QtWidgets.QTableWidgetItem):
            return NotImplemented
        self_data = self.data(QtCore.Qt.ItemDataRole.UserRole)
        other_data = other.data(QtCore.Qt.ItemDataRole.UserRole)
        if self_data is not None and other_data is not None:
            return self_data < other_data
        return super().__lt__(other)

    def __gt__(self, other: QtWidgets.QTableWidgetItem) -> bool:
        """Override less-than operator for sorting."""
        if not isinstance(other, QtWidgets.QTableWidgetItem):
            return NotImplemented
        self_data = self.data(QtCore.Qt.ItemDataRole.UserRole)
        other_data = other.data(QtCore.Qt.ItemDataRole.UserRole)
        if self_data is not None and other_data is not None:
            return self_data > other_data
        return super().__gt__(other)


class DeviceTable(BECWidget, QtWidgets.QWidget):
    """Custom table to display device configurations."""

    RPC = False  # TODO discuss if this should be available for RPC

    # Signal emitted if devices are added (updated) or removed
    #   - device_configs: List of device configurations.
    #   - added: True if devices were added/updated, False if removed.
    #   - skip validation: True if validation should be skipped for added/updated devices.
    device_configs_changed = QtCore.Signal(list, bool, bool)
    # Signal emitted when device selection changes, emits list of selected device configs
    selected_devices = QtCore.Signal(list)
    # Signal emitted when a device row is double-clicked, emits the device config
    device_row_dbl_clicked = QtCore.Signal(dict)
    # Signal emitted when the device config is in sync with Redis
    device_config_in_sync_with_redis = QtCore.Signal(bool)

    _auto_size_request = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent=parent)
        self.headers_key_map: dict[str, str] = {
            "Valid": "valid",
            "Connect": "connect",
            "Name": "name",
            "Device Class": "deviceClass",
            "Readout Priority": "readoutPriority",
            "On Failure": "onFailure",
            "Device Tags": "deviceTags",
            "Description": "description",
            "Enabled": "enabled",
            "Read Only": "readOnly",
            "Software Trigger": "softwareTrigger",
        }

        # General attributes
        self._icon_size = (18, 18)
        self._colors = get_accent_colors()
        self._icons = get_validation_icons(self._colors, self._icon_size)
        self._check_box_icons = {
            "checked": material_icon(
                "check_box", size=(24, 24), color=self._colors.default, convert_to_pixmap=False
            ),
            "unchecked": material_icon(
                "check_box_outline_blank",
                size=(24, 24),
                color=self._colors.default,
                convert_to_pixmap=False,
            ),
        }
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self.setLayout(self._layout)

        # Table related attributes
        self.row_data: dict[str, DeviceTableRow] = {}
        self.table = QtWidgets.QTableWidget(self)
        self.table_sort_on_hold = TableSortOnHold(self.table)
        self._setup_table()
        self.table_sort_on_hold.register_on_hold_method(self._resize_table_policy)
        self.table_sort_on_hold.register_on_hold_method(self._set_table_signals_on_hold)

        # Search related attributes
        self._searchable_keys: list[str] = ["name", "deviceClass", "deviceTags", "description"]
        self._hidden_rows: set[int] = set()
        self._enable_fuzzy_search: bool = True
        self._setup_search()

        # Add components to layout
        self._layout.addLayout(self.search_controls)
        self._layout.addWidget(self.table)

        # Connect slots
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        # Install event filter
        self.table.installEventFilter(self)

    def cleanup(self):
        """Cleanup resources."""
        self.row_data.clear()  # Drop references to row data..
        # self._autosize_timer.stop()
        super().cleanup()

    # -------------------------------------------------------------------------
    # Custom hooks for table events
    # -------------------------------------------------------------------------

    def _on_selection_changed(
        self, selected: QtCore.QItemSelection, deselected: QtCore.QItemSelection
    ):
        """Handle selection changes in the table."""
        rows = set()
        for index in selected.indexes():
            row = index.row()
            rows.add(row)
        selected_configs = []
        for row in rows:
            device_name = self._get_cell_data(row, 2)  # Name column
            if device_name:
                row_data = self.row_data.get(device_name)
                if row_data:
                    cfg = deepcopy(row_data.data)
                    cfg.pop("name")
                    selected_configs.append({device_name: cfg})
        self.selected_devices.emit(selected_configs)

    def _on_cell_double_clicked(self, row: int, column: int):
        """Handle double-click events on table cells."""
        device_name = self._get_cell_data(row, 2)  # Name column
        if device_name:
            row_data = self.row_data.get(device_name)
            if row_data:
                self.device_row_dbl_clicked.emit(row_data.data)

    def eventFilter(self, source: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Customize event filtering for table interactions."""
        if source is self.table:
            if event.type() == QtCore.QEvent.Type.KeyPress:
                if event.key() in (QtCore.Qt.Key.Key_Backspace, QtCore.Qt.Key.Key_Delete):
                    configs = self.get_selected_device_configs()
                    if configs:
                        if self._remove_configs_dialog([cfg["name"] for cfg in configs]):
                            self.remove_device_configs(configs)
                        return True  # Event handled
                if event.key() == QtCore.Qt.Key.Key_Escape:
                    self.table.clearSelection()
                    return True  # handled
        return super().eventFilter(source, event)

    def _on_table_checkbox_clicked(self, row: int, column: int, checked: bool):
        """Handle checkbox clicks in the table."""
        name_index = list(self.headers_key_map.values()).index("name")
        device_name = self._get_cell_data(row, name_index)
        row_data = self.row_data.get(device_name)
        if not row_data:
            return
        row_data.data[self.headers_key_map[list(self.headers_key_map.keys())[column]]] = checked
        self._on_device_row_data_changed(row_data.data)

    def _on_device_row_data_changed(self, data: dict):
        """Handle data change events from device rows."""
        device_name = data.get("name", None)
        cfg = deepcopy(data)
        cfg.pop("name")
        self.selected_devices.emit([{device_name: cfg}])
        self.device_config_in_sync_with_redis.emit(self._is_config_in_sync_with_redis())

    def _apply_row_filter(self, text_input: str):
        """Apply a filter to the table rows based on the filter text."""
        for row in range(self.table.rowCount()):
            device_name = self._get_cell_data(row, 2)  # Name column
            if not device_name:
                continue
            row_data = self.row_data.get(device_name)
            if not row_data:
                continue
            if is_match(
                text_input, row_data.data, self._searchable_keys, self._enable_fuzzy_search
            ):
                self.table.setRowHidden(row, False)
                self._hidden_rows.discard(row)
            else:
                self.table.setRowHidden(row, True)
                self._hidden_rows.add(row)

    def _state_change_fuzzy_search(self, enabled: int):
        """Handle state changes for the fuzzy search toggle."""
        self._enable_fuzzy_search = not bool(enabled)
        # Re-apply filter with updated fuzzy search setting
        current_text = self.search_input.text()
        self._apply_row_filter(current_text)

    # -------------------------------------------------------------------------
    # Custom Dialog
    # -------------------------------------------------------------------------

    def _remove_configs_dialog(self, device_names: list[str]) -> bool:
        """
        Prompt the user to confirm removal of rows and remove them from the model if accepted.

        Args:
            device_names (list[str]): List of device names to be removed.

        Returns:
            bool: True if the user confirmed removal, False otherwise.
        """
        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msg.setWindowTitle("Confirm device removal")
        msg.setText(
            f"Remove device '{device_names[0]}'?"
            if len(device_names) == 1
            else f"Remove {len(device_names)} devices?"
        )
        separator = "\n" if len(device_names) < 12 else ", "
        msg.setInformativeText("Selected devices: \n" + separator.join(device_names))
        msg.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Ok | QtWidgets.QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Cancel)

        res = msg.exec_()
        if res == QtWidgets.QMessageBox.StandardButton.Ok:
            return True
        return False

    # -------------------------------------------------------------------------
    # Setup table
    # -------------------------------------------------------------------------
    def _setup_table(self):
        """Initializes the table configuration and headers."""
        # Temporary instance to get headers dynamically
        headers = list(self.headers_key_map.keys())
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        # Smooth scrolling
        self.table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        # Hide vertical header
        self.table.verticalHeader().setVisible(False)

        # Column resize policies
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(8, QtWidgets.QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(9, QtWidgets.QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(10, QtWidgets.QHeaderView.ResizeMode.Fixed)

        for sizes, col in [
            (0, 85),
            (1, 85),
            (2, 200),
            (3, 200),
            (6, 200),
            (7, 200),
            (8, 90),
            (9, 90),
            (10, 120),
        ]:
            self.table.setColumnWidth(sizes, col)

        # Ensure column widths stay fixed
        header.setStretchLastSection(False)

        # Sorting
        self.table.setSortingEnabled(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(2, QtCore.Qt.SortOrder.AscendingOrder)  # Default sort by name

        # Selection behavior
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        # Connect to selection model to get selection changes
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.horizontalHeader().setHighlightSections(False)

        # Set delegate for checkboxes
        checkbox_delegate = CheckBoxDelegate(self.table)
        icon_delegate = CenterIconDelegate(self.table)
        self.table.setItemDelegateForColumn(0, icon_delegate)  # Config status
        self.table.setItemDelegateForColumn(1, icon_delegate)  # Connection status
        self.table.setWordWrap(True)
        for col in (8, 9, 10):  # enabled, readOnly, softwareTrigger
            self.table.setItemDelegateForColumn(col, checkbox_delegate)
        checkbox_delegate.checkbox_clicked.connect(self._on_table_checkbox_clicked)

    def _set_table_signals_on_hold(self, table: QtWidgets.QTableWidget, enable: bool):
        """Enable or disable table signals."""
        if enable:
            table.blockSignals(False)
        else:
            table.blockSignals(True)

    def _resize_table_policy(self, table: QtWidgets.QTableWidget, enable: bool):
        """Enable or disable column resizing."""
        if enable:
            table.resizeColumnToContents(2)  # Name
            table.resizeColumnToContents(3)  # Device Class
            # table.resizeRowsToContents()

    def _setup_search(self):
        """Create components related to the search functionality"""

        # Create search bar
        self.search_layout = QtWidgets.QHBoxLayout()
        self.search_label = QtWidgets.QLabel("Search:")
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Filter devices (approximate matching)...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._apply_row_filter)
        self.search_layout.addWidget(self.search_label)
        self.search_layout.addWidget(self.search_input)

        # Add exact match toggle
        self.fuzzy_layout = QtWidgets.QHBoxLayout()
        self.fuzzy_label = QtWidgets.QLabel("Exact Match:")
        self.fuzzy_is_disabled = QtWidgets.QCheckBox()

        self.fuzzy_is_disabled.stateChanged.connect(self._state_change_fuzzy_search)
        self.fuzzy_is_disabled.setToolTip(
            "Enable approximate matching (OFF) and exact matching (ON)"
        )
        self.fuzzy_label.setToolTip("Enable approximate matching (OFF) and exact matching (ON)")
        self.fuzzy_layout.addWidget(self.fuzzy_label)
        self.fuzzy_layout.addWidget(self.fuzzy_is_disabled)
        self.fuzzy_layout.addStretch()

        # Add both search components to the layout
        self.search_controls = QtWidgets.QHBoxLayout()
        self.search_controls.addLayout(self.search_layout)
        self.search_controls.addSpacing(20)  # Add some space between the search box and toggle
        self.search_controls.addLayout(self.fuzzy_layout)
        QtCore.QTimer.singleShot(0, lambda: self.fuzzy_is_disabled.stateChanged.emit(0))

    # -------------------------------------------------------------------------
    # Row Management, internal methods.
    # -------------------------------------------------------------------------

    def _add_row(
        self,
        data: dict,
        config_status: ConfigStatus | int,
        connection_status: ConnectionStatus | int,
    ):
        """
        Adds a new row at the bottom and populates it with data. The row widgets
        are stored in self.row_widgets for easy access. Consider to disable sorting
        when adding rows as this method is not responsible for maintaining sort order.

        Args:
            data (dict): The device data to populate the row.
            config_status (ConfigStatus | int): The configuration validation status.
            connection_status (ConnectionStatus | int): The connection status.
        """
        with self.table_sort_on_hold:
            if data["name"] in self.row_data:
                logger.warning(f"Overwriting existing device row for {data['name']}")
                self._remove_rows_by_name([data["name"]])
            row_index = self.table.rowCount()
            self.table.insertRow(row_index)

            # Create row for the table
            device_row = DeviceTableRow(data=data)
            device_row.set_validation_status(config_status, connection_status)

            # Populate cells
            self._populate_device_row_cells(row_index, device_row)

    def _populate_device_row_cells(self, row: int, device_row: DeviceTableRow):
        """Populate the cells of a given row with the widgets from the DeviceTableRow."""
        with self.table_sort_on_hold:
            config_status, connect_status = device_row.validation_status
            column_keys = list(self.headers_key_map.values())
            for ii, key in enumerate(column_keys):
                if key in ("enabled", "readOnly", "softwareTrigger"):  # flags for checkboxes
                    item = SortTableItem()
                    item.setFlags(
                        item.flags()
                        | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                        | QtCore.Qt.ItemFlag.ItemIsEnabled
                    )
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                elif key in ("valid", "connect"):  # status columns
                    item = SortTableItem()
                    item.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
                    )
                    item.setIcon(
                        self._icons["connection_status"][connect_status]
                        if key == "connect"
                        else self._icons["config_status"][config_status]
                    )
                else:
                    item = QtWidgets.QTableWidgetItem()
                    item.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, ii, item)  # +2 offset for status columns
            self.__update_device_row_data(row, device_row.data)

    def __update_device_row_data(self, row: int, data: dict):
        """
        Update an existing device row with new data.

        Args:
            row (int): The row index to update.
            data (dict): The device data to populate the row.
        """
        # Update stored row data
        if data["name"] in self.row_data:
            self.row_data[data["name"]].set_data(data)
        else:
            self.row_data[data["name"]] = DeviceTableRow(data)
        # Update table cells
        with self.table_sort_on_hold:
            column_keys = list(self.headers_key_map.values())  # map columns
            for key, value in data.items():
                if key not in column_keys:
                    continue  # Skip userParameters and deviceConfig
                column = column_keys.index(key)
                item = self.table.item(row, column)
                if not item:
                    continue
                if key in ("enabled", "readOnly", "softwareTrigger"):
                    item.setCheckState(
                        QtCore.Qt.CheckState.Checked if value else QtCore.Qt.CheckState.Unchecked
                    )
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, value)
                    item.setText("")  # No text for checkboxes
                elif key == "deviceTags":
                    item.setText(
                        ", ".join(value) if isinstance(value, (list, set, tuple)) else str(value)
                    )
                elif key == "deviceClass":
                    item.setText(
                        value.split(".")[-1]
                    )  # Only show the DeviceClass, not the full module
                else:
                    if value is None:
                        value = ""
                    item.setText(str(value))
            self._update_device_row_status(
                row,
                self.row_data[data["name"]].validation_status[0],
                self.row_data[data["name"]].validation_status[1],
            )
            self.table.resizeRowToContents(row)
        self._on_device_row_data_changed(self.row_data[data["name"]].data)
        return True

    def _update_device_row_status(
        self, row: int, config_status: int, connection_status: int
    ) -> bool:
        """
        Update an existing device row's validation status.

        Args:
            device_name (str): The name of the device.
            config_status (int): The configuration validation status.
            connection_status (int): The connection status.
        """
        with self.table_sort_on_hold:
            item = self.table.item(row, 0)  # Config status column
            if item:
                item.setData(QtCore.Qt.ItemDataRole.UserRole, config_status)
                item.setIcon(self._icons["config_status"][config_status])
            item = self.table.item(row, 1)  # Connect status column
            if item:
                item.setData(QtCore.Qt.ItemDataRole.UserRole, connection_status)
                item.setIcon(self._icons["connection_status"][connection_status])

            # Update the stored row data as well
            device_name = self._get_cell_data(row, 2)  # Name column
            device_row = self.row_data.get(device_name, None)
            if not device_row:
                return False
            device_row: DeviceTableRow
            device_row.set_validation_status(config_status, connection_status)
        return True

    def _get_cell_data(self, row: int, column: int) -> str | bool | None:
        """
        Get the data from a specific cell.

        Args:
            row (int): The row index.
            column (int): The column index.
        """
        item = self.table.item(row, column)
        if item is None:
            return None
        if column in (8, 9, 10):  # Checkboxes
            return item.checkState() == QtCore.Qt.CheckState.Checked
        return item.text()

    def _update_row(self, data: dict) -> int | None:
        """
        Update an existing row with new data.

        Args:
            data (dict): The device data to populate the row.
        Returns:
            int | None: The row index if updated, else None.
        """
        device_row = self.row_data.get(data.get("name"), {})
        if self._compare_configs(device_row.data, data):
            return None  # No update needed
        row = self._find_row_by_name(data.get("name", ""))
        if row is not None:
            self.__update_device_row_data(row, data)
        return row

    def _compare_configs(self, cfg1: dict, cfg2: dict) -> bool:
        """Compare two device configurations for equality."""
        try:
            cfg1_model = DeviceModel.model_validate(cfg1)
            cfg2_model = DeviceModel.model_validate(cfg2)
            return cfg1_model == cfg2_model
        except Exception as e:
            logger.error(f"Error comparing device configs: {e}")
            return False

    def _clear_table(self):
        """Remove all rows."""
        with self.table_sort_on_hold:
            n_rows = self.table.rowCount()
            for _ in range(n_rows):
                self.table.removeRow(0)
            self.row_data.clear()

    def _find_row_by_name(self, name: str) -> int | None:
        """
        Find a row by device name.

        Args:
            name (str): The name of the device to find.
        Returns:
            int | None: The row index if found, else None.
        """
        for row in range(self.table.rowCount()):
            data = self._get_cell_data(row, 2)
            if data and data == name:
                return row
        return None

    def _remove_rows_by_name(self, device_names: list[str]):
        """
        Remove a row by device name.

        Args:
            device_name (str): The name of the device to remove.
        """
        if not device_names:
            return
        with self.table_sort_on_hold:
            for device_name in device_names:
                row = self._find_row_by_name(device_name)
                if row is None:
                    logger.warning(f"Device {device_name} not found in table for removal.")
                    return
                self.table.removeRow(row)
                self.row_data.pop(device_name, None)

    def _is_config_in_sync_with_redis(self):
        """Check if the current config is in sync with Redis."""
        if (
            not self.client
            or not self.client.device_manager
            or not self.client.device_manager.devices
        ):
            return False  # No proper client connection
        redis_config = [
            DeviceModel.model_validate(device._config)
            for device in self.client.device_manager.devices.values()
        ]
        try:
            current_config = [
                DeviceModel.model_validate(row_data.data) for row_data in self.row_data.values()
            ]
            if redis_config == current_config:
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Error comparing device configs: {e}")
            return False

    # -------------------------------------------------------------------------
    # Public API to manage device configs in the table
    # -------------------------------------------------------------------------

    def get_device_config(self) -> list[dict]:
        """
        Get the current device configurations in the table.

        Returns:
            list[dict]: The list of device configurations.
        """
        cfgs = [
            {"name": device_name, **row_data.data}
            for device_name, row_data in self.row_data.items()
        ]
        return cfgs

    def get_validation_results(self) -> dict[str, Tuple[dict, int, int]]:
        """
        Get the current device validation results in the table.

        Returns:
            dict[str, Tuple[dict, int, int]]: Dictionary mapping of device name to
                                               (device config, config status, connection status).
        """
        return {
            row_data.data.get("name"): (row_data.data, *row_data.validation_status)
            for row_data in self.row_data.values()
            if row_data.data.get("name") is not None
        }

    def get_selected_device_configs(self) -> list[dict]:
        """
        Get the currently selected device configurations in the table.

        Returns:
            list[dict]: The list of selected device configurations.
        """
        selected_configs = []
        selected_rows = set()
        for index in self.table.selectionModel().selectedIndexes():
            selected_rows.add(index.row())
        for row in selected_rows:
            device_name = self._get_cell_data(row, 2)  # Name column
            if device_name:
                row_data = self.row_data.get(device_name)
                if row_data:
                    selected_configs.append(row_data.data)
        return selected_configs

    # -------------------------------------------------------------------------
    # Public API to be called via signals/slots
    # -------------------------------------------------------------------------

    @SafeSlot(list)
    def set_device_config(self, device_configs: _DeviceCfgIter, skip_validation: bool = False):
        """
        Set the device config. This will clear any existing configs.

        Args:
            device_configs (Iterable[dict[str, Any]]): The device configs to set.
        """
        self.set_busy(True, text="Loading device configurations...")
        with self.table_sort_on_hold:
            self.clear_device_configs()
            cfgs_added = []
            for cfg in device_configs:
                self._add_row(cfg, ConfigStatus.UNKNOWN, ConnectionStatus.UNKNOWN)
                cfgs_added.append(cfg)
        self.device_configs_changed.emit(cfgs_added, True, skip_validation)
        in_sync_with_redis = self._is_config_in_sync_with_redis()
        self.device_config_in_sync_with_redis.emit(in_sync_with_redis)
        self.set_busy(False, text="")

    @SafeSlot()
    def clear_device_configs(self):
        """Clear the device configs. Skips validation per default."""
        self.set_busy(True, text="Clearing device configurations...")
        device_configs = self.get_device_config()
        with self.table_sort_on_hold:
            self._clear_table()
        self.device_configs_changed.emit(
            device_configs, False, True
        )  # Skip validation for removals
        in_sync_with_redis = self._is_config_in_sync_with_redis()
        self.device_config_in_sync_with_redis.emit(in_sync_with_redis)
        self.set_busy(False, text="")

    @SafeSlot(list)
    def add_device_configs(self, device_configs: _DeviceCfgIter, skip_validation: bool = False):
        """
        Add devices to the config. If a device already exists, it will be replaced. If the validation is
        skipped, the device will be added with UNKNOWN state to the table and has to be manually adjusted
        by the user later on.

        Args:
            device_configs (Iterable[dict[str, Any]]): The device configs to add.
        """
        self.set_busy(True, text="Adding device configurations...")
        already_in_table = []
        not_in_table = []
        with self.table_sort_on_hold:
            for cfg in device_configs:
                if cfg["name"] in self.row_data:
                    already_in_table.append(cfg)
                else:
                    not_in_table.append(cfg)
            with self.table_sort_on_hold:
                # Remove existing rows first
                if len(already_in_table) > 0:
                    self._remove_rows_by_name([cfg["name"] for cfg in already_in_table])
                    self.device_configs_changed.emit(
                        already_in_table, False, True
                    )  # Skip validation for removals

                all_configs = already_in_table + not_in_table
                if len(all_configs) > 0:
                    for cfg in already_in_table + not_in_table:
                        self._add_row(cfg, ConfigStatus.UNKNOWN, ConnectionStatus.UNKNOWN)

        self.device_configs_changed.emit(already_in_table + not_in_table, True, skip_validation)
        in_sync_with_redis = self._is_config_in_sync_with_redis()
        self.device_config_in_sync_with_redis.emit(in_sync_with_redis)
        self.set_busy(False, text="")

    @SafeSlot(list)
    def update_device_configs(self, device_configs: _DeviceCfgIter, skip_validation: bool = False):
        """
        Update devices in the config. If a device does not exist, it will be added.

        Args:
            device_configs (Iterable[dict[str, Any]]): The device configs to update.
        """
        self.set_busy(True, text="Loading device configurations...")
        cfgs_updated = []
        with self.table_sort_on_hold:
            for cfg in device_configs:
                if cfg["name"] not in self.row_data:
                    self._add_row(cfg, ConfigStatus.UNKNOWN, ConnectionStatus.UNKNOWN)
                    cfgs_updated.append(cfg)
                    continue
                # Update existing row if device config has changed
                row = self._update_row(cfg)
                if row is not None:
                    cfgs_updated.append(cfg)
        self.device_configs_changed.emit(cfgs_updated, True, skip_validation)
        in_sync_with_redis = self._is_config_in_sync_with_redis()
        self.device_config_in_sync_with_redis.emit(in_sync_with_redis)
        self.set_busy(False, text="")

    @SafeSlot(list)
    def remove_device_configs(self, device_configs: _DeviceCfgIter):
        """
        Remove devices from the config.

        Args:
            device_configs (dict[str, dict]): The device configs to remove.
        """
        self.set_busy(True, text="Removing device configurations...")
        cfgs_to_be_removed = list(device_configs)
        with self.table_sort_on_hold:
            self._remove_rows_by_name([cfg["name"] for cfg in cfgs_to_be_removed])
        self.device_configs_changed.emit(
            cfgs_to_be_removed, False, True
        )  # Skip validation for removals
        in_sync_with_redis = self._is_config_in_sync_with_redis()
        self.device_config_in_sync_with_redis.emit(in_sync_with_redis)
        self.set_busy(False, text="")

    @SafeSlot(str)
    def remove_device(self, device_name: str):
        """
        Remove a device from the config.

        Args:
            device_name (str): The name of the device to remove.
        """
        self.set_busy(True, text=f"Removing device configuration for {device_name}...")
        row_data = self.row_data.get(device_name)
        if not row_data:
            logger.warning(f"Device {device_name} not found in table for removal.")
            self.set_busy(False, text="")
            return
        with self.table_sort_on_hold:
            self._remove_rows_by_name([row_data.data["name"]])
        cfgs = [{"name": device_name, **row_data.data}]
        self.device_configs_changed.emit(cfgs, False, True)  # Skip validation for removals
        in_sync_with_redis = self._is_config_in_sync_with_redis()
        self.device_config_in_sync_with_redis.emit(in_sync_with_redis)
        self.set_busy(False, text="")

    @SafeSlot(list)
    def update_multiple_device_validations(self, validation_results: _ValidationResultIter):
        """
        Slot to update multiple device validation statuses. This is recommended and more
        efficient than updating individual device validation statuses which may affect
        the performance of the UI when many devices are being updated in quick succession.

        Args:
            device_configs (Iterable[dict[str, Any]]): The device configs to update.
        """
        self.set_busy(True, text="Updating device validations in session...")
        self.table.setSortingEnabled(False)
        for cfg, config_status, connection_status, _ in validation_results:
            row = self._find_row_by_name(cfg.get("name", ""))
            if row is None:
                logger.warning(f"Device {cfg.get('name')} not found in table for session update.")
                continue
            self._update_device_row_status(row, config_status, connection_status)
        self.table.setSortingEnabled(True)
        self.set_busy(False, text="")

    @SafeSlot(dict, int, int, str)
    def update_device_validation(
        self, device_config: dict, config_status: int, connection_status: int, validation_msg: str
    ) -> None:
        """
        Update the validation status of a device. If multiple devices are being updated in a batch,
        consider using the `update_multiple_device_validations` method instead for better performance.

        Args:

        """
        self.set_busy(True, text="Updating device validation status...")
        row = self._find_row_by_name(device_config.get("name", ""))
        if row is None:
            logger.warning(
                f"Device {device_config.get('name')} not found in table for validation update."
            )
            self.set_busy(False, text="")
            return
        # Disable here sorting without context manager to avoid triggering of registered
        # resizing methods. Those can be quite heavy, thus, should not run on every
        # update of a validation status.
        self.table.setSortingEnabled(False)
        self._update_device_row_status(row, config_status, connection_status)
        self.table.setSortingEnabled(True)
        in_sync_with_redis = self._is_config_in_sync_with_redis()
        self.device_config_in_sync_with_redis.emit(in_sync_with_redis)
        self.set_busy(False, text="")
