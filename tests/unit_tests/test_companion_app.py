"""Unit tests for the GUI-server startup handshake wiring in companion_app."""

from __future__ import annotations

from types import SimpleNamespace

from bec_widgets.applications import companion_app


def _server(**overrides):
    args = SimpleNamespace(
        config=None, id="test", gui_class=None, gui_class_id="bec", hide=False, **overrides
    )
    return companion_app.GUIServer(args)


def test_notify_server_ready_resolves_launcher(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "bec_widgets.utils.launcher_ready.notify_launcher_ready",
        lambda app_name, window: calls.append((app_name, window)) or True,
    )
    marks = []
    monkeypatch.setattr(
        companion_app.startup_profiler, "mark", lambda stage, **kw: marks.append((stage, kw))
    )

    server = _server()
    sentinel_window = object()
    server.launcher_window = sentinel_window
    server._notify_server_ready()

    # The GUI-server path sends the ready edge itself (safety net for launches with no
    # auto-launched gui_class window) and records the final startup stage.
    assert calls == [("bec-gui-server", sentinel_window)]
    assert ("interactive", {"final": True}) in marks
