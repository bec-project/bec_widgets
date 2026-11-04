"""A frameless window that behaves like a tooltip, with any content widget."""

from qtpy import QtGui, QtWidgets
from qtpy.QtCore import QPoint, Qt
from qtpy.QtWidgets import QApplication, QFrame, QVBoxLayout, QWidget


class WidgetTooltip(QWidget):
    """Frameless, always-on-top window that behaves like a tooltip."""

    def __init__(self, content: QWidget) -> None:
        super().__init__(
            None,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.content = content

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)

        self._card = QFrame(self)
        self._card.setObjectName("WidgetTooltipCard")
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.addWidget(self.content)

        shadow = QtWidgets.QGraphicsDropShadowEffect(self._card)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 2)
        shadow.setColor(QtGui.QColor(0, 0, 0, 140))
        self._card.setGraphicsEffect(shadow)

        layout.addWidget(self._card)
        self.apply_theme()
        self.adjustSize()

    def leaveEvent(self, _event) -> None:
        self.hide()

    def apply_theme(self) -> None:
        palette = QApplication.palette()
        base = palette.color(QtGui.QPalette.ColorRole.Base)
        text = palette.color(QtGui.QPalette.ColorRole.Text)
        border = palette.color(QtGui.QPalette.ColorRole.Mid)
        background = QtGui.QColor(base)
        background.setAlpha(242)
        self._card.setStyleSheet(f"""
            QFrame#WidgetTooltipCard {{
                background: {background.name(QtGui.QColor.NameFormat.HexArgb)};
                border: 1px solid {border.name()};
                border-radius: 12px;
            }}
            QFrame#WidgetTooltipCard QLabel {{
                color: {text.name()};
                background: transparent;
            }}
            """)

    def show_above(self, global_pos: QPoint, offset: int = 8) -> None:
        """
        Show the tooltip above a global position, adjusting to stay within screen bounds.

        Args:
            global_pos(QPoint): The global position to show above.
            offset(int, optional): The vertical offset from the global position. Defaults to 8 pixels.
        """
        self.apply_theme()
        self.adjustSize()
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        geom = self.geometry()

        x = global_pos.x() - geom.width() // 2
        y = global_pos.y() - geom.height() - offset

        self._navigate_screen_coordinates(screen_geo, geom, x, y)

    def show_near(self, global_pos: QPoint, offset: QPoint | None = None) -> None:
        """
        Show the tooltip near a global position, adjusting to stay within screen bounds.
        By default, it will try to show below and to the right of the position,
        but if that would cause it to go off-screen, it will flip to the other side.

        Args:
            global_pos(QPoint): The global position to show near.
            offset(QPoint, optional): The offset from the global position. Defaults to QPoint(12, 16).
        """

        self.apply_theme()
        self.adjustSize()
        offset = offset or QPoint(12, 16)
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        geom = self.geometry()

        x = global_pos.x() + offset.x()
        y = global_pos.y() + offset.y()

        if x + geom.width() > screen_geo.right():
            x = global_pos.x() - geom.width() - abs(offset.x())
        if y + geom.height() > screen_geo.bottom():
            y = global_pos.y() - geom.height() - abs(offset.y())

        self._navigate_screen_coordinates(screen_geo, geom, x, y)

    def _navigate_screen_coordinates(self, screen_geo, geom, x, y):
        x = max(screen_geo.left(), min(x, screen_geo.right() - geom.width()))
        y = max(screen_geo.top(), min(y, screen_geo.bottom() - geom.height()))

        self.move(x, y)
        self.show()
        self.raise_()
