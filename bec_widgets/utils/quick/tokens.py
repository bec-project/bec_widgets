"""Design tokens of the BEC UI kit, resolved from the active ``bec_qthemes`` theme.

One :class:`ThemeTokens` object holds every colour and metric the kit uses. The QML bridge
(:class:`~bec_widgets.utils.quick.host.QmlTheme`) and the QWidget controls in
:mod:`bec_widgets.utils.ux_kit` both read from it, so a widget looks the same in either
technology and follows ``app.theme`` when the user switches between light and dark.

Base colours come straight from the theme XML of ``bec_qthemes`` (``BG``, ``CARD_BG``, ``FG``,
``PRIMARY``, ``ACCENT_*`` ...). Everything else (muted text, hover fills, readable status text,
status tints) is derived here, so there is exactly one place that defines those rules.
"""

from __future__ import annotations

from qtpy.QtGui import QColor, QFontDatabase
from qtpy.QtWidgets import QApplication

# Copies of bec_qthemes' dark.xml and light.xml, used before a theme has been applied
# (for example in unit tests or when a widget is created ahead of ``apply_theme``).
FALLBACK_PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "BG": "#1e1f22",
        "CARD_BG": "#2b2c2f",
        "FIELD_BG": "#26272a",
        "FG": "#dddddd",
        "BORDER": "#464749",
        "PRIMARY": "#6089ef",
        "ON_PRIMARY": "#ffffff",
        "ACCENT_DEFAULT": "#40B6E0",
        "ACCENT_HIGHLIGHT": "#DB5860",
        "ACCENT_WARNING": "#EDA200",
        "ACCENT_EMERGENCY": "#E0534B",
        "ACCENT_SUCCESS": "#59A869",
    },
    "light": {
        "BG": "#f6f7fb",
        "CARD_BG": "#ffffff",
        "FIELD_BG": "#ffffff",
        "FG": "#151924",
        "BORDER": "#d9dde6",
        "PRIMARY": "#3b82f6",
        "ON_PRIMARY": "#ffffff",
        "ACCENT_DEFAULT": "#0a60ff",
        "ACCENT_HIGHLIGHT": "#B53565",
        "ACCENT_WARNING": "#EAC435",
        "ACCENT_EMERGENCY": "#CC181E",
        "ACCENT_SUCCESS": "#2CA58D",
    },
}

# Status tones understood by StatusPill, Banner, LinearProgress, ... in both technologies.
# The aliases keep the names used by the first ports (queue: busy/ok/warn/err/stale) working.
TONE_ALIASES: dict[str, str] = {
    "busy": "info",
    "accent": "info",
    "ok": "success",
    "warn": "warning",
    "err": "danger",
    "error": "danger",
    "emergency": "danger",
    "critical": "danger",
    "stale": "subtle",
    "muted": "neutral",
}

# Metrics shared by QML and QWidget controls, in device-independent pixels.
METRICS: dict[str, int] = {
    "radiusSmall": 6,
    "radiusLarge": 10,
    "controlHeight": 32,
    "controlHeightCompact": 28,
    "spacing": 8,
    "padding": 12,
    "fontCaption": 11,
    "fontSmall": 12,
    "fontBody": 13,
    "fontTitle": 15,
    "fontHeadline": 20,
    "fontDisplay": 28,
}


def blend(base: QColor, top: QColor, amount: float) -> QColor:
    """Return ``top`` mixed into ``base`` by ``amount`` (0 = base, 1 = top), fully opaque."""
    return QColor.fromRgbF(
        base.redF() + (top.redF() - base.redF()) * amount,
        base.greenF() + (top.greenF() - base.greenF()) * amount,
        base.blueF() + (top.blueF() - base.blueF()) * amount,
        1.0,
    )


def readable_on(color: QColor, dark: bool) -> QColor:
    """Return ``color`` adjusted so it stays legible as text on a card of the given theme.

    Accent colours such as the light theme's yellow are too pale for text on white, so they are
    darkened; on dark cards accents are lifted slightly towards white.
    """
    if dark:
        return blend(color, QColor("#ffffff"), 0.15)
    return blend(color, QColor("#000000"), 0.35 if color.lightnessF() > 0.5 else 0.1)


def app_theme():
    """Return ``QApplication.instance().theme`` (a ``bec_qthemes`` Theme) or None."""
    app = QApplication.instance()
    return getattr(app, "theme", None) if app is not None else None


