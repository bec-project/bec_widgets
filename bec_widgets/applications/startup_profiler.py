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


# --- cold-start (bytecode cache) detection ---------------------------------
#
# On the very first launch (or after a Python/env update) the interpreter has to
# compile every imported module to bytecode, which dominates the "module imports"
# stage — especially on NFS. We sample a few files from the heavy pure-Python
# packages *before* importing them and report the cache hit-rate to the launcher,
# so its banner can tell the user why the first start takes longer.

_PROBE_PACKAGES = ("bec_widgets", "bec_lib", "pyqtgraph", "qtpy")


def _bytecode_cache_status(max_files_per_pkg: int = 40) -> tuple[int, int]:
    """Return ``(checked, cached)`` counts for sampled .py files of the heavy packages.

    Uses ``importlib.util.find_spec`` (locates without executing the modules) and
    ``cache_from_source``; capped per package so the probe stays cheap even on NFS.
    """
    import importlib.util

    checked = cached = 0
    for pkg in _PROBE_PACKAGES:
        try:
            spec = importlib.util.find_spec(pkg)
        except (ImportError, ValueError):
            continue
        if spec is None or not spec.origin or not spec.origin.endswith(".py"):
            continue
        sampled = 0
        for root, _dirs, files in os.walk(os.path.dirname(spec.origin)):
            for name in files:
                if not name.endswith(".py"):
                    continue
                try:
                    cache = importlib.util.cache_from_source(os.path.join(root, name))
                except (ValueError, NotImplementedError):
                    continue
                checked += 1
                if os.path.exists(cache):
                    cached += 1
                sampled += 1
                if sampled >= max_files_per_pkg:
                    break
            if sampled >= max_files_per_pkg:
                break
    return checked, cached


def _report_bytecode_cache() -> None:
    """Stream the cache status to the launcher banner. Never breaks startup."""
    if launch_progress is None or not launch_progress.enabled:
        return
    try:
        checked, cached = _bytecode_cache_status()
        if not checked:
            return
        pct = round(100 * cached / checked)
        launch_progress.emit_info(cold_start=pct < 50, bytecode_cached_pct=pct)
    except Exception:  # pragma: no cover - diagnostics must never break startup
        pass


# Runs at first import, i.e. before main_app/companion_app perform their heavy
# imports — the launcher learns about a cold start while those imports run.
_report_bytecode_cache()
