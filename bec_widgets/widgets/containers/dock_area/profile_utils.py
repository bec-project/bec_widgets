"""
Utilities for managing BECDockArea profiles stored in INI files.

Policy:
- All created/modified profiles are stored under the BEC settings root:
  <base_path>/profiles/{baseline,runtime}
- Bundled read-only baselines are discovered in BW core profiles and plugin
  bec_widgets/profiles but never written to.
- Lookup order when reading: runtime → settings baseline → app or plugin bundled baseline.
- Legacy settings paths profiles/{default,user} are read through a thin segment
  alias layer and copied to the canonical location on first access.
"""

from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Literal

import slugify
from bec_lib import bec_logger
from bec_lib.client import BECClient
from bec_lib.plugin_helper import plugin_package_name, plugin_repo_path
from pydantic import BaseModel, Field
from qtpy.QtCore import QByteArray, QDateTime, QSettings, QTimeZone
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import QApplication

from bec_widgets.utils.name_utils import sanitize_namespace
from bec_widgets.widgets.containers.qt_ads import CDockWidget

logger = bec_logger.logger

MODULE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

ProfileOrigin = Literal["module", "plugin", "settings", "unknown"]
ProfileSegment = Literal["baseline", "runtime"]

_PROFILE_SEGMENT_ALIASES: dict[ProfileSegment, tuple[str, str]] = {
    "baseline": ("baseline", "default"),
    "runtime": ("runtime", "user"),
}


def module_profiles_dir() -> str:
    """
    Return the built-in BECDockArea profiles directory bundled with the module.

    Returns:
        str: Absolute path of the read-only module profiles directory.
    """
    return os.path.join(MODULE_PATH, "containers", "dock_area", "profiles")


@lru_cache(maxsize=1)
def _plugin_repo_root() -> Path | None:
    """
    Resolve the plugin repository root path if running inside a plugin context.

    Returns:
        Path | None: Root path of the active plugin repository, or ``None`` when
            no plugin context is detected.
    """
    try:
        return Path(plugin_repo_path())
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _plugin_display_name() -> str | None:
    """
    Determine a user-friendly plugin name for provenance labels.

    Returns:
        str | None: Human-readable name inferred from the plugin repo or package,
            or ``None`` if it cannot be determined.
    """
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
    """
    Locate the read-only profiles directory shipped with a beamline plugin.

    Returns:
        str | None: Directory containing bundled plugin profiles, or ``None`` if
            no plugin profiles are available.
    """
    repo_root = _plugin_repo_root()
    if not repo_root:
        return None

    candidates = [repo_root.joinpath("bec_widgets", "profiles")]
    try:
        package_root = repo_root.joinpath(*plugin_package_name().split("."))
        candidates.append(package_root.joinpath("bec_widgets", "profiles"))
    except ValueError as e:
        logger.error(f"Could not determine plugin package name: {e}")

    for candidate in candidates:
        if candidate.is_dir():
            return str(candidate)
    return None


def _settings_profiles_root() -> str:
    """
    Resolve the writable profiles root provided by the BEC client.

    Returns:
        str: Absolute path to the profiles root. The directory is created if missing.
    """
    client = BECClient()
    bec_widgets_settings = client._service_config.config.get("widgets_settings")
    bec_widgets_setting_path = (
        bec_widgets_settings.get("base_path") if bec_widgets_settings else None
    )
    default_path = os.path.join(bec_widgets_setting_path, "profiles")
    root = os.path.expanduser(os.environ.get("BECWIDGETS_PROFILE_DIR", default_path))
    os.makedirs(root, exist_ok=True)
    return root


def _profiles_dir(segment: str, namespace: str | None) -> str:
    """
    Build (and ensure) the directory that holds profiles for a namespace segment.

    Args:
        segment (str): Profile segment directory name.
        namespace (str | None): Optional namespace label to scope profiles.

    Returns:
        str: Absolute directory path for the requested segment/namespace pair.
    """
    base = os.path.join(_settings_profiles_root(), segment)
    ns = slugify.slugify(namespace, separator="_") if namespace else None
    path = os.path.expanduser(os.path.join(base, ns) if ns else base)
    os.makedirs(path, exist_ok=True)
    return path


