"""Ring progress bar with the modernised UX, rendered with plain QWidgets and QPainter.

This is the QWidget twin of :class:`RingProgressBarQML`: same API as :class:`RingProgressBar`,
same look (legend, animated values, center readout, empty state), so both rendering stacks can
be compared side by side.
"""

from __future__ import annotations

import math

from bec_qthemes import material_icon
from qtpy.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from qtpy.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from qtpy.QtWidgets import QBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import PortedPropertiesMixin, TextButton, refresh_kit_theme
from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_bar import RingProgressBar
from bec_widgets.widgets.progress.ring_progress_bar.ring_ux_common import RingStateContainer


class RingCanvas(QWidget):
    """Paints the rings, the center readout and the empty state."""

    def __init__(self, container: "PaintedRingContainer"):
        super().__init__(container)
        self._container = container
        self._snapshots: list[dict] = []
        self._center = ("", "")
        self._max_line_width = 10
        self._start: list[float] = []
        self._target: list[float] = []
        self._progress = 1.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(260)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._on_animation_step)
        self.setMouseTracking(True)
        self.setMinimumSize(60, 60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.add_button = TextButton("Add ring", "neutral", "add", self)
        self.add_button.clicked.connect(container.request_settings)
        self.add_button.hide()

    # ---- state ---------------------------------------------------------------------------

    def set_state(self, snapshots: list[dict], center: tuple[str, str], max_line_width: int):
        """Take new ring snapshots; value changes are animated."""
        shown = self.shown_fractions()
        targets = [snapshot["fraction"] for snapshot in snapshots]
        self._snapshots = snapshots
        self._center = center
        self._max_line_width = max_line_width
        if len(shown) != len(targets):
            shown = targets[:]
        if targets != self._target:
            self._start = shown[: len(targets)]
            self._target = targets
            self._progress = 0.0
            self._animation.stop()
            self._animation.start()
        self.add_button.setVisible(not snapshots)
        self._place_add_button()
        self.update()

    def shown_fractions(self) -> list[float]:
        """Fractions currently drawn, i.e. mid-animation values."""
        if not self._target:
            return []
        return [s + (t - s) * self._progress for s, t in zip(self._start, self._target)]

    def _on_animation_step(self, value: float) -> None:
        self._progress = float(value)
        self.update()

    def stop_animation(self) -> None:
        """Stop the value animation (used on cleanup)."""
        self._animation.stop()

    # ---- geometry ------------------------------------------------------------------------

    def _side(self) -> float:
        return float(min(self.width(), self.height()))

    def _base_radius(self) -> float:
        return (self._side() - 2 * self._max_line_width) / 2

    def ring_at(self, pos: QPointF) -> int:
        """Index of the ring under ``pos`` or -1."""
        dx = pos.x() - self.width() / 2
        dy = pos.y() - self.height() / 2
        distance = math.hypot(dx, dy)
        best, best_delta = -1, float("inf")
        for snapshot in self._snapshots:
            radius = max(1.0, self._base_radius() - snapshot["gap"])
            delta = abs(distance - radius)
            if delta <= snapshot["lineWidth"] / 2 + 2 and delta < best_delta:
                best, best_delta = snapshot["index"], delta
        return best

    def mouseMoveEvent(self, event):  # pylint: disable=invalid-name
        self._container.set_highlighted(self.ring_at(event.position()))
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        self._container.set_highlighted(-1)
        super().leaveEvent(event)

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._place_add_button()

    def _place_add_button(self) -> None:
        hint = self.add_button.sizeHint()
        _circle_y, _radius, caption_top = self._empty_layout()
        self.add_button.setGeometry(
            int((self.width() - hint.width()) / 2), int(caption_top + 28), hint.width(), 32
        )

    # ---- painting ------------------------------------------------------------------------

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = ThemeTokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        if not self._snapshots:
            self._paint_empty(painter, tokens, center)
            painter.end()
            return

        highlighted = self._container.highlighted
        fractions = self.shown_fractions()
        for snapshot, fraction in zip(self._snapshots, fractions):
            radius = max(1.0, self._base_radius() - snapshot["gap"])
            width = snapshot["lineWidth"] + (3 if snapshot["highlighted"] else 0)
            rect = QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)
            painter.setOpacity(0.4 if highlighted >= 0 and not snapshot["highlighted"] else 1.0)

            pen = QPen(QColor(snapshot["trackColor"]), width)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            painter.setPen(pen)
            painter.drawArc(rect, 0, 360 * 16)

            if fraction > 0.001:
                pen = QPen(QColor(snapshot["color"]), width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                span = int(min(fraction, 0.9999) * 360 * 16 * snapshot["direction"])
                painter.drawArc(rect, int(snapshot["startAngle"] * 16), span)
        painter.setOpacity(1.0)

        innermost = self._snapshots[-1]
        inner = max(
            10.0, 2 * (self._base_radius() - innermost["gap"] - innermost["lineWidth"] / 2) * 0.8
        )
        text, caption = self._center
        show_caption = bool(caption) and self._side() > 120
        font = QFont(self.font())
        pixel_size = int(max(12, min(34, self._side() * 0.13)))
        font.setWeight(QFont.Weight.DemiBold)
        # shrink the text to fit the inner circle, like fontSizeMode: HorizontalFit in QML
        while True:
            font.setPixelSize(pixel_size)
            if pixel_size <= 10 or QFontMetricsF(font).horizontalAdvance(text) <= inner - 4:
                break
            pixel_size -= 1
        painter.setFont(font)
        painter.setPen(tokens.fg)
        metrics = painter.fontMetrics()
        text_rect = QRectF(
            center.x() - inner / 2, center.y() - metrics.height() / 2, inner, metrics.height()
        )
        if show_caption:
            text_rect.translate(0, -8)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter,
            metrics.elidedText(text, Qt.TextElideMode.ElideRight, int(text_rect.width())),
        )
        if show_caption:
            font.setPixelSize(11)
            font.setWeight(QFont.Weight.Normal)
            painter.setFont(font)
            painter.setPen(tokens.fg_muted)
            caption_rect = QRectF(text_rect.left(), text_rect.bottom() + 2, text_rect.width(), 16)
            painter.drawText(
                caption_rect,
                Qt.AlignmentFlag.AlignCenter,
                painter.fontMetrics().elidedText(
                    caption, Qt.TextElideMode.ElideRight, int(caption_rect.width())
                ),
            )
        painter.end()

    def _empty_layout(self) -> tuple[float, float, float]:
        """Circle center y, circle radius and caption top of the empty state."""
        radius = min(96, self._side() * 0.5) / 2
        total = 2 * radius + 10 + 18 + 10 + 32
        top = (self.height() - total) / 2
        return top + radius, radius, top + 2 * radius + 10

    def _paint_empty(self, painter: QPainter, tokens: ThemeTokens, center: QPointF) -> None:
        circle_y, radius, caption_top = self._empty_layout()
        painter.setPen(QPen(tokens.border, 6))
        painter.drawEllipse(QPointF(center.x(), circle_y), radius - 3, radius - 3)
        painter.setPen(tokens.fg_muted)
        font = QFont(self.font())
        font.setPixelSize(13)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, caption_top, self.width(), 18), Qt.AlignmentFlag.AlignCenter, "No rings yet"
        )


