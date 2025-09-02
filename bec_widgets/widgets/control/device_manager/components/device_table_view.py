"""Module with the device table view implementation."""

from __future__ import annotations

import copy
import json
from typing import List
from uuid import uuid4

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy import QtCore, QtGui, QtWidgets
from thefuzz import fuzz

from bec_widgets.utils.bec_signal_proxy import BECSignalProxy
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.device_manager.components._util import SharedSelectionSignal
from bec_widgets.widgets.control.device_manager.components.constants import MIME_DEVICE_CONFIG
from bec_widgets.widgets.control.device_manager.components.dm_ophyd_test import ValidationStatus

logger = bec_logger.logger

# Threshold for fuzzy matching, careful with adjusting this. 80 seems good
FUZZY_SEARCH_THRESHOLD = 80


class DictToolTipDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate that shows all key-value pairs of a rows's data as a YAML-like tooltip."""

    def helpEvent(self, event, view, option, index):
        """Override to show tooltip when hovering."""
        if event.type() != QtCore.QEvent.ToolTip:
            return super().helpEvent(event, view, option, index)
        model: DeviceFilterProxyModel = index.model()
        model_index = model.mapToSource(index)
        row_dict = model.sourceModel().get_row_data(model_index)
        description = row_dict.get("description", "")
        QtWidgets.QToolTip.showText(event.globalPos(), description, view)
        return True


