"""Module with the device table view implementation."""

from __future__ import annotations

import copy
import json

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy import QtCore, QtGui, QtWidgets
from thefuzz import fuzz

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot

logger = bec_logger.logger

# Threshold for fuzzy matching, careful with adjusting this. 80 seems good
FUZZY_SEARCH_THRESHOLD = 80


class DictToolTipDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate that shows all key-value pairs of a rows's data as a YAML-like tooltip."""

    @staticmethod
    def dict_to_str(d: dict) -> str:
        """Convert a dictionary to a formatted string."""
        return json.dumps(d, indent=4)

    def helpEvent(self, event, view, option, index):
        """Override to show tooltip when hovering."""
        if event.type() != QtCore.QEvent.ToolTip:
            return super().helpEvent(event, view, option, index)
        model: DeviceFilterProxyModel = index.model()
        model_index = model.mapToSource(index)
        row_dict = model.sourceModel().row_data(model_index)
        row_dict.pop("description", None)
        QtWidgets.QToolTip.showText(event.globalPos(), self.dict_to_str(row_dict), view)
        return True


class CenterCheckBoxDelegate(DictToolTipDelegate):
    """Custom checkbox delegate to center checkboxes in table cells."""

    def __init__(self, parent=None):
        super().__init__(parent)
        colors = get_accent_colors()
        self._icon_checked = material_icon(
            "check_box", size=QtCore.QSize(16, 16), color=colors.default
        )
        self._icon_unchecked = material_icon(
            "check_box_outline_blank", size=QtCore.QSize(16, 16), color=colors.default
        )

    def apply_theme(self, theme: str | None = None):
        colors = get_accent_colors()
        self._icon_checked.setColor(colors.default)
        self._icon_unchecked.setColor(colors.default)

    def paint(self, painter, option, index):
        value = index.model().data(index, QtCore.Qt.CheckStateRole)
        if value is None:
            super().paint(painter, option, index)
            return

        # Choose icon based on state
        pixmap = self._icon_checked if value == QtCore.Qt.Checked else self._icon_unchecked

        # Draw icon centered
        rect = option.rect
        pix_rect = pixmap.rect()
        pix_rect.moveCenter(rect.center())
        painter.drawPixmap(pix_rect.topLeft(), pixmap)

    def editorEvent(self, event, model, option, index):
        if event.type() != QtCore.QEvent.MouseButtonRelease:
            return False
        current = model.data(index, QtCore.Qt.CheckStateRole)
        new_state = QtCore.Qt.Unchecked if current == QtCore.Qt.Checked else QtCore.Qt.Checked
        return model.setData(index, new_state, QtCore.Qt.CheckStateRole)


class WrappingTextDelegate(DictToolTipDelegate):
    """Custom delegate for wrapping text in table cells."""

    def paint(self, painter, option, index):
        text = index.model().data(index, QtCore.Qt.DisplayRole)
        if not text:
            return super().paint(painter, option, index)

        painter.save()
        painter.setClipRect(option.rect)
        text_option = QtCore.Qt.TextWordWrap | QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop
        painter.drawText(option.rect.adjusted(4, 2, -4, -2), text_option, text)
        painter.restore()

    def sizeHint(self, option, index):
        text = str(index.model().data(index, QtCore.Qt.DisplayRole) or "")
        # if not text:
        #     return super().sizeHint(option, index)

        # Use the actual column width
        table = index.model().parent()  # or store reference to QTableView
        column_width = table.columnWidth(index.column())  # - 8

        doc = QtGui.QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setTextWidth(column_width)
        doc.setPlainText(text)

        layout_height = doc.documentLayout().documentSize().height()
        height = int(layout_height) + 4  # Needs some extra padding, otherwise it gets cut off
        return QtCore.QSize(column_width, height)


