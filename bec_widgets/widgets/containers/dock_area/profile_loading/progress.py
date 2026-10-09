"""
Progress card shown over the dock area while a profile fills its docks.

The card floats above the docks, so showing and hiding it never moves the layout. It appears only
when loading takes longer than a short delay, which keeps fast loads free of any flash.
"""

from __future__ import annotations

from qtpy.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from qtpy.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.widgets.containers.dock_area.profile_loading.common import loading_palette

#: Loads that finish faster than this never show the card.
SHOW_DELAY_MS = 180
CARD_WIDTH = 380
CARD_HEIGHT = 64
CARD_MARGIN = 16


class ProfileLoadProgressBase(QWidget):
    """
    Interface of the loading progress card.

    Args:
        parent(QWidget): Widget the card floats over (the dock manager).
    """

    cancel_requested = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("profileLoadProgress")
        self.setProperty("skip_settings", True)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self._profile = ""
        self._done = 0
        self._total = 0
        self._current = ""
        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.setInterval(SHOW_DELAY_MS)
        self._show_timer.timeout.connect(self._reveal)
        self.hide()

    def begin(self, profile: str, total: int) -> None:
        """Start reporting a load of *total* widgets for *profile*; the card shows after a delay."""
        self._profile = profile
        self.update_progress(0, total, "")
        self._show_timer.start()

    def update_progress(self, done: int, total: int, current: str) -> None:
        """Report that *done* of *total* widgets are built and *current* is next."""
        self._done = done
        self._total = total
        self._current = current
        self._render()

    def finish(self) -> None:
        """Hide the card; called when the load completes or is cancelled."""
        self._show_timer.stop()
        if self.isVisible():
            self._fade_out()

    def reposition(self) -> None:
        """Keep the card in the bottom-right corner of its parent, clear of the dock title bars."""
        parent = self.parentWidget()
        if parent is None:
            return
        self.move(
            max(0, parent.width() - self.width() - CARD_MARGIN),
            max(0, parent.height() - self.height() - CARD_MARGIN),
        )

    def _reveal(self) -> None:
        self.reposition()
        self.show()
        self.raise_()

    def _fade_out(self) -> None:
        self.hide()

    def _render(self) -> None:  # pragma: no cover - implemented by subclasses
        pass

    def subtitle(self) -> str:
        """Second line of the card."""
        if self._total <= 0:
            return "Preparing layout"
        if self._done >= self._total:
            return f"{self._total} of {self._total} ready"
        current = f" · {self._current}" if self._current else ""
        return f"{self._done} of {self._total} ready{current}"

    def fraction(self) -> float:
        """Completed fraction in [0, 1]."""
        return 0.0 if self._total <= 0 else min(1.0, self._done / self._total)


class ProfileLoadProgress(ProfileLoadProgressBase):
    """QWidget implementation of the progress card."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._title = QLabel(self)
        title_font = QFont(self.font())
        title_font.setBold(True)
        self._title.setFont(title_font)
        self._subtitle = QLabel(self)
        self._cancel = QPushButton("Cancel", self)
        self._cancel.setObjectName("profileLoadCancel")
        self._cancel.setFlat(True)
        self._cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel.clicked.connect(self.cancel_requested.emit)

        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(self._title)
        text.addWidget(self._subtitle)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 8, 10, 12)
        row.addLayout(text, 1)
        row.addWidget(self._cancel, 0, Qt.AlignmentFlag.AlignVCenter)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setDuration(220)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._on_fade_finished)

    def _reveal(self) -> None:
        self._fade.stop()
        self._opacity.setOpacity(1.0)
        super()._reveal()

    def _fade_out(self) -> None:
        self._fade.stop()
        self._fade.setStartValue(self._opacity.opacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _on_fade_finished(self) -> None:
        if self._fade.endValue() == 0.0:
            self.hide()
            self._opacity.setOpacity(1.0)

    def _render(self) -> None:
        colors = loading_palette()
        self._title.setText(f"Loading workspace “{self._profile}”")
        self._subtitle.setText(self.subtitle())
        self._title.setStyleSheet(f"color: {colors['text'].name()}; background: transparent;")
        self._subtitle.setStyleSheet(f"color: {colors['muted'].name()}; background: transparent;")
        self._cancel.setStyleSheet(
            f"QPushButton {{ color: {colors['accent'].name()}; border: none; padding: 6px 10px;"
            f" background: transparent; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {colors['block'].name()}; border-radius: 6px; }}"
        )
        self.update()

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        """Paint the card (or skeleton) with colors from the active theme."""
        colors = loading_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        card = QPainterPath()
        card.addRoundedRect(rect, 10, 10)
        painter.fillPath(card, colors["card"])
        painter.setPen(QPen(colors["border"], 1))
        painter.drawPath(card)
        # Progress track along the bottom edge, clipped to the card's rounded corners
        painter.setClipPath(card)
        track = QRectF(rect.left(), rect.bottom() - 3, rect.width(), 3)
        painter.fillRect(track, colors["block"])
        done = QRectF(track.left(), track.top(), track.width() * self.fraction(), track.height())
        painter.fillRect(done, QColor(colors["accent"]))
        painter.end()
