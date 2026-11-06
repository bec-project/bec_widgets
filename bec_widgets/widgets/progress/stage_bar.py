"""
Shared painted building blocks of the status widgets: tone colours, a tone chip and the stage bar
(a painted progress bar with a centred label), used by the scan progress bar, the scan queue and
the status bar pills.
"""

from __future__ import annotations

from enum import StrEnum

from qtpy.QtCore import Property, QPointF, QRectF, QSize, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPainterPath, QPen
from qtpy.QtWidgets import QApplication, QLabel, QSizePolicy, QWidget

from bec_widgets.utils.theme_utils import css, theme_colors


class Tone(StrEnum):
    """Colour roles of chips, icons and row flashes."""

    NEUTRAL = "neutral"
    RUN = "run"
    OK = "ok"
    WARN = "warn"
    BAD = "bad"
    ACCENT = "accent"


class BarMode(StrEnum):
    """What a StageBar shows."""

    IDLE = "idle"  # empty track, muted label
    BUSY = "busy"  # something runs without a known progress: moving stripes
    PROGRESS = "progress"  # filled to the fraction
    DONE = "done"  # full, ok colour
    ERROR = "error"  # full, danger colour
    PAUSED = "paused"  # filled to the fraction, warning colour


def mono_font(point_delta: float = 0, bold: bool = False) -> QFont:
    """Return the system fixed-width font, optionally resized and bold."""
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    base = QApplication.font().pointSizeF() if QApplication.instance() else 10
    font.setPointSizeF(max(6.0, base + point_delta))
    font.setBold(bold)
    return font


class Chip(QLabel):
    """A small rounded label with a tone colour, used for states and metadata."""

    TONES = tuple(Tone)

    def __init__(
        self, text: str = "", tone: Tone | str = Tone.NEUTRAL, parent: QWidget | None = None
    ):
        super().__init__(text, parent)
        self._tone = Tone(tone)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.refresh_style()

    def set_tone(self, tone: Tone | str) -> None:
        """Change the tone and restyle."""
        tone = Tone(tone)
        if tone != self._tone:
            self._tone = tone
            self.refresh_style()

    def refresh_style(self) -> None:
        """Re-read the theme colours."""
        colors = theme_colors()
        tone_color = {
            Tone.NEUTRAL: colors["muted"],
            Tone.RUN: colors["run"],
            Tone.OK: colors["ok"],
            Tone.WARN: colors["warn"],
            Tone.BAD: colors["bad"],
            Tone.ACCENT: colors["primary"],
        }.get(self._tone, colors["muted"])
        if self._tone == Tone.NEUTRAL:
            bg, fg, border = css(colors["fg"], 0.06), css(colors["fg"]), css(colors["border"])
        else:
            bg, fg, border = css(tone_color, 0.16), css(tone_color), css(tone_color, 0.45)
        self.setStyleSheet(
            f"QLabel {{ background: {bg}; color: {fg}; border: 1px solid {border};"
            f" border-radius: 9px; padding: 1px 7px; }}"
        )


