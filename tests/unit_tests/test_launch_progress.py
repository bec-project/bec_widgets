"""Unit tests for the launch-progress socket client (child side)."""

from __future__ import annotations

import json
import os
import socket

import pytest

from bec_widgets.utils import launch_progress as lp


def _short_socket_path(suffix: str = "") -> str:
    # AF_UNIX paths are length-limited (~104 on macOS); keep it short and under /tmp.
    return f"/tmp/bec-lp-{os.getpid()}-{suffix or 'x'}.sock"


class _Server:
    """Minimal single-connection AF_UNIX server for assertions."""

    def __init__(self, path: str):
        self.path = path
        self._srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._srv.settimeout(2.0)
        self._srv.bind(path)
        self._srv.listen(1)
        self._conn: socket.socket | None = None

    def read_lines(self) -> list[dict]:
        if self._conn is None:
            self._conn, _ = self._srv.accept()
            self._conn.settimeout(2.0)
        chunks = b""
        while True:
            try:
                data = self._conn.recv(65536)
            except socket.timeout:
                break
            if not data:
                break
            chunks += data
            # Heuristic: stop once we have drained what's buffered.
            if len(data) < 65536:
                break
        return [json.loads(line) for line in chunks.decode().splitlines() if line.strip()]

    def close(self) -> None:
        for sock in (self._conn, self._srv):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
        try:
            os.unlink(self.path)
        except OSError:
            pass


@pytest.fixture
def server():
    srv = _Server(_short_socket_path("srv"))
    try:
        yield srv
    finally:
        srv.close()


def _client_env(monkeypatch, path: str, token: str = "tok-123", app: str = "bec-app"):
    monkeypatch.setenv(lp.SOCKET_ENV, path)
    monkeypatch.setenv(lp.TOKEN_ENV, token)
    monkeypatch.setenv(lp.APP_ENV, app)


def test_client_is_noop_without_env(monkeypatch):
    monkeypatch.delenv(lp.SOCKET_ENV, raising=False)
    monkeypatch.delenv(lp.TOKEN_ENV, raising=False)
    client = lp.LaunchProgressClient()
    assert client.enabled is False
    assert client.emit_stage("module imports", 10, 10) is False
    assert client.emit_ready() is False


def test_client_streams_hello_stage_and_ready(monkeypatch, server):
    _client_env(monkeypatch, server.path, token="tok-abc", app="bec-app")
    client = lp.LaunchProgressClient()
    assert client.enabled is True

    assert client.emit_stage("module imports", 6210.4, 6210.4) is True
    assert client.emit_stage("BEC connection", 18400.0, 24610.4) is True
    assert client.emit_ready(27710.0) is True

    messages = server.read_lines()
    assert messages[0]["t"] == "hello"
    assert messages[0]["token"] == "tok-abc"
    assert messages[0]["app"] == "bec-app"
    assert messages[0]["pid"] == os.getpid()

    stages = [m for m in messages if m["t"] == "stage"]
    assert [s["name"] for s in stages] == ["module imports", "BEC connection"]
    assert stages[0]["delta_ms"] == 6210.4
    assert stages[0]["total_ms"] == 6210.4

    ready = [m for m in messages if m["t"] == "ready"]
    assert ready and ready[0]["total_ms"] == 27710.0


def test_client_never_raises_on_bad_socket(monkeypatch):
    _client_env(monkeypatch, _short_socket_path("nonexistent"))
    client = lp.LaunchProgressClient()
    # No server is listening at the path -> connect fails, but nothing raises.
    assert client.emit_stage("module imports", 1, 1) is False
    assert client.enabled is False  # disabled after the failed connect
    assert client.emit_ready() is False


def test_client_disables_after_server_disconnect(monkeypatch, server):
    _client_env(monkeypatch, server.path)
    client = lp.LaunchProgressClient()
    assert client.emit_stage("first", 1, 1) is True
    # Force the server to drop the connection.
    server.read_lines()
    server.close()
    # Subsequent sends eventually fail and disable the client without raising.
    for _ in range(5):
        client.emit_stage("later", 2, 2)
    assert client.emit_ready() is False
