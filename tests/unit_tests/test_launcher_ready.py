"""Unit tests for ``notify_launcher_ready`` (routes the ready edge over the socket)."""

from __future__ import annotations

import os
import socket

from bec_widgets.utils import launcher_ready
from bec_widgets.utils.launch_progress import LaunchProgressClient


def _short_socket_path() -> str:
    return f"/tmp/bec-ready-{os.getpid()}.sock"


def test_notify_launcher_ready_noops_without_env(monkeypatch):
    monkeypatch.delenv("BEC_LAUNCH_PROGRESS_SOCKET", raising=False)
    monkeypatch.delenv("BEC_LAUNCH_PROGRESS_TOKEN", raising=False)
    # A freshly-built client with no configured socket is disabled -> notify no-ops.
    monkeypatch.setattr(launcher_ready, "launch_progress", LaunchProgressClient())

    assert launcher_ready.notify_launcher_ready("bec-app") is False


def test_notify_launcher_ready_sends_ready(monkeypatch):
    path = _short_socket_path()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.settimeout(2.0)
    # A crashed previous run (with pid reuse) can leave the socket file behind,
    # which would make bind() fail with "Address already in use".
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    srv.bind(path)
    srv.listen(1)
    try:
        monkeypatch.setenv("BEC_LAUNCH_PROGRESS_SOCKET", path)
        monkeypatch.setenv("BEC_LAUNCH_PROGRESS_TOKEN", "tok-xyz")
        monkeypatch.setattr(launcher_ready, "launch_progress", LaunchProgressClient())

        assert launcher_ready.notify_launcher_ready("bec-app") is True

        conn, _ = srv.accept()
        conn.settimeout(2.0)
        data = conn.recv(65536).decode()
        conn.close()
        assert '"t":"hello"' in data
        assert '"token":"tok-xyz"' in data
        assert '"t":"ready"' in data
    finally:
        srv.close()
        try:
            os.unlink(path)
        except OSError:
            pass
