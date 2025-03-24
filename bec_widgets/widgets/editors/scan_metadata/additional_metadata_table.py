from __future__ import annotations

from typing import Any

from qtpy.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal  # type: ignore
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot


class AdditionalMetadataTableModel(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data: list[list[str]] = data
        self._disallowed_keys: list[str] = []

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
            if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
                return str(self._data[index.row()][index.column()])

    def setData(self, index, value, role):
        if role == Qt.ItemDataRole.EditRole:
            if value in self._disallowed_keys or value in self._other_keys(index.row()):
                return False
            self._data[index.row()][index.column()] = str(value)
            return True
        return False

    def update_disallowed_keys(self, keys: list[str]):
        self._disallowed_keys = keys
        for i, item in enumerate(self._data):
            if item[0] in self._disallowed_keys:
                self._data[i][0] = ""
                self.dataChanged.emit(self.index(i, 0), self.index(i, 0))

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

    @SafeSlot(list)
    def delete_rows(self, rows: list[int]):
        # delete from the end so indices stay correct
        for row in sorted(rows, reverse=True):
            self.removeRows(row, 1, QModelIndex())

    def dump_dict(self):
        if self._data == [[]]:
            return {}
        return dict(self._data)


class AdditionalMetadataTable(QWidget):

    delete_rows = Signal(list)

    def __init__(self, initial_data: list[list[str]]):
        super().__init__()

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)
        self._table_model = AdditionalMetadataTableModel(initial_data)
        self._table_view = QTreeView()
        self._table_view.setModel(self._table_model)
        self._table_view.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        )
        self._table_view.setAlternatingRowColors(True)
        self._layout.addWidget(self._table_view)

        self._buttons = QVBoxLayout()
        self._layout.addLayout(self._buttons)
        self._add_button = QPushButton("+")
        self._add_button.setToolTip("add a new row")
        self._remove_button = QPushButton("-")
        self._remove_button.setToolTip("delete rows containing any selected cells")
        self._buttons.addWidget(self._add_button)
        self._buttons.addWidget(self._remove_button)
        self._add_button.clicked.connect(self._table_model.add_row)
        self._remove_button.clicked.connect(self.delete_selected_rows)
        self.delete_rows.connect(self._table_model.delete_rows)

    def delete_selected_rows(self):
        cells: list[QModelIndex] = self._table_view.selectionModel().selectedIndexes()
        row_indices = list({r.row() for r in cells})
        if row_indices:
            self.delete_rows.emit(row_indices)

    def dump_dict(self):
        return self._table_model.dump_dict()

    def update_disallowed_keys(self, keys: list[str]):
        self._table_model.update_disallowed_keys(keys)


if __name__ == "__main__":  # pragma: no cover
    from bec_widgets.utils.colors import set_theme

    app = QApplication([])
    set_theme("dark")

    window = AdditionalMetadataTable([["key1", "value1"], ["key2", "value2"], ["key3", "value3"]])
    window.show()
    app.exec()
