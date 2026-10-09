"""Positioner box with the modernised UX in plain QWidgets, same API as :class:`PositionerBox`.

This is the QWidget twin of :class:`PositionerBoxQML`, built from the same state so both
rendering stacks can be compared side by side.
"""

from __future__ import annotations

from qtpy.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from qtpy.QtGui import QColor, QDoubleValidator, QFont, QPainter
from qtpy.QtWidgets import (
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import (
    Card,
    StatusPill,
    TextButton,
    field_qss,
    refresh_kit_theme,
    set_invalid,
)
from bec_widgets.widgets.control.device_control.positioner_box.positioner_ux_common import (
    PositionerBoxPortBase,
)


class LimitBar(QWidget):
    """Horizontal limit track with the current position and the target marker."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(14)
        self._position = -1.0
        self._shown_position = -1.0
        self._target = -1.0
        self._show_target = False
        self._at_limit = False
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._on_step)

    def set_values(self, position: float, target: float, show_target: bool, at_limit: bool):
        """Update the markers; the position marker glides to its new place."""
        self._target = target
        self._show_target = show_target
        self._at_limit = at_limit
        if position != self._position:
            start = self._shown_position if self._shown_position >= 0 else position
            self._position = position
            self._animation.stop()
            if position >= 0 and start >= 0:
                self._animation.setStartValue(float(start))
                self._animation.setEndValue(float(position))
                self._animation.start()
            else:
                self._shown_position = position
        self.update()

    def _on_step(self, value: float) -> None:
        self._shown_position = float(value)
        self.update()

    def stop_animation(self) -> None:
        """Stop the marker animation."""
        self._animation.stop()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        tokens = ThemeTokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        mid = self.height() / 2
        painter.setBrush(tokens.track)
        painter.drawRoundedRect(QRectF(0, mid - 2, self.width(), 4), 2, 2)
        if self._show_target and self._target >= 0:
            painter.setBrush(tokens.fg_muted)
            painter.drawRect(QRectF(self._target * (self.width() - 2), 0, 2, self.height()))
        if self._shown_position >= 0:
            x = self._shown_position * (self.width() - 12)
            painter.setBrush(tokens.card)
            painter.drawEllipse(QRectF(x - 1, mid - 7, 14, 14))
            painter.setBrush(tokens.warning if self._at_limit else tokens.primary)
            painter.drawEllipse(QRectF(x + 1, mid - 5, 10, 10))
        painter.end()


class PositionerBoxQWidget(PositionerBoxPortBase):
    """Positioner box with the modernised UX in plain QWidgets."""

    def _init_view(self) -> None:
        self.setMinimumSize(260, 250)
        self.card = Card(parent=self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.addWidget(self.card)
        body = self.card.body
        body.setSpacing(10)

        # header
        header = QHBoxLayout()
        header.setSpacing(8)
        self.selector = QComboBox(self.card)
        self.selector.setEditable(True)
        self.selector.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.selector.setAccessibleName("Positioner")
        self.selector.lineEdit().setPlaceholderText("Select positioner")
        completer = QCompleter(self.selector.model(), self.selector)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.selector.setCompleter(completer)
        self.selector.activated.connect(
            lambda index: self.set_positioner(self.selector.itemText(index))
        )
        self.selector.lineEdit().returnPressed.connect(
            lambda: self.set_positioner(self.selector.currentText())
        )
        self.device_label = QLabel(self.card)
        self.status_pill = StatusPill(self.card)
        header.addWidget(self.selector, 1)
        header.addWidget(self.device_label, 1)
        header.addWidget(self.status_pill)
        body.addLayout(header)

        # readback
        self.readback_block = QWidget(self.card)
        readback_layout = QVBoxLayout(self.readback_block)
        readback_layout.setContentsMargins(0, 0, 0, 0)
        readback_layout.setSpacing(0)
        value_row = QHBoxLayout()
        value_row.setSpacing(6)
        self.readback_label = QLabel(self.readback_block)
        self.readback_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.units_label = QLabel(self.readback_block)
        value_row.addWidget(self.readback_label)
        value_row.addWidget(self.units_label, 0, Qt.AlignmentFlag.AlignBaseline)
        value_row.addStretch(1)
        readback_layout.addLayout(value_row)
        self.target_label = QLabel(self.readback_block)
        readback_layout.addWidget(self.target_label)
        body.addWidget(self.readback_block)

        # limits
        self.limits_block = QWidget(self.card)
        limits_layout = QVBoxLayout(self.limits_block)
        limits_layout.setContentsMargins(0, 0, 0, 0)
        limits_layout.setSpacing(3)
        self.limit_bar = LimitBar(self.limits_block)
        limits_layout.addWidget(self.limit_bar)
        limit_labels = QHBoxLayout()
        self.limit_low = QLabel(self.limits_block)
        self.limit_high = QLabel(self.limits_block)
        limit_labels.addWidget(self.limit_low)
        limit_labels.addStretch(1)
        limit_labels.addWidget(self.limit_high)
        limits_layout.addLayout(limit_labels)
        body.addWidget(self.limits_block)

        # absolute move
        self.move_block = QWidget(self.card)
        move_layout = QVBoxLayout(self.move_block)
        move_layout.setContentsMargins(0, 0, 0, 0)
        move_layout.setSpacing(4)
        move_row = QHBoxLayout()
        move_row.setSpacing(6)
        self.target_input = QLineEdit(self.move_block)
        self.target_input.setPlaceholderText("Move to…")
        self.target_input.setAccessibleName("Target position")
        self.target_input.textChanged.connect(self._on_target_edited)
        self.target_input.returnPressed.connect(self._submit_target)
        self.go_button = TextButton("Go", "primary", parent=self.move_block)
        self.go_button.clicked.connect(self._submit_target)
        move_row.addWidget(self.target_input, 1)
        move_row.addWidget(self.go_button)
        move_layout.addLayout(move_row)
        self.error_label = QLabel(self.move_block)
        self.error_label.setVisible(False)
        move_layout.addWidget(self.error_label)
        body.addWidget(self.move_block)

        # tweak
        self.tweak_block = QWidget(self.card)
        tweak_row = QHBoxLayout(self.tweak_block)
        tweak_row.setContentsMargins(0, 0, 0, 0)
        tweak_row.setSpacing(6)
        self.tweak_left = TextButton("", "neutral", "chevron_left", self.tweak_block)
        self.tweak_left.setToolTip("Tweak down by the step")
        self.tweak_left.clicked.connect(self.on_tweak_left)
        self.step_input = QLineEdit(self.tweak_block)
        self.step_input.setFixedWidth(78)
        self.step_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_input.setToolTip("Step size")
        self.step_input.setAccessibleName("Step size")
        step_validator = QDoubleValidator(0.0, float("inf"), 12, self.step_input)
        step_validator.setNotation(QDoubleValidator.Notation.ScientificNotation)
        self.step_input.setValidator(step_validator)
        self.step_input.editingFinished.connect(self._on_step_edited)
        self.tweak_right = TextButton("", "neutral", "chevron_right", self.tweak_block)
        self.tweak_right.setToolTip("Tweak up by the step")
        self.tweak_right.clicked.connect(self.on_tweak_right)
        for button in (self.tweak_left, self.tweak_right):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        tweak_row.addWidget(self.tweak_left, 1)
        tweak_row.addWidget(self.step_input)
        tweak_row.addWidget(self.tweak_right, 1)
        body.addWidget(self.tweak_block)

        self.stop_button = TextButton("Stop", "danger", "stop", self.card)
        self.stop_button.clicked.connect(self.on_stop)
        body.addWidget(self.stop_button)

        self.empty_label = QLabel(
            "Choose a positioner above to see its position and move it.", self.card
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(self.empty_label)
        body.addStretch(1)

        self._apply_styles(ThemeTokens())

    # ---- rendering -----------------------------------------------------------------------

    def _apply_styles(self, tokens: ThemeTokens) -> None:
        self.card.setStyleSheet(self.card.styleSheet() + field_qss(tokens))
        font = QFont("monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPixelSize(26)
        font.setWeight(QFont.Weight.DemiBold)
        self.readback_label.setFont(font)
        plain = "background: none; border: none;"
        self.readback_label.setStyleSheet(f"color: {tokens.fg.name()}; {plain}")
        self.units_label.setStyleSheet(f"color: {tokens.fg_muted.name()}; font-size: 14px; {plain}")
        self.target_label.setStyleSheet(
            f"color: {tokens.fg_muted.name()}; font-size: 12px; font-family: monospace; {plain}"
        )
        for label in (self.limit_low, self.limit_high):
            label.setStyleSheet(f"color: {tokens.fg_subtle.name()}; font-size: 11px; {plain}")
        self.error_label.setStyleSheet(f"color: {tokens.danger.name()}; font-size: 11px; {plain}")
        self.device_label.setStyleSheet(
            f"color: {tokens.fg.name()}; font-size: 14px; font-weight: 600; {plain}"
        )
        self.empty_label.setStyleSheet(f"color: {tokens.fg_muted.name()}; font-size: 12px; {plain}")
        for block in (self.readback_block, self.limits_block, self.move_block, self.tweak_block):
            block.setStyleSheet("background: none;")

    def _tone(self, tone: str, tokens: ThemeTokens) -> QColor:
        return {
            "primary": tokens.primary,
            "success": tokens.success,
            "warning": tokens.warning,
            "danger": tokens.danger,
        }.get(tone, tokens.fg_muted)

    def _sync_view(self) -> None:
        state = self.view_state()
        tokens = ThemeTokens()
        has_device = state["hasDevice"]

        self.selector.setVisible(state["selectable"])
        self.device_label.setVisible(not state["selectable"])
        self.device_label.setText(state["device"] or "No positioner")
        if not self.selector.lineEdit().hasFocus():
            names = self.positioner_names()
            if [self.selector.itemText(i) for i in range(self.selector.count())] != names:
                self.selector.blockSignals(True)
                self.selector.clear()
                self.selector.addItems(names)
                self.selector.blockSignals(False)
            self.selector.setCurrentText(state["device"])
        self.status_pill.set_status(
            state["status"], self._tone(state["statusTone"], tokens), state["moving"]
        )

        for block in (self.readback_block, self.move_block, self.tweak_block, self.stop_button):
            block.setVisible(has_device)
        self.empty_label.setVisible(not has_device)
        self.readback_label.setText(state["readbackText"])
        self.units_label.setText(state["units"])
        self.units_label.setVisible(bool(state["units"]))
        self.target_label.setText(f"target {state['setpointText']}")
        self.target_label.setVisible(state["showTarget"])

        self.limits_block.setVisible(state["hasLimits"])
        self.limit_low.setText(state["limitLowText"])
        self.limit_high.setText(state["limitHighText"])
        self.limit_bar.set_values(
            state["position"], state["target"], state["showTarget"], state["atLimit"]
        )

        self.tweak_left.setText(f"−{state['stepText']}")
        self.tweak_right.setText(f"+{state['stepText']}")
        if not self.step_input.hasFocus():
            self.step_input.setText(state["stepText"])
        self._show_target_problem(state["error"])

    def _on_target_edited(self, text: str) -> None:
        self._show_target_problem(self._error)

    def _show_target_problem(self, fallback: str) -> None:
        text = self.target_input.text()
        problem = self.validate_target(text)
        set_invalid(self.target_input, bool(problem))
        message = problem or fallback
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))
        self.go_button.setEnabled(bool(text.strip()) and not problem)

    def _submit_target(self) -> None:
        if self.move_to(self.target_input.text()):
            self.target_input.clear()
            self.target_input.clearFocus()

    def _on_step_edited(self) -> None:
        text = self.step_input.text()
        try:
            value = float(text)
        except ValueError:
            return
        if value > 0:
            self.step_size = value

    def apply_theme(self, theme: str):
        super().apply_theme(theme)
        tokens = refresh_kit_theme(self)
        self._apply_styles(tokens)
        self._sync_view()

    def cleanup(self):
        self.limit_bar.stop_animation()
        self.status_pill.cleanup()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = PositionerBoxQWidget(device="samx")
    widget.show()
    sys.exit(app.exec())
