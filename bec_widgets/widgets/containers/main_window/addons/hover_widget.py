import sys

from qtpy.QtCore import QPoint, Qt
from qtpy.QtWidgets import QApplication, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget


class WidgetTooltip(QWidget):
    """Frameless, always-on-top window that behaves like a tooltip."""

    def __init__(self, content: QWidget) -> None:
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.content = content

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.content)
        self.adjustSize()

    def leaveEvent(self, _event) -> None:
        self.hide()

    def show_above(self, global_pos: QPoint, offset: int = 8) -> None:
        self.adjustSize()
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        geom = self.geometry()

        x = global_pos.x() - geom.width() // 2
        y = global_pos.y() - geom.height() - offset

        x = max(screen_geo.left(), min(x, screen_geo.right() - geom.width()))
        y = max(screen_geo.top(), min(y, screen_geo.bottom() - geom.height()))

        self.move(x, y)
        self.show()


class HoverWidget(QWidget):

    def __init__(self, parent: QWidget | None = None, *, simple: QWidget, full: QWidget):
        super().__init__(parent)
        self._simple = simple
        self._full = full
        self._full.setVisible(False)
        self._tooltip = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(simple)

    def enterEvent(self, event):
        # suppress empty-label tooltips for labels
        if isinstance(self._full, QLabel) and not self._full.text():
            return

        if self._tooltip is None:  # first time only
            self._tooltip = WidgetTooltip(self._full)
            self._full.setVisible(True)

        centre = self.mapToGlobal(self.rect().center())
        self._tooltip.show_above(centre)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._tooltip and self._tooltip.isVisible():
            self._tooltip.hide()
        super().leaveEvent(event)

    def close(self):
        if self._tooltip:
            self._tooltip.close()
            self._tooltip.deleteLater()
            self._tooltip = None
        super().close()


################################################################################
# Demo
# Just a simple example to show how the HoverWidget can be used to display
# a tooltip with a full widget inside (two different widgets are used
# for the simple and full versions).
################################################################################


class DemoSimpleWidget(QLabel):  # pragma: no cover
    """A simple widget to be used as a trigger for the tooltip."""

    def __init__(self) -> None:
        super().__init__()
        self.setText("Hover me for a preview!")


class DemoFullWidget(QProgressBar):  # pragma: no cover
    """A full widget to be shown in the tooltip."""

    def __init__(self) -> None:
        super().__init__()
        self.setRange(0, 100)
        self.setValue(75)
        self.setFixedWidth(320)
        self.setFixedHeight(30)


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)

    window = QWidget()
    window.layout = QHBoxLayout(window)
    hover_widget = HoverWidget(simple=DemoSimpleWidget(), full=DemoFullWidget())
    window.layout.addWidget(hover_widget)
    window.show()

    sys.exit(app.exec_())
