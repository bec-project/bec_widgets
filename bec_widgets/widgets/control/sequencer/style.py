"""Colors, icons and small shared widgets for the sequencer editors."""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from bec_widgets.utils.colors import get_theme_name, rgba

# One color per kind of step, used by every concept so they read the same.
KIND_COLORS = {
    "light": {
        "set": "#2f6fdf",
        "scan_call": "#23926f",
        "repeat": "#c77a00",
        "for_each": "#8a53c9",
        "while": "#c2416b",
        "sequence": "#6b7280",
        "component_call": "#0e8a9a",
    },
    "dark": {
        "set": "#6c9cf2",
        "scan_call": "#4cc09a",
        "repeat": "#e8a33a",
        "for_each": "#b48ae6",
        "while": "#e2729a",
        "sequence": "#9aa0aa",
        "component_call": "#3fbccc",
    },
}

KIND_ICONS = {
    "set": "open_with",
    "scan_call": "query_stats",
    "repeat": "repeat",
    "for_each": "format_list_numbered",
    "while": "hourglass_top",
    "sequence": "folder_open",
    "component_call": "widgets",
}


def is_dark() -> bool:
    """Return whether the dark theme is active."""
    return get_theme_name() == "dark"


def kind_color(kind: str) -> QColor:
    """Color for a step kind in the current theme."""
    colors = KIND_COLORS["dark" if is_dark() else "light"]
    return QColor(colors.get(kind, colors["sequence"]))


def kind_icon(kind: str, size: int = 18, color: QColor | str | None = None):
    """Material icon for a step kind."""
    color = color if color is not None else kind_color(kind)
    return material_icon(
        KIND_ICONS.get(kind, "radio_button_unchecked"),
        size=(size, size),
        color=QColor(color).name() if not isinstance(color, str) else color,
        convert_to_pixmap=False,
    )


def theme(key: str, fallback: str) -> QColor:
    """Theme color by key, e.g. ``CARD_BG`` or ``BORDER``.

    Returns a copy: the theme hands out shared colors, and changing one (e.g. its alpha) would
    change it for every widget that uses it later.
    """
    app = QApplication.instance()
    if app is not None and hasattr(app, "theme"):
        return QColor(app.theme.color(key, fallback))
    return QColor(fallback)


def card_qss(selector: str, radius: int = 8) -> str:
    """Style sheet for a card: card background with a thin border."""
    return (
        f"{selector} {{ background: {theme('CARD_BG', '#ffffff').name()};"
        f" border: 1px solid {theme('BORDER', '#d0d0d0').name()}; border-radius: {radius}px; }}"
    )


def chip_qss(color: QColor, selector: str = "QLabel") -> str:
    """Style sheet for a small tinted pill."""
    # bright accents (yellow, green) need darker text to stay readable on a light background
    text = color if is_dark() else QColor(color).darker(150)
    return (
        f"{selector} {{ background: {rgba(color, 38)}; color: {text.name()};"
        " border-radius: 9px; padding: 1px 8px; font-weight: 600; }"
    )


class Chip(QLabel):
    """A small tinted pill, e.g. "8 scans" or "Ready to run"."""

    def __init__(self, text: str = "", color: QColor | None = None, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.set_color(color or theme("PRIMARY", "#2f6fdf"))

    def set_color(self, color: QColor) -> None:
        """Change the tint."""
        self.setStyleSheet(chip_qss(color))


def hline(parent: QWidget | None = None) -> QFrame:
    """A thin horizontal divider."""
    line = QFrame(parent)
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {theme('BORDER', '#d0d0d0').name()};")
    return line


def heading(text: str, parent: QWidget | None = None, size: int = 15) -> QLabel:
    """A bold section heading."""
    label = QLabel(text, parent)
    font = label.font()
    font.setPointSize(size)
    font.setBold(True)
    label.setFont(font)
    return label


def hint(text: str, parent: QWidget | None = None) -> QLabel:
    """Muted helper text that wraps."""
    label = QLabel(text, parent)
    label.setWordWrap(True)
    fg = theme("FG", "#333333")
    label.setStyleSheet(f"color: {rgba(fg, 150)};")
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    return label


def problem_label(parent: QWidget | None = None) -> QLabel:
    """Red text that explains what a step still needs; hidden while empty."""
    label = QLabel(parent)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {theme('ACCENT_EMERGENCY', '#e0534b').name()}; font-weight: 600;")
    label.setVisible(False)
    return label


def empty_state(title: str, text: str, parent: QWidget | None = None, icon: str = "playlist_add"):
    """A centered message for an empty sequence: icon, title and a hint."""
    widget = QWidget(parent)
    widget.setObjectName("SequencerEmptyState")
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    widget.setStyleSheet(
        f"#SequencerEmptyState {{ background: {theme('CARD_BG', '#ffffff').name()};"
        f" border: 2px dashed {theme('BORDER', '#d0d0d0').name()}; border-radius: 10px; }}"
    )
    layout = QVBoxLayout(widget)
    layout.addStretch(1)
    picture = QLabel(widget)
    muted = theme("FG", "#333333")
    muted.setAlpha(110)
    picture.setPixmap(
        material_icon(icon, size=(44, 44), color=muted.name(QColor.NameFormat.HexArgb))
    )
    picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(picture)
    name = heading(title, widget, 14)
    name.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(name)
    explanation = hint(text, widget)
    explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
    explanation.setMaximumWidth(420)
    # stretches instead of an alignment flag, so the wrapped text gets the height it needs
    row = QHBoxLayout()
    row.addStretch(1)
    row.addWidget(explanation, 4)
    row.addStretch(1)
    layout.addLayout(row)
    layout.addStretch(1)
    return widget
