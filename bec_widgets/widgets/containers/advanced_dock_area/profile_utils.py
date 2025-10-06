"""
Utilities for managing AdvancedDockArea profiles stored in INI files.

Policy:
- All created/modified profiles are stored under the BEC settings root: <base_path>/profiles/{default,user}
- Bundled read-only defaults are discovered in BW core states/default and plugin bec_widgets/profiles but never written to.
- Lookup order when reading: user → settings default → app or plugin bundled default.
"""

from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Literal

from bec_lib.client import BECClient
from bec_lib.plugin_helper import plugin_package_name, plugin_repo_path
from pydantic import BaseModel, Field
from PySide6QtAds import CDockWidget
from qtpy.QtCore import QByteArray, QDateTime, QSettings, Qt
from qtpy.QtGui import QPixmap

MODULE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

ProfileOrigin = Literal["module", "plugin", "settings", "unknown"]


def module_profiles_dir() -> str:
    """Return the read-only module-bundled profiles directory (no writes here)."""
    return os.path.join(MODULE_PATH, "containers", "advanced_dock_area", "profiles")


@lru_cache(maxsize=1)
def _plugin_repo_root() -> Path | None:
    try:
        return Path(plugin_repo_path())
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _plugin_display_name() -> str | None:
    repo_root = _plugin_repo_root()
    if not repo_root:
        return None
    repo_name = repo_root.name
    if repo_name:
        return repo_name
    try:
        pkg = plugin_package_name()
    except ValueError:
        return None
    return pkg.split(".")[0] if pkg else None


@lru_cache(maxsize=1)
def plugin_profiles_dir() -> str | None:
    """Return the read-only plugin-bundled profiles directory if available."""
    repo_root = _plugin_repo_root()
    if not repo_root:
        return None

    candidates = [repo_root.joinpath("bec_widgets", "profiles")]
    try:
        package_root = repo_root.joinpath(*plugin_package_name().split("."))
        candidates.append(package_root.joinpath("bec_widgets", "profiles"))
    except ValueError:
        pass

    for candidate in candidates:
        if candidate.is_dir():
            return str(candidate)
    return None


def _settings_profiles_root() -> str:
    """Return the writable profiles root provided by BEC client (or env fallback)."""
    client = BECClient()
    bec_widgets_settings = client._service_config.config.get("bec_widgets_settings")
    bec_widgets_setting_path = (
        bec_widgets_settings.get("base_path") if bec_widgets_settings else None
    )
    default_path = os.path.join(bec_widgets_setting_path, "profiles")
    root = os.environ.get("BECWIDGETS_PROFILE_DIR", default_path)
    os.makedirs(root, exist_ok=True)
    return root


def default_profiles_dir() -> str:
    path = os.path.join(_settings_profiles_root(), "default")
    os.makedirs(path, exist_ok=True)
    return path


def user_profiles_dir() -> str:
    path = os.path.join(_settings_profiles_root(), "user")
    os.makedirs(path, exist_ok=True)
    return path


def default_profile_path(name: str) -> str:
    return os.path.join(default_profiles_dir(), f"{name}.ini")


def user_profile_path(name: str) -> str:
    return os.path.join(user_profiles_dir(), f"{name}.ini")


def module_profile_path(name: str) -> str:
    return os.path.join(module_profiles_dir(), f"{name}.ini")


def plugin_profile_path(name: str) -> str | None:
    directory = plugin_profiles_dir()
    if not directory:
        return None
    return os.path.join(directory, f"{name}.ini")


def profile_origin(name: str) -> ProfileOrigin:
    """
    Determine where a profile originates from.

    Returns:
        ProfileOrigin: "module" for bundled BEC profiles, "plugin" for beamline plugin bundles,
        "settings" for user-defined ones, and "unknown" if no backing files are found.
    """
    if os.path.exists(module_profile_path(name)):
        return "module"
    plugin_path = plugin_profile_path(name)
    if plugin_path and os.path.exists(plugin_path):
        return "plugin"
    if os.path.exists(user_profile_path(name)) or os.path.exists(default_profile_path(name)):
        return "settings"
    return "unknown"


