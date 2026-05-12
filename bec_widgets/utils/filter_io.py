"""Small helpers for populating editable combo boxes used by device inputs."""

from __future__ import annotations

from bec_lib.logger import bec_logger
from qtpy.QtWidgets import QComboBox
from typeguard import TypeCheckError

from bec_widgets.utils.ophyd_kind_util import Kind

logger = bec_logger.logger


def replace_combobox_items(combo_box: QComboBox, items: list[str | tuple]) -> None:
    """Replace all combobox entries with strings or ``(text, data)`` tuples."""
    combo_box.clear()
    for item in items:
        if isinstance(item, str):
            combo_box.addItem(item)
        else:
            combo_box.addItem(*item)


def combobox_contains_text(combo_box: QComboBox, text: str) -> bool:
    """Return whether *text* is present as visible combobox text."""
    return any(combo_box.itemText(i) == text for i in range(combo_box.count()))


def signal_items_for_kind(
    *, kind: Kind, signal_filter: set[Kind], device_info: dict, device_name: str
) -> list[tuple[str, dict]]:
    """Build display entries for signals matching a BEC signal kind."""
    items: list[tuple[str, dict]] = []
    for signal_name, signal_info in device_info.items():
        if kind not in signal_filter or signal_info.get("kind_str") != kind.name:
            continue

        obj_name = signal_info.get("obj_name", "")
        component_name = signal_info.get("component_name", "")
        signal_without_device = obj_name.removeprefix(f"{device_name}_")
        if not signal_without_device:
            signal_without_device = obj_name

        if (
            signal_without_device != signal_name
            and component_name.replace(".", "_") != signal_without_device
        ):
            items.append((f"{signal_without_device} ({signal_name})", signal_info))
        else:
            items.append((signal_name, signal_info))
    return items


def get_bec_signals_for_classes(
    *, client, signal_class_filter: str | list[str], ndim_filter: int | list[int] | None = None
) -> list[tuple[str, str, dict]]:
    """Return BEC signals filtered by signal class and optional dimensionality."""
    if not client or not hasattr(client, "device_manager"):
        return []

    try:
        signals = client.device_manager.get_bec_signals(signal_class_filter)
    except TypeCheckError as exc:
        logger.warning(f"Error retrieving signals: {exc}")
        return []

    if ndim_filter is None:
        return signals

    accepted_ndim = [ndim_filter] if isinstance(ndim_filter, int) else ndim_filter
    filtered_signals: list[tuple[str, str, dict]] = []
    for device_name, signal_name, signal_config in signals:
        ndim = None
        if isinstance(signal_config, dict):
            ndim = signal_config.get("describe", {}).get("signal_info", {}).get("ndim")
        if ndim in accepted_ndim:
            filtered_signals.append((device_name, signal_name, signal_config))
    return filtered_signals
