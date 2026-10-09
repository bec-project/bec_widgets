"""State, rules and actions shared by the QWidget and QML profile management windows.

The windows themselves only render what :class:`ProfileLibraryController` and
:func:`check_profile_name` hand them, so both versions behave the same. Everything that
touches profile files goes through :class:`ProfileActions`.

Two behaviours are still open decisions and live in :data:`POLICY` so either answer works:

- ``rename_keeps_old_profile``: renaming saves the layout under the new name and keeps the
  old profile in the library (current behaviour), or moves the old one to Recently deleted.
- ``one_tab_per_profile``: a profile can be open in only one workspace tab (current
  behaviour), or in several.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from bec_lib import bec_logger
from qtpy.QtCore import QDateTime, QObject, Qt, QTimeZone, Signal
from qtpy.QtGui import QPixmap

from bec_widgets.widgets.containers.dock_area.profile_utils import (
    baseline_profile_candidates,
    copy_profile,
    get_profile_info,
    has_saved_baseline,
    is_profile_read_only,
    list_profiles,
    list_trashed_profiles,
    load_baseline_profile_screenshot,
    load_profile_screenshot,
    open_runtime_settings,
    profile_origin,
    profile_origin_display,
    restore_runtime_from_baseline,
    restore_trashed_profile,
    set_profile_notes,
    set_quick_select,
    trash_profile,
)

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea

logger = bec_logger.logger

UI_ENV = "BEC_PROFILE_UI"
UiMode = Literal["legacy", "qwidget", "qml"]
NameMode = Literal["save", "rename", "duplicate"]
Tone = Literal["neutral", "info", "success", "warning", "error"]

INVALID_NAME_CHARS = '/\\:*?"<>|'
MAX_NAME_LENGTH = 64


def profile_ui_mode() -> UiMode:
    """Return which profile windows to use, from ``BEC_PROFILE_UI`` (default ``legacy``)."""
    mode = os.environ.get(UI_ENV, "legacy").strip().lower()
    return mode if mode in ("qwidget", "qml") else "legacy"


@dataclass
class ProfilePolicy:
    """Behaviour switches that are still open decisions; see the module docstring."""

    rename_keeps_old_profile: bool = True
    one_tab_per_profile: bool = True


POLICY = ProfilePolicy()


################################################################################
# Small formatting helpers
################################################################################


def relative_time(iso: str, now: QDateTime | None = None) -> str:
    """
    Format an ISO 8601 UTC timestamp as a short relative time such as ``"3 h ago"``.

    Args:
        iso(str): Timestamp like ``2026-10-09T12:00:00Z``.
        now(QDateTime | None): Reference time; defaults to the current UTC time.

    Returns:
        str: The relative time, or an empty string for an unreadable timestamp.
    """
    stamp = QDateTime.fromString(iso or "", Qt.DateFormat.ISODate)
    if not stamp.isValid():
        return ""
    now = now or QDateTime.currentDateTimeUtc()
    seconds = max(0, stamp.secsTo(now))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    days = seconds // 86400
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    return stamp.toLocalTime().toString("d MMM yyyy")


def absolute_time(iso: str) -> str:
    """Format an ISO 8601 UTC timestamp in local time, e.g. ``"9 Oct 2026, 14:02"``."""
    stamp = QDateTime.fromString(iso or "", Qt.DateFormat.ISODate)
    if not stamp.isValid():
        return ""
    return stamp.toLocalTime().toString("d MMM yyyy, HH:mm")


def widget_count_label(count: int) -> str:
    """Return ``"1 widget"`` or ``"N widgets"``."""
    return "1 widget" if count == 1 else f"{count} widgets"


def unique_name(base: str, taken, suffix: str = "copy") -> str:
    """
    Return ``base_<suffix>``, ``base_<suffix>_2``, ... whichever is free first.

    Args:
        base(str): Name to start from.
        taken(Callable[[str], bool]): Returns True when a name is in use.
        suffix(str): Word appended to the name.
    """
    base = (base or "profile").strip() or "profile"
    candidate = f"{base}_{suffix}"
    counter = 2
    while taken(candidate):
        candidate = f"{base}_{suffix}_{counter}"
        counter += 1
    return candidate


################################################################################
# Name validation
################################################################################


@dataclass
class NameCheck:
    """Result of :func:`check_profile_name`, rendered under the name field.

    Attributes:
        ok: Whether the confirm button is enabled.
        tone: Colour of the hint line.
        message: The hint line.
        action: Label of the confirm button.
        suggestion: A free name the user can pick with one click, if any.
        replaces: Whether confirming replaces an existing user profile.
    """

    ok: bool
    tone: Tone
    message: str
    action: str
    suggestion: str = ""
    replaces: bool = False

    def as_dict(self) -> dict:
        """Return the check as a plain dictionary for QML."""
        return {
            "ok": self.ok,
            "tone": self.tone,
            "message": self.message,
            "action": self.action,
            "suggestion": self.suggestion,
            "replaces": self.replaces,
        }


_ACTION_LABELS = {"save": "Save", "rename": "Rename", "duplicate": "Duplicate"}


def check_profile_name(
    text: str,
    mode: NameMode,
    *,
    namespace: str | None,
    original: str | None = None,
    current: str | None = None,
    open_elsewhere=None,
) -> NameCheck:
    """
    Validate a profile name while the user types it.

    Args:
        text(str): The name as typed.
        mode(NameMode): ``save`` (save the current layout), ``rename`` or ``duplicate``.
        namespace(str | None): Profile namespace.
        original(str | None): The profile being renamed or duplicated.
        current(str | None): The profile shown in the dock area the request comes from.
        open_elsewhere(Callable[[str], bool] | None): Whether a profile is open in another tab.

    Returns:
        NameCheck: What to show and whether the name can be used.
    """
    name = (text or "").strip()
    action = _ACTION_LABELS[mode]

    def taken(candidate: str) -> bool:
        return profile_origin(candidate, namespace) != "unknown"

    if not name:
        return NameCheck(False, "neutral", "Enter a name for the profile.", action)
    bad = sorted({c for c in name if c in INVALID_NAME_CHARS})
    if bad or name.startswith("."):
        shown = " ".join(bad) if bad else "a leading dot"
        return NameCheck(False, "error", f"Names cannot contain {shown}.", action)
    if len(name) > MAX_NAME_LENGTH:
        return NameCheck(
            False, "error", f"Use at most {MAX_NAME_LENGTH} characters ({len(name)} now).", action
        )
    if mode == "rename" and original and name == original:
        return NameCheck(False, "neutral", "This is the current name.", action)

    origin = profile_origin(name, namespace)
    if origin in ("module", "plugin"):
        provider = profile_origin_display(name, namespace) or "BEC"
        return NameCheck(
            False,
            "error",
            f"'{name}' is a read-only profile from {provider}. Pick another name.",
            action,
            suggestion=unique_name(name, taken, "custom"),
        )
    if (
        POLICY.one_tab_per_profile
        and open_elsewhere is not None
        and name != current
        and name != original
        and open_elsewhere(name)
    ):
        return NameCheck(
            False,
            "error",
            f"'{name}' is open in another tab. Close that tab or pick another name.",
            action,
            suggestion=unique_name(name, taken),
        )
    if mode == "save" and current and name == current:
        return NameCheck(True, "info", f"Updates the saved layout of '{name}'.", "Save")
    if origin == "settings":
        info = get_profile_info(name, namespace)
        edited = relative_time(info.modified)
        detail = f" (edited {edited})" if edited else ""
        return NameCheck(
            True,
            "warning",
            f"Replaces the saved profile '{name}'{detail}. "
            "The old version goes to Recently deleted.",
            "Replace",
            replaces=True,
        )
    hints = {
        "save": "Saves the current layout as a new profile.",
        "rename": "",
        "duplicate": f"Creates a copy of '{original}'." if original else "Creates a copy.",
    }
    if mode == "rename":
        if original and POLICY.rename_keeps_old_profile:
            hints["rename"] = f"Saves the layout as '{name}'. '{original}' stays in the library."
        elif original:
            hints["rename"] = (
                f"Renames '{original}' to '{name}'. The old name goes to Recently deleted."
            )
        else:
            hints["rename"] = f"Saves this workspace as '{name}'."
    return NameCheck(True, "neutral", hints[mode], action)


################################################################################
# Actions
################################################################################


class ProfileActions:
    """
    Profile operations used by the reworked windows, working on one dock area and, when the
    dock area lives in workspace tabs, on all tabs.

    Nothing is removed from disk: replaced and deleted profiles are moved to the profile
    trash (Recently deleted), from where they can be restored.

    Args:
        dock_area(BECDockArea): The dock area the windows were opened from.
    """

    def __init__(self, dock_area: BECDockArea):
        self._origin_dock_area = dock_area

    # -- context -----------------------------------------------------------------

    @property
    def host(self):
        """The :class:`WorkspaceTabs` hosting the dock area, or None."""
        return getattr(self._origin_dock_area, "workspace_host", None)

    @property
    def namespace(self) -> str | None:
        """Profile namespace."""
        return self._origin_dock_area.profile_namespace

    def dock_area(self) -> BECDockArea:
        """The dock area actions apply to: the current tab when hosted in tabs."""
        host = self.host
        if host is not None:
            current = host.current_dock_area()
            if current is not None:
                return current
        return self._origin_dock_area

    def current_profile(self) -> str | None:
        """Profile shown in :meth:`dock_area`."""
        return getattr(self.dock_area(), "_current_profile_name", None)

    def open_profiles(self) -> list[str]:
        """Profiles that are open in a tab (or in this dock area when not in tabs)."""
        host = self.host
        if host is not None:
            return [name for name in host.workspace_names() if name]
        current = self.current_profile()
        return [current] if current else []

    def open_elsewhere(self, name: str) -> bool:
        """Whether *name* is open in a tab other than the current one."""
        return name != self.current_profile() and name in self.open_profiles()

    def taken(self, name: str) -> bool:
        """Whether a profile with *name* exists."""
        return profile_origin(name, self.namespace) != "unknown"

    def check(self, text: str, mode: NameMode, original: str | None = None) -> NameCheck:
        """Validate *text* for *mode*; see :func:`check_profile_name`."""
        return check_profile_name(
            text,
            mode,
            namespace=self.namespace,
            original=original,
            current=self.current_profile(),
            open_elsewhere=self.open_elsewhere,
        )

    def _dock_area_showing(self, name: str):
        host = self.host
        if host is not None:
            for dock_area in host.dock_areas():
                if dock_area._current_profile_name == name:  # pylint: disable=protected-access
                    return dock_area
            return None
        dock_area = self._origin_dock_area
        shown = dock_area._current_profile_name  # pylint: disable=protected-access
        return dock_area if shown == name else None

    def _refresh_toolbars(self) -> None:
        host = self.host
        dock_areas = host.dock_areas() if host is not None else [self._origin_dock_area]
        for dock_area in dock_areas:
            dock_area._refresh_workspace_list()  # pylint: disable=protected-access

    def _flush(self, name: str) -> None:
        """Write the live layout of an open profile to its working copy."""
        dock_area = self._dock_area_showing(name)
        if dock_area is not None:
            settings = open_runtime_settings(name, namespace=self.namespace)
            dock_area._write_snapshot_to_settings(settings)  # pylint: disable=protected-access

    def _trash_for_replace(self, name: str) -> bool:
        if self.taken(name) and not is_profile_read_only(name, self.namespace):
            return trash_profile(name, self.namespace) is not None
        return False

    # -- operations --------------------------------------------------------------

    def save_current(
        self, name: str, *, notes: str | None = None, pinned: bool | None = None
    ) -> str:
        """
        Save the layout of :meth:`dock_area` under *name*.

        Returns:
            str: A one-line summary for the confirmation banner.
        """
        dock_area = self.dock_area()
        current = self.current_profile()
        replaced = name != current and self._trash_for_replace(name)
        dock_area.save_profile(name, show_dialog=False, quick_select=pinned)
        if notes is not None:
            set_profile_notes(name, notes, self.namespace)
        if replaced:
            return f"Saved '{name}'. The version it replaced is in Recently deleted."
        return f"Saved '{name}'."

    def open(self, name: str, *, new_tab: bool = True) -> None:
        """Open *name* in a new tab (switching to it when open) or in the current tab."""
        host = self.host
        if host is not None and (new_tab or self.open_elsewhere(name)):
            host.open_workspace(name)
            return
        self.dock_area().load_profile(name)

    def set_pinned(self, name: str, pinned: bool) -> None:
        """Show or hide *name* in the toolbar profile list."""
        set_quick_select(name, pinned, namespace=self.namespace)
        self._refresh_toolbars()

    def set_notes(self, name: str, notes: str) -> None:
        """Store the description of *name*."""
        set_profile_notes(name, notes, self.namespace)

    def duplicate(self, name: str, new_name: str) -> str:
        """Copy *name* to *new_name*; returns the banner text."""
        self._flush(name)
        replaced = self._trash_for_replace(new_name)
        copy_profile(name, new_name, self.namespace)
        suffix = " The version it replaced is in Recently deleted." if replaced else ""
        return f"Created '{new_name}' from '{name}'.{suffix}"

    def rename(self, name: str | None, new_name: str) -> str:
        """
        Rename *name* to *new_name* following :data:`POLICY`; *name* None names the
        unsaved workspace of the current tab. Returns the banner text.
        """
        if name is None:
            return self.save_current(new_name)
        replaced = self._trash_for_replace(new_name)
        dock_area = self._dock_area_showing(name)
        host = self.host
        if dock_area is not None and host is not None:
            index = host.find_workspace(name)
            host.rename_workspace(index, name=new_name, confirm=False)
        elif dock_area is not None:
            dock_area.save_profile(new_name, show_dialog=False)
        else:
            copy_profile(name, new_name, self.namespace)
        moved_old = False
        if not POLICY.rename_keeps_old_profile and not is_profile_read_only(name, self.namespace):
            moved_old = trash_profile(name, self.namespace) is not None
        self._refresh_toolbars()
        parts = [f"Renamed '{name}' to '{new_name}'."]
        if moved_old:
            parts.append(f"'{name}' is in Recently deleted.")
        elif POLICY.rename_keeps_old_profile:
            parts.append(f"'{name}' is still in the library.")
        if replaced:
            parts.append("The profile it replaced is in Recently deleted.")
        return " ".join(parts)

    def can_delete(self, name: str) -> tuple[bool, str]:
        """Whether *name* can be moved to Recently deleted, and why not."""
        if is_profile_read_only(name, self.namespace):
            return False, "Read-only profiles cannot be deleted. Duplicate it to make changes."
        if name in self.open_profiles():
            return False, "Open in a tab. Close the tab to delete the profile."
        return True, ""

    def delete(self, name: str):
        """Move *name* to Recently deleted; returns the trash entry or None."""
        ok, reason = self.can_delete(name)
        if not ok:
            raise ValueError(reason)
        entry = trash_profile(name, self.namespace)
        self._refresh_toolbars()
        return entry

    def restore(self, token: str) -> str:
        """Put a trashed profile back; returns its name."""
        name = restore_trashed_profile(token, self.namespace)
        self._refresh_toolbars()
        return name

    def can_revert(self, name: str) -> bool:
        """Whether *name* has a saved copy to revert to."""
        return has_saved_baseline(name, self.namespace)

    def revert(self, name: str) -> None:
        """Replace the working copy of *name* with its saved copy (and reload it if open)."""
        dock_area = self._dock_area_showing(name)
        if dock_area is not None:
            dock_area.restore_baseline_profile(name, show_dialog=False)
        else:
            restore_runtime_from_baseline(name, namespace=self.namespace)

    def name_form(self, mode: NameMode, original: str = "") -> dict:
        """Initial values of the name dialog: ``initial`` text, ``notes`` and ``pinned``."""
        if mode == "save":
            current = self.current_profile()
            info = get_profile_info(current, self.namespace) if current else None
            return {
                "initial": current or "",
                "notes": info.notes if info else "",
                "pinned": info.is_quick_select if info else True,
            }
        initial = unique_name(original, self.taken) if mode == "duplicate" else original
        return {"initial": initial, "notes": "", "pinned": True}

    def apply_name(
        self, mode: NameMode, original: str, name: str, notes: str = "", pinned: bool = True
    ) -> str:
        """Run a confirmed save, rename or duplicate; returns the banner text."""
        name = name.strip()
        if mode == "save":
            return self.save_current(name, notes=notes, pinned=pinned)
        if mode == "rename":
            return self.rename(original or None, name)
        return self.duplicate(original, name)

    def saved_at(self, name: str) -> str:
        """ISO timestamp of the saved copy of *name*, or an empty string."""
        for path in baseline_profile_candidates(name, self.namespace):
            if os.path.exists(path):
                stamp = QDateTime.fromSecsSinceEpoch(int(os.path.getmtime(path)), QTimeZone.utc())
                return stamp.toString("yyyy-MM-ddTHH:mm:ssZ")
        return ""

    # -- previews ----------------------------------------------------------------

    def live_preview(self, name: str | None = None) -> QPixmap | None:
        """Screenshot of the dock area showing *name* (the current one by default)."""
        dock_area = self.dock_area() if name is None else self._dock_area_showing(name)
        if dock_area is None or not dock_area.isVisible():
            return None
        pixmap = QPixmap()
        data = dock_area.screenshot_bytes()
        if not data or not pixmap.loadFromData(bytes(data)):
            return None
        return pixmap

    def preview(self, name: str) -> QPixmap | None:
        """Best preview of *name*: live when it is shown in the current tab, else stored."""
        if name == self.current_profile():
            live = self.live_preview()
            if live is not None:
                return live
        return load_profile_screenshot(name, namespace=self.namespace)

    def saved_preview(self, name: str) -> QPixmap | None:
        """Stored screenshot of the saved copy of *name*."""
        return load_baseline_profile_screenshot(name, namespace=self.namespace)


################################################################################
# Library state
################################################################################

SECTION_MINE = "My profiles"
SECTION_BUNDLED = "Read-only profiles"
SECTION_TRASH = "Recently deleted"

ROW_KEYS = [
    "key",
    "kind",
    "section",
    "name",
    "subtitle",
    "readOnly",
    "pinned",
    "isOpen",
    "isCurrent",
    "selected",
    "token",
]


@dataclass
class Banner:
    """A one-line confirmation shown at the top of the library, optionally with an action."""

    tone: Tone
    text: str
    action: str = ""
    action_id: str = ""

    def as_dict(self) -> dict:
        """Return the banner as a plain dictionary for QML."""
        return {"tone": self.tone, "text": self.text, "action": self.action, "id": self.action_id}


@dataclass
class LibraryState:
    """Everything the library views render."""

    rows: list[dict] = field(default_factory=list)
    selected: dict | None = None
    query: str = ""
    banner: Banner | None = None
    pending_delete: str = ""
    empty_text: str = ""
    has_tabs: bool = False
    total: int = 0


class ProfileLibraryController(QObject):
    """
    View state of the profile library: rows with sections, the selected profile, the search
    text, inline delete confirmation and the undo banner.

    Args:
        actions(ProfileActions): The profile operations.
        parent(QObject | None): Parent object.
    """

    changed = Signal()
    preview_changed = Signal()
    # Ask the view to show the name dialog: mode, original name
    name_requested = Signal(str, str)
    # Ask the view to confirm a revert: profile name
    revert_requested = Signal(str)

    def __init__(self, actions: ProfileActions, parent: QObject | None = None):
        super().__init__(parent)
        self.actions = actions
        self.state = LibraryState(has_tabs=actions.host is not None)
        self._selected_key = ""
        self._entries: dict[str, dict] = {}
        self.preview_revision = 0
        self.refresh(select=actions.current_profile())

    # -- building ----------------------------------------------------------------

    def refresh(self, select: str | None = None) -> None:
        """Re-read the profiles from disk and rebuild the rows."""
        namespace = self.actions.namespace
        open_names = set(self.actions.open_profiles())
        current = self.actions.current_profile()
        entries: dict[str, dict] = {}
        for name in list_profiles(namespace):
            info = get_profile_info(name, namespace)
            if name == current:
                info.widget_count = len(self.actions.dock_area().dock_list())
            edited = relative_time(info.modified)
            subtitle = [widget_count_label(info.widget_count)]
            if edited:
                subtitle.append(f"edited {edited}")
            entries[f"p:{name}"] = {
                "key": f"p:{name}",
                "kind": "bundled" if info.is_read_only else "user",
                "section": SECTION_BUNDLED if info.is_read_only else SECTION_MINE,
                "name": name,
                "subtitle": " · ".join(subtitle),
                "readOnly": info.is_read_only,
                "pinned": info.is_quick_select,
                "isOpen": name in open_names,
                "isCurrent": name == current,
                "token": "",
                "info": info,
            }
        for entry in list_trashed_profiles(namespace):
            deleted = relative_time(entry.deleted_at)
            entries[f"t:{entry.token}"] = {
                "key": f"t:{entry.token}",
                "kind": "trash",
                "section": SECTION_TRASH,
                "name": entry.name,
                "subtitle": f"deleted {deleted}" if deleted else "deleted",
                "readOnly": False,
                "pinned": False,
                "isOpen": False,
                "isCurrent": False,
                "token": entry.token,
                "info": entry,
            }
        self._entries = entries
        if select:
            self._selected_key = f"p:{select}"
        if self._selected_key not in entries:
            self._selected_key = next(
                (k for k, e in entries.items() if e["kind"] != "trash"), next(iter(entries), "")
            )
        self.preview_revision += 1
        self._rebuild()

    def _matches(self, entry: dict) -> bool:
        query = self.state.query.strip().lower()
        if not query:
            return True
        info = entry["info"]
        haystack = f"{entry['name']} {getattr(info, 'notes', '')}".lower()
        return all(part in haystack for part in query.split())

    def _rebuild(self) -> None:
        order = {SECTION_MINE: 0, SECTION_BUNDLED: 1, SECTION_TRASH: 2}
        visible = [e for e in self._entries.values() if self._matches(e)]
        visible.sort(key=lambda e: (order[e["section"]], e["name"].lower()))
        rows = []
        for entry in visible:
            row = {key: entry.get(key) for key in ROW_KEYS}
            row["selected"] = entry["key"] == self._selected_key
            rows.append(row)
        self.state.rows = rows
        self.state.total = sum(1 for e in self._entries.values() if e["kind"] != "trash")
        if not rows:
            self.state.empty_text = (
                f"No profile matches '{self.state.query.strip()}'."
                if self.state.query.strip()
                else "No saved profiles yet. Save the current layout to create one."
            )
        else:
            self.state.empty_text = ""
        self.state.selected = self._details(self._entries.get(self._selected_key))
        if self.state.pending_delete and (
            not self.state.selected or self.state.selected["name"] != self.state.pending_delete
        ):
            self.state.pending_delete = ""
        self.changed.emit()

    def _details(self, entry: dict | None) -> dict | None:
        if entry is None:
            return None
        if entry["kind"] == "trash":
            trashed = entry["info"]
            return {
                "key": entry["key"],
                "kind": "trash",
                "name": entry["name"],
                "token": entry["token"],
                "facts": [("Deleted", absolute_time(trashed.deleted_at))],
                "notes": "",
                "status": "In Recently deleted. Restore it to use it again.",
                "readOnly": False,
                "pinned": False,
                "isOpen": False,
                "isCurrent": False,
                "canRevert": False,
                "canDelete": False,
                "deleteReason": "",
                "source": "",
            }
        info = entry["info"]
        name = entry["name"]
        can_delete, reason = self.actions.can_delete(name)
        source = profile_origin_display(name, self.actions.namespace) or ""
        if entry["isCurrent"]:
            status = "Shown in this tab" if self.state.has_tabs else "Currently loaded"
        elif entry["isOpen"]:
            status = "Open in another tab"
        else:
            status = ""
        facts = [
            ("Widgets", str(info.widget_count)),
            ("Edited", absolute_time(info.modified)),
            ("Created", absolute_time(info.created)),
            ("Source", f"{source} (read-only)" if info.is_read_only else "Saved by you"),
        ]
        return {
            "key": entry["key"],
            "kind": entry["kind"],
            "name": name,
            "token": "",
            "facts": facts,
            "notes": info.notes,
            "status": status,
            "readOnly": info.is_read_only,
            "pinned": info.is_quick_select,
            "isOpen": entry["isOpen"],
            "isCurrent": entry["isCurrent"],
            "canRevert": self.actions.can_revert(name),
            "canDelete": can_delete,
            "deleteReason": reason,
            "source": source,
        }

    # -- view requests -----------------------------------------------------------

    def selected_name(self) -> str | None:
        """Name of the selected profile (None for nothing or a trashed one)."""
        selected = self.state.selected
        if not selected or selected["kind"] == "trash":
            return None
        return selected["name"]

    def preview_for_selected(self) -> QPixmap | None:
        """Preview of the selected profile."""
        name = self.selected_name()
        return self.actions.preview(name) if name else None

    def select(self, key: str) -> None:
        """Select the row with *key*."""
        if key in self._entries and key != self._selected_key:
            self._selected_key = key
            self.state.pending_delete = ""
            self.preview_revision += 1
            self._rebuild()
            self.preview_changed.emit()

    def move_selection(self, step: int) -> None:
        """Select the next (step > 0) or previous visible row."""
        keys = [row["key"] for row in self.state.rows]
        if not keys:
            return
        index = keys.index(self._selected_key) if self._selected_key in keys else -1
        self.select(keys[max(0, min(len(keys) - 1, index + step))])

    def set_query(self, query: str) -> None:
        """Filter the rows by name and description."""
        self.state.query = query
        self._rebuild()
        keys = [row["key"] for row in self.state.rows]
        if keys and self._selected_key not in keys:
            self.select(keys[0])

    def dismiss_banner(self) -> None:
        """Hide the banner."""
        self.state.banner = None
        self.changed.emit()

    def _done(self, text: str, select: str | None = None, **banner) -> None:
        self.state.banner = Banner(banner.pop("tone", "success"), text, **banner)
        self.refresh(select=select)
        self.preview_changed.emit()

    def _fail(self, exc: Exception) -> None:
        logger.warning(f"Profile library: {exc}")
        self.state.banner = Banner("error", str(exc))
        self.changed.emit()

    def open_selected(self, new_tab: bool = True) -> None:
        """Open the selected profile in a new tab (or the current one)."""
        name = self.selected_name()
        if not name:
            return
        try:
            self.actions.open(name, new_tab=new_tab)
        except Exception as exc:  # pylint: disable=broad-except
            self._fail(exc)
            return
        where = "in a new tab" if new_tab and self.state.has_tabs else "here"
        self._done(f"Opened '{name}' {where}.", select=name, tone="info")

    def toggle_pin(self, key: str | None = None) -> None:
        """Toggle whether a profile shows in the toolbar list."""
        entry = self._entries.get(key or self._selected_key)
        if not entry or entry["kind"] == "trash":
            return
        pinned = not entry["pinned"]
        self.actions.set_pinned(entry["name"], pinned)
        state = "now shows" if pinned else "no longer shows"
        self._done(f"'{entry['name']}' {state} in the toolbar list.", tone="info")

    def save_notes(self, notes: str) -> None:
        """Store the description of the selected profile."""
        name = self.selected_name()
        selected = self.state.selected
        if not name or selected is None or (selected["notes"] or "") == (notes or "").strip():
            return
        self.actions.set_notes(name, notes)
        self.refresh()

    def request_name(self, mode: NameMode) -> None:
        """Ask the view for a name: ``save`` (current layout), ``rename`` or ``duplicate``."""
        original = "" if mode == "save" else (self.selected_name() or "")
        if mode != "save" and not original:
            return
        self.name_requested.emit(mode, original)

    def apply_name(self, mode: NameMode, original: str, name: str, **options) -> bool:
        """Run the confirmed save, rename or duplicate."""
        name = name.strip()
        try:
            text = self.actions.apply_name(mode, original, name, **options)
        except Exception as exc:  # pylint: disable=broad-except
            self._fail(exc)
            return False
        self._done(text, select=name)
        return True

    def request_revert(self) -> None:
        """Ask the view to confirm reverting the selected profile."""
        name = self.selected_name()
        if name and self.actions.can_revert(name):
            self.revert_requested.emit(name)

    def apply_revert(self, name: str) -> None:
        """Revert *name* to its saved copy."""
        try:
            self.actions.revert(name)
        except Exception as exc:  # pylint: disable=broad-except
            self._fail(exc)
            return
        self._done(f"Reverted '{name}' to its saved layout.", select=name)

    def request_delete(self) -> None:
        """Show the inline delete confirmation for the selected profile."""
        name = self.selected_name()
        if name and self.actions.can_delete(name)[0]:
            self.state.pending_delete = name
            self.changed.emit()

    def cancel_delete(self) -> None:
        """Hide the inline delete confirmation."""
        self.state.pending_delete = ""
        self.changed.emit()

    def confirm_delete(self) -> None:
        """Move the profile awaiting confirmation to Recently deleted."""
        name = self.state.pending_delete
        self.state.pending_delete = ""
        if not name:
            return
        try:
            entry = self.actions.delete(name)
        except Exception as exc:  # pylint: disable=broad-except
            self._fail(exc)
            return
        if entry is None:
            self._fail(ValueError(f"No files of '{name}' were found."))
            return
        self._done(
            f"Moved '{name}' to Recently deleted.",
            action="Undo",
            action_id=f"restore:{entry.token}",
        )

    def restore(self, token: str | None = None) -> None:
        """Restore a trashed profile (the selected one by default)."""
        if token is None:
            selected = self.state.selected
            token = selected["token"] if selected and selected["kind"] == "trash" else ""
        if not token:
            return
        try:
            name = self.actions.restore(token)
        except Exception as exc:  # pylint: disable=broad-except
            self._fail(exc)
            return
        self._done(f"Restored '{name}'.", select=name)

    def banner_action(self) -> None:
        """Run the action of the banner (e.g. Undo)."""
        banner = self.state.banner
        if banner is None or not banner.action_id:
            return
        kind, _, value = banner.action_id.partition(":")
        if kind == "restore":
            self.restore(value)