class DeviceTableModel(QtCore.QAbstractTableModel):
    """
    Custom Device Table Model for managing device configurations.

    Sort logic is implemented directly on the data of the table view.
    """

    def __init__(self, device_config: list[dict] | None = None, parent=None):
        super().__init__(parent)
        self._device_config = device_config or []
        self.headers = [
            "name",
            "deviceClass",
            "readoutPriority",
            "enabled",
            "readOnly",
            "deviceTags",
            "description",
        ]
        self._checkable_columns_enabled = {"enabled": True, "readOnly": True}

    ###############################################
    ########## Overwrite custom Qt methods ########
    ###############################################

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self._device_config)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self.headers)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.headers[section]
        return None

    def row_data(self, index: QtCore.QModelIndex) -> dict:
        """Return the row data for the given index."""
        if not index.isValid():
            return {}
        return copy.deepcopy(self._device_config[index.row()])

    def data(self, index, role=QtCore.Qt.DisplayRole):
        """Return data for the given index and role."""
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        key = self.headers[col]
        value = self._device_config[row].get(key)

        if role == QtCore.Qt.DisplayRole:
            if key in ("enabled", "readOnly"):
                return bool(value)
            if key == "deviceTags":
                return ", ".join(str(tag) for tag in value) if value else ""
            return str(value) if value is not None else ""
        if role == QtCore.Qt.CheckStateRole and key in ("enabled", "readOnly"):
            return QtCore.Qt.Checked if value else QtCore.Qt.Unchecked
        if role == QtCore.Qt.TextAlignmentRole:
            if key in ("enabled", "readOnly"):
                return QtCore.Qt.AlignCenter
            return QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
        if role == QtCore.Qt.FontRole:
            font = QtGui.QFont()
            return font
        return None

    def flags(self, index):
        """Flags for the table model."""
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        key = self.headers[index.column()]

        if key in ("enabled", "readOnly"):
            base_flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
            if self._checkable_columns_enabled.get(key, True):
                return base_flags | QtCore.Qt.ItemIsUserCheckable
            else:
                return base_flags  # disable editing but still visible
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def setData(self, index, value, role=QtCore.Qt.EditRole) -> bool:
        """
        Method to set the data of the table.

        Args:
            index (QModelIndex): The index of the item to modify.
            value (Any): The new value to set.
            role (Qt.ItemDataRole): The role of the data being set.

        Returns:
            bool: True if the data was set successfully, False otherwise.
        """
        if not index.isValid():
            return False
        key = self.headers[index.column()]
        row = index.row()

        if key in ("enabled", "readOnly") and role == QtCore.Qt.CheckStateRole:
            if not self._checkable_columns_enabled.get(key, True):
                return False  # ignore changes if column is disabled
            self._device_config[row][key] = value == QtCore.Qt.Checked
            self.dataChanged.emit(index, index, [QtCore.Qt.CheckStateRole])
            return True
        return False

    ####################################
    ############ Public methods ########
    ####################################

    def get_device_config(self) -> list[dict]:
        """Return the current device config (with checkbox updates applied)."""
        return self._device_config

    def set_checkbox_enabled(self, column_name: str, enabled: bool):
        """
        Enable/Disable the checkbox column.

        Args:
            column_name (str): The name of the column to modify.
            enabled (bool): Whether the checkbox should be enabled or disabled.
        """
        if column_name in self._checkable_columns_enabled:
            self._checkable_columns_enabled[column_name] = enabled
            col = self.headers.index(column_name)
            top_left = self.index(0, col)
            bottom_right = self.index(self.rowCount() - 1, col)
            self.dataChanged.emit(
                top_left, bottom_right, [QtCore.Qt.CheckStateRole, QtCore.Qt.DisplayRole]
            )

    def set_device_config(self, device_config: list[dict]):
        """
        Replace the device config.

        Args:
            device_config (list[dict]): The new device config to set.
        """
        self.beginResetModel()
        self._device_config = list(device_config)
        self.endResetModel()

    @SafeSlot(dict)
    def add_device(self, device: dict):
        """
        Add an extra device to the device config at the bottom.

        Args:
            device (dict): The device configuration to add.
        """
        row = len(self._device_config)
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self._device_config.append(device)
        self.endInsertRows()

    @SafeSlot(int)
    def remove_device_by_row(self, row: int):
        """
        Remove one device row by index. This maps to the row to the source of the data model

        Args:
            row (int): The index of the device row to remove.
        """
        if 0 <= row < len(self._device_config):
            self.beginRemoveRows(QtCore.QModelIndex(), row, row)
            self._device_config.pop(row)
            self.endRemoveRows()

    @SafeSlot(list)
    def remove_devices_by_rows(self, rows: list[int]):
        """
        Remove multiple device rows by their indices.

        Args:
            rows (list[int]): The indices of the device rows to remove.
        """
        for row in sorted(rows, reverse=True):
            self.remove_device_by_row(row)

    @SafeSlot(str)
    def remove_device_by_name(self, name: str):
        """
        Remove one device row by name.

        Args:
            name (str): The name of the device to remove.
        """
        for row, device in enumerate(self._device_config):
            if device.get("name") == name:
                self.remove_device_by_row(row)
                break