class StageBar(QWidget):
    """
    A painted progress bar with a centred label.

    Modes:
        busy: animated stripes, for steps without measurable progress.
        progress: a filled share of the bar.
        done / error / paused / idle: a full or empty bar in the matching colour.

    With fill_height the bar grows into all the vertical space it is given and its label grows
    with it; the bar height is then the minimum.
    """

    # How the label grows on a bar taller than its minimum: the text height grows by TEXT_GROWTH
    # per pixel of extra bar height, up to TEXT_MAX_SHARE of the bar height, and the text may use
    # at most TEXT_WIDTH_SHARE of the bar width (minus TEXT_PADDING). Sizes snap to TEXT_STEP
    # points. The width cap is computed for a reserved number of characters rather than the live
    # text: the longest label seen in this scan, rounded up to RESERVE_STEP (at least
    # RESERVE_MIN). A label that changes length on a tick ("0:59" -> "1:00") keeps its size; the
    # reservation only grows within a scan and is reset when a new scan starts.
    TEXT_GROWTH = 0.45
    TEXT_MAX_SHARE = 0.50
    TEXT_WIDTH_SHARE = 0.85
    TEXT_PADDING = 12
    TEXT_STEP = 0.5
    RESERVE_MIN = 16
    RESERVE_STEP = 4

    # emitted when the text scale or the stretched state changes, for controls next to the bar
    sizing_changed = Signal()

    def __init__(self, parent: QWidget | None = None, height: int = 24):
        super().__init__(parent)
        self._mode = BarMode.IDLE
        self._fraction = 0.0
        self._text = ""
        self._phase = 0.0
        self._bar_height = height
        self._fill_height = False
        self._scale = 1.0
        self._stretched = False
        self._reserved = self.RESERVE_MIN
        self._reserve_text = ""
        self.corner_radius: float | None = None  # fixed corner radius, else scaled with height
        self.label_pixel_size: int | None = None  # fixed label size in pixels, else scaled
        # width the label is scaled for on a stretched bar, set by the host from its whole row:
        # the bar's own width changes with the controls next to it (e.g. a Stop button that
        # scales with the label), and following it would make the two resize each other
        self.scale_width: float | None = None
        self._font_key: tuple | None = None
        self._font: QFont | None = None
        self._stripe_timer = QTimer(self)
        self._stripe_timer.setInterval(100)  # 10 Hz is enough for the stripes to read as moving
        self._stripe_timer.timeout.connect(self._advance_stripes)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(80)

    def sizeHint(self) -> QSize:
        return QSize(240, self._bar_height)

    def minimumSizeHint(self) -> QSize:
        return QSize(80, self._bar_height)

    def set_bar_height(self, height: int) -> None:
        """Set the bar height in pixels."""
        self._bar_height = max(10, height)
        self.updateGeometry()
        self.update()

    def get_bar_height(self) -> int:
        """The bar height in pixels."""
        return self._bar_height

    bar_height = Property(int, get_bar_height, set_bar_height)

    def set_fill_height(self, fill: bool) -> None:
        """Grow into all the vertical space the layout gives, with the label scaled to match."""
        self._fill_height = fill
        vertical = QSizePolicy.Policy.Expanding if fill else QSizePolicy.Policy.Fixed
        self.setSizePolicy(QSizePolicy.Policy.Expanding, vertical)
        self.updateGeometry()
        self._sync_sizing()
        self.update()

    def get_fill_height(self) -> bool:
        """Whether the bar fills the vertical space it is given."""
        return self._fill_height

    fill_height = Property(bool, get_fill_height, set_fill_height)

    def text_scale(self, height: float) -> float:
        """
        How much larger than normal text should be on a bar of this height. Shared with
        controls next to the bar, such as a Stop button, so they read as one control.
        """
        if not self._fill_height or height <= self._bar_height:
            return 1.0
        base = QFontMetricsF(mono_font(-1)).height()
        target = base + self.TEXT_GROWTH * (height - self._bar_height)
        target = min(target, height * self.TEXT_MAX_SHARE)
        return max(1.0, target / base)

    def _reserve_for(self, text: str) -> int:
        step = self.RESERVE_STEP
        return max(self.RESERVE_MIN, -(-len(text) // step) * step)

    def reserve(self, text: str) -> None:
        """
        Reserve room for a label at least this long. The reference text only changes when the
        rounded reservation grows, so labels of the same length never change the size.
        """
        reserved = self._reserve_for(text)
        if reserved > self._reserved:
            self._reserved, self._reserve_text = reserved, text
            self._sync_sizing()

    def reset_reserved(self) -> None:
        """Size for the current text again, e.g. when a new scan starts."""
        reserved = self._reserve_for(self._text)
        if (reserved, self._text) != (self._reserved, self._reserve_text):
            self._reserved, self._reserve_text = reserved, self._text
            self._sync_sizing()

    def _reference_text(self) -> str:
        # the reserved label padded to the reserved length; measuring real characters keeps the
        # estimate right for a proportional fallback font as well as for a monospace one
        return self._reserve_text.ljust(self._reserved, "0")

    def label_scale(self, height: float, width: float) -> float:
        """
        The label scale for a bar of this size: 1 at the minimum height, growing gently on a
        taller bar, capped so the reserved number of characters fits the width. It does not
        depend on the live text, so it stays put while the text changes.
        """
        scale = self.text_scale(height)
        if scale <= 1.0:
            return 1.0
        base_font = mono_font(-1)
        reserved_width = QFontMetricsF(base_font).horizontalAdvance(self._reference_text())
        room = (width - self.TEXT_PADDING) * self.TEXT_WIDTH_SHARE
        scale = min(scale, max(1.0, room / reserved_width))
        base = base_font.pointSizeF()
        size = max(base, round(base * scale / self.TEXT_STEP) * self.TEXT_STEP)
        return size / base

    def label_font(self, height: float, width: float) -> QFont:
        """The label font for a bar of this size (see label_scale), cached per size."""
        key = (round(height), round(width), self._reference_text(), self._fill_height)
        key += (self.label_pixel_size,)
        if key != self._font_key or self._font is None:
            font = mono_font(-1)
            if self.label_pixel_size:
                font.setPixelSize(self.label_pixel_size)
            else:
                font.setPointSizeF(font.pointSizeF() * self.label_scale(height, width))
            self._font_key, self._font = key, font
        return self._font

    @property
    def mode(self) -> BarMode:
        """The current display mode."""
        return self._mode

    @property
    def text(self) -> str:
        """The label drawn on the bar."""
        return self._text

    @property
    def fraction(self) -> float:
        """The filled share of the bar, 0..1."""
        return self._fraction

    def set_state(self, mode: BarMode | str, fraction: float = 0.0, text: str = "") -> None:
        """
        Update what the bar shows.

        Args:
            mode(BarMode | str): busy, progress, done, error, paused or idle.
            fraction(float): Filled share for the progress mode, 0..1.
            text(str): Label drawn in the middle of the bar.
        """
        mode = BarMode(mode)
        fraction = min(1.0, max(0.0, fraction))
        if (mode, fraction, text) == (self._mode, self._fraction, self._text):
            return
        text_changed = text != self._text
        self._mode, self._fraction, self._text = mode, fraction, text
        self._sync_timer()
        if text_changed:
            self.reserve(text)  # grows within a scan, never shrinks per tick
            self._sync_tooltip()
        self.update()

    def _bar_rect(self) -> QRectF:
        bar_height = max(self._bar_height, self.height()) if self._fill_height else self._bar_height
        rect = QRectF(0.5, 0.5, self.width() - 1, bar_height - 1)
        rect.moveTop((self.height() - bar_height) / 2 + 0.5)
        return rect

    def _label_width(self, rect: QRectF) -> float:
        if self._fill_height and self.scale_width:
            return min(rect.width(), self.scale_width) if rect.width() < 1 else self.scale_width
        return rect.width()

    def _sync_tooltip(self) -> None:
        """Show the full label as a tooltip only while the painted label is cut."""
        rect = self._bar_rect()
        metrics = QFontMetricsF(self.label_font(rect.height(), self._label_width(rect)))
        cut = bool(self._text) and metrics.horizontalAdvance(self._text) > rect.width() - 12
        tooltip = self._text if cut else ""
        if tooltip != self.toolTip():
            self.setToolTip(tooltip)

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._sync_tooltip()
        self._sync_sizing()

    def _sync_sizing(self) -> None:
        rect = self._bar_rect()
        scale = self.label_scale(rect.height(), self._label_width(rect))
        stretched = self._fill_height and self.height() > self._bar_height
        if (scale, stretched) != (self._scale, self._stretched):
            self._scale, self._stretched = scale, stretched
            self.sizing_changed.emit()

    @property
    def scale(self) -> float:
        """The label's current scale (1.0 at the minimum height)."""
        return self._scale

    @property
    def stretched(self) -> bool:
        """Whether the bar fills more than its minimum height."""
        return self._stretched

    def _sync_timer(self) -> None:
        # a minimized window keeps its widgets "visible"; Qt sends them a spontaneous hide and,
        # on restore, a show event, but a state update while minimized must not restart the timer
        if self._mode == BarMode.BUSY and self.isVisible() and not self.window().isMinimized():
            if not self._stripe_timer.isActive():
                self._stripe_timer.start()
        else:
            self._stripe_timer.stop()

    def showEvent(self, event):  # pylint: disable=invalid-name
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event):  # pylint: disable=invalid-name
        super().hideEvent(event)
        self._stripe_timer.stop()

    def _advance_stripes(self) -> None:
        self._phase = (self._phase + 2.4) % 16
        self.update()

    def cleanup(self) -> None:
        """Stop the stripe animation."""
        self._stripe_timer.stop()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        colors = theme_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self._bar_rect()
        if self.corner_radius is not None:
            radius = min(self.corner_radius, rect.height() / 2)
        else:
            radius = min(10.0, max(6.0, rect.height() * 0.12), rect.height() / 2)
        track = QPainterPath()
        track.addRoundedRect(rect, radius, radius)

        tone = {
            BarMode.BUSY: colors["run"],
            BarMode.PROGRESS: colors["primary"],
            BarMode.DONE: colors["ok"],
            BarMode.ERROR: colors["bad"],
            BarMode.PAUSED: colors["warn"],
        }.get(self._mode, colors["muted"])

        painter.fillPath(track, _with_alpha(colors["fg"], 0.08))
        fill_rect = QRectF(rect)
        if self._mode in (BarMode.PROGRESS, BarMode.PAUSED):
            fill_rect.setWidth(rect.width() * self._fraction)
        elif self._mode == BarMode.IDLE:
            fill_rect.setWidth(0)

        painter.save()
        painter.setClipPath(track)
        if self._mode == BarMode.BUSY:
            painter.fillRect(rect, _with_alpha(tone, 0.22))
            stripe = _with_alpha(tone, 0.38)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(stripe)
            h = rect.height()
            x = rect.left() - h - 16 + self._phase
            while x < rect.right() + h:
                poly = QPainterPath()
                poly.moveTo(QPointF(x, rect.bottom()))
                poly.lineTo(QPointF(x + 8, rect.bottom()))
                poly.lineTo(QPointF(x + 8 + h, rect.top()))
                poly.lineTo(QPointF(x + h, rect.top()))
                poly.closeSubpath()
                painter.drawPath(poly)
                x += 16
        elif fill_rect.width() > 0:
            painter.fillRect(
                fill_rect, tone if self._mode != BarMode.PAUSED else _with_alpha(tone, 0.8)
            )
        painter.restore()

        painter.setPen(QPen(_with_alpha(colors["border"], 0.9), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(track)

        if self._text:
            font = self.label_font(rect.height(), self._label_width(rect))
            painter.setFont(font)
            flags = Qt.AlignmentFlag.AlignCenter
            text_rect = QRectF(rect.toAlignedRect())  # both passes on whole pixels
            text = painter.fontMetrics().elidedText(
                self._text, Qt.TextElideMode.ElideRight, int(rect.width() - 12)
            )
            filled = self._mode in (BarMode.DONE, BarMode.ERROR) or (
                self._mode == BarMode.PROGRESS and self._fraction > 0
            )
            painter.setPen(colors["muted"] if self._mode == BarMode.IDLE else colors["fg"])
            painter.drawText(text_rect, flags, text)
            if filled:
                painter.save()
                painter.setClipRect(fill_rect)
                painter.setPen(colors["on_primary"])
                painter.drawText(text_rect, flags, text)
                painter.restore()
        painter.end()


def _with_alpha(color: QColor, alpha: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(alpha)
    return c
