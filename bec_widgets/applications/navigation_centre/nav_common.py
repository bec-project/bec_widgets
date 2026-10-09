"""Shared model and behaviour of the main app's navigation panel.

The panel has two states that use the same geometry:

* the **rail** (56 px): one row per view with an icon and a short label below it,
* the **drawer** (256 px): the same rows with the full title, a subtitle and the shortcut.

The drawer either **pushes** the views (default, ``BEC_NAV_DRAWER=push``) or **floats** over
them (``BEC_NAV_DRAWER=float``; a pin docks it). In both modes the surface animates above the
views and the layout changes once, at the end of opening or the start of closing, so the views
never reflow frame by frame. Rows keep their height and their icon position in both states, so
nothing jumps while the surface widens; labels only fade.

:class:`NavPanelBase` holds the entries, the state machine (open, pinned, animation), the
keyboard shortcuts and the public API that :class:`~bec_widgets.applications.main_app.BECMainApp`
and the legacy ``SideBar`` share. The QWidget and QML versions only render it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable

from qtpy.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QRect,
    QSettings,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from qtpy.QtGui import QColor, QKeySequence, QPainter, QShortcut
from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets import SafeSlot

RAIL_WIDTH = 56
DRAWER_WIDTH = 256
NAV_ANIMATION_DURATION = 180  # ms
TOGGLE_SHORTCUT = "Ctrl+B"
SETTINGS_KEY = "navigation/pinned"
NAV_PANEL_ENV = "BEC_NAV_PANEL"
NAV_DRAWER_ENV = "BEC_NAV_DRAWER"

# Row heights shared by both versions so they line up pixel for pixel.
HEADER_HEIGHT = 52
ITEM_HEIGHT = 56
SECTION_HEIGHT = 28
SEPARATOR_HEIGHT = 13


@dataclass
class NavEntry:
    """One row of the navigation panel."""

    id: str
    kind: str  # "item", "action", "section" or "separator"
    title: str = ""
    mini_text: str = ""
    icon: str = ""
    subtitle: str = ""
    group: str = "top"  # "top" scrolls with the views, "bottom" stays at the bottom
    toggleable: bool = True
    exclusive: bool = True
    active: bool = False
    shortcut: str = ""
    callback: Callable[[], None] | None = field(default=None, repr=False)

    @property
    def focusable(self) -> bool:
        """Whether keyboard focus can land on this row."""
        return self.kind in ("item", "action")

    @property
    def is_view(self) -> bool:
        """Whether the row selects a view (and therefore gets a Ctrl+<n> shortcut)."""
        return self.kind == "item" and self.toggleable and self.exclusive

    # legacy NavigationItem compatibility, used by the command palette
    @property
    def _icon_name(self) -> str:
        return self.icon

    def is_active(self) -> bool:
        """Return whether the row is the selected one."""
        return self.active


def nav_panel_flavour() -> str:
    """Return the navigation panel chosen with ``BEC_NAV_PANEL`` (qwidget, qml or legacy)."""
    flavour = os.environ.get(NAV_PANEL_ENV, "qwidget").strip().lower()
    return flavour if flavour in ("qwidget", "qml", "legacy") else "qwidget"


def create_side_bar(parent: QWidget | None = None, anim_duration: int | None = None, **kwargs):
    """
    Create the navigation panel of the main app.

    ``BEC_NAV_PANEL=qwidget`` (default) and ``BEC_NAV_PANEL=qml`` select the redesigned panel,
    ``BEC_NAV_PANEL=legacy`` the original expanding side bar.

    Args:
        parent(QWidget | None): Parent widget.
        anim_duration(int | None): Animation duration in ms; ``None`` keeps the panel's default.
        **kwargs: Passed to the panel.

    Returns:
        The panel widget.
    """
    # pylint: disable=import-outside-toplevel
    flavour = nav_panel_flavour()
    if anim_duration is not None:
        kwargs["anim_duration"] = anim_duration
    if flavour == "legacy":
        from bec_widgets.applications.navigation_centre.side_bar import SideBar

        kwargs.pop("remember_state", None)
        return SideBar(parent=parent, **kwargs)
    if flavour == "qml":
        from bec_widgets.applications.navigation_centre.nav_panel_qml import NavPanelQml

        return NavPanelQml(parent=parent, **kwargs)
    from bec_widgets.applications.navigation_centre.nav_panel_qwidget import NavPanelQWidget

    return NavPanelQWidget(parent=parent, **kwargs)


class _ToggleProxy(QObject):
    """Stand-in for the legacy ``SideBar.toggle`` button where the button lives in QML."""

    clicked = Signal()

    def click(self):
        """Toggle the drawer, like clicking the menu button."""
        self.clicked.emit()


class _Scrim(QWidget):
    """Dims the views behind the floating drawer; a click on it closes the drawer."""

    def __init__(self, panel: "NavPanelBase"):
        super().__init__(panel)
        self.panel = panel
        self.setObjectName("NavPanelScrim")
        self.hide()

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        event.accept()
        self.panel.set_expanded(False, restore_focus=False)

    def wheelEvent(self, event):  # pylint: disable=invalid-name
        event.accept()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, int(40 * self.panel.progress)))


class NavPanelBase(QWidget):
    """
    Navigation panel of the main app: the slot in the layout plus the floating surface.

    Subclasses implement the ``_surface_*`` hooks and ``_create_surface``.

    Signals:
        view_selected(str): A row was activated; carries its id.
        toggled(bool): The drawer opened (True) or closed (False).
        pinned_changed(bool): The drawer was pinned open or released.
    """

    view_selected = Signal(str)
    toggled = Signal(bool)
    pinned_changed = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "Navigation",
        collapsed_width: int = RAIL_WIDTH,
        expanded_width: int = DRAWER_WIDTH,
        anim_duration: int = NAV_ANIMATION_DURATION,
        *,
        remember_state: bool = False,
        install_shortcuts: bool = True,
        drawer_mode: str | None = None,
    ):
        super().__init__(parent=parent)
        self.setObjectName("NavPanel")
        self._title = title
        self._rail_width = collapsed_width
        self._drawer_width = expanded_width
        self._remember_state = remember_state
        self._install_shortcuts = install_shortcuts
        mode = (drawer_mode or os.environ.get(NAV_DRAWER_ENV, "push")).strip().lower()
        self._push_mode = mode != "float"

        self.entries: list[NavEntry] = []
        self.components: dict[str, NavEntry | QWidget] = {}
        self._active_id: str | None = None
        self._open = False
        self._pinned = False
        self._progress = 0.0
        self._restore_focus: QWidget | None = None
        self._shortcuts: list[QShortcut] = []
        self._shortcut_window: QWidget | None = None
        self._scrim = _Scrim(self)
        self._theme_entries: set[str] = set()

        self.toggle = _ToggleProxy(self)
        self.toggle.clicked.connect(self.on_expand)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(max(0, int(anim_duration)))
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_value)
        self._anim.finished.connect(self._on_anim_finished)

        self.setFixedWidth(self._rail_width)
        self.surface: QWidget = self._create_surface()
        self.surface.setParent(self)
        self._surface_host: QWidget | None = None

        app = QApplication.instance()
        if app is not None and hasattr(app, "theme") and hasattr(app.theme, "theme_changed"):
            app.theme.theme_changed.connect(self._on_theme_changed)

        if self._remember_state and self._settings().value(SETTINGS_KEY, False, type=bool):
            self.set_pinned(True)

    # ------------------------------------------------------------------ subclass hooks
    def _create_surface(self) -> QWidget:  # pragma: no cover - abstract
        raise NotImplementedError

    def _surface_entries_changed(self) -> None:
        """The list of entries, their titles or their shortcuts changed."""

    def _surface_state_changed(self) -> None:
        """Active row, pinned or open state changed."""

    def _surface_progress(self, progress: float) -> None:
        """The drawer is ``progress`` (0 rail .. 1 drawer) open."""

    def _surface_theme_changed(self) -> None:
        """The application theme changed."""

    def focus_row(self, entry_id: str | None) -> None:
        """Move keyboard focus onto the row ``entry_id`` (or the first row)."""

    def _surface_has_focus(self) -> bool:
        return self.surface.isAncestorOf(QApplication.focusWidget()) or self.surface.hasFocus()

    def tour_target(self, entry_id: str):
        """Return what the guided tour should highlight for ``entry_id`` (or ``"toggle"``)."""
        del entry_id
        return self.surface

    # ------------------------------------------------------------------ entries
    def add_section(  # pylint: disable=redefined-builtin
        self, title: str, id: str, position: int | None = None
    ) -> NavEntry:
        """
        Add a section header. In the rail it shows as a divider, in the drawer as a heading.

        Args:
            title(str): Section title.
            id(str): Unique id.
            position(int, optional): Index among the top rows; appended when omitted.

        Returns:
            NavEntry: The created entry.
        """
        return self._add_entry(NavEntry(id=id, kind="section", title=title), position)

    def add_separator(self, *, from_top: bool = True, position: int | None = None) -> NavEntry:
        """
        Add a divider line.

        Args:
            from_top(bool): Add to the top rows (True) or the bottom rows (False).
            position(int, optional): Index within the group; appended when omitted.

        Returns:
            NavEntry: The created entry.
        """
        sep_id = f"separator_{sum(1 for e in self.entries if e.kind == 'separator')}"
        entry = NavEntry(id=sep_id, kind="separator", group="top" if from_top else "bottom")
        return self._add_entry(entry, position)

    def add_item(  # pylint: disable=redefined-builtin
        self,
        icon: str,
        title: str,
        id: str,
        mini_text: str | None = None,
        position: int | None = None,
        *,
        from_top: bool = True,
        toggleable: bool = True,
        exclusive: bool = True,
        subtitle: str | None = None,
    ) -> NavEntry:
        """
        Add a navigation row.

        Args:
            icon(str): Material icon name.
            title(str): Full title shown in the drawer and the tooltip.
            id(str): Unique id, emitted with ``view_selected``.
            mini_text(str, optional): Short label under the icon in the rail; defaults to title.
            position(int, optional): Index within the group; appended when omitted.
            from_top(bool): Add to the top rows (True) or the bottom rows (False).
            toggleable(bool): Whether the row stays selected (a view) or acts once (an action).
            exclusive(bool): Whether selecting the row deselects the other exclusive rows.
            subtitle(str, optional): One-line description shown in the drawer.

        Returns:
            NavEntry: The created entry.
        """
        entry = NavEntry(
            id=id,
            kind="item" if toggleable else "action",
            title=title,
            mini_text=mini_text or title,
            icon=icon,
            subtitle=subtitle or "",
            group="top" if from_top else "bottom",
            toggleable=toggleable,
            exclusive=exclusive,
        )
        return self._add_entry(entry, position)

    def add_dark_mode_item(  # pylint: disable=redefined-builtin
        self, id: str = "dark_mode", position: int | None = None
    ) -> NavEntry:
        """
        Add the bottom row that switches between the light and the dark theme.

        Args:
            id(str): Unique id.
            position(int, optional): Index within the bottom rows; appended when omitted.

        Returns:
            NavEntry: The created entry.
        """
        entry = NavEntry(
            id=id,
            kind="action",
            group="bottom",
            toggleable=False,
            exclusive=False,
            callback=self._toggle_theme,
        )
        self._sync_theme_entry(entry)
        self._theme_entries.add(id)
        return self._add_entry(entry, position)

    def _add_entry(self, entry: NavEntry, position: int | None) -> NavEntry:
        if entry.id in self.components:
            self.remove_entry(entry.id)
        group = [e for e in self.entries if e.group == entry.group]
        if position is None or position >= len(group):
            anchor = group[-1] if group else None
            index = (self.entries.index(anchor) + 1) if anchor else len(self.entries)
            if anchor is None and entry.group == "top":
                index = 0
        else:
            index = self.entries.index(group[max(0, position)])
        self.entries.insert(index, entry)
        self.components[entry.id] = entry
        self._renumber_shortcuts()
        self._surface_entries_changed()
        return entry

    def remove_entry(self, entry_id: str) -> None:
        """Remove the row ``entry_id``."""
        entry = self.components.pop(entry_id, None)
        if entry is None:
            return
        self.entries.remove(entry)
        if self._active_id == entry_id:
            self._active_id = None
        self._renumber_shortcuts()
        self._surface_entries_changed()

    def ordered_entries(self) -> list[NavEntry]:
        """Entries in display order: the top group, then the bottom group."""
        return [e for e in self.entries if e.group == "top"] + [
            e for e in self.entries if e.group == "bottom"
        ]

    def view_entries(self) -> list[NavEntry]:
        """Rows that select a view, in display order; the first nine get Ctrl+1..9."""
        return [e for e in self.ordered_entries() if e.is_view]

    def _renumber_shortcuts(self) -> None:
        for entry in self.entries:
            entry.shortcut = ""
        for number, entry in enumerate(self.view_entries()[:9], start=1):
            entry.shortcut = QKeySequence(f"Ctrl+{number}").toString(
                QKeySequence.SequenceFormat.NativeText
            )
        self._sync_shortcuts()

    # ------------------------------------------------------------------ activation
    def activate_item(self, target_id: str, *, emit_signal: bool = True):
        """
        Select the row ``target_id`` like a click would.

        Args:
            target_id(str): Row id.
            emit_signal(bool): Emit ``view_selected`` (False only restores the highlight).
        """
        target = self.components.get(target_id)
        if not isinstance(target, NavEntry) or not target.focusable:
            return
        if target.callback is not None and emit_signal:
            target.callback()
        if not target.toggleable:
            if emit_signal:
                self.view_selected.emit(target_id)
            return
        if target.exclusive:
            for entry in self.entries:
                if entry.kind == "item" and entry.exclusive:
                    entry.active = entry is target
        else:
            target.active = not target.active
        self._active_id = target_id
        self._surface_state_changed()
        if emit_signal:
            self.view_selected.emit(target_id)

    def activate_from_user(self, target_id: str) -> None:
        """Activate a row on a click or a key press; closes the floating drawer after a view."""
        target = self.components.get(target_id)
        self.activate_item(target_id)
        if (
            isinstance(target, NavEntry)
            and target.kind == "item"
            and self._open
            and not self._pinned
        ):
            self.set_expanded(False, restore_focus=False)

    @property
    def active_id(self) -> str | None:
        """Id of the selected view row."""
        for entry in self.entries:
            if entry.kind == "item" and entry.exclusive and entry.active:
                return entry.id
        return None

    # ------------------------------------------------------------------ open / pin state
    def _get_is_expanded(self) -> bool:
        return self._open

    # a plain Qt property: readable from Python (a SafeProperty is not) and from Qt
    is_expanded = Property(bool, _get_is_expanded, notify=toggled)

    @property
    def progress(self) -> float:
        """How far the drawer is open, 0 (rail) to 1 (drawer)."""
        return self._progress

    @property
    def pinned(self) -> bool:
        """Whether the drawer is docked open next to the views."""
        return self._pinned

    @property
    def push_mode(self) -> bool:
        """Whether the open drawer pushes the views (True) or floats over them (False)."""
        return self._push_mode

    @property
    def rail_width(self) -> int:
        """Width of the collapsed rail."""
        return self._rail_width

    @property
    def drawer_width(self) -> int:
        """Width of the open drawer."""
        return self._drawer_width

    @property
    def title(self) -> str:
        """Heading of the open drawer."""
        return self._title

    @SafeSlot()
    @SafeSlot(bool)
    def on_expand(self, *_args):
        """Toggle the drawer (legacy name of :meth:`toggle_expanded`)."""
        self.toggle_expanded()

    @SafeSlot()
    def toggle_expanded(self):
        """Open the drawer when it is closed, close it otherwise."""
        self.set_expanded(not self._open)

    def set_expanded(self, expanded: bool, *, restore_focus: bool = True) -> None:
        """
        Open or close the drawer.

        Args:
            expanded(bool): True opens the drawer.
            restore_focus(bool): When closing, give focus back to where it was before.
        """
        expanded = bool(expanded)
        if expanded == self._open:
            return
        if self._push_mode:
            # in push mode the open drawer is always docked next to the views
            if expanded:
                self._remember_focus()
                self.set_pinned(True)
            else:
                self._close_focus(restore_focus)
                self.set_pinned(False)
            return
        if not expanded and self._pinned:
            self.set_pinned(False, collapse=False)
        self._open = expanded
        if expanded:
            self._remember_focus()
        else:
            self._close_focus(restore_focus)
        self._animate_to(1.0 if expanded else 0.0)
        self._surface_state_changed()
        self.toggled.emit(expanded)

    def _remember_focus(self) -> None:
        focus = QApplication.focusWidget()
        if focus is not None and not self.surface.isAncestorOf(focus):
            self._restore_focus = focus

    def _close_focus(self, restore_focus: bool) -> None:
        if restore_focus and self._surface_has_focus() and self._restore_focus is not None:
            try:
                self._restore_focus.setFocus(Qt.FocusReason.OtherFocusReason)
            except RuntimeError:
                pass
        self._restore_focus = None

    def set_pinned(self, pinned: bool, *, collapse: bool = True) -> None:
        """
        Dock the drawer open next to the views (True) or let it float and close again (False).

        Args:
            pinned(bool): Pin state.
            collapse(bool): When unpinning, also close the drawer.
        """
        pinned = bool(pinned)
        if pinned == self._pinned:
            return
        self._pinned = pinned
        if self._remember_state:
            self._settings().setValue(SETTINGS_KEY, pinned)
        if pinned:
            # the views make room once the drawer is fully open (see _on_anim_finished)
            if self._open and self._progress >= 1.0:
                self.setFixedWidth(self._drawer_width)
            if not self._open:
                self._open = True
                self._animate_to(1.0)
                self.toggled.emit(True)
        else:
            # the views take the space back at once; the drawer then shrinks over them
            self.setFixedWidth(self._rail_width)
            if self._open and (collapse or self._push_mode):
                self._open = False
                self._animate_to(0.0)
                self.toggled.emit(False)
        self._place_surface()
        self._surface_state_changed()
        self.pinned_changed.emit(pinned)

    @SafeSlot()
    def toggle_pinned(self):
        """Pin the drawer open, or release it."""
        self.set_pinned(not self._pinned)

    def _animate_to(self, target: float) -> None:
        self._anim.stop()
        if self._anim.duration() <= 0 or not self.isVisible():
            self._on_anim_value(target)
            self._on_anim_finished()
            return
        self._anim.setStartValue(float(self._progress))
        self._anim.setEndValue(float(target))
        self._anim.start()

    def _on_anim_value(self, value) -> None:
        self._progress = float(value)
        self._place_surface()
        self._surface_progress(self._progress)

    def _on_anim_finished(self) -> None:
        if self._pinned and self._open and self._progress >= 1.0:
            self.setFixedWidth(self._drawer_width)
        self._place_surface()
        self._surface_state_changed()

    # ------------------------------------------------------------------ floating surface
    def surface_width(self) -> int:
        """Current width of the floating surface."""
        span = self._drawer_width - self._rail_width
        return int(round(self._rail_width + span * self._progress))

    def _place_surface(self) -> None:
        host = self.parentWidget()
        if host is not None and self.surface.parentWidget() is not host:
            self.surface.setParent(host)
            self._scrim.setParent(host)
            self.surface.show()
            if self._surface_host is not None:
                self._surface_host.removeEventFilter(self)
            host.installEventFilter(self)
            self._surface_host = host
        top_left = self.pos() if host is not None else QPoint(0, 0)
        self.surface.setGeometry(
            QRect(top_left.x(), top_left.y(), self.surface_width(), self.height())
        )
        self.surface.setVisible(self.isVisible())
        floating = self.isVisible() and not self._pinned and self._progress > 0.0
        if host is not None and floating:
            self._scrim.setGeometry(host.rect())
            self._scrim.setVisible(True)
            self._scrim.raise_()
            self._scrim.update()
        else:
            self._scrim.setVisible(False)
        self.surface.raise_()

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        if watched is self._surface_host and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.ChildAdded,
        ):
            QTimer.singleShot(0, self._safe_place)
        return super().eventFilter(watched, event)

    def _safe_place(self):
        try:
            self._place_surface()
        except RuntimeError:
            pass

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._place_surface()

    def moveEvent(self, event):  # pylint: disable=invalid-name
        super().moveEvent(event)
        self._place_surface()

    def showEvent(self, event):  # pylint: disable=invalid-name
        super().showEvent(event)
        self._place_surface()
        self._sync_shortcuts()

    def hideEvent(self, event):  # pylint: disable=invalid-name
        super().hideEvent(event)
        self.surface.setVisible(False)
        self._scrim.setVisible(False)

    # ------------------------------------------------------------------ keyboard
    def _sync_shortcuts(self) -> None:
        if not self._install_shortcuts:
            return
        window = self.window()
        if window is self or window is None:
            return
        if self._shortcut_window is not window:
            for shortcut in self._shortcuts:
                shortcut.setEnabled(False)
                shortcut.deleteLater()
            self._shortcuts = []
            self._shortcut_window = window
            toggle = QShortcut(QKeySequence(TOGGLE_SHORTCUT), window)
            toggle.activated.connect(self._toggle_from_keyboard)
            self._shortcuts.append(toggle)
            for number in range(1, 10):
                shortcut = QShortcut(QKeySequence(f"Ctrl+{number}"), window)
                shortcut.activated.connect(lambda n=number: self._activate_number(n))
                self._shortcuts.append(shortcut)
        views = self.view_entries()
        for number, shortcut in enumerate(self._shortcuts[1:], start=1):
            shortcut.setEnabled(number <= len(views))

    def _toggle_from_keyboard(self):
        opening = not self._open
        self.toggle_expanded()
        if opening:
            self.focus_row(self.active_id)

    def _activate_number(self, number: int) -> None:
        views = self.view_entries()
        if 1 <= number <= len(views):
            self.activate_from_user(views[number - 1].id)

    def move_focus(self, current_id: str | None, step: int) -> str | None:
        """
        Return the id of the focusable row ``step`` rows away from ``current_id``.

        ``step`` of ``-10**6`` / ``10**6`` jumps to the first / last row.
        """
        rows = [e.id for e in self.ordered_entries() if e.focusable]
        if not rows:
            return None
        if current_id not in rows:
            return rows[0] if step > 0 else rows[-1]
        index = max(0, min(len(rows) - 1, rows.index(current_id) + step))
        return rows[index]

    def handle_escape(self) -> None:
        """Esc inside the panel: close the floating drawer, or hand focus back to the view."""
        if self._open and not self._pinned:
            self.set_expanded(False)
            return
        target = self._restore_focus
        if target is None:
            return
        try:
            target.setFocus(Qt.FocusReason.OtherFocusReason)
        except RuntimeError:
            pass

    def tooltip_for(self, entry: NavEntry) -> str:
        """Tooltip of a row in the rail."""
        parts = [entry.title]
        if entry.shortcut:
            parts.append(f"({entry.shortcut})")
        text = " ".join(parts)
        if entry.subtitle:
            text = f"{text}\n{entry.subtitle}"
        return text

    def toggle_tooltip(self) -> str:
        """Tooltip of the menu button."""
        key = QKeySequence(TOGGLE_SHORTCUT).toString(QKeySequence.SequenceFormat.NativeText)
        if self._pinned:
            return f"Collapse navigation ({key})"
        return f"{'Close' if self._open else 'Expand'} navigation ({key})"

    # ------------------------------------------------------------------ theme
    def _toggle_theme(self) -> None:
        # pylint: disable=import-outside-toplevel
        from bec_widgets.utils.colors import apply_theme

        apply_theme("light" if self._is_dark() else "dark")

    @staticmethod
    def _is_dark() -> bool:
        app = QApplication.instance()
        return getattr(getattr(app, "theme", None), "theme", "dark") == "dark"

    def _sync_theme_entry(self, entry: NavEntry) -> None:
        dark = self._is_dark()
        entry.title = "Light theme" if dark else "Dark theme"
        entry.mini_text = "Light" if dark else "Dark"
        entry.icon = "light_mode" if dark else "dark_mode"
        entry.subtitle = "Switch the colour theme"

    @SafeSlot(str)
    def _on_theme_changed(self, *_args) -> None:
        for entry in self.entries:
            if entry.id in self._theme_entries:
                self._sync_theme_entry(entry)
        self._surface_entries_changed()
        self._surface_theme_changed()

    @staticmethod
    def _settings() -> QSettings:
        return QSettings("bec", "bec_app")

    def cleanup(self) -> None:
        """Stop the animation and release the global event filter and shortcuts."""
        self._anim.stop()
        if self._surface_host is not None:
            try:
                self._surface_host.removeEventFilter(self)
            except RuntimeError:
                pass
        for shortcut in self._shortcuts:
            shortcut.setEnabled(False)
        self._shortcuts = []
