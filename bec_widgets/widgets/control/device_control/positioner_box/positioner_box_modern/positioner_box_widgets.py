"""Positioner box with the modernized UX, built from QWidgets."""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QEvent, QPointF, QRectF, Qt, QVariantAnimation
from qtpy.QtGui import QColor, QDoubleValidator, QFont, QIcon, QPainter, QPalette, QPen
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import get_accent_colors, rgba
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_modern.positioner_box_modern_base import (
    MOVING_ACTIVE,
    MOVING_UNKNOWN,
    ModernPositionerBoxBase,
)


def _colors() -> dict[str, QColor]:
    palette = QApplication.palette()
    accents = get_accent_colors()
    return {
        "window": palette.color(QPalette.ColorRole.Window),
        "base": palette.color(QPalette.ColorRole.Base),
        "button": palette.color(QPalette.ColorRole.Button),
        "border": palette.color(QPalette.ColorRole.Mid),
        "text": palette.color(QPalette.ColorRole.WindowText),
        "muted": palette.color(QPalette.ColorRole.PlaceholderText),
        "accent": palette.color(QPalette.ColorRole.Highlight),
        "onAccent": palette.color(QPalette.ColorRole.HighlightedText),
        "success": accents.success,
        "warning": accents.warning,
        "danger": accents.emergency,
    }


class StatusPill(QWidget):
    """Rounded "Moving" / "Idle" chip with a pulsing dot while moving."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._moving = False
        self._dot_alpha = 1.0
        self._colors = _colors()
        self._pulse = QVariantAnimation(self, startValue=1.0, endValue=0.25, duration=500)
        self._pulse.setLoopCount(-1)
        self._pulse.setKeyValueAt(0.5, 0.25)
        self._pulse.setEndValue(1.0)
        self._pulse.valueChanged.connect(self._on_pulse)
        font = self.font()
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)
        self.setFixedHeight(22)

    def set_colors(self, colors: dict[str, QColor]):
        self._colors = colors
        self.update()

    def set_moving(self, moving: bool):
        if moving == self._moving:
            return
        self._moving = moving
        if moving:
            self._pulse.start()
        else:
            self._pulse.stop()
            self._dot_alpha = 1.0
        self.setFixedWidth(self.sizeHint().width())
        self.update()

    def _on_pulse(self, value):
        self._dot_alpha = float(value)
        self.update()

    def _text(self) -> str:
        return "Moving" if self._moving else "Idle"

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(self.fontMetrics().horizontalAdvance(self._text()) + 30)
        return hint

    def paintEvent(self, _event):
        tone = QColor(self._colors["warning" if self._moving else "success"])
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(tone)
        bg.setAlphaF(0.16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(QRectF(self.rect()), 11, 11)
        dot = QColor(tone)
        dot.setAlphaF(self._dot_alpha)
        painter.setBrush(dot)
        painter.drawEllipse(QPointF(12, self.height() / 2), 4, 4)
        painter.setPen(self._colors["text"])
        painter.drawText(
            self.rect().adjusted(22, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, self._text()
        )


class LimitBar(QWidget):
    """Track between the limits with a readback dot and a hollow target ring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._position = -1.0
        self._target = -1.0
        self._low = ""
        self._high = ""
        self._out = False
        self._colors = _colors()
        self._anim = QVariantAnimation(self, duration=120)
        self._anim.valueChanged.connect(self._on_anim)
        self.setFixedHeight(30)
        font = self.font()
        font.setPixelSize(11)
        self.setFont(font)

    def set_colors(self, colors: dict[str, QColor]):
        self._colors = colors
        self.update()

    def set_state(self, position: float, target: float, low: str, high: str, out: bool):
        self._target, self._low, self._high, self._out = target, low, high, out
        if position >= 0 and self._position >= 0 and position != self._position:
            self._anim.stop()
            self._anim.setStartValue(self._position)
            self._anim.setEndValue(position)
            self._anim.start()
        else:
            self._position = position
        self.update()

    def _on_anim(self, value):
        self._position = float(value)
        self.update()

    def paintEvent(self, _event):
        colors = self._colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        mid_y = 7
        track = QColor(colors["border"])
        track.setAlphaF(0.6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, mid_y - 3, width, 6), 3, 3)
        tone = QColor(colors["danger" if self._out else "accent"])
        if self._position >= 0:
            fill = QColor(tone)
            fill.setAlphaF(0.55)
            painter.setBrush(fill)
            painter.drawRoundedRect(QRectF(0, mid_y - 3, width * self._position, 6), 3, 3)
        if self._target >= 0:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(colors["accent"], 2))
            painter.drawEllipse(QPointF(width * self._target, mid_y), 5, 5)
        if self._position >= 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tone)
            painter.drawEllipse(QPointF(width * self._position, mid_y), 6, 6)
        painter.setPen(colors["muted"])
        text_rect = self.rect().adjusted(0, 14, 0, 0)
        painter.drawText(
            text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, self._low
        )
        painter.drawText(
            text_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, self._high
        )


