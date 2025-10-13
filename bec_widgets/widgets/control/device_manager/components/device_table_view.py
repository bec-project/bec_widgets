"""Module with the device table view implementation."""

from __future__ import annotations

import copy
import json
import textwrap
from contextlib import contextmanager
from functools import partial
from typing import TYPE_CHECKING, Any, Iterable, List, Literal
from uuid import uuid4

from bec_lib.atlas_models import Device
from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QModelIndex, QPersistentModelIndex, Qt, QTimer
from qtpy.QtWidgets import QAbstractItemView, QHeaderView, QMessageBox
from thefuzz import fuzz

from bec_widgets.utils.bec_signal_proxy import BECSignalProxy
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.device_manager.components._util import SharedSelectionSignal
from bec_widgets.widgets.control.device_manager.components.constants import (
    HEADERS_HELP_MD,
    MIME_DEVICE_CONFIG,
)
from bec_widgets.widgets.control.device_manager.components.dm_ophyd_test import ValidationStatus

if TYPE_CHECKING:  # pragma: no cover
    from bec_qthemes._theme import AccentColors

logger = bec_logger.logger

_DeviceCfgIter = Iterable[dict[str, Any]]

# Threshold for fuzzy matching, careful with adjusting this. 80 seems good
FUZZY_SEARCH_THRESHOLD = 80

#
USER_CHECK_DATA_ROLE = 101


class DictToolTipDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate that shows all key-value pairs of a rows's data as a YAML-like tooltip."""

    def helpEvent(
        self,
        event: QtCore.QEvent,
        view: QtWidgets.QAbstractItemView,
        option: QtWidgets.QStyleOptionViewItem,
        index: QModelIndex,
    ):
        """Override to show tooltip when hovering."""
        if event.type() != QtCore.QEvent.Type.ToolTip:
            return super().helpEvent(event, view, option, index)
        model: DeviceFilterProxyModel = index.model()
        model_index = model.mapToSource(index)
        row_dict = model.sourceModel().get_row_data(model_index)
        description = row_dict.get("description", "")
        QtWidgets.QToolTip.showText(event.globalPos(), description, view)
        return True


