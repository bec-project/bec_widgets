"""QWidget controls of the BEC UI kit.

They mirror the ``BecUi`` QML controls in ``bec_widgets/utils/quick/qml/BecUi`` one to one, so
the QML and QWidget versions of a widget look and behave the same. Colours and metrics come from
the same :class:`~bec_widgets.utils.quick.tokens.ThemeTokens`.

Every control follows ``app.theme`` by itself: when the user switches between light and dark,
its ``refresh_theme(tokens)`` method runs. :func:`refresh_kit_theme` re-themes a whole subtree
by hand, for controls created before a theme was applied.

See ``bec_widgets/utils/quick/README.md`` for the component reference.
"""

from __future__ import annotations

from typing import Sequence

from bec_qthemes import material_icon
from qtpy.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from qtpy.QtGui import QColor, QFont, QKeySequence, QPainter, QPen, QPixmap
from qtpy.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.quick.tokens import ThemeTokens, app_theme

__all__ = [
    "Badge",
    "Banner",
    "Card",
    "Divider",
    "EmptyState",
    "FormField",
    "IconButton",
    "LinearProgress",
    "PortedPropertiesMixin",
    "SearchField",
    "SegmentedControl",
    "Spinner",
    "StatusPill",
    "SuffixLineEdit",
    "TextButton",
    "ThemeTokens",
    "ToggleSwitch",
    "field_qss",
    "refresh_kit_theme",
    "rgba",
    "set_invalid",
]


def rgba(color: QColor, alpha: float) -> str:
    """Return a QSS ``rgba()`` string for ``color`` with alpha in 0..1."""
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {int(alpha * 255)})"


def refresh_kit_theme(root: QWidget) -> ThemeTokens:
    """Re-theme every kit control below ``root`` and return the current tokens."""
    tokens = ThemeTokens.current()
    for widget in root.findChildren(QWidget):
        refresh = getattr(widget, "refresh_theme", None)
        if callable(refresh):
            refresh(tokens)
    return tokens


def _tone_color(tokens: ThemeTokens, tone: QColor | str) -> QColor:
    """Text colour for a tone given by name or as a colour."""
    if isinstance(tone, str):
        return tokens.tone_text(tone)
    return QColor(tone)


def _px_font(widget: QWidget, size: int, weight: QFont.Weight | None = None) -> QFont:
    font = QFont(widget.font())
    font.setPixelSize(size)
    if weight is not None:
        font.setWeight(weight)
    return font


class _ThemeFollower:
    """Mixin: call ``refresh_theme(tokens)`` whenever ``app.theme`` changes."""

    def _follow_theme(self) -> None:
        theme = app_theme()
        if theme is not None:
            theme.theme_changed.connect(self._on_app_theme_changed)

    def _on_app_theme_changed(self, *_args) -> None:
        refresh = getattr(self, "refresh_theme", None)
        if callable(refresh):
            refresh(ThemeTokens.current())


def field_qss(tokens: ThemeTokens) -> str:
    """Stylesheet for inputs inside kit cards; ``invalid=true`` marks a field with an error."""
    return f"""
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background: {tokens.field.name()};
            color: {tokens.fg.name()};
            border: 1px solid {tokens.border.name()};
            border-radius: {tokens.metrics["radiusSmall"]}px;
            padding: 0px 8px;
            min-height: 30px;
            font-size: {tokens.metrics["fontBody"]}px;
            selection-background-color: {tokens.primary.name()};
        }}
        QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
            border-color: {tokens.fg_subtle.name()};
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 2px solid {tokens.primary.name()};
            padding: 0px 7px;
        }}
        QLineEdit[invalid="true"], QComboBox[invalid="true"],
        QSpinBox[invalid="true"], QDoubleSpinBox[invalid="true"] {{
            border: 2px solid {tokens.danger.name()};
            padding: 0px 7px;
        }}
        QLineEdit:disabled, QComboBox:disabled {{ color: {tokens.fg_subtle.name()}; }}
        QComboBox::drop-down {{ border: none; width: 22px; }}
    """


def set_invalid(widget: QWidget, invalid: bool) -> None:
    """Toggle the ``invalid`` style of a field styled with :func:`field_qss`."""
    if bool(widget.property("invalid")) == invalid:
        return
    widget.setProperty("invalid", invalid)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _spinner_pixmap(size: int, color: QColor, angle: float, ratio: float = 2.0) -> QPixmap:
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    _paint_spinner(painter, QRectF(0, 0, size, size), color, angle)
    painter.end()
    return pixmap