class BECTableView(QtWidgets.QTableView):
    """Table View with custom keyPressEvent to delete rows with backspace or delete key"""

    def keyPressEvent(self, event) -> None:
        """
        Delete selected rows with backspace or delete key

        Args:
            event: keyPressEvent
        """
        if event.key() not in (QtCore.Qt.Key_Backspace, QtCore.Qt.Key_Delete):
            return super().keyPressEvent(event)

        proxy_indexes = self.selectedIndexes()
        if not proxy_indexes:
            return

        # Get unique rows (proxy indices) in reverse order so removal indexes stay valid
        proxy_rows = sorted({idx.row() for idx in proxy_indexes}, reverse=True)
        # Map to source model rows
        source_rows = [
            self.model().mapToSource(self.model().index(row, 0)).row() for row in proxy_rows
        ]

        model: DeviceTableModel = self.model().sourceModel()  # access underlying model
        # Delegate confirmation and removal to helper
        removed = self._confirm_and_remove_rows(model, source_rows)
        if not removed:
            return

    def _confirm_and_remove_rows(self, model: DeviceTableModel, source_rows: list[int]) -> bool:
        """
        Prompt the user to confirm removal of rows and remove them from the model if accepted.

        Returns True if rows were removed, False otherwise.
        """
        cfg = model.get_device_config()
        names = [str(cfg[r].get("name", "<unknown>")) for r in sorted(source_rows)]

        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowTitle("Confirm remove devices")
        if len(names) == 1:
            msg.setText(f"Remove device '{names[0]}'?")
        else:
            msg.setText(f"Remove {len(names)} devices?")
        msg.setInformativeText("\n".join(names))
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        msg.setDefaultButton(QtWidgets.QMessageBox.Cancel)

        res = msg.exec_()
        if res == QtWidgets.QMessageBox.Ok:
            model.remove_devices_by_rows(source_rows)
            # TODO add signal for removed devices
            return True
        return False