class CustomDisplayDelegate(DictToolTipDelegate):
    _paint_test_role = Qt.ItemDataRole.DisplayRole

    def displayText(self, value: Any, locale: QtCore.QLocale | QtCore.QLocale.Language) -> str:
        return ""

    def _test_custom_paint(
        self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QModelIndex
    ):
        v = index.model().data(index, self._paint_test_role)
        return (v is not None), v

    def _do_custom_paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QModelIndex,
        value: Any,
    ): ...

    def paint(
        self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        (check, value) = self._test_custom_paint(painter, option, index)
        if not check:
            return super().paint(painter, option, index)
        super().paint(painter, option, index)
        painter.save()
        self._do_custom_paint(painter, option, index, value)
        painter.restore()


class WrappingTextDelegate(CustomDisplayDelegate):
    """A lightweight delegate that wraps text without expensive size recalculation."""

    def __init__(self, parent: BECTableView | None = None, max_width: int = 300, margin: int = 6):
        super().__init__(parent)
        self._parent = parent
        self.max_width = max_width
        self.margin = margin
        self._cache = {}  # cache text metrics for performance
        self._wrapping_text_columns = None

    @property
    def wrapping_text_columns(self) -> List[int]:
        # Compute once, cache for later
        if self._wrapping_text_columns is None:
            self._wrapping_text_columns = []
            view = self._parent
            proxy: DeviceFilterProxyModel = self._parent.model()
            for col in range(proxy.columnCount()):
                delegate = view.itemDelegateForColumn(col)
                if isinstance(delegate, WrappingTextDelegate):
                    self._wrapping_text_columns.append(col)
        return self._wrapping_text_columns

    def _do_custom_paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QModelIndex,
        value: str,
    ):
        text = str(value)
        if not text:
            return
        painter.save()
        painter.setClipRect(option.rect)

        # Use cached layout if available
        cache_key = (text, option.rect.width())
        layout = self._cache.get(cache_key)
        if layout is None:
            layout = self._compute_layout(text, option)
            self._cache[cache_key] = layout

        # Draw text
        painter.setPen(option.palette.text().color())
        layout.draw(painter, option.rect.topLeft())
        painter.restore()

    def _compute_layout(
        self, text: str, option: QtWidgets.QStyleOptionViewItem
    ) -> QtGui.QTextLayout:
        """Compute and return the text layout for given text and option."""
        layout = self._get_layout(text, option.font)
        layout.beginLayout()
        height = 0
        max_lines = 100  # safety cap, should never be more than 100 lines..
        for _ in range(max_lines):
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(option.rect.width() - self.margin)
            line.setPosition(QtCore.QPointF(self.margin / 2, height))
            line_height = line.height()
            if line_height <= 0:
                break  # avoid negative or zero height lines to be added
            height += line_height
        layout.endLayout()
        return layout

    def _get_layout(self, text: str, font_option: QtGui.QFont) -> QtGui.QTextLayout:
        return QtGui.QTextLayout(text, font_option)

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QModelIndex) -> QtCore.QSize:
        """Return a cached or approximate height; avoids costly recomputation."""
        text = str(index.data(QtCore.Qt.DisplayRole) or "")
        view = self._parent
        view.initViewItemOption(option)
        if view.isColumnHidden(index.column()) or not view.isVisible() or not text:
            return QtCore.QSize(0, option.fontMetrics.height() + 2 * self.margin)

        # Use cache for consistent size computation
        cache_key = (text, self.max_width)
        if cache_key in self._cache:
            layout = self._cache[cache_key]
            height = 0
            for i in range(layout.lineCount()):
                height += layout.lineAt(i).height()
            return QtCore.QSize(self.max_width, int(height + self.margin))

        # Approximate without layout (fast path)
        metrics = option.fontMetrics
        pixel_width = max(self._parent.columnWidth(index.column()), 100)
        if pixel_width > 2000:  # safeguard against uninitialized columns, may return large values
            pixel_width = 100
        char_per_line = self.estimate_chars_per_line(text, option, pixel_width - 2 * self.margin)
        wrapped_lines = textwrap.wrap(text, width=char_per_line)
        lines = len(wrapped_lines)
        return QtCore.QSize(pixel_width, lines * (metrics.height()) + 2 * self.margin)

    def estimate_chars_per_line(
        self, text: str, option: QtWidgets.QStyleOptionViewItem, column_width: int
    ) -> int:
        """Estimate number of characters that fit in a line for given width."""
        metrics = option.fontMetrics
        elided = metrics.elidedText(text, Qt.ElideRight, column_width)
        return len(elided.rstrip("…"))

    @SafeSlot(int, int, int)
    @SafeSlot(int)
    def _on_section_resized(
        self, logical_index: int, old_size: int | None = None, new_size: int | None = None
    ):
        """Only update rows if a wrapped column was resized."""
        self._cache.clear()
        self._update_row_heights()

    def _update_row_heights(self):
        """Efficiently adjust row heights based on wrapped columns."""
        view = self._parent
        proxy = view.model()
        option = QtWidgets.QStyleOptionViewItem()
        view.initViewItemOption(option)
        for row in range(proxy.rowCount()):
            max_height = 18
            for column in self.wrapping_text_columns:
                index = proxy.index(row, column)
                delegate = view.itemDelegateForColumn(column)
                hint = delegate.sizeHint(option, index)
                max_height = max(max_height, hint.height())
            if view.rowHeight(row) != max_height:
                view.setRowHeight(row, max_height)


class CenterCheckBoxDelegate(CustomDisplayDelegate):
    """Custom checkbox delegate to center checkboxes in table cells."""

    _paint_test_role = USER_CHECK_DATA_ROLE

    def __init__(self, parent: BECTableView | None = None, colors: AccentColors | None = None):
        super().__init__(parent)
        colors: AccentColors = colors if colors else get_accent_colors()  # type: ignore
        _icon = partial(material_icon, size=(16, 16), color=colors.default, filled=True)
        self._icon_checked = _icon("check_box")
        self._icon_unchecked = _icon("check_box_outline_blank")

    def apply_theme(self, theme: str | None = None):
        colors = get_accent_colors()
        _icon = partial(material_icon, size=(16, 16), color=colors.default, filled=True)
        self._icon_checked = _icon("check_box")
        self._icon_unchecked = _icon("check_box_outline_blank")

    def _do_custom_paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QModelIndex,
        value: Literal[
            Qt.CheckState.Checked | Qt.CheckState.Unchecked | Qt.CheckState.PartiallyChecked
        ],
    ):
        pixmap = self._icon_checked if value == Qt.CheckState.Checked else self._icon_unchecked
        pix_rect = pixmap.rect()
        pix_rect.moveCenter(option.rect.center())
        painter.drawPixmap(pix_rect.topLeft(), pixmap)

    def editorEvent(
        self,
        event: QtCore.QEvent,
        model: QtCore.QSortFilterProxyModel,
        option: QtWidgets.QStyleOptionViewItem,
        index: QModelIndex,
    ):
        if event.type() != QtCore.QEvent.Type.MouseButtonRelease:
            return False
        current = model.data(index, USER_CHECK_DATA_ROLE)
        new_state = (
            Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
        )
        return model.setData(index, new_state, USER_CHECK_DATA_ROLE)