def _candidate_namespaces(namespace: str | None) -> list[str | None]:
    ns = slugify.slugify(namespace, separator="_") if namespace else None
    if not ns:
        return [None]
    return [ns, None]


def _segment_profile_path(segment_name: str, name: str, namespace: str | None) -> str:
    return os.path.join(_profiles_dir(segment_name, namespace), f"{name}.ini")


def _canonical_profile_path(segment: ProfileSegment, name: str, namespace: str | None) -> str:
    return _segment_profile_path(_PROFILE_SEGMENT_ALIASES[segment][0], name, namespace)


def _segment_path_candidates(
    segment: ProfileSegment,
    name: str,
    namespace: str | None,
    *,
    include_legacy: bool = True,
    migrate_legacy: bool = True,
) -> list[str]:
    """
    Generate profile candidates for a canonical segment.

    Canonical baseline/runtime files are always preferred. Namespace fallback
    files and legacy default/user files are copied to the primary canonical path
    when the primary file does not exist.
    """
    canonical = [
        _segment_profile_path(_PROFILE_SEGMENT_ALIASES[segment][0], name, ns)
        for ns in _candidate_namespaces(namespace)
    ]
    legacy = []
    if include_legacy:
        legacy = [
            _segment_profile_path(_PROFILE_SEGMENT_ALIASES[segment][1], name, ns)
            for ns in _candidate_namespaces(namespace)
        ]

    primary_canonical = canonical[0]
    if migrate_legacy and not os.path.exists(primary_canonical):
        canonical_src = next((path for path in canonical[1:] if os.path.exists(path)), None)
        if canonical_src:
            os.makedirs(os.path.dirname(primary_canonical), exist_ok=True)
            shutil.copy2(canonical_src, primary_canonical)
        elif include_legacy:
            legacy_src = next((path for path in legacy if os.path.exists(path)), None)
            if legacy_src:
                os.makedirs(os.path.dirname(primary_canonical), exist_ok=True)
                shutil.copy2(legacy_src, primary_canonical)

    return list(dict.fromkeys(canonical + legacy))


def baseline_profiles_dir(namespace: str | None = None) -> str:
    """
    Return the directory that stores baseline profiles for the namespace.

    Args:
        namespace (str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        str: Absolute path to the baseline profile directory.
    """
    return _profiles_dir("baseline", namespace)


def runtime_profiles_dir(namespace: str | None = None) -> str:
    """
    Return the directory that stores runtime profiles for the namespace.

    Args:
        namespace (str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        str: Absolute path to the runtime profile directory.
    """
    return _profiles_dir("runtime", namespace)


def baseline_profile_path(name: str, namespace: str | None = None) -> str:
    """
    Compute the canonical baseline profile path for a profile name.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        str: Absolute path to the baseline profile file (.ini).
    """
    return _canonical_profile_path("baseline", name, namespace)


def runtime_profile_path(name: str, namespace: str | None = None) -> str:
    """
    Compute the canonical runtime profile path for a profile name.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        str: Absolute path to the runtime profile file (.ini).
    """
    return _canonical_profile_path("runtime", name, namespace)


def runtime_profile_candidates(name: str, namespace: str | None = None) -> list[str]:
    """
    List all runtime profile path candidates for a profile name.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        list[str]: De-duplicated list of candidate runtime profile paths.
    """
    return _segment_path_candidates("runtime", name, namespace)


def baseline_profile_candidates(name: str, namespace: str | None = None) -> list[str]:
    """
    List all baseline profile path candidates for a profile name.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        list[str]: De-duplicated list of candidate baseline profile paths.
    """
    return _segment_path_candidates("baseline", name, namespace)


def _existing_runtime_settings(name: str, namespace: str | None = None) -> QSettings | None:
    """
    Resolve the first existing runtime profile settings object.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label to search. Defaults to ``None``.

    Returns:
        QSettings | None: Config for the first existing runtime profile candidate, or ``None``
            when no files are present.
    """
    for path in runtime_profile_candidates(name, namespace):
        if os.path.exists(path):
            return QSettings(path, QSettings.IniFormat)
    return None


