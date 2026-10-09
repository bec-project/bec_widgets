"""Improved chrome of the BEC dock area.

:class:`DockChrome` adds to a ``BECDockArea``:

* human dock titles (``Motor``, ``Waveform 2``) that can be renamed by double-clicking the tab,
* tab-only close with an Undo bar instead of deleting a whole group at once,
* one Add widget gallery with search and a placement choice (Ctrl+Shift+A),
* an empty state with starter layouts.

The gallery and the empty state come in a QWidget and a QML version; ``BEC_DOCK_CHROME`` picks
one (see :func:`~.ads_style.chrome_mode`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import QEvent, QObject, Qt, QTimer
from qtpy.QtGui import QKeySequence, QShortcut
from qtpy.QtWidgets import QApplication, QWidget
from shiboken6 import isValid

from bec_widgets.widgets.containers.dock_area.chrome.ads_style import (
    apply_dock_chrome_style,
    chrome_mode,
    configure_ads_flags,
)
from bec_widgets.widgets.containers.dock_area.chrome.catalog import (
    STARTER_LAYOUTS,
    display_name,
    entry_for,
    unique_title,
)
from bec_widgets.widgets.containers.dock_area.chrome.gallery_common import GalleryController
from bec_widgets.widgets.containers.dock_area.chrome.tab_rename import TabRenameFilter
from bec_widgets.widgets.containers.dock_area.chrome.undo_close import PendingCloses, UndoBar
from bec_widgets.widgets.containers.qt_ads import CDockWidget

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea

__all__ = ["DockChrome", "chrome_mode", "configure_ads_flags", "apply_dock_chrome_style"]


class DockChrome(QObject):
    """Owns the gallery, empty state, undo bar and tab renaming of one dock area.

    Args:
        area(BECDockArea): The dock area to decorate.
        mode(str): ``qwidget`` or ``qml``.
    """

    def __init__(self, area: "BECDockArea", mode: str = "qwidget"):
        super().__init__(area)
        self.area = area
        self.mode = mode
        self.controller = GalleryController(parent=self)
        self.controller.widget_requested.connect(self.add_widget)
        self.controller.layout_requested.connect(self.build_layout)
        self.pending = PendingCloses(area._delete_dock, self)
        self.pending.changed.connect(self.refresh_empty_state)
        self._batches: list[list[CDockWidget]] = []
        self._batch_open = False
        self._last_dock: CDockWidget | None = None
        self.gallery = None

        self.undo_bar = UndoBar(area)
        self.undo_bar.undo_requested.connect(self.undo_close)
        self.undo_bar.dismissed.connect(self.pending.flush)
        self.pending.timer.timeout.connect(self.undo_bar.hide)

        self.renamer = TabRenameFilter(
            self.rename_dock, lambda: not self.area.workspace_is_locked, self
        )

        if mode == "qml":
            from bec_widgets.widgets.containers.dock_area.chrome.chrome_qml import EmptyStateQml

            self.empty_state = EmptyStateQml(self.controller, area)
        else:
            from bec_widgets.widgets.containers.dock_area.chrome.chrome_qwidget import (
                EmptyStateQWidget,
            )

            self.empty_state = EmptyStateQWidget(self.controller, area)
        self.empty_state.add_requested.connect(lambda: self.open_gallery(None))
        self.empty_state.hide()

        self._add_shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), area)
        self._add_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._add_shortcut.activated.connect(lambda: self.open_gallery(None))
        self._undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), area)
        self._undo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._undo_shortcut.setEnabled(False)
        self._undo_shortcut.activated.connect(self.undo_close)

        manager = area.dock_manager
        manager.installEventFilter(self)
        manager.dockWidgetAdded.connect(self._on_dock_added)
        manager.dockWidgetRemoved.connect(lambda *_: self.refresh_empty_state())
        manager.stateRestored.connect(self.refresh_empty_state)
        manager.focusedDockWidgetChanged.connect(self._on_focus_changed)
        apply_dock_chrome_style(manager, True)
        QTimer.singleShot(0, self.refresh_empty_state)

    # ------------------------------------------------------------------ titles
    def init_dock(self, dock: CDockWidget, widget: QWidget) -> None:
        """Give a new dock its human title and enable renaming on its tab."""
        if not getattr(dock, "_custom_title", False):
            taken = {d.windowTitle() for d in self.area.dock_list() if d is not dock}
            dock.setWindowTitle(unique_title(display_name(type(widget).__name__), taken))
        self.renamer.watch(dock)

    def rename_dock(self, dock: CDockWidget, title: str) -> None:
        """Set the title shown on ``dock``'s tab and keep it when the profile is saved."""
        title = title.strip()
        if not title or not isValid(dock):
            return
        dock.setWindowTitle(title)
        dock._custom_title = True  # pylint: disable=protected-access
        self.renamer.watch(dock)

    # ------------------------------------------------------------------ close with undo
    def close_dock(self, dock: CDockWidget) -> None:
        """Hide ``dock`` and offer Undo; it is deleted when the undo time runs out."""
        if not self._batch_open:
            self._batches.append([])
            self._batch_open = True
            QTimer.singleShot(0, self._end_batch)
        self._batches[-1].append(dock)
        self.pending.close(dock)
        batch = self._batches[-1]
        if len(batch) == 1:
            text = f"Closed “{dock.windowTitle()}”"
        else:
            text = f"Closed {len(batch)} widgets"
        self.undo_bar.show_message(text)
        self._undo_shortcut.setEnabled(True)

    def _end_batch(self) -> None:
        self._batch_open = False

    def undo_close(self) -> None:
        """Bring back the widgets closed last."""
        if not self._batches:
            self.undo_bar.hide()
            return
        batch = self._batches.pop()
        restored = None
        for dock in reversed(batch):
            if dock in self.pending and dock is self.pending.last:
                restored = self.pending.undo()
        self._batches = [[d for d in b if d in self.pending] for b in self._batches]
        self._batches = [b for b in self._batches if b]
        if restored is not None and isValid(restored):
            self.area.dock_manager.setDockWidgetFocused(restored)
        if not self._batches:
            self.undo_bar.hide()
            self._undo_shortcut.setEnabled(False)
        self.refresh_empty_state()

    def flush(self) -> None:
        """Delete all closed docks now, e.g. before saving or rebuilding the layout."""
        self._batches = []
        self.pending.flush()
        self.undo_bar.hide()
        self._undo_shortcut.setEnabled(False)

    # ------------------------------------------------------------------ adding widgets
    def anchor_dock(self) -> CDockWidget | None:
        """Dock that Beside, Below and As tab refer to: the focused one, else the last added."""
        visible = [d for d in self.area.dock_list() if not d.isClosed()]
        focused = self.area.dock_manager.focusedDockWidget()
        for candidate in (focused, self._last_dock):
            if candidate is not None and isValid(candidate) and candidate in visible:
                if not candidate.isFloating():
                    return candidate
        docked = [d for d in visible if not d.isFloating()]
        return docked[-1] if docked else None

    def open_gallery(self, anchor_widget: QWidget | None = None) -> None:
        """Open the Add widget gallery below ``anchor_widget`` (centred when None)."""
        if self.area.workspace_is_locked:
            return
        anchor = self.anchor_dock()
        self.controller.set_anchor_title(anchor.windowTitle() if anchor is not None else "")
        if self.gallery is None:
            if self.mode == "qml":
                from bec_widgets.widgets.containers.dock_area.chrome.chrome_qml import (
                    WidgetGalleryQmlPopup,
                )

                self.gallery = WidgetGalleryQmlPopup(self.controller, self.area)
            else:
                from bec_widgets.widgets.containers.dock_area.chrome.chrome_qwidget import (
                    WidgetGalleryPopup,
                )

                self.gallery = WidgetGalleryPopup(self.controller, self.area)
        self.gallery.open_at(anchor_widget)

    def add_widget(self, widget_class: str, placement: str = "beside", anchor=None):
        """Add ``widget_class`` at ``placement`` relative to the anchor dock.

        Args:
            widget_class(str): Registered widget class name.
            placement(str): ``beside``, ``below``, ``tab``, ``column`` or ``floating``.
            anchor(CDockWidget | None): Reference dock; defaults to :meth:`anchor_dock`.

        Returns:
            The created widget, or None when creation failed.
        """
        entry = entry_for(widget_class)
        kwargs = dict(entry.new_kwargs) if entry is not None else {}
        anchor = anchor if anchor is not None else self.anchor_dock()
        if placement == "floating":
            kwargs["start_floating"] = True
        elif anchor is None or placement == "column":
            kwargs["where"] = "right"
        elif placement == "beside":
            kwargs.update(where="right", relative_to=anchor)
        elif placement == "below":
            kwargs.update(where="bottom", relative_to=anchor)
        elif placement == "tab":
            kwargs["tab_with"] = anchor
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            widget = self.area.new(widget_class, **kwargs)
        finally:
            QApplication.restoreOverrideCursor()
        dock = self.dock_of(widget)
        if dock is not None:
            dock.setAsCurrentTab()
            self.area.dock_manager.setDockWidgetFocused(dock)
        return widget

    def build_layout(self, name: str) -> None:
        """Fill the dock area with the starter layout called ``name``."""
        layout = next((item for item in STARTER_LAYOUTS if item.name == name), None)
        if layout is None:
            return
        docks: list[CDockWidget | None] = []
        for widget_class, placement, anchor_index in layout.steps:
            anchor = docks[anchor_index] if anchor_index is not None else None
            widget = self.add_widget(widget_class, placement, anchor=anchor)
            docks.append(self.dock_of(widget))

    def dock_of(self, widget) -> CDockWidget | None:
        """Return the dock that holds ``widget``."""
        if widget is None or not isinstance(widget, QWidget):
            return None
        for dock in self.area.dock_list():
            if dock.widget() is widget:
                return dock
        return None

    # ------------------------------------------------------------------ empty state
    def _on_dock_added(self, dock: CDockWidget) -> None:
        self._last_dock = dock
        self.refresh_empty_state()

    def _on_focus_changed(self, _old, new) -> None:
        if new is not None and isValid(new):
            self._last_dock = new

    def refresh_empty_state(self) -> None:
        """Show the empty state when no widget is left in the dock area."""
        if not isValid(self.empty_state):
            return
        empty = not any(not d.isClosed() for d in self.area.dock_list())
        if empty:
            self.empty_state.setGeometry(self.area.dock_manager.geometry())
            self.empty_state.show()
            self.empty_state.raise_()
            if self.undo_bar.isVisible():
                self.undo_bar.raise_()
        else:
            self.empty_state.hide()

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        """Keep the empty state over the dock manager when it moves or resizes."""
        if watched is self.area.dock_manager and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Move,
        ):
            if self.empty_state.isVisible():
                self.empty_state.setGeometry(self.area.dock_manager.geometry())
        return super().eventFilter(watched, event)

    # ------------------------------------------------------------------ theme / teardown
    def refresh_theme(self) -> None:
        """Re-apply theme colours to the chrome."""
        apply_dock_chrome_style(self.area.dock_manager, True)
        self.undo_bar.refresh_theme()
        self.empty_state.refresh_theme()
        if self.gallery is not None:
            self.gallery.refresh_theme()

    def cleanup(self) -> None:
        """Delete pending docks and unload QML scenes."""
        self.flush()
        for view in (self.gallery, self.empty_state):
            if view is not None and hasattr(view, "cleanup"):
                view.cleanup()
        if self.gallery is not None:
            self.gallery.close()
            self.gallery.deleteLater()
            self.gallery = None
