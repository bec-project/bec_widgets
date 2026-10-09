"""Toolkit-independent model of the device and signal pickers.

* :func:`device_snapshot` reads the enabled devices once per device configuration and shares
  the result between all pickers of a client, so a refresh no longer walks the device manager
  for every combobox.
* :class:`PickerEntry`, :func:`rank_entry` and :class:`PickerController` hold the searchable,
  grouped rows, the highlighted row and the details (with the live value) shown in the footer.
  Both the QWidget and the QML popup are thin views over the controller.
"""

from __future__ import annotations

import html
import time
import weakref
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from bec_lib.device import ComputedSignal, Device, Positioner
from bec_lib.device import Signal as BECSignal
from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject, Qt, QTimer, Signal

from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.quick.list_model import DictListModel
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import BECDeviceFilter

logger = bec_logger.logger

MAX_RECENT = 4

# ---- shared device snapshot ------------------------------------------------------------------


@dataclass
class DeviceRecord:
    """What the pickers need to know about one enabled device, read once per configuration."""

    name: str
    device: Any
    kind: str
    filters: frozenset
    readout: Any
    device_class: str
    description: str
    tags: tuple[str, ...]
    write_access: bool


@dataclass
class DeviceSnapshot:
    """All enabled devices of a client at one device configuration generation."""

    generation: int
    fingerprint: tuple = ()
    records: dict[str, DeviceRecord] = field(default_factory=dict)
    signal_classes: dict[tuple, list] = field(default_factory=dict)


class _CatalogState:  # pylint: disable=too-few-public-methods
    """Generation counter bumped by device configuration updates of one device manager.

    The pickers bump it from their device update callbacks. Updates that happen while no picker
    listens are caught by the fingerprint of the device container (see :func:`device_snapshot`).
    """

    def __init__(self):
        self.generation = 0
        self.snapshot: DeviceSnapshot | None = None

    def bump(self, *_args, **_kwargs) -> None:
        """Invalidate the snapshot; called from the BEC callback thread."""
        self.generation += 1


_CATALOGS: "weakref.WeakKeyDictionary[Any, _CatalogState]" = weakref.WeakKeyDictionary()

_KIND_ORDER = (
    (BECDeviceFilter.POSITIONER, "positioner"),
    (BECDeviceFilter.COMPUTED_SIGNAL, "computed"),
    (BECDeviceFilter.SIGNAL, "signal"),
    (BECDeviceFilter.DEVICE, "device"),
)
_FILTER_CLASSES = {
    BECDeviceFilter.DEVICE: Device,
    BECDeviceFilter.POSITIONER: Positioner,
    BECDeviceFilter.SIGNAL: BECSignal,
    BECDeviceFilter.COMPUTED_SIGNAL: ComputedSignal,
}

DEVICE_KIND_LABELS = {
    "positioner": ("Positioners", "open_with"),
    "computed": ("Computed signals", "functions"),
    "signal": ("Signals", "sensors"),
    "device": ("Devices", "memory"),
}


def _catalog_state(client) -> _CatalogState | None:
    device_manager = getattr(client, "device_manager", None)
    if device_manager is None:
        return None
    try:
        state = _CATALOGS.get(device_manager)
    except TypeError:
        return None
    if state is None:
        state = _CatalogState()
        try:
            _CATALOGS[device_manager] = state
        except TypeError:
            return None
    return state


def _record_for(device) -> DeviceRecord:
    filters = frozenset(entry for entry, cls in _FILTER_CLASSES.items() if isinstance(device, cls))
    kind = next((label for entry, label in _KIND_ORDER if entry in filters), "device")
    config = getattr(device, "_config", None) or {}
    info = getattr(device, "_info", None) or {}
    device_class = str(config.get("deviceClass") or "")
    tags = config.get("deviceTags") or ()
    return DeviceRecord(
        name=device.name,
        device=device,
        kind=kind,
        filters=filters,
        readout=getattr(device, "readout_priority", None),
        device_class=device_class.rsplit(".", 1)[-1],
        description=str(config.get("description") or ""),
        tags=tuple(sorted(str(tag) for tag in tags)),
        write_access=bool(info.get("write_access")),
    )


