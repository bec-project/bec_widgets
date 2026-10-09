"""QML rendering of the main app's navigation panel; see :mod:`.nav_common`."""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Property, QObject, QPoint, QRect, Qt, Signal, Slot
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QToolTip, QWidget

from bec_widgets.applications.navigation_centre.nav_common import (
    HEADER_HEIGHT,
    ITEM_HEIGHT,
    SECTION_HEIGHT,
    SEPARATOR_HEIGHT,
    NavEntry,
    NavPanelBase,
)
from bec_widgets.utils.quick.host import ThemeTokens, create_quick_widget, release_quick_widget

QML_FILE = Path(__file__).parent / "qml" / "NavPanelView.qml"
_HEIGHTS = {"section": SECTION_HEIGHT, "separator": SEPARATOR_HEIGHT}


def _row(entry: NavEntry) -> dict:
    return {
        "id": entry.id,
        "kind": entry.kind,
        "title": entry.title,
        "miniText": entry.mini_text,
        "icon": entry.icon,
        "subtitle": entry.subtitle,
        "shortcut": entry.shortcut,
        "focusable": entry.focusable,
        "height": _HEIGHTS.get(entry.kind, ITEM_HEIGHT),
    }


class NavQmlBackend(QObject):
    """State of :class:`NavPanelQml` exposed to ``NavPanelView.qml``."""

    entriesChanged = Signal()
    stateChanged = Signal()
    progressChanged = Signal()
    focusRequested = Signal(str)

    def __init__(self, panel: "NavPanelQml"):
        super().__init__(panel)
        self.panel = panel
        self._top: list[dict] = []
        self._bottom: list[dict] = []
        self._keyboard_focus = False

    def refresh_entries(self) -> None:
        """Rebuild the row lists from the panel entries."""
        self._top = [_row(e) for e in self.panel.ordered_entries() if e.group == "top"]
        self._bottom = [_row(e) for e in self.panel.ordered_entries() if e.group == "bottom"]
        self.entriesChanged.emit()

    # pylint: disable=missing-function-docstring,invalid-name
    def _active_ids(self) -> list[str]:
        return [e.id for e in self.panel.entries if e.active and e.kind == "item"]

    def set_keyboard_focus(self, value: bool) -> None:
        """Show focus rings (keyboard navigation) or hide them (mouse use)."""
        if value != self._keyboard_focus:
            self._keyboard_focus = value
            self.stateChanged.emit()

    def _get_top(self) -> list[dict]:
        return self._top

    def _get_bottom(self) -> list[dict]:
        return self._bottom

    def _get_keyboard_focus(self) -> bool:
        return self._keyboard_focus

    topEntries = Property("QVariantList", _get_top, notify=entriesChanged)
    bottomEntries = Property("QVariantList", _get_bottom, notify=entriesChanged)
    activeIds = Property("QStringList", _active_ids, notify=stateChanged)
    pinned = Property(bool, lambda self: self.panel.pinned, notify=stateChanged)
    opened = Property(bool, lambda self: self.panel.is_expanded, notify=stateChanged)
    keyboardFocus = Property(bool, _get_keyboard_focus, notify=stateChanged)
    toggleTooltip = Property(str, lambda self: self.panel.toggle_tooltip(), notify=stateChanged)
    progress = Property(float, lambda self: self.panel.progress, notify=progressChanged)
    title = Property(str, lambda self: self.panel.title, constant=True)
    railWidth = Property(int, lambda self: self.panel.rail_width, constant=True)
    drawerWidth = Property(int, lambda self: self.panel.drawer_width, constant=True)
    headerHeight = Property(int, lambda self: HEADER_HEIGHT, constant=True)
    pinAvailable = Property(bool, lambda self: not self.panel.push_mode, constant=True)

    @Slot(str)
    def activate(self, entry_id: str) -> None:
        self.panel.activate_from_user(entry_id)

    @Slot(str)
    def activateFromMouse(self, entry_id: str) -> None:
        self.set_keyboard_focus(False)
        self.panel.activate_from_user(entry_id)

    @Slot()
    def toggleExpanded(self) -> None:
        self.set_keyboard_focus(False)
        self.panel.toggle_expanded()

    @Slot(bool)
    def setPinned(self, pinned: bool) -> None:
        self.panel.set_pinned(pinned)

    @Slot()
    def escape(self) -> None:
        self.panel.handle_escape()

    @Slot()
    def expand(self) -> None:
        self.panel.set_expanded(True)

    @Slot()
    def collapse(self) -> None:
        if not self.panel.pinned:
            self.panel.set_expanded(False, restore_focus=False)

    @Slot(str, int, result=str)
    def moveFocus(self, entry_id: str, step: int) -> str:
        self.set_keyboard_focus(True)
        return self.panel.move_focus(entry_id or None, step) or ""

    @Slot(str, float, float)
    def showTooltip(self, entry_id: str, x: float, y: float) -> None:
        entry = self.panel.components.get(entry_id)
        if not isinstance(entry, NavEntry) or self.panel.progress >= 0.5:
            return
        pos = self.panel.surface.mapToGlobal(QPoint(int(x), int(y)))
        QToolTip.showText(pos, self.panel.tooltip_for(entry), self.panel.surface)

    @Slot(str, float, float)
    def showText(self, text: str, x: float, y: float) -> None:
        pos = self.panel.surface.mapToGlobal(QPoint(int(x), int(y)))
        QToolTip.showText(pos, text, self.panel.surface)

    @Slot()
    def hideTooltip(self) -> None:
        QToolTip.hideText()


