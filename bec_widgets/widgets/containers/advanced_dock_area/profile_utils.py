import os

from bec_lib.client import BECClient
from PySide6QtAds import CDockWidget
from qtpy.QtCore import QSettings

MODULE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_DEFAULT_PROFILES_DIR = os.path.join(os.path.dirname(__file__), "states", "default")
_USER_PROFILES_DIR = os.path.join(os.path.dirname(__file__), "states", "user")


def profiles_dir() -> str:
    client = BECClient()
    bec_widgets_settings = client._service_config.config.get("bec_widgets_settings")
    if bec_widgets_settings is not None:
        bec_widgets_setting_path = bec_widgets_settings.get("base_path")
    else:
        bec_widgets_setting_path = None
    if bec_widgets_setting_path:
        default_path = os.path.join(bec_widgets_setting_path, "profiles")
    else:
        default_path = _USER_PROFILES_DIR

    path = os.environ.get("BECWIDGETS_PROFILE_DIR", default_path)
    os.makedirs(path, exist_ok=True)
    return path


def profile_path(name: str) -> str:
    return os.path.join(profiles_dir(), f"{name}.ini")


SETTINGS_KEYS = {
    "geom": "mainWindow/Geometry",
    "state": "mainWindow/State",
    "ads_state": "mainWindow/DockingState",
    "manifest": "manifest/widgets",
    "readonly": "profile/readonly",
}


def list_profiles() -> list[str]:
    return sorted(os.path.splitext(f)[0] for f in os.listdir(profiles_dir()) if f.endswith(".ini"))


def is_profile_readonly(name: str) -> bool:
    """Check if a profile is marked as read-only."""
    settings = open_settings(name)
    return settings.value(SETTINGS_KEYS["readonly"], False, type=bool)


def set_profile_readonly(name: str, readonly: bool) -> None:
    """Set the read-only status of a profile."""
    settings = open_settings(name)
    settings.setValue(SETTINGS_KEYS["readonly"], readonly)
    settings.sync()


def open_settings(name: str) -> QSettings:
    return QSettings(profile_path(name), QSettings.IniFormat)


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
