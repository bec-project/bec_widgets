"""State shared by the QWidget and QML versions of the profile switcher.

The switcher replaces the plain drop-down list of the toolbar profile combo. It shows every
profile with its saved preview, says which one is open (here or in another tab), filters as you
type, and offers Save as, Revert and the profile library at the bottom.
"""

from __future__ import annotations

import os

from qtpy.QtCore import Property, QObject, QSize, Qt, Signal, Slot
from qtpy.QtGui import QPixmap

from bec_widgets.utils.quick.list_model import DictListModel
from bec_widgets.widgets.containers.dock_area.profile_utils import (
    get_profile_info,
    list_profiles,
    load_profile_screenshot,
)
from bec_widgets.widgets.containers.dock_area.profile_ux.common import (
    ProfileActions,
    relative_time,
    widget_count_label,
)

ROW_ROLES = (
    "name",
    "subtitle",
    "section",
    "previewUrl",
    "readOnly",
    "pinned",
    "isCurrent",
    "isOpenElsewhere",
    "header",
)
SECTION_PINNED = "In the toolbar list"
SECTION_OTHER = "Other profiles"
THUMB_SIZE = QSize(96, 54)
# Footer actions: key, label, icon, tooltip
FOOTER_ACTIONS = (
    ("save", "Save as…", "save", "Save the current layout as a profile"),
    ("revert", "Revert…", "history", "Go back to the saved version of this profile"),
    ("library", "All profiles…", "folder_open", "Open the profile library"),
)


def thumbnail(pixmap: QPixmap | None, size: QSize = THUMB_SIZE) -> QPixmap | None:
    """Scale a stored preview down to a list thumbnail, or None when there is none."""
    if pixmap is None or pixmap.isNull():
        return None
    return pixmap.scaled(
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    ).copy(0, 0, size.width(), size.height())


