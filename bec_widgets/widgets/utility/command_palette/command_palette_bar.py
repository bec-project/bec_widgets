"""Bar across the top of a window with a field that opens the command palette.

The field is a launcher, not a second search input: a click (or the palette shortcut) opens the
palette card, which then drops down from under the bar.
"""

from __future__ import annotations

import sys

from qtpy.QtCore import QRectF, QSize, Qt
from qtpy.QtGui import QFontMetrics, QPainter
from qtpy.QtWidgets import QAbstractButton, QApplication, QHBoxLayout, QWidget

from bec_widgets.utils.error_popups import SafeConnect, SafeSlot
from bec_widgets.widgets.utility.command_palette.command_palette_qwidget import (
    ICON_GAP,
    ICON_SIZE,
    _font,
    _icon,
    draw_keycap,
)
from bec_widgets.widgets.utility.command_palette.palette_theme import ThemeTokens

BAR_HEIGHT = 40
FIELD_HEIGHT = 28
FIELD_MIN_WIDTH = 240
FIELD_MAX_WIDTH = 560
FIELD_INSET = 10


def shortcut_label() -> str:
    """The palette shortcut as the platform writes it: ``⌘K`` on macOS, ``Ctrl+K`` elsewhere."""
    return "⌘K" if sys.platform == "darwin" else "Ctrl+K"


class CommandPaletteField(QAbstractButton):
    """Search-field look-alike that opens the command palette when clicked."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("CommandPaletteField")
        self.setText("Command palette")
        self.tokens = ThemeTokens()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # the palette shortcut is the keyboard way in; a focusable look-alike would only add a
        # tab stop that does the same as Ctrl+K
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setToolTip(f"Command palette ({shortcut_label()})")
        self.setAccessibleName("Command palette")
        self.setFixedHeight(FIELD_HEIGHT)
        self.setMinimumWidth(FIELD_MIN_WIDTH)
        self.setMaximumWidth(FIELD_MAX_WIDTH)

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        return QSize(FIELD_MAX_WIDTH, FIELD_HEIGHT)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = self.tokens
        hovered = self.underMouse() or self.isDown()
        fill = tokens.mix(tokens.fg, 0.1) if hovered else tokens.field
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(fill)
        painter.setPen(tokens.mix(tokens.fg, 0.3) if hovered else tokens.border)
        painter.drawRoundedRect(rect, 6, 6)

        text_color = tokens.readable(tokens.fg_muted, fill)
        center_y = rect.center().y()
        left = FIELD_INSET
        painter.drawPixmap(
            int(left), int(center_y - ICON_SIZE / 2), _icon("search", text_color.name(), ICON_SIZE)
        )
        keycap_left = draw_keycap(painter, rect.right() - 4, center_y, shortcut_label(), tokens)
        text_left = left + ICON_SIZE + ICON_GAP - 4
        font = _font(13)
        painter.setFont(font)
        painter.setPen(text_color)
        text = QFontMetrics(font).elidedText(
            self.text(), Qt.TextElideMode.ElideRight, int(keycap_left - 8 - text_left)
        )
        painter.drawText(
            QRectF(text_left, rect.top(), keycap_left - 8 - text_left, rect.height()),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            text,
        )
        painter.end()


class CommandPaletteBar(QWidget):
    """Slim bar with a centred :class:`CommandPaletteField`, meant for the top of a window.

    Connect :attr:`field`'s ``clicked`` to the palette, and pass :attr:`field` to
    :meth:`CommandPalette.set_anchor` so the card opens under it.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("CommandPaletteBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(BAR_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)
        self.field = CommandPaletteField(self)
        layout.addStretch(1)
        layout.addWidget(self.field, 4)
        layout.addStretch(1)
        self.refresh_theme(ThemeTokens())

        self._theme_connection = None
        theme = getattr(QApplication.instance(), "theme", None)
        if theme is not None:
            self._theme_connection = SafeConnect(self, theme.theme_changed, self._on_theme_changed)

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        self.field.tokens = tokens
        self.setStyleSheet(
            f"#CommandPaletteBar {{ background: transparent;"
            f" border-bottom: 1px solid {tokens.border.name()}; }}"
        )
        self.field.update()

    @SafeSlot(str)
    @SafeSlot()
    def _on_theme_changed(self, _theme: str | None = None) -> None:
        self.refresh_theme(ThemeTokens())

    def release(self) -> None:
        """Stop following the application theme."""
        connection, self._theme_connection = self._theme_connection, None
        theme = getattr(QApplication.instance(), "theme", None)
        if connection is None or theme is None:
            return
        connection.invalidate()
        try:
            theme.theme_changed.disconnect(connection)
        except (RuntimeError, TypeError):
            pass  # already gone with the theme object
