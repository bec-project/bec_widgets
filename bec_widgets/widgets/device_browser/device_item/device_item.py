from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import QMimeData, Qt
from qtpy.QtGui import QDrag
from qtpy.QtWidgets import QHBoxLayout, QLabel, QWidget

if TYPE_CHECKING:
    from qtpy.QtGui import QMouseEvent


class DeviceItem(QWidget):
    def __init__(self, device: str) -> None:
        super().__init__()
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
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(self.device)
            drag.setMimeData(mime_data)
            drag.exec_(Qt.MoveAction)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        print("Double Clicked")
        # TODO: Implement double click action for opening the device properties dialog
        return super().mouseDoubleClickEvent(event)


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = DeviceItem("Device")
    widget.show()
    sys.exit(app.exec_())
