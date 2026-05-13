"""Small helpers for populating editable combo boxes used by device inputs."""

from __future__ import annotations

from contextlib import nullcontext

from bec_lib.logger import bec_logger
from qtpy.QtCore import QSignalBlocker
from qtpy.QtWidgets import QComboBox
from typeguard import TypeCheckError

from bec_widgets.utils.ophyd_kind_util import Kind

logger = bec_logger.logger


def replace_combobox_items(
    combo_box: QComboBox,
    items: list[str | tuple],
    *,
    preserve_current_text: bool = False,
    block_signals: bool = False,
) -> None:
    """Replace all combobox entries.

    Args:
        combo_box: Combobox whose entries should be replaced.
        items: Entries to add. String entries are added as display text. Tuple entries are
            passed to ``QComboBox.addItem`` as ``(text, data)``.
        preserve_current_text: If True, restore the combobox text after replacing the items.
        block_signals: If True, block combobox signals while the items are replaced.
    """
    current_text = combo_box.currentText()
    signal_blocker = QSignalBlocker(combo_box) if block_signals else nullcontext()
    with signal_blocker:
        combo_box.clear()
        for item in items:
            if isinstance(item, str):
                combo_box.addItem(item)
            else:
                combo_box.addItem(*item)
        if preserve_current_text:
            combo_box.setCurrentText(current_text)


def signal_items_for_kind(
    *, kind: Kind, signal_filter: set[Kind], device_info: dict, device_name: str
) -> list[tuple[str, dict]]:
    """Build display entries for signals matching a BEC signal kind.

    Args:
        kind: Signal kind to collect.
        signal_filter: Enabled signal kinds.
        device_info: Signal metadata from the BEC device info dictionary.
        device_name: Name of the device owning the signals.

    Returns:
        Combobox entries as ``(display_text, signal_info)`` tuples.
    """
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
    """Return BEC signals filtered by signal class and optional dimensionality.

    Args:
        client: BEC client that provides ``device_manager.get_bec_signals``.
        signal_class_filter: Signal class name or class names passed to the device manager.
        ndim_filter: Optional dimensionality filter. If provided, only signals whose
            ``describe.signal_info.ndim`` is in this value are returned.

    Returns:
        Tuples of ``(device_name, signal_name, signal_config)`` for matching signals.
    """
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
