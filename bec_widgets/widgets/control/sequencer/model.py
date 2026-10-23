"""Plain-data helpers for scan sequencer documents.

The scan sequencer backend (``bec_lib.scan_sequencer``) receives a JSON document made of
nested nodes. The editors in this package keep that document as plain dictionaries so all
concepts share one data format, and use the helpers here to create nodes, walk the tree,
describe steps in plain language and count what a sequence will do.
"""

from __future__ import annotations

import copy
import itertools
import json
from dataclasses import dataclass, field
from typing import Any, Iterator

LOOP_TYPES = ("repeat", "for_each", "while")
CONTAINER_TYPES = ("sequence", *LOOP_TYPES)

# Friendly names for the step kinds shown to users.
KIND_TITLES = {
    "set": "Move",
    "scan_call": "Run scan",
    "repeat": "Repeat",
    "for_each": "For each value",
    "while": "While moving",
    "sequence": "Group",
    "component_call": "Saved block",
}


def empty_document(doc_id: str = "new_sequence") -> dict:
    """Return a sequence document with an empty root group.

    Args:
        doc_id (str): Document identity.

    Returns:
        dict: Sequence document accepted by the backend.
    """
    return {
        "schema_version": 1,
        "type": "sequence",
        "id": doc_id,
        "revision": 1,
        "root": {"id": "root", "type": "sequence", "children": []},
    }


def example_document() -> dict:
    """Return the shared example: two rounds over two sample positions, one scan at each.

    Returns:
        dict: Sequence document.
    """
    doc = empty_document("alternating_positions")
    loop = for_each_node("position", [1, -1], [move_node("samx", ref("position"))])
    loop["body"]["children"].append(
        scan_node("line_scan", ["samy", -2, 2], {"steps": 20, "exp_time": 0.1, "relative": True})
    )
    doc["root"]["children"] = [repeat_node(2, [loop])]
    return normalize(doc)


# ---------------------------------------------------------------------------------------------
# Node construction
# ---------------------------------------------------------------------------------------------
_counter = itertools.count(1)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{next(_counter)}"


def ref(name: str) -> dict:
    """Reference a loop variable.

    Args:
        name (str): Loop variable name.

    Returns:
        dict: Reference expression.
    """
    return {"ref": name}


def is_ref(value: Any) -> bool:
    """Return whether a value is a loop-variable reference."""
    return isinstance(value, dict) and set(value) == {"ref"}


def group_node(children: list[dict] | None = None) -> dict:
    """Create a group of steps that run in order."""
    return {"id": _new_id("group"), "type": "sequence", "children": list(children or [])}


def move_node(device: str, value: Any, wait: bool = True, bind_status: str | None = None) -> dict:
    """Create a Set node for a device or signal."""
    node = {"id": _new_id("move"), "type": "set", "device": device, "value": value, "wait": wait}
    if bind_status:
        node["bind_status"] = bind_status
    return node


def scan_node(name: str, positional: list | None = None, arguments: dict | None = None) -> dict:
    """Create a scan call."""
    return {
        "id": _new_id("scan"),
        "type": "scan_call",
        "name": name,
        "positional": list(positional or []),
        "arguments": dict(arguments or {}),
    }


def repeat_node(count: int, children: list[dict] | None = None) -> dict:
    """Create a repeat loop with a group body."""
    return {"id": _new_id("repeat"), "type": "repeat", "count": count, "body": group_node(children)}


def for_each_node(variable: str, values: list, children: list[dict] | None = None) -> dict:
    """Create a for-each loop with a group body."""
    return {
        "id": _new_id("for_each"),
        "type": "for_each",
        "variable": variable,
        "values": list(values),
        "body": group_node(children),
    }


def while_moving_nodes(device: str, value: Any, children: list[dict] | None = None) -> list[dict]:
    """Create the two nodes behind "keep doing this while a motor moves".

    The first node starts the move without waiting and binds its status, the second loops
    while that status is not done.

    Returns:
        list[dict]: The start-move node and the while loop.
    """
    status = _new_id("motion")
    start = move_node(device, value, wait=False, bind_status=status)
    loop = {
        "id": _new_id("while"),
        "type": "while",
        "condition": {
            "type": "not",
            "operand": {"type": "status_field", "status_ref": status, "field": "done"},
        },
        "body": group_node(children),
    }
    return [start, loop]


