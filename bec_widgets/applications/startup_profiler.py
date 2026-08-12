"""Lightweight startup stage profiler for ``bec-app``.

Logs, for each startup stage, the time since the previous mark and the
cumulative time since process start. A slow/cold start can then be localised
straight from the logs to one of the three cost centres:

* ``module imports``  -> Python import + bytecode + NFS read cost
* ``BEC connection``  -> BEC client / Redis round-trips (dominates when Redis is remote)
* per-view marks      -> widget construction (and any Redis/config the view loads)

Example log::

    [startup] module imports          +6.21s   (total  6.21s)
    [startup] QApplication            +0.34s   (total  6.55s)
    [startup] BEC connection          +18.40s  (total 25.07s)   <- remote Redis
    [startup] DeviceManagerView       +2.10s   (total 27.47s)
    [startup] interactive             +0.06s   (total 27.71s)

The origin is captured at *first import* of this module. ``main_app`` imports it
before its heavy imports, so ``module imports`` covers the real import cost.

Set ``BEC_STARTUP_PROFILE=0`` to silence the output.
"""

from __future__ import annotations

import os
import time

# Captured the moment this module is first imported (before main_app's heavy
# imports run), so it approximates the start of the bec-app import phase.
_ORIGIN = time.perf_counter()

try:
    from bec_lib import bec_logger

    _logger = bec_logger.logger
except Exception:  # pragma: no cover - logging must never break startup
    _logger = None

try:
    # Stdlib-only client: streams the marks below to bec_launcher's loading banner
    # when this process was started by the launcher. A no-op otherwise.
    from bec_widgets.utils.launch_progress import launch_progress
except Exception:  # pragma: no cover - progress streaming must never break startup
    launch_progress = None


def _emit(msg: str) -> None:
    if _logger is not None:
        _logger.info(msg)
    else:  # pragma: no cover
        print(msg, flush=True)


class StartupProfiler:
    """Records named stage timings relative to a fixed origin."""

    def __init__(self, origin: float) -> None:
        self._origin = origin
        self._last = origin
        self._enabled = os.environ.get("BEC_STARTUP_PROFILE", "1").lower() not in (
            "0",
            "false",
            "no",
        )

    def reset(self, origin: float | None = None) -> None:
        """Re-anchor the origin (e.g. to a perf_counter captured even earlier)."""
        self._origin = time.perf_counter() if origin is None else origin
        self._last = self._origin

    def mark(self, stage: str, *, final: bool = False) -> float:
        """Log elapsed-since-last and total-since-origin for ``stage``.

        Returns the cumulative time so callers may use it programmatically.
        """
        now = time.perf_counter()
        delta = now - self._last
        total = now - self._origin
        self._last = now
        if self._enabled:
            _emit(f"[startup] {stage:<26} +{delta:6.2f}s   (total {total:6.2f}s)")
            if final:
                _emit(f"[startup] ---- bec-app interactive after {total:.2f}s ----")
        if launch_progress is not None:
            # Best-effort; the client swallows all socket errors internally.
            launch_progress.emit_stage(stage, delta * 1000.0, total * 1000.0)
        return total


startup_profiler = StartupProfiler(_ORIGIN)