def _fingerprint(devices) -> tuple:
    """Cheap identity of a device container: changes when devices are added, removed or reloaded."""
    if not isinstance(devices, dict):
        return ()
    values = dict.values(devices)
    return (len(devices), hash(tuple(id(device) for device in values)))


def device_snapshot(client, force: bool = False) -> DeviceSnapshot:
    """Return the enabled devices of ``client``, shared by all pickers until the config changes.

    The snapshot is rebuilt when a picker saw a device configuration update, when devices were
    added, removed or reloaded (the device objects change), or when ``force`` is set.

    Args:
        client: BEC client.
        force(bool): Re-read the device manager even if nothing seems to have changed.

    Returns:
        DeviceSnapshot: Records of all enabled devices in device manager order.
    """
    devices = getattr(getattr(client, "device_manager", None), "devices", None)
    fingerprint = _fingerprint(devices)
    state = _catalog_state(client)
    if state is not None and not force:
        snapshot = state.snapshot
        if (
            snapshot is not None
            and snapshot.generation == state.generation
            and snapshot.fingerprint == fingerprint
        ):
            return snapshot
    generation = state.generation if state is not None else -1
    snapshot = DeviceSnapshot(generation=generation, fingerprint=fingerprint)
    for device in getattr(devices, "enabled_devices", None) or []:
        snapshot.records[device.name] = _record_for(device)
    if state is not None:
        state.snapshot = snapshot
    return snapshot


def invalidate_device_snapshot(client) -> None:
    """Drop the shared snapshot of ``client``, e.g. after changing devices in a test."""
    state = _catalog_state(client)
    if state is not None:
        state.bump()


# ---- entries, search and rows ----------------------------------------------------------------


@dataclass(frozen=True)
class PickerEntry:
    """One selectable row of a picker popup.

    Attributes:
        value: Text the combobox receives when the entry is picked.
        title: Primary label.
        subtitle: Muted secondary label, e.g. the device class.
        group: Section the entry is listed under when nothing is searched.
        badge: Short chip text, e.g. the readout priority or signal kind.
        icon: Material icon name.
        device: Device whose live value is shown for the entry.
        signal: Signal object name of the live value; empty for the device's main signal.
        details: Extra text for the footer, e.g. the description or tags.
    """

    value: str
    title: str
    subtitle: str = ""
    group: str = ""
    badge: str = ""
    icon: str = ""
    device: str = ""
    signal: str = ""
    details: str = ""


def _word_starts(text: str) -> list[int]:
    starts = [0]
    for index in range(1, len(text)):
        if text[index - 1] in "_.-: " or (text[index].isupper() and text[index - 1].islower()):
            starts.append(index)
    return starts


def rank_entry(  # pylint: disable=too-many-return-statements
    query: str, entry: PickerEntry
) -> tuple[int, int, int] | None:
    """Score how well ``entry`` matches ``query``; lower is better.

    Ranks: 0 title prefix, 1 prefix of a word in the title (``x`` matches ``sam_x``),
    2 substring of the title, 3 characters of the query in order (``smx`` matches ``samx``),
    4 substring of the subtitle, badge or details.

    Args:
        query(str): Search text; matching ignores case and surrounding blanks.
        entry(PickerEntry): Entry to score.

    Returns:
        tuple[int, int, int] | None: ``(rank, match_start, match_length)`` in the title, or None
        if the entry does not match. Ranks 3 and 4 report no title highlight (``-1, 0``).
    """
    needle = query.strip().lower()
    if not needle:
        return (0, -1, 0)
    title = entry.title.lower()
    position = title.find(needle)
    if position == 0:
        return (0, 0, len(needle))
    if position > 0:
        for start in _word_starts(entry.title):
            if title.startswith(needle, start):
                return (1, start, len(needle))
        return (2, position, len(needle))
    cursor = 0
    for char in needle:
        cursor = title.find(char, cursor)
        if cursor < 0:
            break
        cursor += 1
    else:
        return (3, -1, 0)
    haystack = f"{entry.subtitle} {entry.badge} {entry.details} {entry.signal}".lower()
    if needle in haystack:
        return (4, -1, 0)
    return None