class PositionerBoxWidgets(ModernPositionerBoxBase):
    """Positioner box with the modernized UX, built from QWidgets."""

    def init_view(self):
        self._colors = _colors()
        self._icons: dict[tuple[str, str, int], QIcon] = {}
        root = QWidget(self)
        root.setObjectName("positioner_root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header: device picker and motion status
        header = QHBoxLayout()
        self.device_button = QToolButton(root)
        self.device_button.setObjectName("device_button")
        self.device_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.device_button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.device_button.setToolTip("Change positioner")
        self.device_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.device_button.clicked.connect(self._on_device_button)
        self.status_pill = StatusPill(root)
        header.addWidget(self.device_button)
        header.addStretch()
        header.addWidget(self.status_pill)
        layout.addLayout(header)

        # Readback and target
        readback_row = QHBoxLayout()
        readback_row.setSpacing(6)
        self.readback = QLabel(root)
        self.readback.setObjectName("readback")
        self.units = QLabel(root)
        self.units.setObjectName("units")
        readback_row.addWidget(self.readback)
        readback_row.addWidget(self.units, 0, Qt.AlignmentFlag.AlignBaseline)
        readback_row.addStretch()
        layout.addLayout(readback_row)
        self.target = QLabel(root)
        self.target.setObjectName("target")
        self.target.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.target)

        # Limit track
        self.limit_bar = LimitBar(root)
        self.no_limits = QLabel("No limits set", root)
        self.no_limits.setObjectName("hint")
        layout.addWidget(self.limit_bar)
        layout.addWidget(self.no_limits)

        # Move to
        move_row = QHBoxLayout()
        move_row.setSpacing(6)
        self.setpoint = QLineEdit(root)
        self.setpoint.setPlaceholderText("Move to…")
        self.setpoint.textChanged.connect(self._on_target_text)
        self.setpoint.returnPressed.connect(self.on_go)
        self.setpoint.installEventFilter(self)
        self.go = QPushButton("Go", root)
        self.go.setObjectName("go")
        self.go.setFixedWidth(52)
        self.go.clicked.connect(self.on_go)
        move_row.addWidget(self.setpoint, 1)
        move_row.addWidget(self.go)
        layout.addLayout(move_row)
        self.move_error = QLabel(root)
        self.move_error.setObjectName("error")
        self.move_error.setVisible(False)
        layout.addWidget(self.move_error)

        # Tweak
        tweak_row = QHBoxLayout()
        tweak_row.setSpacing(6)
        self.tweak_left = QPushButton(root)
        self.tweak_left.clicked.connect(lambda: self.tweak(-1))
        self.step = QLineEdit(root)
        self.step.setObjectName("step")
        self.step.setFixedWidth(72)
        self.step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step.setValidator(QDoubleValidator(0, float("inf"), 12, self.step))
        self.step.setToolTip("Step size. Scroll or ↑/↓ to change by ×10")
        self.step.editingFinished.connect(lambda: self.set_step_text(self.step.text()))
        self.step.installEventFilter(self)
        self.tweak_right = QPushButton(root)
        self.tweak_right.clicked.connect(lambda: self.tweak(1))
        tweak_row.addWidget(self.tweak_left, 1)
        tweak_row.addWidget(self.step)
        tweak_row.addWidget(self.tweak_right, 1)
        layout.addLayout(tweak_row)

        layout.addStretch()
        self.stop = QPushButton("Stop", root)
        self.stop.setObjectName("stop")
        self.stop.setMinimumHeight(34)
        self.stop.clicked.connect(self.on_stop)
        layout.addWidget(self.stop)

        root.setMinimumSize(240, 250)
        self.main_layout.addWidget(root)
        self._root = root
        self.state.changed.connect(self._refresh)
        self.apply_theme("")

    def eventFilter(self, obj, event):
        if obj is self.step:
            if event.type() == QEvent.Type.Wheel:
                self.scale_step(10 if event.angleDelta().y() > 0 else 0.1)
                return True
            if event.type() == QEvent.Type.KeyPress and event.key() in (
                Qt.Key.Key_Up,
                Qt.Key.Key_Down,
            ):
                self.scale_step(10 if event.key() == Qt.Key.Key_Up else 0.1)
                return True
        if obj is self.setpoint and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.setpoint.clear()
                self.setpoint.clearFocus()
                return True
        return super().eventFilter(obj, event)

    @SafeSlot()
    def _on_device_button(self):
        self.open_device_picker(
            self.device_button.mapToGlobal(self.device_button.rect().bottomLeft())
        )

    @staticmethod
    def _set_style_flag(widget: QWidget, name: str, value: bool):
        """Set a QSS dynamic property and re-polish only when it changes."""
        if widget.property(name) == value:
            return
        widget.setProperty(name, value)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _icon(self, name: str, color: QColor | str, size: int) -> QIcon:
        key = (name, QColor(color).name(), size)
        if key not in self._icons:
            self._icons[key] = QIcon(
                material_icon(name, size=(size, size), color=key[1], filled=True)
            )
        return self._icons[key]

    @SafeSlot(str)
    def _on_target_text(self, text: str):
        error = self.validate_target(text)
        self.move_error.setText(error)
        self.move_error.setVisible(bool(error))
        self._set_style_flag(self.setpoint, "invalid", bool(error))
        self.go.setEnabled(bool(text.strip()) and not error)

    @SafeSlot()
    def on_go(self):
        """Send the typed target."""
        if self.move_to_text(self.setpoint.text()):
            self.setpoint.clear()
            self.setpoint.clearFocus()

    @SafeSlot()
    def _refresh(self):
        moving = self._moving == MOVING_ACTIVE
        self._root.setEnabled(self.ready)
        self.device_button.setText(self._device or "No device")
        self.device_button.setEnabled(self.device_selectable)
        self.device_button.setIcon(
            self._icon("expand_more", self._colors["muted"], 18)
            if self.device_selectable
            else QIcon()
        )
        self.status_pill.setVisible(self._moving != MOVING_UNKNOWN)
        self.status_pill.set_moving(moving)
        self.readback.setText(self.readback_text)
        self._set_style_flag(self.readback, "out", self.out_of_limits)
        self.units.setText(self._units)
        self.units.setVisible(bool(self._units))
        self.target.setText(f"→ target {self.target_text}" if self.has_target else "at target")
        self._set_style_flag(self.target, "active", self.has_target)
        self.limit_bar.setVisible(self.has_limits)
        self.no_limits.setVisible(not self.has_limits and self.ready)
        self.limit_bar.set_state(
            self.position_fraction,
            self.target_fraction,
            self.low_text,
            self.high_text,
            self.out_of_limits,
        )
        step = self.step_text
        self.tweak_left.setText(f"− {step}")
        self.tweak_right.setText(f"+ {step}")
        self.tweak_left.setToolTip(f"Move by −{step} {self._units}")
        self.tweak_right.setToolTip(f"Move by +{step} {self._units}")
        if not self.step.hasFocus():
            self.step.setText(step)
        self._set_style_flag(self.stop, "moving", moving)
        self.stop.setIcon(self._icon("stop", "#ffffff" if moving else self._colors["danger"], 16))
        self._on_target_text(self.setpoint.text())

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        c = self._colors = _colors()
        self.status_pill.set_colors(c)
        self.limit_bar.set_colors(c)
        name = lambda key: c[key].name()  # pylint: disable=unnecessary-lambda-assignment
        self._root.setStyleSheet(f"""
            #positioner_root {{ background: {name('window')}; }}
            #device_button {{ border: none; border-radius: 6px; padding: 3px 6px;
                font-size: 15px; font-weight: 600; color: {name('text')};
                background: transparent; }}
            #device_button:hover {{ background: {rgba(c['accent'], 38)}; }}
            #readback {{ font-family: monospace; font-size: 26px; font-weight: 500;
                color: {name('text')}; }}
            #readback[out="true"] {{ color: {name('danger')}; }}
            #units {{ font-size: 14px; color: {name('muted')}; }}
            #target, #hint {{ font-size: 12px; color: {name('muted')}; }}
            #hint {{ font-size: 11px; }}
            #target[active="true"] {{ color: {name('accent')}; }}
            #error {{ font-size: 11px; color: {name('danger')}; }}
            QLineEdit {{ min-height: 26px; border-radius: 6px; padding: 0 6px; font-size: 13px;
                background: {name('base')}; color: {name('text')};
                border: 1px solid {name('border')}; }}
            QLineEdit:focus {{ border: 2px solid {name('accent')}; }}
            QLineEdit[invalid="true"] {{ border: 2px solid {name('danger')}; }}
            QPushButton {{ min-height: 28px; border-radius: 6px; font-size: 13px;
                color: {name('text')}; background: {rgba(c['button'], 255)};
                border: 1px solid {rgba(c['border'], 160)}; padding: 0 8px; }}
            QPushButton:hover {{ background: {rgba(c['accent'], 40)}; }}
            QPushButton:pressed {{ background: {rgba(c['accent'], 80)}; }}
            #go {{ background: {name('accent')}; color: {name('onAccent')}; border: none; }}
            #go:disabled {{ background: {rgba(c['accent'], 40)}; color: {name('muted')}; }}
            #stop {{ min-height: 32px; font-weight: 600; color: {name('danger')};
                background: {rgba(c['danger'], 30)}; border: 1px solid {rgba(c['danger'], 128)}; }}
            #stop:hover {{ background: {rgba(c['danger'], 56)}; }}
            #stop[moving="true"] {{ background: {name('danger')}; color: white; border: none; }}
            """)
        self._refresh()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = PositionerBoxWidgets(device="samx")
    widget.show()
    sys.exit(app.exec())