def _existing_baseline_settings(name: str, namespace: str | None = None) -> QSettings | None:
    """
    Resolve the first existing baseline profile settings object.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label to search. Defaults to ``None``.

    Returns:
        QSettings | None: Config for the first existing baseline profile candidate, or ``None``
            when no files are present.
    """
    for path in baseline_profile_candidates(name, namespace):
        if os.path.exists(path):
            return QSettings(path, QSettings.IniFormat)
    return None


def module_profile_path(name: str) -> str:
    """
    Build the absolute path to a bundled module profile.

    Args:
        name (str): Profile name without extension.

    Returns:
        str: Absolute path to the module's read-only profile file.
    """
    return os.path.join(module_profiles_dir(), f"{name}.ini")


def plugin_profile_path(name: str) -> str | None:
    """
    Build the absolute path to a bundled plugin profile if available.

    Args:
        name (str): Profile name without extension.

    Returns:
        str | None: Absolute plugin profile path, or ``None`` when plugins do not
            provide profiles.
    """
    directory = plugin_profiles_dir()
    if not directory:
        return None
    return os.path.join(directory, f"{name}.ini")


def profile_origin(name: str, namespace: str | None = None) -> ProfileOrigin:
    """
    Determine where a profile originates from.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label to consider. Defaults to ``None``.

    Returns:
        ProfileOrigin: ``"module"`` for bundled BEC profiles, ``"plugin"`` for beamline
            plugin bundles, ``"settings"`` for writable copies, and ``"unknown"`` when
            no backing files are found.
    """
    if os.path.exists(module_profile_path(name)):
        return "module"
    plugin_path = plugin_profile_path(name)
    if plugin_path and os.path.exists(plugin_path):
        return "plugin"
    for path in runtime_profile_candidates(name, namespace) + baseline_profile_candidates(
        name, namespace
    ):
        if os.path.exists(path):
            return "settings"
    return "unknown"


def is_profile_read_only(name: str, namespace: str | None = None) -> bool:
    """
    Check whether a profile is read-only because it originates from bundles.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label to consider. Defaults to ``None``.

    Returns:
        bool: ``True`` if the profile originates from module or plugin bundles.
    """
    return profile_origin(name, namespace) in {"module", "plugin"}


def profile_origin_display(name: str, namespace: str | None = None) -> str | None:
    """
    Build a user-facing label describing a profile's origin.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label to consider. Defaults to ``None``.

    Returns:
        str | None: Localized display label such as ``"BEC Widgets"`` or ``"User"``,
            or ``None`` when origin cannot be determined.
    """
    origin = profile_origin(name, namespace)
    if origin == "module":
        return "BEC Widgets"
    if origin == "plugin":
        return _plugin_display_name()
    if origin == "settings":
        return "User"
    return None


def delete_profile_files(name: str, namespace: str | None = None) -> bool:
    """
    Delete the profile files from the writable settings directories.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label scoped to the profile. Defaults
            to ``None``.

    Returns:
        bool: ``True`` if at least one file was removed.
    """
    read_only = is_profile_read_only(name, namespace)

    removed = False
    # Always allow removing runtime copies; keep baseline copies for read-only origins.
    for path in set(runtime_profile_candidates(name, namespace)):
        try:
            os.remove(path)
            removed = True
        except FileNotFoundError:
            continue

    if not read_only:
        for path in set(baseline_profile_candidates(name, namespace)):
            try:
                os.remove(path)
                removed = True
            except FileNotFoundError:
                continue

    if removed and get_last_profile(namespace) == name:
        set_last_profile(None, namespace)

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