class DeviceFilterProxyModel(QtCore.QSortFilterProxyModel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hidden_rows = set()
        self._filter_text = ""
        self._enable_fuzzy = True
        self._filter_columns = [0, 1]  # name and deviceClass for search

    def hide_rows(self, row_indices: list[int]):
        """
        Hide specific rows in the model.

        Args:
            row_indices (list[int]): List of row indices to hide.
        """
        self._hidden_rows.update(row_indices)
        self.invalidateFilter()

    def show_rows(self, row_indices: list[int]):
        """
        Show specific rows in the model.

        Args:
            row_indices (list[int]): List of row indices to show.
        """
        self._hidden_rows.difference_update(row_indices)
        self.invalidateFilter()

    def show_all_rows(self):
        """
        Show all rows in the model.
        """
        self._hidden_rows.clear()
        self.invalidateFilter()

    @SafeSlot(int)
    def disable_fuzzy_search(self, enabled: int):
        self._enable_fuzzy = not bool(enabled)
        self.invalidateFilter()

    def setFilterText(self, text: str):
        self._filter_text = text.lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        # No hidden rows, and no filter text
        if not self._filter_text and not self._hidden_rows:
            return True
        # Hide hidden rows
        if source_row in self._hidden_rows:
            return False
        # Check the filter text for each row
        model = self.sourceModel()
        text = self._filter_text.lower()
        for column in self._filter_columns:
            index = model.index(source_row, column, source_parent)
            data = str(model.data(index, QtCore.Qt.DisplayRole) or "")
            if self._enable_fuzzy is True:
                match_ratio = fuzz.partial_ratio(self._filter_text.lower(), data.lower())
                if match_ratio >= FUZZY_SEARCH_THRESHOLD:
                    return True
            else:
                if text in data.lower():
                    return True
        return False


class DeviceTableView(BECWidget, QtWidgets.QWidget):
    """Device Table View for the device manager."""

    RPC = False
    PLUGIN = False
    devices_removed = QtCore.Signal(list)

    def __init__(self, parent=None, client=None):
        super().__init__(client=client, parent=parent, theme_update=True)

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)

        # Setup table view
        self._setup_table_view()
        # Setup search view, needs table proxy to be iniditate
        self._setup_search()
        # Add widgets to main layout
        self.layout.addLayout(self.search_controls)
        self.layout.addWidget(self.table)

    def _setup_search(self):
        """Create components related to the search functionality"""

        # Create search bar
        self.search_layout = QtWidgets.QHBoxLayout()
        self.search_label = QtWidgets.QLabel("Search:")
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText(
            "Filter devices (approximate matching)..."
        )  # Default to fuzzy search
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.proxy.setFilterText)
        self.search_layout.addWidget(self.search_label)
        self.search_layout.addWidget(self.search_input)

        # Add exact match toggle
        self.fuzzy_layout = QtWidgets.QHBoxLayout()
        self.fuzzy_label = QtWidgets.QLabel("Exact Match:")
        self.fuzzy_is_disabled = QtWidgets.QCheckBox()

        self.fuzzy_is_disabled.stateChanged.connect(self.proxy.disable_fuzzy_search)
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

    def _setup_table_view(self) -> None:
        """Setup the table view."""
        # Model + Proxy
        self.table = BECTableView(self)
        self.model = DeviceTableModel(parent=self.table)
        self.proxy = DeviceFilterProxyModel(parent=self.table)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)

        # Delegates
        self.checkbox_delegate = CenterCheckBoxDelegate(self.table)
        self.wrap_delegate = WrappingTextDelegate(self.table)
        self.tool_tip_delegate = DictToolTipDelegate(self.table)
        self.table.setItemDelegateForColumn(0, self.tool_tip_delegate)  # name
        self.table.setItemDelegateForColumn(1, self.tool_tip_delegate)  # deviceClass
        self.table.setItemDelegateForColumn(2, self.tool_tip_delegate)  # readoutPriority
        self.table.setItemDelegateForColumn(3, self.checkbox_delegate)  # enabled
        self.table.setItemDelegateForColumn(4, self.checkbox_delegate)  # readOnly
        self.table.setItemDelegateForColumn(5, self.wrap_delegate)  # deviceTags
        self.table.setItemDelegateForColumn(6, self.wrap_delegate)  # description

        # Column resize policies
        # TODO maybe we need here a flexible header options as deviceClass
        # may get quite long for beamlines plugin repos
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)  # name
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # deviceClass
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  # readoutPriority
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)  # enabled
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Fixed)  # readOnly
        # TODO maybe better stretch...
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)  # deviceTags
        header.setSectionResizeMode(6, QtWidgets.QHeaderView.Stretch)  # description
        self.table.setColumnWidth(3, 82)
        self.table.setColumnWidth(4, 82)

        # Ensure column widths stay fixed
        header.setMinimumSectionSize(70)
        header.setDefaultSectionSize(90)

        # Enable resizing of column
        header.sectionResized.connect(self.on_table_resized)

        # Selection behavior
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.horizontalHeader().setHighlightSections(False)

        # QtCore.QTimer.singleShot(0, lambda: header.sectionResized.emit(0, 0, 0))

    def device_config(self) -> list[dict]:
        """Get the device config."""
        return self.model.get_device_config()

    def apply_theme(self, theme: str | None = None):
        self.checkbox_delegate.apply_theme(theme)

    ######################################
    ########### Slot API #################
    ######################################

    @SafeSlot(int, int, int)
    def on_table_resized(self, column, old_width, new_width):
        """Handle changes to the table column resizing."""
        if column != len(self.model.headers) - 1:
            return

        for row in range(self.table.model().rowCount()):
            index = self.table.model().index(row, column)
            delegate = self.table.itemDelegate(index)
            option = QtWidgets.QStyleOptionViewItem()
            height = delegate.sizeHint(option, index).height()
            self.table.setRowHeight(row, height)

    ######################################
    ##### Ext.  Slot API #################
    ######################################

    @SafeSlot(list)
    def set_device_config(self, config: list[dict]):
        """
        Set the device config.

        Args:
            config (list[dict]): The device config to set.
        """
        self.model.set_device_config(config)

    @SafeSlot()
    def clear_device_config(self):
        """
        Clear the device config.
        """
        self.model.set_device_config([])

    @SafeSlot(dict)
    def add_device(self, device: dict):
        """
        Add a device to the config.

        Args:
            device (dict): The device to add.
        """
        self.model.add_device(device)

    @SafeSlot(int)
    @SafeSlot(str)
    def remove_device(self, dev: int | str):
        """
        Remove the device from the config either by row id, or device name.

        Args:
            dev (int | str): The device to remove, either by row id or device name.
        """
        if isinstance(dev, int):
            # TODO test this properly, check with proxy index and source index
            # Use the proxy model to map to the correct row
            model_source_index = self.table.model().mapToSource(self.table.model().index(dev, 0))
            self.model.remove_device_by_row(model_source_index.row())
            return
        if isinstance(dev, str):
            self.model.remove_device_by_name(dev)
            return


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = DeviceTableView()
    # pylint: disable=protected-access
    config = window.client.device_manager._get_redis_device_config()
    window.set_device_config(config)
    window.show()
    sys.exit(app.exec_())