class DeviceValidatedDelegate(CustomDisplayDelegate):
    """Custom delegate for displaying validated device configurations."""

    def __init__(self, parent: BECTableView | None = None, colors: AccentColors | None = None):
        super().__init__(parent)
        colors = colors if colors else get_accent_colors()
        _icon = partial(material_icon, icon_name="circle", size=(12, 12), filled=True)
        self._icons = {
            ValidationStatus.PENDING: _icon(color=colors.default),
            ValidationStatus.VALID: _icon(color=colors.success),
            ValidationStatus.FAILED: _icon(color=colors.emergency),
        }

    def apply_theme(self, theme: str | None = None):
        colors = get_accent_colors()
        _icon = partial(material_icon, icon_name="circle", size=(12, 12), filled=True)
        self._icons = {
            ValidationStatus.PENDING: _icon(color=colors.default),
            ValidationStatus.VALID: _icon(color=colors.success),
            ValidationStatus.FAILED: _icon(color=colors.emergency),
        }

    def _do_custom_paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QModelIndex,
        value: Literal[0, 1, 2],
    ):
        """
        Paint the validation status icon centered in the cell.

        Args:
            painter (QtGui.QPainter): The painter object.
            option (QtWidgets.QStyleOptionViewItem): The style options for the item.
            index (QModelIndex): The model index of the item.
            value (Literal[0,1,2]): The validation status value, where 0=Pending, 1=Valid, 2=Failed.
                                    Relates to ValidationStatus enum.
        """
        if pixmap := self._icons.get(value):
            pix_rect = pixmap.rect()
            pix_rect.moveCenter(option.rect.center())
            painter.drawPixmap(pix_rect.topLeft(), pixmap)


