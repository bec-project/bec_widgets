from __future__ import annotations

from typing import Any

from qtpy import QtWidgets
from qtpy.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal  # type: ignore
from qtpy.QtGui import QFontMetrics
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeProperty, SafeSlot

_NOT_SET = object()


class DictBackedTableModel(QAbstractTableModel):
    def __init__(self, data):
        """A model to go with DictBackedTable, which represents key-value pairs
        to be displayed in a TreeWidget.

        Args:
            data (list[list[str]]): list of key-value pairs to initialise with"""
        super().__init__()
        self._data: list[list[str]] = data
        self._default = _NOT_SET
        self._disallowed_keys: list[str] = []

    # pylint: disable=missing-function-docstring
    # see QAbstractTableModel documentation for these methods

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole()
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return "Key" if section == 0 else "Value"
        return super().headerData(section, orientation, role)

    def rowCount(self, index: QModelIndex = QModelIndex()):
        return 0 if index.isValid() else len(self._data)

    def columnCount(self, index: QModelIndex = QModelIndex()):
        return 0 if index.isValid() else 2

    def data(self, index, role=Qt.ItemDataRole):
        if index.isValid():
            if role in [
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.EditRole,
                Qt.ItemDataRole.ToolTipRole,
            ]:
                try:
                    return str(self._data[index.row()][index.column()])
                except IndexError:
                    return None

    def setData(self, index, value, role):
        if role == Qt.ItemDataRole.EditRole:
            if value in self._disallowed_keys or value in self._other_keys(index.row()):
                return False
            self._data[index.row()][index.column()] = str(value)
            self.dataChanged.emit(index, index)
            return True
        return False

    def replaceData(self, data: dict):
        self.delete_rows(list(range(len(self._data))))
        self.resetInternalData()
        self._data = [[str(k), str(v)] for k, v in data.items()]
        self.dataChanged.emit(self.index(0, 0), self.index(len(self._data), 1))

    def update_disallowed_keys(self, keys: list[str]):
        """Set the list of keys which may not be used.

        Args:
            keys (list[str]): list of keys which are forbidden."""
        self._disallowed_keys = keys
        for i, item in enumerate(self._data):
            if item[0] in self._disallowed_keys:
                self._data[i][0] = ""
                self.dataChanged.emit(self.index(i, 0), self.index(i, 1))

    def _other_keys(self, row: int):
        return [r[0] for r in self._data[:row] + self._data[row + 1 :]]

    def flags(self, _):
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable

    def insertRows(self, row, number, index):
        """We only support adding one at a time for now"""
        if row != self.rowCount() or number != 1:
            return False
        self.beginInsertRows(QModelIndex(), 0, 0)
        self._data.append(["", ""])
        self.endInsertRows()
        return True

    def removeRows(self, row, number, index):
        """This can only be consecutive, so instead of trying to be clever, only support removing one at a time"""
        if number != 1:
            return False
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._data[row]
        self.endRemoveRows()
        return True

    @SafeSlot()
    def add_row(self):
        self.insertRow(self.rowCount())
        self.dataChanged.emit(self.index(self.rowCount(), 0), self.index(self.rowCount(), 1), 0)

    @SafeSlot(list)
    def delete_rows(self, rows: list[int]):
        # delete from the end so indices stay correct
        for row in sorted(rows, reverse=True):
            self.dataChanged.emit(self.index(row, 0), self.index(row, 1), 0)
            self.removeRows(row, 1, QModelIndex())

    def set_default(self, value: dict | None):
        self._default = value

    def dump_dict(self):
        if self._data in [[], [[]], [["", ""]]]:
            if self._default is not _NOT_SET:
                return self._default
            return {}
        return dict(self._data)

    def length(self):
        return len(self._data)


class DictBackedTable(QWidget):
    delete_rows = Signal(list)
    data_changed = Signal(dict)

    def __init__(
        self,
        parent: QWidget | None = None,
        initial_data: list[list[str]] = [],
        autoscale_to_data: bool = True,
    ):
        """Widget which uses a DictBackedTableModel to display an editable table
        which can be extracted as a dict.

        Args:
            initial_data (list[list[str]]): list of key-value pairs to initialise with
        """
        super().__init__(parent)

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._table_model = DictBackedTableModel(initial_data)
        self._table_view = QTreeView()

        self._table_view.setModel(self._table_model)
        self._min_lines = 3
        self.set_height_in_lines(len(initial_data))
        self._table_view.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )
        self._table_view.setAlternatingRowColors(True)
        self._table_view.setUniformRowHeights(True)
        self._table_view.setWordWrap(False)
        self._table_view.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self._table_view.header().setSectionResizeMode(5, QtWidgets.QHeaderView.Stretch)
        self.autoscale = autoscale_to_data
        if self.autoscale:
            self.data_changed.connect(self.scale_to_data)
        self._layout.addWidget(self._table_view)

        self._button_holder = QWidget()
        self._buttons = QVBoxLayout()
        self._button_holder.setLayout(self._buttons)
        self._layout.addWidget(self._button_holder)
        self._add_button = QPushButton("+")
        self._add_button.setToolTip("add a new row")
        self._remove_button = QPushButton("-")
        self._remove_button.setToolTip("delete rows containing any selected cells")
        self._buttons.addWidget(self._add_button)
        self._buttons.addWidget(self._remove_button)
        self._add_button.clicked.connect(self._table_model.add_row)
        self._remove_button.clicked.connect(self.delete_selected_rows)
        self.delete_rows.connect(self._table_model.delete_rows)

        self._table_model.dataChanged.connect(lambda *_: self.data_changed.emit(self.dump_dict()))

    def set_default(self, value: dict | None):
        self._table_model.set_default(value)

    def set_button_visibility(self, value: bool):
        self._button_holder.setVisible(value)

    @SafeSlot()
    def clear(self):
        self._table_model.replaceData({})

    def replace_data(self, data: dict | None):
        self._table_model.replaceData(data or {})

    def delete_selected_rows(self):
        """Delete rows which are part of the selection model"""
        cells: list[QModelIndex] = self._table_view.selectionModel().selectedIndexes()
        row_indices = list({r.row() for r in cells})
        if row_indices:
            self.delete_rows.emit(row_indices)

    def dump_dict(self):
        """Get the current content of the table as a dict"""
        return self._table_model.dump_dict()

    def update_disallowed_keys(self, keys: list[str]):
        """Set the list of keys which may not be used.

        Args:
            keys (list[str]): list of keys which are forbidden."""
        self._table_model.update_disallowed_keys(keys)

    def set_height_in_lines(self, lines: int):
        self._table_view.setMaximumHeight(
            int(QFontMetrics(self._table_view.font()).height() * max(lines + 2, self._min_lines))
        )

    @SafeSlot()
    @SafeSlot(dict)
    def scale_to_data(self, *_):
        self.set_height_in_lines(self._table_model.length())

    @SafeProperty(bool)
    def autoscale(self):  # type: ignore
        return self._autoscale

    @autoscale.setter
    def autoscale(self, autoscale: bool):
        self._autoscale = autoscale
        if self._autoscale:
            self.scale_to_data()
            self.data_changed.connect(self.scale_to_data)
        else:
            self.data_changed.disconnect(self.scale_to_data)


if __name__ == "__main__":  # pragma: no cover
    from bec_widgets.utils.colors import set_theme

    app = QApplication([])
    set_theme("dark")

    window = DictBackedTable(None, [["key1", "value1"], ["key2", "value2"], ["key3", "value3"]])
    window.show()
    app.exec()
