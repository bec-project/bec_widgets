"""
Module providing fuzzy search utilities for the BEC widgets.

:func:`is_match` decides with a fuzzy ratio whether a row fits a text. :func:`match` and
:func:`best_matches` find names the way a user types them, with the order of the fits and
the matching letters, and :func:`close_names` offers names close to a text that fits none.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from thefuzz import fuzz

FUZZY_SEARCH_THRESHOLD = 80


def is_match(
    text: str, row_data: dict[str, Any], relevant_keys: list[str], enable_fuzzy: bool
) -> bool:
    """
    Check if the text matches any of the relevant keys in the row data.

    Args:
        text (str): The text to search for.
        row_data (dict[str, Any]): The row data to search in.
        relevant_keys (list[str]): The keys to consider for searching.
        enable_fuzzy (bool): Whether to use fuzzy matching.
    Returns:
        bool: True if a match is found, False otherwise.
    """
    for key in relevant_keys:
        data = str(row_data.get(key, "") or "")
        if enable_fuzzy:
            match_ratio = fuzz.partial_ratio(text.lower(), data.lower())
            if match_ratio >= FUZZY_SEARCH_THRESHOLD:
                return True
        else:
            if text.lower() in data.lower():
                return True
    return False


#: How a typed text fits a name, from the best fit to the widest one.
EXACT, PREFIX, WORD_PREFIX, PIECE, PIECES = range(5)
#: Cost of one more piece of a text cut into pieces: worse than any gap inside a name.
_PIECE_COST = 10_000


class Match(NamedTuple):
    """
    How a text fits a name.

    Attributes:
        rank (tuple[int, int, int, int]): The order of the fits, smaller is better: the way
            it fits (``EXACT`` to ``PIECES``), the cost of the pieces, the place of the first
            matching letter and the length of the name.
        positions (tuple[int, ...]): The matching letters of the name, by their index.
    """

    rank: tuple[int, int, int, int]
    positions: tuple[int, ...]


def _lower(text: str) -> str:
    """Lower case that keeps every character in its place (no letter becomes two)."""
    lowered = text.lower()
    if len(lowered) == len(text):
        return lowered
    return "".join(char.lower() if len(char.lower()) == 1 else char for char in text)


def word_starts(name: str) -> list[bool]:
    """
    Where the words of a name start.

    A word starts at the first letter, after a separator, at a capital after a small letter
    and where letters and digits change (``bpm | 4 | i``).

    Args:
        name (str): The name.

    Returns:
        list[bool]: For every character, whether a word starts there.
    """
    flags, previous = [], ""
    for char in name:
        if not char.isalnum():
            start = False
        elif not previous or not previous.isalnum():
            start = True
        elif char.isdigit() != previous.isdigit():
            start = True
        else:
            start = char.isupper() and previous.islower()
        flags.append(start)
        previous = char
    return flags


def _one_piece(text: str, name: str, starts: list[bool]) -> tuple[int, int] | None:
    """The way and place a text fits a name in one piece, preferring the start of a word."""
    first = name.find(text)
    if first < 0:
        return None
    if first == 0:
        return (EXACT if len(text) == len(name) else PREFIX), 0
    at = first
    while at >= 0:
        if starts[at]:
            return WORD_PREFIX, at
        at = name.find(text, at + 1)
    return PIECE, first


def _pieces(text: str, name: str, starts: list[bool]) -> tuple[int, tuple[int, ...]] | None:
    """
    The cheapest cut of a text into pieces that each start a word of the name, in order.

    Every piece costs ``_PIECE_COST`` and every letter the gap before it, so fewer pieces win
    first and the closest ones next.
    """
    at = -1
    for char in text:  # a cheap answer for the many names that do not fit
        at = name.find(char, at + 1)
        if at < 0:
            return None
    count = len(name)
    infinity = float("inf")
    # cost[j]: the best cost with the current letter of the text on name[j]
    cost = [
        (_PIECE_COST + j) if starts[j] and name[j] == text[0] else infinity for j in range(count)
    ]
    back: list[list[int]] = []
    for char in text[1:]:
        new = [infinity] * count
        came_from = [-1] * count
        # min of cost[k] - k over k < j - 1: where a new piece can follow
        best_shifted = infinity
        best_k = -1
        for j in range(1, count):
            if j >= 2 and cost[j - 2] - (j - 2) < best_shifted:
                best_shifted = cost[j - 2] - (j - 2)
                best_k = j - 2
            if name[j] != char:
                continue
            joined = cost[j - 1]  # the piece goes on
            parted = best_shifted + _PIECE_COST + (j - 1) if starts[j] else infinity
            if joined <= parted:
                new[j], came_from[j] = joined, j - 1
            else:
                new[j], came_from[j] = parted, best_k
        back.append(came_from)
        cost = new
    end = min(range(count), key=cost.__getitem__)
    if cost[end] == infinity:
        return None
    positions = [end]
    for came_from in reversed(back):
        positions.append(came_from[positions[-1]])
    positions.reverse()
    return int(cost[end]), tuple(positions)


def _match_one(text: str, name: str, starts: list[bool]) -> Match | None:
    """How one word of a typed text fits a lower-case name."""
    if len(text) > len(name):
        return None
    piece = _one_piece(text, name, starts)
    if piece is not None:
        kind, at = piece
        return Match((kind, 0, at, len(name)), tuple(range(at, at + len(text))))
    if len(text) < 2:
        return None
    pieces = _pieces(text, name, starts)
    if pieces is None:
        return None
    cost, positions = pieces
    return Match((PIECES, cost, positions[0], len(name)), positions)


def match(text: str, name: str) -> Match | None:
    """
    How a typed text fits a name, if it does.

    A text fits in one of five ways, from the best: the name is the text (``EXACT``), the name
    starts with it (``PREFIX``), a word of the name starts with it (``WORD_PREFIX``), the name
    contains it in one piece (``PIECE``), or the text cut into pieces starts words of the name
    in their order (``PIECES``: ``bp3`` in ``bpm3b``). Letters scattered inside words do not
    fit, and case does not matter. A text with spaces is several texts that must all fit.

    Args:
        text (str): What was typed.
        name (str): The name, for example of a signal.

    Returns:
        Match | None: The fit with its rank and matching letters, or None. An empty text fits
            every name, with no letters.
    """
    parts = _lower(text).split()
    if not parts:
        return Match((EXACT, 0, 0, 0), ())
    lowered = _lower(name)
    starts = word_starts(name)
    kind = cost = 0
    first = len(name)
    positions: set[int] = set()
    for part in parts:
        found = _match_one(part, lowered, starts)
        if found is None:
            return None
        kind = max(kind, found.rank[0])
        cost += found.rank[1]
        first = min(first, found.rank[2])
        positions.update(found.positions)
    return Match((kind, cost, first, len(name)), tuple(sorted(positions)))


def best_matches(text: str, names: list[str]) -> list[tuple[str, Match]]:
    """
    The names a typed text fits, the best fit first.

    Args:
        text (str): What was typed.
        names (list[str]): The names, in the order they are listed.

    Returns:
        list[tuple[str, Match]]: Each name that fits with its fit. Equal fits keep the order
            of ``names``.
    """
    found = [(name, fit) for name in names if (fit := match(text, name)) is not None]
    found.sort(key=lambda item: item[1].rank)
    return found


def close_names(text: str, names: list[str]) -> list[str]:
    """
    Names close to a text that may hold a typo, by the fuzzy ratio of :func:`is_match`.

    Meant for when :func:`match` fits no name: ``bmp4i`` offers ``bpm4i``.

    Args:
        text (str): What was typed; under three letters gives nothing.
        names (list[str]): The names.

    Returns:
        list[str]: The close names, the closest first.
    """
    lowered = _lower(text).strip()
    if len(lowered) < 3:
        return []
    scored = [(fuzz.partial_ratio(lowered, _lower(name)), name) for name in names]
    close = [(ratio, name) for ratio, name in scored if ratio >= FUZZY_SEARCH_THRESHOLD]
    close.sort(key=lambda item: -item[0])
    return [name for _ratio, name in close]
