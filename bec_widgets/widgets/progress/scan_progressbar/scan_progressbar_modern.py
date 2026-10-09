"""Scan progress bar with the modern UX, built from plain QWidgets on top of ScanProgressModel."""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath
from qtpy.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_theme_name
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.progress.scan_progressbar.scan_progress_model import (
    ScanProgressModel,
    current_theme_colors,
)


def _theme_color(key: str, fallback: str = "#888888") -> QColor:
    return current_theme_colors().get(key, QColor(fallback))


class _ProgressTrack(QWidget):
    """Rounded track with an animated fill, a running sheen and an indeterminate mode."""

    def __init__(self, parent=None, height: int = 8):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._fraction = 0.0
        self._color = QColor("#0a60ff")
        self._running = False
        self._indeterminate = False
        self._phase = 0.0

        self._anim = QPropertyAnimation(self, b"fraction", self)
        self._anim.setDuration(250)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # one timer drives the sheen and the indeterminate segment (~30 fps, only when needed)
        self._phase_timer = QTimer(self)
        self._phase_timer.setInterval(33)
        self._phase_timer.timeout.connect(self._advance)

    def get_fraction(self) -> float:
        return self._fraction

    def set_fraction(self, value: float):
        self._fraction = value
        self.update()

    fraction = Property(float, get_fraction, set_fraction)

    def set_state(self, fraction: float, color: QColor, running: bool, indeterminate: bool):
        """Update target fraction, colour and animation mode."""
        self._color = color
        self._running = running
        self._indeterminate = indeterminate
        if abs(fraction - self._fraction) > 1e-4:
            self._anim.stop()
            self._anim.setStartValue(self._fraction)
            self._anim.setEndValue(fraction)
            self._anim.start()
        animate = (running or indeterminate) and self.isVisible()
        if animate and not self._phase_timer.isActive():
            self._phase_timer.start()
        elif not animate:
            self._phase_timer.stop()
        self.update()

    def _advance(self):
        self._phase = (self._phase + 0.033 / 1.6) % 1.0
        self.update()

    def hideEvent(self, event):
        self._phase_timer.stop()
        super().hideEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        track = QColor(255, 255, 255, 20) if get_theme_name() == "dark" else QColor(0, 0, 0, 18)
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.setClipPath(clip)
        painter.fillPath(clip, track)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)

        if self._indeterminate:
            # triangle wave 0..1..0 for the sliding segment
            t = self._phase * 2 if self._phase < 0.5 else 2 - self._phase * 2
            seg = rect.width() * 0.3
            painter.drawRoundedRect(
                QRectF(t * (rect.width() - seg), 0, seg, rect.height()), radius, radius
            )
            return

        if self._fraction <= 0:
            return
        width = max(rect.height(), rect.width() * self._fraction)
        fill = QRectF(0, 0, width, rect.height())
        painter.drawRoundedRect(fill, radius, radius)

        if self._running and width > 24:
            x = -40 + self._phase * (width + 40)
            grad = QLinearGradient(x, 0, x + 40, 0)
            grad.setColorAt(0.0, QColor(255, 255, 255, 0))
            grad.setColorAt(0.5, QColor(255, 255, 255, 72))
            grad.setColorAt(1.0, QColor(255, 255, 255, 0))
            sheen = QPainterPath()
            sheen.addRoundedRect(fill, radius, radius)
            painter.fillPath(sheen, grad)


