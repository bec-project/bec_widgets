from typing import Any, Callable, Generator, Iterable, TypeVar

from PySide6.QtCore import QObject, Signal
from qtpy.QtWidgets import QListWidgetItem

from bec_widgets.widgets.control.device_manager.components.constants import SORT_KEY_ROLE

_T = TypeVar("_T")
_RT = TypeVar("_RT")


def yield_only_passing(fn: Callable[[_T], _RT], vals: Iterable[_T]) -> Generator[_RT, Any, None]:
    for v in vals:
        try:
            yield fn(v)
        except BaseException:
            pass


class SortableQListWidgetItem(QListWidgetItem):
    """Store a sorting string key with .setData(SORT_KEY_ROLE, key) to be able to sort a list with \
    custom widgets and this item."""

    def __gt__(self, other):
        if (self_key := self.data(SORT_KEY_ROLE)) is None or (
            other_key := other.data(SORT_KEY_ROLE)
        ) is None:
            return False
        return self_key.lower() > other_key.lower()

    def __lt__(self, other):
        if (self_key := self.data(SORT_KEY_ROLE)) is None or (
            other_key := other.data(SORT_KEY_ROLE)
        ) is None:
            return False
        return self_key.lower() < other_key.lower()


class SharedSelectionSignal(QObject):
    proc = Signal(str)
