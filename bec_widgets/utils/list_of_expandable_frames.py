from functools import partial
from typing import Generic, Iterable, NamedTuple, TypeVar

from bec_lib.logger import bec_logger
from PySide6.QtWidgets import QListWidgetItem, QWidget
from qtpy.QtCore import QSize
from qtpy.QtWidgets import QListWidget

from bec_widgets.utils.expandable_frame import ExpandableGroupFrame

logger = bec_logger.logger

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
        item_widget = self._item_class(*args, **kwargs)

        item_widget.expansion_state_changed.connect(partial(_updatesize, item, item_widget))
        item_widget.imminent_deletion.connect(partial(_remove_item, item))
        item_widget.broadcast_size_hint.connect(item.setSizeHint)

        self.setItemWidget(item, item_widget)
        self.addItem(item)
        self._item_dict[id] = self.item_tuple(item, item_widget)

        item.setSizeHint(item_widget.sizeHint())
        return item_widget

    def get_item_widget(self, id: str):
        if (item := self._item_dict.get(id)) is None:
            return None
        return item

    def set_hidden(self, ids: Iterable[str]):
        for id in ids:
            if (_item := self._item_dict.get(id)) is not None:
                _item.widget.setHidden(True)
            else:
                logger.warning(
                    f"List {self.__qualname__} does not have an item with ID {id} to hide!"
                )

    def unhide_all(self):
        map(lambda i: i.widget.setHidden(False), self._item_dict.values())
