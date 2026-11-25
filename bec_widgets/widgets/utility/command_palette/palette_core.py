"""Search model of the command palette.

The palette searches a flat list of :class:`PaletteCommand` objects collected from command
sources (see :mod:`palette_sources`). :class:`CommandPaletteController` owns the query, the scope
filter, the ranked results and the keyboard selection; the card only renders its
:class:`ResultModel` and forwards key presses to it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from bec_lib.logger import bec_logger
from qtpy.QtCore import Property, QAbstractListModel, QModelIndex, QObject, Qt, QTimer, Signal

from bec_widgets.utils.error_popups import SafeSlot

logger = bec_logger.logger

# category id -> (label, scope)
CATEGORIES: dict[str, tuple[str, str]] = {
    "navigate": ("Go to", "actions"),
    "actions": ("Actions", "actions"),
    "widgets": ("Widgets", "widgets"),
    "workspaces": ("Workspaces", "workspaces"),
    "devices": ("Devices", "devices"),
}

# scope id, label, query prefix
SCOPES: list[tuple[str, str, str]] = [
    ("all", "All", ""),
    ("actions", "Actions", ">"),
    ("widgets", "Widgets", "+"),
    ("devices", "Devices", "@"),
    ("workspaces", "Workspaces", "#"),
]
_PREFIX_TO_SCOPE = {prefix: scope for scope, _label, prefix in SCOPES if prefix}

MAX_RESULTS = 60
EMPTY_QUERY_SECTION_LIMIT = 6
RECENT_LIMIT = 5

ROLES = [
    "uid",
    "title",
    "positions",
    "subtitle",
    "icon",
    "category",
    "section",
    "shortcut",
    "hint",
    "enabled",
    "tone",
]


@dataclass
class PaletteCommand:
    """One entry of the command palette.

    Args:
        uid(str): Stable id, used to remember recently run commands.
        title(str): Text that is searched and shown.
        callback(Callable[[], object]): Runs the command.
        category(str): One of :data:`CATEGORIES`.
        subtitle(str): Secondary text, also searched with a lower weight.
        icon(str): Material icon name.
        keywords(str): Extra search terms that are not shown.
        shortcut(str): Keyboard shortcut shown as a hint.
        hint(str): Verb shown on the selected row, e.g. ``"Open"``.
        enabled(bool): False shows the row but Enter does nothing; the subtitle says why.
        tone(str): ``"danger"`` marks a row that was refused, e.g. a move outside the limits.
        keep_open(bool): Run without closing the palette, so the row can show what happens.
    """

    uid: str
    title: str
    callback: Callable[[], object]
    category: str = "actions"
    subtitle: str = ""
    icon: str = "bolt"
    keywords: str = ""
    shortcut: str = ""
    hint: str = "Run"
    enabled: bool = True
    tone: str = ""
    keep_open: bool = False
    _title_l: str = field(default="", init=False, repr=False)
    _extra_l: str = field(default="", init=False, repr=False)

    def __post_init__(self):
        self._title_l = self.title.lower()
        self._extra_l = f"{self.subtitle} {self.keywords}".lower()


CommandSource = Callable[[], Iterable[PaletteCommand]]
# called on every search with (query, scope); its commands are listed first, unranked
QueryCommandSource = Callable[[str, str], Iterable[PaletteCommand]]


def _is_boundary(text: str, index: int) -> bool:
    if index == 0:
        return True
    prev, cur = text[index - 1], text[index]
    if not prev.isalnum():
        return True
    return prev.islower() and cur.isupper()


def fuzzy_match(query: str, text: str) -> tuple[float, list[int]] | None:
    """Score how well ``query`` matches ``text``.

    Contiguous substrings rank highest, then matches that start words (``"wf"`` in
    ``"Waveform"`` vs ``"Add Waveform"``), then any in-order subsequence. Case is ignored.

    Args:
        query(str): Search text without whitespace.
        text(str): Candidate text.

    Returns:
        tuple[float, list[int]] | None: Score and matched character positions, or None if the
        characters of ``query`` do not appear in order in ``text``.
    """
    if not query:
        return 0.0, []
    q = query.lower()
    t = text.lower()
    start = t.find(q)
    if start >= 0:
        # prefer an occurrence at a word start, e.g. "form" in "Waveform Form"
        pos = start
        while pos >= 0 and not _is_boundary(text, pos):
            pos = t.find(q, pos + 1)
        boundary = pos >= 0
        if boundary:
            start = pos
        score = 100.0 + 12 * len(q) + (40 if start == 0 else 0) + (25 if boundary else 0)
        score -= 0.3 * len(t)
        return score, list(range(start, start + len(q)))

    # forward pass: earliest in-order match
    positions: list[int] = []
    cursor = 0
    for char in q:
        found = t.find(char, cursor)
        if found < 0:
            return None
        positions.append(found)
        cursor = found + 1
    # backward pass: pull every match as far right as possible to keep it compact, then
    # prefer word starts for each character
    end = positions[-1]
    for i in range(len(q) - 1, -1, -1):
        found = t.rfind(q[i], 0, end + 1)
        positions[i] = found
        end = found - 1
    for i, char in enumerate(q):
        if _is_boundary(text, positions[i]):
            continue
        low = positions[i - 1] + 1 if i else 0
        high = positions[i + 1] if i + 1 < len(q) else len(t)
        for candidate in range(low, high):
            if t[candidate] == char and _is_boundary(text, candidate):
                positions[i] = candidate
                break

    score = 0.0
    for i, pos in enumerate(positions):
        score += 8
        if _is_boundary(text, pos):
            score += 14
        if i and pos == positions[i - 1] + 1:
            score += 10
        elif i:
            score -= min(pos - positions[i - 1] - 1, 8)
    score -= 0.3 * len(t) + positions[0] * 0.5
    return score, positions


def score_command(tokens: list[str], command: PaletteCommand) -> tuple[float, list[int]] | None:
    """Match all whitespace-separated ``tokens`` against a command.

    Each token must fuzzy-match the title (highlighted) or appear verbatim in the subtitle and
    keywords (scored lower, not highlighted).
    """
    total = 0.0
    positions: set[int] = set()
    extra = command._extra_l  # pylint: disable=protected-access
    for token in tokens:
        title_match = fuzzy_match(token, command.title)
        if title_match is not None:
            total += title_match[0]
            positions.update(title_match[1])
            continue
        if token.lower() not in extra:
            return None
        total += 20 + 4 * len(token)
    return total, sorted(positions)


class ResultModel(QAbstractListModel):
    """List model whose rows are dictionaries keyed by :data:`ROLES`.

    :meth:`set_items` updates rows in place when the row count is unchanged, so the list view
    repaints changed rows instead of resetting.
    """

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._roles = {Qt.ItemDataRole.UserRole + 1 + i: key for i, key in enumerate(ROLES)}
        self._items: list[dict[str, Any]] = []

    # pylint: disable=invalid-name
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
        """Replace the rows, reusing existing rows where possible."""
        items = [dict(item) for item in items]
        old_count, new_count = len(self._items), len(items)
        for row in range(min(old_count, new_count)):
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


class CommandPaletteController(QObject):
    """Query, scope, ranked results and selection of the command palette.

    Args:
        sources(Iterable[CommandSource]): Callables returning the commands; they are called
            again on every :meth:`refresh`, i.e. every time the palette opens.
        parent(QObject | None): Parent object.
    """

    queryChanged = Signal()
    scopeChanged = Signal()
    currentIndexChanged = Signal()
    resultsChanged = Signal()
    accepted = Signal(str)
    dismissRequested = Signal()

    def __init__(self, sources: Iterable[CommandSource] = (), parent: QObject | None = None):
        super().__init__(parent)
        self._sources: list[CommandSource] = list(sources)
        self._query_sources: list[QueryCommandSource] = []
        self._commands: list[PaletteCommand] = []
        self._by_uid: dict[str, PaletteCommand] = {}
        self._recent: list[str] = []
        self._query = ""
        self._scope = "all"
        self._current = -1
        self._results: list[PaletteCommand] = []
        self._total = 0
        self._positions: dict[str, list[int]] = {}
        self._sections: dict[str, str] = {}
        self._pending: PaletteCommand | None = None
        self.last_search_ms = 0.0
        self.model = ResultModel(self)

    # ------------------------------------------------------------------ sources
    def add_source(self, source: CommandSource) -> None:
        """Register another command source."""
        self._sources.append(source)

    def add_query_source(self, source: QueryCommandSource) -> None:
        """Register a source that turns the search text itself into commands, e.g. ``samx 10``.

        It is called on every search with the query and the scope and may return nothing.
        """
        self._query_sources.append(source)

    def refresh_live(self) -> None:
        """Re-run the search, e.g. after a live value shown in a row changed.

        The selected row stays selected if it is still listed.
        """
        self._search(keep_selection=True)

    def refresh(self) -> None:
        """Re-collect the commands from all sources and re-run the search."""
        commands: list[PaletteCommand] = []
        for source in self._sources:
            try:
                commands.extend(source())
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(f"Command palette source {source!r} failed: {exc}")
        self._commands = commands
        self._by_uid = {cmd.uid: cmd for cmd in commands}
        self._search()

    @property
    def commands(self) -> list[PaletteCommand]:
        """All commands collected by the last :meth:`refresh`."""
        return list(self._commands)

    @property
    def results(self) -> list[PaletteCommand]:
        """The commands currently listed, in display order."""
        return list(self._results)

    # ------------------------------------------------------------------ properties
    def _get_query(self) -> str:
        return self._query

    def set_query(self, text: str) -> None:
        """Set the search text. A leading ``>``, ``+``, ``@`` or ``#`` switches the scope."""
        text = text or ""
        if text[:1] in _PREFIX_TO_SCOPE:
            self._set_scope_silent(_PREFIX_TO_SCOPE[text[0]])
            text = text[1:].lstrip()
        if text == self._query:
            self._search()
            return
        self._query = text
        self.queryChanged.emit()
        self._search()

    def _get_scope(self) -> str:
        return self._scope

    def _set_scope_silent(self, scope: str) -> None:
        if scope not in {s[0] for s in SCOPES} or scope == self._scope:
            return
        self._scope = scope
        self.scopeChanged.emit()

    def set_scope(self, scope: str) -> None:
        """Restrict the results to one scope, e.g. ``"devices"``; ``"all"`` searches everything."""
        if scope == self._scope:
            return
        self._set_scope_silent(scope)
        self._search()

    def _get_current(self) -> int:
        return self._current

    def set_current_index(self, index: int) -> None:
        """Select a result row; clamped to the result range."""
        index = max(-1, min(int(index), len(self._results) - 1))
        if not self._results:
            index = -1
        elif index < 0:
            index = 0
        if index != self._current:
            self._current = index
            self.currentIndexChanged.emit()

    def _get_result_count(self) -> int:
        return len(self._results)

    def _get_total_count(self) -> int:
        return self._total

    def _get_sectioned(self) -> bool:
        return not self._query

    query = Property(str, _get_query, set_query, notify=queryChanged)
    scope = Property(str, _get_scope, set_scope, notify=scopeChanged)
    currentIndex = Property(int, _get_current, set_current_index, notify=currentIndexChanged)
    resultCount = Property(int, _get_result_count, notify=resultsChanged)
    # matches before MAX_RESULTS cut the list; equals resultCount when nothing was cut
    totalCount = Property(int, _get_total_count, notify=resultsChanged)
    sectioned = Property(bool, _get_sectioned, notify=resultsChanged)

    # ------------------------------------------------------------------ keyboard
    @SafeSlot(int)
    def move(self, delta: int) -> None:
        """Move the selection by ``delta`` rows, wrapping around at the ends."""
        count = len(self._results)
        if not count:
            return
        self.set_current_index((self._current + delta) % count)

    @SafeSlot(int)
    def move_page(self, delta: int) -> None:
        """Move the selection by ``delta`` rows without wrapping."""
        self.set_current_index(max(0, self._current + delta))

    @SafeSlot(int)
    def cycle_scope(self, step: int = 1) -> None:
        """Switch to the next (``step=1``) or previous (``step=-1``) scope."""
        ids = [s[0] for s in SCOPES]
        self.set_scope(ids[(ids.index(self._scope) + step) % len(ids)])

    @SafeSlot()
    def request_dismiss(self) -> None:
        """Ask the hosting overlay to close the palette without running anything."""
        self.dismissRequested.emit()

    @SafeSlot()
    def clear_scope(self) -> None:
        """Backspace in an empty search field drops the scope filter."""
        if self._scope != "all":
            self.set_scope("all")

    def empty_text(self) -> str:
        """Message shown when there are no results."""
        if self._results:
            return ""
        label = dict((s[0], s[1]) for s in SCOPES)[self._scope].lower()
        if self._query:
            where = "" if self._scope == "all" else f" in {label}"
            return f"No matches for “{self._query}”{where}"
        return f"No {label} available"

    @SafeSlot(int)
    def execute(self, index: int = -1) -> None:
        """Run the result at ``index`` (the selected one by default).

        :attr:`accepted` is emitted first so the view can close, unless the command keeps the
        palette open; the command itself runs on the next event-loop turn.
        """
        if index < 0:
            index = self._current
        if not 0 <= index < len(self._results):
            return
        command = self._results[index]
        if not command.enabled:
            return
        if command.uid in self._by_uid:  # rows made from the query itself are not remembered
            if command.uid in self._recent:
                self._recent.remove(command.uid)
            self._recent.insert(0, command.uid)
            del self._recent[20:]
        self._pending = command
        if not command.keep_open:
            self.accepted.emit(command.uid)
        QTimer.singleShot(0, self._run_pending)

    @SafeSlot(popup_error=True)
    def _run_pending(self) -> None:
        command, self._pending = self._pending, None
        if command is not None:
            command.callback()

    def reset(self) -> None:
        """Clear the query and scope, as done whenever the palette opens."""
        self._query = ""
        self._scope = "all"
        self.queryChanged.emit()
        self.scopeChanged.emit()

    # ------------------------------------------------------------------ search
    def _in_scope(self, command: PaletteCommand) -> bool:
        if self._scope == "all":
            return True
        return CATEGORIES.get(command.category, ("", "actions"))[1] == self._scope

    def _live_commands(self) -> list[PaletteCommand]:
        commands: list[PaletteCommand] = []
        for source in self._query_sources:
            try:
                commands.extend(source(self._query, self._scope))
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(f"Command palette query source {source!r} failed: {exc}")
        return commands

    def _search(self, keep_selection: bool = False) -> None:
        started = time.perf_counter()
        selected = None
        if keep_selection and 0 <= self._current < len(self._results):
            selected = self._results[self._current].uid
        candidates = [cmd for cmd in self._commands if self._in_scope(cmd)]
        positions: dict[str, list[int]] = {}
        sections: dict[str, str] = {}
        if not self._query:
            results = self._browse(candidates, sections)
            total = len(candidates) if self._scope != "all" else len(results)
        else:
            tokens = self._query.split()
            ranked = []
            recent_rank = {uid: i for i, uid in enumerate(self._recent)}
            for order, cmd in enumerate(candidates):
                match = score_command(tokens, cmd)
                if match is None:
                    continue
                score, pos = match
                if cmd.uid in recent_rank:
                    score += 20 - 2 * recent_rank[cmd.uid]
                ranked.append((-score, order, cmd))
                positions[cmd.uid] = pos
            ranked.sort(key=lambda item: (item[0], item[1]))
            live = self._live_commands()
            results = live + [cmd for _score, _order, cmd in ranked[: MAX_RESULTS - len(live)]]
            total = len(live) + len(ranked)
        self._results = results
        self._total = total
        self._positions = positions
        self._sections = sections
        self._publish()
        uids = [cmd.uid for cmd in results]
        self._current = -1
        self.set_current_index(uids.index(selected) if selected in uids else 0)
        self.last_search_ms = (time.perf_counter() - started) * 1000

    def _browse(self, candidates: list[PaletteCommand], sections: dict[str, str]):
        """Results for an empty query: recent commands, then a few of each category."""
        results: list[PaletteCommand] = []
        seen: set[str] = set()
        if self._scope == "all":
            in_scope = {cmd.uid for cmd in candidates}
            for uid in self._recent:
                if uid in in_scope and len(results) < RECENT_LIMIT:
                    results.append(self._by_uid[uid])
                    sections[uid] = "Recent"
                    seen.add(uid)
        limit = EMPTY_QUERY_SECTION_LIMIT if self._scope == "all" else MAX_RESULTS
        for category, (label, _scope) in CATEGORIES.items():
            count = 0
            for cmd in candidates:
                if cmd.category != category or cmd.uid in seen:
                    continue
                if count >= limit:
                    break
                results.append(cmd)
                sections[cmd.uid] = label
                seen.add(cmd.uid)
                count += 1
        return results

    def _publish(self) -> None:
        rows = []
        for cmd in self._results:
            pos = self._positions.get(cmd.uid, [])
            rows.append(
                {
                    "uid": cmd.uid,
                    "title": cmd.title,
                    "positions": pos,
                    "subtitle": cmd.subtitle,
                    "icon": cmd.icon,
                    "category": CATEGORIES.get(cmd.category, (cmd.category, ""))[0],
                    "section": self._sections.get(cmd.uid, ""),
                    "shortcut": cmd.shortcut,
                    "hint": cmd.hint,
                    "enabled": cmd.enabled,
                    "tone": cmd.tone,
                }
            )
        self.model.set_items(rows)
        self.resultsChanged.emit()