class NavPanelQml(NavPanelBase):
    """Navigation panel of the main app rendered with Qt Quick."""

    def __init__(self, parent: QWidget | None = None, **kwargs):
        self.backend: NavQmlBackend | None = None
        self.view: QQuickWidget | None = None
        super().__init__(parent=parent, **kwargs)
        self.backend.refresh_entries()

    def _create_surface(self) -> QWidget:
        self.backend = NavQmlBackend(self)
        self.view = create_quick_widget(self, QML_FILE, {"backend": self.backend})
        self.view.setObjectName("NavPanelSurface")
        self.view.setClearColor(ThemeTokens().card)
        self.view.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        return self.view

    def _surface_entries_changed(self) -> None:
        if self.backend is not None:
            self.backend.refresh_entries()

    def _surface_state_changed(self) -> None:
        if self.backend is not None:
            self.backend.stateChanged.emit()

    def _surface_progress(self, progress: float) -> None:
        self.backend.progressChanged.emit()

    def _surface_theme_changed(self) -> None:
        self.view.setClearColor(ThemeTokens().card)

    def focus_row(self, entry_id: str | None) -> None:
        entry_id = entry_id or self.move_focus(None, 1)
        if not entry_id:
            return
        self.backend.set_keyboard_focus(True)
        self.view.setFocus(Qt.FocusReason.TabFocusReason)
        self.backend.focusRequested.emit(entry_id)

    def row_rect(self, entry_id: str) -> QRect | None:
        """Geometry of the row ``entry_id`` in surface coordinates (rows have fixed heights)."""
        width = self.surface_width()
        y = HEADER_HEIGHT
        for entry in [e for e in self.ordered_entries() if e.group == "top"]:
            height = _HEIGHTS.get(entry.kind, ITEM_HEIGHT)
            if entry.id == entry_id:
                return QRect(0, y, width, height)
            y += height
        bottom = [e for e in self.ordered_entries() if e.group == "bottom"]
        y = self.surface.height() - 6 - sum(_HEIGHTS.get(e.kind, ITEM_HEIGHT) for e in bottom)
        for entry in bottom:
            height = _HEIGHTS.get(entry.kind, ITEM_HEIGHT)
            if entry.id == entry_id:
                return QRect(0, y, width, height)
            y += height
        return None

    def tour_target(self, entry_id: str):
        def target():
            if entry_id == "toggle":
                rect = QRect(8, (HEADER_HEIGHT - 40) // 2, 40, 40)
            else:
                rect = self.row_rect(entry_id) or QRect(QPoint(0, 0), self.surface.size())
            window = self.window()
            top_left = self.surface.mapTo(window, rect.topLeft())
            return QRect(top_left, rect.size()), None

        return target

    def cleanup(self) -> None:
        super().cleanup()
        release_quick_widget(self.view)