def rich_title(title: str, start: int, length: int, color: str) -> str:
    """Return ``title`` as Qt rich text with the matched part bold and coloured."""
    if start < 0 or length <= 0:
        return html.escape(title)
    before, match, after = title[:start], title[start : start + length], title[start + length :]
    return (
        f"{html.escape(before)}<b><font color='{color}'>{html.escape(match)}</font></b>"
        f"{html.escape(after)}"
    )


ROW_ROLES = (
    "rowType",
    "value",
    "title",
    "titleRich",
    "subtitle",
    "badge",
    "icon",
    "matchStart",
    "matchLength",
    "isCurrent",
    "count",
)


class PickerRowsModel(DictListModel):
    """Rows of a picker popup: ``header``, ``item`` and ``empty`` rows.

    The display role returns the title, so plain item views and tests can read the rows too.
    """

    def __init__(self, parent=None):
        super().__init__(ROW_ROLES, parent)

    def data(self, index, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and index.isValid():
            role = self.role_id("title")
        return super().data(index, role)

    def role_id(self, key: str) -> int:
        """Qt role id of a row key."""
        return Qt.ItemDataRole.UserRole + 1 + ROW_ROLES.index(key)

    def row(self, row: int) -> dict:
        """Row dictionary at ``row`` (not a copy; do not modify)."""
        return self._items[row]  # pylint: disable=protected-access


def _row(row_type: str, title: str, **values) -> dict:
    """Row dictionary with every role of :data:`ROW_ROLES` set."""
    row = {
        "rowType": row_type,
        "value": "",
        "title": title,
        "titleRich": html.escape(title),
        "subtitle": "",
        "badge": "",
        "icon": "",
        "matchStart": -1,
        "matchLength": 0,
        "isCurrent": False,
        "count": 0,
    }
    row.update(values)
    return row


def format_value(value: Any) -> str:  # pylint: disable=too-many-return-statements
    """Short text for a reading shown in the footer."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6g}"
    shape = getattr(value, "shape", None)
    if shape is not None and len(shape) > 0:
        return f"array {'x'.join(str(dim) for dim in shape)}"
    if isinstance(value, (list, tuple)):
        return f"list [{len(value)}]"
    if isinstance(value, dict):
        return "{…}"
    text = str(value)
    return text if len(text) <= 40 else f"{text[:39]}…"


class PickerController(QObject):
    """Search, grouping, highlight and footer details of an open picker popup.

    Both popups are thin views over this object; all behaviour that the user can observe lives
    here so the QWidget and QML versions behave identically.

    Args:
        noun(str): Plural used in texts, e.g. ``"devices"``.
        live_reader: Called with an entry, returns the cached reading dict (``value``,
            ``timestamp``) or None. Runs debounced when the highlight settles.
        live_watcher: Called with the highlighted entry (or None when the popup closes) so the
            picker can subscribe to live updates of that device only.
        parent: Parent QObject.
    """

    rows_changed = Signal()
    highlight_changed = Signal()
    detail_changed = Signal()
    query_changed = Signal()
    picked = Signal(str)
    dismissed = Signal()

    LIVE_DELAY_MS = 120

    def __init__(
        self,
        noun: str,
        live_reader: Callable[[PickerEntry], dict | None] | None = None,
        live_watcher: Callable[[PickerEntry | None], None] | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._noun = noun
        self._live_reader = live_reader
        self._live_watcher = live_watcher
        self._entries: list[PickerEntry] = []
        self._recent: list[str] = []
        self._current = ""
        self._query = ""
        self._row_entries: list[PickerEntry | None] = []
        self._highlight = -1
        self._match_count = 0
        self._detail: dict = {}
        self._accent = ""
        self._watched: PickerEntry | None = None
        self.model = PickerRowsModel(self)
        self._live_timer = QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.setInterval(self.LIVE_DELAY_MS)
        self._live_timer.timeout.connect(self._load_live_value)

    # ---- state -----------------------------------------------------------------------------

    def open(
        self,
        entries: Sequence[PickerEntry],
        current: str = "",
        query: str = "",
        recent: Sequence[str] = (),
    ) -> None:
        """Load the entries shown by a popup that is about to open.

        Args:
            entries: All selectable entries in display order.
            current: Value of the current selection; it is marked and highlighted.
            query: Initial search text, e.g. what the user started typing in the field.
            recent: Recently picked values listed first while nothing is searched.
        """
        self._entries = list(entries)
        self._current = current or ""
        self._recent = [value for value in recent if any(e.value == value for e in self._entries)]
        self._query = query
        self._rebuild()
        self.query_changed.emit()

    def close(self) -> None:
        """Stop live updates; called when the popup hides."""
        self._live_timer.stop()
        if self._watched is not None and self._live_watcher is not None:
            self._live_watcher(None)
        self._watched = None

    def set_query(self, query: str) -> None:
        """Filter the rows by ``query``."""
        if query == self._query:
            return
        self._query = query
        self._rebuild()
        self.query_changed.emit()

    def move_highlight(self, step: int) -> None:
        """Move the highlight by ``step`` selectable rows, wrapping at the ends."""
        selectable = [row for row, entry in enumerate(self._row_entries) if entry is not None]
        if not selectable:
            return
        if self._highlight not in selectable:
            target = selectable[0] if step > 0 else selectable[-1]
        else:
            position = selectable.index(self._highlight) + step
            target = selectable[position % len(selectable)]
        self.set_highlight(target)

    def page_highlight(self, step: int, rows: int = 8) -> None:
        """Move the highlight by a page of ``rows`` rows without wrapping."""
        selectable = [row for row, entry in enumerate(self._row_entries) if entry is not None]
        if not selectable:
            return
        position = selectable.index(self._highlight) if self._highlight in selectable else 0
        position = max(0, min(len(selectable) - 1, position + step * rows))
        self.set_highlight(selectable[position])

    def set_highlight(self, row: int) -> None:
        """Highlight ``row`` if it is selectable."""
        if not 0 <= row < len(self._row_entries) or self._row_entries[row] is None:
            return
        if row == self._highlight:
            return
        self._highlight = row
        self.highlight_changed.emit()
        self._update_detail()

    def accept(self, row: int = -1) -> bool:
        """Pick ``row``, or the highlighted row when ``row`` is -1.

        Returns:
            bool: True if an entry was picked.
        """
        row = self._highlight if row < 0 else row
        if not 0 <= row < len(self._row_entries):
            return False
        entry = self._row_entries[row]
        if entry is None:
            return False
        self.picked.emit(entry.value)
        return True

    def dismiss(self) -> None:
        """Close without picking."""
        self.dismissed.emit()

    # ---- read-only state used by the views ---------------------------------------------------

    @property
    def query(self) -> str:
        """Current search text."""
        return self._query

    @property
    def highlight(self) -> int:
        """Highlighted row, -1 if none."""
        return self._highlight

    @property
    def detail(self) -> dict:
        """Footer contents for the highlighted entry."""
        return self._detail

    @property
    def summary(self) -> str:
        """Count text shown next to the search field."""
        total = len(self._entries)
        if not self._query.strip():
            return f"{total} {self._noun}"
        return f"{self._match_count} of {total}"

    @property
    def placeholder(self) -> str:
        """Placeholder of the search field."""
        return f"Search {self._noun}…"

    def entry_at(self, row: int) -> PickerEntry | None:
        """Entry shown in ``row`` (None for headers and the empty row)."""
        if 0 <= row < len(self._row_entries):
            return self._row_entries[row]
        return None

    # ---- internals ---------------------------------------------------------------------------

    def _item_row(self, entry: PickerEntry, start: int = -1, length: int = 0) -> tuple:
        accent = self._accent
        return (
            _row(
                "item",
                entry.title,
                value=entry.value,
                titleRich=rich_title(entry.title, start, length, accent),
                subtitle=entry.subtitle,
                badge=entry.badge,
                icon=entry.icon,
                matchStart=start,
                matchLength=length,
                isCurrent=entry.value == self._current,
            ),
            entry,
        )

    def _ranked_rows(self, query: str) -> list[tuple]:
        ranked = []
        for order, entry in enumerate(self._entries):
            score = rank_entry(query, entry)
            if score is not None:
                ranked.append((score[0], order, entry, score))
        ranked.sort(key=lambda item: (item[0], item[1]))
        self._match_count = len(ranked)
        return [self._item_row(entry, score[1], score[2]) for _, _, entry, score in ranked]

    def _grouped_rows(self) -> list[tuple]:
        self._match_count = len(self._entries)
        rows = []
        if self._recent and len(self._entries) > MAX_RECENT * 2:
            by_value = {entry.value: entry for entry in self._entries}
            rows.append((_row("header", "Recent", icon="history", count=len(self._recent)), None))
            rows.extend(self._item_row(by_value[value]) for value in self._recent)
        groups: dict[str, list[PickerEntry]] = {}
        for entry in self._entries:
            groups.setdefault(entry.group, []).append(entry)
        show_headers = len(groups) > 1 or bool(rows)
        for group, entries in groups.items():
            if show_headers and group:
                rows.append((_row("header", group, count=len(entries)), None))
            rows.extend(self._item_row(entry) for entry in entries)
        return rows

    def _rebuild(self) -> None:
        self._accent = ThemeTokens().primary.name()
        query = self._query.strip()
        rows = self._ranked_rows(query) if query else self._grouped_rows()
        if not any(entry is not None for _, entry in rows):
            text = f"No {self._noun} match “{query}”" if query else f"No {self._noun} available"
            rows = [(_row("empty", text, icon="search_off" if query else "block"), None)]
        self._row_entries = [entry for _, entry in rows]
        self.model.set_items([row for row, _ in rows])
        self.rows_changed.emit()

        selectable = [row for row, entry in enumerate(self._row_entries) if entry is not None]
        wanted = None if query else self._current
        target = next(
            (row for row in selectable if self._row_entries[row].value == wanted),
            selectable[0] if selectable else -1,
        )
        self._highlight = target
        self.highlight_changed.emit()
        self._update_detail()

    def _update_detail(self) -> None:
        entry = self.entry_at(self._highlight)
        if entry is None:
            self._detail = {}
            self._live_timer.stop()
        else:
            self._detail = {
                "title": entry.title,
                "subtitle": entry.subtitle,
                "details": entry.details,
                "icon": entry.icon,
                "badge": entry.badge,
                "value": "",
                "valueTime": "",
                "valueState": "loading" if self._live_reader is not None else "none",
            }
            if self._live_reader is not None:
                self._live_timer.start()
        self.detail_changed.emit()

    def _load_live_value(self) -> None:
        entry = self.entry_at(self._highlight)
        if entry is None:
            return
        reading = None
        try:
            reading = self._live_reader(entry) if self._live_reader is not None else None
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug(f"Could not read cached value of {entry.device}: {exc}")
        self.update_live_value(entry, reading)
        if self._live_watcher is not None and entry != self._watched:
            self._watched = entry
            self._live_watcher(entry)

    def update_live_value(self, entry: PickerEntry, reading: dict | None) -> None:
        """Show ``reading`` in the footer if ``entry`` is still highlighted.

        Args:
            entry(PickerEntry): Entry the reading belongs to.
            reading(dict | None): Reading with ``value`` and optional ``timestamp``.
        """
        if self.entry_at(self._highlight) != entry or not self._detail:
            return
        detail = dict(self._detail)
        if reading is None or "value" not in reading:
            detail.update({"value": "", "valueTime": "", "valueState": "none"})
        else:
            stamp = reading.get("timestamp")
            detail.update(
                {
                    "value": format_value(reading.get("value")),
                    "valueTime": (
                        time.strftime("%H:%M:%S", time.localtime(stamp))
                        if isinstance(stamp, (int, float)) and stamp > 0
                        else ""
                    ),
                    "valueState": "live",
                }
            )
        self._detail = detail
        self.detail_changed.emit()


# ---- recent picks ------------------------------------------------------------------------------

_RECENT: dict[str, list[str]] = {"devices": [], "signals": []}


def remember_pick(kind: str, value: str) -> None:
    """Remember ``value`` as recently picked for pickers of ``kind`` in this session."""
    if not value:
        return
    recent = _RECENT.setdefault(kind, [])
    if value in recent:
        recent.remove(value)
    recent.insert(0, value)
    del recent[MAX_RECENT:]


def recent_picks(kind: str) -> list[str]:
    """Recently picked values for pickers of ``kind``, newest first."""
    return list(_RECENT.get(kind, []))


def clear_recent_picks() -> None:
    """Forget the recent picks of all pickers."""
    for values in _RECENT.values():
        values.clear()
