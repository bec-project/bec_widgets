"""
Tabs that are painted from the palette alone, so they look the same on every platform.

The native tab bar of macOS draws its own background, which does not follow the theme of
the application. These tabs only use colours of the palette.
"""

from __future__ import annotations

from qtpy.QtCore import QRect, QSize, Qt, Signal
from qtpy.QtGui import QFont, QFontMetrics, QPainter, QPalette, QPen
from qtpy.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.widgets.services.hdf5_viewer.style import muted_color


class _TabButton(QAbstractButton):
    """One tab: its name, with a line under it while it is the open one."""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _font(self, strong: bool) -> QFont:
        font = QFont(self.font())
        font.setWeight(QFont.Weight.DemiBold if strong else QFont.Weight.Normal)
        return font

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Room for the name in its heavier weight, so the tab keeps its width when opened."""
        metrics = QFontMetrics(self._font(True))
        return QSize(metrics.horizontalAdvance(self.text()) + 28, metrics.height() + 14)

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """The tab does not shrink below its name."""
        return self.sizeHint()

    def paintEvent(self, _event) -> None:  # pylint: disable=invalid-name
        """Draw the name, the line of the open tab and the keyboard focus."""
        painter = QPainter(self)
        palette = self.palette()
        strong = self.isChecked()
        lively = strong or self.underMouse() or self.hasFocus()
        painter.setFont(self._font(strong))
        painter.setPen(palette.color(QPalette.ColorRole.WindowText) if lively else muted_color())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        if strong:
            line = QRect(6, self.height() - 2, self.width() - 12, 2)
            painter.fillRect(line, palette.color(QPalette.ColorRole.Highlight))
        if self.hasFocus():
            pen = QPen(palette.color(QPalette.ColorRole.Highlight))
            pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(pen)
            painter.drawRect(self.rect().adjusted(2, 2, -3, -5))
        painter.end()


class PaneTabs(QWidget):
    """A row of tabs over the page of the open one, with room for a button on the right."""

    #: Emitted with the index of the tab that was opened.
    current_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[_TabButton] = []
        self._row = QHBoxLayout()
        self._row.setContentsMargins(6, 2, 6, 0)
        self._row.setSpacing(2)
        self._row.addStretch(1)
        self._stack = QStackedWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(self._row)
        layout.addWidget(self._stack, 1)
        self._group.idClicked.connect(self.set_current_index)

    def add_tab(self, page: QWidget, text: str, tool_tip: str = "") -> int:
        """
        Add a tab at the end.

        Args:
            page (QWidget): Shown while the tab is open.
            text (str): Name on the tab.
            tool_tip (str): Explains the tab on hover.

        Returns:
            int: Index of the new tab.
        """
        index = self._stack.addWidget(page)
        button = _TabButton(text, self)
        button.setToolTip(tool_tip)
        button.setAccessibleName(text)
        button.setChecked(index == 0)
        self._group.addButton(button, index)
        self._buttons.append(button)
        self._row.insertWidget(index, button)
        return index

    def set_corner_widget(self, widget: QWidget) -> None:
        """
        Put a widget at the right end of the row of tabs.

        Args:
            widget (QWidget): The widget, for example a button.
        """
        self._row.addWidget(widget)

    def current_index(self) -> int:
        """
        The open tab.

        Returns:
            int: Its index.
        """
        return self._stack.currentIndex()

    def set_current_index(self, index: int) -> None:
        """
        Open a tab.

        Args:
            index (int): Index of the tab.
        """
        if not 0 <= index < len(self._buttons) or index == self._stack.currentIndex():
            return
        self._buttons[index].setChecked(True)
        self._stack.setCurrentIndex(index)
        self.current_changed.emit(index)