def new_step(kind: str, *, device: str = "samx", scan: str = "line_scan") -> list[dict]:
    """Create default nodes for a step kind picked in an editor.

    Args:
        kind (str): One of the keys of ``KIND_TITLES`` (``while`` creates two nodes).
        device (str): Default device for moves.
        scan (str): Default scan name.

    Returns:
        list[dict]: New nodes to insert.
    """
    if kind == "set":
        return [move_node(device, 0)]
    if kind == "scan_call":
        return [scan_node(scan)]
    if kind == "repeat":
        return [repeat_node(2)]
    if kind == "for_each":
        return [for_each_node("position", [0, 1])]
    if kind == "while":
        return while_moving_nodes(device, 5)
    if kind == "sequence":
        return [group_node()]
    raise ValueError(f"Unknown step kind: {kind}")


# ---------------------------------------------------------------------------------------------
# Tree access
# ---------------------------------------------------------------------------------------------
def children_of(node: dict) -> list[dict]:
    """Return the list holding a node's direct children (empty for leaves)."""
    if node.get("type") == "sequence":
        return node.setdefault("children", [])
    if node.get("type") in LOOP_TYPES:
        return children_of(node["body"])
    return []


def is_container(node: dict) -> bool:
    """Return whether a node can hold steps."""
    return node.get("type") in CONTAINER_TYPES


def normalize(doc: dict) -> dict:
    """Wrap every loop body in a group, so editors can always add more than one step.

    Args:
        doc (dict): Sequence document; modified in place.

    Returns:
        dict: The same document.
    """

    def visit(node: dict):
        if node.get("type") in LOOP_TYPES and node["body"].get("type") != "sequence":
            node["body"] = group_node([node["body"]])
        for child in children_of(node):
            visit(child)

    if doc["root"].get("type") != "sequence":
        doc["root"] = {"id": "root", "type": "sequence", "children": [doc["root"]]}
    visit(doc["root"])
    return doc


def walk(node: dict, depth: int = 0) -> Iterator[tuple[dict, int, dict]]:
    """Yield ``(node, depth, parent)`` for every node below ``node`` (not ``node`` itself)."""
    for child in children_of(node):
        yield child, depth, node
        yield from walk(child, depth + 1)


def find(root: dict, node_id: str) -> tuple[dict | None, dict | None]:
    """Find a node and its container by id.

    Returns:
        tuple[dict | None, dict | None]: The node and the node whose children list holds it.
    """
    if root.get("id") == node_id:
        return root, None
    for node, _depth, parent in walk(root):
        if node.get("id") == node_id:
            return node, parent
    return None, None


def remove(root: dict, node_id: str) -> dict | None:
    """Remove a node by id; return it."""
    node, parent = find(root, node_id)
    if node is None or parent is None:
        return None
    children_of(parent).remove(node)
    return node


def insert(root: dict, nodes: list[dict], parent_id: str | None = None, index: int = -1) -> None:
    """Insert nodes into a container; ``index=-1`` appends."""
    parent, _ = find(root, parent_id) if parent_id else (root, None)
    if parent is None or not is_container(parent):
        parent = root
    target = children_of(parent)
    if index < 0 or index > len(target):
        index = len(target)
    target[index:index] = nodes


def ancestors(root: dict, node_id: str) -> list[dict]:
    """Return the containers enclosing a node, outermost first (root excluded)."""
    path: list[dict] = []

    def visit(node: dict, trail: list[dict]) -> bool:
        for child in children_of(node):
            if child.get("id") == node_id:
                path.extend(trail)
                return True
            if visit(child, trail + [child]):
                return True
        return False

    visit(root, [])
    return path


def visible_variables(root: dict, node_id: str) -> list[str]:
    """Return loop variable names usable at a node."""
    return [n["variable"] for n in ancestors(root, node_id) if n.get("type") == "for_each"]


def status_owner(root: dict, status: str) -> dict | None:
    """Return the Set node that binds a status name."""
    for node, _depth, _parent in walk(root):
        if node.get("type") == "set" and node.get("bind_status") == status:
            return node
    return None