def list_profiles(namespace: str | None = None) -> list[str]:
    """
    Enumerate all known profile names, syncing bundled baselines when missing locally.

    Args:
        namespace (str | None, optional): Namespace label scoped to the profile set.
            Defaults to ``None``.

    Returns:
        list[str]: Sorted unique profile names.
    """
    ns = slugify.slugify(namespace, separator="_") if namespace else None

    def _collect_from(directory: str) -> set[str]:
        if not os.path.isdir(directory):
            return set()
        return {os.path.splitext(f)[0] for f in os.listdir(directory) if f.endswith(".ini")}

    settings_dirs = {baseline_profiles_dir(namespace), runtime_profiles_dir(namespace)}
    if ns:
        settings_dirs.add(baseline_profiles_dir(None))
        settings_dirs.add(runtime_profiles_dir(None))

    for segment in ("baseline", "runtime"):
        for legacy_dir in [
            _profiles_dir(_PROFILE_SEGMENT_ALIASES[segment][1], item)
            for item in _candidate_namespaces(namespace)
        ]:
            settings_dirs.add(legacy_dir)

    settings_names: set[str] = set()
    for directory in settings_dirs:
        settings_names |= _collect_from(directory)

    for name in sorted(settings_names):
        runtime_profile_candidates(name, namespace)
        baseline_profile_candidates(name, namespace)

    # Also consider read-only baselines from core module and beamline plugin repositories
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
        # Ensure a copy in the namespace-specific settings baseline directory.
        dst_baseline = baseline_profile_path(name, namespace)
        if not os.path.exists(dst_baseline):
            os.makedirs(os.path.dirname(dst_baseline), exist_ok=True)
            shutil.copy2(src, dst_baseline)
        # Ensure a runtime copy exists to allow edits in the writable settings area.
        dst_runtime = runtime_profile_path(name, namespace)
        if not os.path.exists(dst_runtime):
            os.makedirs(os.path.dirname(dst_runtime), exist_ok=True)
            shutil.copy2(src, dst_runtime)
            s = open_runtime_settings(name, namespace)
            if s.value(SETTINGS_KEYS["created_at"], "") == "":
                s.setValue(SETTINGS_KEYS["created_at"], now_iso_utc())

    settings_names |= set(read_only_sources.keys())

    # Return union of all discovered names
    return sorted(settings_names)


def open_baseline_settings(name: str, namespace: str | None = None) -> QSettings:
    """
    Open (and create if necessary) the baseline profile settings file.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        QSettings: Settings instance targeting the baseline profile file.
    """
    baseline_profile_candidates(name, namespace)
    return QSettings(baseline_profile_path(name, namespace), QSettings.IniFormat)


def open_runtime_settings(name: str, namespace: str | None = None) -> QSettings:
    """
    Open (and create if necessary) the runtime profile settings file.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        QSettings: Settings instance targeting the runtime profile file.
    """
    runtime_profile_candidates(name, namespace)
    return QSettings(runtime_profile_path(name, namespace), QSettings.IniFormat)


def _app_settings() -> QSettings:
    """
    Access the application-wide metadata settings file for dock profiles.

    Returns:
        QSettings: Handle to the ``_meta.ini`` metadata store under the profiles root.
    """
    return QSettings(os.path.join(_settings_profiles_root(), "_meta.ini"), QSettings.IniFormat)


def _last_profile_key(namespace: str | None, instance: str | None = None) -> str:
    """
    Build the QSettings key used to store the last profile per namespace and
    optional instance id.

    Args:
        namespace (str | None): Namespace label.

    Returns:
        str: Scoped key string.
    """
    ns = slugify.slugify(namespace, separator="_") if namespace else None
    key = SETTINGS_KEYS["last_profile"]
    if ns:
        key = f"{key}/{ns}"
    inst = slugify.slugify(instance, separator="_") if instance else ""
    if inst:
        key = f"{key}@{inst}"
    return key


def get_last_profile(
    namespace: str | None = None,
    instance: str | None = None,
    *,
    allow_namespace_fallback: bool = True,
) -> str | None:
    """
    Retrieve the last-used profile name persisted in app settings.

    When *instance* is provided, the lookup is scoped to that particular dock
    area instance. If the instance-specific entry is missing and
    ``allow_namespace_fallback`` is True, the namespace-wide entry is
    consulted next.

    Args:
        namespace (str | None, optional): Namespace label. Defaults to ``None``.
        instance (str | None, optional): Optional instance ID. Defaults to ``None``.
        allow_namespace_fallback (bool): Whether to fall back to the namespace
            entry when an instance-specific value is not found. Defaults to ``True``.

    Returns:
        str | None: Profile name or ``None`` if none has been stored.
    """
    s = _app_settings()
    inst = instance or None
    if inst:
        name = s.value(_last_profile_key(namespace, inst), "", type=str)
        if name:
            return name
        if not allow_namespace_fallback:
            return None
    name = s.value(_last_profile_key(namespace, None), "", type=str)
    return name or None


