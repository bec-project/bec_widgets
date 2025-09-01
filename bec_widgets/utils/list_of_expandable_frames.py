import re
from functools import partial
from re import Pattern
from typing import Generic, Iterable, NamedTuple, TypeVar

from bec_lib.logger import bec_logger
from more_itertools import consume
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QListWidgetItem, QWidget
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import QListWidget

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.expandable_frame import ExpandableGroupFrame

logger = bec_logger.logger

_SORT_KEY_ROLE = 117

_EF = TypeVar("_EF", bound=ExpandableGroupFrame)


class ListOfExpandableFrames(QListWidget, Generic[_EF]):
    def __init__(
        self, /, parent: QWidget | None = None, item_class: type[_EF] = ExpandableGroupFrame
    ) -> None:
        super().__init__(parent)
        _Items = NamedTuple("_Items", (("item", QListWidgetItem), ("widget", _EF)))
        self.item_tuple = _Items
        self._item_class = item_class
        self._item_dict: dict[str, _Items] = {}

    def __contains__(self, id: str):
        return id in self._item_dict

    def clear(self) -> None:
        self._item_dict = {}
        return super().clear()

    def add_item(self, id: str, *args, **kwargs) -> _EF:
        """Adds the specified type of widget as an item. args and kwargs are passed to the constructor.

        Args:
            id (str): the key under which to store the list item in the internal dict

        Returns:
            The widget created in the addition process
        """

        def _remove_item(item: QListWidgetItem):
            self.takeItem(self.row(item))
            del self._item_dict[id]
            self.sortItems()

        def _updatesize(item: QListWidgetItem, item_widget: _EF):
            item_widget.adjustSize()
            item.setSizeHint(QSize(item_widget.width(), item_widget.height()))

        item = QListWidgetItem(self)
        item.setData(_SORT_KEY_ROLE, id)  # used for sorting

        item_widget = self._item_class(*args, **kwargs)
        item_widget.expansion_state_changed.connect(partial(_updatesize, item, item_widget))
        item_widget.imminent_deletion.connect(partial(_remove_item, item))
        item_widget.broadcast_size_hint.connect(item.setSizeHint)

        self.addItem(item)
        self.setItemWidget(item, item_widget)
        self._item_dict[id] = self.item_tuple(item, item_widget)

        item.setSizeHint(item_widget.sizeHint())
        return item_widget

    def sort_by_key(self, role=_SORT_KEY_ROLE, order=Qt.SortOrder.AscendingOrder):
        items = [self.takeItem(0) for i in range(self.count())]
        items.sort(key=lambda it: it.data(role), reverse=(order == Qt.SortOrder.DescendingOrder))

        for it in items:
            self.addItem(it)
            # reattach its custom widget
            widget = self.itemWidget(it)
            if widget:
                self.setItemWidget(it, widget)

    def item_widget_pairs(self):
        return self._item_dict.values()

    def widgets(self):
        return (i.widget for i in self._item_dict.values())

    def get_item_widget(self, id: str):
        if (item := self._item_dict.get(id)) is None:
            return None
        return item

    def set_hidden_pattern(self, pattern: Pattern):
        self.hide_all()
        self._set_hidden(filter(pattern.search, self._item_dict.keys()), False)

    def set_hidden(self, ids: Iterable[str]):
        self._set_hidden(ids, True)

    def _set_hidden(self, ids: Iterable[str], hidden: bool):
        for id in ids:
            if (_item := self._item_dict.get(id)) is not None:
                _item.item.setHidden(hidden)
                _item.widget.setHidden(hidden)
            else:
                logger.warning(
                    f"List {self.__qualname__} does not have an item with ID {id} to hide!"
                )
        self.sortItems()

    def hide_all(self):
        self.set_hidden_state_on_all(True)

    def unhide_all(self):
        self.set_hidden_state_on_all(False)

    def set_hidden_state_on_all(self, hidden: bool):
        for _item in self._item_dict.values():
            _item.item.setHidden(hidden)
            _item.widget.setHidden(hidden)
        self.sortItems()

    @SafeSlot(str)
    def update_filter(self, value: str):
        if value == "":
            return self.unhide_all()
        try:
            self.set_hidden_pattern(re.compile(value, re.IGNORECASE))
        except Exception:
            self.unhide_all()