def is_profile_read_only(name: str) -> bool:
    """Return True when the profile originates from bundled module or plugin directories."""
    return profile_origin(name) in {"module", "plugin"}


def profile_origin_display(name: str) -> str | None:
    """Return a human-readable label for the profile's origin."""
    origin = profile_origin(name)
    if origin == "module":
        return "BEC Widgets"
    if origin == "plugin":
        return _plugin_display_name()
    if origin == "settings":
        return "User"
    return None


def delete_profile_files(name: str) -> bool:
    """
    Delete the profile files from the writable settings directories.

    Removes both the user and default copies (if they exist) and clears the last profile
    metadata when applicable. Returns True when at least one file was removed.
    """
    if is_profile_read_only(name):
        return False

    removed = False
    for path in {user_profile_path(name), default_profile_path(name)}:
        try:
            os.remove(path)
            removed = True
        except FileNotFoundError:
            continue

    if removed and get_last_profile() == name:
        set_last_profile(None)

    return removed


SETTINGS_KEYS = {
    "geom": "mainWindow/Geometry",
    "state": "mainWindow/State",
    "ads_state": "mainWindow/DockingState",
    "manifest": "manifest/widgets",
    "created_at": "profile/created_at",
    "is_quick_select": "profile/quick_select",
    "screenshot": "profile/screenshot",
    "screenshot_at": "profile/screenshot_at",
    "last_profile": "app/last_profile",
}


def list_profiles() -> list[str]:
    # Collect profiles from writable settings (default + user)
    defaults = {
        os.path.splitext(f)[0] for f in os.listdir(default_profiles_dir()) if f.endswith(".ini")
    }
    users = {os.path.splitext(f)[0] for f in os.listdir(user_profiles_dir()) if f.endswith(".ini")}

    # Also consider read-only defaults from core module and beamline plugin repositories
    read_only_sources: dict[str, tuple[str, str]] = {}
    sources: list[tuple[str, str | None]] = [
        ("module", module_profiles_dir()),
        ("plugin", plugin_profiles_dir()),
    ]
    for origin, directory in sources:
        if not directory or not os.path.isdir(directory):
            continue
        for filename in os.listdir(directory):
            if not filename.endswith(".ini"):
                continue
            name, _ = os.path.splitext(filename)
            read_only_sources.setdefault(name, (origin, os.path.join(directory, filename)))

    for name, (_origin, src) in sorted(read_only_sources.items()):
        # Ensure a copy in the settings default directory so existing code paths work unchanged
        dst_default = default_profile_path(name)
        if not os.path.exists(dst_default):
            os.makedirs(os.path.dirname(dst_default), exist_ok=True)
            shutil.copyfile(src, dst_default)
        # Ensure a user copy exists to allow edits in the writable settings area
        dst_user = user_profile_path(name)
        if not os.path.exists(dst_user):
            os.makedirs(os.path.dirname(dst_user), exist_ok=True)
            shutil.copyfile(src, dst_user)
            # Minimal metadata touch-up to align with existing expectations
            s = open_user_settings(name)
            if not s.value(SETTINGS_KEYS["created_at"], ""):
                s.setValue(SETTINGS_KEYS["created_at"], now_iso_utc())

    defaults |= set(read_only_sources.keys())
    users |= set(read_only_sources.keys())

    # Return union of all discovered names
    return sorted(defaults | users)


def open_default_settings(name: str) -> QSettings:
    return QSettings(default_profile_path(name), QSettings.IniFormat)


def open_user_settings(name: str) -> QSettings:
    return QSettings(user_profile_path(name), QSettings.IniFormat)


def _app_settings() -> QSettings:
    """Return app-wide settings file for AdvancedDockArea metadata."""
    return QSettings(os.path.join(_settings_profiles_root(), "_meta.ini"), QSettings.IniFormat)