def while_status(node: dict) -> str | None:
    """Return the status a "while moving" loop watches, if it uses that pattern."""
    cond = node.get("condition")
    if isinstance(cond, dict) and cond.get("type") == "not":
        operand = cond.get("operand")
        if isinstance(operand, dict) and operand.get("type") == "status_field":
            return operand.get("status_ref")
    return None


def clone(node: dict) -> dict:
    """Deep-copy a node and give every copied node a new id."""
    copied = copy.deepcopy(node)
    statuses: dict[str, str] = {}

    def visit(n: dict):
        n["id"] = _new_id(n["id"].rsplit("_", 1)[0] or "step")
        if n.get("bind_status"):
            statuses[n["bind_status"]] = _new_id("motion")
            n["bind_status"] = statuses[n["bind_status"]]
        if n.get("type") in LOOP_TYPES:
            n["body"]["id"] = _new_id("group")
        for child in children_of(n):
            visit(child)

    visit(copied)
    return copied


# ---------------------------------------------------------------------------------------------
# Plain-language text
# ---------------------------------------------------------------------------------------------
def scan_title(name: str) -> str:
    """Turn ``line_scan`` into ``Line scan``."""
    words = name.replace("_", " ").strip()
    return words[:1].upper() + words[1:]


def format_value(value: Any) -> str:
    """Show a value the way a scientist would write it."""
    if is_ref(value):
        return f"each {value['ref']}"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, dict) and value.get("type") == "literal":
        return format_value(value.get("value"))
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def format_values(values: Any, limit: int = 6) -> str:
    """Show a list of loop values, shortened when long."""
    if not isinstance(values, list):
        return format_value(values)
    shown = [format_value(v) for v in values[:limit]]
    if len(values) > limit:
        shown.append(f"… ({len(values)} values)")
    return ", ".join(shown) if shown else "no values"


def scan_details(node: dict, entries: dict | None = None) -> str:
    """Summarize scan arguments, e.g. ``samy -2 → 2 · 20 steps · 0.1 s``."""
    entries = entries or {}
    info = entries.get(node.get("name"), {})
    parts = []
    positional = node.get("positional") or []
    bundle = (info.get("arg_bundle_size") or {}).get("bundle") or 0
    if bundle == 3 and len(positional) % 3 == 0:
        for i in range(0, len(positional), 3):
            dev, start, stop = positional[i : i + 3]
            parts.append(f"{format_value(dev)} {format_value(start)} → {format_value(stop)}")
    elif positional:
        parts.append(", ".join(format_value(v) for v in positional))
    args = node.get("arguments") if isinstance(node.get("arguments"), dict) else {}
    for key, value in args.items():
        if key == "metadata" or value in (None, ""):
            continue
        if key == "steps":
            parts.append(f"{format_value(value)} steps")
        elif key in ("exp_time", "interval") and isinstance(value, (int, float)):
            parts.append(f"{value:g} s {'exposure' if key == 'exp_time' else 'interval'}")
        elif key == "relative":
            parts.append("relative" if value else "absolute")
        elif key in ("points",):
            parts.append(f"{format_value(value)} points")
        else:
            parts.append(f"{key.replace('_', ' ')} {format_value(value)}")
    return " · ".join(parts)


def sentence(node: dict, root: dict | None = None, entries: dict | None = None) -> str:
    """Describe one step in plain language (without its children).

    Args:
        node (dict): The step.
        root (dict | None): Document root, used to name the motor a "while" waits for.
        entries (dict | None): Advertised scan info by scan name.

    Returns:
        str: One sentence.
    """
    kind = node.get("type")
    if kind == "set":
        target = node.get("device", "?")
        value = format_value(node.get("value"))
        verb = "Set" if "." in target else "Move"
        if node.get("wait", True):
            return f"{verb} {target} to {value}"
        return f"Start moving {target} to {value} (don't wait)"
    if kind == "scan_call":
        details = scan_details(node, entries)
        return f"Run {scan_title(node.get('name', 'scan')).lower()}" + (
            f": {details}" if details else ""
        )
    if kind == "repeat":
        count = node.get("count", 1)
        return f"Repeat {count} time{'s' if count != 1 else ''}"
    if kind == "for_each":
        return f"For each {node.get('variable')}: {format_values(node.get('values'))}"
    if kind == "while":
        status = while_status(node)
        owner = status_owner(root, status) if (root and status) else None
        if owner is not None:
            return f"While {owner.get('device')} is still moving"
        return "While the condition holds"
    if kind == "component_call":
        definition = node.get("definition", {})
        return f"Use saved block “{definition.get('id')}”"
    if kind == "sequence":
        return "Group"
    return kind or "?"


