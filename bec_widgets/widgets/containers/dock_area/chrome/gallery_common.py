"""State shared by the QWidget and QML versions of the Add widget gallery and the empty state."""

from __future__ import annotations

from qtpy.QtCore import Property, QObject, Signal, Slot

from bec_widgets.utils.quick.list_model import DictListModel
from bec_widgets.widgets.containers.dock_area.chrome.catalog import (
    PLACEMENTS,
    STARTER_LAYOUTS,
    WidgetEntry,
    all_entries,
)

ITEM_ROLES = ("widgetClass", "name", "description", "iconName", "category")
PLACEMENT_ROLES = ("key", "label", "hint", "available")
LAYOUT_ROLES = ("name", "description", "icon", "widgets")


class GalleryController(QObject):
    """Search, highlight and placement of the Add widget gallery.

    Both views bind to this object, so they behave the same: typing filters, the arrow keys move
    the highlight, Enter adds the highlighted widget, and the placement says where it goes.

    Args:
        entries(tuple[WidgetEntry, ...] | None): Widgets to offer; defaults to the full catalog.
        parent(QObject | None): Parent object.
    """

    widget_requested = Signal(str, str)
    layout_requested = Signal(str)
    query_changed = Signal()
    placement_changed = Signal()
    highlight_changed = Signal()
    anchor_changed = Signal()

    def __init__(self, entries: tuple[WidgetEntry, ...] | None = None, parent=None):
        super().__init__(parent)
        self._entries = tuple(entries) if entries is not None else all_entries()
        self._query = ""
        self._placement = "beside"
        self._anchor_title = ""
        self._highlight = 0
        self.items = DictListModel(ITEM_ROLES, self)
        self.placement_model = DictListModel(PLACEMENT_ROLES, self)
        self.layouts = DictListModel(LAYOUT_ROLES, self)
        self.layouts.set_items(
            [
                {
                    "name": layout.name,
                    "description": layout.description,
                    "icon": layout.icon,
                    "widgets": len(layout.steps),
                }
                for layout in STARTER_LAYOUTS
            ]
        )
        self._refresh_items()
        self._refresh_placements()

    # ------------------------------------------------------------------ entries
    @property
    def entries(self) -> tuple[WidgetEntry, ...]:
        """All widgets the gallery offers."""
        return self._entries

    def filtered(self) -> list[WidgetEntry]:
        """Entries matching the query, in catalog order."""
        return [entry for entry in self._entries if entry.matches(self._query)]

    def _refresh_items(self) -> None:
        self.items.set_items(
            [
                {
                    "widgetClass": entry.widget_class,
                    "name": entry.name,
                    "description": entry.description,
                    "iconName": entry.icon,
                    "category": entry.category,
                }
                for entry in self.filtered()
            ]
        )
        self._highlight = 0 if self.items.count else -1
        self.highlight_changed.emit()

    # ------------------------------------------------------------------ query
    def _get_query(self) -> str:
        return self._query

    @Slot(str)
    def set_query(self, text: str) -> None:
        """Filter the gallery by ``text``."""
        if text == self._query:
            return
        self._query = text
        self._refresh_items()
        self.query_changed.emit()

    query = Property(str, _get_query, set_query, notify=query_changed)

    # ------------------------------------------------------------------ placement
    def _get_placement(self) -> str:
        return self._placement if self._anchor_title or self._placement == "floating" else "column"

    @Slot(str)
    def set_placement(self, key: str) -> None:
        """Choose where the next widget goes (see :data:`~.catalog.PLACEMENTS`)."""
        if key not in {p[0] for p in PLACEMENTS} or key == self._placement:
            return
        self._placement = key
        self.placement_changed.emit()
        self._refresh_placements()

    placement = Property(str, _get_placement, set_placement, notify=placement_changed)

    def _get_anchor_title(self) -> str:
        return self._anchor_title

    def set_anchor_title(self, title: str) -> None:
        """Name of the widget that Beside, Below and As tab refer to; empty when there is none."""
        title = title or ""
        if title == self._anchor_title:
            return
        self._anchor_title = title
        self.anchor_changed.emit()
        self.placement_changed.emit()
        self._refresh_placements()

    anchorTitle = Property(str, _get_anchor_title, notify=anchor_changed)

    def _refresh_placements(self) -> None:
        relative = bool(self._anchor_title)
        self.placement_model.set_items(
            [
                {
                    "key": key,
                    "label": label,
                    "hint": hint,
                    "available": relative or key in ("column", "floating"),
                }
                for key, label, hint in PLACEMENTS
            ]
        )

    @Slot(result=str)
    def placement_summary(self) -> str:
        """One line saying where the next widget goes, e.g. ``Beside Waveform 2``."""
        key = self._get_placement()
        if key == "column":
            return "As a new column at the right"
        if key == "floating":
            return "In its own window"
        label = {"beside": "Beside", "below": "Below", "tab": "As a tab with"}[key]
        return f"{label} {self._anchor_title}"

    placementSummary = Property(
        str, lambda self: self.placement_summary(), notify=placement_changed
    )

    # ------------------------------------------------------------------ highlight
    def _get_highlight(self) -> int:
        return self._highlight

    @Slot(int)
    def set_highlight(self, row: int) -> None:
        """Highlight ``row`` of the filtered list."""
        row = max(-1, min(row, self.items.count - 1))
        if row == self._highlight:
            return
        self._highlight = row
        self.highlight_changed.emit()

    highlight = Property(int, _get_highlight, set_highlight, notify=highlight_changed)

    @Slot(int)
    def move_highlight(self, delta: int) -> None:
        """Move the highlight by ``delta`` rows, wrapping around."""
        count = self.items.count
        if count == 0:
            return
        self.set_highlight((max(self._highlight, 0) + delta) % count)

    @Slot()
    @Slot(int)
    def activate(self, row: int = -1) -> None:
        """Add the widget at ``row`` (the highlighted one by default)."""
        row = self._highlight if row < 0 else row
        items = self.items.items
        if not 0 <= row < len(items):
            return
        self.widget_requested.emit(items[row]["widgetClass"], self._get_placement())

    @Slot(str)
    def activate_layout(self, name: str) -> None:
        """Build the starter layout called ``name``."""
        self.layout_requested.emit(name)

    @Slot()
    def reset(self) -> None:
        """Clear the search, e.g. when the gallery opens again."""
        self.set_query("")
        self.set_highlight(0)

    # QML access to the models
    itemModel = Property(QObject, lambda self: self.items, constant=True)
    placementModel = Property(QObject, lambda self: self.placement_model, constant=True)
    layoutModel = Property(QObject, lambda self: self.layouts, constant=True)
