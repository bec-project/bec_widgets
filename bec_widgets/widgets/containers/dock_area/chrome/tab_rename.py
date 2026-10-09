"""Rename a dock in place by double-clicking its tab."""

from __future__ import annotations

from typing import Callable

from qtpy.QtCore import QEvent, QObject, Qt
from qtpy.QtWidgets import QLineEdit, QWidget
from shiboken6 import isValid

from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.widgets.containers.qt_ads import CDockWidget


class TabRenameEditor(QLineEdit):
    """Line edit laid over a dock tab. Enter or focus loss commits, Escape cancels."""

    def __init__(self, dock: CDockWidget, on_commit: Callable[[CDockWidget, str], None]):
        tab = dock.tabWidget()
        super().__init__(dock.windowTitle(), tab)
        self.setObjectName("dockTabRenameEditor")
        self._dock = dock
        self._on_commit = on_commit
        self._done = False
        tokens = ThemeTokens()
        self.setStyleSheet(
            f"#dockTabRenameEditor {{ background: {tokens.field.name()}; color: {tokens.fg.name()};"
            f" border: 2px solid {tokens.primary.name()}; border-radius: 4px; padding: 0 4px; }}"
        )
        self.setGeometry(tab.rect().adjusted(2, 2, -2, -2))
        self.setMinimumWidth(120)
        self.resize(max(self.width(), 140), self.height())
        self.selectAll()
        self.editingFinished.connect(self.commit)

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        """Escape cancels the rename."""
        if event.key() == Qt.Key.Key_Escape:
            self._finish()
            return
        super().keyPressEvent(event)

    def commit(self) -> None:
        """Apply the new title unless it is empty."""
        if self._done:
            return
        text = self.text().strip()
        if text and isValid(self._dock) and text != self._dock.windowTitle():
            self._on_commit(self._dock, text)
        self._finish()

    def _finish(self) -> None:
        self._done = True
        self.hide()
        self.deleteLater()


class TabRenameFilter(QObject):
    """Event filter that opens a :class:`TabRenameEditor` on double-click of a dock tab.

    Args:
        on_commit(Callable[[CDockWidget, str], None]): Called with the dock and its new title.
        enabled(Callable[[], bool]): Returns False while renaming is not allowed (locked layout).
        parent(QObject | None): Parent object.
    """

    def __init__(
        self,
        on_commit: Callable[[CDockWidget, str], None],
        enabled: Callable[[], bool] = lambda: True,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._on_commit = on_commit
        self._enabled = enabled
        self._tabs: dict[int, CDockWidget] = {}

    def watch(self, dock: CDockWidget) -> None:
        """Start listening for double-clicks on the tab of ``dock``."""
        tab = dock.tabWidget()
        if tab is None:
            return
        self._tabs[id(tab)] = dock
        tab.installEventFilter(self)
        tab.setToolTip(f"{dock.windowTitle()}\nDouble-click to rename · ID: {dock.objectName()}")

    def start_rename(self, dock: CDockWidget) -> QLineEdit | None:
        """Open the inline editor on ``dock``'s tab and return it."""
        if not isValid(dock) or not self._enabled():
            return None
        editor = TabRenameEditor(dock, self._on_commit)
        editor.show()
        editor.setFocus(Qt.FocusReason.MouseFocusReason)
        return editor

    def eventFilter(self, watched: QWidget, event: QEvent):  # pylint: disable=invalid-name
        """Open the editor on a double-click of a watched tab."""
        if event.type() == QEvent.Type.MouseButtonDblClick:
            dock = self._tabs.get(id(watched))
            if dock is not None and isValid(dock):
                self.start_rename(dock)
                return True
        return super().eventFilter(watched, event)
