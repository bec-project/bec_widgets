"""
Theme colours and HiDPI-sharp material icons for widgets that paint or style themselves.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent
from qtpy.QtGui import QColor, QGuiApplication, QIcon, QPixmap
from qtpy.QtWidgets import QApplication, QWidget


# TODO this module will be probably moved to bec_qthemes, but for now it is here, bec_qthemes will have another round of refactoring later
def theme_colors() -> dict[str, QColor]:
    """
    Return the colours of the active BEC theme, with fallbacks when no theme is applied.

    Keys: fg, muted, bg, card, field, border, primary, on_primary, ok, warn, bad, run.
    """
    app = QApplication.instance()
    theme = getattr(app, "theme", None)
    palette = app.palette() if app is not None else None

    def pick(key: str, fallback: str) -> QColor:
        if theme is not None:
            return QColor(theme.color(key, fallback))
        return QColor(fallback)

    fg = pick("FG", palette.text().color().name() if palette else "#1f2328")
    bg = pick("BG", palette.window().color().name() if palette else "#f6f7fb")
    muted = QColor(fg)
    muted.setAlphaF(0.62)
    return {
        "fg": fg,
        "muted": muted,
        "bg": bg,
        "card": pick("CARD_BG", bg.name()),
        "field": pick("FIELD_BG", bg.name()),
        "border": pick("BORDER", "#d4d9e2"),
        "primary": pick("PRIMARY", "#2f6df0"),
        "on_primary": pick("ON_PRIMARY", "#ffffff"),
        "ok": pick("ACCENT_SUCCESS", "#2CA58D"),
        "warn": pick("ACCENT_WARNING", "#EAC435"),
        "bad": pick("ACCENT_EMERGENCY", "#CC181E"),
        "run": pick("ACCENT_DEFAULT", "#0a60ff"),
    }


def css(color: QColor, alpha: float | None = None) -> str:
    """Return a QSS rgba() string for a colour, optionally with a new alpha (0..1)."""
    c = QColor(color)
    if alpha is not None:
        c.setAlphaF(alpha)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha()})"


# Events after which a widget may sit on a screen with another device pixel ratio.
DPR_EVENTS = tuple(
    getattr(QEvent.Type, name)
    for name in ("DevicePixelRatioChange", "ScreenChangeInternal")
    if hasattr(QEvent.Type, name)
)

_PIXMAPS: dict[tuple, QPixmap] = {}


def _device_pixel_ratio(widget: QWidget | None) -> float:
    if widget is not None:
        return widget.devicePixelRatioF()
    screen = QGuiApplication.primaryScreen() if QGuiApplication.instance() else None
    return screen.devicePixelRatio() if screen is not None else 1.0


def crisp_pixmap(
    name: str, size: int, color: QColor, filled: bool = False, widget: QWidget | None = None
) -> QPixmap:
    """
    A material icon rendered at the screen's device pixel ratio, so it is sharp on HiDPI
    screens. bec_qthemes renders at the logical size only, which Qt then upscales.

    Args:
        name(str): Material icon name.
        size(int): Logical size in pixels.
        color(QColor): Icon colour.
        filled(bool): Use the filled variant.
        widget(QWidget, optional): Widget whose screen decides the pixel ratio.
    """
    dpr = _device_pixel_ratio(widget)
    key = (name, size, QColor(color).name(QColor.NameFormat.HexArgb), filled, dpr)
    pixmap = _PIXMAPS.get(key)
    if pixmap is None:
        device_size = max(1, round(size * dpr))
        pixmap = material_icon(name, size=(device_size, device_size), color=color, filled=filled)
        pixmap.setDevicePixelRatio(dpr)
        _PIXMAPS[key] = pixmap
    return pixmap


def crisp_icon(
    name: str,
    size: int,
    color: QColor,
    filled: bool = False,
    widget: QWidget | None = None,
    disabled_color: QColor | None = None,
) -> QIcon:
    """A QIcon from crisp_pixmap, with its own pixmap for the disabled state."""
    if disabled_color is None:
        disabled_color = QColor(theme_colors()["muted"])
        disabled_color.setAlphaF(0.45)
    icon = QIcon()
    icon.addPixmap(crisp_pixmap(name, size, color, filled, widget), QIcon.Mode.Normal)
    icon.addPixmap(crisp_pixmap(name, size, disabled_color, filled, widget), QIcon.Mode.Disabled)
    return icon
