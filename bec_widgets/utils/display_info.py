"""Read-only Qt display diagnostics collected inside the GUI process."""

from __future__ import annotations

import os
import sys
from importlib.metadata import version

from qtpy import API_NAME
from qtpy.QtCore import qVersion
from qtpy.QtWidgets import QApplication

import bec_widgets

DISPLAY_ENVIRONMENT_VARIABLES = (
    "XDG_SESSION_TYPE",
    "XDG_CURRENT_DESKTOP",
    "XDG_SESSION_DESKTOP",
    "DESKTOP_SESSION",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "QT_API",
    "QT_QPA_PLATFORM",
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    "QT_PLUGIN_PATH",
    "QT_QPA_PLATFORMTHEME",
    "QT_QPA_GENERIC_PLUGINS",
    "QT_STYLE_OVERRIDE",
    "QT_WAYLAND_SHELL_INTEGRATION",
    "QT_WAYLAND_DISABLE_WINDOWDECORATION",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
)


def get_display_info() -> dict:
    """Return the GUI process's loaded Qt backend, environment hints, and window states.

    Must run in the Qt GUI thread. Environment variables describe the inherited session;
    ``qt_platform`` identifies the platform plugin actually loaded by this application.
    Qt has no portable API for identifying the Wayland compositor.

    Returns:
        dict: JSON-serializable diagnostics without modifying any window or environment setting.
    """
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("Display diagnostics require a running QApplication.")

    windows = []
    for widget in app.topLevelWidgets():
        handle = widget.windowHandle()
        # Ignore internal widgets without a native window; do not create one to inspect it.
        if handle is None:
            continue
        windows.append(
            {
                "object_name": widget.objectName(),
                "title": widget.windowTitle(),
                "visible": widget.isVisible(),
                "minimized": widget.isMinimized(),
                "maximized": widget.isMaximized(),
                "full_screen": widget.isFullScreen(),
                "active": widget.isActiveWindow(),
                "exposed": handle.isExposed(),
                "flags": str(widget.windowFlags()),
                "geometry": list(widget.geometry().getRect()),
                "screen": handle.screen().name() if handle.screen() is not None else None,
            }
        )

    return {
        "pid": os.getpid(),
        "os": sys.platform,
        "python_executable": sys.executable,
        "bec_widgets_version": version("bec_widgets"),
        "bec_widgets_path": bec_widgets.__file__,
        "qt_version": qVersion(),
        "qt_binding": API_NAME,
        "qt_platform": app.platformName(),
        "qt_library_paths": app.libraryPaths(),
        "qt_style": app.style().objectName(),
        "environment": {name: os.environ.get(name) for name in DISPLAY_ENVIRONMENT_VARIABLES},
        "screens": [
            {
                "name": screen.name(),
                "geometry": list(screen.geometry().getRect()),
                "available_geometry": list(screen.availableGeometry().getRect()),
                "device_pixel_ratio": screen.devicePixelRatio(),
            }
            for screen in app.screens()
        ],
        "windows": sorted(windows, key=lambda window: (window["object_name"], window["title"])),
    }
