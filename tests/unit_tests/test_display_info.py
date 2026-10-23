"""Tests for diagnostics collected from the GUI process."""

import json
import os
import sys

from qtpy.QtWidgets import QWidget

from bec_widgets.utils.display_info import get_display_info


def test_display_info_uses_loaded_backend_not_environment(qapp, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "different-from-loaded-backend")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    monkeypatch.setenv("QT_PLUGIN_PATH", "/another/qt/plugins")
    monkeypatch.setenv("UNRELATED_SECRET", "not-for-diagnostics")

    info = get_display_info()

    assert info["qt_platform"] == qapp.platformName()
    assert info["pid"] == os.getpid()
    assert info["python_executable"] == sys.executable
    assert info["qt_library_paths"] == qapp.libraryPaths()
    assert info["environment"]["QT_QPA_PLATFORM"] == "different-from-loaded-backend"
    assert info["environment"]["XDG_CURRENT_DESKTOP"] == "GNOME"
    assert info["environment"]["QT_PLUGIN_PATH"] == "/another/qt/plugins"
    assert "UNRELATED_SECRET" not in info["environment"]
    json.dumps(info)


def test_display_info_reports_visibility_without_changing_windows(qtbot, qapp):
    window = QWidget()
    qtbot.addWidget(window)
    window.setObjectName("display_info_test")
    window.show()
    qapp.processEvents()

    for visible in (True, False):
        window.setVisible(visible)
        info = get_display_info()
        state = next(item for item in info["windows"] if item["object_name"] == window.objectName())
        assert state["visible"] is visible
        assert state["minimized"] is False
        assert window.isVisible() is visible

    unshown = QWidget()
    qtbot.addWidget(unshown)
    assert unshown.windowHandle() is None
    get_display_info()
    assert unshown.windowHandle() is None