def set_last_profile(
    name: str | None, namespace: str | None = None, instance: str | None = None
) -> None:
    """
    Persist the last-used profile name (or clear the value when ``None``).

    When *instance* is provided, the value is stored under a key specific to
    that dock area instance; otherwise it is stored under the namespace-wide key.

    Args:
        name (str | None): Profile name to store.
        namespace (str | None, optional): Namespace label. Defaults to ``None``.
        instance (str | None, optional): Optional instance ID. Defaults to ``None``.
    """
    s = _app_settings()
    key = _last_profile_key(namespace, instance)
    if name:
        s.setValue(key, name)
    else:
        s.remove(key)


def now_iso_utc() -> str:
    """
    Return the current UTC timestamp formatted in ISO 8601.

    Returns:
        str: UTC timestamp string (e.g., ``"2024-06-05T12:34:56Z"``).
    """
    return QDateTime.currentDateTimeUtc().toString("yyyy-MM-ddTHH:mm:ssZ")


def write_manifest(settings: QSettings, docks: list[CDockWidget]) -> None:
    """
    Write the manifest of dock widgets to settings.

    Args:
        settings(QSettings): Settings object to write to.
        docks(list[CDockWidget]): List of dock widgets to serialize.
    """

    def _floating_snapshot(dock: CDockWidget) -> dict | None:
        if not hasattr(dock, "isFloating") or not dock.isFloating():
            return None
        container = dock.floatingDockContainer() if hasattr(dock, "floatingDockContainer") else None
        if container is None:
            return None
        geom = container.frameGeometry()
        if geom.isNull():
            return None
        absolute = {"x": geom.x(), "y": geom.y(), "w": geom.width(), "h": geom.height()}
        screen = container.screen() if hasattr(container, "screen") else None
        if screen is None:
            screen = QApplication.screenAt(geom.center()) if QApplication.instance() else None
        screen_name = ""
        relative = None
        if screen is not None:
            if hasattr(screen, "name"):
                try:
                    screen_name = screen.name()
                except Exception:
                    screen_name = ""
            avail = screen.availableGeometry()
            width = max(1, avail.width())
            height = max(1, avail.height())
            relative = {
                "x": (geom.left() - avail.left()) / float(width),
                "y": (geom.top() - avail.top()) / float(height),
                "w": geom.width() / float(width),
                "h": geom.height() / float(height),
            }
        return {"screen_name": screen_name, "relative": relative, "absolute": absolute}

    ordered_docks = [dock for dock in docks if dock.isFloating()] + [
        dock for dock in docks if not dock.isFloating()
    ]
    settings.beginWriteArray(SETTINGS_KEYS["manifest"], len(ordered_docks))
    for i, dock in enumerate(ordered_docks):
        settings.setArrayIndex(i)
        w = dock.widget()
        settings.setValue("object_name", w.objectName())
        settings.setValue("widget_class", w.__class__.__name__)
        settings.setValue("closable", getattr(dock, "_default_closable", True))
        settings.setValue("floatable", getattr(dock, "_default_floatable", True))
        settings.setValue("movable", getattr(dock, "_default_movable", True))
        is_floating = bool(dock.isFloating())
        settings.setValue("floating", is_floating)
        if is_floating:
            snapshot = _floating_snapshot(dock)
            if snapshot:
                relative = snapshot.get("relative") or {}
                absolute = snapshot.get("absolute") or {}
                settings.setValue("floating_screen", snapshot.get("screen_name", ""))
                settings.setValue("floating_rel_x", relative.get("x", 0.0))
                settings.setValue("floating_rel_y", relative.get("y", 0.0))
                settings.setValue("floating_rel_w", relative.get("w", 0.0))
                settings.setValue("floating_rel_h", relative.get("h", 0.0))
                settings.setValue("floating_abs_x", absolute.get("x", 0))
                settings.setValue("floating_abs_y", absolute.get("y", 0))
                settings.setValue("floating_abs_w", absolute.get("w", 0))
                settings.setValue("floating_abs_h", absolute.get("h", 0))
        else:
            settings.setValue("floating_screen", "")
            settings.setValue("floating_rel_x", 0.0)
            settings.setValue("floating_rel_y", 0.0)
            settings.setValue("floating_rel_w", 0.0)
            settings.setValue("floating_rel_h", 0.0)
            settings.setValue("floating_abs_x", 0)
            settings.setValue("floating_abs_y", 0)
            settings.setValue("floating_abs_w", 0)
            settings.setValue("floating_abs_h", 0)
    settings.endArray()


