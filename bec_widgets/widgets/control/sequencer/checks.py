"""Checks that run in the editor before the backend sees a sequence.

The backend validates scan arguments and devices but stops at the first error and does not
know about steps that are simply unfinished. These checks find every unfinished step at
once and also catch motor positions outside the soft limits, so every concept can mark each
step that needs attention.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.backend import Problem

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.control.sequencer.backend import SequencerBackend


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _format_limit(value: float) -> str:
    return f"{value:g}"


def _check_set(node: dict, root: dict, backend: SequencerBackend, known: set[str]) -> str:
    device = (node.get("device") or "").strip()
    if not device:
        return "Choose a motor"
    if known and device.split(".", maxsplit=1)[0] not in known:
        return f"There is no device called “{device}”"
    value = node.get("value")
    if value is None or value == "":
        return "Enter a position" if backend.is_motor(device) else "Enter a value"
    if model.is_ref(value):
        values = model.loop_values(root, node["id"], value["ref"])
        if values is None:
            return f"“{value['ref']}” is only known inside its “For each {value['ref']}” loop"
    else:
        values = [value]
    if not backend.is_motor(device):
        return ""
    if any(not _is_number(v) for v in values):
        return f"{device} needs a number"
    limits = backend.limits(device)
    if limits is not None:
        low, high = limits
        outside = [v for v in values if not low <= v <= high]
        if outside:
            return (
                f"{model.format_value(outside[0])} is outside the limits of {device}"
                f" ({_format_limit(low)} to {_format_limit(high)})"
            )
    return ""


def _is_device_input(kind) -> bool:
    if isinstance(kind, dict):  # annotated inputs: {"Annotated": {"type": "float", ...}}
        kind = (kind.get("Annotated") or {}).get("type", "")
    return "device" in str(kind).lower()


def _device_positions(info: dict) -> list[int]:
    """Positions inside one argument bundle that hold a device name."""
    arg_input = info.get("arg_input") or {}
    return [i for i, kind in enumerate(arg_input.values()) if _is_device_input(kind)]


def _check_scan(node: dict, entries: dict, known: set[str]) -> str:
    name = node.get("name") or ""
    if not name:
        return "Choose a scan"
    if entries and name not in entries:
        return f"This beamline has no scan called “{name}”"
    info = entries.get(name, {})
    bundle = (info.get("arg_bundle_size") or {}).get("bundle") or 0
    positional = node.get("positional") or []
    if bundle and not positional:
        return "Add at least one motor to the scan"
    if bundle:
        for offset in _device_positions(info):
            for value in positional[offset::bundle]:
                if model.is_ref(value):
                    continue
                if not value:
                    return "Choose a motor for the scan"
                if known and str(value).split(".", maxsplit=1)[0] not in known:
                    return f"There is no device called “{value}”"
    return ""


def check(root: dict, backend: SequencerBackend) -> list[Problem]:
    """Find unfinished steps and positions outside the motor limits.

    Args:
        root (dict): Root group of the document.
        backend (SequencerBackend): Gives the scans, devices and limits of the beamline.

    Returns:
        list[Problem]: One problem per step that needs attention, in document order.
    """
    entries = backend.scan_entries()
    known = set(backend.device_names())
    problems: list[Problem] = []
    for node, _depth, _parent in model.walk(root):
        kind = node.get("type")
        message = ""
        if kind == "set":
            message = _check_set(node, root, backend, known)
        elif kind == "scan_call":
            message = _check_scan(node, entries, known)
        elif kind == "for_each":
            if not (node.get("variable") or "").strip():
                message = "Give the value a name"
            elif not node.get("values"):
                message = "Enter at least one value"
        elif kind == "repeat":
            count = node.get("count")
            if not isinstance(count, int) or isinstance(count, bool) or count < 1:
                message = "Repeat at least once"
        elif kind == "while":
            status = model.while_status(node)
            if status is None or model.status_owner(root, status) is None:
                message = "This loop has no motor to wait for"
        elif kind == "component_call":
            message = "Saved blocks cannot be used in this editor yet"
        if not message and kind in model.LOOP_TYPES and not model.children_of(node):
            message = "This loop has no steps inside"
        if message:
            problems.append(Problem(node["id"], message))
    return problems
