from qtpy.QtWidgets import QListWidgetItem

from bec_widgets.widgets.control.device_manager.components.constants import SORT_KEY_ROLE


class SortableQListWidgetItem(QListWidgetItem):
    """Store a sorting string key with .setData(SORT_KEY_ROLE, key) to be able to sort a list with
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