def _paint_spinner(painter: QPainter, rect: QRectF, color: QColor, angle: float) -> None:
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    width = max(1.5, rect.width() / 8)
    arc = rect.adjusted(width / 2, width / 2, -width / 2, -width / 2)
    track = QColor(color)
    track.setAlphaF(0.2)
    painter.setPen(QPen(track, width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(arc)
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawArc(arc, int((90 - angle) * 16), int(-100 * 16))


# --------------------------------------------------------------------------------------------
# Buttons
# --------------------------------------------------------------------------------------------


class IconButton(_ThemeFollower, QToolButton):
    """Flat square icon button with hover feedback, matching ``BecUi.IconButton``.

    The tip is required in practice: it is the tooltip and the accessible name.

    Args:
        icon_name(str): Material icon name.
        tip(str): Tooltip and accessible name.
        parent(QWidget | None): Parent widget.
        size(int): Icon size in pixels.
        danger(bool): Tint the icon red, for destructive actions.
        compact(bool): 28 px instead of 30 px.
    """

    def __init__(
        self,
        icon_name: str,
        tip: str = "",
        parent: QWidget | None = None,
        size: int = 18,
        danger: bool = False,
        compact: bool = False,
    ):
        super().__init__(parent)
        self._icon_name = icon_name
        self._danger = danger
        self.setToolTip(tip)
        self.setAccessibleName(tip)
        self.setAutoRaise(True)
        side = 28 if compact else 30
        self.setFixedSize(side, side)
        self.setIconSize(QSize(size, size))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(lambda _checked: self.refresh_theme(ThemeTokens.current()))
        self.refresh_theme(ThemeTokens.current())
        self._follow_theme()

    def set_icon_name(self, icon_name: str) -> None:
        """Change the Material icon."""
        self._icon_name = icon_name
        self.refresh_theme(ThemeTokens.current())

    def set_danger(self, danger: bool) -> None:
        """Tint the icon red."""
        self._danger = danger
        self.refresh_theme(ThemeTokens.current())

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        if self.isChecked():
            color = tokens.primary
        elif self._danger:
            color = tokens.danger_text
        else:
            color = tokens.fg_muted
        self.setIcon(
            material_icon(
                self._icon_name,
                size=(48, 48),
                color=color,
                filled=self.isChecked(),
                convert_to_pixmap=False,
            )
        )
        hover = tokens.danger_tint if self._danger else tokens.hover
        radius = tokens.metrics["radiusSmall"]
        self.setStyleSheet(
            f"QToolButton {{ border: none; border-radius: {radius}px; background: transparent; }}"
            f"QToolButton:hover {{ background: {hover.name()}; }}"
            f"QToolButton:checked {{ background: {tokens.hover.name()}; }}"
            f"QToolButton:pressed {{ background: {tokens.pressed.name()}; }}"
            f"QToolButton:focus {{ border: 2px solid {tokens.primary.name()}; }}"
            f"QToolButton:disabled {{ background: transparent; }}"
        )


class TextButton(_ThemeFollower, QPushButton):
    """Labelled button, matching ``BecUi.TextButton``.

    Variants: ``primary``, ``danger``, ``success`` (solid), ``neutral`` (outlined),
    ``dangerOutline`` (red outline) and ``ghost`` (no border).

    Args:
        text(str): Label.
        variant(str): Colour variant.
        icon_name(str): Optional Material icon shown before the label.
        parent(QWidget | None): Parent widget.
        compact(bool): 28 px high with a 12 px label.
    """

    SOLID = ("primary", "danger", "success")

    def __init__(
        self,
        text: str,
        variant: str = "neutral",
        icon_name: str = "",
        parent: QWidget | None = None,
        compact: bool = False,
    ):
        super().__init__(text, parent)
        self._variant = variant
        self._icon_name = icon_name
        self._compact = compact
        self._busy = False
        self._busy_angle = 0.0
        self._busy_timer = QTimer(self)
        self._busy_timer.setInterval(40)
        self._busy_timer.timeout.connect(self._advance_busy)
        self.setMinimumHeight(28 if compact else 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_theme(ThemeTokens.current())
        self._follow_theme()

    def set_variant(self, variant: str) -> None:
        """Switch the colour variant."""
        self._variant = variant
        self.refresh_theme(ThemeTokens.current())

    def set_icon_name(self, icon_name: str) -> None:
        """Change the Material icon."""
        self._icon_name = icon_name
        self.refresh_theme(ThemeTokens.current())

    def set_busy(self, busy: bool) -> None:
        """Show a spinner instead of the icon, e.g. while a request is in flight."""
        self._busy = busy
        if busy and self.isVisible():
            self._busy_timer.start()
        elif not busy:
            self._busy_timer.stop()
        self.refresh_theme(ThemeTokens.current())

    def showEvent(self, event):  # pylint: disable=invalid-name
        super().showEvent(event)
        if self._busy:
            self._busy_timer.start()

    def hideEvent(self, event):  # pylint: disable=invalid-name
        super().hideEvent(event)
        self._busy_timer.stop()

    @property
    def busy(self) -> bool:
        """Whether the spinner is shown."""
        return self._busy

    def _label_color(self, tokens: ThemeTokens) -> QColor:
        if self._variant == "primary":
            return tokens.on_primary
        if self._variant in self.SOLID:
            return QColor("white")
        if self._variant == "dangerOutline":
            return tokens.danger_text
        return tokens.fg

    def _advance_busy(self) -> None:
        self._busy_angle = (self._busy_angle + 16) % 360
        size = 14
        self.setIcon(
            _spinner_pixmap(size, self._label_color(ThemeTokens.current()), self._busy_angle)
        )
        self.setIconSize(QSize(size, size))

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        radius = tokens.metrics["radiusSmall"]
        font_px = tokens.metrics["fontSmall" if self._compact else "fontBody"]
        pad = 9 if self._compact else 12
        label = self._label_color(tokens)
        base = {"primary": tokens.primary, "danger": tokens.danger, "success": tokens.success}.get(
            self._variant
        )
        if base is not None:
            qss = (
                f"QPushButton {{ background: {base.name()}; color: {label.name()}; border: none;"
                f" border-radius: {radius}px; padding: 0 {pad}px; font-size: {font_px}px;"
                f" font-weight: 600; }}"
                f"QPushButton:hover {{ background: {base.lighter(110).name()}; }}"
                f"QPushButton:pressed {{ background: {base.darker(125).name()}; }}"
                f"QPushButton:focus {{ border: 2px solid {tokens.primary.lighter(140).name()}; }}"
                f"QPushButton:disabled {{ background: {rgba(base, 0.45)};"
                f" color: {rgba(label, 0.7)}; }}"
            )
        else:
            if self._variant == "neutral":
                border = tokens.border.name()
            elif self._variant == "dangerOutline":
                border = rgba(tokens.danger, 0.6)
            else:
                border = "transparent"
            hover = tokens.danger_tint if self._variant == "dangerOutline" else tokens.hover
            qss = (
                f"QPushButton {{ background: transparent; color: {label.name()};"
                f" border: 1px solid {border}; border-radius: {radius}px; padding: 0 {pad}px;"
                f" font-size: {font_px}px; font-weight: 500; }}"
                f"QPushButton:hover {{ background: {hover.name()}; }}"
                f"QPushButton:pressed {{ background: {tokens.pressed.name()}; }}"
                f"QPushButton:focus {{ border: 2px solid {tokens.primary.name()}; }}"
                f"QPushButton:disabled {{ color: {tokens.fg_subtle.name()};"
                f" border-color: {tokens.track.name()}; }}"
            )
        self.setStyleSheet(qss)
        if self._busy:
            self._advance_busy()
        elif self._icon_name:
            self.setIcon(
                material_icon(self._icon_name, size=(32, 32), color=label, convert_to_pixmap=False)
            )
            self.setIconSize(QSize(15, 15) if self._compact else QSize(16, 16))
        else:
            self.setIcon(QPixmap())


# --------------------------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------------------------


class Spinner(_ThemeFollower, QWidget):
    """Small indeterminate spinner, matching ``BecUi.Spinner``."""

    def __init__(self, parent: QWidget | None = None, size: int = 16, color: QColor | None = None):
        super().__init__(parent)
        self._color = color
        self._angle = 0.0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._advance)
        self._running = True
        self._follow_theme()

    def showEvent(self, event):  # pylint: disable=invalid-name
        super().showEvent(event)
        if self._running:
            self._timer.start()

    def hideEvent(self, event):  # pylint: disable=invalid-name
        super().hideEvent(event)
        self._timer.stop()

    def _advance(self) -> None:
        self._angle = (self._angle + 12) % 360
        self.update()

    def set_running(self, running: bool) -> None:
        """Start or stop the animation; a stopped spinner hides itself."""
        self._running = running
        self.setVisible(running)
        if not running:
            self._timer.stop()

    def refresh_theme(self, _tokens: ThemeTokens) -> None:
        """Repaint with the new primary colour."""
        self.update()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        painter = QPainter(self)
        color = self._color or ThemeTokens.current().primary
        _paint_spinner(painter, QRectF(self.rect()), color, self._angle)
        painter.end()

    def cleanup(self) -> None:
        """Stop the animation timer."""
        self._timer.stop()


class StatusPill(_ThemeFollower, QWidget):
    """Rounded status chip with a coloured dot or icon, matching ``BecUi.StatusPill``.

    The tone is a name (``neutral``, ``info``, ``success``, ``warning``, ``danger``, ``subtle``
    or an alias such as ``ok``/``err``) or a colour.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        text: str = "",
        tone: QColor | str = "neutral",
        pulse: bool = False,
        icon_name: str = "",
        outlined: bool = False,
    ):
        super().__init__(parent)
        self._text = ""
        self._tone: QColor | str = "neutral"
        self._icon_name = ""
        self._outlined = outlined
        self._icon_pixmap = QPixmap()
        self._dot_opacity = 1.0
        self._pulse = QPropertyAnimation(self, b"dot_opacity", self)
        self._pulse.setDuration(1100)
        self._pulse.setKeyValueAt(0.0, 1.0)
        self._pulse.setKeyValueAt(0.5, 0.25)
        self._pulse.setKeyValueAt(1.0, 1.0)
        self._pulse.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._pulse.setLoopCount(-1)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFont(_px_font(self, 12, QFont.Weight.DemiBold))
        self.set_status(text, tone, pulse, icon_name)
        self._follow_theme()

    def set_status(
        self, text: str, tone: QColor | str, pulse: bool = False, icon_name: str = ""
    ) -> None:
        """Set label, tone, whether the dot pulses and an optional icon replacing the dot."""
        self._text = text
        self._tone = tone if isinstance(tone, str) else QColor(tone)
        self._icon_name = icon_name
        if pulse and self._pulse.state() != QPropertyAnimation.State.Running:
            self._pulse.start()
        elif not pulse:
            self._pulse.stop()
            self._dot_opacity = 1.0
        self.setToolTip(text)
        self.setAccessibleName(text)
        self.refresh_theme(ThemeTokens.current())

    def set_outlined(self, outlined: bool) -> None:
        """Quiet look: no fill, hairline border."""
        self._outlined = outlined
        self.update()

    @property
    def text(self) -> str:
        """Current label."""
        return self._text

    @property
    def pulsing(self) -> bool:
        """Whether the dot animation runs."""
        return self._pulse.state() == QPropertyAnimation.State.Running

    def _get_dot_opacity(self) -> float:
        return self._dot_opacity

    def _set_dot_opacity(self, value: float) -> None:
        self._dot_opacity = value
        self.update()

    dot_opacity = Property(float, _get_dot_opacity, _set_dot_opacity)

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Re-resolve a named tone and repaint."""
        color = _tone_color(tokens, self._tone)
        self._icon_pixmap = (
            material_icon(self._icon_name, size=(28, 28), color=color, convert_to_pixmap=True)
            if self._icon_name
            else QPixmap()
        )
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        extra = 30 if self._icon_name else 26
        return QSize(self.fontMetrics().horizontalAdvance(self._text) + extra, 22)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = ThemeTokens.current()
        tone = _tone_color(tokens, self._tone)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        if self._outlined:
            painter.setPen(QPen(tokens.separator, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        else:
            background = QColor(tone)
            background.setAlphaF(0.18 if tokens.dark else 0.13)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawRoundedRect(rect, radius, radius)
        if self._icon_name:
            painter.drawPixmap(
                QRectF(7, rect.height() / 2 - 7, 14, 14), self._icon_pixmap, QRectF()
            )
            text_left = 25
        else:
            dot = QColor(tone)
            dot.setAlphaF(self._dot_opacity)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(dot)
            painter.drawEllipse(QRectF(9, rect.height() / 2 - 3.5, 7, 7))
            text_left = 22
        painter.setPen(tone)
        painter.drawText(
            rect.adjusted(text_left, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, self._text
        )
        painter.end()

    def cleanup(self) -> None:
        """Stop the pulse animation."""
        self._pulse.stop()


class Badge(_ThemeFollower, QWidget):
    """Count bubble, matching ``BecUi.Badge``. Hidden at zero unless ``show_zero``."""

    def __init__(
        self,
        parent: QWidget | None = None,
        count: int = 0,
        tone: str = "danger",
        solid: bool | None = None,
        show_zero: bool = False,
        maximum: int = 99,
    ):
        super().__init__(parent)
        self._count = 0
        self._tone = tone
        self._solid = solid
        self._show_zero = show_zero
        self._maximum = maximum
        self.setFont(_px_font(self, 10, QFont.Weight.Bold))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set_count(count)
        self._follow_theme()

    @property
    def label(self) -> str:
        """Displayed text, e.g. ``99+``."""
        return f"{self._maximum}+" if self._count > self._maximum else str(self._count)

    def set_count(self, count: int) -> None:
        """Set the number shown."""
        self._count = int(count)
        self.setVisible(self._count > 0 or self._show_zero)
        self.setAccessibleName(self.label)
        self.updateGeometry()
        self.update()

    def set_tone(self, tone: str) -> None:
        """Set the tone name."""
        self._tone = tone
        self.update()

    def refresh_theme(self, _tokens: ThemeTokens) -> None:
        """Repaint with the new colours."""
        self.update()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        return QSize(max(16, self.fontMetrics().horizontalAdvance(self.label) + 9), 16)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = ThemeTokens.current()
        solid = self._solid if self._solid is not None else self._tone not in ("neutral", "primary")
        base = tokens.primary if self._tone == "primary" else tokens.tone(self._tone)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        fill = QColor(base)
        if not solid:
            fill.setAlphaF(0.22 if tokens.dark else 0.14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        if solid:
            luma = 0.299 * base.redF() + 0.587 * base.greenF() + 0.114 * base.blueF()
            text = QColor("#1a1a1a") if luma > 0.6 else QColor("white")
        else:
            text = tokens.tone_text(self._tone)
        painter.setPen(text)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.label)
        painter.end()


class LinearProgress(_ThemeFollower, QWidget):
    """Thin progress bar, matching ``BecUi.LinearProgress``.

    ``set_value`` takes 0..1 and animates; ``set_indeterminate`` shows a sliding segment.
    """

    def __init__(self, parent: QWidget | None = None, tone: str = "primary", thickness: int = 6):
        super().__init__(parent)
        self._tone = tone
        self._value = 0.0
        self._shown = 0.0
        self._indeterminate = False
        self._phase = 0.0
        self.setFixedHeight(thickness)
        self.setMinimumWidth(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(220)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._on_animated)
        self._runner = QVariantAnimation(self)
        self._runner.setStartValue(0.0)
        self._runner.setEndValue(1.0)
        self._runner.setDuration(1300)
        self._runner.setLoopCount(-1)
        self._runner.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._runner.valueChanged.connect(self._on_phase)
        self._follow_theme()

    @property
    def value(self) -> float:
        """Target value in 0..1."""
        return self._value

    def set_value(self, value: float, animate: bool = True) -> None:
        """Set the progress in 0..1."""
        self._value = max(0.0, min(1.0, float(value)))
        self._animation.stop()
        if animate and self.isVisible():
            self._animation.setStartValue(self._shown)
            self._animation.setEndValue(self._value)
            self._animation.start()
        else:
            self._shown = self._value
            self.update()

    def set_indeterminate(self, indeterminate: bool) -> None:
        """Switch between a determinate bar and a sliding busy segment."""
        self._indeterminate = indeterminate
        if indeterminate:
            self._runner.start()
        else:
            self._runner.stop()
        self.update()

    def set_tone(self, tone: str) -> None:
        """Fill tone: ``primary``, ``success``, ``warning``, ``danger`` ..."""
        self._tone = tone
        self.update()

    def _on_animated(self, value) -> None:
        self._shown = float(value)
        self.update()

    def _on_phase(self, value) -> None:
        self._phase = float(value)
        self.update()

    def refresh_theme(self, _tokens: ThemeTokens) -> None:
        """Repaint with the new colours."""
        self.update()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = ThemeTokens.current()
        color = tokens.primary if self._tone == "primary" else tokens.tone(self._tone)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(tokens.track)
        painter.drawRoundedRect(rect, radius, radius)
        painter.setBrush(color)
        if self._indeterminate:
            width = rect.width() * 0.3
            left = -width + (rect.width() + width) * self._phase
            painter.setClipRect(rect)
            painter.drawRoundedRect(QRectF(left, 0, width, rect.height()), radius, radius)
        elif self._shown > 0:
            width = max(rect.height(), rect.width() * self._shown)
            painter.drawRoundedRect(QRectF(0, 0, width, rect.height()), radius, radius)
        painter.end()

    def cleanup(self) -> None:
        """Stop the animations."""
        self._animation.stop()
        self._runner.stop()


# --------------------------------------------------------------------------------------------
# Surfaces and feedback
# --------------------------------------------------------------------------------------------


class Card(_ThemeFollower, QFrame):
    """Rounded surface with an optional title row, matching ``BecUi.Card``.

    Put content into :attr:`body`; add buttons to the title row with :meth:`add_header_widget`.

    Args:
        title(str): Title text.
        parent(QWidget | None): Parent widget.
        padding(int): Inner padding.
        title_style(str): ``"title"`` or ``"caption"`` (small uppercase, for form sections).
        collapsible(bool): Clicking the title row hides or shows the body.
        icon_name(str): Optional icon before the title.
        surface(str): ``"card"`` or ``"sunken"`` (a nested section inside a card).
    """

    expanded_changed = Signal(bool)

    def __init__(
        self,
        title: str = "",
        parent: QWidget | None = None,
        padding: int = 12,
        title_style: str = "title",
        collapsible: bool = False,
        icon_name: str = "",
        surface: str = "card",
    ):
        super().__init__(parent)
        self.setObjectName("uxCard")
        self._title_style = title_style
        self._collapsible = collapsible
        self._expanded = True
        self._icon_name = icon_name
        self._surface = surface
        outer = QVBoxLayout(self)
        outer.setContentsMargins(padding, padding, padding, padding)
        outer.setSpacing(10)
        self.header = QHBoxLayout()
        self.header.setSpacing(6)
        self.chevron = QLabel(self)
        self.chevron.setVisible(collapsible)
        self.icon_label = QLabel(self)
        self.icon_label.setVisible(bool(icon_name))
        self.title_label = QLabel("", self)
        self.subtitle_label = QLabel("", self)
        self.subtitle_label.setVisible(False)
        self.header.addWidget(self.chevron)
        self.header.addWidget(self.icon_label)
        self.header.addWidget(self.title_label)
        self.header.addWidget(self.subtitle_label, 1)
        self.header.addStretch(1)
        self.header_extras = QHBoxLayout()
        self.header_extras.setSpacing(4)
        self.header.addLayout(self.header_extras)
        outer.addLayout(self.header)
        self.body_widget = QWidget(self)
        self.body_widget.setObjectName("uxCardBody")
        self.body = QVBoxLayout(self.body_widget)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)
        outer.addWidget(self.body_widget, 1)
        self._has_extras = False
        self.set_title(title)
        self.refresh_theme(ThemeTokens.current())
        self._follow_theme()

    def set_title(self, title: str, subtitle: str = "") -> None:
        """Set the title and an optional muted subtitle."""
        self._title = title
        shown = title.upper() if self._title_style == "caption" else title
        self.title_label.setText(shown)
        self.subtitle_label.setText(subtitle)
        self.subtitle_label.setVisible(bool(subtitle))
        self._update_header_visibility()

    def add_header_widget(self, widget: QWidget) -> None:
        """Add a widget to the right end of the title row."""
        self.header_extras.addWidget(widget)
        self._has_extras = True
        self._update_header_visibility()

    @property
    def expanded(self) -> bool:
        """Whether the body is shown."""
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        """Show or hide the body of a collapsible card."""
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self.body_widget.setVisible(expanded)
        self._update_chevron(ThemeTokens.current())
        self.expanded_changed.emit(expanded)

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        if self._collapsible and event.position().y() <= self.body_widget.geometry().top():
            self.set_expanded(not self._expanded)
            event.accept()
            return
        super().mousePressEvent(event)

    def _update_header_visibility(self) -> None:
        has_title = bool(self.title_label.text())
        self.title_label.setVisible(has_title)
        visible = has_title or self._has_extras
        for index in range(self.header.count()):
            item = self.header.itemAt(index).widget()
            if item is not None and item not in (self.subtitle_label, self.chevron):
                if item is self.icon_label:
                    item.setVisible(visible and bool(self._icon_name))
                elif item is self.title_label:
                    item.setVisible(has_title)
        self.chevron.setVisible(self._collapsible and visible)

    def _update_chevron(self, tokens: ThemeTokens) -> None:
        if self._collapsible:
            name = "expand_more" if self._expanded else "chevron_right"
            self.chevron.setPixmap(
                material_icon(
                    name, size=(36, 36), color=tokens.fg_muted, convert_to_pixmap=True
                ).scaled(
                    18,
                    18,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        background = tokens.sunken if self._surface == "sunken" else tokens.card
        self.setStyleSheet(
            f"QFrame#uxCard {{ background: {background.name()};"
            f" border: 1px solid {tokens.border.name()};"
            f" border-radius: {tokens.metrics['radiusLarge']}px; }}"
            f"QWidget#uxCardBody {{ background: transparent; }}"
        )
        if self._title_style == "caption":
            self.title_label.setStyleSheet(
                f"color: {tokens.fg_muted.name()}; font-size: {tokens.metrics['fontCaption']}px;"
                f" font-weight: 700; letter-spacing: 0.8px; background: none;"
            )
        else:
            self.title_label.setStyleSheet(
                f"color: {tokens.fg.name()}; font-size: {tokens.metrics['fontBody']}px;"
                f" font-weight: 600; background: none;"
            )
        self.subtitle_label.setStyleSheet(
            f"color: {tokens.fg_subtle.name()}; font-size: {tokens.metrics['fontSmall']}px;"
            f" background: none;"
        )
        self.chevron.setStyleSheet("background: none;")
        self.icon_label.setStyleSheet("background: none;")
        if self._icon_name:
            self.icon_label.setPixmap(
                material_icon(
                    self._icon_name, size=(32, 32), color=tokens.fg_muted, convert_to_pixmap=True
                ).scaled(
                    16,
                    16,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self._update_chevron(tokens)


class Divider(_ThemeFollower, QFrame):
    """Hairline separator, matching ``BecUi.Divider``."""

    def __init__(self, parent: QWidget | None = None, vertical: bool = False):
        super().__init__(parent)
        if vertical:
            self.setFixedWidth(1)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        else:
            self.setFixedHeight(1)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.refresh_theme(ThemeTokens.current())
        self._follow_theme()

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        self.setStyleSheet(f"background: {tokens.separator.name()}; border: none;")


class Banner(_ThemeFollower, QFrame):
    """Inline message with a tone icon, title, text, action and close button.

    Matches ``BecUi.Banner``.

    Signals:
        action_triggered: The action button was clicked.
        closed: The close button was clicked; the banner hides itself.
    """

    action_triggered = Signal()
    closed = Signal()

    _ICONS = {"success": "check_circle", "warning": "warning", "danger": "error", "info": "info"}

    def __init__(
        self,
        tone: str = "info",
        title: str = "",
        text: str = "",
        parent: QWidget | None = None,
        action_text: str = "",
        closable: bool = False,
        icon_name: str = "",
    ):
        super().__init__(parent)
        self.setObjectName("uxBanner")
        self._tone = ThemeTokens.tone_name(tone)
        self._icon_name = icon_name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 8, 10)
        layout.setSpacing(10)
        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(18, 18)
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title_label = QLabel(title, self)
        self.title_label.setWordWrap(True)
        self.text_label = QLabel(text, self)
        self.text_label.setWordWrap(True)
        self.text_label.setTextFormat(Qt.TextFormat.PlainText)
        texts.addWidget(self.title_label)
        texts.addWidget(self.text_label)
        layout.addLayout(texts, 1)
        self.action_button = TextButton(action_text, "neutral", parent=self, compact=True)
        self.action_button.setVisible(bool(action_text))
        self.action_button.clicked.connect(self.action_triggered)
        layout.addWidget(self.action_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.close_button = IconButton("close", "Dismiss", self, size=16, compact=True)
        self.close_button.setVisible(closable)
        self.close_button.clicked.connect(self._on_close)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        self.set_message(title, text)
        self.setAccessibleName(f"{title} {text}".strip())
        self._follow_theme()

    def set_message(self, title: str, text: str, tone: str | None = None) -> None:
        """Update the content and optionally the tone."""
        if tone is not None:
            self._tone = ThemeTokens.tone_name(tone)
        self.title_label.setText(title)
        self.title_label.setVisible(bool(title))
        self.text_label.setText(text)
        self.text_label.setVisible(bool(text))
        self.refresh_theme(ThemeTokens.current())

    def _on_close(self) -> None:
        self.hide()
        self.closed.emit()

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        base = tokens.tone(self._tone)
        tint = tokens.tone_tint(self._tone)
        text = tokens.tone_text(self._tone)
        radius = tokens.metrics["radiusSmall"] + 2
        self.setStyleSheet(
            f"QFrame#uxBanner {{ background: {tint.name()}; border: 1px solid {rgba(base, 0.45)};"
            f" border-radius: {radius}px; }}"
        )
        has_title = bool(self.title_label.text())
        self.title_label.setStyleSheet(
            f"color: {tokens.fg.name()}; font-size: {tokens.metrics['fontBody']}px;"
            f" font-weight: 600; background: none; border: none;"
        )
        size = tokens.metrics["fontSmall" if has_title else "fontBody"]
        color = tokens.fg_muted if has_title else tokens.fg
        self.text_label.setStyleSheet(
            f"color: {color.name()}; font-size: {size}px; background: none; border: none;"
        )
        self.icon_label.setStyleSheet("background: none; border: none;")
        icon = self._icon_name or self._ICONS.get(self._tone, "info")
        self.icon_label.setPixmap(
            material_icon(
                icon, size=(36, 36), color=text, filled=True, convert_to_pixmap=True
            ).scaled(
                18,
                18,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.update()

    def paintEvent(self, event):  # pylint: disable=invalid-name
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ThemeTokens.current().tone(self._tone))
        painter.drawRoundedRect(QRectF(6, 6, 3, self.height() - 12), 1.5, 1.5)
        painter.end()


class EmptyState(_ThemeFollower, QWidget):
    """Placeholder for an empty list or view, matching ``BecUi.EmptyState``."""

    action_triggered = Signal()

    def __init__(
        self,
        icon_name: str = "inbox",
        title: str = "",
        text: str = "",
        parent: QWidget | None = None,
        action_text: str = "",
        action_icon: str = "",
        compact: bool = False,
    ):
        super().__init__(parent)
        self._icon_name = icon_name
        self._compact = compact
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4 if compact else 8)
        self.icon_label = QLabel(self)
        side = 36 if compact else 52
        self.icon_label.setFixedSize(side, side)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignHCenter)
        self.title_label = QLabel(title, self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setVisible(bool(title))
        layout.addSpacing(2 if compact else 4)
        layout.addWidget(self.title_label)
        self.text_label = QLabel(text, self)
        self.text_label.setWordWrap(True)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setVisible(bool(text))
        layout.addWidget(self.text_label)
        self.action_button = TextButton(action_text, "neutral", action_icon, self, compact=compact)
        self.action_button.setVisible(bool(action_text))
        self.action_button.clicked.connect(self.action_triggered)
        layout.addSpacing(6)
        layout.addWidget(self.action_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.refresh_theme(ThemeTokens.current())
        self._follow_theme()

    def set_content(self, title: str, text: str = "", icon_name: str | None = None) -> None:
        """Change title, text and optionally the icon."""
        if icon_name is not None:
            self._icon_name = icon_name
        self.title_label.setText(title)
        self.title_label.setVisible(bool(title))
        self.text_label.setText(text)
        self.text_label.setVisible(bool(text))
        self.refresh_theme(ThemeTokens.current())

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        side = self.icon_label.width()
        icon = 20 if self._compact else 28
        self.icon_label.setStyleSheet(
            f"background: {tokens.hover.name()}; border-radius: {side // 2}px;"
        )
        self.icon_label.setPixmap(
            material_icon(
                self._icon_name,
                size=(icon * 2, icon * 2),
                color=tokens.fg_subtle,
                convert_to_pixmap=True,
            ).scaled(
                icon,
                icon,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        title_px = tokens.metrics["fontBody" if self._compact else "fontTitle"]
        text_px = tokens.metrics["fontSmall" if self._compact else "fontBody"]
        self.title_label.setStyleSheet(
            f"color: {tokens.fg.name()}; font-size: {title_px}px; font-weight: 600;"
            f" background: none;"
        )
        self.text_label.setStyleSheet(
            f"color: {tokens.fg_muted.name()}; font-size: {text_px}px; background: none;"
        )


# --------------------------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------------------------


class ToggleSwitch(QPushButton):
    """Checkable switch painted like ``BecUi.SwitchField``; the label shows On or Off."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(32)
        self.setFixedWidth(84)
        self._knob = 0.0
        self._animation = QPropertyAnimation(self, b"knob", self)
        self._animation.setDuration(120)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _animate(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._knob)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def setChecked(self, checked: bool) -> None:  # pylint: disable=invalid-name
        """Set the state without animating."""
        self.blockSignals(True)
        super().setChecked(checked)
        self.blockSignals(False)
        self._animation.stop()
        self._knob = 1.0 if checked else 0.0
        self.update()

    def _get_knob(self) -> float:
        return self._knob

    def _set_knob(self, value: float) -> None:
        self._knob = value
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def refresh_theme(self, _tokens: ThemeTokens) -> None:
        """Repaint with the new colours."""
        self.update()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = ThemeTokens.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(0, (self.height() - 22) / 2, 38, 22)
        painter.setPen(tokens.primary if self.isChecked() else tokens.border)
        painter.setBrush(tokens.primary if self.isChecked() else tokens.track)
        painter.drawRoundedRect(track, 11, 11)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(tokens.on_primary if self.isChecked() else tokens.fg_muted)
        painter.drawEllipse(QRectF(track.left() + 3 + self._knob * 16, track.top() + 3, 16, 16))
        painter.setPen(tokens.fg)
        font = self.font()
        font.setPixelSize(13)
        painter.setFont(font)
        painter.drawText(
            QRectF(track.right() + 8, 0, self.width() - track.right() - 8, self.height()),
            Qt.AlignmentFlag.AlignVCenter,
            "On" if self.isChecked() else "Off",
        )
        painter.end()


class SuffixLineEdit(QLineEdit):
    """Line edit that paints a unit suffix inside its right edge, like ``BecUi.InputField``.

    Style it with :func:`field_qss`; ``set_icon_name`` adds a leading icon.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._suffix = ""
        self._icon_action = None

    def set_suffix(self, suffix: str) -> None:
        """Set the unit shown at the right edge."""
        self._suffix = suffix or ""
        width = self.fontMetrics().horizontalAdvance(self._suffix) + 10 if self._suffix else 0
        self.setTextMargins(0, 0, width, 0)
        self.update()

    def set_icon_name(self, icon_name: str) -> None:
        """Show a Material icon at the left edge."""
        if self._icon_action is not None:
            self.removeAction(self._icon_action)
            self._icon_action = None
        if icon_name:
            icon = material_icon(
                icon_name,
                size=(32, 32),
                color=ThemeTokens.current().fg_subtle,
                convert_to_pixmap=False,
            )
            self._icon_action = self.addAction(icon, QLineEdit.ActionPosition.LeadingPosition)

    def paintEvent(self, event):  # pylint: disable=invalid-name
        super().paintEvent(event)
        if not self._suffix:
            return
        painter = QPainter(self)
        painter.setPen(ThemeTokens.current().fg_subtle)
        font = self.font()
        font.setPixelSize(12)
        painter.setFont(font)
        painter.drawText(
            self.rect().adjusted(0, 0, -9, 0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            self._suffix,
        )
        painter.end()


class SearchField(_ThemeFollower, QLineEdit):
    """Search input with a magnifier, a clear button and a shortcut hint.

    Matches ``BecUi.SearchField``. Escape clears the text and emits :attr:`cleared`.
    """

    cleared = Signal()

    def __init__(
        self, parent: QWidget | None = None, placeholder: str = "Search", shortcut_hint: str = ""
    ):
        super().__init__(parent)
        self._hint = shortcut_hint
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.setAccessibleName(placeholder)
        self._search_action = None
        self.refresh_theme(ThemeTokens.current())
        self._follow_theme()

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        if event.matches(QKeySequence.StandardKey.Cancel) and self.text():
            self.clear()
            self.cleared.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        if self._search_action is not None:
            self.removeAction(self._search_action)
        icon = material_icon(
            "search", size=(32, 32), color=tokens.fg_subtle, convert_to_pixmap=False
        )
        self._search_action = self.addAction(icon, QLineEdit.ActionPosition.LeadingPosition)
        self.setStyleSheet(field_qss(tokens))

    def paintEvent(self, event):  # pylint: disable=invalid-name
        super().paintEvent(event)
        if not self._hint or self.text() or self.hasFocus():
            return
        tokens = ThemeTokens.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = _px_font(self, tokens.metrics["fontCaption"])
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(self._hint) + 10
        rect = QRectF(self.width() - width - 8, (self.height() - 18) / 2, width, 18)
        painter.setPen(QPen(tokens.border, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
        painter.setPen(tokens.fg_subtle)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._hint)
        painter.end()


class FormField(_ThemeFollower, QWidget):
    """Label above a control with a required mark, unit, helper and error line.

    Matches ``BecUi.FormField``. :meth:`set_error` replaces the helper with a red message and
    marks the control invalid (see :func:`set_invalid`).
    """

    def __init__(
        self,
        label: str,
        control: QWidget,
        parent: QWidget | None = None,
        required: bool = False,
        helper: str = "",
        unit: str = "",
    ):
        super().__init__(parent)
        self.control = control
        self._helper = helper
        self._error = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        text = label.replace("{", "{{").replace("}", "}}")
        if required:
            text += " <span style='color:{danger}'>*</span>"
        if unit:
            text += f" <span style='color:{{subtle}}'>({unit})</span>"
        self._label_template = text
        self.label = QLabel(self)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setVisible(bool(label))
        layout.addWidget(self.label)
        layout.addWidget(control)
        self.message_row = QWidget(self)
        message = QHBoxLayout(self.message_row)
        message.setContentsMargins(0, 0, 0, 0)
        message.setSpacing(4)
        self.error_icon = QLabel(self.message_row)
        self.error_icon.setFixedSize(13, 13)
        self.message = QLabel(self.message_row)
        self.message.setWordWrap(True)
        message.addWidget(self.error_icon, 0, Qt.AlignmentFlag.AlignTop)
        message.addWidget(self.message, 1)
        layout.addWidget(self.message_row)
        self.refresh_theme(ThemeTokens.current())
        self._follow_theme()

    def set_error(self, error: str) -> None:
        """Show an error under the control, or clear it with an empty string."""
        self._error = error or ""
        set_invalid(self.control, bool(self._error))
        self.refresh_theme(ThemeTokens.current())

    def set_helper(self, helper: str) -> None:
        """Set the helper line shown when there is no error."""
        self._helper = helper
        self.refresh_theme(ThemeTokens.current())

    @property
    def error(self) -> str:
        """Current error message."""
        return self._error

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        small = tokens.metrics["fontSmall"]
        self.label.setText(
            self._label_template.format(
                danger=tokens.danger_text.name(), subtle=tokens.fg_subtle.name()
            )
        )
        self.label.setStyleSheet(
            f"color: {tokens.fg_muted.name()}; font-size: {small}px; font-weight: 500;"
            f" background: none;"
        )
        shown = self._error or self._helper
        self.message_row.setVisible(bool(shown))
        self.message.setText(shown)
        color = tokens.danger_text if self._error else tokens.fg_subtle
        self.message.setStyleSheet(
            f"color: {color.name()}; font-size: {small}px; background: none;"
        )
        self.error_icon.setVisible(bool(self._error))
        if self._error:
            self.error_icon.setPixmap(
                material_icon(
                    "error",
                    size=(26, 26),
                    color=tokens.danger_text,
                    filled=True,
                    convert_to_pixmap=True,
                ).scaled(
                    13,
                    13,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )


class SegmentedControl(_ThemeFollower, QFrame):
    """Row of mutually exclusive options, matching ``BecUi.SegmentedControl``.

    Items are strings or ``{"text": ..., "icon_name": ..., "count": ...}`` dictionaries.
    :attr:`activated` fires on user clicks; :meth:`set_current_index` changes the state silently.
    """

    activated = Signal(int)

    def __init__(
        self, items: Sequence[str | dict] = (), parent: QWidget | None = None, compact: bool = False
    ):
        super().__init__(parent)
        self.setObjectName("uxSegmented")
        self._compact = compact
        self._current = 0
        self._buttons: list[QPushButton] = []
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(3, 3, 3, 3)
        self._layout.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set_items(items)
        self._follow_theme()

    def set_items(self, items: Sequence[str | dict]) -> None:
        """Replace the options."""
        for button in self._buttons:
            button.deleteLater()
        self._buttons = []
        self._items = [item if isinstance(item, dict) else {"text": item} for item in items]
        for index, item in enumerate(self._items):
            button = QPushButton(self)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAccessibleName(item.get("text", ""))
            button.clicked.connect(lambda _=False, i=index: self._on_clicked(i))
            self._layout.addWidget(button)
            self._buttons.append(button)
        self._current = min(self._current, max(0, len(self._buttons) - 1))
        self.refresh_theme(ThemeTokens.current())

    def set_count(self, index: int, count: int) -> None:
        """Update the count shown next to an option."""
        self._items[index]["count"] = count
        self.refresh_theme(ThemeTokens.current())

    @property
    def current_index(self) -> int:
        """Index of the selected option."""
        return self._current

    def set_current_index(self, index: int) -> None:
        """Select an option without emitting :attr:`activated`."""
        self._current = index
        for i, button in enumerate(self._buttons):
            button.setChecked(i == index)

    def _on_clicked(self, index: int) -> None:
        self.set_current_index(index)
        self.activated.emit(index)

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        height = tokens.metrics["controlHeightCompact" if self._compact else "controlHeight"]
        font_px = tokens.metrics["fontSmall" if self._compact else "fontBody"]
        radius = tokens.metrics["radiusSmall"]
        self.setFixedHeight(height)
        self.setStyleSheet(
            f"QFrame#uxSegmented {{ background: {tokens.sunken.name()};"
            f" border: 1px solid {tokens.border.name()}; border-radius: {radius + 1}px; }}"
            f"QFrame#uxSegmented QPushButton {{ background: transparent; border: 1px solid"
            f" transparent; border-radius: {radius - 1}px; color: {tokens.fg_muted.name()};"
            f" font-size: {font_px}px; font-weight: 500;"
            f" padding: 0 {8 if self._compact else 11}px; min-height: {height - 8}px; }}"
            f"QFrame#uxSegmented QPushButton:hover {{ color: {tokens.fg.name()}; }}"
            f"QFrame#uxSegmented QPushButton:checked {{ background: {tokens.card.name()};"
            f" border-color: {tokens.border.name()}; color: {tokens.fg.name()};"
            f" font-weight: 600; }}"
        )
        for index, (button, item) in enumerate(zip(self._buttons, self._items)):
            text = item.get("text", "")
            count = item.get("count")
            button.setText(f"{text}  {count}" if count is not None else text)
            if item.get("icon_name"):
                button.setIcon(
                    material_icon(
                        item["icon_name"],
                        size=(30, 30),
                        color=tokens.fg_muted,
                        convert_to_pixmap=False,
                    )
                )
            button.setChecked(index == self._current)


class PortedPropertiesMixin:
    """Make a port export and load the ``SafeProperty`` settings of the class it ports.

    ``BECConnector`` only collects the properties defined directly on ``type(self)``, so a
    subclass would silently drop the inherited ones (e.g. ``ring_json``) from saved profiles.
    Set ``PORTED_FROM`` to the original class; its properties and those of every class in
    between are collected.
    """

    PORTED_FROM: type | None = None

    def _get_bec_meta_objects(self) -> dict:
        objects = {}
        for cls in type(self).__mro__:
            for name, attr in vars(cls).items():
                if name in objects or not isinstance(attr, Property):
                    continue
                if getattr(attr.fget, "__is_safe_getter__", False):
                    objects[name] = attr
            if cls is self.PORTED_FROM:
                break
        return objects