def read_manifest(settings: QSettings) -> list[dict]:
    """
    Read the manifest of dock widgets from settings.

    Args:
        settings(QSettings): Settings object to read from.

    Returns:
        list[dict]: List of dock widget metadata dictionaries.
    """
    items: list[dict] = []
    count = settings.beginReadArray(SETTINGS_KEYS["manifest"])
    for i in range(count):
        settings.setArrayIndex(i)
        floating = settings.value("floating", False, type=bool)
        rel = {
            "x": float(settings.value("floating_rel_x", 0.0)),
            "y": float(settings.value("floating_rel_y", 0.0)),
            "w": float(settings.value("floating_rel_w", 0.0)),
            "h": float(settings.value("floating_rel_h", 0.0)),
        }
        abs_geom = {
            "x": int(settings.value("floating_abs_x", 0)),
            "y": int(settings.value("floating_abs_y", 0)),
            "w": int(settings.value("floating_abs_w", 0)),
            "h": int(settings.value("floating_abs_h", 0)),
        }
        if not floating:
            rel = None
            abs_geom = None
        items.append(
            {
                "object_name": settings.value("object_name"),
                "widget_class": settings.value("widget_class"),
                "closable": settings.value("closable", type=bool),
                "floatable": settings.value("floatable", type=bool),
                "movable": settings.value("movable", type=bool),
                "floating": floating,
                "floating_screen": settings.value("floating_screen", ""),
                "floating_relative": rel,
                "floating_absolute": abs_geom,
            }
        )
    settings.endArray()
    return items


def restore_runtime_from_baseline(name: str, namespace: str | None = None) -> None:
    """
    Copy the baseline profile to the runtime profile, preserving quick-select flag.

    Args:
        name(str): Profile name without extension.
        namespace(str | None, optional): Namespace label. Defaults to ``None``.
    """
    src = None
    for candidate in baseline_profile_candidates(name, namespace):
        if os.path.exists(candidate):
            src = candidate
            break
    if not src:
        return
    dst = runtime_profile_path(name, namespace)
    preserve_quick_select = is_quick_select(name, namespace)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    s = open_runtime_settings(name, namespace)
    if not s.value(SETTINGS_KEYS["created_at"], ""):
        s.setValue(SETTINGS_KEYS["created_at"], now_iso_utc())
    if preserve_quick_select:
        s.setValue(SETTINGS_KEYS["is_quick_select"], True)


def is_quick_select(name: str, namespace: str | None = None) -> bool:
    """
    Return True if profile is marked to appear in quick-select combo.

    Args:
        name(str): Profile name without extension.
        namespace(str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        bool: True if quick-select is enabled for the profile.
    """
    s = _existing_runtime_settings(name, namespace)
    if s is None:
        s = _existing_baseline_settings(name, namespace)
    if s is None:
        return False
    return s.value(SETTINGS_KEYS["is_quick_select"], False, type=bool)


def set_quick_select(name: str, enabled: bool, namespace: str | None = None) -> None:
    """
    Set or clear the quick-select flag for a profile.

    Args:
        name(str): Profile name without extension.
        enabled(bool): True to enable quick-select, False to disable.
        namespace(str | None, optional): Namespace label. Defaults to ``None``.
    """
    s = open_runtime_settings(name, namespace)
    s.setValue(SETTINGS_KEYS["is_quick_select"], bool(enabled))


def list_quick_profiles(namespace: str | None = None) -> list[str]:
    """
    List only profiles that have quick-select enabled (runtime wins over baseline).

    Args:
        namespace(str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        list[str]: Sorted list of profile names with quick-select enabled.
    """
    names = list_profiles(namespace)
    return [n for n in names if is_quick_select(n, namespace)]