class DeviceTableModel(QtCore.QAbstractTableModel):
    """
    Custom Device Table Model for managing device configurations.

    Sort logic is implemented directly on the data of the table view.
    """

    # tuple of list[dict[str, Any]] of configs which were added and bool True if added or False if removed
    configs_changed = QtCore.Signal(list, bool)

    def __init__(self, parent: DeviceTableModel | None = None):
        super().__init__(parent)
        self._device_config: list[dict[str, Any]] = []
        self._validation_status: dict[str, ValidationStatus] = {}
        # TODO 882 keep in sync with HEADERS_HELP_MD
        self.headers = [
            "status",
            "name",
            "deviceClass",
            "readoutPriority",
            "onFailure",
            "deviceTags",
            "description",
            "enabled",
            "readOnly",
            "softwareTrigger",
        ]
        self._checkable_columns_enabled = {"enabled": True, "readOnly": True}
        self._device_model_schema = Device.model_json_schema()

    ###############################################
    ########## Override custom Qt methods #########
    ###############################################

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QtCore.QModelIndex()) -> int:
        return len(self._device_config)

    def columnCount(
        self, parent: QModelIndex | QPersistentModelIndex = QtCore.QModelIndex()
    ) -> int:
        return len(self.headers)

    def headerData(self, section, orientation, role=int(Qt.ItemDataRole.DisplayRole)):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if section == 9:  # softwareTrigger
                return "softTrig"
            return self.headers[section]
        return None

    def get_row_data(self, index: QtCore.QModelIndex) -> dict:
        """Return the row data for the given index."""
        if not index.isValid():
            return {}
        return copy.deepcopy(self._device_config[index.row()])

    def data(self, index, role=int(Qt.ItemDataRole.DisplayRole)):
        """Return data for the given index and role."""
        if not index.isValid():
            return None
        row, col = index.row(), index.column()

        if col == 0 and role == Qt.ItemDataRole.DisplayRole:
            dev_name = self._device_config[row].get("name", "")
            return self._validation_status.get(dev_name, ValidationStatus.PENDING)

        key = self.headers[col]
        value = self._device_config[row].get(key, None)
        if value is None:
            value = (
                self._device_model_schema.get("properties", {}).get(key, {}).get("default", None)
            )

        if role == Qt.ItemDataRole.DisplayRole:
            if key in ("enabled", "readOnly", "softwareTrigger"):
                return bool(value)
            if key == "deviceTags":
                return ", ".join(str(tag) for tag in value) if value else ""
            if key == "deviceClass":
                return str(value).split(".")[-1]
            return str(value) if value is not None else ""
        if role == USER_CHECK_DATA_ROLE and key in ("enabled", "readOnly", "softwareTrigger"):
            return Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if key in ("enabled", "readOnly", "softwareTrigger"):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.FontRole:
            font = QtGui.QFont()
            return font
        return None

    def flags(self, index):
        """Flags for the table model."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        key = self.headers[index.column()]

        base_flags = super().flags(index) | (
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDropEnabled
        )

        if key in ("enabled", "readOnly", "softwareTrigger"):
            if self._checkable_columns_enabled.get(key, True):
                return base_flags | Qt.ItemFlag.ItemIsUserCheckable
            else:
                return base_flags  # disable editing but still visible
        return base_flags

    def setData(self, index, value, role=int(Qt.ItemDataRole.EditRole)) -> bool:
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
        if key in ("enabled", "readOnly", "softwareTrigger") and role == USER_CHECK_DATA_ROLE:
            if not self._checkable_columns_enabled.get(key, True):
                return False  # ignore changes if column is disabled
            self._device_config[index.row()][key] = value == Qt.CheckState.Checked
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, USER_CHECK_DATA_ROLE])
            return True
        return False

    ####################################
    ############ Drag and Drop #########
    ####################################

    def mimeTypes(self) -> List[str]:
        return [*super().mimeTypes(), MIME_DEVICE_CONFIG]

    def supportedDropActions(self):
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction

    def dropMimeData(self, data, action, row, column, parent):
        if action not in [Qt.DropAction.CopyAction, Qt.DropAction.MoveAction]:
            return False
        if (raw_data := data.data(MIME_DEVICE_CONFIG)) is None:
            return False
        self.add_device_configs(json.loads(raw_data.toStdString()))
        return True

    ####################################
    ############ Public methods ########
    ####################################

    def get_device_config(self) -> list[dict[str, Any]]:
        """Method to get the device configuration."""
        return copy.deepcopy(self._device_config)

    def device_names(self, configs: _DeviceCfgIter | None = None) -> set[str]:
        _configs = self._device_config if configs is None else configs
        return set(cfg.get("name") for cfg in _configs if cfg.get("name") is not None)  # type: ignore

    def _name_exists_in_config(self, name: str, exists: bool):
        if (name in self.device_names()) == exists:
            return True
        return not exists

    def add_device_configs(self, device_configs: _DeviceCfgIter):
        """
        Add devices to the model.

        Args:
            device_configs (_DeviceCfgList): An iterable of device configurations to add.
        """
        already_in_list = []
        added_configs = []
        for cfg in device_configs:
            if self._name_exists_in_config(name := cfg.get("name", "<not found>"), True):
                logger.warning(f"Device {name} is already in the config. It will be updated.")
                self.remove_configs_by_name([name])
            row = len(self._device_config)
            self.beginInsertRows(QtCore.QModelIndex(), row, row)
            self._device_config.append(copy.deepcopy(cfg))
            added_configs.append(cfg)
            self.endInsertRows()
        self.configs_changed.emit(device_configs, True)

    def remove_device_configs(self, device_configs: _DeviceCfgIter):
        """
        Remove devices from the model.

        Args:
            device_configs (_DeviceCfgList): An iterable of device configurations to remove.
        """
        removed = []
        for cfg in device_configs:
            if cfg not in self._device_config:
                logger.warning(f"Device {cfg.get('name')} does not exist in the model.")
                continue
            with self._remove_row(self._device_config.index(cfg)) as row:
                removed.append(self._device_config.pop(row))
        self.configs_changed.emit(removed, False)

    def remove_configs_by_name(self, names: Iterable[str]):
        configs = filter(lambda cfg: cfg is not None, (self.get_by_name(name) for name in names))
        self.remove_device_configs(configs)  # type: ignore # Nones are filtered

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        for cfg in self._device_config:
            if cfg.get("name") == name:
                return cfg
        logger.warning(f"Device {name} does not exist in the model.")
        return None

    @contextmanager
    def _remove_row(self, row: int):
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        try:
            yield row
        finally:
            self.endRemoveRows()

    def set_device_config(self, device_configs: _DeviceCfgIter):
        """
        Replace the device config.

        Args:
            device_config (Iterable[dict[str,Any]]): An iterable of device configurations to set.
        """
        diff_names = self.device_names(device_configs) - self.device_names()
        diff = [cfg for cfg in self._device_config if cfg.get("name") in diff_names]
        self.beginResetModel()
        self._device_config = copy.deepcopy(list(device_configs))
        self.endResetModel()
        self.configs_changed.emit(diff, False)
        self.configs_changed.emit(device_configs, True)

    def clear_table(self):
        """
        Clear the table.
        """
        self.beginResetModel()
        self._device_config.clear()
        self.endResetModel()
        self.configs_changed.emit(self._device_config, False)

    def update_validation_status(self, device_name: str, status: int | ValidationStatus):
        """
        Handle device status changes.

        Args:
            device_name (str): The name of the device.
            status (int): The new status of the device.
        """
        if isinstance(status, int):
            status = ValidationStatus(status)
        if device_name not in self.device_names():
            logger.warning(f"Device {device_name} not found in table")
            return
        self._validation_status[device_name] = status
        row = None
        for ii, item in enumerate(self._device_config):
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
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])

    def validation_statuses(self):
        return copy.deepcopy(self._validation_status)


class BECTableView(QtWidgets.QTableView):
    """Table View with custom keyPressEvent to delete rows with backspace or delete key"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtWidgets.QTableView.DragDropMode.DropOnly)

    def model(self) -> DeviceFilterProxyModel:
        return super().model()  # type: ignore

    def keyPressEvent(self, event) -> None:
        """
        Delete selected rows with backspace or delete key

        Args:
            event: keyPressEvent
        """
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            return self.delete_selected()
        return super().keyPressEvent(event)

    def contains_invalid_devices(self):
        return ValidationStatus.FAILED in self.model().sourceModel().validation_statuses().values()

    def all_configs(self):
        return self.model().sourceModel().get_device_config()

    def selected_configs(self):
        return self.model().get_row_data(self.selectionModel().selectedRows())

    def delete_selected(self):
        proxy_indexes = self.selectionModel().selectedRows()
        if not proxy_indexes:
            return
        model: DeviceTableModel = self.model().sourceModel()  # access underlying model
        self._confirm_and_remove_rows(model, self._get_source_rows(proxy_indexes))

    def _get_source_rows(self, proxy_indexes: list[QModelIndex]) -> list[QModelIndex]:
        """
        Map proxy model indices to source model row indices.

        Args:
            proxy_indexes (list[QModelIndex]): List of proxy model indices.

        Returns:
            list[int]: List of source model row indices.
        """
        proxy_rows = sorted({idx for idx in proxy_indexes}, reverse=True)
        return list(set(self.model().mapToSource(idx) for idx in proxy_rows))

    def _confirm_and_remove_rows(
        self, model: DeviceTableModel, source_rows: list[QModelIndex]
    ) -> bool:
        """
        Prompt the user to confirm removal of rows and remove them from the model if accepted.

        Returns True if rows were removed, False otherwise.
        """
        configs = [model.get_row_data(r) for r in sorted(source_rows, key=lambda r: r.row())]
        names = [cfg.get("name", "<unknown>") for cfg in configs]

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Confirm device removal")
        msg.setText(
            f"Remove device '{names[0]}'?" if len(names) == 1 else f"Remove {len(names)} devices?"
        )
        separator = "\n" if len(names) < 12 else ", "
        msg.setInformativeText("Selected devices: \n" + separator.join(names))
        msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)

        res = msg.exec_()
        if res == QMessageBox.StandardButton.Ok:
            model.remove_device_configs(configs)
            return True
        return False


