"""
Skeleton placeholders that stand in for dock widgets while a profile loads.

A placeholder occupies the dock of a widget that is not built yet. It carries the widget class and
object name from the profile manifest, so a snapshot taken mid-load still describes the full
profile, and it shows a shimmering skeleton shaped like the widget it stands for.
"""

from __future__ import annotations

import math
import random

from qtpy.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from bec_widgets.widgets.containers.dock_area.profile_loading.common import (
    STATE_TEXT,
    PlaceholderState,
    loading_palette,
    shimmer_phase,
    skeleton_kind,
    skeleton_seed,
)


class DockPlaceholder(QWidget):
    """
    Base class for profile loading placeholders.

    Args:
        widget_class(str): Class name of the widget this placeholder stands for.
        object_name(str): Object name the real widget will get.
        icon_name(str | None): Material icon of the widget class, shown on the dock tab.
        parent(QWidget | None): Parent widget.
    """

    load_requested = Signal(str)

    def __init__(
        self,
        widget_class: str,
        object_name: str,
        icon_name: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.profile_widget_class = widget_class
        self.profile_object_name = object_name
        if icon_name:
            # Read by the dock area to put the widget's icon on the dock tab
            self.ICON_NAME = icon_name
        self.setObjectName(object_name)
        # The state manager must not save or restore anything for a placeholder
        self.setProperty("skip_settings", True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._state: PlaceholderState = "queued"
        self._message = ""

    @property
    def state(self) -> PlaceholderState:
        """Current loading state."""
        return self._state

    @property
    def message(self) -> str:
        """Error message shown in the failed state."""
        return self._message

    def set_state(self, state: PlaceholderState, message: str = "") -> None:
        """
        Update the loading state shown by the placeholder.

        Args:
            state(PlaceholderState): New state.
            message(str): Optional detail, used for the failed state.
        """
        self._state = state
        self._message = message
        self._on_state_changed()

    def _on_state_changed(self) -> None:  # pragma: no cover - implemented by subclasses
        pass

    def minimumSizeHint(self):  # noqa: N802 - Qt API
        """Keep placeholders from forcing a large minimum dock size."""
        hint = super().minimumSizeHint()
        hint.setWidth(min(max(hint.width(), 0), 120))
        hint.setHeight(min(max(hint.height(), 0), 80))
        return hint


class _ShimmerTicker:
    """One timer animates every visible skeleton, so they shimmer in sync and cost one wake-up."""

    _timer: QTimer | None = None
    _targets: set[QWidget] = set()

    @classmethod
    def add(cls, widget: QWidget) -> None:
        """Animate *widget* until it is removed."""
        cls._targets.add(widget)
        if cls._timer is None:
            cls._timer = QTimer()
            cls._timer.setInterval(33)
            cls._timer.timeout.connect(cls._tick)
        if not cls._timer.isActive():
            cls._timer.start()

    @classmethod
    def remove(cls, widget: QWidget) -> None:
        """Stop animating *widget*; the timer stops with the last one."""
        cls._targets.discard(widget)
        if not cls._targets and cls._timer is not None:
            cls._timer.stop()
            cls._timer.deleteLater()
            cls._timer = None

    @classmethod
    def _tick(cls) -> None:
        for widget in list(cls._targets):
            widget.update()


class SkeletonPlaceholder(DockPlaceholder):
    """QWidget placeholder that paints a shimmering skeleton of the widget it stands for."""

    def __init__(
        self,
        widget_class: str,
        object_name: str,
        icon_name: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(widget_class, object_name, icon_name, parent)
        self._kind = skeleton_kind(widget_class)
        self._seed = skeleton_seed(object_name)

        self._action = QPushButton("Load now", self)
        self._action.setObjectName("placeholderAction")
        self._action.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action.clicked.connect(lambda: self.load_requested.emit(self.profile_object_name))
        self._action.hide()

        # The button is the only child; the skeleton itself is painted
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._action)
        row.addStretch(1)
        layout.addLayout(row)

    # Qt events ------------------------------------------------------------------------------

    def showEvent(self, event):  # noqa: N802 - Qt API
        """Start the shimmer when the skeleton becomes visible."""
        super().showEvent(event)
        if self._animated():
            _ShimmerTicker.add(self)

    def hideEvent(self, event):  # noqa: N802 - Qt API
        """Stop the shimmer while hidden."""
        _ShimmerTicker.remove(self)
        super().hideEvent(event)

    def closeEvent(self, event):  # noqa: N802 - Qt API
        """Stop the shimmer before the placeholder is deleted."""
        _ShimmerTicker.remove(self)
        super().closeEvent(event)

    def _animated(self) -> bool:
        return self._state in ("queued", "loading")

    def _on_state_changed(self) -> None:
        self._action.setVisible(self._state in ("paused", "failed"))
        self._action.setText("Retry" if self._state == "failed" else "Load now")
        if self._animated() and self.isVisible():
            _ShimmerTicker.add(self)
        else:
            _ShimmerTicker.remove(self)
        self.update()

    # Painting -------------------------------------------------------------------------------

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        """Paint the card (or skeleton) with colors from the active theme."""
        colors = loading_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), colors["window"])

        area = QRectF(self.rect()).adjusted(14, 14, -14, -14)
        caption_height = 30 if self._state in ("queued", "loading") else 78
        body = QRectF(area.left(), area.top(), area.width(), area.height() - caption_height - 10)
        if body.height() > 24 and body.width() > 40:
            path, accent_path = self._skeleton_paths(body)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._block_brush(colors, area))
            painter.drawPath(path)
            if accent_path is not None:
                accent = QColor(colors["accent"])
                accent.setAlphaF(0.28 if self._animated() else 0.14)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(accent, 2.0))
                painter.drawPath(accent_path)

        caption = QRectF(area.left(), area.bottom() - caption_height, area.width(), caption_height)
        self._paint_caption(painter, caption, colors)
        painter.end()

    def _block_brush(self, colors: dict[str, QColor], area: QRectF):
        if not self._animated():
            return colors["block"]
        # A soft band sweeps diagonally across all blocks
        width = max(area.width(), 1.0)
        phase = shimmer_phase()
        x = area.left() - width * 0.6 + phase * width * 2.2
        gradient = QLinearGradient(QPointF(x - width * 0.35, 0), QPointF(x + width * 0.35, 0))
        gradient.setColorAt(0.0, colors["block"])
        gradient.setColorAt(0.5, colors["shine"])
        gradient.setColorAt(1.0, colors["block"])
        return gradient

    def _skeleton_paths(self, body: QRectF) -> tuple[QPainterPath, QPainterPath | None]:
        """Blocks to shimmer, plus an optional accent trace, shaped like the widget kind."""
        rng = random.Random(self._seed)
        if self._kind == "plot":
            return self._plot_paths(body, rng)
        if self._kind == "list":
            return self._list_path(body, rng), None
        return self._form_path(body, rng), None

    @staticmethod
    def _plot_paths(body: QRectF, rng: random.Random) -> tuple[QPainterPath, QPainterPath | None]:
        # Toolbar row, plot frame with axis ticks and a faint trace
        path = QPainterPath()
        for i in range(5):
            path.addRoundedRect(QRectF(body.left() + i * 26, body.top(), 18, 18), 4, 4)
        frame = QRectF(body.left() + 34, body.top() + 30, body.width() - 34, body.height() - 52)
        outline = QPainterPath()
        outline.addRoundedRect(frame, 6, 6)
        inner = QPainterPath()
        inner.addRoundedRect(frame.adjusted(2, 2, -2, -2), 5, 5)
        path.addPath(outline.subtracted(inner))
        ticks_y = max(2, int(frame.height() // 48))
        for i in range(ticks_y + 1):
            y = frame.top() + i * (frame.height() / ticks_y) - 4
            path.addRoundedRect(QRectF(body.left(), y, 24, 8), 3, 3)
        ticks_x = max(2, int(frame.width() // 90))
        for i in range(ticks_x + 1):
            x = frame.left() + i * (frame.width() / ticks_x) - 14
            path.addRoundedRect(QRectF(x, frame.bottom() + 10, 28, 8), 3, 3)
        if frame.width() <= 60 or frame.height() <= 40:
            return path, None
        trace = QPainterPath()
        freq = 1.5 + rng.random() * 2
        shift = rng.random() * math.pi
        steps = 64
        for i in range(steps + 1):
            t = i / steps
            y = 0.5 + 0.32 * math.sin(t * freq * math.pi + shift) * math.exp(-1.2 * t)
            point = QPointF(
                frame.left() + 10 + t * (frame.width() - 20),
                frame.top() + 10 + y * (frame.height() - 20),
            )
            if i == 0:
                trace.moveTo(point)
            else:
                trace.lineTo(point)
        return path, trace

    @staticmethod
    def _list_path(body: QRectF, rng: random.Random) -> QPainterPath:
        # Header, then rows with a status dot and a label of varying length
        path = QPainterPath()
        path.addRoundedRect(QRectF(body.left(), body.top(), body.width() * 0.4, 14), 4, 4)
        y = body.top() + 30
        while y + 16 < body.bottom():
            path.addEllipse(QRectF(body.left(), y, 14, 14))
            length = body.width() * (0.35 + 0.5 * rng.random())
            path.addRoundedRect(QRectF(body.left() + 24, y + 1, length - 24, 12), 4, 4)
            path.addRoundedRect(
                QRectF(body.right() - body.width() * 0.12, y + 1, body.width() * 0.12, 12), 4, 4
            )
            y += 30
        return path

    @staticmethod
    def _form_path(body: QRectF, rng: random.Random) -> QPainterPath:
        # Labels with input fields and a primary action
        path = QPainterPath()
        y = body.top()
        field_w = body.width()
        while y + 52 < body.bottom():
            path.addRoundedRect(
                QRectF(body.left(), y, field_w * (0.18 + 0.15 * rng.random()), 10), 3, 3
            )
            path.addRoundedRect(QRectF(body.left(), y + 16, field_w, 26), 6, 6)
            y += 58
        button_w = min(140, field_w * 0.4)
        path.addRoundedRect(QRectF(body.right() - button_w, y + 4, button_w, 30), 6, 6)
        return path

    def _paint_caption(self, painter: QPainter, rect: QRectF, colors: dict[str, QColor]) -> None:
        font = QFont(self.font())
        font.setPointSizeF(max(8.0, font.pointSizeF() * 0.95))
        painter.setFont(font)
        title = self.profile_widget_class
        state = STATE_TEXT[self._state]
        if self._state in ("queued", "loading"):
            painter.setPen(colors["muted"])
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                f"{title}  ·  {state}",
            )
            return
        color = colors["danger"] if self._state == "failed" else colors["muted"]
        painter.setPen(color)
        text_rect = QRectF(rect.left(), rect.top(), rect.width(), 22)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{title}  ·  {state}")
        if self._message:
            painter.setPen(colors["muted"])
            metrics = painter.fontMetrics()
            detail = metrics.elidedText(
                self._message, Qt.TextElideMode.ElideRight, int(rect.width())
            )
            painter.drawText(
                QRectF(rect.left(), rect.top() + 20, rect.width(), 18),
                Qt.AlignmentFlag.AlignCenter,
                detail,
            )
