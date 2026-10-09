"""A small list model that feeds lists of dictionaries to QML views."""

from __future__ import annotations

from typing import Any, Sequence

from qtpy.QtCore import Property, QAbstractListModel, QByteArray, QModelIndex, Qt, Signal


class DictListModel(QAbstractListModel):
    """List model whose rows are plain dictionaries with a fixed set of keys.

    Each key becomes a QML role. :meth:`set_items` updates rows in place when the row count is
    unchanged, so QML delegates are kept alive and ``Behavior`` animations run on value changes
    instead of the delegates being rebuilt.

    Args:
        roles(Sequence[str]): Keys of the row dictionaries exposed as roles.
        parent: Parent QObject.
    """

    count_changed = Signal()

    def __init__(self, roles: Sequence[str], parent=None):
        super().__init__(parent)
        self._keys = list(roles)
        self._roles = {Qt.ItemDataRole.UserRole + 1 + i: key for i, key in enumerate(self._keys)}
        self._items: list[dict[str, Any]] = []

    # pylint: disable=invalid-name
    def roleNames(self) -> dict[int, QByteArray]:
        return {role: QByteArray(key.encode()) for role, key in self._roles.items()}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        key = self._roles.get(role)
        if key is None:
            return None
        return self._items[index.row()].get(key)

    @property
    def items(self) -> list[dict[str, Any]]:
        """Copy of the current rows."""
        return [dict(item) for item in self._items]

    def set_items(self, items: Sequence[dict[str, Any]]) -> None:
        """Replace the rows, reusing existing rows where possible.

        Args:
            items(Sequence[dict]): New rows.
        """
        items = [dict(item) for item in items]
        old_count = len(self._items)
        new_count = len(items)
        common = min(old_count, new_count)
        for row in range(common):
            changed = [
                role
                for role, key in self._roles.items()
                if self._items[row].get(key) != items[row].get(key)
            ]
            self._items[row] = items[row]
            if changed:
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, changed)
        if new_count > old_count:
            self.beginInsertRows(QModelIndex(), old_count, new_count - 1)
            self._items.extend(items[old_count:])
            self.endInsertRows()
        elif new_count < old_count:
            self.beginRemoveRows(QModelIndex(), new_count, old_count - 1)
            del self._items[new_count:]
            self.endRemoveRows()
        if new_count != old_count:
            self.count_changed.emit()

    count = Property(int, lambda self: len(self._items), notify=count_changed)