class CenterCheckBoxDelegate(DictToolTipDelegate):
    """Custom checkbox delegate to center checkboxes in table cells."""

    def __init__(self, parent=None, colors=None):
        super().__init__(parent)
        self._colors = colors if colors else get_accent_colors()
        self._icon_checked = material_icon(
            "check_box", size=QtCore.QSize(16, 16), color=self._colors.default, filled=True
        )
        self._icon_unchecked = material_icon(
            "check_box_outline_blank",
            size=QtCore.QSize(16, 16),
            color=self._colors.default,
            filled=True,
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


class DeviceValidatedDelegate(DictToolTipDelegate):
    """Custom delegate for displaying validated device configurations."""

    def __init__(self, parent=None, colors=None):
        super().__init__(parent)
        self._colors = colors if colors else get_accent_colors()
        self._icons = {
            ValidationStatus.PENDING: material_icon(
                icon_name="circle", size=(12, 12), color=self._colors.default, filled=True
            ),
            ValidationStatus.VALID: material_icon(
                icon_name="circle", size=(12, 12), color=self._colors.success, filled=True
            ),
            ValidationStatus.FAILED: material_icon(
                icon_name="circle", size=(12, 12), color=self._colors.emergency, filled=True
            ),
        }

    def apply_theme(self, theme: str | None = None):
        colors = get_accent_colors()
        for status, icon in self._icons.items():
            icon.setColor(colors[status])

    def paint(self, painter, option, index):
        status = index.model().data(index, QtCore.Qt.DisplayRole)
        if status is None:
            return super().paint(painter, option, index)

        pixmap = self._icons.get(status)
        if pixmap:
            rect = option.rect
            pix_rect = pixmap.rect()
            pix_rect.moveCenter(rect.center())
            painter.drawPixmap(pix_rect.topLeft(), pixmap)

        super().paint(painter, option, index)


class WrappingTextDelegate(DictToolTipDelegate):
    """Custom delegate for wrapping text in table cells."""

    def __init__(self, table: BECTableView, parent=None):
        super().__init__(parent)
        self._table = table

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
        column_width = self._table.columnWidth(index.column()) - 8  # -4 & 4

        # Avoid pathological heights for too-narrow columns
        min_width = option.fontMetrics.averageCharWidth() * 4
        if column_width < min_width:
            fm = QtGui.QFontMetrics(option.font)
            elided = fm.elidedText(text, QtCore.Qt.ElideRight, column_width)
            return QtCore.QSize(column_width, fm.height() + 4)

        doc = QtGui.QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setTextWidth(column_width)
        doc.setPlainText(text)

        layout_height = doc.documentLayout().documentSize().height()
        return QtCore.QSize(column_width, int(layout_height) + 4)

    # def sizeHint(self, option, index):
    #     text = str(index.model().data(index, QtCore.Qt.DisplayRole) or "")
    #     # if not text:
    #     #     return super().sizeHint(option, index)

    #     # Use the actual column width
    #     table = index.model().parent()  # or store reference to QTableView
    #     column_width = table.columnWidth(index.column())  # - 8

    #     doc = QtGui.QTextDocument()
    #     doc.setDefaultFont(option.font)
    #     doc.setTextWidth(column_width)
    #     doc.setPlainText(text)

    #     layout_height = doc.documentLayout().documentSize().height()
    #     height = int(layout_height) + 4  # Needs some extra padding, otherwise it gets cut off
    #     return QtCore.QSize(column_width, height)


class DeviceTableModel(QtCore.QAbstractTableModel):
    """
    Custom Device Table Model for managing device configurations.

    Sort logic is implemented directly on the data of the table view.
    """

    device_configs_added = QtCore.Signal(dict)  # Dict[str, dict] of configs that were added
    devices_removed = QtCore.Signal(list)  # List of strings with device names that were removed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._device_config: dict[str, dict] = {}
        self._list_items: list[dict] = []
        self._validation_status: dict[str, ValidationStatus] = {}
        self.headers = [
            "",
            "name",
            "deviceClass",
            "readoutPriority",
            "deviceTags",
            "enabled",
            "readOnly",
        ]
        self._checkable_columns_enabled = {"enabled": True, "readOnly": True}

    ###############################################
    ########## Overwrite custom Qt methods ########
    ###############################################

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self._list_items)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self.headers)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.headers[section]
        return None

    def get_row_data(self, index: QtCore.QModelIndex) -> dict:
        """Return the row data for the given index."""
        if not index.isValid():
            return {}
        return copy.deepcopy(self._list_items[index.row()])

    def data(self, index, role=QtCore.Qt.DisplayRole):
        """Return data for the given index and role."""
        if not index.isValid():
            return None
        row, col = index.row(), index.column()

        if col == 0 and role == QtCore.Qt.DisplayRole:  # QtCore.Qt.DisplayRole:
            dev_name = self._list_items[row].get("name", "")
            return self._validation_status.get(dev_name, ValidationStatus.PENDING)

        key = self.headers[col]
        value = self._list_items[row].get(key)

        if role == QtCore.Qt.DisplayRole:
            if key in ("enabled", "readOnly"):
                return bool(value)
            if key == "deviceTags":
                return ", ".join(str(tag) for tag in value) if value else ""
            if key == "deviceClass":
                return str(value).split(".")[-1]
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

        base_flags = super().flags(index) | (
            QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsSelectable
            | QtCore.Qt.ItemFlag.ItemIsDropEnabled
        )

        if key in ("enabled", "readOnly"):
            if self._checkable_columns_enabled.get(key, True):
                return base_flags | QtCore.Qt.ItemFlag.ItemIsUserCheckable
            else:
                return base_flags  # disable editing but still visible
        return base_flags

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
            self._list_items[row][key] = value == QtCore.Qt.Checked
            self.dataChanged.emit(index, index, [QtCore.Qt.CheckStateRole])
            return True
        return False

    ####################################
    ############ Drag and Drop #########
    ####################################

    def mimeTypes(self) -> List[str]:
        return [*super().mimeTypes(), MIME_DEVICE_CONFIG]

    def supportedDropActions(self):
        return QtCore.Qt.DropAction.CopyAction | QtCore.Qt.DropAction.MoveAction

    def dropMimeData(self, data, action, row, column, parent):
        if action not in [QtCore.Qt.DropAction.CopyAction, QtCore.Qt.DropAction.MoveAction]:
            return False
        if (raw_data := data.data(MIME_DEVICE_CONFIG)) is None:
            return False
        device_list = json.loads(raw_data.toStdString())
        self.add_device_configs({dev.pop("name"): dev for dev in device_list})
        return True

    ####################################
    ############ Public methods ########
    ####################################

    def get_device_config(self) -> dict[str, dict]:
        """Method to get the device configuration."""
        return self._device_config

    def add_device_configs(self, device_configs: dict[str, dict]):
        """
        Add devices to the model.

        Args:
            device_configs (dict[str, dict]): A dictionary of device configurations to add.
        """
        already_in_list = []
        for k, cfg in device_configs.items():
            if k in self._device_config:
                logger.warning(f"Device {k} already exists in the model.")
                already_in_list.append(k)
                continue
            self._device_config[k] = cfg
            new_list_cfg = copy.deepcopy(cfg)
            new_list_cfg["name"] = k
            row = len(self._list_items)
            self.beginInsertRows(QtCore.QModelIndex(), row, row)
            self._list_items.append(new_list_cfg)
            self.endInsertRows()
        for k in already_in_list:
            device_configs.pop(k)
        self.device_configs_added.emit(device_configs)

    def set_device_config(self, device_configs: dict[str, dict]):
        """
        Replace the device config.

        Args:
            device_config (dict[str, dict]): The new device config to set.
        """
        diff_names = set(device_configs.keys()) - set(self._device_config.keys())
        self.beginResetModel()
        self._device_config.clear()
        self._list_items.clear()
        for k, cfg in device_configs.items():
            self._device_config[k] = cfg
            new_list_cfg = copy.deepcopy(cfg)
            new_list_cfg["name"] = k
            self._list_items.append(new_list_cfg)
        self.endResetModel()
        self.devices_removed.emit(diff_names)
        self.device_configs_added.emit(device_configs)

    def remove_device_configs(self, device_configs: dict[str, dict]):
        """
        Remove devices from the model.

        Args:
            device_configs (dict[str, dict]): A dictionary of device configurations to remove.
        """
        removed = []
        for k in device_configs.keys():
            if k not in self._device_config:
                logger.warning(f"Device {k} does not exist in the model.")
                continue
            new_cfg = self._device_config.pop(k)
            new_cfg["name"] = k
            row = self._list_items.index(new_cfg)
            self.beginRemoveRows(QtCore.QModelIndex(), row, row)
            self._list_items.pop(row)
            self.endRemoveRows()
            removed.append(k)
        self.devices_removed.emit(removed)

    def clear_table(self):
        """
        Clear the table.
        """
        device_names = list(self._device_config.keys())
        self.beginResetModel()
        self._device_config.clear()
        self._list_items.clear()
        self.endResetModel()
        self.devices_removed.emit(device_names)

    def update_validation_status(self, device_name: str, status: int | ValidationStatus):
        """
        Handle device status changes.

        Args:
            device_name (str): The name of the device.
            status (int): The new status of the device.
        """
        if isinstance(status, int):
            status = ValidationStatus(status)
        if device_name not in self._device_config:
            logger.warning(
                f"Device {device_name} not found in device_config dict {self._device_config}"
            )
            return
        self._validation_status[device_name] = status
        row = None
        for ii, item in enumerate(self._list_items):
            if item["name"] == device_name:
                row = ii
                break
        if row is None:
            logger.warning(
                f"Device {device_name} not found in device_status dict {self._validation_status}"
            )
            return
        # Emit dataChanged for column 0 (status column)
        index = self.index(row, 0)
        self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole])