def get_last_profile() -> str | None:
    """Return the last-used profile name if stored, else None."""
    s = _app_settings()
    name = s.value(SETTINGS_KEYS["last_profile"], "", type=str)
    return name or None


def set_last_profile(name: str | None) -> None:
    """Persist the last-used profile name (or clear it if None)."""
    s = _app_settings()
    if name:
        s.setValue(SETTINGS_KEYS["last_profile"], name)
    else:
        s.remove(SETTINGS_KEYS["last_profile"])


def now_iso_utc() -> str:
    return QDateTime.currentDateTimeUtc().toString(Qt.ISODate)


def write_manifest(settings: QSettings, docks: list[CDockWidget]) -> None:
    settings.beginWriteArray(SETTINGS_KEYS["manifest"], len(docks))
    for i, dock in enumerate(docks):
        settings.setArrayIndex(i)
        w = dock.widget()
        settings.setValue("object_name", w.objectName())
        settings.setValue("widget_class", w.__class__.__name__)
        settings.setValue("closable", getattr(dock, "_default_closable", True))
        settings.setValue("floatable", getattr(dock, "_default_floatable", True))
        settings.setValue("movable", getattr(dock, "_default_movable", True))
    settings.endArray()


def read_manifest(settings: QSettings) -> list[dict]:
    items: list[dict] = []
    count = settings.beginReadArray(SETTINGS_KEYS["manifest"])
    for i in range(count):
        settings.setArrayIndex(i)
        items.append(
            {
                "object_name": settings.value("object_name"),
                "widget_class": settings.value("widget_class"),
                "closable": settings.value("closable", type=bool),
                "floatable": settings.value("floatable", type=bool),
                "movable": settings.value("movable", type=bool),
            }
        )
    settings.endArray()
    return items


def restore_user_from_default(name: str) -> None:
    """Overwrite the user profile with the default baseline (keep default intact)."""
    src = default_profile_path(name)
    dst = user_profile_path(name)
    if not os.path.exists(src):
        return
    preserve_quick_select = is_quick_select(name)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    s = open_user_settings(name)
    if not s.value(SETTINGS_KEYS["created_at"], ""):
        s.setValue(SETTINGS_KEYS["created_at"], now_iso_utc())
    if preserve_quick_select:
        s.setValue(SETTINGS_KEYS["is_quick_select"], True)


def is_quick_select(name: str) -> bool:
    """Return True if profile is marked to appear in quick-select combo."""
    s = (
        open_user_settings(name)
        if os.path.exists(user_profile_path(name))
        else (open_default_settings(name) if os.path.exists(default_profile_path(name)) else None)
    )
    if s is None:
        return False
    return s.value(SETTINGS_KEYS["is_quick_select"], False, type=bool)


def set_quick_select(name: str, enabled: bool) -> None:
    """Set/unset the quick-select flag on the USER copy (creates it if missing)."""
    s = open_user_settings(name)
    s.setValue(SETTINGS_KEYS["is_quick_select"], bool(enabled))


def list_quick_profiles() -> list[str]:
    """List only profiles that have quick-select enabled (user wins over default)."""
    names = list_profiles()
    return [n for n in names if is_quick_select(n)]


def _file_modified_iso(path: str) -> str:
    try:
        mtime = os.path.getmtime(path)
        return QDateTime.fromSecsSinceEpoch(int(mtime), Qt.UTC).toString(Qt.ISODate)
    except Exception:
        return now_iso_utc()


def _manifest_count(settings: QSettings) -> int:
    n = settings.beginReadArray(SETTINGS_KEYS["manifest"])
    settings.endArray()
    return int(n or 0)