class _StateChip(QWidget):
    """Pill with a filled Material icon and the state label, tinted with the state colour."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor("#888888")
        self._icon = QLabel(self)
        self._label = QLabel(self)
        font = self._label.font()
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        self._label.setFont(font)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 2, 8, 2)
        layout.setSpacing(4)
        layout.addWidget(self._icon)
        layout.addWidget(self._label)
        self.setFixedHeight(20)
        self._icon_key = None

    def set_state(self, label: str, icon: str, color: QColor):
        self._color = color
        # chip text needs more contrast than the bar fill on light backgrounds
        ink = color if get_theme_name() == "dark" else color.darker(150)
        self._label.setText(label)
        _set_text_color(self._label, ink.name())
        key = (icon, ink.name())
        if key != self._icon_key:
            self._icon.setPixmap(material_icon(icon, size=(14, 14), color=ink, filled=True))
            self._icon_key = key
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(self._color)
        bg.setAlphaF(0.16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        r = QRectF(self.rect())
        painter.drawRoundedRect(r, r.height() / 2, r.height() / 2)


class _Dot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(8, 8)
        self.color = QColor("#888888")

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.color)
        painter.drawEllipse(self.rect())


def _set_text_color(label: QLabel, color: str):
    """Set the label colour, skipping the costly stylesheet update when it is unchanged."""
    if label.property("_text_color") != color:
        label.setProperty("_text_color", color)
        label.setStyleSheet(f"color: {color};")


def _small_label(parent, size: int = 11, bold: bool = False) -> QLabel:
    label = QLabel(parent)
    font = label.font()
    font.setPixelSize(size)
    if bold:
        font.setWeight(QFont.Weight.DemiBold)
    label.setFont(font)
    return label


class ScanProgressBarModern(BECWidget, QWidget):
    """
    Scan progress bar with a state chip, smooth bar and time estimate, built from QWidgets.

    Same UX as ``ScanProgressBarQml`` and the same public API as ``ScanProgressBar``.
    """

    ICON_NAME = "timelapse"
    PLUGIN = False
    RPC = False
    progress_started = Signal()
    progress_finished = Signal()

    def __init__(
        self, parent=None, client=None, config=None, gui_id=None, one_line_design=False, **kwargs
    ):
        kwargs.pop("enable_dynamic_stylesheet", None)
        super().__init__(parent=parent, client=client, config=config, gui_id=gui_id, **kwargs)
        self.get_bec_shortcuts()
        self._compact = bool(one_line_design)
        self._show_elapsed = True
        self._show_remaining = True
        self._show_source = True

        self.model = ScanProgressModel(self.bec_dispatcher, parent=self)
        self.model.progress_started.connect(self.progress_started)
        self.model.progress_finished.connect(self.progress_finished)
        self.model.changed.connect(self._render)

        if self._compact:
            self._build_compact()
        else:
            self._build_full()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._render()

    @property
    def progress_tracker(self):
        """The underlying BECProgressTracker."""
        return self.model.tracker

    def _build_full(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.chip = _StateChip(self)
        self.title_label = _small_label(self, 12)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.percent_label = _small_label(self, 15, bold=True)
        top.addWidget(self.chip)
        top.addWidget(self.title_label, 1)
        top.addWidget(self.percent_label)

        self.track = _ProgressTrack(self, height=8)

        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        self.count_label = _small_label(self)
        self.elapsed_label = _small_label(self)
        self.dot_label = _small_label(self)
        self.dot_label.setText("·")
        self.time_label = _small_label(self)
        bottom.addWidget(self.count_label)
        bottom.addStretch(1)
        bottom.addWidget(self.elapsed_label)
        bottom.addWidget(self.dot_label)
        bottom.addWidget(self.time_label)

        layout.addLayout(top)
        layout.addWidget(self.track)
        layout.addLayout(bottom)
        self.setFixedHeight(58)

    def _build_compact(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(6)
        self.dot = _Dot(self)
        self.title_label = _small_label(self)
        self.title_label.setMaximumWidth(120)
        self.track = _ProgressTrack(self, height=6)
        self.percent_label = _small_label(self)
        self.time_label = _small_label(self)
        for w in (self.dot, self.title_label, self.track, self.percent_label, self.time_label):
            layout.addWidget(w, 1 if w is self.track else 0, Qt.AlignmentFlag.AlignVCenter)
        self.setFixedHeight(22)

    @SafeSlot()
    def _render(self):
        m = self.model
        color = _theme_color(m.stateColorKey)
        fg = _theme_color("FG", "#e0e0e0").name()
        muted = _theme_color("DISABLED_FG").name()
        self.track.set_state(m.fraction, color, m.state == "running", m.indeterminate)
        self.title_label.setText(
            self.title_label.fontMetrics().elidedText(
                m.title, Qt.TextElideMode.ElideRight, max(40, self.title_label.width())
            )
            if not self._compact
            else m.title
        )
        self.title_label.setVisible(self._show_source)
        self.percent_label.setText(m.percentText)
        self.time_label.setText(m.timeText)
        self.time_label.setVisible(self._show_remaining and bool(m.timeText))
        self.setToolTip(m.toolTip)

        if self._compact:
            self.dot.color = color
            self.dot.update()
            for lbl in (self.title_label, self.percent_label):
                _set_text_color(lbl, fg)
            _set_text_color(self.time_label, muted)
            return

        self.chip.set_state(m.stateLabel, m.stateIcon, color)
        _set_text_color(self.title_label, muted if m.state == "idle" else fg)
        _set_text_color(self.percent_label, fg)
        self.count_label.setText(f"{m.countText} points" if m.countText else "")
        show_elapsed = self._show_elapsed and m.active and bool(m.elapsedText)
        self.elapsed_label.setText(f"{m.elapsedText} elapsed")
        self.elapsed_label.setVisible(show_elapsed)
        self.dot_label.setVisible(show_elapsed and self.time_label.isVisibleTo(self))
        for lbl in (self.count_label, self.elapsed_label, self.dot_label):
            _set_text_color(lbl, muted)
        _set_text_color(self.time_label, fg if m.state == "running" else muted)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._compact:
            self._render()

    def apply_theme(self, theme: str):
        self._render()

    @SafeProperty(bool)
    def show_elapsed_time(self):
        return self._show_elapsed

    @show_elapsed_time.setter
    def show_elapsed_time(self, value):
        self._show_elapsed = bool(value)
        self._render()

    @SafeProperty(bool)
    def show_remaining_time(self):
        return self._show_remaining

    @show_remaining_time.setter
    def show_remaining_time(self, value):
        self._show_remaining = bool(value)
        self._render()

    @SafeProperty(bool)
    def show_source_label(self):
        return self._show_source

    @show_source_label.setter
    def show_source_label(self, value):
        self._show_source = bool(value)
        self._render()

    def update_labels(self):
        """Kept for API compatibility; the view updates itself from the model."""
        self.model._tick()

    def cleanup(self):
        self.model.cleanup()
        self.track._phase_timer.stop()
        self.track._anim.stop()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    widget = ScanProgressBarModern()
    widget.show()
    app.exec_()