# ---------------------------------------------------------------------------------------------
# Counting and preview
# ---------------------------------------------------------------------------------------------
@dataclass
class Summary:
    """What a sequence will do, counted without running it."""

    scans: int = 0
    moves: int = 0
    open_ended: bool = False
    empty_loops: list[str] = field(default_factory=list)

    def text(self) -> str:
        """Short summary such as ``8 scans · 4 moves``."""
        if not self.scans and not self.moves and not self.open_ended:
            return "Nothing to run yet"
        plus = "+" if self.open_ended else ""
        parts = [f"{self.scans}{plus} scan{'s' if self.scans != 1 else ''}"]
        parts.append(f"{self.moves} move{'s' if self.moves != 1 else ''}")
        if self.open_ended:
            parts.append("repeats while a motor moves")
        return " · ".join(parts)


def summarize(root: dict) -> Summary:
    """Count scans and moves, multiplying through loops."""
    summary = Summary()

    def visit(node: dict, factor: int):
        kind = node.get("type")
        if kind == "scan_call":
            summary.scans += factor
        elif kind == "set":
            summary.moves += factor
        if kind == "repeat":
            factor *= max(int(node.get("count", 1)), 0)
        elif kind == "for_each":
            values = node.get("values")
            factor *= len(values) if isinstance(values, list) else 1
        elif kind == "while":
            summary.open_ended = True
        if kind in LOOP_TYPES and not children_of(node):
            summary.empty_loops.append(node["id"])
        for child in children_of(node):
            visit(child, factor)

    for child in children_of(root):
        visit(child, 1)
    return summary


@dataclass
class TimelineItem:
    """One concrete action in the order it will run."""

    node_id: str
    kind: str
    text: str
    context: str


def timeline(root: dict, entries: dict | None = None, limit: int = 300) -> list[TimelineItem]:
    """Unroll loops into the list of concrete actions, substituting loop values.

    While loops are shown once, marked as repeating.
    """
    items: list[TimelineItem] = []

    def subst(value, env):
        if is_ref(value) and value["ref"] in env:
            return env[value["ref"]]
        if isinstance(value, list):
            return [subst(v, env) for v in value]
        if isinstance(value, dict) and not value.get("type") == "literal":
            return {k: subst(v, env) for k, v in value.items()}
        return value

    def visit(node: dict, env: dict, context: list[str]) -> bool:
        if len(items) >= limit:
            return False
        kind = node.get("type")
        ctx = " · ".join(context)
        if kind in ("set", "scan_call", "component_call"):
            concrete = dict(node)
            for key in ("value", "positional", "arguments"):
                if key in concrete:
                    concrete[key] = subst(concrete[key], env)
            items.append(TimelineItem(node["id"], kind, sentence(concrete, root, entries), ctx))
            return True
        if kind == "repeat":
            count = int(node.get("count", 1))
            for i in range(count):
                for child in children_of(node):
                    if not visit(child, env, context + [f"round {i + 1}/{count}"]):
                        return False
            return True
        if kind == "for_each":
            values = node.get("values") if isinstance(node.get("values"), list) else []
            for value in values:
                inner = {**env, node["variable"]: subst(value, env)}
                label = f"{node['variable']} = {format_value(inner[node['variable']])}"
                for child in children_of(node):
                    if not visit(child, inner, context + [label]):
                        return False
            return True
        if kind == "while":
            for child in children_of(node):
                if not visit(child, env, context + ["repeats while moving"]):
                    return False
            return True
        for child in children_of(node):
            if not visit(child, env, context):
                return False
        return True

    for child in children_of(root):
        if not visit(child, {}, []):
            break
    return items