class ThemeTokens:
    """Resolved colour and metric tokens of the active BEC theme.

    Use :meth:`current` in paint code; it caches the tokens until the theme changes.

    Args:
        theme_name(str | None): Force ``"dark"`` or ``"light"`` fallback colours. By default the
            application theme is used and the dark palette is the fallback.
    """

    _cache: tuple[object, ThemeTokens] | None = None

    def __init__(self, theme_name: str | None = None):
        theme = app_theme() if theme_name is None else None
        name = theme_name or (getattr(theme, "theme", "dark") if theme is not None else "dark")
        fallback = FALLBACK_PALETTES.get(str(name), FALLBACK_PALETTES["dark"])

        def color(key: str) -> QColor:
            default = fallback.get(key, "#808080")
            if theme is None:
                return QColor(default)
            return QColor(theme.color(key, default))

        self.name: str = str(name)
        self.bg = color("BG")
        self.card = color("CARD_BG")
        self.field = color("FIELD_BG")
        self.border = color("BORDER")
        self.fg = color("FG")
        self.primary = color("PRIMARY")
        self.on_primary = color("ON_PRIMARY")
        self.accent = color("ACCENT_DEFAULT")
        self.highlight = color("ACCENT_HIGHLIGHT")
        self.warning = color("ACCENT_WARNING")
        self.danger = color("ACCENT_EMERGENCY")
        self.success = color("ACCENT_SUCCESS")
        self.info = self.accent
        self.dark = self.bg.lightnessF() < 0.5

        self.fg_muted = blend(self.card, self.fg, 0.62)
        self.fg_subtle = blend(self.card, self.fg, 0.4)
        self.hover = blend(self.card, self.fg, 0.06)
        self.pressed = blend(self.card, self.fg, 0.12)
        self.track = blend(self.card, self.fg, 0.1)
        self.separator = self.track
        self.sunken = blend(self.bg, self.fg, 0.03 if self.dark else 0.015)

        tint = 0.18 if self.dark else 0.12
        for tone in ("info", "success", "warning", "danger", "highlight"):
            base = getattr(self, tone)
            setattr(self, f"{tone}_text", readable_on(base, self.dark))
            setattr(self, f"{tone}_tint", blend(self.card, base, tint))

        self.mono_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        self.metrics = dict(METRICS)

    @classmethod
    def current(cls) -> ThemeTokens:
        """Return cached tokens for the active theme; rebuilt when the theme changes."""
        theme = app_theme()
        key = (id(theme), getattr(theme, "theme", None), id(getattr(theme, "_colors", None)))
        if cls._cache is None or cls._cache[0] != key:
            cls._cache = (key, cls())
        return cls._cache[1]

    def soft(self, color: QColor, amount: float = 0.16) -> QColor:
        """Tint ``color`` onto the card background, e.g. for chips and banners."""
        return blend(self.card, color, amount)

    @staticmethod
    def tone_name(tone: str) -> str:
        """Normalise a tone name: ``ok`` -> ``success``, ``err`` -> ``danger`` and so on."""
        tone = (tone or "neutral").lower()
        return TONE_ALIASES.get(tone, tone)

    def tone(self, tone: str) -> QColor:
        """Base colour of a tone (``neutral``, ``subtle``, ``primary``, ``info``, ``success``,
        ``warning``, ``danger``, ``highlight`` or an alias)."""
        tone = self.tone_name(tone)
        if tone == "neutral":
            return self.fg_muted
        if tone == "subtle":
            return self.fg_subtle
        return QColor(getattr(self, tone, self.fg_muted))

    def tone_text(self, tone: str) -> QColor:
        """Text colour of a tone that stays readable on cards."""
        tone = self.tone_name(tone)
        if tone == "primary":
            return readable_on(self.primary, self.dark)
        return QColor(getattr(self, f"{tone}_text", self.tone(tone)))

    def tone_tint(self, tone: str) -> QColor:
        """Soft background fill of a tone; neutral tones use the hover fill."""
        tone = self.tone_name(tone)
        if tone in ("neutral", "subtle"):
            return self.hover
        if tone == "primary":
            return self.soft(self.primary, 0.18 if self.dark else 0.12)
        return QColor(getattr(self, f"{tone}_tint", self.hover))