class DeviceFilterProxyModel(QtCore.QSortFilterProxyModel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hidden_rows = set()
        self._filter_text = ""
        self._enable_fuzzy = True
        self._filter_columns = [1, 2, 6]  # name, deviceClass and description for search
        self._status_order = {
            ValidationStatus.VALID: 0,
            ValidationStatus.PENDING: 1,
            ValidationStatus.FAILED: 2,
        }

    def get_row_data(self, rows: Iterable[QModelIndex]) -> Iterable[dict[str, Any]]:
        return (self.sourceModel().get_row_data(self.mapToSource(idx)) for idx in rows)

    def sourceModel(self) -> DeviceTableModel:
        return super().sourceModel()  # type: ignore

    def hide_rows(self, row_indices: list[int]):
        """
        Hide specific rows in the model.

        Args:
            row_indices (list[int]): List of row indices to hide.
        """
        self._hidden_rows.update(row_indices)
        self.invalidateFilter()

    def lessThan(self, left, right):
        """Add custom sorting for the status column"""
        if left.column() != 0 or right.column() != 0:
            return super().lessThan(left, right)
        left_data = self.sourceModel().data(left, Qt.ItemDataRole.DisplayRole)
        right_data = self.sourceModel().data(right, Qt.ItemDataRole.DisplayRole)
        return self._status_order.get(left_data, 99) < self._status_order.get(right_data, 99)

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
            data = str(model.data(index, Qt.ItemDataRole.DisplayRole) or "")
            if self._enable_fuzzy is True:
                match_ratio = fuzz.partial_ratio(self._filter_text.lower(), data.lower())
                if match_ratio >= FUZZY_SEARCH_THRESHOLD:
                    return True
            else:
                if text in data.lower():
                    return True
        return False

    def flags(self, index):
        return super().flags(index) | Qt.ItemFlag.ItemIsDropEnabled

    def supportedDropActions(self):
        return self.sourceModel().supportedDropActions()

    def mimeTypes(self):
        return self.sourceModel().mimeTypes()

    def dropMimeData(self, data, action, row, column, parent):
        sp = self.mapToSource(parent) if parent.isValid() else QtCore.QModelIndex()
        return self.sourceModel().dropMimeData(data, action, row, column, sp)


class DeviceTableView(BECWidget, QtWidgets.QWidget):
    """Device Table View for the device manager."""

    # Selected device configuration list[dict[str, Any]]
    selected_devices = QtCore.Signal(list)  # type: ignore
    # tuple of list[dict[str, Any]] of configs which were added and bool True if added or False if removed
    device_configs_changed = QtCore.Signal(list, bool)  # type: ignore

    RPC = False
    PLUGIN = False

    def __init__(self, parent=None, client=None, shared_selection_signal=SharedSelectionSignal()):
        super().__init__(client=client, parent=parent, theme_update=True)

        self._shared_selection_signal = shared_selection_signal
        self._shared_selection_uuid = str(uuid4())
        self._shared_selection_signal.proc.connect(self._handle_shared_selection_signal)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self.setLayout(self._layout)

        # Setup table view
        self._setup_table_view()
        # Setup search view, needs table proxy to be iniditate
        self._setup_search()
        # Add widgets to main layout
        self._layout.addLayout(self.search_controls)
        self._layout.addWidget(self.table)

        # Connect signals
        self._model.configs_changed.connect(self.device_configs_changed.emit)

    def get_help_md(self) -> str:
        """
        Generate Markdown help for a cell or header.
        """
        pos = self.table.mapFromGlobal(QtGui.QCursor.pos())
        model: DeviceTableModel = self._model  # access underlying model
        index = self.table.indexAt(pos)
        if index.isValid():
            column = index.column()
            label = model.headerData(column, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole)
            if label == "softTrig":
                label = "softwareTrigger"
            return HEADERS_HELP_MD.get(label, "")
        return ""

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
        QTimer.singleShot(0, lambda: self.fuzzy_is_disabled.stateChanged.emit(0))

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
        self.tool_tip_delegate = DictToolTipDelegate(self.table)
        self.validated_delegate = DeviceValidatedDelegate(self.table, colors=colors)
        self.wrapped_delegate = WrappingTextDelegate(self.table, max_width=300)
        # Add resize handling for wrapped delegate
        header = self.table.horizontalHeader()

        self.table.setItemDelegateForColumn(0, self.validated_delegate)  # status
        self.table.setItemDelegateForColumn(1, self.tool_tip_delegate)  # name
        self.table.setItemDelegateForColumn(2, self.tool_tip_delegate)  # deviceClass
        self.table.setItemDelegateForColumn(3, self.tool_tip_delegate)  # readoutPriority
        self.table.setItemDelegateForColumn(4, self.tool_tip_delegate)  # onFailure
        self.table.setItemDelegateForColumn(5, self.wrapped_delegate)  # deviceTags
        self.table.setItemDelegateForColumn(6, self.wrapped_delegate)  # description
        self.table.setItemDelegateForColumn(7, self.checkbox_delegate)  # enabled
        self.table.setItemDelegateForColumn(8, self.checkbox_delegate)  # readOnly
        self.table.setItemDelegateForColumn(9, self.checkbox_delegate)  # softwareTrigger

        # Disable wrapping, use eliding, and smooth scrolling
        self.table.setWordWrap(False)
        self.table.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        self.table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)

        # Column resize policies
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # ValidationStatus
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)  # name
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)  # deviceClass
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)  # readoutPriority
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)  # onFailure
        header.setSectionResizeMode(
            5, QHeaderView.ResizeMode.Interactive
        )  # deviceTags: expand to fill
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # descript: expand to fill
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)  # enabled
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)  # readOnly
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)  # softwareTrigger

        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(5, 200)
        self.table.setColumnWidth(6, 200)
        self.table.setColumnWidth(7, 70)
        self.table.setColumnWidth(8, 70)
        self.table.setColumnWidth(9, 70)

        # Ensure column widths stay fixed
        header.setMinimumSectionSize(25)
        header.setDefaultSectionSize(90)
        header.setStretchLastSection(False)

        # Resize policy for wrapped text delegate
        self._resize_proxy = BECSignalProxy(
            header.sectionResized,
            rateLimit=25,
            slot=self.wrapped_delegate._on_section_resized,
            timeout=1.0,
        )

        # Selection behavior
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # Connect to selection model to get selection changes
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.horizontalHeader().setHighlightSections(False)

        # Connect model signals to autosize request
        self._model.rowsInserted.connect(self._request_autosize_columns)
        self._model.modelReset.connect(self._request_autosize_columns)
        self._model.dataChanged.connect(self._request_autosize_columns)

    def remove_selected_rows(self):
        self.table.delete_selected()

    def get_device_config(self) -> list[dict[str, Any]]:
        """Get the device config."""
        return self._model.get_device_config()

    def apply_theme(self, theme: str | None = None):
        self.checkbox_delegate.apply_theme(theme)
        self.validated_delegate.apply_theme(theme)

    ######################################
    ########### Slot API #################
    ######################################

    def _request_autosize_columns(self, *args):
        if not hasattr(self, "_autosize_timer"):
            self._autosize_timer = QtCore.QTimer(self)
            self._autosize_timer.setSingleShot(True)
            self._autosize_timer.timeout.connect(self._autosize_columns)
        self._autosize_timer.start(0)

    @SafeSlot()
    def _autosize_columns(self):
        if self._model.rowCount() == 0:
            return
        for col in (1, 2, 3):
            self.table.resizeColumnToContents(col)

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
        if not (selected_configs := list(self.table.selected_configs())):
            return
        self.selected_devices.emit(selected_configs)

    ######################################
    ##### Ext.  Slot API #################
    ######################################

    @SafeSlot(list)
    def set_device_config(self, device_configs: _DeviceCfgIter):
        """
        Set the device config.

        Args:
            config (Iterable[str,dict]): The device config to set.
        """
        self._model.set_device_config(device_configs)

    @SafeSlot()
    def clear_device_configs(self):
        """Clear the device configs."""
        self._model.clear_table()

    @SafeSlot(list)
    def add_device_configs(self, device_configs: _DeviceCfgIter):
        """
        Add devices to the config.

        Args:
            device_configs (dict[str, dict]): The device configs to add.
        """
        self._model.add_device_configs(device_configs)

    @SafeSlot(list)
    def remove_device_configs(self, device_configs: _DeviceCfgIter):
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
        self._model.remove_configs_by_name([device_name])

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
        names = list(window._model.device_names())
        for name in names:
            window.update_device_validation(
                name, ValidationStatus.VALID if np.random.rand() > 0.5 else ValidationStatus.FAILED
            )

    button.clicked.connect(_button_clicked)
    # pylint: disable=protected-access
    config = window.client.device_manager._get_redis_device_config()
    # names = [cfg.pop("name") for cfg in config]
    # config_dict = {name: cfg for name, cfg in zip(names, config)}
    window.set_device_config(config)
    widget.show()
    sys.exit(app.exec_())
