"""
Small visual building blocks of the scan widgets: labels, chips and the stage bar.
"""

from __future__ import annotations

from typing import Any

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QSizePolicy, QWidget

from bec_widgets.utils.theme_utils import css, theme_colors
from bec_widgets.widgets.progress.stage_bar import Chip, Tone

# Keyword arguments that every scan request carries and that say nothing about the scan itself.
_HIDDEN_KWARGS = {
    "system_config",
    "user_metadata",
    "scan_queue",
    "metadata",
    "file_suffix",
    "file_directory",
    "monitored",
    "readout_priority",
    "optim_trajectory",
}


def scan_display_name(
    user_metadata: dict | None, scan_type: str | None, fallback: str = "scan"
) -> str:
    """
    The name a scan is shown with everywhere: the scan_name the user gave in its metadata
    ("My Scan"), else the scan type ("line_scan").

    Args:
        user_metadata(dict): The scan's user metadata.
        scan_type(str): The scan type, e.g. "line_scan".
        fallback(str): Shown when neither is known.
    """
    name = (user_metadata or {}).get("scan_name")
    return str(name) if name else (scan_type or fallback)


def format_value(value: Any) -> str:
    """Format one argument or metadata value compactly."""
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, (list, tuple)):
        return " → ".join(format_value(v) for v in value) if len(value) <= 3 else f"[{len(value)}]"
    return str(value)


def _kwargs_parts(kwargs: dict) -> list[str]:
    parts = []
    for key, value in (kwargs or {}).items():
        if key in _HIDDEN_KWARGS or value is None or isinstance(value, dict) or value is False:
            continue
        parts.append(key if value is True else f"{key} {format_value(value)}")
    return parts


def scan_bundle_names(scans: Any, scan_type: str | None) -> list[str]:
    """
    The names of the values of one argument bundle of a scan, after its device, as the scan
    server publishes them, e.g. ["start", "stop", "steps"] for a grid scan.

    Args:
        scans(Any): The client's scans object.
        scan_type(str): The scan type, e.g. "grid_scan".

    Returns:
        list[str]: The names; empty for a scan without bundles or when the scan is not known.
    """
    info = getattr(getattr(scans, scan_type or "", None), "scan_info", None)
    arg_input = info.get("arg_input") if isinstance(info, dict) else None
    return list(arg_input)[1:] if isinstance(arg_input, dict) else []


def _bundle_values(values: Any, names: list[str] | None) -> str:
    """
    Format the values of one argument bundle: start → stop for a range, any other value with its
    name ("-5 → 5 steps 10"). Without names only a pair is taken for a range.
    """
    values = list(values) if isinstance(values, (list, tuple)) else [values]
    if not names or len(names) != len(values):
        separator = " → " if len(values) == 2 else " "
        return separator.join(format_value(v) for v in values)
    named = dict(zip(names, values))
    parts = []
    if "start" in named and "stop" in named:
        parts.append(f"{format_value(named.pop('start'))} → {format_value(named.pop('stop'))}")
    elif len(named) == 1:
        return format_value(values[0])  # the one value of a move or a list of positions
    parts.extend(f"{name} {format_value(value)}" for name, value in named.items())
    return " ".join(parts)


def _rpc_value(value: Any) -> str:
    return f"{value:.4g}" if isinstance(value, float) else repr(value)


def rpc_call(kwargs: dict | None) -> str:
    """
    The call of a device_rpc request as it reads in code, e.g. "samx.set(5, wait=True)".

    Args:
        kwargs(dict): The request's keyword arguments, with device, func and its arguments.

    Returns:
        str: The call; empty when this is not a device RPC.
    """
    kwargs = kwargs or {}
    device, func = kwargs.get("device"), kwargs.get("func")
    if not device or not func:
        return ""
    call_args = [_rpc_value(arg) for arg in kwargs.get("func_args") or []]
    func_kwargs = kwargs.get("func_kwargs") or {}
    call_args += [f"{key}={_rpc_value(value)}" for key, value in func_kwargs.items()]
    return f"{device}.{func}({', '.join(call_args)})"


def args_summary(parameter: dict | None, names: list[str] | None = None) -> str:
    """
    Summarise the arguments of a scan request ("samx -5 → 5 · steps 50 · exp_time 0.1").

    Args:
        parameter(dict): ScanQueueMessage.parameter, with "args" and "kwargs".
        names(list[str]): The names of a bundle's values, from scan_bundle_names.
    """
    parameter = parameter or {}
    call = rpc_call(parameter.get("kwargs"))
    if call:
        return call
    parts: list[str] = []
    args = parameter.get("args")
    if isinstance(args, dict):
        for device, values in args.items():
            parts.append(f"{device} {_bundle_values(values, names)}".strip())
    elif isinstance(args, (list, tuple)):
        parts.extend(format_value(a) for a in args)
    parts.extend(_kwargs_parts(parameter.get("kwargs", {})))
    return " · ".join(p for p in parts if p)


