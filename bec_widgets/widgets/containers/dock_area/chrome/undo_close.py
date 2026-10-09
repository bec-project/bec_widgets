"""Close a dock with Undo instead of deleting it at once.

A closed dock is hidden and kept for :data:`UNDO_SECONDS`. A small bar at the bottom of the dock
area says what was closed and offers Undo. When the time runs out, or before anything that saves
or rebuilds the layout, the hidden docks are deleted for real.
"""

from __future__ import annotations

from typing import Callable

from qtpy.QtCore import QEvent, QObject, Qt, QTimer, Signal
from qtpy.QtWidgets import QHBoxLayout, QLabel, QWidget
from shiboken6 import isValid

from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import IconButton, TextButton
from bec_widgets.widgets.containers.qt_ads import CDockWidget

UNDO_SECONDS = 8


class PendingCloses(QObject):
    """Bookkeeping of docks that were closed but can still be restored.

    Args:
        finalize(Callable[[CDockWidget], None]): Deletes a dock for real.
        parent(QObject | None): Parent object.
    """

    changed = Signal()

    def __init__(self, finalize: Callable[[CDockWidget], None], parent: QObject | None = None):
        super().__init__(parent)
        self._finalize = finalize
        self._docks: list[CDockWidget] = []
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(UNDO_SECONDS * 1000)
        self.timer.timeout.connect(self.flush)

    def __contains__(self, dock: object) -> bool:
        return any(d is dock for d in self._docks)

    def __len__(self) -> int:
        return len(self._docks)

    @property
    def last(self) -> CDockWidget | None:
        """The most recently closed dock that can still be restored."""
        self._docks = [d for d in self._docks if isValid(d)]
        return self._docks[-1] if self._docks else None

    def close(self, dock: CDockWidget) -> None:
        """Hide ``dock`` and keep it restorable for a few seconds."""
        if dock in self:
            return
        dock.toggleView(False)
        self._docks.append(dock)
        self.timer.start()
        self.changed.emit()

    def undo(self) -> CDockWidget | None:
        """Show the most recently closed dock again and return it."""
        dock = self.last
        if dock is None:
            return None
        self._docks.remove(dock)
        dock.toggleView(True)
        dock.setAsCurrentTab()
        if self._docks:
            self.timer.start()
        else:
            self.timer.stop()
        self.changed.emit()
        return dock

    def flush(self) -> None:
        """Delete every pending dock now."""
        self.timer.stop()
        docks, self._docks = self._docks, []
        for dock in docks:
            if isValid(dock):
                self._finalize(dock)
        if docks:
            self.changed.emit()


class UndoBar(QWidget):
    """Floating bar shown at the bottom of the dock area after a widget was closed."""

    undo_requested = Signal()
    dismissed = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("dockUndoBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 6, 6)
        layout.setSpacing(8)
        self.label = QLabel(self)
        self.undo_button = TextButton("Undo", "ghost", "undo", self)
        self.undo_button.setToolTip("Bring the widget back (Ctrl+Z)")
        self.close_button = IconButton("close", "Dismiss", self, size=16)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.undo_button)
        layout.addWidget(self.close_button)
        self.undo_button.clicked.connect(self.undo_requested)
        self.close_button.clicked.connect(self.dismissed)
        parent.installEventFilter(self)
        self.refresh_theme()
        self.hide()

    def refresh_theme(self) -> None:
        """Apply the current theme colours."""
        tokens = ThemeTokens()
        self.setStyleSheet(
            f"#dockUndoBar {{ background: {tokens.card.name()};"
            f" border: 1px solid {tokens.border.name()}; border-radius: 8px; }}"
            f"#dockUndoBar QLabel {{ color: {tokens.fg.name()}; font-size: 13px; }}"
        )
        self.undo_button.refresh_theme(tokens)
        self.close_button.refresh_theme(tokens)

    def show_message(self, text: str) -> None:
        """Show ``text`` with the Undo button and place the bar."""
        self.label.setText(text)
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()

    def _place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        width = min(max(self.sizeHint().width(), 320), max(parent.width() - 32, 200))
        self.resize(width, self.sizeHint().height())
        self.move((parent.width() - width) // 2, parent.height() - self.height() - 18)

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        """Keep the bar at the bottom centre when the dock area is resized."""
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            if self.isVisible():
                self._place()
        return super().eventFilter(watched, event)