def _load_screenshot_from_settings(settings: QSettings) -> QPixmap | None:
    data = settings.value(SETTINGS_KEYS["screenshot"], None)
    if not data:
        return None

    buf = None
    if isinstance(data, QByteArray):
        buf = data
    elif isinstance(data, (bytes, bytearray, memoryview)):
        buf = bytes(data)
    elif isinstance(data, str):
        try:
            buf = QByteArray(data.encode("latin-1"))
        except Exception:
            buf = None

    if buf is None:
        return None

    pm = QPixmap()
    ok = pm.loadFromData(buf)
    return pm if ok and not pm.isNull() else None


class ProfileInfo(BaseModel):
    name: str
    author: str = "BEC Widgets"
    notes: str = ""
    created: str = Field(default_factory=now_iso_utc)
    modified: str = Field(default_factory=now_iso_utc)
    is_quick_select: bool = False
    widget_count: int = 0
    size_kb: int = 0
    user_path: str = ""
    default_path: str = ""
    origin: ProfileOrigin = "unknown"
    is_read_only: bool = False


def get_profile_info(name: str) -> ProfileInfo:
    """
    Return merged metadata for a profile as a validated Pydantic model.
    Prefers the USER copy; falls back to DEFAULT if the user copy is missing.
    """
    u_path = user_profile_path(name)
    d_path = default_profile_path(name)
    origin = profile_origin(name)
    prefer_user = os.path.exists(u_path)
    read_only = origin in {"module", "plugin"}
    s = (
        open_user_settings(name)
        if prefer_user
        else (open_default_settings(name) if os.path.exists(d_path) else None)
    )
    if s is None:
        if origin == "module":
            author = "BEC Widgets"
        elif origin == "plugin":
            author = _plugin_display_name() or "Plugin"
        elif origin == "settings":
            author = "User"
        else:
            author = ""
        return ProfileInfo(
            name=name,
            author=author,
            notes="",
            created=now_iso_utc(),
            modified=now_iso_utc(),
            is_quick_select=False,
            widget_count=0,
            size_kb=0,
            user_path=u_path,
            default_path=d_path,
            origin=origin,
            is_read_only=read_only,
        )

    created = s.value(SETTINGS_KEYS["created_at"], "", type=str) or now_iso_utc()
    src_path = u_path if prefer_user else d_path
    modified = _file_modified_iso(src_path)
    count = _manifest_count(s)
    try:
        size_kb = int(os.path.getsize(src_path) / 1024)
    except Exception:
        size_kb = 0
    settings_author = s.value("profile/author", "", type=str) or None
    if origin == "module":
        author = "BEC Widgets"
    elif origin == "plugin":
        author = _plugin_display_name() or "Plugin"
    elif origin == "settings":
        author = "User"
    else:
        author = settings_author or "user"

    return ProfileInfo(
        name=name,
        author=author,
        notes=s.value("profile/notes", "", type=str) or "",
        created=created,
        modified=modified,
        is_quick_select=is_quick_select(name),
        widget_count=count,
        size_kb=size_kb,
        user_path=u_path,
        default_path=d_path,
        origin=origin,
        is_read_only=read_only,
    )


def load_profile_screenshot(name: str) -> QPixmap | None:
    """Load the stored screenshot pixmap for a profile from settings (user preferred)."""
    u_path = user_profile_path(name)
    d_path = default_profile_path(name)
    s = (
        open_user_settings(name)
        if os.path.exists(u_path)
        else (open_default_settings(name) if os.path.exists(d_path) else None)
    )
    if s is None:
        return None
    return _load_screenshot_from_settings(s)


def load_user_profile_screenshot(name: str) -> QPixmap | None:
    """Load the screenshot from the user profile copy, if available."""
    if not os.path.exists(user_profile_path(name)):
        return None
    return _load_screenshot_from_settings(open_user_settings(name))


def load_default_profile_screenshot(name: str) -> QPixmap | None:
    """Load the screenshot from the default profile copy, if available."""
    if not os.path.exists(default_profile_path(name)):
        return None
    return _load_screenshot_from_settings(open_default_settings(name))
