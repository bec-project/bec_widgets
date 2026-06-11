from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bec_lib.device import DeviceBase

ASYNC_SIGNAL_CLASSES = frozenset({"AsyncSignal", "AsyncMultiSignal", "DynamicSignal"})
_NON_CURVE_ROLES = frozenset({"preview", "diagnostic", "file_event", "progress"})


class SignalCategory(str, Enum):
    """Data-delivery category of a signal."""

    SYNC = "sync"
    ASYNC = "async"
    UNKNOWN = "unknown"


def classify_signal_info(signal_info: dict[str, Any] | None) -> SignalCategory:
    """
    Classify a serialized signal-info dict (one entry of
    ``device._info["signals"]``).

    Args:
        signal_info: The serialized signal info, or None.

    Returns:
        SignalCategory: ASYNC for the DynamicSignal family (including
        subclasses detected via the embedded ``signal_info`` block), SYNC for
        all other concrete signal classes, UNKNOWN when no decision is
        possible.
    """
    if not isinstance(signal_info, dict) or not signal_info:
        return SignalCategory.UNKNOWN

    signal_class = signal_info.get("signal_class")
    if signal_class in ASYNC_SIGNAL_CLASSES:
        return SignalCategory.ASYNC

    describe = signal_info.get("describe")
    embedded = describe.get("signal_info") if isinstance(describe, dict) else None
    if isinstance(embedded, dict):
        role = embedded.get("role", "main")
        if role in _NON_CURVE_ROLES:
            return SignalCategory.UNKNOWN
        return SignalCategory.ASYNC

    if signal_class:
        return SignalCategory.SYNC

    return SignalCategory.UNKNOWN


def classify_device_signal(device: DeviceBase | None, entry: str) -> SignalCategory:
    """
    Classify a signal of a device by its serialized info.

    Args:
        device: The client device (``bec_lib.device.DeviceBase``) from the device
            manager, or None (e.g. history data whose device no longer exists).
        entry: The signal entry name (component name used in curve configs).

    Returns:
        SignalCategory: The category, UNKNOWN when the device or entry cannot
        be resolved.
    """
    if device is None or not entry:
        return SignalCategory.UNKNOWN
    info = getattr(device, "_info", None)
    if not isinstance(info, dict):
        return SignalCategory.UNKNOWN
    signals = info.get("signals")
    if not isinstance(signals, dict):
        return SignalCategory.UNKNOWN

    signal_info = signals.get(entry)
    if signal_info is None:
        for candidate in signals.values():
            if isinstance(candidate, dict) and candidate.get("obj_name") == entry:
                signal_info = candidate
                break
    return classify_signal_info(signal_info)
