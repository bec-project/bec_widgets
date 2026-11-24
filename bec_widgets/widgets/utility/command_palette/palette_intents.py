"""Typed device commands of the command palette, e.g. ``samx 10`` or ``move samx by -0.5``.

:func:`parse_intent` turns the search text into a :class:`DeviceIntent` with a small fixed
grammar. It knows nothing about the devices; the palette resolves the device name, checks limits
and units and shows the result as a preview row that runs only on Enter.

Accepted forms (case-insensitive verbs, the device name is matched as typed)::

    samx 10              samx move 10        move samx to 10      mv samx 10
    samx = 10            samx to 10 mm       umv samx 10
    samx +2              samx += 2           move samx by -0.5    umvr samx 1     mvr samx -1
    samx?                where samx          wm samx              samx pos
    stop samx            samx stop

A leading ``+`` makes a move relative; a plain negative number stays absolute (``samx -2`` moves to
-2, as ``mv`` does in the BEC client).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal

from bec_widgets.widgets.utility.command_palette.palette_core import fuzzy_match

IntentKind = Literal["move", "where", "stop"]

ABSOLUTE_VERBS = frozenset({"move", "mv", "umv", "go", "goto", "set"})
RELATIVE_VERBS = frozenset({"mvr", "umvr", "tweak", "nudge"})
WHERE_VERBS = frozenset({"where", "wm", "pos", "position", "?"})
STOP_VERBS = frozenset({"stop", "halt"})
TO_WORDS = frozenset({"to", "=", "->", "at"})

_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?"
_NUMBER_RE = re.compile(rf"^{_NUMBER}$", re.IGNORECASE)
_NUMBER_UNIT_RE = re.compile(rf"^({_NUMBER})([a-zµ°%][\w/°]*)$", re.IGNORECASE)
_NAME_RE = re.compile(r"^[A-Za-z_][\w.]*$")
_UNIT_RE = re.compile(r"^[a-zµ°%][\w/°]*$", re.IGNORECASE)
_UNIT_ALIASES = {
    "°": "deg",
    "degree": "deg",
    "degrees": "deg",
    "µm": "um",
    "micron": "um",
    "microns": "um",
    "μm": "um",
}


@dataclass(frozen=True)
class DeviceIntent:
    """A typed device command, before the device name is resolved.

    Args:
        kind(IntentKind): ``"move"``, ``"where"`` or ``"stop"``.
        device(str): Device name as typed; may be a partial name.
        value(float | None): Target of a move, or the step of a relative move.
        relative(bool): Whether ``value`` is added to the current position.
        unit(str): Unit typed after the number, empty if none.
    """

    kind: IntentKind
    device: str
    value: float | None = None
    relative: bool = False
    unit: str = ""


def tokenize(text: str) -> list[str]:
    """Split ``text`` into words; ``=``, ``+=``, ``-=``, ``->`` and ``?`` are words of their own."""
    text = re.sub(r"(\+=|-=|->|\?|(?<![<>!+-])=)", r" \1 ", text)
    return text.split()


def _split_number(token: str) -> tuple[float, str] | None:
    """Return ``(value, unit)`` for ``"10"``, ``"-0.5"`` or ``"10mm"``, else None."""
    if _NUMBER_RE.match(token):
        return float(token), ""
    match = _NUMBER_UNIT_RE.match(token)
    if match:
        return float(match.group(1)), match.group(2)
    return None


def parse_intent(text: str) -> DeviceIntent | None:
    """Parse a typed device command.

    Args:
        text(str): Search text without the scope prefix.

    Returns:
        DeviceIntent | None: The command, or None if ``text`` is not one; the palette then
        searches as usual.
    """
    words = tokenize(text)
    if not words:
        return None

    kind: IntentKind | None = None
    relative = False
    verb = words[0].lower()
    if verb in ABSOLUTE_VERBS:
        kind = "move"
    elif verb in RELATIVE_VERBS:
        kind, relative = "move", True
    elif verb in WHERE_VERBS:
        kind = "where"
    elif verb in STOP_VERBS:
        kind = "stop"
    if kind is not None:
        words = words[1:]
        if kind == "where" and words[:1] == ["is"]:
            words = words[1:]
    if not words or not _NAME_RE.match(words[0]):
        return None
    device, rest = words[0], words[1:]

    if kind is None and rest:
        verb = rest[0].lower()
        if verb in ABSOLUTE_VERBS:
            kind, rest = "move", rest[1:]
        elif verb in RELATIVE_VERBS:
            kind, relative, rest = "move", True, rest[1:]
        elif verb in WHERE_VERBS:
            kind, rest = "where", rest[1:]
        elif verb in STOP_VERBS:
            kind, rest = "stop", rest[1:]

    if kind in ("where", "stop"):
        if rest == ["?"] and kind == "where":
            rest = []
        return DeviceIntent(kind=kind, device=device) if not rest else None

    # a move: [to|by|+=|-=] NUMBER [UNIT]
    explicit_absolute = False
    sign = 1.0
    if rest and rest[0].lower() in TO_WORDS:
        explicit_absolute, rest = True, rest[1:]
    elif rest and rest[0].lower() == "by":
        relative, rest = True, rest[1:]
    elif rest and rest[0] in ("+=", "-="):
        relative, sign, rest = True, (1.0 if rest[0] == "+=" else -1.0), rest[1:]
    if not rest or len(rest) > 2:
        return None
    number = _split_number(rest[0])
    if number is None:
        return None
    value, unit = number
    if len(rest) == 2:
        if unit or not _UNIT_RE.match(rest[1]):
            return None
        unit = rest[1]
    if rest[0].startswith("+") and not explicit_absolute:
        relative = True
    if relative and explicit_absolute:
        return None
    return DeviceIntent(
        kind="move", device=device, value=sign * value, relative=relative, unit=unit
    )


def resolve_device(query: str, names: Iterable[str], fuzzy: bool = True) -> list[str]:
    """Device names ``query`` may refer to, best first.

    An exact name (ignoring case) wins on its own. Otherwise every name starting with ``query``
    is returned, or with ``fuzzy`` every name the palette's fuzzy matcher accepts; one entry
    means the name is unambiguous.

    Args:
        query(str): Device name as typed, possibly partial (``"sax"``).
        names(Iterable[str]): Known device names.
        fuzzy(bool): Also accept partial names that are not a prefix.

    Returns:
        list[str]: Matching names; empty if nothing matches.
    """
    names = list(names)
    if query in names:
        return [query]
    folded = [name for name in names if name.lower() == query.lower()]
    if len(folded) == 1:
        return folded
    if not fuzzy:
        prefix = query.lower()
        return sorted((n for n in names if n.lower().startswith(prefix)), key=lambda n: (len(n), n))
    scored = []
    for name in names:
        match = fuzzy_match(query, name)
        if match is not None:
            scored.append((-match[0], name))
    scored.sort()
    return [name for _score, name in scored]


def units_match(typed: str, egu: str) -> bool:
    """Whether a typed unit names the device's engineering unit (``"deg"`` matches ``"°"``)."""
    return _UNIT_ALIASES.get(typed.lower(), typed.lower()) == _UNIT_ALIASES.get(
        egu.lower(), egu.lower()
    )