def _file_modified_iso(path: str) -> str:
    """
    Get the file modification time as an ISO 8601 UTC string.

    Args:
        path(str): Path to the file.

    Returns:
        str: ISO 8601 UTC timestamp of last modification, or current time if unavailable.
    """
    try:
        mtime = os.path.getmtime(path)
        return QDateTime.fromSecsSinceEpoch(int(mtime), QTimeZone.utc()).toString(
            "yyyy-MM-ddTHH:mm:ssZ"
        )
    except Exception:
        return now_iso_utc()


def _manifest_count(settings: QSettings) -> int:
    """
    Get the number of widgets recorded in the manifest.

    Args:
        settings(QSettings): Settings object to read from.

    Returns:
        int: Number of widgets in the manifest.
    """
    n = settings.beginReadArray(SETTINGS_KEYS["manifest"])
    settings.endArray()
    return int(n or 0)


def _load_screenshot_from_settings(settings: QSettings) -> QPixmap | None:
    """
    Load the screenshot pixmap stored in the given settings.

    Args:
        settings(QSettings): Settings object to read from.

    Returns:
        QPixmap | None: Screenshot pixmap or ``None`` if unavailable.
    """
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
    """Pydantic model capturing profile metadata surfaced in the UI."""

    name: str
    author: str = "BEC Widgets"
    notes: str = ""
    created: str = Field(default_factory=now_iso_utc)
    modified: str = Field(default_factory=now_iso_utc)
    is_quick_select: bool = False
    widget_count: int = 0
    size_kb: int = 0
    runtime_path: str = ""
    baseline_path: str = ""
    origin: ProfileOrigin = "unknown"
    is_read_only: bool = False


def get_profile_info(name: str, namespace: str | None = None) -> ProfileInfo:
    """
    Assemble metadata and statistics for a profile.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        ProfileInfo: Structured profile metadata, preferring the runtime copy when present.
    """
    runtime_paths = runtime_profile_candidates(name, namespace)
    baseline_paths = baseline_profile_candidates(name, namespace)
    r_path = next((p for p in runtime_paths if os.path.exists(p)), runtime_paths[0])
    b_path = next((p for p in baseline_paths if os.path.exists(p)), baseline_paths[0])
    origin = profile_origin(name, namespace)
    read_only = origin in {"module", "plugin"}
    prefer_runtime = os.path.exists(r_path)
    if prefer_runtime:
        s = QSettings(r_path, QSettings.IniFormat)
    elif os.path.exists(b_path):
        s = QSettings(b_path, QSettings.IniFormat)
    else:
        s = None
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
            runtime_path=r_path,
            baseline_path=b_path,
            origin=origin,
            is_read_only=read_only,
        )

    created = s.value(SETTINGS_KEYS["created_at"], "", type=str) or now_iso_utc()
    src_path = r_path if prefer_runtime else b_path
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
        is_quick_select=is_quick_select(name, namespace),
        widget_count=count,
        size_kb=size_kb,
        runtime_path=r_path,
        baseline_path=b_path,
        origin=origin,
        is_read_only=read_only,
    )


def load_profile_screenshot(name: str, namespace: str | None = None) -> QPixmap | None:
    """
    Load the stored screenshot pixmap for a profile from settings (runtime preferred).

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        QPixmap | None: Screenshot pixmap or ``None`` if unavailable.
    """
    s = _existing_runtime_settings(name, namespace)
    if s is None:
        s = _existing_baseline_settings(name, namespace)
    if s is None:
        return None
    return _load_screenshot_from_settings(s)


def load_baseline_profile_screenshot(name: str, namespace: str | None = None) -> QPixmap | None:
    """
    Load the screenshot from the baseline profile copy, if available.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        QPixmap | None: Screenshot pixmap or ``None`` if unavailable.
    """
    s = _existing_baseline_settings(name, namespace)
    if s is None:
        return None
    return _load_screenshot_from_settings(s)


def load_runtime_profile_screenshot(name: str, namespace: str | None = None) -> QPixmap | None:
    """
    Load the screenshot from the runtime profile copy, if available.

    Args:
        name (str): Profile name without extension.
        namespace (str | None, optional): Namespace label. Defaults to ``None``.

    Returns:
        QPixmap | None: Screenshot pixmap or ``None`` if unavailable.
    """
    s = _existing_runtime_settings(name, namespace)
    if s is None:
        return None
    return _load_screenshot_from_settings(s)
