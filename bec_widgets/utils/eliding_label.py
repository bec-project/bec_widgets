from __future__ import annotations

from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import QLabel, QSizePolicy, QWidget


class ElidingLabel(QLabel):
    """A ``QLabel`` that elides its text with an ellipsis when too narrow to show it in full.

    ``QLabel`` itself has no elide support (only item views expose ``setTextElideMode``), so this
    computes the elided string with ``QFontMetrics.elidedText`` and refreshes it on every resize.

    ``text()`` always returns the full, unelided text, so callers see the logical value while the
    display shrinks. The label is allowed to shrink below its text width, so a long string never
    forces its container wider or taller.
    """

    def __init__(
        self, parent: QWidget | None = None, mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text: str) -> None:  # noqa: N802
        self._full_text = text or ""
        self._elide()

    def text(self) -> str:
        return self._full_text

    def set_elide_mode(self, mode: Qt.TextElideMode) -> None:
        """Set how the text is shortened (``ElideRight``/``ElideLeft``/``ElideMiddle``)."""
        self._mode = mode
        self._elide()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, super().minimumSizeHint().height())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        super().setText(self.fontMetrics().elidedText(self._full_text, self._mode, self.width()))
