from qtpy.QtCore import QTimer
from qtpy.QtGui import QFontMetrics, QPainter
from qtpy.QtWidgets import QLabel


class ScrollLabel(QLabel):
    """A QLabel that scrolls its text horizontally across the widget."""

    def __init__(self, parent=None, speed_ms=30, step_px=1, delay_ms=2000):
        super().__init__(parent=parent)
        self._offset = 0
        self._text_width = 0

        # scrolling timer (runs continuously once started)
        self._timer = QTimer(self)
        self._timer.setInterval(speed_ms)
        self._timer.timeout.connect(self._scroll)

        # delay‑before‑scroll timer (single‑shot)
        self._delay_timer = QTimer(self)
        self._delay_timer.setSingleShot(True)
        self._delay_timer.setInterval(delay_ms)
        self._delay_timer.timeout.connect(self._timer.start)

        self._step_px = step_px

    def setText(self, text):
        """
        Overridden to ensure that new text replaces the current one
        immediately.
        If the label was already scrolling (or in its delay phase),
        the next message starts **without** the extra delay.
        """
        # Determine whether the widget was already in a scrolling cycle
        was_scrolling = self._timer.isActive() or self._delay_timer.isActive()

        super().setText(text)

        fm = QFontMetrics(self.font())
        self._text_width = fm.horizontalAdvance(text)
        self._offset = 0

        # Skip the delay when we were already scrolling
        self._update_timer(skip_delay=was_scrolling)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_timer()

    def _update_timer(self, *, skip_delay: bool = False):
        """
        Decide whether to start or stop scrolling.

        If the text is wider than the visible area, start a single‑shot
        delay timer (2s by default). Scrolling begins only after this
        delay. Any change (resize or new text) restarts the logic.
        """
        needs_scroll = self._text_width > self.width()

        if needs_scroll:
            # Reset any running timers
            if self._timer.isActive():
                self._timer.stop()
            if self._delay_timer.isActive():
                self._delay_timer.stop()

            self._offset = 0

            # Start scrolling immediately when we should skip the delay,
            # otherwise apply the configured delay_ms interval
            if skip_delay:
                self._timer.start()
            else:
                self._delay_timer.start()
        else:
            if self._delay_timer.isActive():
                self._delay_timer.stop()
            if self._timer.isActive():
                self._timer.stop()
            self.update()

    def _scroll(self):
        self._offset += self._step_px
        if self._offset >= self._text_width:
            self._offset = 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing)
        text = self.text()
        if not text:
            return
        fm = QFontMetrics(self.font())
        y = (self.height() + fm.ascent() - fm.descent()) // 2
        if self._text_width <= self.width():
            painter.drawText(0, y, text)
        else:
            x = -self._offset
            gap = 50  # space between repeating text blocks
            while x < self.width():
                painter.drawText(x, y, text)
                x += self._text_width + gap

    def cleanup(self):
        """Stop all timers to prevent memory leaks."""
        if self._timer.isActive():
            self._timer.stop()
        if self._delay_timer.isActive():
            self._delay_timer.stop()