def args_items(parameter: dict | None, names: list[str] | None = None) -> list[tuple[str, str]]:
    """
    Every argument of a scan request as its own (name, value) row, for detail views.

    Args:
        parameter(dict): ScanQueueMessage.parameter, with "args" and "kwargs".
        names(list[str]): The names of a bundle's values, from scan_bundle_names.
    """
    parameter = parameter or {}
    call = rpc_call(parameter.get("kwargs"))
    if call:
        return [("call", call)]
    items: list[tuple[str, str]] = []
    args = parameter.get("args")
    if isinstance(args, dict):
        for device, values in args.items():
            items.append((str(device), _bundle_values(values, names)))
    elif isinstance(args, (list, tuple)) and args:
        items.append(("args", " ".join(format_value(a) for a in args)))
    for key, value in (parameter.get("kwargs") or {}).items():
        if key in _HIDDEN_KWARGS or value is None or isinstance(value, dict):
            continue
        items.append((str(key), format_value(value)))
    return items


def request_inputs_summary(request_inputs: dict | None, names: list[str] | None = None) -> str:
    """
    Summarise ScanStatusMessage.request_inputs the same way as args_summary.

    Args:
        request_inputs(dict): The request inputs, with "arg_bundle", "inputs" and "kwargs".
        names(list[str]): The names of a bundle's values, from scan_bundle_names.
    """
    request_inputs = request_inputs or {}
    inputs = request_inputs.get("inputs") or {}
    call = rpc_call({**inputs, **(request_inputs.get("kwargs") or {})})
    if call:
        return call
    parts: list[str] = []
    bundle = list(request_inputs.get("arg_bundle") or [])
    if bundle and names and len(bundle) % (len(names) + 1) == 0:
        size = len(names) + 1
        for index in range(0, len(bundle), size):
            device, values = bundle[index], bundle[index + 1 : index + size]
            parts.append(f"{device} {_bundle_values(values, names)}")
    elif bundle:
        parts.append(" ".join(format_value(a) for a in bundle))
    for key, value in inputs.items():
        parts.append(f"{key} {format_value(value)}")
    parts.extend(_kwargs_parts(request_inputs.get("kwargs", {})))
    return " · ".join(p for p in parts if p)


def metadata_items(user_metadata: dict | None) -> list[tuple[str, str]]:
    """Return user metadata as (key, value) pairs worth showing, scan_name excluded."""
    items = []
    for key, value in (user_metadata or {}).items():
        if key == "scan_name" or str(key).startswith("_") or value in (None, "", {}, []):
            continue
        items.append((str(key), format_value(value)))
    return items


class ElidedLabel(QLabel):
    """
    A single-line label that elides its text instead of growing or clipping. When the text is
    cut, its tooltip shows the full text; otherwise the tooltip is left free for the parent.

    Setting the same text again does nothing, so a widget that re-renders several times a second
    neither re-elides nor touches the tooltip, and an open tooltip does not flicker.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._full = ""
        self._tooltip = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(10)
        self._elide()
        self.setText(text)

    def setText(self, text: str) -> None:  # pylint: disable=invalid-name
        """Set the full text; the shown text is elided to fit."""
        text = text or ""
        if text == self._full:
            return
        self._full = text
        self._elide()

    def full_text(self) -> str:
        """The text before eliding."""
        return self._full

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        width = max(10, self.width())
        shown = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, width)
        if shown != super().text():
            super().setText(shown)
        tooltip = self._full if shown != self._full else ""
        if tooltip != self._tooltip:
            self._tooltip = tooltip
            self.setToolTip(tooltip)


class MetaChip(Chip):
    """A metadata chip showing a muted key and its value."""

    def __init__(self, key: str, value: str, parent: QWidget | None = None):
        self._key = key
        self._value = value
        super().__init__("", Tone.NEUTRAL, parent)
        self.setToolTip(f"{key}: {value}")
        self._update_text()

    def _update_text(self) -> None:
        muted = css(theme_colors()["muted"])
        value = self._value if len(self._value) <= 28 else f"{self._value[:27]}…"
        self.setText(f"<span style='color:{muted}'>{self._key}</span>&nbsp;{value}")

    def refresh_style(self) -> None:
        super().refresh_style()
        if hasattr(self, "_key"):
            self._update_text()
