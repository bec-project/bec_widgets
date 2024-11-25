from __future__ import annotations

from typing import TYPE_CHECKING

from bec_lib.logger import bec_logger
from qtpy.QtCore import QMimeData, Qt
from qtpy.QtGui import QDrag
from qtpy.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

if TYPE_CHECKING:
    from qtpy.QtGui import QMouseEvent

logger = bec_logger.logger


class DeviceItem(QWidget):
    def __init__(self, device: str) -> None:
        super().__init__()

        self._drag_pos = None

        self.device = device
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 2, 10, 2)
        self.label = QLabel(device)
        layout.addWidget(self.label)
        self.setLayout(layout)

        self.setStyleSheet(
            """
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 10px;
        """
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not (event.buttons() and Qt.LeftButton):
            return
        if (event.pos() - self._drag_pos).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.device)
        drag.setMimeData(mime_data)
        drag.exec_(Qt.MoveAction)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        logger.debug("Double Clicked")
        # TODO: Implement double click action for opening the device properties dialog
        return super().mouseDoubleClickEvent(event)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = DeviceItem("Device")
    widget.show()
    sys.exit(app.exec_())
