from __future__ import annotations

from qtpy.QtCore import Signal
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QLabel


class ClickableLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        self.clicked.emit()
        return super().mouseReleaseEvent(ev)