class LegendRow(QWidget):
    """One legend entry: colour dot, ring name, value and percentage or a done check."""

    def __init__(self, container: "PaintedRingContainer", parent: QWidget):
        super().__init__(parent)
        self._container = container
        self._index = -1
        self._color = QColor()
        self._highlighted = False
        self._hover_color = QColor()
        self._full_label = ""
        self.setFixedHeight(30)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(26, 0, 8, 0)
        layout.setSpacing(8)
        self.label = QLabel(self)
        self.value = QLabel(self)
        self.percent = QLabel(self)
        self.percent.setFixedWidth(36)
        self.percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.value.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.value)
        layout.addWidget(self.percent)

    def set_snapshot(self, snapshot: dict, tokens: ThemeTokens) -> None:
        """Show one ring snapshot."""
        self._index = snapshot["index"]
        self._color = QColor(snapshot["color"])
        self._highlighted = snapshot["highlighted"]
        self._full_label = snapshot["label"]
        self._elide_label()
        self.label.setToolTip(snapshot["label"])
        self.value.setText(snapshot["valueText"])
        if snapshot["done"]:
            self.percent.setPixmap(
                material_icon(
                    "check_circle", size=(28, 28), color=tokens.success, filled=True
                ).scaled(
                    14,
                    14,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.percent.setText(snapshot["percentText"])
        self.label.setStyleSheet(f"color: {tokens.fg.name()}; font-size: 12px;")
        self.value.setStyleSheet(
            f"color: {tokens.fg_muted.name()}; font-size: 12px; font-family: monospace;"
        )
        done_color = tokens.success if snapshot["done"] else tokens.fg
        self.percent.setStyleSheet(
            f"color: {done_color.name()}; font-size: 12px; font-weight: 600;"
        )
        self._hover_color = tokens.hover
        self.update()

    def _elide_label(self) -> None:
        self.label.setText(
            self.label.fontMetrics().elidedText(
                self._full_label, Qt.TextElideMode.ElideRight, max(20, self.label.width())
            )
        )

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._elide_label()

    def enterEvent(self, event):  # pylint: disable=invalid-name
        self._container.set_highlighted(self._index)
        super().enterEvent(event)

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        self._container.set_highlighted(-1)
        super().leaveEvent(event)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if self._highlighted:
            painter.setBrush(self._hover_color)
            painter.drawRoundedRect(QRectF(self.rect()), 6, 6)
        painter.setBrush(self._color)
        painter.drawEllipse(QRectF(8, self.height() / 2 - 5, 10, 10))
        painter.end()


class RingLegend(QWidget):
    """Vertical list of :class:`LegendRow` entries."""

    def __init__(self, container: "PaintedRingContainer"):
        super().__init__(container)
        self._container = container
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._layout.addStretch(1)
        self._layout.addStretch(1)
        self.rows: list[LegendRow] = []

    def set_snapshots(self, snapshots: list[dict]) -> None:
        """Create or reuse rows for the snapshots."""
        tokens = ThemeTokens()
        while len(self.rows) < len(snapshots):
            row = LegendRow(self._container, self)
            self._layout.insertWidget(len(self.rows) + 1, row)
            self.rows.append(row)
        while len(self.rows) > len(snapshots):
            row = self.rows.pop()
            self._layout.removeWidget(row)
            row.deleteLater()
        for row, snapshot in zip(self.rows, snapshots):
            row.set_snapshot(snapshot, tokens)


class PaintedRingContainer(RingStateContainer):
    """Ring container rendered with QPainter and QWidgets."""

    def _init_view(self) -> None:
        self._show_legend = True
        self._box = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._box.setContentsMargins(8, 8, 8, 8)
        self._box.setSpacing(16)
        self.canvas = RingCanvas(self)
        self.legend = RingLegend(self)
        self._box.addWidget(self.canvas, 1)
        self._box.addWidget(self.legend)
        self.layout().addLayout(self._box)

    def _sync_view(self) -> None:
        snapshots = self.snapshots()
        self.canvas.set_state(snapshots, self.center_texts(), self.get_max_ring_size())
        self.legend.set_snapshots(snapshots)
        self._update_arrangement()

    def set_show_legend(self, show: bool) -> None:
        """Show or hide the legend."""
        self._show_legend = bool(show)
        self._update_arrangement()

    def _update_arrangement(self) -> None:
        wide = self.width() >= self.height() * 1.35
        self._box.setDirection(
            QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.TopToBottom
        )
        if wide:
            self.legend.setFixedWidth(int(min(260, self.width() * 0.45)))
            self.legend.setMaximumHeight(16777215)
        else:
            self.legend.setMinimumWidth(0)
            self.legend.setMaximumWidth(16777215)
            self.legend.setFixedHeight(int(min(len(self.rings) * 32, self.height() * 0.38)))
        visible = (
            self._show_legend
            and bool(self.rings)
            and (self.width() > 260 if wide else self.height() > 230)
        )
        self.legend.setVisible(visible)

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        QWidget.resizeEvent(self, event)
        self._update_arrangement()

    def apply_theme(self, _theme: str | None = None) -> None:
        """Re-read theme colours."""
        refresh_kit_theme(self)
        self._sync_view()

    def closeEvent(self, event):  # pylint: disable=invalid-name
        self.canvas.stop_animation()
        super().closeEvent(event)


class RingProgressBarQWidget(PortedPropertiesMixin, RingProgressBar):
    """Ring progress bar with the modernised UX in plain QWidgets; same API as RingProgressBar."""

    PLUGIN = False
    RPC = False
    rpc_widget_class = "RingProgressBar"
    PORTED_FROM = RingProgressBar

    def _create_ring_container(self) -> PaintedRingContainer:
        return PaintedRingContainer(self)

    def apply_theme(self, theme: str):
        super().apply_theme(theme)
        self.ring_progress_bar.apply_theme(theme)

    @property
    def show_legend(self) -> bool:
        """Whether the legend next to the rings is shown."""
        return self.ring_progress_bar._show_legend  # pylint: disable=protected-access

    @show_legend.setter
    def show_legend(self, show: bool):
        self.ring_progress_bar.set_show_legend(show)

    def cleanup(self):
        self.ring_progress_bar.canvas.stop_animation()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = RingProgressBarQWidget()
    for value in (72, 35, 90):
        widget.add_ring().set_value(value)
    widget.show()
    sys.exit(app.exec())