class ProfileSwitcherController(QObject):  # pylint: disable=too-many-instance-attributes
    """Rows, search and highlight of the profile switcher.

    Args:
        actions(ProfileActions): Profile operations of the dock area the switcher belongs to.
        publish_preview(callable | None): Turns a thumbnail into a URL for QML; the QWidget view
            reads :meth:`thumbnail_for` instead.
        parent(QObject | None): Parent object.
    """

    # name, open in a new tab
    profile_chosen = Signal(str, bool)
    # one of the FOOTER_ACTIONS keys
    action_requested = Signal(str)
    rows_changed = Signal()
    query_changed = Signal()
    highlight_changed = Signal()

    def __init__(self, actions: ProfileActions, publish_preview=None, parent=None):
        super().__init__(parent)
        self.actions = actions
        self._publish = publish_preview
        self._query = ""
        self._highlight = 0
        self._entries: list[dict] = []
        self._thumbs: dict[str, QPixmap | None] = {}
        # name -> (file stamps, thumbnail); previews are only decoded again when a file changed
        self._thumb_cache: dict[str, tuple[tuple, QPixmap | None]] = {}
        self.rows = DictListModel(ROW_ROLES, self)

    # ------------------------------------------------------------------ building
    def refresh(self) -> None:
        """Re-read profiles and previews from disk."""
        namespace = self.actions.namespace
        current = self.actions.current_profile()
        open_names = set(self.actions.open_profiles())
        entries = []
        self._thumbs = {}
        for name in list_profiles(namespace):
            info = get_profile_info(name, namespace)
            count = info.widget_count
            if name == current:
                count = len(self.actions.dock_area().dock_list())
            subtitle = [widget_count_label(count)]
            edited = relative_time(info.modified)
            if edited:
                subtitle.append(f"edited {edited}")
            if info.notes:
                subtitle = [info.notes.splitlines()[0]]
            thumb = self._cached_thumbnail(name, info)
            self._thumbs[name] = thumb
            entries.append(
                {
                    "name": name,
                    "subtitle": " · ".join(subtitle),
                    "section": SECTION_PINNED if info.is_quick_select else SECTION_OTHER,
                    "previewUrl": self._publish(f"switcher-{name}", thumb) if self._publish else "",
                    "readOnly": info.is_read_only,
                    "pinned": info.is_quick_select,
                    "isCurrent": name == current,
                    "isOpenElsewhere": name != current and name in open_names,
                }
            )
        order = {SECTION_PINNED: 0, SECTION_OTHER: 1}
        entries.sort(key=lambda e: (order[e["section"]], e["name"].lower()))
        self._entries = entries
        self._rebuild(keep_current=True)

    def _cached_thumbnail(self, name: str, info) -> QPixmap | None:
        stamps = tuple(
            os.path.getmtime(path) if path and os.path.exists(path) else 0.0
            for path in (info.runtime_path, info.baseline_path)
        )
        cached = self._thumb_cache.get(name)
        if cached is not None and cached[0] == stamps:
            return cached[1]
        thumb = thumbnail(load_profile_screenshot(name, namespace=self.actions.namespace))
        self._thumb_cache[name] = (stamps, thumb)
        return thumb

    def _matches(self, entry: dict) -> bool:
        query = self._query.strip().lower()
        if not query:
            return True
        haystack = f"{entry['name']} {entry['subtitle']}".lower()
        return all(part in haystack for part in query.split())

    def _rebuild(self, keep_current: bool = False) -> None:
        rows = [dict(entry) for entry in self._entries if self._matches(entry)]
        sections = {row["section"] for row in rows}
        previous = None
        for row in rows:
            # Section title on the first row of each section, when there is more than one
            row["header"] = (
                row["section"] if len(sections) > 1 and row["section"] != previous else ""
            )
            previous = row["section"]
        self.rows.set_items(rows)
        highlight = 0
        if keep_current:
            highlight = next((i for i, row in enumerate(rows) if row["isCurrent"]), 0)
        self.set_highlight(highlight)
        self.rows_changed.emit()

    def thumbnail_for(self, name: str) -> QPixmap | None:
        """List thumbnail of *name*, or None when it has no saved preview."""
        return self._thumbs.get(name)

    # ------------------------------------------------------------------ properties
    def _get_query(self) -> str:
        return self._query

    @Slot(str)
    def set_query(self, text: str) -> None:
        """Filter the rows by name and description."""
        if text == self._query:
            return
        self._query = text
        self.query_changed.emit()
        self._rebuild()

    query = Property(str, _get_query, set_query, notify=query_changed)

    def _get_highlight(self) -> int:
        return self._highlight

    @Slot(int)
    def set_highlight(self, row: int) -> None:
        """Highlight *row* (clamped to the visible rows)."""
        row = max(0, min(row, self.rows.count - 1)) if self.rows.count else -1
        if row != self._highlight:
            self._highlight = row
            self.highlight_changed.emit()

    highlight = Property(int, _get_highlight, set_highlight, notify=highlight_changed)

    @Slot(int)
    def move_highlight(self, delta: int) -> None:
        """Move the highlight up or down, wrapping around."""
        if self.rows.count:
            self.set_highlight((self._highlight + delta) % self.rows.count)

    def _current_name(self) -> str:
        return self.actions.current_profile() or ""

    def _can_revert(self) -> bool:
        name = self._current_name()
        return bool(name) and self.actions.can_revert(name)

    def _empty_text(self) -> str:
        query = self._query.strip()
        if query:
            return f"No profile matches '{query}'."
        return "No saved profiles yet. Use Save as… to keep this layout."

    def _has_tabs(self) -> bool:
        return self.actions.host is not None

    currentName = Property(str, _current_name, notify=rows_changed)
    hasTabs = Property(bool, _has_tabs, constant=True)
    canRevert = Property(bool, _can_revert, notify=rows_changed)
    emptyText = Property(str, _empty_text, notify=rows_changed)

    # ------------------------------------------------------------------ actions
    @Slot()
    @Slot(int)
    @Slot(int, bool)
    def activate(self, row: int = -1, new_tab: bool = False) -> None:
        """Open the highlighted (or given) profile."""
        row = self._highlight if row < 0 else row
        items = self.rows.items
        if not 0 <= row < len(items):
            return
        self.profile_chosen.emit(items[row]["name"], bool(new_tab))

    @Slot(str)
    def request(self, key: str) -> None:
        """Run a footer action: ``save``, ``revert`` or ``library``."""
        self.action_requested.emit(key)

    def reset(self) -> None:
        """Clear the search and reload, highlighting the open profile."""
        self._query = ""
        self.query_changed.emit()
        self.refresh()

    rowModel = Property(QObject, lambda self: self.rows, constant=True)
