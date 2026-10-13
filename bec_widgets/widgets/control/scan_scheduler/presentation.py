"""Compact step cards and collapsible inspector sections."""

from __future__ import annotations

from qtpy.QtCore import QEvent, QRect, QSize, Qt
from qtpy.QtGui import QColor, QFont, QPainter, QPen
from qtpy.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import theme_color

# Qt signal descriptors are not understood by pylint.
# pylint: disable=no-member

LABELS = {
    "sequence": "Sequence group",
    "repeat": "Repeat group",
    "for_each": "For each value",
    "while": "While condition",
    "set": "Set device or signal",
    "scan_call": "Scan",
    "component_call": "Reusable component",
}


def step_title(node: dict) -> str:
    """Return the supplied step name or a readable name for a generated identity.

    Args:
        node (dict): Sequence component.

    Returns:
        str: Human-readable tree title.
    """
    identity = node["id"]
    if identity.startswith(node["type"] + "_"):
        if node["type"] == "scan_call" and node.get("name"):
            return node["name"].replace("_", " ").capitalize()
        return LABELS[node["type"]]
    return identity.replace("_", " ").capitalize()


class StepDelegate(QStyledItemDelegate):
    """Paint two-line nested step cards using the application's palette."""

    def sizeHint(self, _option, _index) -> QSize:
        """Reserve a compact card row.

        Args:
            _option (QStyleOptionViewItem): Item style options.
            _index (QModelIndex): Tree item index.

        Returns:
            QSize: Card dimensions.
        """
        return QSize(240, 66)

    def paint(self, painter, option, index) -> None:
        """Render a step title and its execution behavior.

        Args:
            painter (QPainter): Active Qt painter.
            option (QStyleOptionViewItem): Item style options.
            index (QModelIndex): Tree item index.
        """
        painter.save()
        rect = option.rect.adjusted(2, 3, -8, -3)
        selected = bool(option.state & QStyle.State_Selected)
        palette = QApplication.palette()
        theme = getattr(QApplication.instance(), "theme", None)
        accent = theme_color(theme, "PRIMARY", palette.highlight().color())
        background = theme_color(theme, "CARD_BG", palette.window().color())
        foreground = theme_color(theme, "FG", palette.text().color())
        border = theme_color(theme, "BORDER", palette.midlight().color())
        if selected:
            background = QColor(
                int(background.red() * 0.9 + accent.red() * 0.1),
                int(background.green() * 0.9 + accent.green() * 0.1),
                int(background.blue() * 0.9 + accent.blue() * 0.1),
            )
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(accent if selected else border, 1))
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 5, 5)
        title = QFont(option.font)
        title.setBold(True)
        painter.setFont(title)
        painter.setPen(foreground)
        painter.drawText(
            rect.adjusted(30, 8, -32, -28),
            Qt.AlignVCenter,
            option.fontMetrics.elidedText(str(index.data()), Qt.ElideRight, rect.width() - 62),
        )
        if index.data(Qt.DecorationRole) is not None:
            index.data(Qt.DecorationRole).paint(
                painter, QRect(rect.left() + 10, rect.top() + 11, 14, 14)
            )
        painter.drawText(rect.adjusted(rect.width() - 26, 5, -6, -30), Qt.AlignCenter, "⋯")
        painter.setFont(option.font)
        muted = QColor(foreground)
        muted.setAlpha(160)
        painter.setPen(muted)
        subtitle = str(index.data(Qt.UserRole + 1) or "")
        painter.drawText(
            rect.adjusted(12, 30, -12, -7),
            Qt.AlignVCenter,
            option.fontMetrics.elidedText(subtitle, Qt.ElideRight, rect.width() - 24),
        )
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:
        """Open step actions from the card's overflow control.

        Args:
            event (QEvent): Item input event.
            model (QAbstractItemModel): Tree model.
            option (QStyleOptionViewItem): Item geometry.
            index (QModelIndex): Target item.

        Returns:
            bool: Whether the overflow click was handled.
        """
        if (
            event.type() == QEvent.MouseButtonRelease
            and event.button() == Qt.LeftButton
            and event.pos().x() > option.rect.right() - 35
        ):
            self.parent().customContextMenuRequested.emit(event.pos())
            return True
        return super().editorEvent(event, model, option, index)


class Section(QWidget):
    """Hold optional inspector controls behind a disclosure button.

    Args:
        title (str): Section label.
        content (QWidget): Controls to show when expanded.
        parent (QWidget | None): Owning widget.
    """

    def __init__(self, title: str, content: QWidget, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.toggle = QToolButton(self)
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.RightArrow)
        content.setVisible(False)
        layout.addWidget(self.toggle)
        layout.addWidget(content)
        self.toggle.toggled.connect(content.setVisible)
        self.toggle.toggled.connect(
            lambda checked: self.toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        )
