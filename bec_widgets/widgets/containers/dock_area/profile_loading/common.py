"""
Shared pieces of the progressive profile loading UI: placeholder states, skeleton shapes per widget
type and the switch between the QWidget and QML variants.
"""

from __future__ import annotations

import os
import time
import zlib
from typing import Literal

from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication

from bec_widgets.utils.colors import get_accent_colors

PlaceholderState = Literal["queued", "loading", "paused", "failed"]
SkeletonKind = Literal["plot", "list", "form"]

#: Environment variable selecting the loading UI: ``qwidget`` (default) or ``qml``.
LOADING_UI_ENV = "BEC_PROFILE_LOADING_UI"
#: Environment variable that switches profile loading back to the previous blocking pipeline.
LOADING_MODE_ENV = "BEC_PROFILE_LOADING"

_PLOT_WIDGETS = {
    "Waveform",
    "MultiWaveform",
    "ScatterWaveform",
    "Image",
    "MotorMap",
    "Heatmap",
    "PlotBase",
}
_LIST_WIDGETS = {
    "BECQueue",
    "DeviceBrowser",
    "BECStatusBox",
    "LogPanel",
    "ScanHistory",
    "AvailableDeviceResources",
    "DeviceManagerView",
    "BeamlineStateManager",
}

STATE_TEXT: dict[str, str] = {
    "queued": "Waiting",
    "loading": "Loading",
    "paused": "Not loaded",
    "failed": "Could not load",
}

#: One shimmer sweep across a skeleton, in seconds.
SHIMMER_PERIOD = 1.6


def loading_ui_variant() -> Literal["qwidget", "qml"]:
    """Return the configured loading UI variant."""
    value = os.environ.get(LOADING_UI_ENV, "qwidget").strip().lower()
    return "qml" if value == "qml" else "qwidget"


def progressive_loading_enabled() -> bool:
    """Return False when the previous blocking pipeline was requested."""
    return os.environ.get(LOADING_MODE_ENV, "").strip().lower() != "legacy"


def skeleton_kind(widget_class: str) -> SkeletonKind:
    """Pick the skeleton shape that resembles *widget_class*."""
    if widget_class in _PLOT_WIDGETS:
        return "plot"
    if widget_class in _LIST_WIDGETS:
        return "list"
    return "form"


def skeleton_seed(name: str) -> int:
    """Stable per-dock seed so the skeleton rows keep their shape between repaints."""
    return zlib.crc32(name.encode("utf-8"))


def shimmer_phase() -> float:
    """Shared shimmer position in [0, 1); all skeletons shimmer in sync."""
    return (time.monotonic() % SHIMMER_PERIOD) / SHIMMER_PERIOD


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


def loading_palette() -> dict[str, QColor]:
    """
    Colors for skeletons and the progress card, derived from the active application palette so
    they follow the light and dark themes.
    """
    app = QApplication.instance()
    palette = app.palette() if app is not None else None
    window = palette.window().color() if palette else QColor("#1e1f22")
    text = palette.windowText().color() if palette else QColor("#e6e6e6")
    dark = window.lightness() < 128
    accents = get_accent_colors()
    accent = QColor(accents.default) if accents is not None else QColor("#3b82f6")
    emergency = QColor(accents.emergency) if accents is not None else QColor("#d64545")
    return {
        "window": window,
        "text": text,
        "muted": _mix(window, text, 0.62),
        "block": _mix(window, text, 0.09 if dark else 0.07),
        "block_strong": _mix(window, text, 0.14 if dark else 0.11),
        "shine": _mix(window, text, 0.2 if dark else 0.02),
        "card": _mix(window, text, 0.06) if dark else QColor("#ffffff"),
        "border": _mix(window, text, 0.16),
        "accent": accent,
        "danger": emergency,
    }
