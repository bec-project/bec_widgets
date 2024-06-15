from enum import Enum
from typing import Literal

from PyQt6.QtGui import QPaintEvent
from qtpy import QtGui
from qtpy.QtCore import QRect, Qt
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget

from bec_widgets.utils.bec_connector import BECConnector, ConnectionConfig


class RoundStatusIndicatorConfig(ConnectionConfig):
    """
    Configuration for the RoundStatusIndicator
    """

    state: Literal["success", "failure", "warning"] = "success"


class RoundStatusIndicator(BECConnector, QWidget):

    indicator_config = {
        "success": {"color": "#24a148", "text": "✔", "offset": 0.25},
        "failure": {"color": "#da1e28", "text": "✘", "offset": 0.28},
        "warning": {"color": "#ffcc00", "text": "!", "offset": 0.28},
    }

    USER_ACCESS = ["set_state"]

    def __init__(
        self,
        client=None,
        config: RoundStatusIndicatorConfig | dict | None = None,
        gui_id=None,
        parent=None,
    ):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QWidget.__init__(self, parent=parent)
        self.config = config or RoundStatusIndicatorConfig(widget_class=self.__class__.__name__)
        self.active_state_config = self.indicator_config[self.config.state]

    def paintEvent(self, _event: QPaintEvent) -> None:
        """
        Paint the widget.

        Args:
            _event (QPaintEvent): The paint event
        """

        color = QtGui.QColor(self.active_state_config["color"])  # Red color as default
        text_color = QtGui.QColor("#ffffff")  # White color for text
        text = self.active_state_config["text"]
        offset = self.active_state_config["offset"]

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Determine the size of the widget
        size = min(self.width(), self.height())
        rect = QRect(0, 0, size, size)

        # Set the color and draw the disk
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect)

        # Draw the exclamation mark "!"
        painter.setPen(text_color)
        font = painter.font()
        font.setPixelSize(int(size * 0.9))  # Adjust font size based on widget size
        painter.setFont(font)

        # text_rect = painter.boundingRect(rect, Qt.AlignmentFlag.AlignCenter, text)

        font_metrics = QtGui.QFontMetrics(font)
        text_width = font_metrics.horizontalAdvance(text)
        text_height = font_metrics.height()

        text_x = int(rect.center().x() - text_width / 2)
        text_y = int(rect.center().y() + text_height * offset)
        painter.drawText(text_x, text_y, text)

    def set_state(self, state: Literal["success", "failure", "warning"]) -> None:
        """
        Set the state of the indicator.

        Args:
            state (str): The state of the indicator. Can be "success", "failure", or "warning"

        """
        self.config.state = state
        self.active_state_config = self.indicator_config[state]
        self.update()


if __name__ == "__main__":
    app = QApplication([])

    window = QMainWindow()
    status_indicator = RoundStatusIndicator()
    window.setCentralWidget(status_indicator)
    window.resize(200, 200)
    window.show()

    # Example of changing the color
    status_indicator.set_state("warning")  # Change to a different color

    app.exec()
