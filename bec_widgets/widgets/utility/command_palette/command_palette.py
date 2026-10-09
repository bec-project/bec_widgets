"""Ctrl+K command palette overlay for BEC windows.

The overlay dims the window and shows a search card near its top. The card is rendered either
with QWidgets (:mod:`command_palette_qwidget`) or with Qt Quick (:mod:`command_palette_qml`);
both drive the same :class:`CommandPaletteController`, so search, ranking and keyboard handling
are identical.

Typical use::

    palette = CommandPalette(window, sources=[lambda: my_commands])
    palette.install_shortcuts()
"""

from __future__ import annotations

import os
from typing import Iterable, Literal

from qtpy.QtCore import QEvent, QObject, QRect, QRectF, Qt, Signal
from qtpy.QtGui import QColor, QKeySequence, QPainter, QShortcut
from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.widgets.utility.command_palette.palette_core import (
    CommandPaletteController,
    CommandSource,
)

Flavour = Literal["qwidget", "qml"]
FLAVOUR_ENV = "BEC_COMMAND_PALETTE"
SHORTCUTS = ("Ctrl+K", "Ctrl+Shift+P")
CARD_WIDTH = 640
CARD_HEIGHT = 440
SHADOW_LAYERS = 6


def default_flavour() -> Flavour:
    """Renderer chosen by the ``BEC_COMMAND_PALETTE`` environment variable (``qwidget``)."""
    value = os.environ.get(FLAVOUR_ENV, "qwidget").strip().lower()
    return "qml" if value in ("qml", "quick") else "qwidget"


class CommandPalette(QWidget):
    """Window overlay hosting the command palette card.

    Args:
        window(QWidget): Window to cover, usually the main window.
        sources(Iterable[CommandSource]): Command sources, called each time the palette opens.
        flavour(Flavour | None): ``"qwidget"`` or ``"qml"``; defaults to :func:`default_flavour`.
    """

    opened = Signal()
    closed = Signal()

    def __init__(
        self, window: QWidget, sources: Iterable[CommandSource] = (), flavour: Flavour | None = None
    ):
        super().__init__(window)
        self.setObjectName("CommandPalette")
        self.flavour: Flavour = flavour or default_flavour()
        self.controller = CommandPaletteController(sources, self)
        self.controller.accepted.connect(self.close_palette)
        self.controller.dismissRequested.connect(self.close_palette)
        self._previous_focus: QWidget | None = None
        self._shortcuts: list[QShortcut] = []

        # imported lazily so the QWidget flavour does not load Qt Quick
        # pylint: disable=import-outside-toplevel
        if self.flavour == "qml":
            from bec_widgets.widgets.utility.command_palette.command_palette_qml import (
                PaletteCardQuick as Card,
            )
        else:
            from bec_widgets.widgets.utility.command_palette.command_palette_qwidget import (
                PaletteCardWidget as Card,
            )
        self.card = Card(self.controller, self)

        window.installEventFilter(self)
        self.hide()

    # ------------------------------------------------------------------ public API
    def install_shortcuts(self, sequences: Iterable[str] = SHORTCUTS) -> list[QShortcut]:
        """Open the palette with ``sequences`` anywhere in the window (Ctrl+K, Ctrl+Shift+P)."""
        window = self.parentWidget()
        for sequence in sequences:
            shortcut = QShortcut(QKeySequence(sequence), window)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(self.toggle)
            self._shortcuts.append(shortcut)
        return self._shortcuts

    def is_open(self) -> bool:
        """Whether the palette is currently shown."""
        return self.isVisible()

    def toggle(self) -> None:
        """Open the palette, or close it if it is already open."""
        if self.is_open():
            self.close_palette()
        else:
            self.open_palette()

    def open_palette(self, text: str = "") -> None:
        """Show the palette with a fresh command list.

        Args:
            text(str): Initial query; a leading ``>``, ``+``, ``@`` or ``#`` selects a scope.
        """
        tokens = ThemeTokens()
        self.controller.set_highlight_color(tokens.primary.name())
        self.controller.reset()
        self.controller.refresh()
        if text:
            self.controller.set_query(text)
        self.card.refresh_theme(tokens)
        focus = QApplication.focusWidget()
        if focus is not None and focus is not self and not self.isAncestorOf(focus):
            self._previous_focus = focus
        self._update_geometry()
        self.show()
        self.raise_()
        self.card.focus_input()
        self.opened.emit()

    def close_palette(self) -> None:
        """Hide the palette and give the focus back to where it was."""
        if not self.isVisible():
            return
        self.hide()
        previous, self._previous_focus = self._previous_focus, None
        if previous is not None:
            try:
                previous.setFocus(Qt.FocusReason.PopupFocusReason)
            except RuntimeError:
                pass  # the widget was deleted meanwhile
        self.closed.emit()

    def card_geometry(self) -> QRect:
        """Geometry of the visible card (without shadow margins) in overlay coordinates."""
        width = min(CARD_WIDTH, max(320, self.width() - 32))
        height = min(CARD_HEIGHT, max(200, self.height() - 48))
        top = max(24, int(self.height() * 0.12))
        top = min(top, max(8, self.height() - height - 8))
        return QRect((self.width() - width) // 2, top, width, height)

    # ------------------------------------------------------------------ Qt overrides
    def _update_geometry(self) -> None:
        window = self.parentWidget()
        if window is None:
            return
        self.setGeometry(window.rect())
        margin = getattr(self.card, "shadow_margin", 0)
        self.card.setGeometry(self.card_geometry().adjusted(-margin, -margin, margin, margin))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            if self.isVisible():
                self._update_geometry()
        return super().eventFilter(watched, event)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = ThemeTokens()
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120 if tokens.dark else 70))
        if not getattr(self.card, "shadow_margin", 0):
            # layered soft shadow below the QWidget card, the same recipe the QML card uses;
            # a QGraphicsDropShadowEffect would re-render the whole card on every list repaint
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            card = QRectF(self.card_geometry())
            for i in range(SHADOW_LAYERS):
                alpha = (0.11 if tokens.dark else 0.045) * (1 - i / (SHADOW_LAYERS + 1))
                painter.setBrush(QColor(0, 0, 0, int(255 * alpha)))
                rect = card.adjusted(-3 * i, 10 - 2 * i, 3 * i, 10 + 3 * i)
                painter.drawRoundedRect(rect, 12 + 3 * i, 12 + 3 * i)
        painter.end()

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        if not self.card_geometry().contains(event.position().toPoint()):
            self.close_palette()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        if event.key() == Qt.Key.Key_Escape:
            self.close_palette()
            event.accept()
            return
        super().keyPressEvent(event)

    def cleanup(self) -> None:
        """Release the card, e.g. unload the QML scene before the controller is deleted."""
        window = self.parentWidget()
        if window is not None:
            window.removeEventFilter(self)
        release = getattr(self.card, "release", None)
        if callable(release):
            release()
