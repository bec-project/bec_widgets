"""Colour roles for the fit dialogs, derived from the active bec_qthemes theme."""

from __future__ import annotations

from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication

from bec_widgets.utils.colors import get_theme_name

_FALLBACK = {
    "dark": {
        "BG": "#0f1115",
        "CARD_BG": "#171a21",
        "FIELD_BG": "#10131a",
        "BORDER": "#2a2f3a",
        "FG": "#e8ebf1",
        "PRIMARY": "#3b82f6",
        "ON_PRIMARY": "#ffffff",
    },
    "light": {
        "BG": "#f6f7fb",
        "CARD_BG": "#ffffff",
        "FIELD_BG": "#f0f2f7",
        "BORDER": "#d9dde6",
        "FG": "#151924",
        "PRIMARY": "#0a60ff",
        "ON_PRIMARY": "#ffffff",
    },
}
_ACCENTS = {"ACCENT_SUCCESS": "#2CA58D", "ACCENT_WARNING": "#EAC435", "ACCENT_EMERGENCY": "#CC181E"}


def _mix(a: QColor, b: QColor, t: float) -> str:
    return QColor(
        round(a.red() * (1 - t) + b.red() * t),
        round(a.green() * (1 - t) + b.green() * t),
        round(a.blue() * (1 - t) + b.blue() * t),
    ).name()


def fit_dialog_palette() -> dict[str, str]:
    """Return the dialog's colour roles as hex strings for the current theme.

    Returns:
        dict[str, str]: Colour roles shared by the QML and QWidget fit dialogs.
    """
    name = get_theme_name()
    fallback = _FALLBACK.get(name, _FALLBACK["dark"])
    theme = getattr(QApplication.instance(), "theme", None)

    def color(key: str) -> QColor:
        default = fallback.get(key) or _ACCENTS.get(key, "#888888")
        if theme is None:
            return QColor(default)
        return theme.color(key, default)

    bg, card, border, fg = (color(k) for k in ("BG", "CARD_BG", "BORDER", "FG"))
    primary = color("PRIMARY")
    success, warning, danger = (
        color(k) for k in ("ACCENT_SUCCESS", "ACCENT_WARNING", "ACCENT_EMERGENCY")
    )
    return {
        "dark": "true" if name == "dark" else "",
        "bg": bg.name(),
        "card": card.name(),
        "field": _mix(card, fg, 0.06),
        "border": border.name(),
        "fg": fg.name(),
        "muted": _mix(fg, card, 0.45),
        "primary": primary.name(),
        "on_primary": color("ON_PRIMARY").name(),
        "selection": _mix(primary, card, 0.8),
        "warning": warning.name() if name == "dark" else _mix(warning, fg, 0.35),
        "warning_bg": _mix(warning, card, 0.82),
        "quality_good": success.name(),
        "quality_fair": warning.name() if name == "dark" else _mix(warning, fg, 0.25),
        "quality_poor": danger.name(),
        "quality_failed": danger.name(),
        "quality_unknown": _mix(fg, card, 0.45),
    }
