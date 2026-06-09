from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from bec_lib import bec_logger
from qtpy.QtWidgets import QDoubleSpinBox, QSpinBox, QWidget

logger = bec_logger.logger

UNIT_TOOLTIP_PREFIXES = ("Units:", "Units from:")


def format_display_name(name: str) -> str:
    """Convert a raw argument name into a user-facing label."""
    parts = re.split(r"(_|\d+)", name)
    return " ".join(part.capitalize() for part in parts if part.isalnum()).strip()


def resolve_tooltip(scan_argument: Mapping[str, Any]) -> str | None:
    """Resolve explicit tooltip text, falling back to the description."""
    return scan_argument.get("tooltip") or scan_argument.get("description")


def ui_config_from_metadata(
    name: str,
    metadata: Mapping[str, Any],
    *,
    default: Any = None,
    input_type: Any = None,
    arg: bool = False,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Build the normalized scan-input item consumed by form widgets."""
    return {
        "arg": arg,
        "name": name,
        "type": input_type,
        "display_name": display_name or metadata.get("display_name") or format_display_name(name),
        "tooltip": resolve_tooltip(metadata),
        "default": default,
        "expert": metadata.get("expert", False),
        "hidden": metadata.get("hidden", False),
        "precision": metadata.get("precision"),
        "units": metadata.get("units"),
        "reference_units": metadata.get("reference_units"),
        "reference_limits": metadata.get("reference_limits"),
        "gt": metadata.get("gt"),
        "ge": metadata.get("ge"),
        "lt": metadata.get("lt"),
        "le": metadata.get("le"),
        "alternative_group": metadata.get("alternative_group"),
    }


def unit_tooltip(item: Mapping[str, Any], units: str | None = None) -> str | None:
    """Build tooltip text from scan argument unit metadata."""
    tooltip = item.get("tooltip")
    reference_units = item.get("reference_units")
    units = units or item.get("units")

    tooltip_parts = [tooltip] if tooltip else []
    if units:
        tooltip_parts.append(f"Units: {units}")
    elif reference_units:
        tooltip_parts.append(f"Units from: {reference_units}")
    if tooltip_parts:
        return "\n".join(str(part) for part in tooltip_parts)
    return None


def strip_unit_tooltip(tooltip: str) -> str:
    """Remove unit lines added by :func:`apply_unit_metadata`."""
    return "\n".join(
        line for line in tooltip.splitlines() if not line.startswith(UNIT_TOOLTIP_PREFIXES)
    ).strip()


def apply_unit_metadata(widget: QWidget, item: Mapping[str, Any], units: str | None = None) -> None:
    """Apply unit tooltip text and numeric suffix metadata to a widget."""
    units = units or item.get("units")
    tooltip = unit_tooltip(item, units)
    existing_tooltip = strip_unit_tooltip(widget.toolTip())
    base_tooltip = item.get("tooltip")
    if base_tooltip and existing_tooltip == base_tooltip:
        existing_tooltip = ""

    if tooltip:
        widget.setToolTip(f"{existing_tooltip}\n{tooltip}" if existing_tooltip else tooltip)
    else:
        widget.setToolTip(existing_tooltip)

    if hasattr(widget, "setSuffix"):
        widget.setSuffix(f" {units}" if units else "")


def device_units(device: object) -> str | None:
    """Return engineering units from a BEC device object when available."""
    egu = getattr(device, "egu", None)
    if not callable(egu):
        return None
    try:
        return egu()
    except Exception:
        logger.exception("Failed to fetch engineering units from device %s", device)
        return None


def apply_numeric_precision(widget: QWidget, item: Mapping[str, Any]) -> None:
    """Apply decimal precision metadata to spinboxes supporting ``setDecimals``."""
    if not hasattr(widget, "setDecimals"):
        return

    precision = item.get("precision")
    if precision is None:
        return

    try:
        widget.setDecimals(max(0, int(precision)))
    except (TypeError, ValueError):
        logger.warning(
            "Ignoring invalid precision %r for parameter %s", precision, item.get("name")
        )


def apply_numeric_limits(widget: QWidget, item: Mapping[str, Any]) -> None:
    """Apply ``gt/ge/lt/le`` numeric bounds to Qt spinboxes."""
    if isinstance(widget, QSpinBox) and not isinstance(widget, QDoubleSpinBox):
        minimum = -2147483647
        maximum = 2147483647
        if item.get("ge") is not None:
            minimum = int(item["ge"])
        if item.get("gt") is not None:
            minimum = int(item["gt"]) + 1
        if item.get("le") is not None:
            maximum = int(item["le"])
        if item.get("lt") is not None:
            maximum = int(item["lt"]) - 1
        widget.setRange(minimum, maximum)
        return

    if isinstance(widget, QDoubleSpinBox):
        minimum = -float("inf")
        maximum = float("inf")
        step = 10 ** (-widget.decimals())
        if item.get("ge") is not None:
            minimum = float(item["ge"])
        if item.get("gt") is not None:
            minimum = float(item["gt"]) + step
        if item.get("le") is not None:
            maximum = float(item["le"])
        if item.get("lt") is not None:
            maximum = float(item["lt"]) - step
        widget.setRange(minimum, maximum)
