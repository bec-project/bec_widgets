from bec_lib.logger import bec_logger
from qtpy.QtWidgets import QListWidget, QListWidgetItem, QWidget

logger = bec_logger.logger


class BECList(QListWidget):
    """List Widget that manages ListWidgetItems with associated widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widget_map: dict[str, tuple[QListWidgetItem, QWidget]] = {}

    def __contains__(self, key: str) -> bool:
        return key in self._widget_map

    def add_widget_item(self, key: str, widget: QWidget):
        """
        Add a widget to the list, mapping is associated with the given key.

        Args:
            key (str): Key to associate with the widget.
            widget (QWidget): Widget to add to the list.
        """
        if key in self._widget_map:
            self.remove_widget_item(key)

        item = QListWidgetItem()
        item.setSizeHint(widget.sizeHint())
        self.insertItem(0, item)
        self.setItemWidget(item, widget)
        self._widget_map[key] = (item, widget)

    def remove_widget_item(self, key: str):
        """
        Remove a widget by identifier key.

        Args:
            key (str): Key associated with the widget to remove.
        """
        if key not in self._widget_map:
            return

        item, widget = self._widget_map.pop(key)
        row = self.row(item)
        self.takeItem(row)
        try:
            widget.close()
        except Exception:
            logger.debug(f"Could not close widget properly for key: {key}.")
        try:
            widget.deleteLater()
        except Exception:
            logger.debug(f"Could not delete widget properly for key: {key}.")

    def clear_widgets(self):
        """Remove and destroy all widget items."""
        for key in list(self._widget_map.keys()):
            self.remove_widget_item(key)
        self._widget_map.clear()
        self.clear()

    def get_widget(self, key: str) -> QWidget | None:
        """Return the widget for a given key."""
        entry = self._widget_map.get(key)
        return entry[1] if entry else None

    def get_item(self, key: str) -> QListWidgetItem | None:
        """Return the QListWidgetItem for a given key."""
        entry = self._widget_map.get(key)
        return entry[0] if entry else None

    def get_widgets(self) -> list[QWidget]:
        """Return all managed widgets."""
        return [w for _, w in self._widget_map.values()]

    def get_widget_for_item(self, item: QListWidgetItem) -> QWidget | None:
        """Return the widget associated with a given QListWidgetItem."""
        for itm, widget in self._widget_map.values():
            if itm == item:
                return widget
        return None

    def get_item_for_widget(self, widget: QWidget) -> QListWidgetItem | None:
        """Return the QListWidgetItem associated with a given widget."""
        for itm, w in self._widget_map.values():
            if w == widget:
                return itm
        return None

    def get_all_keys(self) -> list[str]:
        """Return all keys for managed widgets."""
        return list(self._widget_map.keys())