class BECTableView(QtWidgets.QTableView):
    """Table View with custom keyPressEvent to delete rows with backspace or delete key"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtWidgets.QTableView.DragDropMode.DropOnly)

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

        source_rows = self._get_source_rows(proxy_indexes)

        model: DeviceTableModel = self.model().sourceModel()  # access underlying model
        # Delegate confirmation and removal to helper
        removed = self._confirm_and_remove_rows(model, source_rows)
        if not removed:
            return

    def _get_source_rows(self, proxy_indexes: list[QtWidgets.QModelIndex]) -> list[int]:
        """
        Map proxy model indices to source model row indices.

        Args:
            proxy_indexes (list[QModelIndex]): List of proxy model indices.

        Returns:
            list[int]: List of source model row indices.
        """
        proxy_rows = sorted({idx for idx in proxy_indexes}, reverse=True)
        source_rows = [self.model().mapToSource(idx).row() for idx in proxy_rows]
        return list(set(source_rows))

    def _confirm_and_remove_rows(self, model: DeviceTableModel, source_rows: list[int]) -> bool:
        """
        Prompt the user to confirm removal of rows and remove them from the model if accepted.

        Returns True if rows were removed, False otherwise.
        """
        configs = [model._list_items[r] for r in sorted(source_rows)]
        names = [cfg.get("name", "<unknown>") for cfg in configs]

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
            configs_to_be_removed = {model._device_config[name] for name in names}
            model.remove_device_configs(configs_to_be_removed)
            return True
        return False


class DeviceFilterProxyModel(QtCore.QSortFilterProxyModel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hidden_rows = set()
        self._filter_text = ""
        self._enable_fuzzy = True
        self._filter_columns = [1, 2]  # name and deviceClass for search

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

    def flags(self, index):
        return super().flags(index) | QtCore.Qt.ItemFlag.ItemIsDropEnabled

    def supportedDropActions(self):
        return self.sourceModel().supportedDropActions()

    def mimeTypes(self):
        return self.sourceModel().mimeTypes()

    def dropMimeData(self, data, action, row, column, parent):
        sp = self.mapToSource(parent) if parent.isValid() else QtCore.QModelIndex()
        return self.sourceModel().dropMimeData(data, action, row, column, sp)


class DeviceTableView(BECWidget, QtWidgets.QWidget):
    """Device Table View for the device manager."""

    selected_device = QtCore.Signal(dict)  # Selected device configuration dict[str,dict]
    device_configs_added = QtCore.Signal(dict)  # Dict[str, dict] of configs that were added
    devices_removed = QtCore.Signal(list)  # List of strings with device names that were removed

    RPC = False
    PLUGIN = False

    def __init__(self, parent=None, client=None, shared_selection_signal=SharedSelectionSignal()):
        super().__init__(client=client, parent=parent, theme_update=True)

        self._shared_selection_signal = shared_selection_signal
        self._shared_selection_uuid = str(uuid4())
        self._shared_selection_signal.proc.connect(self._handle_shared_selection_signal)

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

        # Connect signals
        self._model.devices_removed.connect(self.devices_removed.emit)
        self._model.device_configs_added.connect(self.device_configs_added.emit)

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
        self._model = DeviceTableModel(parent=self.table)
        self.proxy = DeviceFilterProxyModel(parent=self.table)
        self.proxy.setSourceModel(self._model)
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)

        # Delegates
        colors = get_accent_colors()
        self.checkbox_delegate = CenterCheckBoxDelegate(self.table, colors=colors)
        self.wrap_delegate = WrappingTextDelegate(self.table)
        self.tool_tip_delegate = DictToolTipDelegate(self.table)
        self.validated_delegate = DeviceValidatedDelegate(self.table, colors=colors)
        self.table.setItemDelegateForColumn(0, self.validated_delegate)  # ValidationStatus
        self.table.setItemDelegateForColumn(1, self.tool_tip_delegate)  # name
        self.table.setItemDelegateForColumn(2, self.tool_tip_delegate)  # deviceClass
        self.table.setItemDelegateForColumn(3, self.tool_tip_delegate)  # readoutPriority
        self.table.setItemDelegateForColumn(4, self.wrap_delegate)  # deviceTags
        self.table.setItemDelegateForColumn(5, self.checkbox_delegate)  # enabled
        self.table.setItemDelegateForColumn(6, self.checkbox_delegate)  # readOnly

        # Column resize policies
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)  # ValidationStatus
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # name
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  # deviceClass
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)  # readoutPriority
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)  # deviceTags
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.Fixed)  # enabled
        header.setSectionResizeMode(6, QtWidgets.QHeaderView.Fixed)  # readOnly

        self.table.setColumnWidth(0, 25)
        self.table.setColumnWidth(5, 70)
        self.table.setColumnWidth(6, 70)

        # Ensure column widths stay fixed
        header.setMinimumSectionSize(25)
        header.setDefaultSectionSize(90)

        # Enable resizing of column
        self._geometry_resize_proxy = BECSignalProxy(
            header.geometriesChanged, rateLimit=10, slot=self._on_table_resized
        )

        # Selection behavior
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        # Connect to selection model to get selection changes
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.horizontalHeader().setHighlightSections(False)

        # QtCore.QTimer.singleShot(0, lambda: header.sectionResized.emit(0, 0, 0))

    def get_device_config(self) -> dict[str, dict]:
        """Get the device config."""
        return self._model.get_device_config()

    def apply_theme(self, theme: str | None = None):
        self.checkbox_delegate.apply_theme(theme)
        self.validated_delegate.apply_theme(theme)

    ######################################
    ########### Slot API #################
    ######################################

    @SafeSlot()
    def _on_table_resized(self, *args):
        """Handle changes to the table column resizing."""
        option = QtWidgets.QStyleOptionViewItem()
        model = self.table.model()
        for row in range(model.rowCount()):
            index = model.index(row, 4)
            height = self.wrap_delegate.sizeHint(option, index).height()
            self.table.setRowHeight(row, height)

    @SafeSlot(str)
    def _handle_shared_selection_signal(self, uuid: str):
        if uuid != self._shared_selection_uuid:
            self.table.clearSelection()

    @SafeSlot(QtCore.QItemSelection, QtCore.QItemSelection)
    def _on_selection_changed(
        self, selected: QtCore.QItemSelection, deselected: QtCore.QItemSelection
    ) -> None:
        """
        Handle selection changes in the device table.

        Args:
            selected (QtCore.QItemSelection): The selected items.
            deselected (QtCore.QItemSelection): The deselected items.
        """

        self._shared_selection_signal.proc.emit(self._shared_selection_uuid)

        # TODO also hook up logic if a config update is propagated from somewhere!
        # selected_indexes = selected.indexes()
        selected_indexes = self.table.selectionModel().selectedIndexes()
        if not selected_indexes:
            return

        source_indexes = [self.proxy.mapToSource(idx) for idx in selected_indexes]
        source_rows = {idx.row() for idx in source_indexes}
        configs = [copy.deepcopy(self._model._list_items[r]) for r in sorted(source_rows)]
        names = [cfg.pop("name") for cfg in configs]
        selected_cfgs = {name: cfg for name, cfg in zip(names, configs)}
        self.selected_device.emit(selected_cfgs)

    ######################################
    ##### Ext.  Slot API #################
    ######################################

    @SafeSlot(dict)
    def set_device_config(self, device_configs: dict[str, dict]):
        """
        Set the device config.

        Args:
            config (dict[str,dict]): The device config to set.
        """
        self._model.set_device_config(device_configs)

    @SafeSlot()
    def clear_device_configs(self):
        """Clear the device configs."""
        self._model.clear_table()

    @SafeSlot(dict)
    def add_device_configs(self, device_configs: dict[str, dict]):
        """
        Add devices to the config.

        Args:
            device_configs (dict[str, dict]): The device configs to add.
        """
        self._model.add_device_configs(device_configs)

    @SafeSlot(dict)
    def remove_device_configs(self, device_configs: dict[str, dict]):
        """
        Remove devices from the config.

        Args:
            device_configs (dict[str, dict]): The device configs to remove.
        """
        self._model.remove_device_configs(device_configs)

    @SafeSlot(str)
    def remove_device(self, device_name: str):
        """
        Remove a device from the config.

        Args:
            device_name (str): The name of the device to remove.
        """
        cfg = self._model._device_config.get(device_name, None)
        if cfg is None:
            logger.warning(f"Device {device_name} not found in device_config dict")
            return
        self._model.remove_device_configs({device_name: cfg})

    @SafeSlot(str, int)
    def update_device_validation(
        self, device_name: str, validation_status: int | ValidationStatus
    ) -> None:
        """
        Update the validation status of a device.

        Args:
            device_name (str): The name of the device.
            validation_status (int | ValidationStatus): The new validation status.
        """
        self._model.update_validation_status(device_name, validation_status)


if __name__ == "__main__":
    import sys

    import numpy as np
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    window = DeviceTableView()
    layout.addWidget(window)
    # QPushButton
    button = QtWidgets.QPushButton("Test status_update")
    layout.addWidget(button)

    def _button_clicked():
        names = list(window._model._device_config.keys())
        for name in names:
            window.update_device_validation(
                name, ValidationStatus.VALID if np.random.rand() > 0.5 else ValidationStatus.FAILED
            )

    button.clicked.connect(_button_clicked)
    # pylint: disable=protected-access
    config = window.client.device_manager._get_redis_device_config()
    names = [cfg.pop("name") for cfg in config]
    config_dict = {name: cfg for name, cfg in zip(names, config)}
    window.set_device_config(config_dict)
    widget.show()
    sys.exit(app.exec_())
