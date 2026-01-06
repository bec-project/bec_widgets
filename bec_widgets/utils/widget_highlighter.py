from __future__ import annotations

import shiboken6
from qtpy.QtCore import QPropertyAnimation, QRect, QSequentialAnimationGroup, Qt
from qtpy.QtWidgets import QFrame, QWidget


class WidgetHighlighter:
    """
    Utility that highlights widgets by drawing a temporary frame around them.
    """

    def __init__(
        self,
        *,
        frame_parent: QWidget | None = None,
        window_flags: Qt.WindowType | Qt.WindowFlags = Qt.WindowType.Tool
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint,
        style_sheet: str = "border: 2px solid #FF00FF; border-radius: 6px; background: transparent;",
    ) -> None:
        self._frame_parent = frame_parent
        self._window_flags = window_flags
        self._style_sheet = style_sheet
        self._frame: QFrame | None = None
        self._animation_group: QSequentialAnimationGroup | None = None

    def highlight(self, widget: QWidget | None) -> None:
        """
        Highlight the given widget with a pulsing frame.
        """
        if widget is None or not shiboken6.isValid(widget):
            return

        frame = self._ensure_frame()
        frame.hide()

        geom = widget.frameGeometry()
        top_left = widget.mapToGlobal(widget.rect().topLeft())
        frame.setGeometry(top_left.x(), top_left.y(), geom.width(), geom.height())
        frame.setWindowOpacity(1.0)
        frame.show()

        start_rect = QRect(
            top_left.x() - 5, top_left.y() - 5, geom.width() + 10, geom.height() + 10
        )

        pulse = QPropertyAnimation(frame, b"geometry", frame)
        pulse.setDuration(300)
        pulse.setStartValue(start_rect)
        pulse.setEndValue(QRect(top_left.x(), top_left.y(), geom.width(), geom.height()))

        fade = QPropertyAnimation(frame, b"windowOpacity", frame)
        fade.setDuration(2000)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.finished.connect(frame.hide)

        if self._animation_group is not None:
            old_group = self._animation_group
            self._animation_group = None
            old_group.stop()
            old_group.deleteLater()

        animation = QSequentialAnimationGroup(frame)
        animation.addAnimation(pulse)
        animation.addAnimation(fade)
        animation.start()

        self._animation_group = animation

    def cleanup(self) -> None:
        """
        Delete the highlight frame and cancel pending animations.
        """
        if self._animation_group is not None:
            self._animation_group.stop()
            self._animation_group.deleteLater()
            self._animation_group = None
        if self._frame is not None:
            self._frame.hide()
            self._frame.deleteLater()
            self._frame = None

    @property
    def frame(self) -> QFrame | None:
        """Return the currently allocated highlight frame (if any)."""
        return self._frame

    def _ensure_frame(self) -> QFrame:
        if self._frame is None:
            self._frame = QFrame(self._frame_parent, self._window_flags)
            self._frame.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self._frame.setStyleSheet(self._style_sheet)
        return self._frame
