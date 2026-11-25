"""Colour tokens of the command palette, resolved from the active BEC theme."""

from __future__ import annotations

from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication

from bec_widgets.utils.colors import Colors

_DARK_FALLBACK = {
    "PRIMARY": "#3b82f6",
    "BG": "#0f1115",
    "CARD_BG": "#171a21",
    "FIELD_BG": "#10131a",
    "BORDER": "#2a2f3a",
    "FG": "#e8ebf1",
    "ACCENT_WARNING": "#EAC435",
    "ACCENT_EMERGENCY": "#CC181E",
}


class ThemeTokens:
    """Colours of the active theme plus the mixes the palette paints with."""

    def __init__(self):
        app = QApplication.instance()
        theme = getattr(app, "theme", None) if app is not None else None

        def color(key: str) -> QColor:
            fallback = _DARK_FALLBACK.get(key, "#808080")
            if theme is None:
                return QColor(fallback)
            return QColor(theme.color(key, fallback))

        self.bg = color("BG")
        self.card = color("CARD_BG")
        self.field = color("FIELD_BG")
        self.border = color("BORDER")
        self.fg = color("FG")
        self.primary = color("PRIMARY")
        self.warning = color("ACCENT_WARNING")
        self.danger = color("ACCENT_EMERGENCY")
        self.dark = self.bg.lightnessF() < 0.5
        self.fg_muted = self.mix(self.fg, 0.62)
        self.fg_subtle = self.mix(self.fg, 0.4)
        self.hover = self.mix(self.fg, 0.06)
        self.track = self.mix(self.fg, 0.1)
        self.danger_text = self.readable(self.danger)

    def mix(self, color: QColor, amount: float) -> QColor:
        """Return ``color`` mixed into the card background by ``amount`` (0 = card)."""
        return Colors._blend(self.card, color, amount)  # pylint: disable=protected-access

    def readable(
        self, color: QColor, background: QColor | None = None, ratio: float = 4.5
    ) -> QColor:
        """``color`` lightened (dark theme) or darkened (light theme) until text in it reaches
        ``ratio`` contrast on ``background`` (the card by default)."""
        background = self.card if background is None else background

        def contrast(a: QColor, b: QColor) -> float:
            la, lb = Colors.relative_luminance(a), Colors.relative_luminance(b)
            return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

        result = QColor(color)
        target = QColor("#ffffff") if self.dark else QColor("#000000")
        for step in range(1, 11):
            if contrast(result, background) >= ratio:
                break
            result = Colors._blend(color, target, step / 10)  # pylint: disable=protected-access
        return result

    def soft(self, color: QColor, amount: float = 0.16) -> QColor:
        """Tint ``color`` onto the card background, e.g. for chips and the selected row."""
        return self.mix(color, amount)
