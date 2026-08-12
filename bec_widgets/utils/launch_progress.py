"""Client side of the BEC launch-progress handshake.

When ``bec_launcher`` starts a GUI it opens a per-launch AF_UNIX socket and passes
its path plus a one-shot token to the child through the environment. The child
streams startup-stage updates and a final ``ready`` edge back over that socket so
the launcher can show a live loading banner instead of a blind spinner.

The whole thing is best-effort and must *never* interfere with startup:

* if the environment variables are absent (app started outside the launcher) every
  call is a cheap no-op returning ``False``;
* any socket error disables the client for the rest of the process and is swallowed.

The module deliberately depends only on the standard library (no Qt, no bec_lib
heavy imports) because it is imported by :mod:`startup_profiler` *before* the
QApplication and the heavy widget imports exist.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading

SOCKET_ENV = "BEC_LAUNCH_PROGRESS_SOCKET"
TOKEN_ENV = "BEC_LAUNCH_PROGRESS_TOKEN"
APP_ENV = "BEC_LAUNCH_APP"

_CONNECT_TIMEOUT_S = 0.75
_SEND_TIMEOUT_S = 0.75


class LaunchProgressClient:
    """Best-effort AF_UNIX client that streams startup stages to the launcher."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sock: socket.socket | None = None
        # Tri-state: None = not yet attempted, True = live, False = disabled.
        self._live: bool | None = None
        self._hello_sent = False
        self._path = os.environ.get(SOCKET_ENV) or ""
        self._token = os.environ.get(TOKEN_ENV) or ""

    # -- public API ---------------------------------------------------------
    @property
    def enabled(self) -> bool:
        """True when the launcher provided a socket + token for this launch."""
        return bool(self._path and self._token and self._live is not False)

    def emit_stage(self, name: str, delta_ms: float, total_ms: float) -> bool:
        return self._send(
            {
                "t": "stage",
                "name": name,
                "delta_ms": round(float(delta_ms), 1),
                "total_ms": round(float(total_ms), 1),
            }
        )

    def emit_ready(self, total_ms: float | None = None) -> bool:
        payload: dict[str, object] = {"t": "ready"}
        if total_ms is not None:
            payload["total_ms"] = round(float(total_ms), 1)
        return self._send(payload)

    def emit_error(self, message: str) -> bool:
        return self._send({"t": "error", "msg": str(message)})

    def close(self) -> None:
        with self._lock:
            self._disconnect_locked()
            self._live = False

    # -- internals ----------------------------------------------------------
    def _send(self, payload: dict[str, object]) -> bool:
        if not (self._path and self._token):
            return False
        with self._lock:
            if self._live is False:
                return False
            if self._sock is None and not self._connect_locked():
                return False
            line = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
            try:
                self._sock.sendall(line)  # type: ignore[union-attr]
                return True
            except OSError:
                self._disconnect_locked()
                self._live = False
                return False

    def _connect_locked(self) -> bool:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(_CONNECT_TIMEOUT_S)
            sock.connect(self._path)
            sock.settimeout(_SEND_TIMEOUT_S)
        except OSError:
            self._live = False
            return False
        self._sock = sock
        self._live = True
        if not self._hello_sent:
            hello = {
                "t": "hello",
                "token": self._token,
                "app": os.environ.get(APP_ENV) or _default_app_name(),
                "pid": os.getpid(),
            }
            try:
                sock.sendall((json.dumps(hello, separators=(",", ":")) + "\n").encode("utf-8"))
                self._hello_sent = True
            except OSError:
                self._disconnect_locked()
                self._live = False
                return False
        return True

    def _disconnect_locked(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None


def _default_app_name() -> str:
    argv0 = sys.argv[0] if sys.argv else ""
    return os.path.basename(argv0) or "bec"


# Process-wide singleton; env is read once at import time.
launch_progress = LaunchProgressClient()
